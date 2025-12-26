from __future__ import annotations

import gzip
import logging
import os
import shutil
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def _is_fits_tile_compressed(path: str) -> bool:
    lower = (path or '').lower()
    if not lower.endswith(('.fits', '.fit', '.fts', '.fz', '.fits.fz', '.fit.fz', '.fts.fz')):
        return False

    try:
        from astropy.io import fits

        with fits.open(path, memmap=False) as hdul:
            for hdu in hdul:
                if isinstance(hdu, fits.CompImageHDU):
                    return True
                try:
                    if bool(hdu.header.get('ZIMAGE', False)):
                        return True
                except Exception:
                    continue
    except Exception:
        return False

    return False


def is_compressed_path(path: str) -> bool:
    if not path:
        return False
    lower = path.lower()
    if lower.endswith(('.gz', '.bz2', '.xz', '.fz')):
        return True
    return _is_fits_tile_compressed(path)


def get_decompressed_dest_path(dest_path: str) -> str:
    """If dest_path indicates a compressed file, return the decompressed output path."""
    if not dest_path:
        return ''
    lower = dest_path.lower()
    if lower.endswith('.fits.fz'):
        return dest_path[:-3]  # strip .fz
    if lower.endswith('.fit.fz') or lower.endswith('.fts.fz'):
        return dest_path[:-3]
    if lower.endswith('.fits.gz'):
        return dest_path[:-3]
    if lower.endswith('.fit.gz') or lower.endswith('.fts.gz'):
        return dest_path[:-3]
    if lower.endswith('.gz'):
        return dest_path[:-3]
    if lower.endswith('.fz'):
        return dest_path[:-3]
    if lower.endswith('.bz2'):
        return dest_path[:-4]
    return dest_path


def decompress_to(src_path: str, dest_path: str) -> bool:
    """Decompress a compressed FITS file into dest_path.

    Supports .fits.fz (via astropy) and .gz (via gzip module).
    """
    try:
        if not src_path or not os.path.exists(src_path):
            return False

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        lower = src_path.lower()

        # FITS tile compression can be present with or without the conventional .fz suffix.
        if lower.endswith('.fz') or _is_fits_tile_compressed(src_path):
            # .fits.fz (or .fz) - FITS tiled compression (fpack) is typically stored
            # as an image-compression extension (CompImageHDU / BINTABLE) while the
            # primary HDU may have no data. We must read the first HDU that yields data.
            from astropy.io import fits

            with fits.open(src_path, memmap=False) as hdul:
                primary_header = hdul[0].header

                data_hdu = None
                for hdu in hdul:
                    try:
                        if getattr(hdu, 'data', None) is not None:
                            data_hdu = hdu
                            break
                    except Exception:
                        continue

                if data_hdu is None:
                    return False

                data = data_hdu.data

            # Prefer preserving primary header metadata (WCS/object/etc) but allow astropy
            # to fix structural keywords to match the decompressed data.
            fits.writeto(dest_path, data, header=primary_header, overwrite=True, output_verify='silentfix')
            return True

        if lower.endswith('.gz'):
            # stream-decompress
            with gzip.open(src_path, 'rb') as f_in:
                with open(dest_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return True

        # Unknown compression
        return False

    except Exception as e:
        logger.error(f"Failed to decompress {src_path} -> {dest_path}: {e}")
        return False


def create_symlink(src_path: str, dest_path: str) -> bool:
    try:
        if os.path.exists(dest_path):
            return True
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        if sys.platform == 'win32':
            import subprocess

            result = subprocess.run(
                f'mklink "{dest_path}" "{src_path}"',
                shell=True,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise Exception(f"mklink failed: {result.stderr}")
            return True

        os.symlink(src_path, dest_path)
        return True

    except Exception as e:
        logger.error(f"Failed to create symlink {dest_path} -> {src_path}: {e}")
        return False


def materialize_file(*, src_path: str, dest_path: str, copy_files: bool, decompress: bool) -> bool:
    """Create the requested file in dest_path based on options.

    - If decompress is True and src is compressed, write decompressed output into dest folder.
    - Else if copy_files is True, copy the file.
    - Else create a symlink.
    """
    try:
        if not src_path or not os.path.exists(src_path):
            return False

        if decompress and is_compressed_path(src_path):
            out_path = get_decompressed_dest_path(dest_path)
            if os.path.exists(out_path):
                return True
            return decompress_to(src_path, out_path)

        if copy_files:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            if os.path.exists(dest_path):
                return True
            shutil.copy2(src_path, dest_path)
            return True

        return create_symlink(src_path, dest_path)

    except Exception as e:
        logger.error(f"Failed to materialize {src_path} -> {dest_path}: {e}")
        return False
