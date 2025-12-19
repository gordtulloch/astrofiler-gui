#!/usr/bin/env python3
"""
Trace the exact master matching for session 598949b6-aa11-498f-bc8c-ca49c792f6d8
"""
import sys
sys.path.insert(0, 'src')

from astrofiler.models import fitsFile, fitsSession, Masters
from astrofiler.core.master_manager import get_master_manager

session_id = '598949b6-aa11-498f-bc8c-ca49c792f6d8'

print("="*80)
print(f"Tracing Master Matching for Session: {session_id}")
print("="*80)

# Get the session
session = fitsSession.get_or_none(fitsSession.fitsSessionId == session_id)

if not session:
    print(f"❌ Session not found!")
    sys.exit(1)

print(f"\nSession Details:")
print(f"  Object: {session.fitsSessionObjectName}")
print(f"  Telescope: {session.fitsSessionTelescope}")
print(f"  Camera: {session.fitsSessionImager}")
print(f"  Exposure: {session.fitsSessionExposure}s")
print(f"  Binning: {session.fitsSessionBinningX}x{session.fitsSessionBinningY}")
print(f"  Temp: {session.fitsSessionCCDTemp}°C" if session.fitsSessionCCDTemp else "  Temp: N/A")
print(f"  Gain: {session.fitsSessionGain}" if session.fitsSessionGain else "  Gain: N/A")
print(f"  Offset: {session.fitsSessionOffset}" if session.fitsSessionOffset else "  Offset: N/A")

# Build session_data exactly as the UI does
session_data = {
    'telescope': session.fitsSessionTelescope,
    'instrument': session.fitsSessionImager,
    'exposure_time': session.fitsSessionExposure,
    'filter_name': session.fitsSessionFilter,
    'binning_x': session.fitsSessionBinningX,
    'binning_y': session.fitsSessionBinningY,
    'ccd_temp': session.fitsSessionCCDTemp,
    'gain': session.fitsSessionGain,
    'offset': session.fitsSessionOffset
}

print("\n" + "="*80)
print("Session Data for Master Matching:")
print("="*80)
for key, value in session_data.items():
    print(f"  {key}: {value}")

# Use master_manager to find matching dark
print("\n" + "="*80)
print("Using MasterManager.find_matching_master():")
print("="*80)

master_manager = get_master_manager()
master_dark = master_manager.find_matching_master(session_data, 'dark')

if master_dark:
    print(f"\n✅ Found dark master:")
    print(f"  Path: {master_dark.master_path}")
    print(f"  Telescope: {master_dark.telescope}")
    print(f"  Instrument: {master_dark.instrument}")
    print(f"  Exposure: {master_dark.exposure_time}s")
    print(f"  Binning: {master_dark.binning_x}x{master_dark.binning_y}")
    print(f"  Temp: {master_dark.ccd_temp}°C" if master_dark.ccd_temp else "  Temp: N/A")
    print(f"  Created: {master_dark.creation_date}")
    
    if master_dark.exposure_time != session.fitsSessionExposure:
        print(f"\n❌ EXPOSURE MISMATCH!")
        print(f"  Light frame needs: {session.fitsSessionExposure}s")
        print(f"  Dark master is: {master_dark.exposure_time}s")
else:
    print("\n❌ No dark master found!")

# Now manually check what criteria are being used
print("\n" + "="*80)
print("Manual Query Breakdown:")
print("="*80)

# Simulate the criteria building from master_manager
criteria = {
    'exposure_time': session_data.get('exposure_time') if 'dark' else None,
    'binning_x': session_data.get('binning_x'),
    'binning_y': session_data.get('binning_y'),
    'ccd_temp': session_data.get('ccd_temp'),
    'gain': session_data.get('gain'),
    'offset': session_data.get('offset')
}

# Remove None values as master_manager does
criteria = {k: v for k, v in criteria.items() if v is not None}

print(f"\nCriteria after filtering None values:")
for key, value in criteria.items():
    print(f"  {key}: {value}")

# Now query directly
print("\n" + "="*80)
print("Direct Masters Query:")
print("="*80)

query = Masters.select().where(
    Masters.telescope == session.fitsSessionTelescope,
    Masters.instrument == session.fitsSessionImager,
    Masters.master_type == 'dark',
    Masters.soft_delete == False
)

print(f"\nBase query (telescope + instrument + type + not deleted):")
print(f"  Found: {query.count()} masters")

# Add exposure_time criteria
if 'exposure_time' in criteria:
    query_with_exp = query.where(Masters.exposure_time == criteria['exposure_time'])
    print(f"\nWith exposure_time == {criteria['exposure_time']}:")
    print(f"  Found: {query_with_exp.count()} masters")
    
    if query_with_exp.count() > 0:
        print(f"\n  Available masters:")
        for m in query_with_exp:
            print(f"    - {m.master_path}")
            print(f"      Binning: {m.binning_x}x{m.binning_y}, Temp: {m.ccd_temp}°C")

# Add binning criteria
if 'binning_x' in criteria and 'binning_y' in criteria:
    query_with_bin = query.where(
        Masters.binning_x == criteria['binning_x'],
        Masters.binning_y == criteria['binning_y']
    )
    print(f"\nWith binning {criteria['binning_x']}x{criteria['binning_y']}:")
    print(f"  Found: {query_with_bin.count()} masters")

# All criteria combined
full_query = query.where(
    Masters.binning_x == criteria.get('binning_x'),
    Masters.binning_y == criteria.get('binning_y')
)
if 'exposure_time' in criteria:
    full_query = full_query.where(Masters.exposure_time == criteria['exposure_time'])
if 'ccd_temp' in criteria:
    full_query = full_query.where(Masters.ccd_temp == criteria['ccd_temp'])

print(f"\nWith all criteria combined:")
print(f"  Found: {full_query.count()} masters")

if full_query.count() > 0:
    first = full_query.first()
    print(f"\n  First match:")
    print(f"    Path: {first.master_path}")
    print(f"    Exposure: {first.exposure_time}s")
    print(f"    Temp: {first.ccd_temp}°C" if first.ccd_temp else "    Temp: N/A")
else:
    print(f"\n  No matches with all criteria")
    print(f"\n  Checking if temperature is the issue...")
    
    # Try without temperature
    query_no_temp = query.where(
        Masters.binning_x == criteria.get('binning_x'),
        Masters.binning_y == criteria.get('binning_y')
    )
    if 'exposure_time' in criteria:
        query_no_temp = query_no_temp.where(Masters.exposure_time == criteria['exposure_time'])
    
    print(f"  Without temperature requirement: {query_no_temp.count()} masters")
    
    if query_no_temp.count() > 0:
        print(f"\n  ✅ Temperature matching is too strict!")
        print(f"  Available masters without temp requirement:")
        for m in query_no_temp:
            print(f"    - Temp: {m.ccd_temp}°C, Path: {m.master_path}")

print("\n" + "="*80)
