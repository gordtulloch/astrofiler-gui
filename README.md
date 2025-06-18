# astrofiler
Software to name and file astronomical images

Python (any recent version) and Git must be installed. Install as follows:

## In Linux or Mac
git clone https://github.com/gordtulloch/astrofiler.git
cd astrofiler
python -m venv .venv
nano astrofiler.ini          # Edit to set your SOURCE and REPO folders properly
source .venv/bin/activate    # Activate Python virtual environment
pip3 install -r requirements.txt
python3 astrofiler.py

##  In Windows
git clone https://github.com/gordtulloch/astrofiler.git
cd astrofiler
python -m venv .venv
notepad astrofiler.ini       # Edit to set your SOURCE and REPO folders properly
./venv/scripts/activate.bat  # Activate Python virtual environment
pip3 install -r requirements.txt
python3 astrofiler.py



