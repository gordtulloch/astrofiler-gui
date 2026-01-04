"""GitHub release update checker.

Checks GitHub Releases for the latest published release and compares it with the
currently running version.

UX requirement:
- If a newer version exists, show a single prompt with two buttons:
  - Update
  - Ignore

"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6.QtCore import QObject, Signal, QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget


GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/gordtulloch/astrofiler-gui/releases/latest"
GITHUB_RELEASES_LATEST_PAGE = "https://github.com/gordtulloch/astrofiler-gui/releases/latest"


@dataclass(frozen=True)
class ReleaseInfo:
    tag_name: str
    html_url: str


def _normalize_version_str(value: str) -> str:
    v = (value or "").strip()
    if v.lower().startswith("v"):
        v = v[1:]
    return v


def _parse_version_tuple(value: str) -> Tuple[int, ...]:
    """Best-effort parse: '1.2.0' -> (1,2,0). Non-numeric parts are ignored."""
    v = _normalize_version_str(value)
    parts = []
    for chunk in v.replace("-", ".").split("."):
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        if num == "":
            break
        parts.append(int(num))
    return tuple(parts) if parts else (0,)


def _is_newer(latest: str, current: str) -> bool:
    latest_t = _parse_version_tuple(latest)
    current_t = _parse_version_tuple(current)
    # Pad to equal length for stable comparison
    n = max(len(latest_t), len(current_t))
    latest_t = latest_t + (0,) * (n - len(latest_t))
    current_t = current_t + (0,) * (n - len(current_t))
    return latest_t > current_t


def _fetch_latest_release(timeout_s: float = 3.5) -> Optional[ReleaseInfo]:
    req = urllib.request.Request(
        GITHUB_LATEST_RELEASE_API,
        headers={
            # User-Agent required by GitHub API; keep it simple.
            "User-Agent": "AstroFiler",
            "Accept": "application/vnd.github+json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = str(data.get("tag_name") or "").strip()
        url = str(data.get("html_url") or "").strip() or GITHUB_RELEASES_LATEST_PAGE
        if not tag:
            return None
        return ReleaseInfo(tag_name=tag, html_url=url)
    except Exception:
        return None


class _UpdateSignal(QObject):
    ready = Signal(object)  # Optional[ReleaseInfo]


def _find_upgrade_script() -> Optional[Path]:
    """Locate an upgrade script by walking up from this module."""
    here = Path(__file__).resolve()
    candidates: list[Path]
    if os.name == "nt":
        candidates = [Path("install") / "upgrade.ps1"]
    elif sys.platform == "darwin":
        candidates = [Path("install") / "upgrade_macos.sh", Path("install") / "upgrade.sh"]
    else:
        candidates = [Path("install") / "upgrade.sh"]

    for parent in [here.parent, *here.parents]:
        for rel in candidates:
            candidate = parent / rel
            if candidate.is_file():
                return candidate
    return None


def _launch_upgrade_script_new_console() -> bool:
    """Launch the upgrade script in a new terminal/console window."""
    script = _find_upgrade_script()
    if script is None:
        return False

    try:
        if os.name == "nt":
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            return True

        if sys.platform == "darwin":
            # Open Terminal.app and run the script.
            cmd = f"cd {script.parent.parent.as_posix()}; bash {script.as_posix()}"
            osa = (
                "tell application \"Terminal\"\n"
                "  activate\n"
                f"  do script \"{cmd.replace('\\', '\\\\').replace('"', '\\"')}\"\n"
                "end tell\n"
            )
            subprocess.Popen(["osascript", "-e", osa])
            return True

        # Linux/Unix: best-effort choose a terminal emulator
        term_cmds = [
            ("x-terminal-emulator", ["x-terminal-emulator", "-e"]),
            ("gnome-terminal", ["gnome-terminal", "--"]),
            ("konsole", ["konsole", "-e"]),
            ("xfce4-terminal", ["xfce4-terminal", "-e"]),
            ("xterm", ["xterm", "-e"]),
        ]
        terminal_prefix: Optional[list[str]] = None
        for exe, prefix in term_cmds:
            if shutil.which(exe):
                terminal_prefix = prefix
                break

        # Fall back: run in background without new window
        if terminal_prefix is None:
            subprocess.Popen(["bash", str(script)])
            return True

        subprocess.Popen(terminal_prefix + ["bash", str(script)])
        return True
    except Exception:
        return False


def schedule_update_prompt(
    parent: QWidget,
    *,
    current_version: str,
    force: bool = False,
    show_if_up_to_date: bool = False,
    show_if_check_failed: bool = False,
) -> None:
    """Check GitHub in the background and prompt if a newer release exists.

    Args:
        parent: Parent widget for the prompt.
        current_version: Current app version.
        force: If True, bypass the ignored-release setting.
    """

    settings = QSettings()
    ignored = settings.value("updates/ignored_release", "", type=str) or ""

    signal = _UpdateSignal(parent)

    def on_ready(release: Optional[ReleaseInfo]) -> None:
        try:
            if release is None:
                if show_if_check_failed:
                    QMessageBox.warning(parent, "AstroFiler", "Could not check for updates")
                return

            if not _is_newer(release.tag_name, current_version):
                if show_if_up_to_date:
                    QMessageBox.information(parent, "AstroFiler", "You are at the current version")
                return

            if (not force) and ignored and _normalize_version_str(ignored) == _normalize_version_str(release.tag_name):
                return

            box = QMessageBox(parent)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("New version available")
            box.setText("New version available")

            update_btn = box.addButton("Update", QMessageBox.AcceptRole)
            ignore_btn = box.addButton("Ignore", QMessageBox.RejectRole)
            box.setDefaultButton(update_btn)

            box.exec()
            clicked = box.clickedButton()

            if clicked == update_btn:
                # Preferred UX on Windows: run our upgrade script in a new console
                # and then exit so files can be updated.
                launched = _launch_upgrade_script_new_console()
                if not launched:
                    QDesktopServices.openUrl(QUrl(release.html_url))

                app = QApplication.instance()
                if app is not None:
                    app.quit()
            elif clicked == ignore_btn:
                settings.setValue("updates/ignored_release", release.tag_name)
        except Exception:
            # Never break the UI startup flow.
            return

    signal.ready.connect(on_ready)

    def worker() -> None:
        release = _fetch_latest_release()
        if release is None:
            if show_if_check_failed:
                signal.ready.emit(None)
            return
        signal.ready.emit(release)

    t = threading.Thread(target=worker, name="AstroFilerUpdateCheck", daemon=True)
    t.start()
