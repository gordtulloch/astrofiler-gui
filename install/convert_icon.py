#!/usr/bin/env python3
"""
Simple icon converter using PIL to create a PNG version of the ICO file
for better Linux desktop integration.
"""

import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("PIL (Pillow) not available. Cannot convert icon.")
    sys.exit(1)

def convert_ico_to_png(ico_path, png_path):
    """Convert ICO file to PNG format."""
    try:
        # Open the ICO file
        with Image.open(ico_path) as img:
            # Get the largest size available in the ICO
            if hasattr(img, 'size'):
                sizes = [img.size]
            else:
                sizes = []
                try:
                    while True:
                        sizes.append(img.size)
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass
                img.seek(0)
            
            # Find the largest size (prefer 48x48 or larger for desktop icons)
            if sizes:
                best_size = max(sizes, key=lambda x: x[0] * x[1])
                if best_size != img.size:
                    for i in range(100):  # Try to find the best size
                        try:
                            img.seek(i)
                            if img.size == best_size:
                                break
                        except EOFError:
                            img.seek(0)
                            break
            
            # Convert to RGBA if necessary
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Save as PNG
            img.save(png_path, 'PNG')
            print(f"Successfully converted {ico_path} to {png_path}")
            return True
            
    except Exception as e:
        print(f"Error converting icon: {e}")
        return False

if __name__ == "__main__":
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    
    ico_path = project_dir / "astrofiler.ico"
    png_path = project_dir / "astrofiler.png"
    
    if not ico_path.exists():
        print(f"Error: {ico_path} not found!")
        sys.exit(1)
    
    if convert_ico_to_png(ico_path, png_path):
        print("Icon conversion completed successfully!")
    else:
        print("Icon conversion failed!")
        sys.exit(1)
