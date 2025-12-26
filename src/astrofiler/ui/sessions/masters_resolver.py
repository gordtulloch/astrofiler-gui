from __future__ import annotations

import os
from typing import Iterable, List, Set, Tuple

from ...core.master_manager import get_master_manager


def find_matching_masters_for_light_session(session, light_files: Iterable) -> List[Tuple[str, str]]:
    """Return a list of (master_type, master_path) for a light session.

    - Bias/Dark are resolved once from session parameters.
    - Flat masters are filter-dependent; we return a master for each filter present
      in the session's light files (falling back to the session filter).

    This helper is UI-agnostic and does not touch the filesystem besides existence checks.
    """
    master_files: List[Tuple[str, str]] = []

    filters: Set[str] = set(
        [getattr(lf, 'fitsFileFilter', None) for lf in light_files if getattr(lf, 'fitsFileFilter', None)]
    )

    session_data = {
        'telescope': getattr(session, 'fitsSessionTelescope', None),
        'instrument': getattr(session, 'fitsSessionImager', None),
        'exposure_time': getattr(session, 'fitsSessionExposure', None),
        'filter_name': getattr(session, 'fitsSessionFilter', None),
        'binning_x': getattr(session, 'fitsSessionBinningX', None),
        'binning_y': getattr(session, 'fitsSessionBinningY', None),
        'ccd_temp': getattr(session, 'fitsSessionCCDTemp', None),
        'gain': getattr(session, 'fitsSessionGain', None),
        'offset': getattr(session, 'fitsSessionOffset', None),
    }

    master_manager = get_master_manager()

    master_bias = master_manager.find_matching_master(session_data, 'bias')
    master_dark = master_manager.find_matching_master(session_data, 'dark')

    if master_bias and os.path.exists(master_bias.master_path):
        master_files.append(('bias', master_bias.master_path))

    if master_dark and os.path.exists(master_dark.master_path):
        master_files.append(('dark', master_dark.master_path))

    # Flat masters are filter-dependent.
    for flat_filter_name in (filters or {getattr(session, 'fitsSessionFilter', None)}):
        if not flat_filter_name:
            continue
        flat_session_data = dict(session_data)
        flat_session_data['filter_name'] = flat_filter_name
        master_flat = master_manager.find_matching_master(flat_session_data, 'flat')
        if master_flat and os.path.exists(master_flat.master_path):
            master_files.append(('flat', master_flat.master_path))

    # De-dupe by path while preserving order (prevents double-counting the same master).
    seen: Set[str] = set()
    unique: List[Tuple[str, str]] = []
    for t, p in master_files:
        if p in seen:
            continue
        seen.add(p)
        unique.append((t, p))
    return unique
