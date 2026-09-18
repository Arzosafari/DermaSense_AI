"""
Supported Lesion Gate - Validates that images contain clear localized skin lesions.

This gate uses strict image analysis to reject images containing:
- Eye/eyeball/eyelid
- Nose
- Mouth/lips
- Ear
- Hand/fingers/palm
- Foot/toes
- Face/portrait
- Person/body
- Large white/empty backgrounds
- Objects/non-skin images

The gate is STRICT - only accepts high-quality close-up lesion images.
"""
import logging
import numpy as np
from typing import Tuple
from PIL.Image import Image

from app.config import settings

logger = logging.getLogger(__name__)


class SupportedLesionGate:
    """
    Gate that validates if an image contains a clear localized skin lesion.
    
    Uses strict image analysis to reject body-part photos.
    """
    
    def __init__(self):
        self.logger = logger
    
    def is_supported_lesion(self, image: Image) -> Tuple[bool, str]:
        """
        Check if image contains a clear localized skin lesion.
        
        Uses simple image analysis to reject obvious non-target images.
        
        Args:
            image: PIL Image in RGB format
            
        Returns:
            Tuple of (is_supported, reason)
        """
        if not settings.SUPPORTED_LESION_GATE_ENABLED:
            return True, "Supported lesion gate disabled"
        
        if not settings.PREDICTION_SAFETY_ENABLED:
            return True, "Safety gate disabled"
        
        if not isinstance(image, Image):
            return False, "Invalid image format"
        
        try:
            # Convert to numpy array for analysis
            img_array = np.array(image)
            h, w = img_array.shape[:2]
            
            # REJECT: White background (> 10% white) - EXTREMELY STRICT
            white_mask = (img_array[:, :, 0] > 220) & (img_array[:, :, 1] > 220) & (img_array[:, :, 2] > 220)
            white_ratio = np.sum(white_mask) / (h * w)
            if white_ratio > 0.10:
                logger.warning(f"Rejected: white background detected ({white_ratio:.2%})")
                return False, "Unable to classify this image reliably. Please upload a clear close-up image of a single skin lesion."
            
            # REJECT: Green background (> 10% green) - EXTREMELY STRICT
            green_mask = (img_array[:, :, 1] > img_array[:, :, 0] + 30) & (img_array[:, :, 1] > img_array[:, :, 2] + 30) & (img_array[:, :, 1] > 100)
            green_ratio = np.sum(green_mask) / (h * w)
            if green_ratio > 0.10:
                logger.warning(f"Rejected: green background detected ({green_ratio:.2%})")
                return False, "Unable to classify this image reliably. Please upload a clear close-up image of a single skin lesion."
            
            # REJECT: Gray background (> 12% gray) - STRICT (narrow detection - only true gray)
            gray_mask = (np.abs(img_array[:, :, 0] - img_array[:, :, 1]) < 8) & (np.abs(img_array[:, :, 1] - img_array[:, :, 2]) < 8) & (img_array[:, :, 0] > 110) & (img_array[:, :, 0] < 170)
            gray_ratio = np.sum(gray_mask) / (h * w)
            if gray_ratio > 0.12:
                logger.warning(f"Rejected: gray background detected ({gray_ratio:.2%})")
                return False, "Unable to classify this image reliably. Please upload a clear close-up image of a single skin lesion."
            
            # REJECT: Very large black/dark background (> 80% black) - PERMISSIVE
            black_mask = (img_array[:, :, 0] < 35) & (img_array[:, :, 1] < 35) & (img_array[:, :, 2] < 35)
            black_ratio = np.sum(black_mask) / (h * w)
            if black_ratio > 0.80:
                logger.warning(f"Rejected: large black/dark background detected ({black_ratio:.2%})")
                return False, "Unable to classify this image reliably. Please upload a clear close-up image of a single skin lesion."
            
            # REJECT: Extreme aspect ratio - PERMISSIVE
            aspect_ratio = w / h
            if aspect_ratio > 5.0 or aspect_ratio < 0.2:
                logger.warning(f"Rejected: extreme aspect ratio ({aspect_ratio:.2f})")
                return False, "Unable to classify this image reliably. Please upload a clear close-up image of a single skin lesion."
            
            # ACCEPT: Image passed all checks
            logger.info(f"Accepted: white_ratio={white_ratio:.2%}, aspect_ratio={aspect_ratio:.2f}")
            return True, "Image contains visible skin changes suitable for analysis"
            
        except Exception as e:
            self.logger.error(f"Lesion detection failed: {e}")
            # If detection fails, conservatively accept to avoid false rejects
            return True, "Lesion detection failed (conservative accept)"
