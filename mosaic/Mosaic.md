
# Siril Mosaic Builder with pySiril

Create large, seamless astronomical **mosaics** from multiple panels using **Siril 1.4+** driven by **pySiril**. The companion script, `siril_mosaic.py`, automates calibration, registration, panel stacking, and final mosaic stitching with feathering and overlap normalization.

---

## Overview

**What this script does**
- **Per-panel processing**: builds **master Bias**, **master Flat** (bias-calibrated), and **master Dark**; calibrates and (optionally) **debayers** the lights; **registers** and **stacks** each panel into a single high-SNR tile.
- **Astrometric mosaic**: plate-solves the panel stacks, **applies existing registration** (astrometric), then performs a **mosaic stack** using Siril’s `-maximize` canvas with optional **`-feather`** and **`-overlap_norm`** for seamless joints.
- **Arbitrary dimensions**: any number of panel folders (e.g., 3×3, 2×5, etc.).

**Why this flow?** Stacking per panel first is more memory‑efficient and aligns with Siril’s recommended mosaic workflow for 1.4+. Final stitching uses additive-with-scaling normalization and options tuned for mosaics.

---

## Prerequisites

- **Siril 1.4+** (for astrometric registration & mosaic features)
- **Python 3.9+**
- **pySiril** (Python wrapper for Siril)
- Sufficient RAM and **SSD** storage for large mosaics
- Recommended: **Local astrometric catalogs** in Siril for robust, fast `seqplatesolve`

### Verify Siril
```bash
siril-cli --version
```

### Install pySiril
Use the official wheel if available (recommended by the pySiril tutorial):
```bash
python -m pip uninstall -y pysiril  # if previously installed
python -m pip install pysiril-<version>-py3-none-any.whl
```
Or from PyPI (if published for your environment):
```bash
python -m pip install pysiril
```

---

## Input Directory Layout

```
/path/to/dataset_root/
  panel_01/
    lights/   # required
    darks/    # optional (panel-specific)
    flats/    # optional (panel-specific)
    biases/   # optional (panel-specific)
  panel_02/
    lights/
    ...
  darks/      # optional (global fallback)
  flats/      # optional (global fallback)
  biases/     # optional (global fallback)
```
- If a panel has its own calibration frames, they are used; otherwise the script falls back to the **global** sets at the root (if present).

---

## Quick-Start Guide

**1) Place `siril_mosaic.py` somewhere on your system.**

**2) Organize your data** as shown above (one subfolder per panel with a `lights/` subfolder).

**3) Run with defaults** (OSC/DSLR typical workflow, debayer on, feather 60px):
```bash
python siril_mosaic.py \
  --root "/data/m31_mosaic_2025-08-12" \
  --out  "/data/m31_mosaic_2025-08-12/m31_mosaic.fit"
```

**Mono camera (no debayer) & stronger seam feathering**:
```bash
python siril_mosaic.py \
  --root "/data/SHO_mosaic" \
  --no-cfa --no-debayer \
  --feather 120 \
  --out "/data/SHO_mosaic/SHO_mosaic.fit"
```

**Huge mosaic (limit memory/display) — downscale during mosaic step**:
```bash
python siril_mosaic.py \
  --root "/data/huge_mosaic" \
  --scale 0.75 \
  --out "/data/huge_mosaic/huge_mosaic.fit"
```

---

## Command-Line Options

- `--root <PATH>`: Dataset root containing panel subfolders (**required**)
- `--out <FILE>`: Output FITS path for final mosaic (**required**)
- `--panel-stack-method {median,avg,sum,rej}`: Method for **per-panel stack** (default: `median`)
- `--cfa / --no-cfa`: Treat lights as **CFA/OSC** data (default: `--cfa`)
- `--debayer / --no-debayer`: Debayer during calibration (default: `--debayer`)
- `--feather <px>`: Feather distance (pixels) for mosaic seams (default: `60`)
- `--overlap-norm / --no-overlap-norm`: Normalize on **overlaps** (default: enabled)
- `--scale <float>`: Mosaic downscale factor (≤1.0); useful for very large canvases (default: `1.0`)

**Notes**
- Use **`--overlap-norm`** for classic mosaics when tile backgrounds differ; typically **disable** it for heavy overlap/fieldRotation scenarios.
- Median for per‑panel stacks is robust to satellites; final mosaic uses **average** with **addscale** normalization for smooth joins.

---

## Visual Workflow

```mermaid
flowchart TD
  A[Start] --> B[Scan dataset root]
  B --> C{Panels found?}
  C -- No --> Z[Exit with error]
  C -- Yes --> D[For each panel]
  D --> E[Detect panel/local calibration frames]
  E --> F[Create Master Bias]
  E --> G[Create Master Flat (bias-calibrated)]
  E --> H[Create Master Dark]
  F --> I[Convert lights -> FITSEQ]
  G --> I
  H --> I
  I --> J[Preprocess (apply dark/flat, CFA eq, optional debayer)]
  J --> K[Register pp_light]
  K --> L[Stack r_pp_light -> panel_i_stacked.fit]
  L --> M{More panels?}
  M -- Yes --> D
  M -- No --> N[Collect panel_*_stacked.fit]
  N --> O[Renumber to mosaicpanel_00001.fit ...]
  O --> P[convert mosaicpanel -fitseq]
  P --> Q[seqplatesolve mosaicpanel (whole seq)]
  Q --> R[seqapplyreg mosaicpanel]
  R --> S[stack r_mosaicpanel -maximize -norm=addscale]
  S --> T{Options}
  T --> U[-feather=<px>]
  T --> V[-overlap_norm]
  U --> W[Write r_mosaicpanel_stacked.fit]
  V --> W
  W --> X[Rename to final output path]
```

**Key options**
- `-maximize`: expands the mosaic canvas to include all tiles.
- `-feather`: blends seams; higher values soften edges more.
- `-overlap_norm`: normalizes using **only overlapping regions** (great when panels contain different sky statistics).

---

## Detailed Workflow Notes

1. **Masters**  
   - `bias_stacked.fit` is built first; then **flats** are calibrated with it before stacking (`pp_flat_stacked.fit`).  
   - **Darks** are stacked into `dark_stacked.fit`.
2. **Calibrate lights**  
   - `preprocess` applies master dark/flat. With `--cfa`, it also enables **CFA equalization**; `--debayer` performs demosaic here (recommended for most OSC mosaics).
3. **Register + Stack per panel**  
   - Classic star-based registration (`register`), then per-panel **median** (default) or chosen method.
4. **Mosaic**  
   - Panel stacks are renumbered to a common prefix and converted into a new sequence.  
   - `seqplatesolve` plate-solves **the whole sequence**; `seqapplyreg` applies astrometric transforms.  
   - Final `stack` with `-maximize`, optional `-feather`, and `-overlap_norm` produces the mosaic.

---

## Troubleshooting & Tips

- **Images too large to display in Siril**: Siril’s UI has display limits (~32768 px per side). You can still process headless; or use `--scale 0.75` (or lower) to reduce output size.
- **Plate solve fails for some tiles**: Install local catalogs in Siril and enable near-solve; ensure FITS headers have approximate coordinates; check focus/trailed stars.
- **Seams visible**: Increase `--feather`; enable `--overlap-norm` when panels contain very different background conditions.
- **Memory pressure**: Work on SSD, close other apps, consider downscaling with `--scale`, or stack fewer/ smaller panels at a time.

---

## References
- **Automating with pySiril** (installation & code examples): https://siril.org/tutorials/pysiril/
- **Siril Mosaics tutorial** (astrometric alignment, feather, overlap normalization): https://siril.org/tutorials/mosaics/
- **Siril Commands reference** (stack, register, seqplatesolve, seqapplyreg, etc.): https://free-astro.org/index.php?title=Siril:Commands
- **When to use `-overlap_norm` discussion**: https://discuss.pixls.us/t/when-should-i-use-the-stacking-parameter-overlap-norm/51048

---

## License
This documentation is provided as-is. Use at your own risk; always back up your data before bulk processing.
