"""Tests for astrofiler.credentials: the iTelescope password must not live in astrofiler.ini."""

import configparser

import pytest

from astrofiler import credentials
from astrofiler.credentials import ITELESCOPE_PASSWORD, get_ini_secret, store_ini_secret

keyring = pytest.importorskip("keyring")
from keyring.backend import KeyringBackend  # noqa: E402
from keyring.errors import PasswordDeleteError  # noqa: E402


class MemoryKeyring(KeyringBackend):
    """In-memory backend so tests never touch the real credential store."""

    priority = 1

    def __init__(self):
        super().__init__()
        self.data = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.data:
            raise PasswordDeleteError("not found")
        del self.data[(service, username)]


class BrokenKeyring(MemoryKeyring):
    def set_password(self, service, username, password):
        raise RuntimeError("keyring locked")


@pytest.fixture
def memory_keyring(monkeypatch):
    monkeypatch.delenv("ASTROFILER_DISABLE_KEYRING", raising=False)
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


@pytest.fixture(autouse=True)
def _reset_warning():
    credentials._warned_no_keyring = False


def _config(text=""):
    cfg = configparser.ConfigParser()
    cfg.read_string("[DEFAULT]\n" + text)
    return cfg


def test_store_puts_password_in_keyring_not_in_config(memory_keyring):
    cfg = _config("itelescope_password = old\n")

    assert store_ini_secret(cfg, ITELESCOPE_PASSWORD, "  s3cret  ") is True

    assert memory_keyring.data[("AstroFiler", ITELESCOPE_PASSWORD)] == "s3cret"
    assert not cfg.has_option("DEFAULT", ITELESCOPE_PASSWORD)  # so the widget never writes it to disk


def test_get_reads_from_keyring(memory_keyring):
    memory_keyring.data[("AstroFiler", ITELESCOPE_PASSWORD)] = "from-keyring"

    assert get_ini_secret(_config(), ITELESCOPE_PASSWORD) == "from-keyring"


def test_legacy_plaintext_password_is_migrated_and_scrubbed_from_the_file(memory_keyring, tmp_path):
    ini = tmp_path / "astrofiler.ini"
    ini.write_text(
        "[DEFAULT]\n# my settings\nitelescope_username = alice\nitelescope_password = hunter2\ntheme = dark\n",
        encoding="utf-8",
    )
    cfg = configparser.ConfigParser()
    cfg.read(ini)

    assert get_ini_secret(cfg, ITELESCOPE_PASSWORD, config_path=str(ini)) == "hunter2"

    assert memory_keyring.data[("AstroFiler", ITELESCOPE_PASSWORD)] == "hunter2"
    text = ini.read_text(encoding="utf-8")
    assert "hunter2" not in text and "itelescope_password" not in text
    # everything else, including comments, is untouched
    assert "# my settings" in text and "itelescope_username = alice" in text and "theme = dark" in text


def test_leftover_plaintext_copy_is_removed_when_keyring_already_has_the_password(memory_keyring, tmp_path):
    memory_keyring.data[("AstroFiler", ITELESCOPE_PASSWORD)] = "current"
    ini = tmp_path / "astrofiler.ini"
    ini.write_text("[DEFAULT]\nitelescope_password = stale\n", encoding="utf-8")
    cfg = configparser.ConfigParser()
    cfg.read(ini)

    assert get_ini_secret(cfg, ITELESCOPE_PASSWORD, config_path=str(ini)) == "current"
    assert "stale" not in ini.read_text(encoding="utf-8")


def test_empty_password_clears_the_keyring(memory_keyring):
    memory_keyring.data[("AstroFiler", ITELESCOPE_PASSWORD)] = "x"

    assert store_ini_secret(_config(), ITELESCOPE_PASSWORD, "") is True

    assert ("AstroFiler", ITELESCOPE_PASSWORD) not in memory_keyring.data


def test_clearing_when_nothing_is_stored_does_not_fail(memory_keyring):
    assert store_ini_secret(_config(), ITELESCOPE_PASSWORD, "") is True


def test_without_a_keyring_the_ini_file_is_still_used(monkeypatch, caplog):
    monkeypatch.setenv("ASTROFILER_DISABLE_KEYRING", "1")
    cfg = _config()

    with caplog.at_level("WARNING"):
        assert store_ini_secret(cfg, ITELESCOPE_PASSWORD, "pw") is False

    assert cfg.get("DEFAULT", ITELESCOPE_PASSWORD) == "pw"  # falls back to plain text, as before
    assert get_ini_secret(cfg, ITELESCOPE_PASSWORD) == "pw"
    assert "plain text" in caplog.text


def test_a_failing_keyring_falls_back_to_the_ini_file(monkeypatch):
    monkeypatch.delenv("ASTROFILER_DISABLE_KEYRING", raising=False)
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        cfg = _config()
        assert store_ini_secret(cfg, ITELESCOPE_PASSWORD, "pw") is False
        assert cfg.get("DEFAULT", ITELESCOPE_PASSWORD) == "pw"
    finally:
        keyring.set_keyring(previous)


def test_fail_backend_counts_as_unavailable(monkeypatch):
    from keyring.backends.fail import Keyring as FailKeyring

    monkeypatch.delenv("ASTROFILER_DISABLE_KEYRING", raising=False)
    previous = keyring.get_keyring()
    keyring.set_keyring(FailKeyring())
    try:
        assert credentials.keyring_available() is False
    finally:
        keyring.set_keyring(previous)


def test_telescope_manager_reads_password_from_keyring_and_scrubs_the_ini(memory_keyring, tmp_path, monkeypatch):
    """End to end through the code path the download dialog and CLI use."""
    from astrofiler.services.telescope import SmartTelescopeManager

    home = tmp_path / "home"
    home.mkdir()
    ini = home / "astrofiler.ini"
    ini.write_text("[DEFAULT]\nitelescope_username = alice\nitelescope_password = hunter2\n", encoding="utf-8")
    monkeypatch.setenv("ASTROFILER_HOME", str(home))

    assert SmartTelescopeManager().get_itelescope_credentials() == ("alice", "hunter2")

    assert "hunter2" not in ini.read_text(encoding="utf-8")
    # second call comes from the keyring
    assert SmartTelescopeManager().get_itelescope_credentials() == ("alice", "hunter2")
