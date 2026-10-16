"""
Credential storage in the OS keychain.

Passwords are kept out of ``astrofiler.ini``. A plaintext password left in the ini file by an
older version is moved into the keychain the first time it is read. If no keychain backend is
available (e.g. a headless Linux box) the helpers log a warning and behave as if no password
were configured rather than raising.
"""

import configparser
import logging

logger = logging.getLogger(__name__)

_KEYRING_SERVICE = "astrofiler"
_ITELESCOPE_USER = "itelescope"
_INI_PATH = "astrofiler.ini"


def set_itelescope_password(password: str) -> None:
    """Store the iTelescope FTPS password in the OS keychain (an empty string clears it)."""
    try:
        import keyring
        if password:
            keyring.set_password(_KEYRING_SERVICE, _ITELESCOPE_USER, password)
        else:
            try:
                keyring.delete_password(_KEYRING_SERVICE, _ITELESCOPE_USER)
            except Exception:
                logger.debug("Nothing to delete from the OS keychain", exc_info=True)
    except Exception:
        logger.warning("Could not save the iTelescope password to the OS keychain", exc_info=True)


def get_itelescope_password(ini_path: str = _INI_PATH) -> str:
    """The iTelescope FTPS password from the OS keychain ('' if unset or unavailable).

    A legacy plaintext ``itelescope_password`` in the ini file is migrated into the keychain and
    removed from the file.
    """
    stored = None
    try:
        import keyring
        stored = keyring.get_password(_KEYRING_SERVICE, _ITELESCOPE_USER)
    except Exception:
        logger.warning("Could not read the iTelescope password from the OS keychain", exc_info=True)
    if stored:
        return stored

    config = configparser.ConfigParser()
    config.read(ini_path)
    legacy = config.get("DEFAULT", "itelescope_password", fallback="").strip()
    if not legacy:
        return ""
    set_itelescope_password(legacy)
    config.remove_option("DEFAULT", "itelescope_password")
    try:
        with open(ini_path, "w") as f:
            config.write(f)
        logger.info("Migrated the iTelescope password from %s into the OS keychain", ini_path)
    except OSError:
        logger.warning("Could not strip the legacy iTelescope password from %s", ini_path, exc_info=True)
    return legacy


_SFTP_USER = "sftp"


def get_sftp_password() -> str:
    """The SFTP server password from the OS keychain ('' if unset or unavailable)."""
    try:
        import keyring
        return keyring.get_password(_KEYRING_SERVICE, _SFTP_USER) or ""
    except Exception:
        logger.warning("Could not read the SFTP password from the OS keychain", exc_info=True)
        return ""


def set_sftp_password(password: str) -> None:
    """Store the SFTP server password in the OS keychain (an empty string clears it)."""
    try:
        import keyring
        if password:
            keyring.set_password(_KEYRING_SERVICE, _SFTP_USER, password)
        else:
            try:
                keyring.delete_password(_KEYRING_SERVICE, _SFTP_USER)
            except Exception:
                logger.debug("Nothing to delete from the OS keychain", exc_info=True)
    except Exception:
        logger.warning("Could not save the SFTP password to the OS keychain", exc_info=True)


def get_sftp_settings(ini_path: str = _INI_PATH) -> dict:
    """The SFTP server's connection settings (Config > Smart Telescopes); the password is from the keychain."""
    config = configparser.ConfigParser()
    config.read(ini_path)
    port_text = config.get("DEFAULT", "sftp_port", fallback="22").strip()
    return {
        "username": config.get("DEFAULT", "sftp_username", fallback="").strip(),
        "password": get_sftp_password(),
        "key_path": config.get("DEFAULT", "sftp_key_path", fallback="").strip(),
        "remote_path": config.get("DEFAULT", "sftp_remote_path", fallback="/").strip() or "/",
        "port": int(port_text) if port_text.isdigit() else 22,
        "strict_host_keys": config.get("DEFAULT", "sftp_strict_host_keys", fallback="False").strip().lower()
        in ("true", "1", "yes", "on"),
    }
