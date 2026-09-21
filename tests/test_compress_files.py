"""Tests for FITS tile compression (astrofiler.core.compress_files)."""

import hashlib

import numpy as np
import pytest
from astropy.io import fits

from astrofiler.core.compress_files import FitsCompressor


@pytest.fixture
def compressor(tmp_path, monkeypatch):
    # FitsCompressor reads astrofiler.ini from the cwd; run in an empty dir so tests
    # never pick up a developer's real configuration.
    monkeypatch.chdir(tmp_path)
    comp = FitsCompressor()
    comp.verify_compression = True
    return comp


def _write_fits(path, data, in_extension=False):
    if in_extension:
        fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(data)]).writeto(path, overwrite=True)
    else:
        fits.PrimaryHDU(data).writeto(path, overwrite=True)


def _tile_type(path):
    """ZCMPTYPE of the first tile-compressed HDU (raw header; astropy hides it on the image view)."""
    with fits.open(path, disable_image_compression=True) as hdul:
        for hdu in hdul:
            if hdu.header.get("ZIMAGE"):
                return hdu.header["ZCMPTYPE"]
    return None


def _first_image(path):
    with fits.open(path) as hdul:
        return next(hdu.data.copy() for hdu in hdul if hdu.data is not None)


def _sample(dtype):
    rng = np.random.default_rng(1)
    data = rng.normal(2000, 50, (64, 96))
    if np.dtype(dtype).kind in "iu":
        data = data.clip(0, np.iinfo(dtype).max)
    return data.astype(dtype)


@pytest.mark.parametrize(
    "dtype, expected_type",
    [
        (np.uint16, "RICE_1"),   # 8/16-bit integers: Rice is smallest and lossless
        (np.int16, "RICE_1"),
        (np.int32, "GZIP_2"),    # wider integers
        (np.float32, "GZIP_2"),  # floats
        (np.float64, "GZIP_2"),
    ],
)
def test_auto_selects_algorithm_by_dtype_and_is_lossless(compressor, tmp_path, dtype, expected_type):
    path = tmp_path / "frame.fits"
    data = _sample(dtype)
    _write_fits(path, data)

    out = compressor.compress_fits_file(str(path), replace_original=True, algorithm="auto")

    assert out == str(path)  # in-place import compression keeps the file name
    assert _tile_type(out) == expected_type
    # Bit-for-bit: astropy quantizes float tiles by default, which is lossy.
    assert np.array_equal(_first_image(out), data)


def test_auto_handles_image_in_extension_hdu(compressor, tmp_path):
    path = tmp_path / "ext.fits"
    data = _sample(np.uint16)
    _write_fits(path, data, in_extension=True)

    out = compressor.compress_fits_file(str(path), replace_original=True, algorithm="auto")

    assert _tile_type(out) == "RICE_1"
    assert np.array_equal(_first_image(out), data)


@pytest.mark.parametrize(
    "algorithm, expected_type",
    [("fits_gzip1", "GZIP_1"), ("fits_gzip2", "GZIP_2"), ("fits_rice", "RICE_1")],
)
def test_explicit_algorithms_are_honoured(compressor, tmp_path, algorithm, expected_type):
    path = tmp_path / "frame.fits"
    data = _sample(np.uint16)
    _write_fits(path, data)

    out = compressor.compress_fits_file(str(path), replace_original=True, algorithm=algorithm)

    assert _tile_type(out) == expected_type
    assert np.array_equal(_first_image(out), data)


def test_rice_is_never_used_for_float_data(compressor, tmp_path):
    """RICE on floats needs quantization (lossy), so it must fall back to GZIP_2."""
    path = tmp_path / "float.fits"
    data = _sample(np.float32)
    _write_fits(path, data)

    out = compressor.compress_fits_file(str(path), replace_original=True, algorithm="fits_rice")

    assert _tile_type(out) == "GZIP_2"
    assert np.array_equal(_first_image(out), data)


def test_failed_verification_leaves_original_untouched(compressor, tmp_path, monkeypatch):
    """Verification runs on the temp file, so a failure must not damage the source."""
    path = tmp_path / "frame.fits"
    _write_fits(path, _sample(np.uint16))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(compressor, "_verify_fits_internal_compression", lambda *a, **k: False)

    out = compressor.compress_fits_file(str(path), replace_original=True, algorithm="auto")

    assert out is None
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert not (tmp_path / "frame.fits.tmp").exists()


def test_already_compressed_file_is_skipped(compressor, tmp_path):
    path = tmp_path / "frame.fits"
    _write_fits(path, _sample(np.uint16))
    first = compressor.compress_fits_file(str(path), replace_original=True, algorithm="auto")
    size = path.stat().st_size

    second = compressor.compress_fits_file(first, replace_original=True, algorithm="auto")

    assert second == first
    assert path.stat().st_size == size
