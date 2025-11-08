#!/bin/bash
# AstroFiler Installation Script for macOS
# This script checks for Python, installs it if needed (via Homebrew),
# creates a virtual environment, and installs all required dependencies.

set -e  # Exit on any error

echo "======================================"
echo "AstroFiler Installation Script for macOS"
echo "======================================"
echo

# Change to parent directory (where astrofiler.py is located)
cd "$(dirname "$0")/.."

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Homebrew
install_homebrew() {
    echo "Homebrew is not installed. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/usr/local/bin/brew shellenv)"
    fi
}

# Function to install Python via Homebrew
install_python() {
    echo "Installing Python via Homebrew..."
    if ! command_exists brew; then
        install_homebrew
    fi
    
    brew install python
    
    # Link python3 to python if not already done
    if ! command_exists python; then
        if command_exists python3; then
            echo "Creating python symlink..."
            ln -sf $(which python3) /usr/local/bin/python 2>/dev/null || true
        fi
    fi
}

# Check if Python is installed
python_cmd=""
if command_exists python3; then
    python_cmd="python3"
elif command_exists python; then
    # Check if it's Python 3
    python_version=$(python --version 2>&1)
    if [[ $python_version == *"Python 3"* ]]; then
        python_cmd="python"
    fi
fi

if [ -z "$python_cmd" ]; then
    echo "Python 3 is not installed."
    echo
    read -p "Do you want to install Python via Homebrew? [Y/n]: " choice
    case "$choice" in 
        n|N ) 
            echo "Please install Python 3.8+ manually and run this script again."
            echo "You can download it from: https://www.python.org/downloads/"
            echo "Or install via Homebrew: brew install python"
            exit 1
            ;;
        * ) 
            install_python
            python_cmd="python3"
            ;;
    esac
fi

# Check Python version
echo "Checking Python installation..."
$python_cmd --version

# Check if Python version is 3.8+
$python_cmd -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Error: Python 3.8 or higher is required."
    echo "Please upgrade your Python installation."
    exit 1
fi

echo "Python version is compatible."
echo

# Check if virtual environment already exists
if [ -d ".venv" ]; then
    echo "Virtual environment already exists."
    read -p "Do you want to recreate it? (This will remove all installed packages) [y/N]: " choice
    case "$choice" in 
        y|Y ) 
            echo "Removing existing virtual environment..."
            rm -rf .venv
            ;;
        * ) 
            echo "Using existing virtual environment."
            ;;
    esac
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $python_cmd -m venv .venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment."
        echo "Make sure you have the venv module installed."
        exit 1
    fi
    echo "Virtual environment created successfully."
fi

echo

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment."
    exit 1
fi

echo "Virtual environment activated."
echo

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip
echo

# Install requirements
echo "Installing required packages..."
if [ -f "requirements.txt" ]; then
    python -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install some packages."
        echo "Please check the error messages above."
        echo
        echo "Note: On Apple Silicon Macs, some packages may require additional setup."
        echo "If you encounter issues, try installing with:"
        echo "  arch -arm64 python -m pip install -r requirements.txt"
        exit 1
    fi
else
    echo "Warning: requirements.txt not found."
    echo "Installing packages manually..."
    python -m pip install astropy peewee numpy matplotlib pytz PySide6
fi

echo
echo "======================================"
echo "Installation completed successfully!"
echo "======================================"
echo
echo "To run AstroFiler:"
echo "1. Open Terminal in this directory"
echo "2. Run: source .venv/bin/activate"
echo "3. Run: python astrofiler.py"
echo
echo "You can also use the run_astrofiler.sh script for convenience."
echo

# Create convenience run script
echo "Creating run scripts..."
cat > run_astrofiler.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python astrofiler.py
EOF

chmod +x run_astrofiler.sh

# Ask user about automatic updates
echo
read -p "Do you want automatic updates? (Updates will be checked on each launch) [Y/n]: " enable_auto_update

# Create custom launch script based on auto-update preference
echo "Creating launch script..."
AUTO_UPDATE_ENABLED=true
case "$enable_auto_update" in
    [nN]|[nN][oO])
        AUTO_UPDATE_ENABLED=false
        ;;
    *)
        AUTO_UPDATE_ENABLED=true
        ;;
esac

# Make desktop launcher executable
chmod +x install/launch_astrofiler_macos.sh

if [ "$AUTO_UPDATE_ENABLED" = true ]; then
    echo "run_astrofiler.sh created and made executable (with auto-updates)."
else
    echo "run_astrofiler.sh created and made executable (without auto-updates)."
fi
echo "Desktop launcher created and made executable: install/launch_astrofiler_macos.sh"

# Create macOS app launcher
echo
read -p "Do you want to create a macOS app launcher? [Y/n]: " create_app
case "$create_app" in 
    n|N )
        echo "Skipping app creation."
        ;;
    * )
        echo "Creating macOS app launcher..."
        app_name="AstroFiler.app"
        if [ -d "$app_name" ]; then
            rm -rf "$app_name"
        fi
        
        mkdir -p "$app_name/Contents/MacOS"
        mkdir -p "$app_name/Contents/Resources"
        
        # Create Info.plist
        cat > "$app_name/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>AstroFiler</string>
    <key>CFBundleIdentifier</key>
    <string>com.astrofiler.app</string>
    <key>CFBundleName</key>
    <string>AstroFiler</string>
    <key>CFBundleDisplayName</key>
    <string>AstroFiler</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.education</string>
</dict>
</plist>
EOF

        # Create executable script
        cat > "$app_name/Contents/MacOS/AstroFiler" << EOF
#!/bin/bash
# Navigate to the original installation directory
APP_DIR="$(pwd)"
cd "\$APP_DIR"
EOF

        if [ "$AUTO_UPDATE_ENABLED" = true ]; then
            cat >> "$app_name/Contents/MacOS/AstroFiler" << 'EOF'

# Check for updates from GitHub if this is a git repository
if [ -d ".git" ]; then
    echo "Checking for updates from GitHub..."
    echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - INFO - Checking for updates from GitHub..." >> astrofiler.log
    if command -v git >/dev/null 2>&1; then
        git fetch origin main >/dev/null 2>&1
        UPDATE_COUNT=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo "0")
        if [ "$UPDATE_COUNT" -gt 0 ] 2>/dev/null; then
            echo "Updates available! Pulling latest changes..."
            echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - INFO - Updates available! $UPDATE_COUNT commits behind. Pulling latest changes..." >> astrofiler.log
            if git fetch origin && git reset --hard origin/main; then
                echo "Successfully updated to latest version."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - INFO - Successfully updated to latest version from GitHub" >> astrofiler.log
                # Run database migrations after successful update
                echo "Running database migrations..."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - INFO - Running database migrations after update" >> astrofiler.log
                if [ -f ".venv/bin/python" ]; then
                    if .venv/bin/python migrate.py run; then
                        echo "Database migrations completed successfully."
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - INFO - Database migrations completed successfully" >> astrofiler.log
                    else
                        echo "Warning: Database migration failed. AstroFiler may not function correctly."
                        echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - WARNING - Database migration failed after update" >> astrofiler.log
                    fi
                fi
            else
                echo "Warning: Failed to update from GitHub. Continuing with current version."
                echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - WARNING - Failed to update from GitHub. Continuing with current version" >> astrofiler.log
            fi
        else
            echo "Already up to date."
            echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - INFO - Repository already up to date" >> astrofiler.log
        fi
    else
        echo "Note: git not available, skipping update check."
        echo "$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - INFO - git not available, skipping update check" >> astrofiler.log
    fi
    echo
fi
EOF
        fi

        cat >> "$app_name/Contents/MacOS/AstroFiler" << EOF

# Check if virtual environment exists
if [ ! -f ".venv/bin/activate" ]; then
    osascript -e 'tell application "System Events" to display dialog "AstroFiler virtual environment not found. Please run install_macos.sh first." with title "AstroFiler Error" buttons {"OK"} default button "OK"'
    exit 1
fi

echo "Starting AstroFiler..."
echo "\$(date '+%Y-%m-%d %H:%M:%S') - AstroFiler.app - INFO - Starting AstroFiler application via macOS app" >> astrofiler.log

# Activate virtual environment and run AstroFiler
source .venv/bin/activate
python astrofiler.py

# If there's an error, show it
if [ \$? -ne 0 ]; then
    osascript -e 'tell application "System Events" to display dialog "AstroFiler exited with an error. Check the terminal for details." with title "AstroFiler Error" buttons {"OK"} default button "OK"'
fi
EOF
        
        chmod +x "$app_name/Contents/MacOS/AstroFiler"
        
        # Copy icon if it exists
        if [ -f "astrofiler.ico" ]; then
            cp astrofiler.ico "$app_name/Contents/Resources/"
        fi
        
        echo "$app_name created successfully!"
        
        # Ask about desktop shortcut
        read -p "Do you want to create a desktop alias to the app? [Y/n]: " create_alias
        case "$create_alias" in 
            n|N )
                echo "Skipping desktop alias creation."
                ;;
            * )
                if [ -d "$HOME/Desktop" ]; then
                    ln -sf "$(pwd)/$app_name" "$HOME/Desktop/AstroFiler.app"
                    echo "Desktop alias created: $HOME/Desktop/AstroFiler.app"
                else
                    echo "Desktop directory not found, skipping alias creation."
                fi
                ;;
        esac
        
        # Ask about Applications folder
        read -p "Do you want to add the app to your Applications folder? [Y/n]: " add_to_apps
        case "$add_to_apps" in 
            n|N )
                echo "Skipping Applications folder installation."
                ;;
            * )
                if [ -d "/Applications" ]; then
                    if [ -w "/Applications" ]; then
                        cp -R "$app_name" "/Applications/"
                        echo "App installed to Applications folder: /Applications/$app_name"
                    else
                        echo "Installing to Applications folder (requires admin password)..."
                        sudo cp -R "$app_name" "/Applications/"
                        echo "App installed to Applications folder: /Applications/$app_name"
                    fi
                else
                    echo "Applications folder not found, skipping installation."
                fi
                ;;
        esac
        ;;
esac

echo
