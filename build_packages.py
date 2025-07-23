#!/usr/bin/env python3
"""
AstroFiler PyInstaller Packaging Script
Creates standalone executable packages for Linux, Windows, and macOS
"""

import os
import sys
import shutil
import subprocess
import platform
import tempfile
import tarfile
import zipfile
from pathlib import Path

# Version information
VERSION = "1.0.0"
APP_NAME = "AstroFiler"

def check_pyinstaller():
    """Check if PyInstaller is installed"""
    try:
        import PyInstaller
        return True
    except ImportError:
        print("PyInstaller not found. Installing...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
            return True
        except subprocess.CalledProcessError:
            print("Failed to install PyInstaller")
            return False

def build_executable():
    """Build the executable using PyInstaller"""
    print("Building executable with PyInstaller...")
    
    # Clean previous builds
    for dir_name in ['build', 'dist']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    # Run PyInstaller
    cmd = [sys.executable, '-m', 'PyInstaller', 'astrofiler.spec', '--clean']
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("PyInstaller build failed:")
        print(result.stderr)
        return False
    
    print("PyInstaller build completed successfully")
    return True

def create_linux_package():
    """Create Linux .tar.gz package"""
    print("\nCreating Linux package...")
    
    if not os.path.exists('dist/astrofiler'):
        print("Linux executable not found in dist/astrofiler")
        return None
    
    package_name = f"{APP_NAME}-{VERSION}-linux-x64.tar.gz"
    
    with tarfile.open(package_name, "w:gz") as tar:
        # Add the executable directory
        tar.add('dist/astrofiler', arcname=f'{APP_NAME}-{VERSION}')
    
    print(f"Linux package created: {package_name}")
    return package_name

def create_windows_package():
    """Create Windows .zip package"""
    print("\nCreating Windows package...")
    
    if not os.path.exists('dist/astrofiler'):
        print("Windows executable not found in dist/astrofiler")
        return None
    
    package_name = f"{APP_NAME}-{VERSION}-windows-x64.zip"
    
    with zipfile.ZipFile(package_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('dist/astrofiler'):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join(f'{APP_NAME}-{VERSION}', 
                                     os.path.relpath(file_path, 'dist/astrofiler'))
                zipf.write(file_path, arcname)
    
    print(f"Windows package created: {package_name}")
    return package_name

def create_mac_package():
    """Create macOS .dmg package"""
    print("\nCreating macOS package...")
    
    system = platform.system()
    machine = platform.machine()
    
    # Determine architecture suffix
    if machine == 'arm64':
        arch_suffix = 'apple-silicon'
    else:
        arch_suffix = 'intel'
    
    # Check for app bundle (macOS) or regular executable
    app_path = 'dist/AstroFiler.app'
    exe_path = 'dist/astrofiler'
    
    if os.path.exists(app_path):
        source_path = app_path
        is_app_bundle = True
    elif os.path.exists(exe_path):
        source_path = exe_path
        is_app_bundle = False
    else:
        print("macOS executable/app not found")
        return None, None
    
    # Create tar.gz first (universal)
    tgz_name = f"{APP_NAME}-{VERSION}-macos-{arch_suffix}.tar.gz"
    with tarfile.open(tgz_name, "w:gz") as tar:
        if is_app_bundle:
            tar.add(source_path, arcname='AstroFiler.app')
        else:
            tar.add(source_path, arcname=f'{APP_NAME}-{VERSION}')
    
    print(f"macOS tar.gz package created: {tgz_name}")
    
    # Try to create DMG if on macOS
    dmg_name = None
    if system == "Darwin":
        try:
            dmg_name = f"{APP_NAME}-{VERSION}-macos-{arch_suffix}.dmg"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create DMG source directory
                dmg_source = os.path.join(temp_dir, 'dmg_source')
                os.makedirs(dmg_source)
                
                # Copy app/executable to DMG source
                if is_app_bundle:
                    shutil.copytree(source_path, os.path.join(dmg_source, 'AstroFiler.app'))
                else:
                    shutil.copytree(source_path, os.path.join(dmg_source, f'{APP_NAME}-{VERSION}'))
                
                # Create Applications symlink
                os.symlink('/Applications', os.path.join(dmg_source, 'Applications'))
                
                # Calculate size
                size_kb = sum(os.path.getsize(os.path.join(dp, f)) 
                             for dp, dn, fn in os.walk(dmg_source) 
                             for f in fn) // 1024
                size_mb = max(50, (size_kb // 1024) + 20)
                
                # Create temporary DMG
                temp_dmg = os.path.join(temp_dir, 'temp.dmg')
                subprocess.run([
                    'hdiutil', 'create', '-size', f'{size_mb}m',
                    '-fs', 'HFS+', '-volname', f'{APP_NAME} {VERSION}',
                    temp_dmg
                ], check=True)
                
                # Mount DMG
                mount_point = os.path.join(temp_dir, 'mount')
                os.makedirs(mount_point)
                subprocess.run([
                    'hdiutil', 'attach', temp_dmg, '-mountpoint', mount_point
                ], check=True)
                
                try:
                    # Copy contents to mounted DMG
                    for item in os.listdir(dmg_source):
                        src = os.path.join(dmg_source, item)
                        dst = os.path.join(mount_point, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
                finally:
                    # Unmount DMG
                    subprocess.run(['hdiutil', 'detach', mount_point], check=True)
                
                # Convert to compressed DMG
                subprocess.run([
                    'hdiutil', 'convert', temp_dmg, '-format', 'UDZO',
                    '-o', dmg_name
                ], check=True)
            
            print(f"macOS DMG package created: {dmg_name}")
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Could not create DMG: {e}")
            print("DMG creation requires macOS with hdiutil")
    
    return dmg_name, tgz_name

def create_build_info():
    """Create a build info file"""
    build_info = f"""AstroFiler Build Information
============================

Version: {VERSION}
Build Date: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}
Platform: {platform.system()} {platform.machine()}
Python Version: {sys.version}

Included Files:
- commands/ - Command-line utilities
- css/ - User interface themes  
- images/ - Application icons and graphics
- astrofiler.ico - Application icon
- astrofiler.ini - Default configuration
- LICENSE - License information
- README.md - Documentation

System Requirements:
- No additional dependencies required (standalone executable)
- Minimum OS versions:
  * Windows: Windows 10 or later
  * macOS: macOS 10.15 (Catalina) or later
  * Linux: Recent distributions with glibc 2.17+

Installation:
1. Extract the archive
2. Run the executable:
   - Windows: astrofiler.exe
   - macOS: Double-click AstroFiler.app
   - Linux: ./astrofiler

For more information, see README.md
"""
    
    with open('BUILD_INFO.txt', 'w') as f:
        f.write(build_info)

def main():
    """Main packaging function"""
    print(f"AstroFiler PyInstaller Packaging Script v{VERSION}")
    print("=" * 60)
    
    # Check PyInstaller
    if not check_pyinstaller():
        sys.exit(1)
    
    # Build executable
    if not build_executable():
        sys.exit(1)
    
    # Create build info
    create_build_info()
    
    # Create platform-specific packages
    packages_created = []
    
    current_platform = platform.system().lower()
    
    if current_platform == 'linux':
        linux_pkg = create_linux_package()
        if linux_pkg:
            packages_created.append(linux_pkg)
    
    elif current_platform == 'windows':
        windows_pkg = create_windows_package()
        if windows_pkg:
            packages_created.append(windows_pkg)
    
    elif current_platform == 'darwin':
        dmg_pkg, tgz_pkg = create_mac_package()
        if dmg_pkg:
            packages_created.append(dmg_pkg)
        if tgz_pkg:
            packages_created.append(tgz_pkg)
    
    # Summary
    print("\n" + "=" * 60)
    print("Packaging complete!")
    
    if packages_created:
        print("\nPackages created:")
        for pkg in packages_created:
            if os.path.exists(pkg):
                size = os.path.getsize(pkg) / (1024 * 1024)
                print(f"  {pkg} ({size:.1f} MB)")
    else:
        print("\nNo packages were created successfully.")
    
    print(f"\nExecutable location: dist/")
    if os.path.exists('dist/AstroFiler.app'):
        print("  macOS App Bundle: dist/AstroFiler.app")
    if os.path.exists('dist/astrofiler'):
        print("  Executable Directory: dist/astrofiler/")

if __name__ == "__main__":
    main()
