import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import numpy as np
from astropy.io import fits

from astrofiler.core.light_calibration import calibrate_light_frame
from astrofiler.core.utils import exposures_match, is_dark_image_type, is_flat_dark_image_type, is_flat_image_type


def _write_fits(path, data):
    fits.PrimaryHDU(data=np.asarray(data, dtype=np.float32)).writeto(path, overwrite=True)


def test_flatdark_helpers_classify_types():
    assert is_flat_dark_image_type('FlatDark')
    assert is_flat_dark_image_type('dark_flat')
    assert not is_dark_image_type('FlatDark')
    assert not is_flat_image_type('FlatDark')
    assert is_dark_image_type('Dark')
    assert is_flat_image_type('Flat')
    assert exposures_match('0.500', '0.5')


def test_calibrate_light_frame_uses_flatdark_for_flat_correction(tmp_path):
    light_path = tmp_path / 'light.fits'
    dark_path = tmp_path / 'dark.fits'
    flat_path = tmp_path / 'flat.fits'
    bias_path = tmp_path / 'bias.fits'
    flat_dark_path = tmp_path / 'flatdark.fits'

    _write_fits(light_path, [[100, 100], [100, 100]])
    _write_fits(dark_path, [[10, 10], [10, 10]])
    _write_fits(flat_path, [[20, 22], [24, 26]])
    _write_fits(bias_path, [[2, 2], [2, 2]])
    _write_fits(flat_dark_path, [[5, 5], [5, 5]])

    result = calibrate_light_frame(
        light_path=str(light_path),
        dark_master=str(dark_path),
        flat_master=str(flat_path),
        bias_master=str(bias_path),
        flat_dark_master=str(flat_dark_path),
    )

    assert result.get('success') is True
    assert any(step.startswith('FLATDARK:') for step in result['calibration_steps'])
    assert 'flat-dark corrected' in result['calibration_steps'][-1]

    with fits.open(result['output_path']) as hdul:
        data = hdul[0].data.astype(np.float64)
        header = hdul[0].header

    expected_light = np.array([[92.0, 92.0], [92.0, 92.0]])
    expected_flat = np.array([[17.0, 19.0], [21.0, 23.0]])
    expected = expected_light / (expected_flat / expected_flat.mean())

    np.testing.assert_allclose(data, expected, rtol=0, atol=1e-5)
    assert header['FDARKMST'] == 'flatdark.fits'
