#!/bin/bash
# AstroFiler Installation Script for Linux/Unix
# This script checks for Python, installs it if needed (with package manager),
# creates a virtual environment, and installs all required dependencies.

set -e  # Exit on any error

echo "========================================"
echo "AstroFiler Installation Script for Linux"
echo "========================================"
echo

# Change to parent directory (where astrofiler.py is located)
cd "$(dirname "$0")/.."

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect package manager and install Python
install_python() {
    echo "Python is not installed. Attempting to install..."
    
    if command_exists apt-get; then
        # Debian/Ubuntu
        echo "Detected Debian/Ubuntu system. Installing Python..."
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv python3-dev
    elif command_exists yum; then
        # RHEL/CentOS (older)
        echo "Detected RHEL/CentOS system. Installing Python..."
        sudo yum install -y python3 python3-pip python3-venv python3-devel
    elif command_exists dnf; then
        # Fedora/RHEL 8+
        echo "Detected Fedora/RHEL 8+ system. Installing Python..."
        sudo dnf install -y python3 python3-pip python3-venv python3-devel
    elif command_exists pacman; then
        # Arch Linux
        echo "Detected Arch Linux system. Installing Python..."
        sudo pacman -S --noconfirm python python-pip python-virtualenv
    elif command_exists zypper; then
        # openSUSE
        echo "Detected openSUSE system. Installing Python..."
        sudo zypper install -y python3 python3-pip python3-venv python3-devel
    elif command_exists brew; then
        # macOS with Homebrew
        echo "Detected macOS with Homebrew. Installing Python..."
        brew install python
    else
        echo "Error: Could not detect package manager."
        echo "Please install Python 3.8+ manually and run this script again."
        echo "Visit: https://www.python.org/downloads/"
        exit 1
    fi
}

# Check if Python is installed
if ! command_exists python3; then
    install_python
fi

# Check Python version
echo "Checking Python installation..."
python3 --version

# Check if Python version is 3.8+
python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null
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
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment."
        echo "Make sure you have the venv module installed."
        echo "You can install it with your package manager or: pip3 install virtualenv"
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
        exit 1
    fi
else
    echo "Warning: requirements.txt not found."
    echo "Installing packages manually..."
    python -m pip install astropy peewee numpy matplotlib pytz PySide6 Pillow
fi

echo
echo "========================================"
echo "Installation completed successfully!"
echo "========================================"
echo
echo "To run AstroFiler:"
echo "1. Open terminal in this directory"
echo "2. Run: source .venv/bin/activate"
echo "3. Run: python astrofiler.py"
echo
echo "You can also use the run_astrofiler.sh script for convenience."
echo

# Create convenience run script
echo "Creating run script..."
cat > run_astrofiler.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python astrofiler.py
EOF

chmod +x run_astrofiler.sh
echo "run_astrofiler.sh created and made executable."

# Make desktop launcher executable
chmod +x install/launch_astrofiler.sh
echo "Desktop launcher created and made executable: install/launch_astrofiler.sh"

# Create desktop shortcut
echo
read -p "Do you want to create a desktop shortcut? [y/N]: " create_desktop
case "$create_desktop" in 
    y|Y )
        echo "Creating desktop shortcut..."
        
        # Get current directory
        CURRENT_DIR="$(pwd)"
        
        # Convert ICO to PNG for better Linux compatibility using Python
        echo "Converting icon to PNG format for better compatibility..."
        python3 -c "
try:
    from PIL import Image
    import sys
    
    # Open the ICO file and convert to PNG
    with Image.open('astrofiler.ico') as img:
        # Convert to RGBA if necessary
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Save as PNG
        img.save('astrofiler.png', 'PNG')
        print('Icon converted successfully!')
except ImportError:
    print('PIL not available, trying without it...')
    # Fallback: just copy the ico file and rename it
    import shutil
    shutil.copy2('astrofiler.ico', 'astrofiler.png')
    print('Icon copied (may not display correctly)')
except Exception as e:
    print(f'Icon conversion failed: {e}')
    print('Will use original ICO file')
" 2>/dev/null || echo "Note: Icon conversion failed, using ICO file"
        
        # Validate that the launcher script exists and is executable
        if [ ! -f "install/launch_astrofiler.sh" ]; then
            echo "Error: launch_astrofiler.sh not found!"
            exit 1
        fi
        
        # Make sure the launcher is executable
        chmod +x install/launch_astrofiler.sh
        
        # Create desktop file with correct paths
        if [ -f "astrofiler.png" ]; then
            # Use PNG icon if available
            sed "s|ASTROFILER_PATH|$CURRENT_DIR|g; s|astrofiler\.ico|astrofiler.png|g" install/astrofiler.desktop > install/astrofiler_configured.desktop
        else
            # Fall back to ICO icon
            sed "s|ASTROFILER_PATH|$CURRENT_DIR|g" install/astrofiler.desktop > install/astrofiler_configured.desktop
        fi
        
        # Make the desktop file executable
        chmod +x install/astrofiler_configured.desktop
        
        # Validate the desktop file if desktop-file-validate is available
        if command_exists desktop-file-validate; then
            echo "Validating desktop file..."
            if desktop-file-validate install/astrofiler_configured.desktop; then
                echo "Desktop file validation passed."
            else
                echo "Warning: Desktop file validation failed, but continuing anyway."
            fi
        fi
        
        # Copy to desktop if it exists
        if [ -d "$HOME/Desktop" ]; then
            cp install/astrofiler_configured.desktop "$HOME/Desktop/AstroFiler.desktop"
            chmod +x "$HOME/Desktop/AstroFiler.desktop"
            echo "Desktop shortcut created: $HOME/Desktop/AstroFiler.desktop"
        fi
        
        # Install to applications menu
        if [ -d "$HOME/.local/share/applications" ]; then
            mkdir -p "$HOME/.local/share/applications"
            cp install/astrofiler_configured.desktop "$HOME/.local/share/applications/astrofiler.desktop"
            chmod +x "$HOME/.local/share/applications/astrofiler.desktop"
            echo "Application menu entry created: $HOME/.local/share/applications/astrofiler.desktop"
        fi
        
        # Update desktop database if available
        if command_exists update-desktop-database; then
            update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        fi
        
        # Clean up temporary file
        rm -f install/astrofiler_configured.desktop
        
        echo "Desktop integration completed!"
        echo
        echo "If the desktop icon shows as broken:"
        echo "1. Right-click the icon and select 'Properties' or 'Allow Launching'"
        echo "2. Check that the 'Allow executing file as program' option is enabled"
        echo "3. If the icon doesn't appear, try logging out and back in"
        echo "4. You can also run: update-desktop-database ~/.local/share/applications"
        ;;
    * )
        echo "Skipping desktop shortcut creation."
        ;;
esac

echo
