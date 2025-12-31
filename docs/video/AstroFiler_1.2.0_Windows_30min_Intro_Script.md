# AstroFiler 1.2.0 (Windows) — 30‑Minute Intro Video Script

## 0:00–0:45 — Cold open (hook)

**VO:**
If your astrophotography workflow is getting buried under FITS files—lights, darks, flats, bias—and you’re spending more time organizing than processing, this software is for you.

In this video I’m introducing **AstroFiler 1.2.0** on **Windows**. We’ll install it using the **SETUP** package, walk through first launch and configuration, then do a complete beginner workflow: ingest FITS files, organize sessions, create master calibration frames, calibrate light frames, measure real quality metrics, and do sample stacks of images.

**Switch to Desktop**
Hello from Sunny but frigid Winnipeg Manitoba Canada. My name is Gord Tulloch and I am the author of Astrofiler. Lets get started!

**On-screen text:**
AstroFiler 1.2.0 (Windows)
Install → Configure → Sessions → Auto‑Calibration → Quality

**Show:**
AstroFiler splash screen + main window (quick glimpse).

---

## 0:45–2:00 — What AstroFiler is (and what it isn’t)

**VO:**
AstroFiler is a FITS-first image management system for astrophotography. It reads FITS headers, renames and files images consistently, tracks sessions, and keeps a searchable database of your frames.

It also automates master creation and calibration, has command line versions of time intensive functions, and can integrate with sources like smart telescopes using Seestar, DWARF III, and Stellarmate, as well as remote observatories like iTelescopes.

What AstroFiler is *not* is a replacement for your full processing stack. The goal is to keep your data organized, track what’s been done to each frame, and make your next step obvious.

**On-screen text:**
FITS organization • Sessions • Calibration workflow • Quality metrics

**Show:**
Images view → Sessions view (quick pan).

---

## 2:00–3:30 — What’s new in 1.2.0 (high-level)

**VO:**
Version 1.2.0 is a major release.

The big headline is **Auto‑Calibration**: one-click master creation and light calibration using internal functions. Once you have masters and calibrated lights, the software will do a trial stack to allow you to see what you have and create a thumbnail. 

Also new in 1.2.0 are **session-level average quality metrics**, automatic FITS standard file compression, a photometry-safe stacking option, cloud syncronization, duplicate prevention, Stellarmate and iTelescope support, much improved performance, and a smoother startup experience.  Most of the time intensive functions of Astrofiler are available as Command Line utilities to facilite automation.

Lets get started by installing the software on Windows. I will release videos on installation on Linux and Mac shortly.

**On-screen text:**
New in 1.2.0
Auto‑Calibration • SEP Quality • Session Averages • Photometric Stack

**Show:**
Quick montage: Sessions → Auto-Calibration → Session tooltip → Stack (photometric) → Cloud Sync.

---

# Part A — Install on Windows using SETUP

## 3:30–4:00 — Where to get it

**VO:**
Let’s install AstroFiler on Windows using the **SETUP** package. This is the easiest path for new users because it automates the Python environment and dependencies. 

**On-screen text:**
Windows Install (SETUP)

**Show:**
Download page / release page.

---

## 4:00–5:00 — Download and extract

**VO:**
I’m downloading the Windows SETUP package from the RELEASES menu on Github. Here's the Github URL you will need to access to load this software. Click on releases, and download SETUP.ZIP. Extract and run SETUP.exe

SETUP.EXE is another piece of software I wrote named PyWinInstall which makes it easy for Windows users to set up Python software. It will install Python if required, download the code for Astrofiler, and build the runtime environment on the fly. 

When all is complete Astrofiler is about 1.75GB on disk, not counting your.

**On-screen text:**
Download → Extract All

**Show:**
File Explorer → Extract All.

---

## 5:00–6:30 — Run SETUP and explain what it does

**VO:**
Now I’m running **SETUP.EXE**.

Behind the scenes, the installer prepares a dedicated Python environment for AstroFiler:
- It checks whether Python is available.
- If Python isn’t installed or isn’t in PATH, the installer path can download and install Python.
- It creates a virtual environment—think of it as a clean sandbox for AstroFiler.
- It installs required packages.

AstroFiler 1.2.0 also installs **pysiril**, which is required for advanced calibration workflows. In the SETUP flow, there’s a special step to ensure `pysiril` gets installed correctly—even attempting to install from a wheel file, and if needed downloading build artifacts or falling back to installing from source.

When this finishes, you should have a launcher or shortcut you can use to start AstroFiler.

**On-screen text:**
Installer actions
Python check → .venv → dependencies → pysiril

**Show:**
Installer progress screens + completion.

**Optional VO (SmartScreen):**
Depending on how the installer is signed and distributed, Windows SmartScreen may show a warning. If it does, you may need to click “More info” then “Run anyway.”

---

# Part B — First launch and configuration

## 6:30–7:30 — First launch + splash screen

**VO:**
I’m launching AstroFiler.

In 1.2.0 there’s a splash screen with progress messages. It’s useful because it shows what’s happening: configuration loading, database initialization, and applying any database migrations.

**On-screen text:**
First Launch

**Show:**
Launch → splash screen → main window.

---

## 7:30–10:00 — Configure the repository (tabbed config)

**VO:**
Now I’m opening the configuration dialog. In 1.2.0 it’s organized into tabs: General, Cloud Sync, Calibration, and Smart Telescopes.

For new users, the most important setting is the **Repository path**. This is where AstroFiler will store and organize your FITS files.

I’m setting this to: **[REPO_PATH]**.

**On-screen text:**
Config → General → Repository path

**Show:**
Open config → set repository path.

**VO (Siril note):**
If you plan to use Auto‑Calibration, make sure **Siril** is installed and reachable. AstroFiler calls Siril to build masters and calibrate frames.

**On-screen text:**
Auto‑Calibration requires Siril installed

---

# Part C — Ingest data and understand sessions

## 10:00–13:00 — Ingest: what scanning does

**VO:**
Next, we need to bring FITS files into AstroFiler.

When AstroFiler scans or loads files, it reads FITS header metadata, calculates hashes for identification, and registers everything in the database.

That database powers search, duplicate handling, session grouping, and quality metrics.

**On-screen text:**
Ingest = read headers + hash + register in DB

**Show:**
Run the “Load Repository” / scan workflow, and show files appearing.

---

## 13:00–15:00 — FITS header mapping (for messy headers)

**VO:**
If your FITS headers aren’t consistent—for example if OBJECT values vary—AstroFiler has a FITS header mapping system.

Mappings are database-driven and can standardize values for common FITS cards like TELESCOP, INSTRUME, OBSERVER, OBJECT, FILTER, and NOTES.

This helps ensure files get named and filed correctly in the repository.

**On-screen text:**
Header mapping: standardize values during ingestion

**Show:**
Open mapping UI; show OBJECT mapping support.

---

## 15:00–17:30 — Sessions: what they are and why you care

**VO:**
Now let’s talk sessions.

A session groups images that belong together—typically one target, one night, one gear configuration.

In 1.2.0, session creation and grouping for calibration frames is improved so you don’t end up with one session per calibration frame. That keeps your workflow aligned with how you actually shoot data.

**On-screen text:**
Sessions = your work units (targets + nights + gear)

**Show:**
Sessions view; point out calibration sessions vs light sessions.

---

# Part D — Auto‑Calibration (the main 1.2.0 feature)

## 17:30–18:15 — Auto‑Calibration overview

**VO:**
This is the centerpiece of 1.2.0: Auto‑Calibration.

The goal is to create masters reliably, calibrate lights quickly, and keep full tracking in the database so nothing gets lost or ambiguous.

**On-screen text:**
Auto‑Calibration
Masters → Calibrate lights → Track history

**Show:**
Auto‑Calibration entry point in Sessions.

---

## 18:15–21:30 — Create masters (bias/dark/flat)

**VO (click-by-click):**
I’m selecting a calibration session and starting master creation.

AstroFiler groups calibration frames intelligently—by telescope, instrument, binning, and temperature—so masters are created only from compatible data.

Siril runs the actual master creation, and AstroFiler writes masters with comprehensive FITS header metadata and processing history.

A key fix in 1.2.0: master filenames use the **observation date** from the session instead of the processing date. That makes your master library easier to understand later.

**On-screen text:**
Masters: grouped by config • Siril-powered • Obs-date naming

**Show:**
Trigger master creation; show progress; then show resulting masters in UI and/or the Masters folder.

---

## 21:30–23:30 — Soft delete: keep your repo clean without losing data

**VO:**
After masters are created, AstroFiler can soft-delete the source calibration frames.

Soft delete means the files are still on disk—but hidden from normal views. It keeps the working set clean without destroying anything.

If I want to see them, I can toggle “Show Deleted.”

**On-screen text:**
Soft delete = hidden, not destroyed

**Show:**
Images view → toggle “Show Deleted” → demonstrate visibility change.

---

## 23:30–26:30 — Calibrate a light session (auto master matching)

**VO (what I’m clicking and why):**
Now I’m right-clicking a light session and choosing the calibration action.

AstroFiler automatically detects the appropriate masters based on session matching.

As calibration runs, AstroFiler tracks outputs and registers the calibrated frames into the database so they appear immediately in the UI.

This is important because it prevents a common workflow gap: processing happened, but your catalog doesn’t know about the new files.

**On-screen text:**
One-click calibration
Auto master detection • Outputs registered

**Show:**
Right-click session → calibrate → show calibrated frames appearing.

---

# Part E — Quality metrics (SEP) + session averages

## 26:30–28:30 — What’s new: quantitative quality analysis

**VO:**
Quality assessment in 1.2.0 is quantitative. AstroFiler uses **SEP**, a professional star detection and measurement library, to compute:
- FWHM in arcseconds
- Eccentricity
- HFR in arcseconds
- Image SNR
- Star count
- Image scale

These metrics are stored in the database so you can compare sessions and frames using real measurements.

**On-screen text:**
Quality metrics
FWHM(″) • Eccentricity • HFR(″) • SNR • Star count • Scale

**Show:**
Run quality assessment or show quality fields on files.

---

## 28:30–30:30 — Reliability: SEP with fallback + stability improvements

**VO:**
SEP is the primary detection method, and there’s a fallback method using photutils for maximum reliability.

1.2.0 also improves stability by focusing star measurements on a limited set of the brightest detections for more consistent metrics, and it suppresses noisy FITS warnings during analysis.

**On-screen text:**
SEP-based detection + fallback

**Show:**
Quality analysis running; show stable results.

---

## 30:30–33:00 — Session-level average quality tooltip (big usability win)

**VO:**
One of the best features for day-to-day use is session-level quality averages.

AstroFiler calculates and stores average quality metrics on the session.

So instead of opening many subs, I can hover a session and immediately see average FWHM, average eccentricity, average HFR, and more.

This makes it easy to compare nights, filters, or gear setups.

**On-screen text:**
Hover session → average metrics

**Show:**
Hover tooltip in Sessions view.

---

# Part F — Stacking (including photometry-safe)

## 33:00–35:30 — Deep stack vs photometry-safe stack

**VO:**
Stacking is where workflows diverge.

For deep images, you often use rejection like sigma clipping.

But for photometry, you often want a stack that avoids clipping and preserves linear measurement behavior.

AstroFiler 1.2.0 adds “Stack (photometric)”: a registered-mean stack with no sigma clipping and float output.

**On-screen text:**
New: Stack (photometric)
Mean • no sigma clipping • float output

**Show:**
Sessions context menu → Stack (photometric) → resulting `photometric_stack_*.fits`.

---

# Part G — Cloud Sync (hash-based duplicate prevention)

## 35:30–38:00 — Smarter duplicate handling

**VO:**
Cloud Sync in 1.2.0 is smarter about duplicates.

Instead of relying on filenames alone, it can use MD5 hash comparisons to skip identical uploads, upload new content, or overwrite changed content.

It can also analyze cloud storage for duplicates and estimate wasted space.

**On-screen text:**
Cloud Sync
MD5 duplicate prevention • Cloud duplicate analysis

**Show:**
Tools → Cloud Sync → Analyze → (optional) Sync.

---

# Part H — Smart telescopes (highlight: iTelescope)

## 38:00–40:00 — iTelescope support (FTPS + .fit.zip)

**VO:**
AstroFiler 1.2.0 adds iTelescope network support via secure FTPS, including handling of their `.fit.zip` format.

You configure credentials in the Smart Telescopes tab, then use the download tool to scan and fetch calibrated files.

**On-screen text:**
iTelescope support (FTPS)

**Show:**
Config → Smart Telescopes → iTelescope credentials → download workflow.

---

# Part I — Wrap-up (and how to hit 30 minutes cleanly)

## 40:00–30:00 — Recording guidance

This script intentionally includes “pause time” segments where you can let viewers watch progress bars (install, masters, calibration, stacking). To hit ~30:00 in a real recording:
- Hold on each major screen for 5–10 seconds while you summarize.
- Pause for progress dialogs and narrate what the status messages mean.

Optional 2–3 minute add-ons if needed:
- Demonstrate Images view behavior (no pagination) while using search/sort/filters.
- Explain database lock behavior and what users should do (close other instances; retry behavior).
- Do a slow tour of the tabbed configuration dialog and what new users can ignore at first.

---

## Final 45 seconds — Closing

**VO:**
That’s AstroFiler 1.2.0 on Windows: install with SETUP, configure a repository, ingest FITS files, organize sessions, create masters, calibrate lights, and measure real quality metrics you can compare across sessions.

If you want follow-up videos, tell me whether you want a deeper Auto‑Calibration tutorial, a full cloud backup workflow, or a guide on FITS header mapping best practices.

**On-screen text:**
AstroFiler 1.2.0 — Thanks for watching
