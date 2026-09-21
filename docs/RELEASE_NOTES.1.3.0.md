# AstroFiler 1.3.0 – Release Notes

Changes since **1.2.3**. Release date: _to be set when the release is tagged._

## Highlights

- **Variable-star photometry.** Mark targets as variable stars, then run an automated pipeline (calibrate → photometric stack → ensemble photometry against AAVSO comparison stars).
- **Aperture photometry command** for FITS/XISF images, writing a CSV per image.
- **Flat-dark calibration frames** are supported, so flats can be dark-corrected with a matching master flat-dark.
- **Celestron Origin** discovery and download fixes, and **Dwarf Mini** imports now work.
- **Python 3.12 or newer is now required.**
- **AstroFiler is now a properly installable package**: working `astrofiler` / `astrofiler-gui` commands, and bundled themes, images and database migrations.
- **FITS compression fixes**: `auto` now really chooses the algorithm from the image data type, and floating-point frames are compressed losslessly (they were previously skipped).
- **Security fixes** for file names that could run shell commands.

## New features

### Variable-star photometry
- **Add Variable Star** in the Images view context menu marks a target as a variable-star photometry target. Targets are stored in a new `VariableStars` table (migration `012`, applied automatically).
- New command `commands/VariableStarPhotometry.py`. For a session (`--session`) or an existing stacked image (`--stacked-fits`) it:
  1. calibrates the session's light frames if they aren't already calibrated,
  2. builds a registered, photometric mean stack,
  3. measures the target with ensemble photometry against comparison stars fetched from the **AAVSO Variable Star Plotter (VSP)** (needs internet access). Band (`--band`), comparison-star magnitude range (`--bright` / `--dim`), detection SNR, match radius and aperture size are command-line options, an optional check star can be given with `--check-auid`, and results can be written as JSON (`--out-json`) and per-star CSV (`--out-csv`).

### Flat-dark frames
- `FlatDark` is now a recognised image/session type. Flat-dark masters are matched separately from ordinary dark masters, shown on calibration-session rows in the Sessions view, and included in checkout.
- Light-frame calibration accepts an optional master flat-dark, which is bias-corrected (when a bias is available) and subtracted from the flat before it is used.

### Aperture photometry
- New command `commands/Photometry.py`: instrumental aperture photometry on a FITS or XISF file, folder or glob, writing one CSV per input image. Source detection uses SEP. This is an initial version.

## Changes

### FITS compression
- **`auto` now selects the algorithm from the data type**, and the choice is actually applied. Previously every internal-compression path was hard-coded to GZIP_2.
  - 8/16-bit integer data → **RICE_1** (smaller: about 72 KB vs 89 KB for a test 16-bit frame).
  - 32-bit integers and floating-point data → **GZIP_2**.
  - Other types → GZIP_1.
  - `fits_rice`, `fits_gzip1` and `fits_gzip2` are honoured when chosen explicitly. RICE on non-integer data falls back to GZIP_2 with a warning, because RICE would be lossy there.
- **Floating-point frames are now compressed, and losslessly.** astropy quantizes float data by default, which made the built-in verification reject every float32/float64 frame, so they silently stayed uncompressed. Quantization is now disabled; float frames round-trip bit-for-bit.
- Verification now runs on the temporary file **before** the original is replaced, so a failed check leaves the source file untouched.
- Auto-import still compresses in place and keeps the `.fits` file name. Only an explicit `replace_original=False` call writes a separate `name.fits.fz` file.

### Repository defaults
- If `repo` / `source` aren't set in `astrofiler.ini`, AstroFiler now uses `REPOSITORY` and `REPOSITORY.incoming` in the working directory. Before, it used the working directory itself and created `Light/`, `Calibrate/`, `Masters/`… loose in it.
- On first run the Settings screen now writes `source = REPOSITORY.incoming/` and `repo = REPOSITORY/` to `astrofiler.ini` if they are missing, so the defaults become visible and editable.

### Where configuration, database and log live
- New `astrofiler.paths` module; nothing depends on the launch directory any more.
  1. `$ASTROFILER_HOME`, if set.
  2. Otherwise the **project folder** when running from a source checkout or editable install. This is where the install scripts already keep these files, so **existing installs are unaffected**.
  3. Otherwise a per-user folder: `%APPDATA%\AstroFiler` (Windows), `~/Library/Application Support/AstroFiler` (macOS), `$XDG_CONFIG_HOME/astrofiler` or `~/.config/astrofiler` (Linux).
- `ASTROFILER_DB_PATH` still overrides the database location.
- The GUI and every `commands/` script now share the same `astrofiler.log`, and the commands' `--config` / `--log-file` defaults point at the application folder.

### Version handling
- One version number, defined in `astrofiler.__version__`, is used by the window title, About box, update checker, package metadata, macOS `Info.plist`, splash screen and FITS headers. Calibrated files previously recorded `1.2.0` in `CALVER` / `CALSOFT`.
- The registration ping now identifies itself as `AF1.3.0`.

### Credentials
- The **iTelescope password is now stored in your system's credential store** (Windows Credential Manager, macOS Keychain, or Secret Service/KWallet on Linux) instead of in `astrofiler.ini`. An existing plain-text password is moved there automatically the first time it is needed, and its line is removed from the file.
- If no credential store is available (for example a headless Linux machine), AstroFiler keeps using the ini file as before, logs a warning, and restricts the file to your user account.

### Star detection and dependencies
- Star detection and image-quality analysis use **SEP** only. The optional photutils detector was removed, and `photutils` is no longer a requirement.

### Smart telescopes and import fixes
- **Celestron Origin:** more reliable telescope discovery. The hostname is read from configuration, plain IP addresses are accepted as well as `.local` names, and hostname matching is stricter. Covered by new tests (`tests/test_telescope.py`).
- **Dwarf Mini** (and other DWARF variants such as DWARF II/3) are now detected on import even when the `TELESCOP` header value differs from `DWARF`.
- **XISF import:** fixed the converter not being initialised correctly in the file-format handler, while keeping the existing failed-conversion error handling.

## Removed

- The `astrofiler-cli` entry point (it pointed at a module that never existed). Use the scripts in `commands/`.
- The optional photutils star detector (SEP is used instead; see above).

## Packaging and installation

- **Python 3.12+ required** (was 3.8+). The install and launch scripts check for it, and the Windows installer now downloads Python 3.12.10.
- The `astrofiler` and `astrofiler-gui` commands now work: the launcher moved into the package (`astrofiler.main`), and `python astrofiler.py` remains as a thin wrapper.
- Dark/light themes, the About-screen background, the splash logo and the **16 database migrations** are now part of the package, so a wheel-installed copy can create its database and shows its themes.
- `astroalign`, used to align light frames when stacking, is now declared in the package's dependencies (it was only in `requirements.txt`; without it stacking silently skips alignment).
- Three GUI modules no longer import `setup_path`, a development helper that isn't part of the package.

## Fixes

- **Security: shell-command injection through file names.** Opening a file in the default viewer (Images and Sessions views) used `os.system` with the file name in the command, and session checkout on Windows used `mklink` through the shell. A crafted file name could run commands. Both now avoid the shell entirely (`QDesktopServices` and `os.symlink`).
- macOS in-app updater: fixed a Python-3.12-only syntax that stopped the module from importing on older Pythons, and paths with spaces or quotes are now quoted correctly.
- The Duplicates view no longer creates an empty `astrofiler.db` in the working directory when launched from elsewhere.
- On Windows, a missing symlink privilege now logs how to fix it (enable Developer Mode, or use the copy option).

## Developer notes

- Automated tests (`tests/`, 32 tests): compression behaviour, file locations, packaging data and repository defaults, flat-dark calibration and Celestron Origin/telescope handling. Run with `pytest tests` (`pytest-cov` is needed for the repo's default options, or pass `-o addopts=""`).
- macOS install scripts (`install_macos.sh`, `launch_astrofiler_macos.sh`) are now executable in git.
- `REPOSITORY/` and `REPOSITORY.incoming/` now contain tracked placeholder files and are no longer git-ignored. Anything you import into them will appear as untracked in `git status`.
- `pyproject.toml`: version is read from `astrofiler.__version__`; black/mypy target Python 3.12; pytest `pythonpath = ["src"]`.

## Upgrade notes

1. **Install Python 3.12 or newer** and recreate the virtual environment (the install scripts do this check for you). Run `pip install -r requirements.txt` to refresh dependencies; this adds `keyring` for the credential store.
2. **Database:** migration `012` is applied automatically on start, or run `python migrate.py run`.
3. **Existing settings, database and logs stay where they are** for source-checkout installs. Only a `pip`-installed copy uses the per-user folder.
4. **Float FITS frames imported before 1.3.0 are still uncompressed.** They are not re-compressed automatically.
5. If `repo` / `source` are unset in your `astrofiler.ini`, files will now go into `REPOSITORY/` and `REPOSITORY.incoming/` under the folder you launch from.

## Known limitations

- The new per-user folders for macOS and Linux are covered by unit tests but have not been run on those systems; the wheel-install check was done on Windows only.
- An installed copy starts with an empty configuration; existing settings are not imported.
- The credential store has been exercised on Windows only; the macOS Keychain and Linux Secret Service backends rely on the `keyring` package and have not been tested here.
