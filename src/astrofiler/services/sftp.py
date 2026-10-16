"""SFTP session for retrieving FITS files from a remote observatory or data server."""

from __future__ import annotations

import logging
import stat as stat_module
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SftpDownloadCancelled(Exception):
    """Raised from a transfer's progress callback to stop it part-way."""


class SftpSession:
    """A blocking SFTP connection: list, fetch and delete FITS files. Use as a context manager.

    Callers are worker threads (the Download dialog runs these off the UI thread already).

    Authentication is the key file if given, otherwise *password*, otherwise whatever paramiko finds
    on its own (an SSH agent, ``~/.ssh``). *strict_host_keys* refuses any server whose host key is not
    already in the system's known-hosts file; the default accepts an unknown key but logs its
    fingerprint at WARNING, which suits the LAN-only smart-telescope/remote-observatory use case where
    there is no interactive prompt to ask the user — set it for anything reachable over the internet.
    """

    def __init__(
        self,
        host: str,
        user: str = "",
        password: str | None = None,
        key_path: str = "",
        port: int = 22,
        strict_host_keys: bool = False,
    ) -> None:
        self.host = host
        self.user = user
        self.password = password or ""
        self.key_path = key_path
        self.port = port
        self.strict_host_keys = strict_host_keys
        self._client: Any = None
        self._sftp: Any = None

    def __enter__(self) -> SftpSession:
        try:
            self.open()
        except BaseException:
            self.close()        # __exit__ doesn't run when __enter__ raises
            raise
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def open(self) -> None:
        import paramiko  # type: ignore[import]

        class _LogUnknownHostKey(paramiko.MissingHostKeyPolicy):
            """Accept an unknown host key, but say so — paramiko's own WarningPolicy goes through
            ``warnings``, which an app's logging setup never sees."""
            def missing_host_key(self, client, hostname, key):
                logger.warning("SFTP: accepting unknown host key for %s (%s %s) — add it to known_hosts "
                               "or set strict_host_keys", hostname, key.get_name(), key.get_fingerprint().hex())

        client = paramiko.SSHClient()
        self._client = client       # set first so close() releases it if connecting fails
        client.load_system_host_keys()
        client.set_missing_host_key_policy(
            paramiko.RejectPolicy() if self.strict_host_keys else _LogUnknownHostKey())
        kwargs: dict = {"hostname": self.host, "username": self.user or None, "timeout": 10}
        if self.port != 22:
            kwargs["port"] = self.port
        if self.key_path:
            kwargs["key_filename"] = self.key_path
        if self.password:
            kwargs["password"] = self.password
        client.connect(**kwargs)
        self._sftp = client.open_sftp()

    def close(self) -> None:
        for resource in (self._sftp, self._client):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    logger.debug("SFTP: error while closing", exc_info=True)
        self._sftp = self._client = None

    @staticmethod
    def _is_fits(name: str) -> bool:
        return name.lower().endswith((".fits", ".fit", ".fts", ".zip"))

    def listdir(self, remote_path: str):
        """The raw directory entries (paramiko ``SFTPAttributes``) of one remote folder."""
        return self._sftp.listdir_attr(remote_path)

    def list_fits(self, remote_path: str = "/", max_depth: int = 10) -> list[dict]:
        """Every FITS (or zipped FITS) file under *remote_path*, as the Library's file-info dicts:
        ``name``, ``path`` (full remote path), ``size`` and ``folder_name`` (the containing folder)."""
        found: list[dict] = []

        def walk(directory: str, depth: int) -> None:
            for entry in self.listdir(directory):
                full = f"{directory.rstrip('/')}/{entry.filename}"
                if stat_module.S_ISDIR(entry.st_mode or 0):
                    if depth < max_depth:
                        walk(full, depth + 1)
                elif self._is_fits(entry.filename):
                    found.append({
                        "name": entry.filename,
                        "path": full,
                        "size": entry.st_size or 0,
                        "folder_name": directory.rstrip("/").rsplit("/", 1)[-1] or "root",
                    })

        walk(remote_path or "/", 0)
        return found

    def get(self, remote_path: str, local_path: str | Path, progress_callback=None) -> None:
        """Fetch one file. *progress_callback(bytes_done, bytes_total)* may return ``False`` to cancel,
        which raises :class:`SftpDownloadCancelled` and removes the partial file."""
        local = Path(local_path)
        local.parent.mkdir(parents=True, exist_ok=True)

        def report(done: int, total: int) -> None:
            if progress_callback is not None and progress_callback(done, total) is False:
                raise SftpDownloadCancelled(remote_path)

        try:
            self._sftp.get(remote_path, str(local), callback=report)
        except BaseException:
            local.unlink(missing_ok=True)
            raise

    def remove(self, remote_path: str) -> None:
        self._sftp.remove(remote_path)
