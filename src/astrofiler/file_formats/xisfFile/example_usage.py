"""
Example usage of the XISF to FITS converter

This example demonstrates how to use the XISFConverter class to convert
XISF files to FITS format.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to path so we can import xisfFile
sys.path.insert(0, str(Path(__file__).parent.parent))

from xisfFile import XISFConverter


def convert_xisf_file(xisf_path: str, output_path: str = None) -> bool:
    """
    Convert a single XISF file to FITS format.
    
    Args:
        xisf_path (str): Path to the XISF file
        output_path (str, optional): Output FITS file path
        
    Returns:
        bool: True if conversion was successful, False otherwise
    """
    try:
        # Create converter instance
        print(f"Loading XISF file: {xisf_path}")
        converter = XISFConverter(xisf_path)
        
        # Display file information
        info = converter.get_image_info()
        geometry = info['geometry']
        print(f"Image dimensions: {geometry['width']}x{geometry['height']}")
        print(f"Channels: {geometry['channels']}")
        print(f"Sample format: {geometry['sample_format']}")
        print(f"Compression: {geometry['compression_codec']}")
        print(f"Color space: {geometry['color_space']}")
        print(f"Header cards: {info['header_cards_count']}")
        print(f"Location method: {info['location_method']}")
        
        if info['location_method'] == 'attachment':
            print(f"Attachment offset: {info['location_start']}")
            print(f"Attachment length: {info['location_length']}")
        
        # Display geometry details
        if len(geometry['dimensions']) > 2:
            print(f"Multi-dimensional image: {geometry['dimensions']}")
        
        # Check for compression details
        if geometry['compression']:
            print(f"Compression details: {geometry['compression']}")
            if '+sh' in geometry['compression']:
                print("  → Uses byte shuffling")
        
        # Convert to FITS
        print("Converting to FITS format...")
        output_file = converter.convert_to_fits(output_path)
        print(f"FITS file created: {output_file}")
        
        # Display some header information
        header_cards = converter.get_header_cards()
        print("\nKey FITS header cards:")
        for key in ['SIMPLE', 'BITPIX', 'NAXIS', 'NAXIS1', 'NAXIS2']:
            if key in header_cards:
                print(f"  {key}: {header_cards[key]}")
        
        return True
        
    except Exception as e:
        print(f"Error converting {xisf_path}: {e}")
        return False


def convert_directory(directory_path: str, output_directory: str = None) -> None:
    """
    Convert all XISF files in a directory to FITS format.
    
    Args:
        directory_path (str): Directory containing XISF files
        output_directory (str, optional): Output directory for FITS files
    """
    directory = Path(directory_path)
    if not directory.exists():
        print(f"Directory not found: {directory_path}")
        return
    
    # Find all XISF files
    xisf_files = list(directory.glob("*.xisf"))
    if not xisf_files:
        print(f"No XISF files found in {directory_path}")
        return
    
    print(f"Found {len(xisf_files)} XISF files to convert")
    
    successful = 0
    failed = 0
    
    for xisf_file in xisf_files:
        print(f"\n--- Converting {xisf_file.name} ---")
        
        # Determine output path
        if output_directory:
            output_dir = Path(output_directory)
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"{xisf_file.stem}.fits"
        else:
            output_path = xisf_file.with_suffix('.fits')
        
        if convert_xisf_file(str(xisf_file), str(output_path)):
            successful += 1
        else:
            failed += 1
    
    print(f"\n--- Conversion Summary ---")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(xisf_files)}")


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert XISF files to FITS format")
    parser.add_argument("input", help="Input XISF file or directory")
    parser.add_argument("-o", "--output", help="Output FITS file or directory")
    parser.add_argument("-d", "--directory", action="store_true", 
                       help="Process all XISF files in input directory")
    
    args = parser.parse_args()
    
    if args.directory:
        convert_directory(args.input, args.output)
    else:
        if not os.path.exists(args.input):
            print(f"File not found: {args.input}")
            return 1
        
        success = convert_xisf_file(args.input, args.output)
        return 0 if success else 1


if __name__ == "__main__":
    # Example usage when run directly
    
    # Example 1: Convert a single file
    example_file = "example.xisf"
    if os.path.exists(example_file):
        print("Example 1: Converting single file")
        convert_xisf_file(example_file)
    else:
        print(f"Example file {example_file} not found")
    
    # Example 2: Convert all files in a directory
    #example_dir = "xisf_files"
    #if os.path.exists(example_dir):
    #    print("\nExample 2: Converting directory")
    #    convert_directory(example_dir, "fits_output")
    #else:
    #    print(f"Example directory {example_dir} not found")
    
    # Run command-line interface if arguments provided
    if len(sys.argv) > 1:
        exit(main())