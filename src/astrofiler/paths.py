"""Locations of AstroFiler's per-user files and bundled resources.

Nothing here depends on the current working directory, so the app behaves the
same no matter where it is launched from.

Application directory (holds ``astrofiler.ini``, ``astrofiler.db``, ``astrofiler.log``):

1. ``$ASTROFILER_HOME`` if set.
2. The project root when running from a source checkout or an editable install
   (a ``pyproject.toml`` next to ``src/astrofiler``). This is where the install
   scripts and ``python astrofiler.py`` have always kept these files.
3. Otherwise a per-user directory: ``%APPDATA%\\AstroFiler`` on Windows,
   ``~/Library/Application Support/AstroFiler`` on macOS,
   ``$XDG_CONFIG_HOME/astrofiler`` (default ``~/.config/astrofiler``) elsewhere.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

CONFIG_FILENAME = "astrofiler.ini"
DATABASE_FILENAME = "astrofiler.db"
LOG_FILENAME = "astrofiler.log"

_PACKAGE_DIR = Path(__file__).resolve().parent
_RESOURCES_DIR = _PACKAGE_DIR / "resources"


def _source_checkout_root() -> Path | None:
    """Return the project root if this package is running from a source checkout."""
    root = _PACKAGE_DIR.parent.parent
    if (root / "pyproject.toml").is_file() and (root / "src" / "astrofiler").is_dir():
        return root
    return None


def _user_app_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "AstroFiler"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AstroFiler"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "astrofiler"


def _resolve_app_dir() -> Path:
    override = os.environ.get("ASTROFILER_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (_source_checkout_root() or _user_app_dir()).resolve()


def get_app_dir() -> Path:
    """Directory holding the config file, database and log. Created if it doesn't exist."""
    app_dir = _resolve_app_dir()
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_config_path() -> Path:
    return get_app_dir() / CONFIG_FILENAME


def get_database_path() -> Path:
    """SQLite database path. ``ASTROFILER_DB_PATH`` overrides the default location."""
    override = os.environ.get("ASTROFILER_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return get_app_dir() / DATABASE_FILENAME


def get_log_path() -> Path:
    return get_app_dir() / LOG_FILENAME


def default_repo_folder() -> str:
    """Repository folder used when ``repo`` isn't set in astrofiler.ini.

    Deliberately ``<cwd>/REPOSITORY`` rather than the working directory itself, so
    the repository's ``Light/``, ``Calibrate/``, ``Masters/``... folders are never
    created loose in the root folder. (Unlike the config/DB/log, this follows the
    working directory; from the project root it is git-ignored.)
    """
    return os.path.join(os.getcwd(), "REPOSITORY")


def default_source_folder() -> str:
    """Incoming folder used when ``source`` isn't set in astrofiler.ini: ``<cwd>/REPOSITORY.incoming``."""
    return os.path.join(os.getcwd(), "REPOSITORY.incoming")


def resource_path(*parts: str) -> Path:
    """Path to a file bundled inside the package (``astrofiler/resources/...``)."""
    return _RESOURCES_DIR.joinpath(*parts)


# Default for ``config_path`` parameters. Evaluated once at import time, so set
# ASTROFILER_HOME before importing astrofiler if you need to override it.
DEFAULT_CONFIG_PATH = str(_resolve_app_dir() / CONFIG_FILENAME)
