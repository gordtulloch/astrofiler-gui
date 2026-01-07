#!/usr/bin/env python3
r"""Photometry.py - Command line utility for automated aperture photometry on FITS/XISF images.

This is an initial v1.3.0 scaffold: it performs instrumental aperture photometry
and writes a CSV per input image.

Examples:
    .venv\Scripts\python commands\Photometry.py path\to\image.fits
    .venv\Scripts\python commands\Photometry.py path\to\image.xisf --aperture 5
    .venv\Scripts\python commands\Photometry.py path\to\folder --glob "*_astro.fits"
"""

import argparse
import logging
import os
import sys
from typing import List


# Configure Python path for new package structure - must be before any astrofiler imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, "src")

# Ensure src path is first in path to avoid conflicts with root astrofiler.py
if src_path in sys.path:
    sys.path.remove(src_path)
sys.path.insert(0, src_path)


def setup_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.FileHandler("astrofiler.log", mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    logging.getLogger("peewee").setLevel(logging.WARNING)
    return logging.getLogger(__name__)


def _iter_inputs(path_or_file: str, glob_pattern: str) -> List[str]:
    if os.path.isdir(path_or_file):
        import glob

        return sorted(glob.glob(os.path.join(path_or_file, glob_pattern)))
    return [path_or_file]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated aperture photometry (instrumental magnitudes) for FITS/XISF",
    )
    parser.add_argument("input", help="Input FITS/XISF file or a directory")
    parser.add_argument("--glob", default="*.fits", help="Glob pattern when input is a directory")
    parser.add_argument("-o", "--output", default=None, help="Output CSV path (single-file mode). Default: next to input")
    parser.add_argument(
        "--fwhm",
        type=float,
        default=4.0,
        help="(Deprecated) Star finder FWHM (pixels). SEP does not use this.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=5.0,
        help="(Alias) Detection threshold in SNR units (legacy name from sigma threshold)",
    )
    parser.add_argument(
        "--source-snr",
        type=float,
        default=None,
        help="SEP detection threshold in SNR units (overrides --threshold)",
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=5,
        help="SEP minimum area (pixels) for detected sources",
    )
    parser.add_argument("--max-sources", type=int, default=500, help="Max sources to measure")
    parser.add_argument("--aperture", type=float, default=4.0, help="Aperture radius (pixels)")
    parser.add_argument("--annulus-in", type=float, default=6.0, help="Background annulus inner radius (pixels)")
    parser.add_argument("--annulus-out", type=float, default=10.0, help="Background annulus outer radius (pixels)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)

    from astrofiler.core.photometry import PhotometryOptions, run_aperture_photometry, write_photometry_csv
    from astrofiler.core.file_processing import FileProcessor

    source_snr = float(args.source_snr) if args.source_snr is not None else float(args.threshold)

    options = PhotometryOptions(
        fwhm_pixels=float(args.fwhm),
        threshold_sigma=float(args.threshold),
        source_snr=source_snr,
        min_area_pixels=int(args.min_area),
        max_sources=int(args.max_sources),
        aperture_radius_pixels=float(args.aperture),
        annulus_inner_radius_pixels=float(args.annulus_in),
        annulus_outer_radius_pixels=float(args.annulus_out),
    )

    inputs = _iter_inputs(args.input, args.glob)
    if not inputs:
        logger.error("No input files matched")
        return 2

    fp = FileProcessor()
    ok_any = False
    for path in inputs:
        if not os.path.exists(path):
            logger.warning(f"Missing file: {path}")
            continue

        in_path = path
        if path.lower().endswith(".xisf"):
            logger.info(f"Converting XISF to FITS: {path}")
            in_path = fp.convertXisfToFits(path, outputFile=None)
            if not in_path or not os.path.exists(in_path):
                logger.error(f"Failed to convert XISF: {path}")
                continue

        rows = run_aperture_photometry(in_path, options=options)
        if args.output and len(inputs) == 1:
            out_csv = args.output
        else:
            base = os.path.splitext(os.path.basename(in_path))[0]
            out_csv = os.path.join(os.path.dirname(in_path), f"photometry_{base}.csv")

        write_photometry_csv(rows, out_csv)
        logger.info(f"Photometry: {len(rows)} sources -> {out_csv}")
        ok_any = True

    return 0 if ok_any else 1


if __name__ == "__main__":
    raise SystemExit(main())
