#!/usr/bin/env python3
"""
siril_mosaic.py
Builds a mosaic from multiple panels using Siril 1.4+ via pySiril.

Pipeline (per panel):
  - Create master BIAS -> used to calibrate FLATs
  - Create master FLAT (bias-calibrated)
  - Create master DARK
  - Calibrate + (optional) debayer lights
  - Register panel lights
  - Stack panel lights (median by default) -> produces one stacked FITS per panel

Mosaic:
  - Create a sequence from all stacked panels
  - Plate solve the whole sequence and store registration info
  - Apply existing registration (astrometric)
  - Mosaic stack with maximize framing, feathering, and optional normalize-on-overlaps

Requires: Siril 1.4+, pySiril
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

# pySiril imports
from pysiril.siril import Siril
from pysiril.wrapper import Wrapper

# ---------- Utilities ----------

def log(msg: str):
    print(f"[siril-mosaic] {msg}", flush=True)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def has_any_files(p: Path) -> bool:
    return p.exists() and any(p.iterdir())

def detect_subdir(base: Path, names: List[str]) -> Optional[Path]:
    for nm in names:
        p = base / nm
        if p.exists() and p.is_dir() and has_any_files(p):
            return p
    return None

def find_panels(root: Path) -> List[Path]:
    # Any immediate child with a 'lights' (or 'light') folder is a panel
    panels = []
    for child in sorted([p for p in root.iterdir() if p.is_dir()]):
        lights = detect_subdir(child, ["lights", "light"])
        if lights:
            panels.append(child)
    return panels

# ---------- Siril helpers ----------

def srun(app: Siril, cmd: str):
    log(f"Siril> {cmd}")
    app.Execute(cmd)

def make_master_bias(cmd: Wrapper, app: Siril, bias_dir: Path, process_dir: Path):
    # Bias -> bias_stacked.fit
    srun(app, f'cd "{bias_dir.as_posix()}"')
    cmd.convert('bias', out=process_dir.as_posix(), fitseq=True)
    srun(app, f'cd "{process_dir.as_posix()}"')
    # Winsorized sigma (rej) is standard; you can tweak sigmas if desired
    cmd.stack('bias', type='rej', sigma_low=3, sigma_high=3, norm='no')

def make_master_flat(cmd: Wrapper, app: Siril, flat_dir: Path, process_dir: Path, have_bias: bool):
    # Flat -> bias-calibrated flats -> pp_flat_stacked.fit
    srun(app, f'cd "{flat_dir.as_posix()}"')
    cmd.convert('flat', out=process_dir.as_posix(), fitseq=True)
    srun(app, f'cd "{process_dir.as_posix()}"')
    if have_bias:
        cmd.preprocess('flat', bias='bias_stacked')
    else:
        # If no bias exists, flats still can be stacked; normalization will be 'mul'
        pass
    cmd.stack('pp_flat', type='rej', sigma_low=3, sigma_high=3, norm='mul')

def make_master_dark(cmd: Wrapper, app: Siril, dark_dir: Path, process_dir: Path):
    # Dark -> dark_stacked.fit
    srun(app, f'cd "{dark_dir.as_posix()}"')
    cmd.convert('dark', out=process_dir.as_posix(), fitseq=True)
    srun(app, f'cd "{process_dir.as_posix()}"')
    cmd.stack('dark', type='rej', sigma_low=3, sigma_high=3, norm='no')

def preprocess_register_stack_panel(
    cmd: Wrapper,
    app: Siril,
    panel_dir: Path,
    process_dir: Path,
    panel_out_dir: Path,
    cfa: bool,
    debayer: bool,
    panel_name: str,
    panel_stack_method: str,
):
    # Convert lights to sequence
    lights_dir = detect_subdir(panel_dir, ["lights", "light"])
    if not lights_dir:
        raise RuntimeError(f"No lights found under {panel_dir}")
    srun(app, f'cd "{lights_dir.as_posix()}"')
    cmd.convert('light', out=process_dir.as_posix(), fitseq=True)

    # Calibrate lights
    srun(app, f'cd "{process_dir.as_posix()}"')
    kwargs = {}
    if (process_dir / "dark_stacked.fit").exists():
        kwargs["dark"] = "dark_stacked"
    if (process_dir / "pp_flat_stacked.fit").exists():
        kwargs["flat"] = "pp_flat_stacked"

    # CFA/debayer handling
    if cfa:
        kwargs["cfa"] = True
        # Equalize CFA is often a good idea on OSC data
        kwargs["equalize_cfa"] = True
        if debayer:
            kwargs["debayer"] = True

    cmd.preprocess('light', **kwargs)

    # Register panel lights (classical star registration)
    cmd.register('pp_light')

    # Stack panel (median default as requested)
    ensure_dir(panel_out_dir)
    outdir = panel_out_dir.as_posix()
    # normalization addscale is common; output_norm keeps normalized copy
    cmd.stack('r_pp_light',
              type=panel_stack_method,
              norm='addscale',
              output_norm=True,
              out=outdir)

    # The stacked file will be named r_pp_light_stacked.fit in outdir
    # Rename to descriptive panel name
    src = Path(outdir) / "r_pp_light_stacked.fit"
    dst = Path(outdir) / f"{panel_name}_stacked.fit"
    if src.exists():
        try:
            src.replace(dst)
        except Exception:
            pass
    # Close sequence
    srun(app, "close")

def build_mosaic(
    app: Siril,
    stacked_dir: Path,
    final_out: Path,
    feather: int,
    overlap_norm: bool,
    scale: float,
):
    """
    Create a sequence from the stacked panels, plate-solve the whole sequence,
    apply existing registration, and mosaic-stack with maximize framing.
    """
    srun(app, f'cd "{stacked_dir.as_posix()}"')

    # Ensure the stacked panel files share a consistent prefix to build a sequence cleanly
    # We will copy/renumber into a temp working prefix 'mosaicpanel_#####.fit' using Siril 'convert -fitseq'
    # Approach: hard-link (link) or convert; using convert on FITS with -fitseq is supported.
    # First, ensure there are FITS files:
    fits = sorted(stacked_dir.glob("*_stacked.fit"))
    if len(fits) < 2:
        raise RuntimeError("Need at least two stacked panels to build a mosaic.")

    # Create a text list of filenames for convert to pick up (Siril converts by prefix; here we use current dir glob)
    # Simpler: copy/rename files to a common prefix mosaicpanel_00001.fit, ..., then generate sequence via 'convert'
    for i, f in enumerate(fits, start=1):
        newname = stacked_dir / f"mosaicpanel_{i:05d}.fit"
        if f != newname:
            try:
                # copy/rename to common prefix (rename is fine; we already renamed outputs above)
                f.replace(newname)
            except Exception:
                # fallback: create a duplicate if rename fails
                import shutil
                shutil.copy2(f, newname)

    # Now create a sequence from these mosaicpanel_*.fit
    srun(app, f'convert mosaicpanel -out="{stacked_dir.as_posix()}" -fitseq')
    # Sequence name is 'mosaicpanel' by prefix

    # Plate-solve the whole sequence and record reg info
    # Siril 1.4: seqplatesolve can solve a whole seq; registration info can be used for 'apply existing registration'
    srun(app, 'seqplatesolve mosaicpanel')

    # Apply existing registration (astrometric) to produce registered sequence on disk
    # The seqapplyreg command applies the stored transforms
    srun(app, 'seqapplyreg mosaicpanel')

    # Mosaic stack:
    # - maximize framing (large canvas)
    # - additive with scaling normalization (per Siril tutorial)
    # - option to feather seams
    # - option to normalize on overlaps for tiles with different backgrounds
    # NOTE: Use average without rejection for panel stacks; per-tile rejection was already done at panel stage.
    # We will use raw CLI to access mosaic flags explicitly.
    stack_cmd = [
        'stack r_mosaicpanel',          # registered sequence name gets 'r_' prefix
        'avg',                          # average combine for seamless blend per doc
        '-norm=addscale',
        '-maximize',                    # expand canvas
        f'-scale={scale:.6f}',          # allow downscaling if needed to fit display/memory
    ]
    if feather > 0:
        stack_cmd.append(f'-feather={feather}')
    if overlap_norm:
        stack_cmd.append('-overlap_norm')

    # Output file
    # Use explicit save path via -out; Siril will name r_mosaicpanel_stacked.fit in that folder
    outdir = final_out.parent.as_posix()
    ensure_dir(Path(outdir))
    stack_cmd.append(f'-out="{outdir}"')

    srun(app, " ".join(stack_cmd))

    # Rename final product
    produced = Path(outdir) / "r_mosaicpanel_stacked.fit"
    if produced.exists():
        try:
            produced.replace(final_out)
        except Exception:
            pass

# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="Calibrate, register, stack, and mosaic panels with Siril via pySiril.")
    parser.add_argument("--root", required=True, help="Dataset root folder containing panel subfolders.")
    parser.add_argument("--panel-stack-method", default="median", choices=["median", "avg", "sum", "rej"],
                        help="Stacking method for per-panel stacks (default: median).")
    parser.add_argument("--cfa", action="store_true", default=True, help="Treat lights as CFA/OSC (default: True).")
    parser.add_argument("--no-cfa", dest="cfa", action="store_false", help="Disable CFA handling.")
    parser.add_argument("--debayer", action="store_true", default=True, help="Debayer calibrated lights (default: True).")
    parser.add_argument("--no-debayer", dest="debayer", action="store_false", help="Do not debayer.")
    parser.add_argument("--feather", type=int, default=60, help="Feather distance (px) for mosaic seams (default: 60).")
    parser.add_argument("--overlap-norm", action="store_true", default=True,
                        help="Normalize on overlaps (recommended for mosaics; default: True).")
    parser.add_argument("--no-overlap-norm", dest="overlap_norm", action="store_false", help="Disable overlap normalization.")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Mosaic scale factor (<=1.0 to reduce final size if needed; default: 1.0).")
    parser.add_argument("--out", required=True, help="Output FITS path for final mosaic, e.g., /path/mosaic_final.fit")

    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    final_out = Path(args.out).expanduser().resolve()
    stacked_dir = root / "_stacked_panels"
    process_dir_root = root / "_process"

    panels = find_panels(root)
    if not panels:
        log("No panels found. Each panel must have a 'lights' subfolder.")
        sys.exit(1)

    log(f"Found {len(panels)} panel(s): " + ", ".join(p.name for p in panels))

    # Start pySiril
    app = Siril()
    cmd = None
    try:
        cmd = Wrapper(app)
        app.Open()
        # Global settings
        srun(app, 'set16bits')
        srun(app, 'setext fit')

        ensure_dir(stacked_dir)

        # Optional global calibration frames
        global_bias = detect_subdir(root, ["biases", "bias"])
        global_flats = detect_subdir(root, ["flats", "flat"])
        global_darks = detect_subdir(root, ["darks", "dark"])

        for idx, panel in enumerate(panels, start=1):
            log(f"Processing panel {panel.name} ({idx}/{len(panels)})")
            process_dir = process_dir_root / panel.name
            ensure_dir(process_dir)

            # Detect per-panel calib, fall back to global
            bias_dir = detect_subdir(panel, ["biases", "bias"]) or global_bias
            flat_dir = detect_subdir(panel, ["flats", "flat"]) or global_flats
            dark_dir = detect_subdir(panel, ["darks", "dark"]) or global_darks

            # Masters
            if bias_dir:
                make_master_bias(cmd, app, bias_dir, process_dir)
            if flat_dir:
                make_master_flat(cmd, app, flat_dir, process_dir, have_bias=bias_dir is not None)
            if dark_dir:
                make_master_dark(cmd, app, dark_dir, process_dir)

            # Panel preprocess/register/stack
            panel_out_dir = stacked_dir
            panel_name = f"panel_{idx:02d}"
            preprocess_register_stack_panel(
                cmd, app, panel, process_dir, panel_out_dir,
                cfa=args.cfa, debayer=args.debayer,
                panel_name=panel_name,
                panel_stack_method=args.panel_stack_method
            )

        # Build mosaic
        build_mosaic(
            app=app,
            stacked_dir=stacked_dir,
            final_out=final_out,
            feather=args.feather,
            overlap_norm=args.overlap_norm,
            scale=args.scale,
        )

        log(f"Done. Mosaic saved to: {final_out}")

    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(2)
    finally:
        try:
            app.Close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
