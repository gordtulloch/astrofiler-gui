"""
Enhanced quality analysis with SEP star detection and photometry for AstroFiler.

This module provides advanced quality metrics including:
- SEP-based star detection and source extraction
- FWHM measurement in arcseconds 
- Star eccentricity analysis
- Half Flux Radius (HFR) calculation
- Signal-to-noise ratio assessment
- Image scale calculation from FITS headers
"""

import os
import logging
import numpy as np
import warnings
from typing import Dict, List, Optional, Tuple
from astropy.io import fits
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS
from astropy.wcs import FITSFixedWarning
from astropy.stats import sigma_clipped_stats, mad_std
import datetime

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=FITSFixedWarning)  # Suppress WCS auto-correction warnings

logger = logging.getLogger(__name__)

try:
    import sep
    SEP_AVAILABLE = True
except ImportError:
    SEP_AVAILABLE = False
    logger.warning("SEP not available. Star detection will be limited.")

try:
    from scipy.optimize import curve_fit
    from scipy import ndimage
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available. Some advanced fitting methods will be limited.")


class EnhancedQualityAnalyzer:
    """
    Advanced quality analyzer with SEP-based star detection and photometry capabilities.
    """
    
    def __init__(self):
        """Initialize the enhanced quality analyzer."""
        self.min_star_count = 3  # Minimum stars needed for reliable analysis
        self.max_star_count = 10  # Maximum stars to analyze (top brightest for quality metrics)
        
        # SEP detection parameters - optimized from notebook development
        self.detection_threshold = 5.0  # Sigma threshold for star detection
        self.min_area = 5  # Minimum area in pixels
        
    def analyze_image_quality(self, fits_file_path: str, 
                            progress_callback: Optional[callable] = None) -> Dict:
        """
        Perform comprehensive quality analysis with star detection and photometry.
        
        Args:
            fits_file_path: Path to FITS file
            progress_callback: Optional progress callback function
            
        Returns:
            dict: Quality analysis results including:
                - avg_fwhm_arcsec: Average FWHM in arcseconds
                - avg_eccentricity: Average star eccentricity (0-1)
                - avg_hfr_arcsec: Average HFR in arcseconds
                - image_snr: Overall image signal-to-noise ratio
                - star_count: Number of detected stars
                - image_scale: Image scale in arcsec/pixel
        """
        try:
            if progress_callback:
                should_continue = progress_callback(0, 100, "Loading FITS file...")
                if not should_continue:
                    return {"status": "cancelled"}
            
            # Load FITS file
            with fits.open(fits_file_path) as hdul:
                header = hdul[0].header
                data = hdul[0].data.astype(np.float64)
                
                results = {
                    "file_path": fits_file_path,
                    "avg_fwhm_arcsec": None,
                    "avg_eccentricity": None,
                    "avg_hfr_arcsec": None,
                    "image_snr": None,
                    "star_count": 0,
                    "image_scale": None,
                    "analysis_timestamp": datetime.datetime.now().isoformat(),
                    "status": "success"
                }
                
                # Step 1: Calculate image scale from header (20%)
                if progress_callback:
                    should_continue = progress_callback(10, 100, "Calculating image scale...")
                    if not should_continue:
                        return {"status": "cancelled"}
                
                image_scale = self._calculate_image_scale(header)
                results["image_scale"] = image_scale
                
                # Step 2: Calculate basic image SNR (20%)
                if progress_callback:
                    should_continue = progress_callback(20, 100, "Calculating image SNR...")
                    if not should_continue:
                        return {"status": "cancelled"}
                
                results["image_snr"] = self._calculate_image_snr(data)
                
                # Step 3: Detect stars (30%)
                if progress_callback:
                    should_continue = progress_callback(40, 100, "Detecting stars...")
                    if not should_continue:
                        return {"status": "cancelled"}
                
                sources = self._detect_stars(data)
                results["star_count"] = len(sources) if sources is not None else 0
                
                if sources is not None and len(sources) >= self.min_star_count:
                    # Step 4: Measure star properties (30%)
                    if progress_callback:
                        should_continue = progress_callback(70, 100, 
                                        f"Analyzing {len(sources)} stars...")
                        if not should_continue:
                            return {"status": "cancelled"}
                    
                    star_metrics = self._analyze_star_properties(data, sources, image_scale)
                    results.update(star_metrics)
                else:
                    logger.warning(f"Insufficient stars detected ({results['star_count']}) for "
                                 f"reliable analysis in {fits_file_path}")
                
                if progress_callback:
                    progress_callback(100, 100, "Quality analysis completed!")
                
                return results
                
        except Exception as e:
            logger.error(f"Error analyzing {fits_file_path}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "file_path": fits_file_path
            }
    
    def update_file_quality_metrics(self, fits_file_id: str, quality_results: Dict) -> bool:
        """
        Update quality metrics in the database for a specific FITS file.
        
        Args:
            fits_file_id: ID of the FITS file to update
            quality_results: Quality analysis results dictionary
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Import here to avoid circular imports
            from astrofiler.models import fitsFile
            
            # Prepare update data
            update_data = {}
            
            if quality_results.get("avg_fwhm_arcsec") is not None:
                update_data["fitsFileAvgFWHMArcsec"] = quality_results["avg_fwhm_arcsec"]
            
            if quality_results.get("avg_eccentricity") is not None:
                update_data["fitsFileAvgEccentricity"] = quality_results["avg_eccentricity"]
            
            if quality_results.get("avg_hfr_arcsec") is not None:
                update_data["fitsFileAvgHFRArcsec"] = quality_results["avg_hfr_arcsec"]
            
            if quality_results.get("image_snr") is not None:
                update_data["fitsFileImageSNR"] = quality_results["image_snr"]
            
            if quality_results.get("star_count") is not None:
                update_data["fitsFileStarCount"] = quality_results["star_count"]
            
            if quality_results.get("image_scale") is not None:
                update_data["fitsFileImageScale"] = quality_results["image_scale"]
            
            # Only update if we have data to update
            if update_data:
                # Update the database record
                query = fitsFile.update(**update_data).where(fitsFile.fitsFileId == fits_file_id)
                rows_updated = query.execute()
                
                if rows_updated > 0:
                    logger.info(f"Updated quality metrics for file {fits_file_id}")
                    return True
                else:
                    logger.warning(f"No file found with ID {fits_file_id} to update")
                    return False
            else:
                logger.warning("No quality metrics to update")
                return False
                
        except Exception as e:
            logger.error(f"Error updating quality metrics for {fits_file_id}: {e}")
            return False
    
    def analyze_and_update_file(self, fits_file_path: str, fits_file_id: str, 
                              progress_callback: Optional[callable] = None) -> Dict:
        """
        Perform quality analysis and update the database in one operation.
        
        Args:
            fits_file_path: Path to FITS file
            fits_file_id: Database ID of the FITS file
            progress_callback: Optional progress callback function
            
        Returns:
            dict: Quality analysis results
        """
        # Analyze the file
        results = self.analyze_image_quality(fits_file_path, progress_callback)
        
        # Update database if analysis was successful
        if results.get("status") == "success":
            self.update_file_quality_metrics(fits_file_id, results)
        
        return results
    
    def _calculate_image_scale(self, header: fits.Header) -> Optional[float]:
        """
        Calculate image scale in arcsec/pixel from FITS header.
        
        Args:
            header: FITS header
            
        Returns:
            float: Image scale in arcsec/pixel, or None if not determinable
        """
        try:
            # Method 1: Try WCS from header
            try:
                wcs = WCS(header)
                if wcs.has_celestial:
                    pixel_scale = wcs.pixel_scale_matrix
                    scale = np.sqrt(np.abs(np.linalg.det(pixel_scale))) * 3600.0  # deg to arcsec
                    if 0.1 < scale < 100.0:  # Reasonable range for most telescopes
                        return float(scale)
            except:
                pass
            
            # Method 2: Try PIXSCALE header keyword
            pixscale = header.get('PIXSCALE')
            if pixscale is not None:
                return float(pixscale)
            
            # Method 3: Try SCALE header keyword  
            scale = header.get('SCALE')
            if scale is not None:
                return float(scale)
            
            # Method 4: Try CDELT keywords
            cdelt1 = header.get('CDELT1')
            cdelt2 = header.get('CDELT2')
            if cdelt1 is not None and cdelt2 is not None:
                # Average of the two deltas, convert to arcsec
                avg_cdelt = (abs(float(cdelt1)) + abs(float(cdelt2))) / 2.0 * 3600.0
                if 0.1 < avg_cdelt < 100.0:
                    return avg_cdelt
            
            # Method 5: Calculate from focal length and pixel size
            focal_length = header.get('FOCALLEN')  # focal length in mm
            if focal_length is not None:
                # Get pixel size based on instrument/camera
                pixel_size_microns = self._get_pixel_size(header)
                if pixel_size_microns is not None:
                    # Use the correct formula: 206.265 * pixel_size_microns / focal_length_mm
                    scale = 206.265 * pixel_size_microns / float(focal_length)
                    if 0.1 < scale < 100.0:  # Reasonable range check
                        return float(scale)
            
            # Method 6: Try to estimate from telescope/instrument (fallback)
            telescope = header.get('TELESCOP', '').lower()
            instrument = header.get('INSTRUME', '').lower()
            
            # Common telescope/instrument combinations
            if 'seestar' in telescope:
                return 1.11  # Seestar S50 typical scale
            elif 'itelescope' in telescope:
                return 1.0   # iTelescope typical scale
            
            logger.warning("Could not determine image scale from header")
            return None
            
        except Exception as e:
            logger.warning(f"Error calculating image scale: {e}")
            return None
    
    def _calculate_image_snr(self, data: np.ndarray) -> float:
        """
        Calculate overall image signal-to-noise ratio.
        
        Args:
            data: Image data array
            
        Returns:
            float: Signal-to-noise ratio
        """
        try:
            # Use sigma-clipped statistics to get robust estimates
            mean, median, std = sigma_clipped_stats(data, sigma=3.0, maxiters=5)
            
            # SNR = signal / noise
            # Use median as signal estimate, std as noise estimate
            if std > 0:
                snr = median / std
                return max(0.0, float(snr))
            else:
                return 0.0
                
        except Exception as e:
            logger.warning(f"Error calculating image SNR: {e}")
            return 0.0
    
    def _get_pixel_size(self, header: fits.Header) -> Optional[float]:
        """
        Determine pixel size in microns based on camera/instrument information.
        
        Args:
            header: FITS header
            
        Returns:
            float: Pixel size in microns, or None if not determinable
        """
        try:
            # Check for explicit pixel size in header
            if 'PIXSIZE' in header:
                return float(header['PIXSIZE'])
            if 'XPIXSZ' in header:
                return float(header['XPIXSZ'])
            
            # Determine pixel size from instrument/camera name
            instrument = header.get('INSTRUME', '').lower()
            camera = header.get('CAMERA', '').lower()
            
            # Common cameras and their pixel sizes (microns)
            camera_pixel_sizes = {
                'asi183mm': 2.4,      # ZWO ASI183MM Pro
                'asi183mc': 2.4,      # ZWO ASI183MC Pro
                'asi294mm': 4.63,     # ZWO ASI294MM Pro
                'asi294mc': 4.63,     # ZWO ASI294MC Pro
                'asi2600mm': 3.76,    # ZWO ASI2600MM Pro
                'asi2600mc': 3.76,    # ZWO ASI2600MC Pro
                'asi533mm': 3.76,     # ZWO ASI533MM Pro
                'asi533mc': 3.76,     # ZWO ASI533MC Pro
                'asi1600mm': 3.8,     # ZWO ASI1600MM Pro
                'asi1600mc': 3.8,     # ZWO ASI1600MC Pro
                'asi6200mm': 3.76,    # ZWO ASI6200MM Pro
                'asi6200mc': 3.76,    # ZWO ASI6200MC Pro
                'qhy268m': 3.76,      # QHY268M
                'qhy268c': 3.76,      # QHY268C
                'qhy294m': 4.63,      # QHY294M
                'qhy294c': 4.63,      # QHY294C
                'qhy600m': 3.76,      # QHY600M
                'qhy600c': 3.76,      # QHY600C
                'sbig': 6.8,          # SBIG cameras (typical)
                'moravian': 4.54,     # Moravian cameras (typical)
                'atik': 4.54,         # Atik cameras (typical)
                'canon': 4.3,         # Canon DSLR (typical)
                'nikon': 4.2,         # Nikon DSLR (typical)
                'sony': 4.0,          # Sony cameras (typical)
            }
            
            # Try to match camera/instrument name
            full_name = f"{instrument} {camera}".lower()
            for camera_key, pixel_size in camera_pixel_sizes.items():
                if camera_key in full_name:
                    return pixel_size
            
            # Try individual words
            words = instrument.split() + camera.split()
            for word in words:
                word = word.lower().strip()
                if word in camera_pixel_sizes:
                    return pixel_size
            
            # Check for specific patterns
            if any(x in full_name for x in ['asi183', 'zwo 183']):
                return 2.4
            elif any(x in full_name for x in ['asi294', 'zwo 294']):
                return 4.63
            elif any(x in full_name for x in ['asi2600', 'zwo 2600']):
                return 3.76
            elif any(x in full_name for x in ['asi533', 'zwo 533']):
                return 3.76
            elif any(x in full_name for x in ['qhy268']):
                return 3.76
            elif any(x in full_name for x in ['qhy294']):
                return 4.63
            
            logger.warning(f"Could not determine pixel size for instrument: {instrument}, camera: {camera}")
            return None
            
        except Exception as e:
            logger.warning(f"Error determining pixel size: {e}")
            return None
    
    def _detect_stars(self, data: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect stars in the image using SEP.
        
        Args:
            data: Image data array
            
        Returns:
            numpy.ndarray: Array of detected sources or None if detection fails
        """
        if not SEP_AVAILABLE:
            logger.warning("SEP not available for star detection")
            return None
        return self._detect_stars_sep(data)
    
    def _detect_stars_sep(self, data: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect stars using SEP (Source Extractor Python).
        
        Args:
            data: Image data array
            
        Returns:
            numpy.ndarray: Array of detected sources or None if detection fails
        """
        try:
            # Prepare data for SEP (needs to be C-contiguous)
            data_sep = data.copy(order='C')
            
            # Subtract background
            bkg = sep.Background(data_sep)
            data_sub = data_sep - bkg
            
            # Extract sources
            objects = sep.extract(data_sub, self.detection_threshold, 
                                err=bkg.globalrms, minarea=self.min_area)
            
            if len(objects) == 0:
                logger.warning("No stars detected with SEP")
                return None
            
            # Calculate enhanced measurements
            try:
                # Filter out sources with invalid ellipse parameters
                valid_mask = (objects['a'] > 0) & (objects['b'] > 0) & \
                           np.isfinite(objects['a']) & np.isfinite(objects['b'])
                valid_objects = objects[valid_mask]
                
                if len(valid_objects) == 0:
                    logger.warning("No sources with valid ellipse parameters")
                    return None
                
                # Calculate Kron radius for flux measurements
                kronrad, krflag = sep.kron_radius(data_sub, valid_objects['x'], valid_objects['y'], 
                                                 valid_objects['a'], valid_objects['b'], 
                                                 valid_objects['theta'], 6.0)
                
                # Use minimum radius for failed Kron calculations
                kronrad = np.maximum(kronrad, 2.5)  # Minimum radius of 2.5 pixels
                
                # Calculate flux within Kron apertures
                flux, fluxerr, flag = sep.sum_ellipse(data_sub, valid_objects['x'], valid_objects['y'], 
                                                     valid_objects['a'], valid_objects['b'], 
                                                     valid_objects['theta'], 
                                                     2.5*kronrad, subpix=1, err=bkg.globalrms)
                
                # Calculate FWHM from semi-major and semi-minor axes
                fwhm = 2.0 * np.sqrt(2.0 * np.log(2.0)) * np.sqrt(valid_objects['a'] * valid_objects['b'])
                
                # Calculate eccentricity: e = sqrt(1 - (b/a)^2)
                eccentricity = np.sqrt(1.0 - (valid_objects['b'] / valid_objects['a'])**2)
                
                # Calculate Half Flux Radius (HFR) - approximation using sqrt(a*b)
                hfr = np.sqrt(valid_objects['a'] * valid_objects['b'])
                
                # Create arrays for all objects (valid and invalid)
                all_fwhm = np.full(len(objects), np.nan)
                all_eccentricity = np.full(len(objects), np.nan)
                all_hfr = np.full(len(objects), np.nan)
                all_flux = np.full(len(objects), np.nan)
                
                # Fill in values for valid objects
                all_fwhm[valid_mask] = fwhm
                all_eccentricity[valid_mask] = eccentricity
                all_hfr[valid_mask] = hfr
                all_flux[valid_mask] = flux
                
                # Add new fields to objects structured array
                import numpy.lib.recfunctions as rfn
                objects = rfn.append_fields(objects, 'fwhm', all_fwhm)
                objects = rfn.append_fields(objects, 'eccentricity', all_eccentricity)
                objects = rfn.append_fields(objects, 'hfr', all_hfr)
                objects = rfn.append_fields(objects, 'flux_kron', all_flux)
                
                logger.info(f"SEP detected {len(objects)} sources, {np.sum(~np.isnan(all_fwhm))} with valid measurements")
                
            except Exception as calc_error:
                logger.warning(f"Could not calculate enhanced SEP measurements: {calc_error}")
                # Add dummy fields if calculation fails
                import numpy.lib.recfunctions as rfn
                fwhm = np.full(len(objects), np.nan)
                eccentricity = np.full(len(objects), np.nan)
                hfr = np.full(len(objects), np.nan)
                flux = np.full(len(objects), np.nan)
                objects = rfn.append_fields(objects, 'fwhm', fwhm)
                objects = rfn.append_fields(objects, 'eccentricity', eccentricity)
                objects = rfn.append_fields(objects, 'hfr', hfr)
                objects = rfn.append_fields(objects, 'flux_kron', flux)
            
            # Limit number of sources for performance
            if len(objects) > self.max_star_count:
                # Sort by flux and take brightest stars
                valid_flux_mask = ~np.isnan(objects['flux_kron'])
                if np.any(valid_flux_mask):
                    flux_sort_idx = np.argsort(objects['flux_kron'])[::-1]
                    objects = objects[flux_sort_idx[:self.max_star_count]]
                else:
                    objects = objects[:self.max_star_count]
            
            return objects
            
        except Exception as e:
            logger.warning(f"Error in SEP star detection: {e}")
            return None
    
    def _analyze_star_properties(self, data: np.ndarray, sources, 
                               image_scale: Optional[float]) -> Dict:
        """
        Analyze properties of detected stars.
        
        Args:
            data: Image data array
            sources: Detected sources from SEP or DAOStarFinder
            image_scale: Image scale in arcsec/pixel
            
        Returns:
            dict: Star analysis results
        """
        try:
            # With SEP-only detection, sources should always have SEP-derived measurements.
            has_sep_measurements = hasattr(sources, 'dtype') and 'fwhm' in sources.dtype.names
            if not has_sep_measurements:
                return {}
            return self._analyze_sep_measurements(sources, image_scale)
                
        except Exception as e:
            logger.warning(f"Error analyzing star properties: {e}")
            return {}
    
    def _analyze_sep_measurements(self, sources, image_scale: Optional[float]) -> Dict:
        """
        Analyze star properties from SEP measurements.
        
        Args:
            sources: SEP sources with calculated measurements
            image_scale: Image scale in arcsec/pixel
            
        Returns:
            dict: Star analysis results
        """
        try:
            # Extract valid measurements
            valid_fwhm = sources['fwhm'][~np.isnan(sources['fwhm'])]
            valid_hfr = sources['hfr'][~np.isnan(sources['hfr'])]
            valid_ecc = sources['eccentricity'][~np.isnan(sources['eccentricity'])]
            
            # Calculate averages
            results = {}
            
            if len(valid_fwhm) > 0:
                avg_fwhm_pixels = np.median(valid_fwhm)
                results['avg_fwhm_pixels'] = float(avg_fwhm_pixels)
                
                # Convert to arcseconds if we have image scale
                if image_scale is not None:
                    results['avg_fwhm_arcsec'] = float(avg_fwhm_pixels * image_scale)
                else:
                    results['avg_fwhm_arcsec'] = None
            else:
                results['avg_fwhm_arcsec'] = None
                
            if len(valid_ecc) > 0:
                results['avg_eccentricity'] = float(np.median(valid_ecc))
            else:
                results['avg_eccentricity'] = None
                
            if len(valid_hfr) > 0:
                avg_hfr_pixels = np.median(valid_hfr)
                results['avg_hfr_pixels'] = float(avg_hfr_pixels)
                
                # Convert to arcseconds if we have image scale
                if image_scale is not None:
                    results['avg_hfr_arcsec'] = float(avg_hfr_pixels * image_scale)
                else:
                    results['avg_hfr_arcsec'] = None
            else:
                results['avg_hfr_arcsec'] = None
            
            logger.info(f"SEP analysis: {len(valid_fwhm)} FWHM, {len(valid_hfr)} HFR, {len(valid_ecc)} eccentricity measurements")
            return results
            
        except Exception as e:
            logger.warning(f"Error analyzing SEP measurements: {e}")
            return {}
    
    
    def _measure_star_properties(self, cutout: np.ndarray) -> Dict:
        """
        Measure FWHM, eccentricity, and HFR for a single star cutout.
        
        Args:
            cutout: Star cutout image
            
        Returns:
            dict: Star properties
        """
        try:
            # Calculate background
            mean, median, std = sigma_clipped_stats(cutout, sigma=2.0)
            cutout_sub = cutout - median
            
            # Find the peak
            peak_y, peak_x = np.unravel_index(np.argmax(cutout_sub), cutout_sub.shape)
            
            if cutout_sub[peak_y, peak_x] < 3 * std:
                # Too faint
                return {'fwhm': None, 'eccentricity': None, 'hfr': None}
            
            # Measure FWHM using radial profile
            fwhm = self._measure_fwhm_radial(cutout_sub, peak_x, peak_y)
            
            # Measure eccentricity using moments
            eccentricity = self._measure_eccentricity_moments(cutout_sub, peak_x, peak_y)
            
            # Measure HFR
            hfr = self._measure_hfr(cutout_sub, peak_x, peak_y)
            
            return {
                'fwhm': fwhm,
                'eccentricity': eccentricity,
                'hfr': hfr
            }
            
        except Exception as e:
            logger.debug(f"Error measuring star properties: {e}")
            return {'fwhm': None, 'eccentricity': None, 'hfr': None}
    
    def _measure_fwhm_radial(self, cutout: np.ndarray, center_x: float, 
                           center_y: float) -> Optional[float]:
        """
        Measure FWHM using radial profile method.
        
        Args:
            cutout: Background-subtracted star cutout
            center_x, center_y: Star center coordinates
            
        Returns:
            float: FWHM in pixels, or None if measurement fails
        """
        try:
            # Create coordinate arrays
            y, x = np.mgrid[:cutout.shape[0], :cutout.shape[1]]
            r = np.sqrt((x - center_x)**2 + (y - center_y)**2)
            
            # Create radial profile with finer resolution
            r_max = min(cutout.shape) // 2  # Use more of the cutout
            r_bins = np.linspace(0, r_max, int(r_max * 4) + 1)  # Finer bins
            
            # Calculate radial profile
            radial_profile = []
            radial_counts = []
            
            for i in range(len(r_bins) - 1):
                mask = (r >= r_bins[i]) & (r < r_bins[i + 1])
                if np.any(mask):
                    profile_value = np.mean(cutout[mask])
                    pixel_count = np.sum(mask)
                    radial_profile.append(profile_value)
                    radial_counts.append(pixel_count)
                else:
                    radial_profile.append(0)
                    radial_counts.append(0)
            
            radial_profile = np.array(radial_profile)
            radial_counts = np.array(radial_counts)
            r_centers = (r_bins[:-1] + r_bins[1:]) / 2
            
            # Only use bins with enough pixels for reliable measurement
            valid_mask = radial_counts >= 3
            if not np.any(valid_mask):
                return None
                
            radial_profile = radial_profile[valid_mask]
            r_centers = r_centers[valid_mask]
            
            # Find FWHM (half maximum)
            max_value = np.max(radial_profile)
            if max_value <= 0:
                return None
                
            half_max = max_value / 2.0
            
            # Find where profile crosses half maximum
            above_half = radial_profile >= half_max
            if not np.any(above_half):
                return None
            
            # Find the last radius where we're above half maximum
            above_indices = np.where(above_half)[0]
            if len(above_indices) > 0:
                # Use interpolation for more precise FWHM measurement
                last_above_idx = above_indices[-1]
                
                # Try to interpolate the crossing point
                if last_above_idx < len(radial_profile) - 1:
                    # Interpolate between the last point above and first point below
                    r1, r2 = r_centers[last_above_idx], r_centers[last_above_idx + 1]
                    v1, v2 = radial_profile[last_above_idx], radial_profile[last_above_idx + 1]
                    
                    if v1 != v2:  # Avoid division by zero
                        # Linear interpolation to find exact crossing
                        fwhm_radius = r1 + (half_max - v1) * (r2 - r1) / (v2 - v1)
                    else:
                        fwhm_radius = r1
                else:
                    fwhm_radius = r_centers[last_above_idx]
                
                # FWHM is full width (diameter), so multiply by 2
                fwhm = fwhm_radius * 2.0
                
                # Sanity check: FWHM should be reasonable (0.5 to 50 pixels typically)
                if 0.5 <= fwhm <= 50.0:
                    return float(fwhm)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error in FWHM calculation: {e}")
            return None
    
    def _measure_eccentricity_moments(self, cutout: np.ndarray, center_x: float, 
                                    center_y: float) -> Optional[float]:
        """
        Measure eccentricity using image moments.
        
        Args:
            cutout: Background-subtracted star cutout
            center_x, center_y: Star center coordinates
            
        Returns:
            float: Eccentricity (0=circular, 1=highly elongated), or None if fails
        """
        try:
            # Create coordinate arrays using mgrid for proper 2D arrays
            yy, xx = np.mgrid[0:cutout.shape[0], 0:cutout.shape[1]]
            x = xx.astype(float) - center_x
            y = yy.astype(float) - center_y
            
            # Only use positive values for moments calculation
            mask = cutout > 0
            if not np.any(mask):
                return None
            
            weights = cutout[mask]
            x_coords = x[mask]
            y_coords = y[mask]
            
            # Calculate second moments
            total_weight = np.sum(weights)
            if total_weight <= 0:
                return None
            
            m20 = np.sum(weights * x_coords**2) / total_weight
            m02 = np.sum(weights * y_coords**2) / total_weight
            m11 = np.sum(weights * x_coords * y_coords) / total_weight
            
            # Calculate eccentricity from moments
            # e = sqrt(1 - b^2/a^2) where a, b are semi-major, semi-minor axes
            trace = m20 + m02
            det = m20 * m02 - m11**2
            
            if det <= 0 or trace <= 0:
                return None
            
            # Semi-axes from eigenvalues
            discriminant = (m20 - m02)**2 + 4*m11**2
            if discriminant < 0:
                return None
            
            a_sq = (trace + np.sqrt(discriminant)) / 2
            b_sq = (trace - np.sqrt(discriminant)) / 2
            
            if a_sq <= 0 or b_sq <= 0:
                return None
            
            eccentricity = np.sqrt(1 - b_sq / a_sq)
            return float(np.clip(eccentricity, 0.0, 1.0))
            
        except Exception as e:
            logger.debug(f"Error in eccentricity calculation: {e}")
            return None
    
    def _measure_hfr(self, cutout: np.ndarray, center_x: float, center_y: float) -> Optional[float]:
        """
        Measure Half Flux Radius (HFR).
        
        Args:
            cutout: Background-subtracted star cutout
            center_x, center_y: Star center coordinates
            
        Returns:
            float: HFR in pixels, or None if measurement fails
        """
        try:
            y, x = np.ogrid[:cutout.shape[0], :cutout.shape[1]]
            r = np.sqrt((x - center_x)**2 + (y - center_y)**2)
            
            # Only consider positive flux
            mask = cutout > 0
            if not np.any(mask):
                return None
            
            # Sort pixels by radius
            flux_values = cutout[mask]
            radius_values = r[mask]
            
            # Calculate cumulative flux as function of radius
            max_radius = np.max(radius_values)
            r_bins = np.linspace(0, max_radius, 100)
            cumulative_flux = []
            
            total_flux = np.sum(flux_values)
            if total_flux <= 0:
                return None
            
            for radius in r_bins:
                flux_within = np.sum(flux_values[radius_values <= radius])
                cumulative_flux.append(flux_within)
            
            cumulative_flux = np.array(cumulative_flux)
            
            # Find radius containing half the flux
            half_flux = total_flux / 2.0
            
            # Interpolate to find HFR
            if len(cumulative_flux) > 1:
                hfr_idx = np.searchsorted(cumulative_flux, half_flux)
                if 0 < hfr_idx < len(r_bins):
                    hfr = r_bins[hfr_idx]
                    return float(hfr)
            
            return None
            
        except Exception:
            return None