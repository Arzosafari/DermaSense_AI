"""
Heatmap/Explainability Service - Generates visual explanations for model predictions.

This service attempts to create attention heatmaps to show which regions of the image
most influenced the model's prediction. This is for educational purposes only and should
not be presented as diagnostic evidence.
"""
import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple
from PIL import Image
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class HeatmapService:
    """Service for generating attention heatmaps for model explainability."""
    
    def __init__(self):
        self.logger = logger
        self.available = False
        self.vit_attention_available = False
    
    def is_available(self) -> bool:
        """Check if heatmap generation is available (requires model access)."""
        return self.available
    
    def generate_attention_heatmap(
        self, 
        model: torch.nn.Module,
        image_tensor: torch.Tensor,
        predicted_class: int,
        device: str = "cpu"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate attention heatmap using Grad-CAM or attention rollouts.
        
        Args:
            model: The neural network model
            image_tensor: Preprocessed image tensor
            predicted_class: The predicted class index
            device: Device to run computation on
            
        Returns:
            Dictionary with heatmap data or None if not available
        """
        try:
            # Try to use Grad-CAM for CNNs or attention extraction for ViTs
            if self._is_vision_transformer(model):
                return self._extract_vit_attention(model, image_tensor, predicted_class, device)
            else:
                return self._generate_gradcam(model, image_tensor, predicted_class, device)
        except Exception as e:
            logger.warning(f"Heatmap generation failed: {e}")
            return None
    
    def _is_vision_transformer(self, model: torch.nn.Module) -> bool:
        """Check if model is a Vision Transformer."""
        # Heuristic check for ViT architecture
        model_str = str(model).lower()
        return any(keyword in model_str for keyword in ["transformer", "vit", "attention", "encoder"])
    
    def _extract_vit_attention(
        self, 
        model: torch.nn.Module, 
        image_tensor: torch.Tensor, 
        predicted_class: int,
        device: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract attention maps from Vision Transformer.
        
        Note: This requires the model to expose attention weights.
        Many ViT implementations don't easily expose this, so this may fail.
        """
        try:
            # This is a simplified approach - actual implementation depends on model architecture
            # For many ViTs, we need to hook into the attention layers
            
            logger.info("Attempting to extract ViT attention maps...")
            
            # For now, return a placeholder indicating ViT attention extraction
            # would require model-specific hooks
            return {
                "available": False,
                "reason": "ViT attention extraction requires model-specific hooks not currently implemented",
                "suggestion": "Consider using a CNN-based model for Grad-CAM or implement ViT-specific attention rollout"
            }
            
        except Exception as e:
            logger.error(f"ViT attention extraction failed: {e}")
            return None
    
    def _generate_gradcam(
        self, 
        model: torch.nn.Module, 
        image_tensor: torch.Tensor, 
        predicted_class: int,
        device: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate Grad-CAM heatmap for CNN models.
        
        Note: This requires finding the last convolutional layer and hooking into it.
        """
        try:
            logger.info("Attempting to generate Grad-CAM heatmap...")
            
            # Find the last convolutional layer
            target_layer = None
            for name, module in reversed(list(model.named_modules())):
                if isinstance(module, torch.nn.Conv2d):
                    target_layer = module
                    target_layer_name = name
                    break
            
            if target_layer is None:
                return {
                    "available": False,
                    "reason": "No convolutional layer found for Grad-CAM",
                    "suggestion": "Grad-CAM requires CNN architecture with conv layers"
                }
            
            # Hook for gradients
            gradients = []
            activations = []
            
            def forward_hook(module, input, output):
                activations.append(output)
            
            def backward_hook(module, grad_input, grad_output):
                gradients.append(grad_output[0])
            
            # Register hooks
            forward_handle = target_layer.register_forward_hook(forward_hook)
            backward_handle = target_layer.register_backward_hook(backward_hook)
            
            try:
                # Forward pass
                model.eval()
                output = model(image_tensor)
                
                # Backward pass for predicted class
                model.zero_grad()
                output[0, predicted_class].backward()
                
                # Get gradients and activations
                if gradients and activations:
                    grads = gradients[0]
                    acts = activations[0]
                    
                    # Global average pooling of gradients
                    weights = torch.mean(grads, dim=(2, 3), keepdim=True)
                    
                    # Weighted combination of activation maps
                    cam = torch.sum(weights * acts, dim=1, keepdim=True)
                    cam = F.relu(cam)
                    
                    # Resize to input size
                    cam = F.interpolate(cam, size=(224, 224), mode='bilinear', align_corners=False)
                    
                    # Normalize
                    cam = cam.squeeze().cpu().numpy()
                    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
                    
                    return {
                        "available": True,
                        "heatmap": cam.tolist(),
                        "method": "Grad-CAM",
                        "target_layer": target_layer_name,
                        "disclaimer": "This heatmap shows regions that influenced the model's prediction. It is not a diagnostic map."
                    }
                
            finally:
                # Remove hooks
                forward_handle.remove()
                backward_handle.remove()
            
            return {
                "available": False,
                "reason": "Grad-CAM generation failed during computation"
            }
            
        except Exception as e:
            logger.error(f"Grad-CAM generation failed: {e}")
            return None
    
    def create_overlay_image(
        self, 
        original_image: Image.Image, 
        heatmap_data: list,
        alpha: float = 0.4
    ) -> Optional[Image.Image]:
        """
        Create an overlay image with heatmap on top of original.
        
        Args:
            original_image: Original PIL Image
            heatmap_data: Heatmap data as 2D list
            alpha: Transparency of heatmap overlay (0-1)
            
        Returns:
            PIL Image with heatmap overlay or None if failed
        """
        try:
            # Convert heatmap to numpy array
            heatmap = np.array(heatmap_data)
            
            # Normalize to 0-255
            heatmap = (heatmap * 255).astype(np.uint8)
            
            # Apply colormap (using PIL for simplicity)
            heatmap_image = Image.fromarray(heatmap, mode='L')
            heatmap_image = heatmap_image.convert('RGB')
            
            # Resize heatmap to match original image
            heatmap_image = heatmap_image.resize(original_image.size)
            
            # Create overlay
            overlay = Image.blend(original_image, heatmap_image, alpha)
            
            return overlay
            
        except Exception as e:
            logger.error(f"Overlay creation failed: {e}")
            return None
    
    def get_explainability_disclaimer(self) -> str:
        """Get standard disclaimer for heatmap/explainability features."""
        return (
            "The highlighted regions show areas that most influenced the model's prediction. "
            "This is for educational purposes only and is not a clinical diagnostic map. "
            "It does not prove the presence or absence of cancer."
        )


# Global instance
heatmap_service = HeatmapService()