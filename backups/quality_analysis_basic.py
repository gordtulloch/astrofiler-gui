"""
Quality analysis module for AstroFiler.

This module handles comprehensive FITS frame quality assessment including
noise analysis, uniformity analysis, FWHM analysis, and overall scoring.
"""

import os
import logging
import datetime
import numpy as np
from astropy.io import fits

logger = logging.getLogger(__name__)


class QualityAnalyzer:
    """
    Handles quality analysis operations for FITS frames.
    """
    
    def __init__(self):
        """Initialize QualityAnalyzer."""
        pass

    def assessFrameQuality(self, fits_file_path, frame_type="auto", progress_callback=None):
        """
        Comprehensive quality assessment for FITS frames.
        
        Args:
            fits_file_path: Path to FITS file to analyze
            frame_type: Type of frame ("light", "bias", "dark", "flat", "auto")
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: Comprehensive quality assessment including:
                - overall_score: Overall quality score (0-100)
                - frame_type: Detected or specified frame type
                - noise_metrics: Noise analysis results
                - uniformity_metrics: Uniformity analysis (for calibration frames)
                - fwhm_metrics: FWHM analysis (for light frames only)
                - acquisition_quality: Header-based quality indicators
                - quality_category: Text description of quality level
                - recommendations: List of quality improvement suggestions
        """
        try:
            logger.info(f"Assessing frame quality: {fits_file_path}")
            
            if progress_callback:
                should_continue = progress_callback(0, 100, "Loading FITS file...")
                if not should_continue:
                    return {"status": "cancelled", "message": "Quality assessment cancelled"}
            
            # Load the FITS file
            with fits.open(fits_file_path) as hdul:
                header = hdul[0].header
                data = hdul[0].data.astype(float)
                
                results = {
                    "file_path": fits_file_path,
                    "overall_score": 0,
                    "frame_type": frame_type,
                    "noise_metrics": {},
                    "uniformity_metrics": {},
                    "fwhm_metrics": {},
                    "acquisition_quality": {},
                    "quality_category": "",
                    "recommendations": [],
                    "assessment_timestamp": datetime.datetime.now().isoformat()
                }
                
                # Auto-detect frame type if needed
                if frame_type == "auto":
                    results["frame_type"] = self._detectFrameType(header, data)
                
                # Phase 1: Noise analysis (30% progress)
                if progress_callback:
                    should_continue = progress_callback(20, 100, "Analyzing noise characteristics...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["noise_metrics"] = self._analyzeNoiseMetrics(data, header, progress_callback)
                
                # Phase 2: Uniformity analysis for calibration frames (30% progress)
                if results["frame_type"] in ["bias", "dark", "flat"]:
                    if progress_callback:
                        should_continue = progress_callback(50, 100, "Assessing frame uniformity...")
                        if not should_continue:
                            return {"status": "cancelled", "message": "Quality assessment cancelled"}
                    
                    results["uniformity_metrics"] = self._analyzeUniformityMetrics(data)
                
                # Phase 3: FWHM analysis for light frames (30% progress)
                elif results["frame_type"] == "light":
                    if progress_callback:
                        should_continue = progress_callback(50, 100, "Analyzing star profiles (FWHM)...")
                        if not should_continue:
                            return {"status": "cancelled", "message": "Quality assessment cancelled"}
                    
                    results["fwhm_metrics"] = self._analyzeFWHMMetrics(data)
                
                # Phase 4: Acquisition quality analysis (20% progress)
                if progress_callback:
                    should_continue = progress_callback(80, 100, "Assessing acquisition quality...")
                    if not should_continue:
                        return {"status": "cancelled", "message": "Quality assessment cancelled"}
                
                results["acquisition_quality"] = self._analyzeAcquisitionQuality(header, results["frame_type"])
                
                # Phase 5: Overall scoring and recommendations
                results["overall_score"] = self._calculateOverallQualityScore(results, results["frame_type"])
                results["quality_category"] = self._getQualityCategory(results["overall_score"])
                results["recommendations"] = self._generateRecommendations(results, results["frame_type"])
                
                if progress_callback:
                    progress_callback(100, 100, "Quality assessment completed!")
                
                logger.info(f"Quality assessment complete: scored {results['overall_score']}/100 ({results['quality_category']})")
                return results
                
        except Exception as e:
            logger.error(f"Error in quality assessment for {fits_file_path}: {e}")
            return {
                "status": "error",
                "message": f"Quality assessment failed: {e}",
                "file_path": fits_file_path,
                "overall_score": 0
            }

    def batchAssessQuality(self, file_paths, frame_type="auto", progress_callback=None):
        """
        Batch quality assessment for multiple files.
        
        Args:
            file_paths: List of FITS file paths to analyze
            frame_type: Type of frames or "auto" for auto-detection
            progress_callback: Optional callback for progress updates
            
        Returns:
            list: List of quality assessment results
        """
        results = []
        total_files = len(file_paths)
        
        logger.info(f"Starting batch quality assessment for {total_files} files")
        
        for i, file_path in enumerate(file_paths):
            if progress_callback:
                should_continue = progress_callback(i, total_files, f"Processing {os.path.basename(file_path)}...")
                if not should_continue:
                    logger.info("Batch quality assessment cancelled by user")
                    break
            
            try:
                result = self.assessFrameQuality(file_path, frame_type)
                results.append(result)
                
                if result.get("status") == "error":
                    logger.warning(f"Failed to assess {file_path}: {result.get('message', 'Unknown error')}")
                else:
                    logger.debug(f"Assessed {file_path}: {result.get('overall_score', 0)}/100")
                    
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                results.append({
                    "status": "error",
                    "message": str(e),
                    "file_path": file_path,
                    "overall_score": 0
                })
        
        if progress_callback:
            progress_callback(total_files, total_files, "Batch assessment completed")
        
        # Calculate summary statistics
        successful_results = [r for r in results if r.get("status") != "error"]
        if successful_results:
            scores = [r.get("overall_score", 0) for r in successful_results]
            avg_score = sum(scores) / len(scores)
            logger.info(f"Batch assessment complete: {len(successful_results)}/{total_files} files assessed, average score: {avg_score:.1f}")
        
        return results

    def _detectFrameType(self, header, image_data):
        """
        Auto-detect the frame type from header and image data.
        
        Args:
            header: FITS header
            image_data: FITS image data
            
        Returns:
            str: Detected frame type ('light', 'bias', 'dark', 'flat')
        """
        # Check header for explicit frame type
        imagetyp = header.get('IMAGETYP', '').upper()
        if 'LIGHT' in imagetyp:
            return 'light'
        elif 'BIAS' in imagetyp:
            return 'bias'
        elif 'DARK' in imagetyp:
            return 'dark'
        elif 'FLAT' in imagetyp:
            return 'flat'
        
        # Check object field
        object_name = header.get('OBJECT', '').upper()
        if 'BIAS' in object_name:
            return 'bias'
        elif 'DARK' in object_name:
            return 'dark'
        elif 'FLAT' in object_name:
            return 'flat'
        
        # Check exposure time for bias frames
        exptime = header.get('EXPTIME', header.get('EXPOSURE', 1))
        if exptime == 0 or exptime < 0.001:
            return 'bias'
        
        # Default to light frame
        return 'light'

    def _analyzeNoiseMetrics(self, image_data, header, progress_callback=None):
        """
        Analyze noise characteristics of the image.
        
        Args:
            image_data: FITS image data
            header: FITS header
            progress_callback: Optional progress callback
            
        Returns:
            dict: Noise analysis results
        """
        try:
            # Basic statistics
            mean_value = float(np.mean(image_data))
            std_value = float(np.std(image_data))
            median_value = float(np.median(image_data))
            min_value = float(np.min(image_data))
            max_value = float(np.max(image_data))
            
            # Signal-to-noise ratio estimate
            snr = mean_value / std_value if std_value > 0 else 0
            
            # Hot pixel detection (pixels > mean + 5*std)
            hot_pixel_threshold = mean_value + 5 * std_value
            hot_pixels = np.sum(image_data > hot_pixel_threshold)
            hot_pixels_percent = (hot_pixels / image_data.size) * 100
            
            # Cold pixel detection (pixels < mean - 5*std)
            cold_pixel_threshold = mean_value - 5 * std_value
            cold_pixels = np.sum(image_data < cold_pixel_threshold)
            cold_pixels_percent = (cold_pixels / image_data.size) * 100
            
            # Noise score (0-100, higher is better)
            noise_score = max(0, min(100, 100 - (std_value / mean_value * 100) if mean_value > 0 else 0))
            
            return {
                'mean': mean_value,
                'std': std_value,
                'median': median_value,
                'min': min_value,
                'max': max_value,
                'snr': snr,
                'hot_pixels': int(hot_pixels),
                'hot_pixels_percent': hot_pixels_percent,
                'cold_pixels': int(cold_pixels),
                'cold_pixels_percent': cold_pixels_percent,
                'noise_score': noise_score
            }
            
        except Exception as e:
            logger.error(f"Error in noise analysis: {e}")
            return {
                'mean': 0, 'std': 0, 'median': 0, 'min': 0, 'max': 0,
                'snr': 0, 'hot_pixels': 0, 'hot_pixels_percent': 0,
                'cold_pixels': 0, 'cold_pixels_percent': 0, 'noise_score': 0
            }

    def _analyzeUniformityMetrics(self, image_data):
        """
        Analyze spatial uniformity of the image (for calibration frames).
        
        Args:
            image_data: FITS image data
            
        Returns:
            dict: Uniformity analysis results
        """
        try:
            h, w = image_data.shape
            
            # Divide image into quadrants
            h_mid, w_mid = h // 2, w // 2
            q1 = image_data[:h_mid, :w_mid]  # Top-left
            q2 = image_data[:h_mid, w_mid:]  # Top-right
            q3 = image_data[h_mid:, :w_mid]  # Bottom-left
            q4 = image_data[h_mid:, w_mid:]  # Bottom-right
            
            quadrant_means = [float(np.mean(q)) for q in [q1, q2, q3, q4]]
            quadrant_uniformity = float(np.std(quadrant_means))
            
            # Calculate vignetting indicator (center vs corner brightness)
            center_region = image_data[h//4:3*h//4, w//4:3*w//4]
            corner_regions = [
                image_data[:h//4, :w//4],  # Top-left corner
                image_data[:h//4, 3*w//4:],  # Top-right corner
                image_data[3*h//4:, :w//4],  # Bottom-left corner
                image_data[3*h//4:, 3*w//4:]  # Bottom-right corner
            ]
            
            center_mean = float(np.mean(center_region))
            corner_mean = float(np.mean([np.mean(corner) for corner in corner_regions]))
            
            vignetting_ratio = (center_mean / corner_mean) if corner_mean > 0 else 1.0
            
            # Overall uniformity score (0-100, higher is better)
            cv = (np.std(image_data) / np.mean(image_data) * 100) if np.mean(image_data) > 0 else 100
            uniformity_score = max(0.0, 100.0 - cv)
            
            return {
                'coefficient_variation': cv,
                'spatial_uniformity': quadrant_uniformity,
                'vignetting_ratio': vignetting_ratio,
                'uniformity_score': uniformity_score,
                'quadrant_means': quadrant_means,
                'center_corner_ratio': vignetting_ratio
            }
            
        except Exception as e:
            logger.error(f"Error analyzing uniformity: {e}")
            return {
                'coefficient_variation': 100.0,
                'spatial_uniformity': 100.0,
                'vignetting_ratio': 1.0,
                'uniformity_score': 0.0,
                'quadrant_means': [0, 0, 0, 0],
                'center_corner_ratio': 1.0
            }

    def _analyzeFWHMMetrics(self, image_data):
        """
        Analyze FWHM (Full Width at Half Maximum) for light frames.
        
        Args:
            image_data: FITS image data
            
        Returns:
            dict: FWHM analysis results
        """
        try:
            # Basic FWHM analysis (simplified implementation)
            # In a full implementation, this would use star detection and PSF fitting
            
            # For now, provide a basic estimate based on image characteristics
            mean_value = np.mean(image_data)
            std_value = np.std(image_data)
            
            # Estimate seeing based on image noise characteristics
            # This is a placeholder - real FWHM analysis requires star detection
            estimated_fwhm = max(1.0, min(10.0, 3.0 + (std_value / mean_value) * 2))
            
            # Estimate number of stars (very basic)
            threshold = mean_value + 3 * std_value
            potential_stars = np.sum(image_data > threshold)
            estimated_star_count = min(1000, potential_stars // 100)  # Rough estimate
            
            return {
                'estimated_fwhm': estimated_fwhm,
                'estimated_star_count': estimated_star_count,
                'seeing_quality': 'Good' if estimated_fwhm < 3.0 else 'Poor',
                'fwhm_score': max(0, 100 - (estimated_fwhm - 1.5) * 20)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing FWHM: {e}")
            return {
                'estimated_fwhm': 5.0,
                'estimated_star_count': 0,
                'seeing_quality': 'Unknown',
                'fwhm_score': 50
            }

    def _analyzeAcquisitionQuality(self, header, frame_type):
        """
        Analyze acquisition quality based on FITS header information.
        
        Args:
            header: FITS header
            frame_type: Type of frame
            
        Returns:
            dict: Acquisition quality metrics
        """
        try:
            quality_indicators = {}
            
            # Temperature stability (for all frames)
            ccd_temp = header.get('CCD-TEMP', header.get('SET-TEMP'))
            if ccd_temp is not None:
                quality_indicators['temperature_stable'] = abs(float(ccd_temp)) < 50  # Reasonable range
                quality_indicators['ccd_temp'] = float(ccd_temp)
            
            # Exposure time validation
            exptime = header.get('EXPTIME', header.get('EXPOSURE', 0))
            if frame_type == 'light':
                quality_indicators['exposure_adequate'] = exptime > 10  # At least 10 seconds for lights
            elif frame_type == 'bias':
                quality_indicators['exposure_adequate'] = exptime < 0.01  # Very short for bias
            else:
                quality_indicators['exposure_adequate'] = exptime > 0
            
            quality_indicators['exposure_time'] = float(exptime)
            
            # Binning check
            xbin = header.get('XBINNING', 1)
            ybin = header.get('YBINNING', 1)
            quality_indicators['binning_consistent'] = (xbin == ybin)
            quality_indicators['binning'] = f"{xbin}x{ybin}"
            
            # Gain setting
            gain = header.get('GAIN')
            if gain is not None:
                quality_indicators['gain_reasonable'] = 0 < float(gain) < 1000
                quality_indicators['gain'] = float(gain)
            
            # Calculate overall acquisition score
            score = 0
            max_score = 0
            
            for key, value in quality_indicators.items():
                if isinstance(value, bool):
                    score += 25 if value else 0
                    max_score += 25
            
            quality_indicators['acquisition_score'] = (score / max_score * 100) if max_score > 0 else 50
            
            return quality_indicators
            
        except Exception as e:
            logger.error(f"Error analyzing acquisition quality: {e}")
            return {'acquisition_score': 50}

    def _calculateOverallQualityScore(self, results, frame_type):
        """
        Calculate overall quality score from individual metrics.
        
        Args:
            results: Dictionary containing all analysis results
            frame_type: Type of frame being analyzed
            
        Returns:
            float: Overall quality score (0-100)
        """
        try:
            # Weight factors for different aspects
            if frame_type == "light":
                # For light frames: FWHM is most important, then noise, then acquisition
                weights = {
                    "fwhm": 0.4,
                    "noise": 0.3,
                    "acquisition": 0.3
                }
            else:
                # For calibration frames: uniformity and noise are most important
                weights = {
                    "uniformity": 0.4,
                    "noise": 0.4,
                    "acquisition": 0.2
                }
            
            scores = []
            
            # Noise score (applies to all frame types)
            noise_score = results.get("noise_metrics", {}).get("noise_score", 0)
            scores.append(noise_score * weights.get("noise", 0.3))
            
            # Frame-type specific scores
            if frame_type == "light":
                fwhm_score = results.get("fwhm_metrics", {}).get("fwhm_score", 50)
                scores.append(fwhm_score * weights.get("fwhm", 0.4))
            else:
                uniformity_score = results.get("uniformity_metrics", {}).get("uniformity_score", 50)
                scores.append(uniformity_score * weights.get("uniformity", 0.4))
            
            # Acquisition score
            acquisition_score = results.get("acquisition_quality", {}).get("acquisition_score", 50)
            scores.append(acquisition_score * weights.get("acquisition", 0.2))
            
            overall_score = sum(scores)
            return max(0.0, min(100.0, overall_score))
            
        except Exception as e:
            logger.error(f"Error calculating overall quality score: {e}")
            return 50.0

    def _getQualityCategory(self, overall_score):
        """
        Get quality category based on overall score.
        
        Args:
            overall_score: Overall quality score (0-100)
            
        Returns:
            str: Quality category
        """
        if overall_score >= 90:
            return "Excellent"
        elif overall_score >= 75:
            return "Good"
        elif overall_score >= 60:
            return "Acceptable"
        elif overall_score >= 40:
            return "Poor"
        else:
            return "Unusable"

    def _generateRecommendations(self, results, frame_type):
        """
        Generate quality improvement recommendations.
        
        Args:
            results: Dictionary containing all analysis results
            frame_type: Type of frame
            
        Returns:
            list: List of recommendation strings
        """
        recommendations = []
        
        try:
            overall_score = results.get("overall_score", 50)
            
            # General recommendations based on overall score
            if overall_score < 40:
                recommendations.append("Poor quality detected. Consider reacquiring frames.")
            elif overall_score < 60:
                recommendations.append("Moderate quality. May benefit from better conditions or longer exposures.")
            elif overall_score >= 90:
                recommendations.append("Excellent quality frame suitable for high-quality processing.")
            
            # Noise-specific recommendations
            noise_metrics = results.get("noise_metrics", {})
            if noise_metrics.get("hot_pixels_percent", 0) > 1.0:
                recommendations.append("High hot pixel count detected. Check CCD cooling and consider dark subtraction.")
            
            if noise_metrics.get("snr", 0) < 10:
                recommendations.append("Low signal-to-noise ratio. Consider longer exposures or better conditions.")
            
            # Frame-type specific recommendations
            if frame_type == "light":
                fwhm_metrics = results.get("fwhm_metrics", {})
                if fwhm_metrics.get("estimated_fwhm", 5) > 4.0:
                    recommendations.append("Poor seeing detected. Consider shorter exposures or better focusing.")
                
                if fwhm_metrics.get("estimated_star_count", 0) < 10:
                    recommendations.append("Few stars detected. Check focus and field selection.")
            
            else:  # Calibration frames
                uniformity_metrics = results.get("uniformity_metrics", {})
                if uniformity_metrics.get("uniformity_score", 100) < 50:
                    recommendations.append("Poor uniformity detected. Check for dust, vignetting, or flat field issues.")
            
            if not recommendations:
                recommendations.append("Frame quality is acceptable for processing.")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Error generating recommendations"]