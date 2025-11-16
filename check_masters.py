#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')
from astropy.io import fits
import numpy as np
from astrofiler.models import Masters

# Find a dark and flat for the same session
dark = Masters.select().where(Masters.type == 'dark').order_by(Masters.creation_date.desc()).first()
flat = Masters.select().where(Masters.type == 'flat').order_by(Masters.creation_date.desc()).first()
bias = Masters.select().where(Masters.type == 'bias').order_by(Masters.creation_date.desc()).first()

if bias:
    b_data = fits.open(bias.master_path)[0].data
    print(f'BIAS: min={np.min(b_data)}, max={np.max(b_data)}, mean={np.mean(b_data):.1f}, median={np.median(b_data):.1f}')

if dark:
    d_data = fits.open(dark.master_path)[0].data
    print(f'DARK: min={np.min(d_data)}, max={np.max(d_data)}, mean={np.mean(d_data):.1f}, median={np.median(d_data):.1f}')

if flat:
    f_data = fits.open(flat.master_path)[0].data
    print(f'FLAT: min={np.min(f_data):.1f}, max={np.max(f_data):.1f}, mean={np.mean(f_data):.1f}, median={np.median(f_data):.1f}')

# Manual calculation
print("\n--- Manual Calibration Check ---")
light_path = 'K:/00 REPOSITORY/Light/AB Aur/Celestron_C8_2032@F_10.0/ZWO_CCD_ASI183MM_Pro/20240226/AB Aur-Celestron_C8_2032@F_10.0-ZWO_CCD_ASI183MM_Pro-V-20240226015546-30.0s-1x1-t-25.0.fits'
light = fits.open(light_path)[0].data.astype(np.float64)
print(f'LIGHT: min={np.min(light)}, max={np.max(light)}, mean={np.mean(light):.1f}')

result = light - d_data
print(f'After Dark Subtraction: min={np.min(result):.1f}, max={np.max(result):.1f}, mean={np.mean(result):.1f}')

flat_median = np.median(f_data)
flat_norm = f_data / flat_median
result = result / flat_norm
print(f'After Flat Division: min={np.min(result):.1f}, max={np.max(result):.1f}, mean={np.mean(result):.1f}')
