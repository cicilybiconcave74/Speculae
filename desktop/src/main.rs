// Speculae desktop wrapper.
//
// Strategy: sidecar pattern.
//   1. Spawn `speculae-journal` (the PyInstaller-compiled Flask server) as a sidecar.
//   2. Poll http://127.0.0.1:7730/api/stats until Flask is ready (max 30s).
//   3. Open a Tauri webview window pointing at http://127.0.0.1:7730.
//   4. When the last window closes, send SIGTERM to the sidecar.
//
// The webview renders the existing single-page frontend unchanged.
// No Tauri IPC is used — the app is purely a native shell around the
// existing web interface.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use std::thread;

use tauri::{AppHandle, Manager, RunEvent};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

const SERVER_PORT: u16 = 7730;
const READY_TIMEOUT_SECS: u64 = 30;
const POLL_INTERVAL_MS: u64 = 200;

/// Poll `127.0.0.1:7730` via TCP connect until the port accepts connections
/// or the timeout is reached. Returns `true` if the server came up in time.
fn wait_for_server(timeout: Duration) -> bool {
    let start = Instant::now();
    let addr = format!("127.0.0.1:{}", SERVER_PORT);
    loop {
        if TcpStream::connect(&addr).is_ok() {
            return true;
        }
        if start.elapsed() >= timeout {
            return false;
        }
        thread::sleep(Duration::from_millis(POLL_INTERVAL_MS));
    }
}

fn main() {
    // Hold the sidecar child process handle so we can kill it on exit.
    let sidecar_child: Arc<Mutex<Option<CommandChild>>> = Arc::new(Mutex::new(None));
    let sidecar_child_clone = Arc::clone(&sidecar_child);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let app_handle: AppHandle = app.handle().clone();

            // Spawn the sidecar. Tauri resolves the binary from
            // the `externalBin` path declared in tauri.conf.json.
            // The sidecar name must match without the target-triple suffix.
            let shell = app_handle.shell();
            let (mut rx, child) = shell
                .sidecar("speculae-journal")
                .expect("speculae-journal sidecar not found — did you copy the exe to desktop/binaries/?")
                .spawn()
                .expect("failed to spawn speculae-journal sidecar");

            // Store the child handle so we can kill it on app exit.
            {
                let mut guard = sidecar_child_clone.lock().unwrap();
                *guard = Some(child);
            }

            // Drain sidecar stdout/stderr in a background thread so the
            // internal pipe buffer never fills up and blocks the server.
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            // In debug builds, mirror server logs to the console.
                            #[cfg(debug_assertions)]
                            eprintln!("[speculae-journal] {}", String::from_utf8_lossy(&line));
                            #[cfg(not(debug_assertions))]
                            let _ = line;
                        }
                        CommandEvent::Stderr(line) => {
                            #[cfg(debug_assertions)]
                            eprintln!("[speculae-journal stderr] {}", String::from_utf8_lossy(&line));
                            #[cfg(not(debug_assertions))]
                            let _ = line;
                        }
                        CommandEvent::Error(e) => {
                            eprintln!("[speculae-journal] process error: {e}");
                            break;
                        }
                        CommandEvent::Terminated(status) => {
                            eprintln!(
                                "[speculae-journal] process terminated (code={:?})",
                                status.code
                            );
                            break;
                        }
                        _ => {}
                    }
                }
            });

            // Wait for Flask to accept connections before opening the window.
            // This runs on the setup thread (not async) — it's a brief spin poll.
            let timeout = Duration::from_secs(READY_TIMEOUT_SECS);
            if !wait_for_server(timeout) {
                // Server didn't come up in time. Kill the sidecar and bail.
                if let Ok(mut guard) = sidecar_child_clone.lock() {
                    if let Some(child) = guard.take() {
                        let _ = child.kill();
                    }
                }
                return Err("speculae-journal server did not start within 30 seconds".into());
            }

            // Open the main window. The URL is the local Flask server.
            // The window was pre-declared in tauri.conf.json; navigate it now.
            let url = format!("http://127.0.0.1:{}", SERVER_PORT);
            if let Some(win) = app_handle.get_webview_window("main") {
                win.navigate(url.parse().expect("invalid server URL"))
                    .expect("failed to navigate webview");
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building Tauri application")
        .run(move |_app, event| {
            // Kill the sidecar when the application exits.
            if let RunEvent::Exit = event {
                if let Ok(mut guard) = sidecar_child.lock() {
                    if let Some(child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        });
}
