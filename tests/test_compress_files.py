"""Internal FITS tile compression must be lossless and never harm the original."""

import numpy as np
from astropy.io import fits

from astrofiler.core.compress_files import FitsCompressor


def _compressor(tmp_path):
    ini = tmp_path / 'astrofiler.ini'
    ini.write_text('[DEFAULT]\ncompress_fits=true\nverify_compression=true\n')
    return FitsCompressor(str(ini))


def _write(path, data):
    hdu = fits.PrimaryHDU(data)
    hdu.header['OBJECT'] = 'M13'
    hdu.header['HISTORY'] = 'first step'
    hdu.header['HISTORY'] = 'second step'
    hdu.header['COMMENT'] = 'a comment'
    hdu.writeto(path)


def test_float_image_round_trips_exactly_with_history(tmp_path):
    rng = np.random.default_rng(1)
    data = rng.normal(1000, 50, (64, 64)).astype(np.float32)
    data[3, 3] = np.nan
    src = tmp_path / 'light.fits'
    _write(src, data)

    out = _compressor(tmp_path)._compress_fits_internal(str(src), True, 'fits_gzip2')

    assert out == str(src)
    with fits.open(src) as hdul:
        assert any(isinstance(h, fits.CompImageHDU) for h in hdul)
        img = next(h for h in hdul if isinstance(h, fits.CompImageHDU))
        assert np.array_equal(img.data, data, equal_nan=True)
        hist = [c.value for h in hdul for c in h.header.cards if c.keyword == 'HISTORY']
        assert 'first step' in hist and 'second step' in hist  # none lost
        assert hdul[0].header['OBJECT'] == 'M13'


def test_failed_verification_leaves_original_untouched(tmp_path, monkeypatch):
    data = np.arange(400, dtype=np.int16).reshape(20, 20)
    src = tmp_path / 'bias.fits'
    _write(src, data)
    before = src.read_bytes()
    comp = _compressor(tmp_path)
    monkeypatch.setattr(comp, '_verify_fits_internal_compression', lambda *a: False)

    assert comp._compress_fits_internal(str(src), True, 'fits_gzip2') is None
    assert src.read_bytes() == before
    assert not list(tmp_path.glob('*.tmp'))
