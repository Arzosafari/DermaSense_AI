"""PanDerm ISIC 2019 + PAD-UFES skin cancer prediction tool.

This tool wraps the new PanDermTool adapter and provides backward compatibility
with the existing SmartHealth interface.
"""
import logging
from typing import Any, Dict
from PIL.Image import Image

from app.config import settings
from app.tools.base_tool import BaseTool
from app.tools.ml.panderm_tool import PanDermTool
from app.utils.isic_classes import normalize_class_name, is_malignant

logger = logging.getLogger(__name__)


class PanDermSkinCancerTool(BaseTool):
    name = "panderm_skin_cancer_predictor"
    description = "Predicts ISIC 2019 + PAD-UFES skin lesion class using fine-tuned PanDerm Vision Transformer."

    def __init__(self):
        super().__init__()
        try:
            # Use the new PanDermTool adapter
            self.panderm_tool = PanDermTool()
            self.backend = "panderm_vit"
            logger.info("PanDermSkinCancerTool initialized with PanDerm Vision Transformer")
        except Exception as exc:
            logger.error(f"Failed to initialize PanDermTool: {exc}", exc_info=True)
            raise RuntimeError(f"PanDermTool initialization failed: {exc}")

    async def run(self, image: Image) -> Dict[str, Any]:
        """
        Run PanDerm inference with SmartHealth-compatible output format.
        
        Args:
            image: PIL Image in RGB format
            
        Returns:
            Dictionary with prediction results compatible with existing SmartHealth pipeline
        """
        if not isinstance(image, Image):
            return {"error": "Input must be a PIL Image"}
        
        try:
            # Get prediction from PanDermTool
            result = await self.panderm_tool.run(image)
            
            if "error" in result:
                return result
            
            # Normalize class names for compatibility
            predicted_class = normalize_class_name(result["predicted_class"])
            
            # Normalize top predictions
            top_predictions = [
                {
                    "class": normalize_class_name(pred["class"]),
                    "confidence": pred["probability"]
                }
                for pred in result["top_predictions"]
            ]
            
            # Normalize all scores
            all_scores = {
                normalize_class_name(class_name): score
                for class_name, score in result["all_scores"].items()
            }
            
            return {
                "predicted_class": predicted_class,
                "confidence": result["confidence"],
                "is_malignant": is_malignant(predicted_class),
                "top3_predictions": top_predictions,
                "model_backend": self.backend,
                "all_scores": all_scores,
            }
            
        except Exception as exc:
            logger.error(f"PanDermSkinCancerTool prediction failed: {exc}", exc_info=True)
            return {"error": f"Prediction failed: {exc}"}
