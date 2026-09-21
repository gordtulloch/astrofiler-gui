"""Tests for astrofiler.paths: file locations must not depend on the working directory."""

import fnmatch
import tomllib
from pathlib import Path

import pytest

from astrofiler import paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("ASTROFILER_HOME", raising=False)
    monkeypatch.delenv("ASTROFILER_DB_PATH", raising=False)


def test_astrofiler_home_overrides_everything(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTROFILER_HOME", str(tmp_path / "home"))

    assert paths.get_app_dir() == (tmp_path / "home").resolve()
    assert paths.get_app_dir().is_dir()  # created on demand
    assert paths.get_config_path() == (tmp_path / "home").resolve() / "astrofiler.ini"
    assert paths.get_database_path() == (tmp_path / "home").resolve() / "astrofiler.db"
    assert paths.get_log_path() == (tmp_path / "home").resolve() / "astrofiler.log"


def test_locations_do_not_depend_on_working_directory(tmp_path, monkeypatch):
    before = (paths.get_config_path(), paths.get_database_path(), paths.get_log_path())
    elsewhere = tmp_path / "somewhere_else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert (paths.get_config_path(), paths.get_database_path(), paths.get_log_path()) == before
    assert list(elsewhere.iterdir()) == []  # asking for a path must not create files in the cwd


def test_source_checkout_uses_project_root():
    # These tests run from a source checkout, which is where the install scripts keep the files.
    assert paths._source_checkout_root() == PROJECT_ROOT
    assert paths.get_app_dir() == PROJECT_ROOT


def test_database_path_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTROFILER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ASTROFILER_DB_PATH", str(tmp_path / "other" / "my.db"))

    assert paths.get_database_path() == (tmp_path / "other" / "my.db").resolve()
    assert paths.get_config_path().parent == (tmp_path / "home").resolve()  # override is DB-only


@pytest.mark.parametrize(
    "platform, env, expected_tail",
    [
        ("win32", {"APPDATA": "C:/Users/x/AppData/Roaming"}, ("AstroFiler",)),
        ("linux", {"XDG_CONFIG_HOME": "/home/x/.cfg"}, ("astrofiler",)),
        ("darwin", {}, ("Library", "Application Support", "AstroFiler")),
    ],
)
def test_installed_package_uses_per_user_directory(monkeypatch, tmp_path, platform, env, expected_tail):
    """Outside a source checkout the app directory is a per-user location, never the cwd."""
    monkeypatch.setattr(paths, "_source_checkout_root", lambda: None)
    monkeypatch.setattr(paths.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    for key in ("APPDATA", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(Path, "mkdir", lambda self, *a, **k: None)  # don't create real dirs

    app_dir = paths.get_app_dir()

    assert app_dir.parts[-len(expected_tail):] == expected_tail
    assert app_dir != Path.cwd()


def test_bundled_resources_exist():
    for parts in [("css", "dark.css"), ("css", "light.css"), ("images", "background.jpg"), ("astrofiler.png")]:
        parts = (parts,) if isinstance(parts, str) else parts
        assert paths.resource_path(*parts).is_file(), parts


def test_every_bundled_resource_is_listed_in_package_data():
    """Guards the installable package: a resource missing from package-data ships broken."""
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = pyproject["tool"]["setuptools"]["package-data"]["astrofiler"]
    resources_dir = PROJECT_ROOT / "src" / "astrofiler" / "resources"

    missing = [
        rel
        for rel in (p.relative_to(PROJECT_ROOT / "src" / "astrofiler").as_posix() for p in resources_dir.rglob("*") if p.is_file())
        if not any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)
    ]

    assert missing == []


def test_migrations_are_bundled_and_found():
    """An installed copy needs the migrations to create its database."""
    from astrofiler import database

    bundled = PROJECT_ROOT / "src" / "astrofiler" / "migrations"
    assert database.MIGRATIONS_DIR == bundled
    assert list(bundled.glob("[0-9]*.py"))

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = pyproject["tool"]["setuptools"]["package-data"]["astrofiler"]
    assert "migrations/*.py" in patterns


def test_default_repository_and_incoming_folders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert Path(paths.default_repo_folder()) == tmp_path / "REPOSITORY"
    assert Path(paths.default_source_folder()) == tmp_path / "REPOSITORY.incoming"
    assert list(tmp_path.iterdir()) == []  # just computing them creates nothing


def test_unconfigured_repository_is_not_created_loose_in_the_working_directory(tmp_path, monkeypatch):
    """With no `repo` in the ini, Light/Calibrate/Masters/... must go under REPOSITORY/."""
    from astrofiler.core.repository import RepositoryManager

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("ASTROFILER_HOME", str(tmp_path / "home"))  # empty: no astrofiler.ini
    monkeypatch.chdir(work)

    manager = RepositoryManager()
    assert Path(manager.repoFolder) == work / "REPOSITORY"
    assert Path(manager.sourceFolder) == work / "REPOSITORY.incoming"

    assert manager.createRepositoryStructure()
    assert (work / "REPOSITORY" / "Light").is_dir()
    assert [p.name for p in work.iterdir()] == ["REPOSITORY"]  # nothing loose next to it


def test_configured_repository_wins_over_the_default(tmp_path, monkeypatch):
    from astrofiler.core.repository import RepositoryManager

    home = tmp_path / "home"
    home.mkdir()
    (home / "astrofiler.ini").write_text(
        f"[DEFAULT]\nrepo = {tmp_path / 'my_repo'}\nsource = {tmp_path / 'my_incoming'}\n", encoding="utf-8"
    )
    monkeypatch.setenv("ASTROFILER_HOME", str(home))
    monkeypatch.chdir(tmp_path)

    manager = RepositoryManager()

    assert Path(manager.repoFolder) == tmp_path / "my_repo"
    assert Path(manager.sourceFolder) == tmp_path / "my_incoming"
