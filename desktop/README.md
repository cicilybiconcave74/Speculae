# Speculae Desktop (Tauri)

Native desktop wrapper for Speculae. Bundles the Flask server as a sidecar binary
and renders the existing web UI in a native webview.

## Architecture

```
speculae-desktop.exe (Tauri/Rust)
  └── spawns: speculae-web-x86_64-pc-windows-msvc.exe (PyInstaller sidecar)
        └── serves: http://127.0.0.1:7730 (Flask + index.html)
              └── rendered by: Tauri WebView2 window
```

The Rust binary:
1. Spawns `speculae-web.exe` as a managed child process
2. Polls `127.0.0.1:7730` via TCP until the Flask server is ready (max 30s)
3. Opens a native WebView2 window pointing at `http://127.0.0.1:7730`
4. Kills the child process on app exit

No Tauri IPC is used — the web frontend is completely unchanged.

## Prerequisites

- Rust stable (1.78+) with MSVC target: `rustup target list --installed`
- MSVC Build Tools 2022 (for `link.exe`)
- Windows 11 SDK (for `kernel32.lib`)
- WebView2 runtime (ships with Windows 10/11)
- `~/.cargo/config.toml` with linker and LIB paths set (done during Phase 5 setup)

## Build steps

### 1. Build the sidecar (speculae-web.exe)

The sidecar must be built before the Tauri app. From the Speculae repo root:

```powershell
pip install -e . pyinstaller
python scripts/build_exe.py
```

This produces `dist/speculae-web.exe`.

### 2. Copy the sidecar into the binaries directory

Tauri requires the sidecar binary to have the target-triple suffix:

```powershell
copy dist\speculae-web.exe desktop\binaries\speculae-web-x86_64-pc-windows-msvc.exe
```

### 3. Build the Tauri app

```powershell
cd desktop
cargo build --release
```

The output is `desktop/target/release/speculae-desktop.exe`.

### 4. Build the installer (optional)

Requires `cargo-tauri` CLI:

```powershell
cargo install tauri-cli
cargo tauri build
```

Produces an NSIS installer and MSI in `desktop/target/release/bundle/`.

## Development (without installer)

Run the Flask server manually in one terminal, then open the Tauri window:

```powershell
# Terminal 1
speculae-web

# Terminal 2 (after Flask is running)
cd desktop
cargo run
```

## Icons

Current icons are placeholders (solid ochre squares). Replace files in `icons/` with
proper artwork before a production release. See the Tauri icon guide:
https://v2.tauri.app/distribute/app-icon/

Required files:
- `icons/32x32.png`
- `icons/128x128.png`
- `icons/128x128@2x.png` (256×256)
- `icons/icon.ico`
- `icons/icon.icns` (macOS — not used on Windows but config references it)

## CI

The GitHub Actions build workflow (`.github/workflows/build.yml`) has been updated to:
1. Build `speculae-web.exe` via PyInstaller
2. Copy it to `desktop/binaries/speculae-web-x86_64-pc-windows-msvc.exe`
3. Build `speculae-desktop.exe` via `cargo build --release`
4. Upload both executables as release artifacts
