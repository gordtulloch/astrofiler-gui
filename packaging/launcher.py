"""PyInstaller entry point.

AstroFiler keeps its database, astrofiler.ini, log and stylesheets/images relative to the current
directory, which is read-only (or meaningless) for an installed app.  The frozen app therefore runs
from a per-user data folder, seeded with the bundled css/ and images/, and then hands over to the
bundled astrofiler.py exactly as `python astrofiler.py` would.

`--selftest <report-file>` imports the heavy dependencies and checks the bundled data, then exits;
CI uses it to prove the frozen app is complete.
"""
import os
import runpy
import shutil
import sys
from pathlib import Path

BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "AstroFiler"


def prepare_workdir() -> Path:
    work = data_dir()
    work.mkdir(parents=True, exist_ok=True)
    for name in ("css", "images"):
        src = BUNDLE / name
        if src.is_dir():
            shutil.copytree(src, work / name, dirs_exist_ok=True)
    os.chdir(work)
    os.environ.setdefault("ASTROFILER_DB_PATH", str(work / "astrofiler.db"))
    os.environ.setdefault("ASTROFILER_MIGRATIONS_DIR", str(BUNDLE / "migrations"))
    return work


def selftest(report: Path) -> int:
    lines, ok = [], True
    # A stray bundle/src would be put first on sys.path by astrofiler.py and shadow the frozen package.
    shadow = (BUNDLE / "src").exists()
    ok &= not shadow
    lines.append(f"{'FAIL ' if shadow else 'ok   '} no src/ shadow folder in bundle")
    for mod in ("astrofiler.exceptions", "astrofiler.types", "PySide6.QtWidgets", "astropy.io.fits", "peewee", "peewee_migrate", "numpy", "scipy",
                "matplotlib", "PIL", "lz4.frame", "smb.SMBConnection", "google.cloud.storage",
                "reproject", "sep", "astroalign", "photutils", "astrofiler.database",
                "astrofiler.ui.main_window"):
        try:
            __import__(mod)
            lines.append(f"ok    {mod}")
        except Exception as exc:  # noqa: BLE001 - report every failure, not just the first
            ok = False
            lines.append(f"FAIL  {mod}: {exc!r}")
    mig = Path(os.environ["ASTROFILER_MIGRATIONS_DIR"])
    n = len(list(mig.glob("[0-9]*.py"))) if mig.is_dir() else 0
    if n == 0:
        ok = False
    lines.append(f"{'ok   ' if n else 'FAIL '} migrations: {n} files in {mig}")
    for rel in ("css/dark.css", "css/light.css", "astrofiler.png", "astrofiler.py"):
        present = (BUNDLE / rel).exists()
        ok &= present
        lines.append(f"{'ok   ' if present else 'FAIL '} bundled {rel}")
    lines.append("SELFTEST OK" if ok else "SELFTEST FAILED")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    prepare_workdir()
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        sys.exit(selftest(Path(sys.argv[2])))
    script = BUNDLE / "astrofiler.py"
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")
