from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QDialogButtonBox,
    QFileDialog,
    QWidget,
)


@dataclass(frozen=True)
class CheckoutOptions:
    dest_dir: str
    copy_files: bool
    decompress: bool
    masters_only: bool


def prompt_checkout_options(parent: QWidget, title: str) -> Optional[CheckoutOptions]:
    """Prompt for checkout target directory and options.

    Returns CheckoutOptions or None if cancelled.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)

    # Make the dialog comfortably wide for long folder paths.
    dialog.setMinimumWidth(700)
    dialog.resize(900, dialog.sizeHint().height())

    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Target directory:"))
    dir_row = QHBoxLayout()
    dir_edit = QLineEdit()
    dir_edit.setText(os.path.expanduser("~"))
    dir_edit.setMinimumWidth(600)
    browse_btn = QPushButton("Browse...")
    dir_row.addWidget(dir_edit)
    dir_row.addWidget(browse_btn)
    layout.addLayout(dir_row)

    copy_cb = QCheckBox("Copy Files, Don't Link (Slower)")
    copy_cb.setChecked(False)
    decompress_cb = QCheckBox("Decompress")
    decompress_cb.setChecked(False)
    masters_only_cb = QCheckBox("Masters Only")
    masters_only_cb.setChecked(True)

    layout.addWidget(copy_cb)
    layout.addWidget(decompress_cb)
    layout.addWidget(masters_only_cb)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    layout.addWidget(buttons)

    def _browse() -> None:
        chosen = QFileDialog.getExistingDirectory(
            parent,
            "Select Target Directory",
            dir_edit.text() or os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly,
        )
        if chosen:
            dir_edit.setText(chosen)

    def _update_ok_state() -> None:
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        if ok_btn is not None:
            ok_btn.setEnabled(bool(dir_edit.text().strip()))

    browse_btn.clicked.connect(_browse)
    dir_edit.textChanged.connect(_update_ok_state)
    _update_ok_state()

    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    if dialog.exec() != QDialog.Accepted:
        return None

    dest_dir = dir_edit.text().strip()
    if not dest_dir:
        return None

    return CheckoutOptions(
        dest_dir=dest_dir,
        copy_files=bool(copy_cb.isChecked()),
        decompress=bool(decompress_cb.isChecked()),
        masters_only=bool(masters_only_cb.isChecked()),
    )
