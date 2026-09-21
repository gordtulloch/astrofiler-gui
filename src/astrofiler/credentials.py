"""Storage for secrets (currently the iTelescope password).

Secrets are kept in the operating system's credential store via the ``keyring``
package (Windows Credential Manager, macOS Keychain, Secret Service/KWallet on
Linux) instead of as plain text in ``astrofiler.ini``.

* Reading: the keyring is consulted first. If the ini file still holds a
  plain-text value (an older install), it is moved into the keyring and removed
  from the file.
* Writing: stored in the keyring and removed from the ini file.
* No usable keyring (e.g. a headless Linux box, or ``keyring`` not installed, or
  ``ASTROFILER_DISABLE_KEYRING=1``): the value stays in the ini file as before,
  a warning is logged once, and the file is restricted to the current user where
  the platform supports it.
"""

from __future__ import annotations

import logging
import os
import re
import stat
import sys
from pathlib import Path
from typing import Optional

from .paths import get_config_path

logger = logging.getLogger(__name__)

SERVICE_NAME = "AstroFiler"
ITELESCOPE_PASSWORD = "itelescope_password"

_warned_no_keyring = False


def _backend():
    """Return the keyring module if a real backend is available, else None."""
    if os.environ.get("ASTROFILER_DISABLE_KEYRING"):
        return None
    try:
        import keyring
        from keyring.backends import fail, null
    except ImportError:
        return None
    try:
        active = keyring.get_keyring()
    except Exception:  # a broken backend must not stop the app
        return None
    if isinstance(active, (fail.Keyring, null.Keyring)):
        return None
    return keyring


def keyring_available() -> bool:
    return _backend() is not None


def _warn_no_keyring_once() -> None:
    global _warned_no_keyring
    if not _warned_no_keyring:
        _warned_no_keyring = True
        logger.warning(
            "No system keyring is available; the iTelescope password is stored in plain text in "
            "astrofiler.ini. Install the 'keyring' package (and a backend such as Secret Service on "
            "Linux) to store it securely."
        )


def _scrub_ini_option(option: str, config_path: Optional[str] = None) -> None:
    """Remove ``option`` from the ini file line by line, preserving comments and layout."""
    path = Path(config_path) if config_path else get_config_path()
    if not path.is_file():
        return
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    pattern = re.compile(r"^[ \t]*" + re.escape(option) + r"[ \t]*[=:].*(?:\r?\n|$)", re.IGNORECASE | re.MULTILINE)
    scrubbed = pattern.sub("", text)
    if scrubbed != text:
        path.write_bytes(scrubbed.encode("utf-8"))


def protect_config_file(config_path: Optional[str] = None) -> None:
    """Restrict the ini file to the current user (POSIX only; Windows profile ACLs already do this)."""
    if sys.platform == "win32":
        return
    path = Path(config_path) if config_path else get_config_path()
    try:
        if path.is_file():
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError as e:
        logger.debug(f"Could not restrict permissions on {path}: {e}")


def get_ini_secret(config, option: str, config_path: Optional[str] = None) -> str:
    """Return a secret, preferring the keyring; migrates a legacy plain-text ini value.

    ``config`` is an already-loaded ``ConfigParser``; ``config_path`` is the file it
    came from (defaults to the application config file).
    """
    legacy = (config.get("DEFAULT", option, fallback="") or "").strip()
    keyring = _backend()
    if keyring is None:
        if legacy:
            _warn_no_keyring_once()
        return legacy

    try:
        stored = keyring.get_password(SERVICE_NAME, option)
    except Exception as e:
        logger.warning(f"Could not read '{option}' from the system keyring: {e}")
        return legacy
    if stored:
        if legacy:
            _scrub_ini_option(option, config_path)  # leftover plain-text copy
        return stored

    if legacy:
        try:
            keyring.set_password(SERVICE_NAME, option, legacy)
        except Exception as e:
            logger.warning(f"Could not move '{option}' into the system keyring: {e}")
            return legacy
        _scrub_ini_option(option, config_path)
        logger.info(f"Moved '{option}' from astrofiler.ini into the system keyring.")
    return legacy


def store_ini_secret(config, option: str, value: str) -> bool:
    """Store a secret. Returns True if it went into the keyring (and was removed from ``config``).

    When there is no keyring the value is set on ``config`` (plain text, as before) and
    False is returned; the caller writes the file, then should call ``protect_config_file``.
    An empty value clears the secret everywhere.
    """
    value = (value or "").strip()
    keyring = _backend()

    if keyring is not None:
        try:
            if value:
                keyring.set_password(SERVICE_NAME, option, value)
            else:
                try:
                    keyring.delete_password(SERVICE_NAME, option)
                except Exception:
                    pass  # nothing stored, or the backend can't delete: either way it is cleared
            config.remove_option("DEFAULT", option)
            return True
        except Exception as e:
            logger.warning(f"Could not store '{option}' in the system keyring ({e}); falling back to astrofiler.ini.")

    if value:
        _warn_no_keyring_once()
    config.set("DEFAULT", option, value)
    return False
