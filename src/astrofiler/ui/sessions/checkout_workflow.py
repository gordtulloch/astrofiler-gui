from __future__ import annotations

import logging
import os
from datetime import datetime as dt

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QProgressDialog, QMessageBox, QWidget

from astrofiler.models import fitsFile as FitsFileModel, fitsSession as FitsSessionModel

from .checkout_files import get_decompressed_dest_path, materialize_file
from .checkout_options_dialog import prompt_checkout_options
from .masters_resolver import find_matching_masters_for_light_session

logger = logging.getLogger(__name__)


def _format_method_desc(*, decompress: bool, copy_files: bool, masters_only: bool) -> str:
    method_bits: list[str] = []
    if decompress:
        method_bits.append("decompressed")
    method_bits.append("copied" if copy_files else "linked")
    if masters_only:
        method_bits.append("masters-only")
    return "+".join(method_bits)


def _show_checkout_complete(parent: QWidget, *, created_items: int, method_desc: str, out_dir: str, extra: str = "") -> None:
    message = f"Created {created_items} files ({method_desc}).\n\nFiles created in:\n{out_dir}"
    if extra:
        message = extra + "\n\n" + message
    QMessageBox.information(parent, "Checkout Complete", message)
    QDesktopServices.openUrl(QUrl.fromLocalFile(out_dir))


def _show_checkout_failed(parent: QWidget, *, message: str) -> None:
    QMessageBox.warning(parent, "Checkout Failed", message)


def checkout_single_session(parent: QWidget, item) -> None:
    """Create symbolic links/copies/decompressed outputs for a single session."""
    try:
        session_date = item.text(2)
        object_name = item.parent().text(0)

        session = (
            FitsSessionModel.select()
            .where(
                (FitsSessionModel.fitsSessionObjectName == object_name)
                & (FitsSessionModel.fitsSessionDate == session_date)
            )
            .first()
        )

        if not session:
            QMessageBox.warning(parent, "Error", "Session not found in database")
            return
        logger.info(f"Found session: {object_name} on {session_date}")

        light_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsSessionId)
        lights_calibrated = all(lf.fitsFileCalibrated for lf in light_files)

        dark_files = []
        bias_files = []
        flat_files = []
        master_files: list[tuple[str, str]] = []

        if object_name not in ['Bias', 'Dark', 'Flat']:
            if not lights_calibrated:
                if session.fitsBiasSession:
                    bias_files = FitsFileModel.select().where(
                        FitsFileModel.fitsFileSession == session.fitsBiasSession
                    )
                    logger.info(f"Found {bias_files.count()} bias files")

                if session.fitsDarkSession:
                    dark_files = FitsFileModel.select().where(
                        FitsFileModel.fitsFileSession == session.fitsDarkSession
                    )
                    logger.info(f"Found {dark_files.count()} dark files")

                filters = set([lf.fitsFileFilter for lf in light_files if lf.fitsFileFilter])
                logger.info(f"Filters used in light frames: {filters}")

                for filter_name in filters:
                    flat_sessions = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName == 'Flat')
                        & (FitsSessionModel.fitsSessionTelescope == session.fitsSessionTelescope)
                        & (FitsSessionModel.fitsSessionImager == session.fitsSessionImager)
                        & (FitsSessionModel.fitsSessionBinningX == session.fitsSessionBinningX)
                        & (FitsSessionModel.fitsSessionBinningY == session.fitsSessionBinningY)
                        & (FitsSessionModel.fitsSessionFilter == filter_name)
                    )
                    for flat_session in flat_sessions:
                        these_flats = FitsFileModel.select().where(
                            FitsFileModel.fitsFileSession == flat_session.fitsSessionId
                        )
                        flat_files.extend(list(these_flats))
                        logger.info(f"Found {these_flats.count()} flat files for filter {filter_name}")

                master_files = find_matching_masters_for_light_session(session, light_files)
                for master_type, master_path in master_files:
                    label = 'flat master' if master_type == 'flat' else f"{master_type} master"
                    logger.info(f"Found matching {label}: {os.path.basename(master_path)}")
            else:
                logger.info("Light frames are already calibrated, skipping calibration files and masters")

        opts = prompt_checkout_options(parent, "Check out Session")
        if not opts:
            return
        dest_dir, copy_files, decompress, masters_only = (
            opts.dest_dir,
            opts.copy_files,
            opts.decompress,
            opts.masters_only,
        )

        include_calibration_frames = (
            (not masters_only)
            and (not lights_calibrated)
            and (object_name not in ['Bias', 'Dark', 'Flat'])
        )

        all_files = list(light_files)
        if include_calibration_frames:
            all_files += list(dark_files) + list(bias_files) + list(flat_files)

        if not all_files:
            QMessageBox.information(parent, "Information", "No files found for this session")
            return

        logger.info(f"Found {len(all_files)} files for session {object_name} on {session_date}")

        session_dir = os.path.join(dest_dir, f"{object_name}_{session_date.replace(':', '-')}")
        light_dir = os.path.join(session_dir, "lights")
        os.makedirs(light_dir, exist_ok=True)

        dark_dir = None
        flat_dir = None
        bias_dir = None
        masters_dir = None

        if (not lights_calibrated) and (object_name not in ['Bias', 'Dark', 'Flat']):
            masters_dir = os.path.join(session_dir, "masters")
            os.makedirs(masters_dir, exist_ok=True)

            if include_calibration_frames:
                dark_dir = os.path.join(session_dir, "darks")
                flat_dir = os.path.join(session_dir, "flats")
                bias_dir = os.path.join(session_dir, "bias")
                os.makedirs(dark_dir, exist_ok=True)
                os.makedirs(flat_dir, exist_ok=True)
                os.makedirs(bias_dir, exist_ok=True)
                logger.info(f"Created session directory structure with calibration folders at {session_dir}")
            else:
                logger.info(f"Created session directory structure (lights + masters only) at {session_dir}")
        else:
            logger.info(f"Created session directory structure (lights only) at {session_dir}")

        if decompress and copy_files:
            progress_label = "Creating files (decompress/copy)..."
        elif decompress:
            progress_label = "Creating files (decompress/link)..."
        elif copy_files:
            progress_label = "Copying files..."
        else:
            progress_label = "Creating symbolic links..."

        progress = QProgressDialog(progress_label, "Cancel", 0, 100, parent)
        progress.setWindowModality(Qt.WindowModal)

        created_items = 0
        total_items = len(all_files) + (len(master_files) if masters_dir else 0)
        current_item = 0

        for file in all_files:
            progress.setValue(int(current_item * 100 / total_items) if total_items > 0 else 0)
            current_item += 1
            if progress.wasCanceled():
                break

            if "LIGHT" in file.fitsFileType.upper():
                dest_folder = light_dir
            elif "DARK" in file.fitsFileType.upper():
                dest_folder = dark_dir if dark_dir else None
            elif "FLAT" in file.fitsFileType.upper():
                dest_folder = flat_dir if flat_dir else None
            elif "BIAS" in file.fitsFileType.upper():
                dest_folder = bias_dir if bias_dir else None
            else:
                logger.warning(f"Unknown file type for {file.fitsFileName}, skipping")
                continue

            if dest_folder is None:
                logger.debug(f"Skipping calibration file {file.fitsFileName} (lights already calibrated)")
                continue

            if not file.fitsFileName or not os.path.exists(file.fitsFileName):
                continue

            filename = os.path.basename(file.fitsFileName)
            dest_path = os.path.join(dest_folder, filename)

            try:
                if os.path.exists(dest_path) or os.path.exists(get_decompressed_dest_path(dest_path)):
                    continue

                ok = materialize_file(
                    src_path=file.fitsFileName,
                    dest_path=dest_path,
                    copy_files=copy_files,
                    decompress=decompress,
                )
                if not ok:
                    raise Exception("Failed to create output")

                created_items += 1
                logger.info(f"Created checkout file for {file.fitsFileName} -> {dest_path}")
            except Exception as e:
                logger.error(f"Error creating link for {file.fitsFileName}: {e}")

        if masters_dir and master_files:
            for master_type, master_path in master_files:
                progress.setValue(int(current_item * 100 / total_items) if total_items > 0 else 0)
                current_item += 1
                if progress.wasCanceled():
                    break

                filename = os.path.basename(master_path)
                dest_path = os.path.join(masters_dir, filename)

                try:
                    if os.path.exists(dest_path) or os.path.exists(get_decompressed_dest_path(dest_path)):
                        continue

                    ok = materialize_file(
                        src_path=master_path,
                        dest_path=dest_path,
                        copy_files=copy_files,
                        decompress=decompress,
                    )
                    if ok:
                        created_items += 1
                        logger.info(f"Created checkout file for {master_type} master: {filename}")
                except Exception as e:
                    logger.error(f"Error creating link for master {master_path}: {e}")

        progress.setValue(100)

        method_desc = _format_method_desc(
            decompress=decompress,
            copy_files=copy_files,
            masters_only=masters_only,
        )

        _show_checkout_complete(
            parent,
            created_items=created_items,
            method_desc=method_desc,
            out_dir=session_dir,
        )

    except Exception as e:
        QMessageBox.critical(parent, "Checkout Failed", f"Failed to create symbolic links: {str(e)}")
        logger.error(f"Error in checkout_session: {str(e)}")


def checkout_multiple_sessions(parent: QWidget, session_items) -> None:
    """Create symbolic links/copies/decompressed outputs for multiple sessions in a common directory structure."""
    try:
        opts = prompt_checkout_options(parent, "Check out Multiple Sessions")
        if not opts:
            return
        dest_dir, copy_files, decompress, masters_only = (
            opts.dest_dir,
            opts.copy_files,
            opts.decompress,
            opts.masters_only,
        )

        checkout_dir = os.path.join(dest_dir, f"Sessions_Checkout_{dt.now().strftime('%Y%m%d_%H%M%S')}")
        light_dir = os.path.join(checkout_dir, "lights")
        process_dir = os.path.join(checkout_dir, "process")

        # Create only folders that are always needed up-front.
        # Calibration and masters folders are created lazily, only if any selected session needs them.
        os.makedirs(light_dir, exist_ok=True)
        os.makedirs(process_dir, exist_ok=True)

        dark_dir: str | None = None
        flat_dir: str | None = None
        bias_dir: str | None = None
        masters_dir: str | None = None

        total_sessions = len(session_items)
        current_session = 0

        overall_progress = QProgressDialog("Processing sessions...", "Cancel", 0, total_sessions, parent)
        overall_progress.setWindowModality(Qt.WindowModal)
        overall_progress.setWindowTitle("Checking Out Multiple Sessions")

        successful_sessions = 0
        failed_sessions = []
        total_created_items = 0

        for session_item in session_items:
            if overall_progress.wasCanceled():
                break

            try:
                session_id = session_item.data(0, Qt.UserRole)
                if not session_id:
                    logger.error("Session item has no session ID, skipping")
                    failed_sessions.append("Session item missing ID")
                    current_session += 1
                    continue

                session = FitsSessionModel.get_by_id(session_id)
                if not session:
                    failed_sessions.append(f"Session ID {session_id}: Not found in database")
                    current_session += 1
                    continue

                parent_item = session_item.parent()
                object_name = parent_item.text(0) if parent_item else session.fitsSessionObjectName
                session_date = session.fitsSessionDate
                filter_name = session.fitsSessionFilter or "NoFilter"

                overall_progress.setLabelText(f"Processing {object_name} - {session_date} ({filter_name})...")
                overall_progress.setValue(current_session)

                light_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsSessionId)
                lights_calibrated = all(lf.fitsFileCalibrated for lf in light_files)

                dark_files = []
                bias_files = []
                flat_files = []

                if session.fitsBiasSession:
                    bias_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsBiasSession)
                if session.fitsDarkSession:
                    dark_files = FitsFileModel.select().where(FitsFileModel.fitsFileSession == session.fitsDarkSession)

                filters = set([lf.fitsFileFilter for lf in light_files if lf.fitsFileFilter])
                for filter_name in filters:
                    flat_sessions = FitsSessionModel.select().where(
                        (FitsSessionModel.fitsSessionObjectName == 'Flat')
                        & (FitsSessionModel.fitsSessionTelescope == session.fitsSessionTelescope)
                        & (FitsSessionModel.fitsSessionImager == session.fitsSessionImager)
                        & (FitsSessionModel.fitsSessionBinningX == session.fitsSessionBinningX)
                        & (FitsSessionModel.fitsSessionBinningY == session.fitsSessionBinningY)
                        & (FitsSessionModel.fitsSessionFilter == filter_name)
                    )
                    for flat_session in flat_sessions:
                        these_flats = FitsFileModel.select().where(
                            FitsFileModel.fitsFileSession == flat_session.fitsSessionId
                        )
                        flat_files.extend(list(these_flats))

                include_calibration_frames = (
                    (not masters_only)
                    and (not lights_calibrated)
                    and (object_name not in ['Bias', 'Dark', 'Flat'])
                )

                if include_calibration_frames:
                    if dark_dir is None:
                        dark_dir = os.path.join(checkout_dir, "darks")
                        os.makedirs(dark_dir, exist_ok=True)
                    if flat_dir is None:
                        flat_dir = os.path.join(checkout_dir, "flats")
                        os.makedirs(flat_dir, exist_ok=True)
                    if bias_dir is None:
                        bias_dir = os.path.join(checkout_dir, "bias")
                        os.makedirs(bias_dir, exist_ok=True)

                all_files = list(light_files)
                if include_calibration_frames:
                    all_files += list(dark_files) + list(bias_files) + list(flat_files)

                session_links = 0
                for file in all_files:
                    if "LIGHT" in file.fitsFileType.upper():
                        dest_folder = light_dir
                    elif "DARK" in file.fitsFileType.upper():
                        dest_folder = dark_dir if include_calibration_frames else None
                    elif "FLAT" in file.fitsFileType.upper():
                        dest_folder = flat_dir if include_calibration_frames else None
                    elif "BIAS" in file.fitsFileType.upper():
                        dest_folder = bias_dir if include_calibration_frames else None
                    else:
                        continue

                    if dest_folder is None:
                        continue

                    if not file.fitsFileName or not os.path.exists(file.fitsFileName):
                        continue

                    filename = os.path.basename(file.fitsFileName)
                    dest_path = os.path.join(dest_folder, filename)

                    try:
                        if os.path.exists(dest_path) or os.path.exists(get_decompressed_dest_path(dest_path)):
                            continue

                        ok = materialize_file(
                            src_path=file.fitsFileName,
                            dest_path=dest_path,
                            copy_files=copy_files,
                            decompress=decompress,
                        )
                        if ok:
                            session_links += 1
                    except Exception as e:
                        logger.error(f"Error creating link for {file.fitsFileName}: {e}")

                successful_sessions += 1
                total_created_items += session_links
                logger.info(
                    f"Successfully processed session {object_name} - {session_date} with {session_links} links"
                )

                if masters_only and (not lights_calibrated) and (object_name not in ['Bias', 'Dark', 'Flat']):
                    try:
                        if masters_dir is None:
                            masters_dir = os.path.join(checkout_dir, "masters")
                            os.makedirs(masters_dir, exist_ok=True)

                        master_candidates = [p for _, p in find_matching_masters_for_light_session(session, light_files)]
                        for master_path in master_candidates:
                            filename = os.path.basename(master_path)
                            dest_path = os.path.join(masters_dir, filename)

                            if os.path.exists(dest_path) or os.path.exists(get_decompressed_dest_path(dest_path)):
                                continue

                            ok = materialize_file(
                                src_path=master_path,
                                dest_path=dest_path,
                                copy_files=copy_files,
                                decompress=decompress,
                            )
                            if ok:
                                total_created_items += 1
                    except Exception as e:
                        logger.error(f"Error creating master files for session {session_id}: {e}")

            except Exception as e:
                import traceback

                error_msg = (
                    f"{object_name if 'object_name' in locals() else 'Unknown'} - "
                    f"{session_date if 'session_date' in locals() else 'Unknown'}: {str(e)}"
                )
                failed_sessions.append(error_msg)
                logger.error(f"Error processing session: {error_msg}")
                logger.error(f"Traceback: {traceback.format_exc()}")

            current_session += 1
            logger.info(f"Completed session {current_session} of {total_sessions}")

        overall_progress.setValue(total_sessions)

        method_desc = _format_method_desc(
            decompress=decompress,
            copy_files=copy_files,
            masters_only=masters_only,
        )

        message = f"Successfully processed {successful_sessions} out of {total_sessions} sessions."
        if failed_sessions:
            message += "\n\nFailed sessions:\n" + "\n".join(failed_sessions)

        if successful_sessions > 0:
            _show_checkout_complete(
                parent,
                created_items=total_created_items,
                method_desc=method_desc,
                out_dir=checkout_dir,
                extra=message,
            )
        else:
            _show_checkout_failed(parent, message=message)

    except Exception as e:
        QMessageBox.critical(parent, "Checkout Failed", f"Failed to checkout multiple sessions: {str(e)}")
        logger.error(f"Error in checkout_multiple_sessions: {str(e)}")
