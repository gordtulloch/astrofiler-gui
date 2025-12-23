#!/usr/bin/env python3
r"""Stack.py - Command line utility for batch stacking light sessions

This command stacks light sessions using AstroFiler's internal sigma-clipped stacker.

Modes:
  - Stack all light sessions
  - Stack only unstacked light sessions
  - Stack a single session by ID

Notes:
  - This command only stacks sessions that already have stackable frames available:
      * Precalibrated sessions (iTelescope/SeeStar): stacks non-soft-deleted light frames
      * Other sessions: stacks calibrated, non-soft-deleted light frames
  - Star registration for light stacking uses astroalign (required).

Examples:
  .venv\Scripts\python commands\Stack.py --all
  .venv\Scripts\python commands\Stack.py --unstacked
  .venv\Scripts\python commands\Stack.py --session 12345
  .venv\Scripts\python commands\Stack.py --unstacked --dry-run
    .venv\Scripts\python commands\Stack.py --session 12345 --photometric
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional

# Configure Python path for new package structure - must be before any astrofiler imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')

# Ensure src path is first in path to avoid conflicts with root astrofiler.py
if src_path in sys.path:
    sys.path.remove(src_path)
sys.path.insert(0, src_path)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging to both console and astrofiler.log."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(levelname)s - %(message)s'

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.FileHandler('astrofiler.log', mode='a'),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Reduce peewee noise
    logging.getLogger('peewee').setLevel(logging.WARNING)

    return logging.getLogger(__name__)


def _is_precalibrated_session(telescope: Optional[str], instrument: Optional[str]) -> bool:
    telescope = telescope or ''
    instrument = instrument or ''
    return ('itelescope' in telescope.lower()) or ('seestar' in instrument.lower())


def _light_type_values() -> List[str]:
    # Database values vary across imports; include common variants.
    return ['Light Frame', 'LIGHT', 'LIGHT FRAME']


def _get_stack_candidates(session_id: str, precalibrated: bool):
    from astrofiler.models import fitsFile as FitsFileModel

    base = (
        (FitsFileModel.fitsFileSession == session_id)
        & (FitsFileModel.fitsFileSoftDelete == False)
        & (FitsFileModel.fitsFileType.in_(_light_type_values()))
    )

    if precalibrated:
        return list(FitsFileModel.select().where(base))

    return list(
        FitsFileModel.select().where(
            base & (FitsFileModel.fitsFileCalibrated == 1)
        )
    )


def _select_best_reference_path(files) -> Optional[str]:
    best_ref_path = None
    best_hfr = None

    for f in files:
        p = getattr(f, 'fitsFileName', None)
        if not p or not os.path.exists(p):
            continue
        hfr = getattr(f, 'fitsFileAvgHFRArcsec', None)
        if hfr is None:
            continue
        try:
            hfr_val = float(hfr)
        except Exception:
            continue
        if best_hfr is None or hfr_val < best_hfr:
            best_hfr = hfr_val
            best_ref_path = p

    return best_ref_path


def _default_output_path(session, file_paths: List[str], object_name: str) -> str:
    from astrofiler.core.utils import sanitize_filesystem_name

    out_dir = os.path.dirname(file_paths[0])
    safe_object = sanitize_filesystem_name(object_name or 'Unknown')
    date_str = str(session.fitsSessionDate) if session.fitsSessionDate else 'unknown_date'
    return os.path.join(out_dir, f"stack_{safe_object}_{date_str}_{session.fitsSessionId}.fits")


def _session_is_unstacked(session_id: str) -> bool:
    """Heuristic: session is 'unstacked' if no light files are marked stacked."""
    from astrofiler.models import fitsFile as FitsFileModel

    q = FitsFileModel.select().where(
        (FitsFileModel.fitsFileSession == session_id)
        & (FitsFileModel.fitsFileSoftDelete == False)
        & (FitsFileModel.fitsFileType.in_(_light_type_values()))
        & (FitsFileModel.fitsFileStacked == 1)
    )
    return q.count() == 0


def _mark_files_stacked(file_ids: List[str]) -> None:
    from astrofiler.models import fitsFile as FitsFileModel

    if not file_ids:
        return

    FitsFileModel.update(fitsFileStacked=1).where(FitsFileModel.fitsFileId.in_(file_ids)).execute()


def stack_session(session_id: str, dry_run: bool, logger: logging.Logger, photometric: bool = False) -> bool:
    from astrofiler.core.master_manager import get_master_manager
    from astrofiler.models import fitsSession as FitsSessionModel

    try:
        session = FitsSessionModel.get_by_id(session_id)
    except Exception:
        logger.error(f"Session not found: {session_id}")
        return False

    object_name = session.fitsSessionObjectName or 'Unknown'
    if object_name.lower() in ['bias', 'dark', 'flat']:
        logger.info(f"Skipping calibration session {session_id} ({object_name})")
        return True

    precal = _is_precalibrated_session(session.fitsSessionTelescope, session.fitsSessionImager)
    candidates = _get_stack_candidates(session_id=str(session.fitsSessionId), precalibrated=precal)

    if not candidates:
        if precal:
            logger.info(f"No light frames found for precalibrated session {session_id}; skipping")
        else:
            logger.info(
                f"No calibrated light frames found for session {session_id}; skipping (calibrate first in GUI or via AutoCalibration)"
            )
        return True

    file_paths = [f.fitsFileName for f in candidates if f.fitsFileName and os.path.exists(f.fitsFileName)]
    if len(file_paths) < 2:
        logger.info(f"Not enough frames to stack for session {session_id} (found {len(file_paths)}); skipping")
        return True

    if photometric:
        from astrofiler.core.utils import sanitize_filesystem_name

        out_dir = os.path.dirname(file_paths[0])
        safe_object = sanitize_filesystem_name(object_name or 'Unknown')
        date_str = str(session.fitsSessionDate) if session.fitsSessionDate else 'unknown_date'
        output_path = os.path.join(out_dir, f"photometric_stack_{safe_object}_{date_str}_{session.fitsSessionId}.fits")
    else:
        output_path = _default_output_path(session, file_paths, object_name)

    best_ref_path = _select_best_reference_path(candidates)

    if dry_run:
        mode = 'photometric' if photometric else 'deep'
        logger.info(f"[DRY RUN] Would stack ({mode}) session {session_id} -> {output_path}")
        logger.info(f"[DRY RUN]   Frames: {len(file_paths)}")
        if best_ref_path:
            logger.info(f"[DRY RUN]   Reference: {best_ref_path}")
        return True

    if os.path.exists(output_path):
        logger.info(f"Stack already exists for session {session_id}: {output_path}")
        return True

    def _progress_callback(current, total, message):
        # Keep CLI output minimal; log milestones only.
        if message:
            logger.info(str(message))

    mode = 'photometric' if photometric else 'deep'
    logger.info(f"Stacking ({mode}) session {session_id} ({object_name})")
    logger.info(f"Output: {output_path}")

    master_manager = get_master_manager()
    if photometric:
        ok = master_manager._create_light_stack_photometric_mean(
            file_paths=file_paths,
            output_path=output_path,
            reference_path=best_ref_path,
            progress_callback=_progress_callback,
            thumbnail_session_id=str(session.fitsSessionId),
        )
    else:
        ok = master_manager._create_master_sigma_clip(
            file_paths=file_paths,
            output_path=output_path,
            cal_type='light',
            reference_path=best_ref_path,
            progress_callback=_progress_callback,
            thumbnail_session_id=str(session.fitsSessionId),
        )

    if not ok or not os.path.exists(output_path):
        logger.error(f"Stack failed for session {session_id}")
        return False

    try:
        _mark_files_stacked([str(f.fitsFileId) for f in candidates if getattr(f, 'fitsFileId', None)])
    except Exception as e:
        logger.warning(f"Stack created but failed to mark files stacked in DB: {e}")

    logger.info(f"Stack created: {output_path}")
    return True


def _select_target_sessions(mode_all: bool, mode_unstacked: bool, single_session: Optional[str]):
    from astrofiler.models import fitsSession as FitsSessionModel

    # Light sessions are sessions that are not auto-calibration and not named Bias/Dark/Flat.
    q = FitsSessionModel.select().where(
        (FitsSessionModel.is_auto_calibration == False) | (FitsSessionModel.is_auto_calibration.is_null())
    )

    sessions = []
    for s in q:
        obj = (s.fitsSessionObjectName or '').strip().lower()
        if obj in ['bias', 'dark', 'flat']:
            continue
        sessions.append(s)

    if single_session:
        return [s for s in sessions if str(s.fitsSessionId) == str(single_session)]

    if mode_all:
        return sessions

    # mode_unstacked
    return [s for s in sessions if _session_is_unstacked(str(s.fitsSessionId))]


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Batch stack light sessions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true', help='Stack all light sessions')
    group.add_argument('--unstacked', action='store_true', help='Stack only unstacked light sessions')
    group.add_argument('--session', type=str, help='Stack a single session by session ID')

    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without writing output files')
    parser.add_argument(
        '--photometric',
        action='store_true',
        help='Use photometry-safe stacking (registered mean, no sigma clipping). Default is deep/pretty sigma-clipped stacking.',
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info('=== AstroFiler Stack Starting ===')
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        from astrofiler.database import setup_database
        setup_database()

        sessions = _select_target_sessions(args.all, args.unstacked, args.session)
        if args.session and not sessions:
            logger.error(f"Session not found or not a light session: {args.session}")
            return 2

        logger.info(f"Sessions selected: {len(sessions)}")

        failures = 0
        for s in sessions:
            ok = stack_session(
                str(s.fitsSessionId),
                dry_run=args.dry_run,
                logger=logger,
                photometric=bool(args.photometric),
            )
            if not ok:
                failures += 1

        if failures:
            logger.error(f"Completed with failures: {failures}/{len(sessions)}")
            return 1

        logger.info('Stack complete')
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
