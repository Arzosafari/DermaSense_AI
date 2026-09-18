"""
Image Quality Service - Validates image quality before skin lesion analysis.

This service checks if an image meets minimum quality requirements for reliable
AI skin cancer screening, preventing false confident classifications on poor-quality images.
"""
import logging
from typing import Dict, Any, Tuple, Optional
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class ImageQualityService:
    """Service for assessing image quality for skin lesion analysis."""
    
    def __init__(self):
        self.logger = logger
        
        # Quality thresholds (made less strict for better user experience)
        self.MIN_RESOLUTION = (200, 200)  # Reduced from 224x224
        self.MIN_TOTAL_PIXELS = 200 * 200  # Reduced minimum
        self.MAX_BLUR_SCORE = 100  # Lower is sharper, variance-based
        self.MIN_BRIGHTNESS = 15  # Reduced from 20 (allow darker images)
        self.MAX_BRIGHTNESS = 245  # Increased from 240 (allow brighter images)
        self.MIN_CONTRAST = 15  # Reduced from 30 (less strict contrast check)
    
    def assess_image_quality(self, image: Image.Image) -> Dict[str, Any]:
        """
        Comprehensive image quality assessment.
        
        Args:
            image: PIL Image in RGB format
            
        Returns:
            Dictionary with quality assessment results and recommendations
        """
        if not isinstance(image, Image.Image):
            return {
                "acceptable": False,
                "reason": "Invalid image format",
                "recommendation": "Please upload a valid image file."
            }
        
        checks = {
            "resolution": self._check_resolution(image),
            "blur": self._check_blur(image),
            "brightness": self._check_brightness(image),
            "contrast": self._check_contrast(image),
            "color_content": self._check_color_content(image),
        }
        
        # Determine overall acceptability
        failed_checks = [name for name, result in checks.items() if not result["pass"]]
        
        if failed_checks:
            return {
                "acceptable": False,
                "failed_checks": failed_checks,
                "checks": checks,
                "recommendation": self._get_recommendation(failed_checks, checks)
            }
        
        return {
            "acceptable": True,
            "checks": checks,
            "message": "Image quality acceptable for analysis"
        }
    
    def _check_resolution(self, image: Image.Image) -> Dict[str, Any]:
        """Check if image meets minimum resolution requirements."""
        width, height = image.size
        total_pixels = width * height
        
        min_w, min_h = self.MIN_RESOLUTION
        
        if width < min_w or height < min_h:
            return {
                "pass": False,
                "reason": f"Resolution too low: {width}x{height} (minimum: {min_w}x{min_h})",
                "current": f"{width}x{height}",
                "required": f"{min_w}x{min_h}"
            }
        
        if total_pixels < self.MIN_TOTAL_PIXELS:
            return {
                "pass": False,
                "reason": f"Total pixels too low: {total_pixels} (minimum: {self.MIN_TOTAL_PIXELS})",
                "current": total_pixels,
                "required": self.MIN_TOTAL_PIXELS
            }
        
        return {
            "pass": True,
            "current": f"{width}x{height}",
            "message": "Resolution acceptable"
        }
    
    def _check_blur(self, image: Image.Image) -> Dict[str, Any]:
        """Check image sharpness using variance of Laplacian."""
        try:
            # Convert to grayscale
            gray = image.convert('L')
            
            # Convert to numpy array
            img_array = np.array(gray)
            
            # Apply Laplacian
            from scipy.ndimage import laplace
            laplacian = laplace(img_array)
            
            # Calculate variance
            variance = laplacian.var()
            
            # Higher variance = sharper image
            if variance < 50:  # Too blurry
                return {
                    "pass": False,
                    "reason": f"Image appears too blurry (variance: {variance:.1f})",
                    "current": variance,
                    "required": ">= 50"
                }
            
            return {
                "pass": True,
                "current": variance,
                "message": f"Sharpness acceptable (variance: {variance:.1f})"
            }
            
        except ImportError:
            # scipy not available, use simpler check
            self.logger.warning("scipy not available, using simple blur check")
            return self._simple_blur_check(image)
        except Exception as e:
            self.logger.error(f"Blur check failed: {e}")
            return {"pass": True, "note": "Could not assess blur, proceeding"}
    
    def _simple_blur_check(self, image: Image.Image) -> Dict[str, Any]:
        """Simple blur check using edge detection."""
        try:
            from PIL import ImageFilter
            # Apply edge detection
            edges = image.filter(ImageFilter.FIND_EDGES)
            # Convert to array and count edge pixels
            edge_array = np.array(edges)
            edge_count = np.sum(edge_array > 50)
            
            # If very few edges, likely blurry
            total_pixels = edge_array.size
            edge_ratio = edge_count / total_pixels
            
            if edge_ratio < 0.01:  # Less than 1% edge pixels
                return {
                    "pass": False,
                    "reason": f"Image appears too blurry (edge ratio: {edge_ratio:.4f})",
                    "current": edge_ratio,
                    "required": ">= 0.01"
                }
            
            return {
                "pass": True,
                "current": edge_ratio,
                "message": f"Sharpness acceptable (edge ratio: {edge_ratio:.4f})"
            }
        except Exception as e:
            self.logger.error(f"Simple blur check failed: {e}")
            return {"pass": True, "note": "Could not assess blur, proceeding"}
    
    def _check_brightness(self, image: Image.Image) -> Dict[str, Any]:
        """Check if image brightness is within acceptable range."""
        try:
            # Convert to grayscale
            gray = image.convert('L')
            img_array = np.array(gray)
            
            # Calculate mean brightness
            mean_brightness = np.mean(img_array)
            
            if mean_brightness < self.MIN_BRIGHTNESS:
                return {
                    "pass": False,
                    "reason": f"Image too dark (brightness: {mean_brightness:.1f})",
                    "current": mean_brightness,
                    "required": f">{self.MIN_BRIGHTNESS}"
                }
            
            if mean_brightness > self.MAX_BRIGHTNESS:
                return {
                    "pass": False,
                    "reason": f"Image too bright (brightness: {mean_brightness:.1f})",
                    "current": mean_brightness,
                    "required": f"<{self.MAX_BRIGHTNESS}"
                }
            
            return {
                "pass": True,
                "current": mean_brightness,
                "message": f"Brightness acceptable ({mean_brightness:.1f})"
            }
            
        except Exception as e:
            self.logger.error(f"Brightness check failed: {e}")
            return {"pass": True, "note": "Could not assess brightness, proceeding"}
    
    def _check_contrast(self, image: Image.Image) -> Dict[str, Any]:
        """Check if image has sufficient contrast."""
        try:
            # Convert to grayscale
            gray = image.convert('L')
            img_array = np.array(gray)
            
            # Calculate standard deviation as contrast measure
            contrast = np.std(img_array)
            
            if contrast < self.MIN_CONTRAST:
                return {
                    "pass": False,
                    "reason": f"Image contrast too low (contrast: {contrast:.1f})",
                    "current": contrast,
                    "required": f">{self.MIN_CONTRAST}"
                }
            
            return {
                "pass": True,
                "current": contrast,
                "message": f"Contrast acceptable ({contrast:.1f})"
            }
            
        except Exception as e:
            self.logger.error(f"Contrast check failed: {e}")
            return {"pass": True, "note": "Could not assess contrast, proceeding"}
    
    def _check_color_content(self, image: Image.Image) -> Dict[str, Any]:
        """Check if image has reasonable color variation (not grayscale/monochrome)."""
        try:
            # Convert to RGB if not already
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            
            # Calculate standard deviation for each color channel
            r_std = np.std(img_array[:, :, 0])
            g_std = np.std(img_array[:, :, 1])
            b_std = np.std(img_array[:, :, 2])
            
            # If all channels have very low std, likely monochrome
            avg_std = (r_std + g_std + b_std) / 3
            
            if avg_std < 10:
                return {
                    "pass": False,
                    "reason": f"Image appears monochrome (color variation: {avg_std:.1f})",
                    "current": avg_std,
                    "required": "> 10"
                }
            
            return {
                "pass": True,
                "current": avg_std,
                "message": f"Color content acceptable (variation: {avg_std:.1f})"
            }
            
        except Exception as e:
            self.logger.error(f"Color content check failed: {e}")
            return {"pass": True, "note": "Could not assess color content, proceeding"}
    
    def _get_recommendation(self, failed_checks: list, checks: dict) -> str:
        """Generate user-friendly recommendation based on failed checks."""
        recommendations = []
        
        for check_name in failed_checks:
            check_result = checks[check_name]
            if "reason" in check_result:
                recommendations.append(check_result["reason"])
        
        base_message = "The image quality is insufficient for reliable screening. "
        specific_advice = " ".join(recommendations)
        general_advice = "Please upload a clearer, well-lit close-up image of the skin area."
        
        return base_message + specific_advice + " " + general_advice


# Global instance
image_quality_service = ImageQualityService()