from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats


try:
    import sep

    _SEP_AVAILABLE = True
except ImportError:  # pragma: no cover
    sep = None  # type: ignore
    _SEP_AVAILABLE = False


@dataclass(frozen=True)
class PhotometryOptions:
    # Legacy options kept for compatibility with earlier DAOStarFinder-based version.
    # The SEP-based implementation uses `source_snr` for detection.
    fwhm_pixels: float = 4.0
    threshold_sigma: float = 5.0

    # SEP detection tuning
    source_snr: float = 5.0
    min_area_pixels: int = 5

    max_sources: int = 500
    aperture_radius_pixels: float = 4.0
    annulus_inner_radius_pixels: float = 6.0
    annulus_outer_radius_pixels: float = 10.0


def _require_sep() -> None:
    if not _SEP_AVAILABLE:
        raise ImportError(
            "SEP is required for SEP-based photometry. Install with: pip install sep"
        )


def instrumental_mag(flux: float) -> float:
    """Compute instrumental magnitude from flux.

    Uses: m_inst = -2.5 log10(flux)
    """
    return _instrumental_mag(flux)


def _safe_log10(x: float) -> float:
    if x <= 0:
        return float("nan")
    return math.log10(x)


def _instrumental_mag(flux: float) -> float:
    # m_inst = -2.5 log10(flux)
    return -2.5 * _safe_log10(float(flux))


def _load_fits_image(path: str) -> Tuple[np.ndarray, fits.Header]:
    with fits.open(path, memmap=False) as hdul:
        hdu = hdul[0]
        data = np.asarray(hdu.data, dtype=float)
        header = hdu.header
    if data.ndim != 2:
        raise ValueError(f"Expected 2D FITS image; got shape={data.shape} for {path}")
    return data, header


def _annulus_median_background(
    image: np.ndarray,
    x: float,
    y: float,
    *,
    r_in: float,
    r_out: float,
) -> float:
    h, w = image.shape

    x0 = int(max(0, math.floor(x - r_out)))
    x1 = int(min(w, math.ceil(x + r_out + 1)))
    y0 = int(max(0, math.floor(y - r_out)))
    y1 = int(min(h, math.ceil(y + r_out + 1)))
    if x1 <= x0 or y1 <= y0:
        return float("nan")

    cutout = image[y0:y1, x0:x1]
    yy, xx = np.indices(cutout.shape)
    dx = xx + x0 - float(x)
    dy = yy + y0 - float(y)
    rr2 = dx * dx + dy * dy

    m = (rr2 >= float(r_in * r_in)) & (rr2 <= float(r_out * r_out))
    if not np.any(m):
        return float("nan")

    vals = cutout[m]
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return float("nan")
    return float(np.nanmedian(vals))


def extract_sources_sep(data: np.ndarray, *, source_snr: float = 20.0) -> np.ndarray:
    """Extract sources and centroid positions using SEP.

    Returns the SEP objects structured array.
    """
    _require_sep()

    # SEP expects native-endian float32.
    data_sep = np.asarray(data, dtype=np.float32)
    bkg = sep.Background(data_sep)  # type: ignore[union-attr]
    data_sub = data_sep - bkg
    threshold = float(source_snr) * float(bkg.globalrms)
    objects = sep.extract(data_sub, threshold)  # type: ignore[union-attr]
    return objects


def aperture_photometry_sep(
    data: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    *,
    aperture_radius_pixels: float = 6.0,
    subtract_background: bool = True,
) -> np.ndarray:
    """Circular-aperture photometry at given (x,y) positions using SEP."""
    _require_sep()

    data_sep = np.asarray(data, dtype=np.float32)
    if subtract_background:
        bkg = sep.Background(data_sep)  # type: ignore[union-attr]
        data_sep = data_sep - bkg

    flux, fluxerr, flag = sep.sum_circle(  # type: ignore[union-attr]
        data_sep,
        x.astype(float),
        y.astype(float),
        r=float(aperture_radius_pixels),
        err=None,
        gain=1.0,
    )
    return np.asarray(flux, dtype=float)


def run_aperture_photometry(
    fits_path: str,
    options: Optional[PhotometryOptions] = None,
) -> List[dict]:
    """Run simple automated aperture photometry on a FITS image.

    Returns a list of dict rows suitable for CSV export.
    """
    if options is None:
        options = PhotometryOptions()

    _require_sep()

    image, header = _load_fits_image(fits_path)
    # Keep sigma-clipped stats for a quick sanity background estimate.
    _, median, _ = sigma_clipped_stats(image, sigma=3.0)

    # SEP expects native-endian float32.
    image_sep = np.asarray(image, dtype=np.float32)
    bkg = sep.Background(image_sep)  # type: ignore[union-attr]
    image_sub = image_sep - bkg

    # Detection threshold in units of global RMS.
    # Prefer SEP-native option if set; fall back to legacy threshold_sigma.
    snr = float(getattr(options, "source_snr", options.threshold_sigma))
    threshold = snr * float(bkg.globalrms)
    minarea = int(getattr(options, "min_area_pixels", 5))

    objects = sep.extract(image_sub, threshold, minarea=minarea)  # type: ignore[union-attr]
    if objects is None or len(objects) == 0:
        return []

    # Sort brightest first and apply max_sources cap.
    if "flux" in objects.dtype.names:
        order = np.argsort(np.asarray(objects["flux"], dtype=float))[::-1]
    elif "peak" in objects.dtype.names:
        order = np.argsort(np.asarray(objects["peak"], dtype=float))[::-1]
    else:
        order = np.arange(len(objects))

    if options.max_sources and int(options.max_sources) > 0:
        order = order[: int(options.max_sources)]
    objects = objects[order]

    x = np.asarray(objects["x"], dtype=float)
    y = np.asarray(objects["y"], dtype=float)

    # Raw aperture sum (includes local background)
    flux_raw, _, _ = sep.sum_circle(  # type: ignore[union-attr]
        image_sep,
        x,
        y,
        r=float(options.aperture_radius_pixels),
        err=None,
        gain=1.0,
    )
    flux_raw = np.asarray(flux_raw, dtype=float)

    # Local background median from annulus; net flux = raw - (bkg_median * area)
    bkg_medians: List[float] = []
    for xi, yi in zip(x, y):
        bkg_medians.append(
            _annulus_median_background(
                image_sep,
                float(xi),
                float(yi),
                r_in=float(options.annulus_inner_radius_pixels),
                r_out=float(options.annulus_outer_radius_pixels),
            )
        )
    bkg_medians_arr = np.asarray(bkg_medians, dtype=float)
    aperture_area = float(math.pi * float(options.aperture_radius_pixels) ** 2)
    flux_net = flux_raw - (bkg_medians_arr * aperture_area)

    # Optional WCS -> RA/Dec per source if header supports it.
    ra_deg = np.full_like(flux_net, fill_value=np.nan, dtype=float)
    dec_deg = np.full_like(flux_net, fill_value=np.nan, dtype=float)
    try:
        from astropy.wcs import WCS

        wcs = WCS(header)
        if wcs.has_celestial:
            world = wcs.pixel_to_world(x, y)
            ra_deg = np.array(world.ra.deg, dtype=float)
            dec_deg = np.array(world.dec.deg, dtype=float)
    except Exception:
        pass

    rows: List[dict] = []
    for idx in range(len(x)):
        rows.append(
            {
                "source_id": int(idx + 1),
                "x": float(x[idx]),
                "y": float(y[idx]),
                "flux_raw": float(flux_raw[idx]),
                "bkg_median": float(bkg_medians_arr[idx]),
                "flux_net": float(flux_net[idx]),
                "inst_mag": float(_instrumental_mag(float(flux_net[idx]))),
                "ra_deg": float(ra_deg[idx]),
                "dec_deg": float(dec_deg[idx]),
            }
        )

    return rows


def write_photometry_csv(rows: Sequence[dict], output_csv_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
    fieldnames = [
        "source_id",
        "x",
        "y",
        "flux_raw",
        "bkg_median",
        "flux_net",
        "inst_mag",
        "ra_deg",
        "dec_deg",
    ]
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
