#!/usr/bin/env python3
"""Freeze AstroFiler into a self-contained one-folder app with PyInstaller.

Run from the repo root on the platform being targeted (PyInstaller cannot cross-compile):

    pip install -r requirements.txt -e . pyinstaller
    python packaging/build.py

Output: dist/AstroFiler/ (Windows, Linux) or dist/AstroFiler.app (macOS).  The per-platform
wrappers (windows/astrofiler.iss, macos/build_dmg.sh, linux/build_appimage.sh) turn that
into the single installable file.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
SEP = ";" if sys.platform == "win32" else ":"


def make_icns(out: Path) -> bool:
    """Build an .icns from astrofiler.png with macOS sips/iconutil."""
    iconset = out.with_suffix(".iconset")
    iconset.mkdir(parents=True, exist_ok=True)
    try:
        for size in (16, 32, 64, 128, 256, 512):
            for scale, px in ((1, size), (2, size * 2)):
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                subprocess.run(["sips", "-z", str(px), str(px), str(ROOT / "astrofiler.png"),
                                "--out", str(iconset / name)], check=True, capture_output=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def main() -> None:
    args = [
        str(ROOT / "packaging" / "launcher.py"),
        "--name", "AstroFiler",
        "--noconfirm", "--clean",
        "--windowed",
        "--paths", str(ROOT / "src"),
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        # The launcher runs the real entry point (astrofiler.py) from the bundle root, so ship it as data.
        "--add-data", f"{ROOT / 'astrofiler.py'}{SEP}.",
        "--add-data", f"{ROOT / 'astrofiler.png'}{SEP}.",
        # astrofiler.py reads the version from this file by path.
        "--add-data", f"{ROOT / 'src' / 'astrofiler' / '__init__.py'}{SEP}src/astrofiler",
        # peewee-migrate loads these .py files from a directory at run time, so they are data, not imports.
        "--add-data", f"{ROOT / 'migrations'}{SEP}migrations",
        # Stylesheets and images are opened by relative path; the launcher copies them to the user data folder.
        "--add-data", f"{ROOT / 'css'}{SEP}css",
        "--add-data", f"{ROOT / 'images'}{SEP}images",
        "--collect-submodules", "astrofiler",
        "--collect-submodules", "peewee_migrate",
        "--collect-submodules", "smb",
        "--collect-data", "astropy",
        "--collect-data", "photutils",
        "--collect-data", "reproject",
        "--collect-data", "certifi",
        "--copy-metadata", "google-cloud-storage",
        "--hidden-import", "sep",
        "--hidden-import", "astroalign",
        "--hidden-import", "lz4.frame",
    ]
    if sys.platform == "win32":
        args += ["--icon", str(ROOT / "astrofiler.ico")]
    elif sys.platform == "darwin":
        icns = ROOT / "build" / "astrofiler.icns"
        icns.parent.mkdir(exist_ok=True)
        if make_icns(icns):
            args += ["--icon", str(icns)]
        args += ["--osx-bundle-identifier", "com.gordtulloch.astrofiler"]
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
