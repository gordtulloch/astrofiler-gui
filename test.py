from astrofiler_file import fitsProcessing
import os

# Test the configuration and file finding
fp = fitsProcessing()
print(f'Source folder: {fp.sourceFolder}')
print(f'Repo folder: {fp.repoFolder}')
print(f'Source folder exists: {os.path.exists(fp.sourceFolder)}')
print(f'Repo folder exists: {os.path.exists(fp.repoFolder)}')

if os.path.exists(fp.sourceFolder):
    print(f'Contents of source folder:')
    for root, dirs, files in os.walk(fp.sourceFolder):
        for file in files:
            print(f'  {file}')
        if len(files) == 0:
            print('  (no files found)')
        break  # Just show first level