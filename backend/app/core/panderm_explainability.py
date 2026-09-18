"""
PanDerm Explainability Service

Generates class-specific gradient-based visualizations for PanDerm Vision Transformer predictions.
Uses Grad-CAM style attribution with proper spatial alignment for preprocessing pipeline.
"""
import logging
import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
import cv2

logger = logging.getLogger(__name__)


class PanDermExplainability:
    """
    Generates class-specific explainability visualizations for PanDerm Vision Transformer.
    
    Uses gradient-based attribution with proper handling of the preprocessing pipeline
    (Resize 256 → CenterCrop 224) to ensure spatial alignment.
    """
    
    def __init__(self, model: nn.Module, device: str = "cpu"):
        """
        Initialize explainability service.
        
        Args:
            model: Loaded PanDerm model
            device: Device the model is on
        """
        self.model = model
        self.device = device
        
        # PanDerm architecture parameters
        self.img_size = 224
        self.pre_resize_size = 256  # PanDerm resizes to 256 before center cropping to 224
        self.patch_size = 16
        self.embed_dim = 768
        self.depth = 12
        self.num_heads = 12
        self.patch_grid = (self.img_size // self.patch_size, self.img_size // self.patch_size)  # (14, 14)
        self.num_patches = self.patch_grid[0] * self.patch_grid[1]  # 196
        
        logger.info("PanDermExplainability initialized for class-specific gradient attribution")
    
    def _get_gradient_attribution(
        self, 
        tensor: torch.Tensor, 
        predicted_class_idx: int
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Compute gradient-based attribution for the target class using Grad-CAM style approach.
        
        Captures feature maps from the final transformer block and computes gradients
        with respect to the target class logit.
        
        Args:
            tensor: Input tensor (1, 3, 224, 224) - already preprocessed
            predicted_class_idx: Index of the predicted class to explain
            
        Returns:
            Tuple of (patch attribution array, debug info dict)
        """
        debug_info = {}
        
        # Hook to capture feature maps and gradients
        feature_maps = []
        gradients = []
        
        def forward_hook(module, input, output):
            # output shape: (1, 197, 768) where 197 = 1 CLS + 196 patches
            feature_maps.append(output)
        
        def backward_hook(module, grad_input, grad_output):
            # grad_output[0] shape: (1, 197, 768)
            gradients.append(grad_output[0])
        
        # Register hooks on the final norm layer (before classification head)
        forward_hook_handle = self.model.norm.register_forward_hook(forward_hook)
        backward_hook_handle = self.model.norm.register_full_backward_hook(backward_hook)
        
        # Enable gradient computation
        tensor.requires_grad_(True)
        
        # Forward pass
        outputs = self.model(tensor)
        
        # Get the logit for the target class
        target_logit = outputs[0, predicted_class_idx]
        
        debug_info["target_logit"] = target_logit.item()
        debug_info["all_logits"] = outputs[0].detach().cpu().numpy()
        
        # Backward pass to get gradients
        self.model.zero_grad()
        target_logit.backward(retain_graph=True)
        
        # Remove hooks
        forward_hook_handle.remove()
        backward_hook_handle.remove()
        
        # Get feature map and gradients
        if not feature_maps or not gradients:
            raise ValueError("Failed to capture feature maps or gradients")
        
        feature_map = feature_maps[0]  # (1, 197, 768)
        grad = gradients[0]  # (1, 197, 768)
        
        # Compute improved Grad-CAM: gradient * activation
        # Use only spatial tokens (skip CLS token at index 0)
        spatial_features = feature_map[0, 1:, :]  # (196, 768)
        spatial_grads = grad[0, 1:, :]  # (196, 768)
        
        # Improved weight computation using Grad-CAM++ style
        # This better captures the importance of features for prominent lesions
        # Take absolute gradients to capture both positive and negative contributions
        grad_abs = torch.abs(spatial_grads)
        
        # Compute weights using weighted average (emphasize larger gradients)
        # This helps focus on salient features like prominent lesions
        weights = (grad_abs * spatial_features).sum(dim=0) / (grad_abs.sum(dim=0) + 1e-8)  # (768,)
        
        # Weighted sum of feature maps
        attribution = (spatial_features * weights.unsqueeze(0)).sum(dim=1)  # (196,)
        
        # Apply ReLU to keep only positive contributions
        attribution = F.relu(attribution)
        
        # Additional refinement: emphasize higher attribution values
        # This helps focus on the most salient regions
        attribution = attribution * (attribution / (attribution.max() + 1e-8))
        
        # Disable gradients
        tensor.requires_grad_(False)
        
        debug_info["feature_map_shape"] = feature_map.shape
        debug_info["grad_shape"] = grad.shape
        debug_info["spatial_features_shape"] = spatial_features.shape
        debug_info["attribution_shape"] = attribution.shape
        debug_info["attribution_min"] = attribution.min().item()
        debug_info["attribution_max"] = attribution.max().item()
        
        return attribution.detach().cpu().numpy(), debug_info
    
    def _gradients_to_patch_attribution(
        self, 
        attribution: np.ndarray
    ) -> np.ndarray:
        """
        Convert attribution array to patch-level heatmap.
        
        Improved with mild smoothing to reduce noise while preserving important features.
        
        Args:
            attribution: Attribution array (196,)
            
        Returns:
            Patch-level attribution (14, 14)
        """
        # Reshape the 196 spatial tokens to 14x14 grid
        h, w = self.patch_grid
        patch_attribution = attribution.reshape(h, w)
        
        # Apply mild Gaussian smoothing to reduce noise
        # This helps reduce scattered attention while preserving main features
        patch_attribution_smoothed = cv2.GaussianBlur(
            patch_attribution.astype(np.float32), 
            (3, 3), 
            sigmaX=0.7
        )
        
        return patch_attribution_smoothed
    
    def _normalize_attribution(self, attribution: np.ndarray) -> np.ndarray:
        """
        Normalize attribution map to [0, 1] range with robust handling.
        
        Improved normalization to better focus on salient regions like prominent lesions.
        
        Args:
            attribution: Raw attribution map
            
        Returns:
            Normalized attribution map
        """
        # Handle edge cases
        if np.isnan(attribution).any() or np.isinf(attribution).any():
            attribution = np.nan_to_num(attribution, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Use tighter percentile range for better focus on important regions
        # Changed from [1, 99] to [5, 95] to reduce noise and focus on salient features
        p5, p95 = np.percentile(attribution, [5, 95])
        
        if p95 - p5 < 1e-8:
            # All values are the same
            logger.warning("Attribution map has uniform values, returning uniform heatmap")
            return np.ones_like(attribution) * 0.5
        
        # Clip to percentile range then normalize
        attribution_clipped = np.clip(attribution, p5, p95)
        normalized = (attribution_clipped - p5) / (p95 - p5)
        
        # Apply mild sharpening to emphasize high-value regions
        # This helps focus on the most important patches
        normalized = normalized ** 1.2  # Slight power transformation
        
        return normalized
    
    def _generate_colored_heatmap(self, attribution: np.ndarray) -> np.ndarray:
        """
        Convert attribution to colored heatmap using jet colormap.
        
        Improved to better highlight salient regions and reduce noise.
        
        Args:
            attribution: Normalized attribution (14, 14)
            
        Returns:
            Colored heatmap (14, 14, 3) in RGB
        """
        # Use jet colormap (blue -> green -> yellow -> red)
        colormap = cv2.COLORMAP_JET
        
        # Convert to 0-255 range with enhanced contrast
        attribution_enhanced = np.clip(attribution * 280, 0, 255).astype(np.uint8)
        
        # Apply colormap
        heatmap_colored = cv2.applyColorMap(attribution_enhanced, colormap)
        
        # Convert BGR to RGB
        heatmap_rgb = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
        
        return heatmap_rgb
    
    def _reverse_preprocessing(
        self, 
        heatmap_224: np.ndarray, 
        original_image: Image
    ) -> np.ndarray:
        """
        Reverse the preprocessing pipeline to map heatmap back to original image coordinates.
        
        PanDerm preprocessing: Original → Resize(shorter_side=256) → CenterCrop(224) → Tensor
        
        IMPORTANT: transforms.Resize(256) resizes the SHORTER side to 256, preserving aspect ratio.
        This means the intermediate image is NOT always 256x256 - it depends on original aspect ratio.
        
        To reverse: Heatmap(224) → Resize directly to original dimensions (without padding)
        
        The key insight is that the 224x224 heatmap represents the attribution for the central
        cropped region. Instead of padding and then resizing, we directly resize the heatmap
        to the original image dimensions. This spreads the heatmap across the full image while
        maintaining the relative attribution pattern.
        
        Args:
            heatmap_224: Heatmap at 224x224 resolution
            original_image: Original PIL Image
            
        Returns:
            Heatmap at original image resolution
        """
        original_w, original_h = original_image.size  # (width, height)
        
        logger.info(f"Original size: {original_w}x{original_h}")
        logger.info(f"Heatmap input size: {heatmap_224.shape[:2][::-1]}")
        
        # Direct resize from 224x224 to original dimensions
        # This spreads the heatmap across the full original image
        heatmap_original = cv2.resize(
            heatmap_224, 
            (original_w, original_h), 
            interpolation=cv2.INTER_LINEAR
        )
        
        logger.info(f"Final heatmap size: {heatmap_original.shape[:2][::-1]}")
        
        return heatmap_original
    
    def _generate_overlay(
        self, 
        original_image: Image, 
        heatmap: np.ndarray, 
        alpha: float = 0.4
    ) -> np.ndarray:
        """
        Generate overlay of heatmap on original image.
        
        Args:
            original_image: PIL Image
            heatmap: Colored heatmap (height, width, 3)
            alpha: Transparency of heatmap
            
        Returns:
            Overlay image as numpy array
        """
        # Convert original image to numpy
        original_np = np.array(original_image)
        
        # Ensure heatmap is same size as original
        if heatmap.shape[:2] != original_np.shape[:2]:
            heatmap = cv2.resize(heatmap, (original_np.shape[1], original_np.shape[0]))
        
        # Blend
        overlay = (original_np * (1 - alpha) + heatmap * alpha).astype(np.uint8)
        
        return overlay
    
    def _save_debug_visualizations(
        self,
        original_image: Image,
        attribution_14x14: np.ndarray,
        heatmap_224: np.ndarray,
        heatmap_original: np.ndarray,
        output_dir: str,
        analysis_id: str,
        argmax_patch_idx: int = None,
        argmax_patch_row: int = None,
        argmax_patch_col: int = None,
        argmax_original_x: int = None,
        argmax_original_y: int = None
    ):
        """
        Save debug visualizations to verify spatial transformations.
        
        Args:
            original_image: Original PIL Image
            attribution_14x14: 14x14 attribution map
            heatmap_224: 224x224 heatmap
            heatmap_original: Original-sized heatmap
            output_dir: Output directory
            analysis_id: Unique identifier
        """
        from torchvision import transforms
        
        # Apply the same preprocessing as PanDerm
        crop_pct = 224 / 256
        size = int(224 / crop_pct)
        transform = transforms.Compose([
            transforms.Resize(size, interpolation=3),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        
        # Step 1: Visualize original with center crop rectangle
        # We need to show which region of the ORIGINAL image ends up in the 224x224 input
        orig_np = np.array(original_image)
        orig_h, orig_w = orig_np.shape[:2]
        
        # Calculate the actual preprocessing pipeline
        # transforms.Resize(256) resizes shorter side to 256
        if orig_w >= orig_h:
            resized_h = 256
            resized_w = int(orig_w * (256 / orig_h))
        else:
            resized_w = 256
            resized_h = int(orig_h * (256 / orig_w))
        
        # Calculate which region of the resized image is center-cropped to 224x224
        crop_x1 = (resized_w - 224) // 2
        crop_y1 = (resized_h - 224) // 2
        crop_x2 = crop_x1 + 224
        crop_y2 = crop_y1 + 224
        
        # Map these coordinates back to the original image
        scale_x = orig_w / resized_w
        scale_y = orig_h / resized_h
        
        orig_x1 = int(crop_x1 * scale_x)
        orig_y1 = int(crop_y1 * scale_y)
        orig_x2 = int(crop_x2 * scale_x)
        orig_y2 = int(crop_y2 * scale_y)
        
        logger.info(f"Original image: {orig_w}x{orig_h}")
        logger.info(f"After Resize(256): {resized_w}x{resized_h}")
        logger.info(f"CenterCrop(224) region in resized: ({crop_x1},{crop_y1}) to ({crop_x2},{crop_y2})")
        logger.info(f"Mapped to original: ({orig_x1},{orig_y1}) to ({orig_x2},{orig_y2})")
        
        orig_with_crop = orig_np.copy()
        cv2.rectangle(orig_with_crop, (orig_x1, orig_y1), (orig_x2, orig_y2), (0, 255, 0), 2)
        crop_path = os.path.join(output_dir, f"{analysis_id}_debug_original_with_crop.png")
        Image.fromarray(orig_with_crop).save(crop_path)
        
        # Step 2: Visualize the 224x224 input with patch grid
        transformed = transforms.Compose([
            transforms.Resize(size, interpolation=3),
            transforms.CenterCrop(224),
        ])(original_image)
        transformed_np = np.array(transformed)
        
        # Draw 14x14 patch grid
        patch_h = 224 // 14
        patch_w = 224 // 14
        
        for i in range(1, 14):
            cv2.line(transformed_np, (0, i * patch_h), (224, i * patch_h), (0, 255, 0), 1)
            cv2.line(transformed_np, (i * patch_w, 0), (i * patch_w, 224), (0, 255, 0), 1)
        
        # Add patch numbers
        for i in range(14):
            for j in range(14):
                patch_num = i * 14 + j
                cv2.putText(transformed_np, str(patch_num), (j * patch_w + 5, i * patch_h + 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)
        
        grid_path = os.path.join(output_dir, f"{analysis_id}_debug_224_grid.png")
        Image.fromarray(transformed_np).save(grid_path)
        
        # Step 3: Visualize 14x14 attribution
        attribution_colored = self._generate_colored_heatmap(attribution_14x14)
        attribution_path = os.path.join(output_dir, f"{analysis_id}_debug_14x14_attribution.png")
        Image.fromarray(attribution_colored).save(attribution_path)
        
        # Step 4: Visualize 224x224 attribution
        heatmap_224_path = os.path.join(output_dir, f"{analysis_id}_debug_224_heatmap.png")
        Image.fromarray(heatmap_224).save(heatmap_224_path)
        
        # Step 5: Visualize heatmap at original dimensions (direct resize from 224)
        # This matches the new _reverse_preprocessing logic
        heatmap_original_debug = cv2.resize(
            heatmap_224, 
            (orig_w, orig_h), 
            interpolation=cv2.INTER_LINEAR
        )
        
        heatmap_original_debug_path = os.path.join(output_dir, f"{analysis_id}_debug_original_heatmap.png")
        Image.fromarray(heatmap_original_debug).save(heatmap_original_debug_path)
        
        # Step 7: Visualize final overlay with argmax marker
        if argmax_original_x is not None and argmax_original_y is not None:
            overlay_with_marker = orig_np.copy()
            # Draw a red circle at the argmax location
            cv2.circle(overlay_with_marker, (argmax_original_x, argmax_original_y), 10, (0, 0, 255), 2)
            # Draw a cross
            cv2.line(overlay_with_marker, (argmax_original_x - 15, argmax_original_y), (argmax_original_x + 15, argmax_original_y), (0, 0, 255), 2)
            cv2.line(overlay_with_marker, (argmax_original_x, argmax_original_y - 15), (argmax_original_x, argmax_original_y + 15), (0, 0, 255), 2)
            # Add text
            cv2.putText(overlay_with_marker, f"Argmax: patch {argmax_patch_idx}", (argmax_original_x + 15, argmax_original_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            overlay_marker_path = os.path.join(output_dir, f"{analysis_id}_debug_overlay_with_marker.png")
            Image.fromarray(overlay_with_marker).save(overlay_marker_path)
            
            # Also mark the argmax patch on the 224 grid image
            transformed_np_marked = transformed_np.copy()
            patch_h_marked = 224 // 14
            patch_w_marked = 224 // 14
            
            # Highlight the argmax patch
            argmax_224_x1 = argmax_patch_col * patch_w_marked
            argmax_224_y1 = argmax_patch_row * patch_h_marked
            argmax_224_x2 = argmax_224_x1 + patch_w_marked
            argmax_224_y2 = argmax_224_y1 + patch_h_marked
            
            cv2.rectangle(transformed_np_marked, (argmax_224_x1, argmax_224_y1), (argmax_224_x2, argmax_224_y2), (0, 0, 255), 3)
            cv2.putText(transformed_np_marked, f"MAX", (argmax_224_x1 + 2, argmax_224_y1 + 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
            
            grid_marker_path = os.path.join(output_dir, f"{analysis_id}_debug_224_grid_with_marker.png")
            Image.fromarray(transformed_np_marked).save(grid_marker_path)
        
        logger.info(f"Debug visualizations saved to {output_dir}")
    
    def generate_heatmap(
        self,
        image: Image,
        tensor: torch.Tensor,
        predicted_class_idx: int,
        output_dir: str,
        analysis_id: str
    ) -> Dict[str, Any]:
        """
        Generate class-specific explainability heatmap for a prediction.
        
        Args:
            image: Original PIL Image
            tensor: Preprocessed tensor for model input (1, 3, 224, 224)
            predicted_class_idx: Index of predicted class to explain
            output_dir: Directory to save output images
            analysis_id: Unique identifier for this analysis
            
        Returns:
            Dictionary with paths to generated images and availability status
        """
        try:
            # DEBUG INFORMATION
            original_size = image.size  # (width, height)
            tensor_size = tensor.shape  # (1, 3, 224, 224)
            
            logger.info("=" * 80)
            logger.info("PANDERM EXPLAINABILITY DEBUG INFO")
            logger.info("=" * 80)
            logger.info(f"Original image size: {original_size}")
            logger.info(f"Preprocessed tensor size: {tensor_size}")
            logger.info(f"Preprocessing pipeline: Original → Resize({self.pre_resize_size}) → CenterCrop({self.img_size})")
            logger.info(f"Reverse preprocessing: Heatmap(224) → Direct resize to original dimensions")
            logger.info(f"Patch size: {self.patch_size}x{self.patch_size}")
            logger.info(f"Patch grid: {self.patch_grid}")
            logger.info(f"Number of patches: {self.num_patches}")
            logger.info(f"CLS token: YES")
            logger.info(f"Mean pooling: YES")
            logger.info(f"Target class index: {predicted_class_idx}")
            logger.info("=" * 80)
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Set model to eval mode
            self.model.eval()
            
            # Compute gradient-based attribution for target class
            logger.info("Computing gradient-based attribution...")
            attribution, debug_info = self._get_gradient_attribution(tensor, predicted_class_idx)
            
            logger.info(f"Attribution computed, shape: {debug_info['attribution_shape']}")
            logger.info(f"Attribution min: {debug_info['attribution_min']:.6f}")
            logger.info(f"Attribution max: {debug_info['attribution_max']:.6f}")
            logger.info(f"Target logit: {debug_info['target_logit']:.6f}")
            
            # Convert to patch-level attribution
            patch_attribution = self._gradients_to_patch_attribution(attribution)
            logger.info(f"Patch attribution shape: {patch_attribution.shape}")
            logger.info(f"Patch attribution min: {patch_attribution.min():.6f}")
            logger.info(f"Patch attribution max: {patch_attribution.max():.6f}")
            
            # NUMERICAL DEBUGGING: Track attribution argmax through coordinate transformations
            argmax_patch_idx = int(np.argmax(patch_attribution))
            argmax_patch_row = argmax_patch_idx // 14
            argmax_patch_col = argmax_patch_idx % 14
            argmax_value = patch_attribution[argmax_patch_row, argmax_patch_col]
            
            logger.info(f"=" * 80)
            logger.info("ATTRIBUTION ARGMAX TRACKING")
            logger.info(f"=" * 80)
            logger.info(f"Attribution argmax patch index: {argmax_patch_idx}")
            logger.info(f"Attribution argmax patch coordinates: row={argmax_patch_row}, col={argmax_patch_col}")
            logger.info(f"Attribution argmax value: {argmax_value:.6f}")
            
            # Calculate pixel coordinates in 224x224 image
            # Each patch is 16x16 pixels (224/14 = 16)
            patch_pixel_size = 16
            argmax_224_x_center = argmax_patch_col * patch_pixel_size + patch_pixel_size // 2
            argmax_224_y_center = argmax_patch_row * patch_pixel_size + patch_pixel_size // 2
            argmax_224_x_min = argmax_patch_col * patch_pixel_size
            argmax_224_y_min = argmax_patch_row * patch_pixel_size
            argmax_224_x_max = argmax_224_x_min + patch_pixel_size
            argmax_224_y_max = argmax_224_y_min + patch_pixel_size
            
            logger.info(f"224x224 pixel coordinates (center): x={argmax_224_x_center}, y={argmax_224_y_center}")
            logger.info(f"224x224 pixel coordinates (range): x=[{argmax_224_x_min}, {argmax_224_x_max}), y=[{argmax_224_y_min}, {argmax_224_y_max})")
            
            # Normalize
            normalized_attribution = self._normalize_attribution(patch_attribution)
            logger.info(f"Normalized attribution min: {normalized_attribution.min():.6f}")
            logger.info(f"Normalized attribution max: {normalized_attribution.max():.6f}")
            
            # Generate colored heatmap at 14x14
            heatmap_14x14 = self._generate_colored_heatmap(normalized_attribution)
            logger.info(f"14x14 heatmap generated, shape: {heatmap_14x14.shape}")
            
            # Resize to 224x224 (transformed image size)
            heatmap_224 = cv2.resize(heatmap_14x14, (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR)
            logger.info(f"224x224 heatmap generated, shape: {heatmap_224.shape}")
            
            # Reverse preprocessing to map back to original image coordinates
            heatmap_original = self._reverse_preprocessing(heatmap_224, image)
            logger.info(f"Original size heatmap generated, shape: {heatmap_original.shape}")
            
            # Continue coordinate tracking through inverse preprocessing
            original_w, original_h = image.size
            
            # Direct mapping from 224 coordinates to original coordinates
            # Since we resize directly from 224 to original dimensions
            scale_x = original_w / 224
            scale_y = original_h / 224
            argmax_original_x = int(argmax_224_x_center * scale_x)
            argmax_original_y = int(argmax_224_y_center * scale_y)
            
            logger.info(f"Scale factors (direct 224->original): x={scale_x:.4f}, y={scale_y:.4f}")
            logger.info(f"Original coordinates: x={argmax_original_x}, y={argmax_original_y}")
            logger.info(f"=" * 80)
            
            # Generate overlay
            overlay = self._generate_overlay(image, heatmap_original, alpha=0.4)
            logger.info(f"Overlay generated, shape: {overlay.shape}")
            
            # Save images
            original_path = os.path.join(output_dir, f"{analysis_id}_original.png")
            heatmap_path = os.path.join(output_dir, f"{analysis_id}_heatmap.png")
            overlay_path = os.path.join(output_dir, f"{analysis_id}_overlay.png")
            
            # Save original image for reference
            image.save(original_path)
            
            # Save heatmap
            Image.fromarray(heatmap_original).save(heatmap_path)
            
            # Save overlay
            Image.fromarray(overlay).save(overlay_path)
            
            # Save debug visualizations
            self._save_debug_visualizations(
                image, 
                normalized_attribution, 
                heatmap_224, 
                heatmap_original, 
                output_dir, 
                analysis_id,
                argmax_patch_idx,
                argmax_patch_row,
                argmax_patch_col,
                argmax_original_x,
                argmax_original_y
            )
            
            # Convert paths to forward slashes for URL compatibility
            original_path_url = original_path.replace('\\', '/')
            heatmap_path_url = heatmap_path.replace('\\', '/')
            overlay_path_url = overlay_path.replace('\\', '/')
            
            logger.info("=" * 80)
            logger.info("HEATMAP GENERATION SUCCESS")
            logger.info("=" * 80)
            logger.info(f"Original image saved: {original_path}")
            logger.info(f"Heatmap saved: {heatmap_path}")
            logger.info(f"Overlay saved: {overlay_path}")
            logger.info("=" * 80)
            
            return {
                "available": True,
                "method": "class_specific_gradient_attribution",
                "target_class_idx": predicted_class_idx,
                "heatmap_path": heatmap_path_url,
                "overlay_path": overlay_path_url,
                "original_path": original_path_url
            }
            
        except Exception as e:
            logger.error(f"Heatmap generation failed: {e}", exc_info=True)
            return {
                "available": False,
                "reason": f"Heatmap generation error: {str(e)}"
            }


def generate_panderm_heatmap(
    model: nn.Module,
    device: str,
    image: Image,
    tensor: torch.Tensor,
    predicted_class_idx: int,
    output_dir: str,
    analysis_id: str
) -> Dict[str, Any]:
    """
    Convenience function to generate PanDerm explainability heatmap.
    
    Args:
        model: Loaded PanDerm model
        device: Device the model is on
        image: Original PIL Image
        tensor: Preprocessed tensor for model input
        predicted_class_idx: Index of predicted class to explain
        output_dir: Directory to save output images
        analysis_id: Unique identifier for this analysis
        
    Returns:
        Dictionary with heatmap generation results
    """
    explainability = PanDermExplainability(model, device)
    return explainability.generate_heatmap(
        image=image,
        tensor=tensor,
        predicted_class_idx=predicted_class_idx,
        output_dir=output_dir,
        analysis_id=analysis_id
    )
