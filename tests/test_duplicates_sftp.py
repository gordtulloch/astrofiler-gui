"""Integrity/duplicate queries, SFTP settings and the keychain-backed passwords."""

import hashlib

import peewee as pw
import pytest

from astrofiler.core import duplicates
from astrofiler.models import fitsFile


@pytest.fixture
def catalog(tmp_path):
    db = pw.SqliteDatabase(str(tmp_path / 'test.db'))
    with db.bind_ctx([fitsFile]):
        db.create_tables([fitsFile])
        yield tmp_path


def _add(tmp, name, content):
    path = tmp / name
    path.write_bytes(content)
    return fitsFile.create(
        fitsFileId=name, fitsFileName=str(path),
        fitsFileHash=hashlib.sha256(content).hexdigest())


def test_find_duplicate_hashes_and_files(catalog):
    a = _add(catalog, 'a.fits', b'same')
    _add(catalog, 'b.fits', b'same')
    _add(catalog, 'c.fits', b'other')

    assert duplicates.find_duplicate_hashes() == [(a.fitsFileHash, 2)]
    assert [f.fitsFileId for f in duplicates.files_with_hash(a.fitsFileHash)] == ['a.fits', 'b.fits']


def test_verify_integrity_reports_missing_and_modified(catalog):
    _add(catalog, 'ok.fits', b'ok')
    _add(catalog, 'gone.fits', b'gone')
    _add(catalog, 'edited.fits', b'edited')
    (catalog / 'gone.fits').unlink()
    (catalog / 'edited.fits').write_bytes(b'edited!')

    problems = {p.file.fitsFileId: p.reason for p in duplicates.verify_integrity()}

    assert problems == {'gone.fits': 'missing', 'edited.fits': 'modified'}


def test_sftp_settings_defaults_and_values(tmp_path, monkeypatch):
    from astrofiler.services import credentials
    monkeypatch.setattr(credentials, 'get_sftp_password', lambda: 'secret')
    ini = tmp_path / 'a.ini'
    assert credentials.get_sftp_settings(str(ini))['port'] == 22
    ini.write_text('[DEFAULT]\nsftp_username=obs\nsftp_port=2222\nsftp_strict_host_keys=True\n'
                   'sftp_remote_path=/data\n')

    s = credentials.get_sftp_settings(str(ini))

    assert (s['username'], s['password'], s['port'], s['remote_path'], s['strict_host_keys']) == \
        ('obs', 'secret', 2222, '/data', True)


def test_legacy_itelescope_password_migrates_to_keychain(tmp_path, monkeypatch):
    keyring = pytest.importorskip('keyring')
    from astrofiler.services import credentials
    store = {}
    monkeypatch.setattr(keyring, 'get_password', lambda svc, user: store.get((svc, user)))
    monkeypatch.setattr(keyring, 'set_password', lambda svc, user, pw_: store.__setitem__((svc, user), pw_))
    ini = tmp_path / 'a.ini'
    ini.write_text('[DEFAULT]\nitelescope_username=me\nitelescope_password=hunter2\n')

    assert credentials.get_itelescope_password(str(ini)) == 'hunter2'
    assert 'itelescope_password' not in ini.read_text()
    assert 'itelescope_username = me' in ini.read_text()
    assert credentials.get_itelescope_password(str(ini)) == 'hunter2'  # now from the keychain
