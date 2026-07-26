"""
Build a standalone speculae-journal.exe using PyInstaller.

Usage:
    python scripts/build_exe.py

Output: dist/speculae-journal.exe
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = ROOT / "dist"
SPEC = HERE / "speculae-journal.spec"


def main():
    print("  o  building speculae-journal.exe ...\n")

    # ensure PyInstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("  Installing PyInstaller ...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"]
        )

    # clean previous builds
    for p in [DIST, ROOT / "build", SPEC]:
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    src = ROOT / "src"
    # build
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--name", "speculae-journal",
        "--onefile",
        "--noconsole",
        "--icon", str(ROOT / "desktop" / "icons" / "icon.ico"),
        "--add-data", f"{src / 'speculae/web'}{os.pathsep}speculae/web",
        "--hidden-import", "flask",
        "--hidden-import", "speculae.config",
        "--hidden-import", "speculae.db",
        "--hidden-import", "speculae.patterns",
        "--hidden-import", "speculae.insights",
        "--hidden-import", "speculae.models",
        "--distpath", str(DIST),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(HERE),
        str(src / "speculae" / "web" / "server.py"),
    ])

    exe = DIST / "speculae-journal.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\n  done.  {exe}  ({size_mb:.1f} MB)")
    else:
        print("\n  build failed — no exe produced")
        sys.exit(1)


if __name__ == "__main__":
    main()
