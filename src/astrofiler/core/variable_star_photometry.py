from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
import astropy.units as u

from astrofiler.core.photometry import (
    aperture_photometry_sep,
    extract_sources_sep,
    instrumental_mag,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VariableStarPhotometryOptions:
    band: str = "V"
    field_of_view_arcmin: float = 18.5
    brightest_comp_mag: float = 11.0
    dimmest_comp_mag: float = 13.0
    source_snr: float = 20.0
    match_radius_arcsec: float = 4.0
    aperture_radius_pixels: float = 6.0
    bkg_subtract: bool = True


def _fetch_json(url: str, timeout_s: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "AstroFiler/1.3"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def get_aavso_comparison_stars(
    ra_deg: float,
    dec_deg: float,
    *,
    band: str = "V",
    field_of_view_arcmin: float = 18.5,
) -> Tuple[List[dict], str]:
    """Download comparison stars via AAVSO VSP API.

    Returns (stars, chart_id).
    Each star dict includes: auid, ra, dec, vmag, error.
    """
    base = "https://www.aavso.org/apps/vsp/api/chart/"
    params = {
        "format": "json",
        "fov": str(field_of_view_arcmin),
        "maglimit": "18.5",
        "ra": str(ra_deg),
        "dec": str(dec_deg),
    }
    url = f"{base}?{urllib.parse.urlencode(params)}"
    doc = _fetch_json(url)

    chart_id = str(doc.get("chartid", ""))
    stars: List[dict] = []
    for star in doc.get("photometry", []) or []:
        row: dict = {
            "auid": star.get("auid"),
            "ra": star.get("ra"),
            "dec": star.get("dec"),
            "vmag": None,
            "error": None,
        }
        for b in star.get("bands", []) or []:
            if str(b.get("band")) == str(band):
                row["vmag"] = b.get("mag")
                row["error"] = b.get("error")
                break
        stars.append(row)
    return stars, chart_id


def resolve_target_coordinates(star_name: str) -> SkyCoord:
    """Resolve a star name to ICRS coordinates.

    Uses Astropy's name resolver (network required).
    """
    # SkyCoord.from_name returns ICRS coordinate.
    return SkyCoord.from_name(star_name)


def _load_fits_image(path: str) -> Tuple[np.ndarray, fits.Header]:
    with fits.open(path, memmap=False) as hdul:
        hdu = hdul[0]
        data = np.asarray(hdu.data, dtype=np.float32)
        header = hdu.header
    if data.ndim != 2:
        raise ValueError(f"Expected 2D FITS image; got shape={data.shape} for {path}")
    return data, header


def _pixel_radius_for_arcsec(wcs: WCS, arcsec: float) -> float:
    # Approximate pixel scale using tangent-plane scales
    scales = proj_plane_pixel_scales(wcs) * u.deg
    # take mean of x/y scale
    mean_scale_deg = float(np.mean(scales.to(u.deg).value))
    mean_scale_arcsec = mean_scale_deg * 3600.0
    if mean_scale_arcsec <= 0:
        return float("nan")
    return float(arcsec) / mean_scale_arcsec


def match_catalog_to_sources(
    wcs: WCS,
    sources: np.ndarray,
    catalog: Sequence[dict],
    *,
    match_radius_arcsec: float = 4.0,
) -> List[dict]:
    """Match catalog stars to nearest SEP source within radius.

    Returns list of catalog dicts enriched with x,y,peak when matched.
    """
    if sources is None or len(sources) == 0:
        return []

    src_x = np.asarray(sources["x"], dtype=float)
    src_y = np.asarray(sources["y"], dtype=float)

    radius_pix = _pixel_radius_for_arcsec(wcs, match_radius_arcsec)
    if not np.isfinite(radius_pix) or radius_pix <= 0:
        radius_pix = 4.0  # fallback similar to the notebook

    matched: List[dict] = []
    for star in catalog:
        try:
            ra = float(star["ra"])
            dec = float(star["dec"])
        except Exception:
            continue
        sky = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
        x, y = wcs.world_to_pixel(sky)
        x = float(x)
        y = float(y)

        dx = src_x - x
        dy = src_y - y
        dist2 = dx * dx + dy * dy
        j = int(np.argmin(dist2))
        if float(dist2[j]) <= float(radius_pix * radius_pix):
            s = dict(star)
            s["x"] = x
            s["y"] = y
            try:
                s["peak"] = float(sources["peak"][j])
            except Exception:
                s["peak"] = None
            matched.append(s)

    return matched


def ensemble_fit(
    instrumental_mags: np.ndarray,
    catalog_mags: np.ndarray,
) -> Tuple[np.poly1d, np.ndarray]:
    fit, residuals, rank, singular_values, rcond = np.polyfit(
        instrumental_mags, catalog_mags, 1, full=True
    )
    return np.poly1d(fit), residuals


def run_variable_star_photometry(
    stacked_fits_path: str,
    *,
    star_name: str,
    options: Optional[VariableStarPhotometryOptions] = None,
    check_auid: Optional[str] = None,
) -> Dict:
    """Run the RWAUR-style workflow on a photometric stack.

    Output dict contains summary + per-star rows.
    """
    if options is None:
        options = VariableStarPhotometryOptions()

    data, header = _load_fits_image(stacked_fits_path)
    wcs = WCS(header)
    if wcs is None or not wcs.has_celestial:
        raise ValueError("Stacked FITS must contain a valid celestial WCS for variable star processing")

    target_coord = resolve_target_coordinates(star_name)
    ra_deg = float(target_coord.icrs.ra.deg)
    dec_deg = float(target_coord.icrs.dec.deg)

    comp, chart_id = get_aavso_comparison_stars(
        ra_deg,
        dec_deg,
        band=options.band,
        field_of_view_arcmin=options.field_of_view_arcmin,
    )

    # Add the target as a synthetic catalog entry
    catalog = list(comp)
    catalog.append({"auid": "target", "ra": ra_deg, "dec": dec_deg, "vmag": None, "error": None})

    sources = extract_sources_sep(data, source_snr=options.source_snr)
    matched = match_catalog_to_sources(
        wcs,
        sources,
        catalog,
        match_radius_arcsec=options.match_radius_arcsec,
    )

    if not matched:
        raise RuntimeError("No catalog stars matched to detected sources")

    xs = np.array([m["x"] for m in matched], dtype=float)
    ys = np.array([m["y"] for m in matched], dtype=float)
    flux = aperture_photometry_sep(
        data,
        xs,
        ys,
        aperture_radius_pixels=options.aperture_radius_pixels,
        subtract_background=options.bkg_subtract,
    )

    rows: List[dict] = []
    for i, m in enumerate(matched):
        row = dict(m)
        row["aperture_sum"] = float(flux[i])
        row["instrumental_mag"] = float(instrumental_mag(float(flux[i])))
        rows.append(row)

    # Select comp stars for linear fit
    comp_for_fit = [
        r
        for r in rows
        if r.get("auid") != "target"
        and r.get("vmag") is not None
        and float(r.get("vmag")) > float(options.brightest_comp_mag)
        and float(r.get("vmag")) < float(options.dimmest_comp_mag)
        and np.isfinite(float(r.get("instrumental_mag")))
    ]

    if len(comp_for_fit) < 2:
        raise RuntimeError("Not enough comparison stars in magnitude range for ensemble fit")

    x_fit = np.array([float(r["instrumental_mag"]) for r in comp_for_fit], dtype=float)
    y_fit = np.array([float(r["vmag"]) for r in comp_for_fit], dtype=float)

    fit_fn, residuals = ensemble_fit(x_fit, y_fit)

    target_rows = [r for r in rows if r.get("auid") == "target"]
    if not target_rows:
        raise RuntimeError("Target did not match a detected source")
    target_inst = float(target_rows[0]["instrumental_mag"])
    target_mag = float(fit_fn(target_inst))

    check_mag = None
    if check_auid:
        check_rows = [r for r in rows if r.get("auid") == check_auid]
        if check_rows:
            check_mag = float(fit_fn(float(check_rows[0]["instrumental_mag"])))

    # Observation date for AAVSO summary
    obs_dt = None
    date_obs = header.get("DATE-OBS")
    if date_obs:
        try:
            obs_dt = datetime.fromisoformat(str(date_obs).replace("Z", "+00:00"))
        except Exception:
            obs_dt = None

    return {
        "star_name": star_name,
        "band": options.band,
        "chart_id": chart_id,
        "stacked_fits": stacked_fits_path,
        "target_ra_deg": ra_deg,
        "target_dec_deg": dec_deg,
        "target_instrumental_mag": target_inst,
        "target_magnitude": target_mag,
        "residuals": residuals.tolist() if hasattr(residuals, "tolist") else [float(residuals)],
        "check_auid": check_auid,
        "check_magnitude": check_mag,
        "date_obs": str(date_obs) if date_obs else None,
        "rows": rows,
        "ensemble_auids": [r.get("auid") for r in comp_for_fit],
    }
