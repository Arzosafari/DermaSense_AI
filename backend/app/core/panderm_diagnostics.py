"""
PanDerm Diagnostics Tool

Comprehensive analysis tool for PanDerm classification and explainability.
Investigates classification errors, preprocessing impact, and attribution methods.
"""
import logging
import os
import json
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
import cv2

logger = logging.getLogger(__name__)


class PanDermDiagnostics:
    """
    Comprehensive diagnostics for PanDerm Vision Transformer.
    
    Analyzes:
    - Class mapping correctness
    - Preprocessing pipeline impact
    - Classification errors per class
    - Multiple attribution methods
    - Spatial alignment verification
    """
    
    def __init__(self, model: nn.Module, device: str = "cpu"):
        self.model = model
        self.device = device
        
        # Architecture parameters
        self.img_size = 224
        self.pre_resize_size = 256
        self.patch_size = 16
        self.patch_grid = (self.img_size // self.patch_size, self.img_size // self.patch_size)
        self.num_patches = self.patch_grid[0] * self.patch_grid[1]
        
        # Class names (from labels.json)
        self.class_names = [
            "melanocytic nevus",
            "melanoma",
            "benign keratosis",
            "basal cell carcinoma",
            "actinic keratosis",
            "vascular lesion",
            "dermatofibroma",
            "squamous cell carcinoma"
        ]
        
        logger.info("PanDermDiagnostics initialized")
    
    def visualize_preprocessing(
        self, 
        image: Image, 
        output_dir: str, 
        analysis_id: str
    ) -> Dict[str, str]:
        """
        Visualize the preprocessing pipeline to understand spatial transformations.
        
        Args:
            image: Original PIL Image
            output_dir: Directory to save outputs
            analysis_id: Unique identifier
            
        Returns:
            Dictionary with paths to saved images
        """
        os.makedirs(output_dir, exist_ok=True)
        
        from torchvision import transforms
        
        original_size = image.size
        logger.info(f"Original image size: {original_size}")
        
        # Step 1: Save original
        original_path = os.path.join(output_dir, f"{analysis_id}_0_original.png")
        image.save(original_path)
        
        # Step 2: Resize to 256
        resize_transform = transforms.Resize(self.pre_resize_size, interpolation=3)
        resized_image = resize_transform(image)
        resized_path = os.path.join(output_dir, f"{analysis_id}_1_resized_256.png")
        resized_image.save(resized_path)
        logger.info(f"Resized to: {resized_image.size}")
        
        # Step 3: CenterCrop to 224
        crop_transform = transforms.CenterCrop(self.img_size)
        cropped_image = crop_transform(resized_image)
        cropped_path = os.path.join(output_dir, f"{analysis_id}_2_cropped_224.png")
        cropped_image.save(cropped_path)
        logger.info(f"Cropped to: {cropped_image.size}")
        
        # Step 4: Convert to tensor and normalize
        to_tensor = transforms.ToTensor()
        normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        
        tensor = to_tensor(cropped_image)
        tensor_normalized = normalize(tensor)
        
        # Save normalized tensor as image (denormalize for visualization)
        mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        tensor_denorm = tensor_normalized * std + mean
        tensor_denorm = torch.clamp(tensor_denorm, 0, 1)
        
        tensor_path = os.path.join(output_dir, f"{analysis_id}_3_tensor_224.png")
        transforms.ToPILImage()(tensor_denorm).save(tensor_path)
        
        # Step 5: Draw patch grid on cropped image
        patch_grid_path = os.path.join(output_dir, f"{analysis_id}_4_patch_grid.png")
        self._draw_patch_grid(cropped_image, patch_grid_path)
        
        # Step 6: Compute lesion scale (if possible)
        lesion_info = self._estimate_lesion_scale(image, cropped_image)
        
        return {
            "original_path": original_path.replace('\\', '/'),
            "resized_path": resized_path.replace('\\', '/'),
            "cropped_path": cropped_path.replace('\\', '/'),
            "tensor_path": tensor_path.replace('\\', '/'),
            "patch_grid_path": patch_grid_path.replace('\\', '/'),
            "original_size": original_size,
            "resized_size": resized_image.size,
            "cropped_size": cropped_image.size,
            "lesion_info": lesion_info
        }
    
    def _draw_patch_grid(self, image: Image, output_path: str):
        """Draw 14x14 patch grid on the image."""
        img_np = np.array(image)
        h, w = img_np.shape[:2]
        
        # Draw grid lines
        patch_h = h // 14
        patch_w = w // 14
        
        for i in range(1, 14):
            # Horizontal lines
            cv2.line(img_np, (0, i * patch_h), (w, i * patch_h), (0, 255, 0), 1)
            # Vertical lines
            cv2.line(img_np, (i * patch_w, 0), (i * patch_w, h), (0, 255, 0), 1)
        
        # Add patch numbers
        for i in range(14):
            for j in range(14):
                patch_num = i * 14 + j
                cv2.putText(img_np, str(patch_num), (j * patch_w + 5, i * patch_h + 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)
        
        cv2.imwrite(output_path, img_np)
    
    def _estimate_lesion_scale(self, original: Image, cropped: Image) -> Dict[str, Any]:
        """Estimate lesion scale and position."""
        # Simple heuristic: measure pixel intensity variance
        orig_np = np.array(original)
        cropped_np = np.array(cropped)
        
        # Convert to grayscale
        orig_gray = cv2.cvtColor(orig_np, cv2.COLOR_RGB2GRAY)
        cropped_gray = cv2.cvtColor(cropped_np, cv2.COLOR_RGB2GRAY)
        
        # Simple lesion detection using thresholding
        _, orig_thresh = cv2.threshold(orig_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, cropped_thresh = cv2.threshold(cropped_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Count lesion pixels
        orig_lesion_pixels = np.sum(orig_thresh < 128)
        cropped_lesion_pixels = np.sum(cropped_thresh < 128)
        
        total_pixels = orig_thresh.size
        orig_lesion_ratio = orig_lesion_pixels / total_pixels
        cropped_lesion_ratio = cropped_lesion_pixels / (cropped_thresh.size)
        
        return {
            "original_lesion_ratio": orig_lesion_ratio,
            "cropped_lesion_ratio": cropped_lesion_ratio,
            "lesion_scale": "small" if orig_lesion_ratio < 0.1 else "medium" if orig_lesion_ratio < 0.3 else "large"
        }
    
    def compare_attribution_methods(
        self,
        image: Image,
        tensor: torch.Tensor,
        predicted_class_idx: int,
        output_dir: str,
        analysis_id: str
    ) -> Dict[str, Any]:
        """
        Compare multiple attribution methods on the same image.
        
        Args:
            image: Original PIL Image
            tensor: Preprocessed tensor
            predicted_class_idx: Target class index
            output_dir: Output directory
            analysis_id: Unique identifier
            
        Returns:
            Dictionary with comparison results
        """
        os.makedirs(output_dir, exist_ok=True)
        
        results = {}
        
        # Method 1: Gradient-based (current implementation)
        from app.core.panderm_explainability import PanDermExplainability
        explainability = PanDermExplainability(self.model, self.device)
        
        grad_result = explainability.generate_heatmap(
            image=image,
            tensor=tensor,
            predicted_class_idx=predicted_class_idx,
            output_dir=output_dir,
            analysis_id=f"{analysis_id}_gradcam"
        )
        
        results["gradient_based"] = grad_result
        
        # Method 2: Attention Rollout (previous implementation)
        attn_result = self._attention_rollout_attribution(
            image=image,
            tensor=tensor,
            predicted_class_idx=predicted_class_idx,
            output_dir=output_dir,
            analysis_id=f"{analysis_id}_attn_rollout"
        )
        
        results["attention_rollout"] = attn_result
        
        # Method 3: Simple saliency (gradient magnitude)
        saliency_result = self._saliency_attribution(
            image=image,
            tensor=tensor,
            predicted_class_idx=predicted_class_idx,
            output_dir=output_dir,
            analysis_id=f"{analysis_id}_saliency"
        )
        
        results["saliency"] = saliency_result
        
        return results
    
    def _attention_rollout_attribution(
        self,
        image: Image,
        tensor: torch.Tensor,
        predicted_class_idx: int,
        output_dir: str,
        analysis_id: str
    ) -> Dict[str, Any]:
        """Compute attention rollout attribution."""
        try:
            attention_maps = []
            original_forwards = {}
            
            # Patch attention modules
            for idx, block in enumerate(self.model.blocks):
                if hasattr(block, 'attn'):
                    attn_module = block.attn
                    original_forwards[idx] = attn_module.forward
                    
                    def make_patched_forward(original_forward, layer_idx, attn_maps_list):
                        def patched_forward(self, x, rel_pos_bias=None):
                            B, N, C = x.shape
                            qkv_bias = None
                            if self.q_bias is not None:
                                qkv_bias = torch.cat((self.q_bias, torch.zeros_like(self.v_bias, requires_grad=False), self.v_bias))
                            qkv = F.linear(input=x, weight=self.qkv.weight, bias=qkv_bias)
                            qkv = qkv.reshape(B, N, 3, self.num_heads, -1).permute(2, 0, 3, 1, 4)
                            q, k, v = qkv[0], qkv[1], qkv[2]
                            
                            q = q * self.scale
                            attn = (q @ k.transpose(-2, -1))
                            
                            if self.relative_position_bias_table is not None:
                                relative_position_bias = \
                                    self.relative_position_bias_table[self.relative_position_index.view(-1)].view(
                                        self.window_size[0] * self.window_size[1] + 1,
                                        self.window_size[0] * self.window_size[1] + 1, -1)
                                relative_position_bias = relative_position_bias.permute(2, 0, 1).contiguous()
                                attn = attn + relative_position_bias.unsqueeze(0)
                            
                            if rel_pos_bias is not None:
                                attn = attn + rel_pos_bias
                            
                            attn_weights = attn.softmax(dim=-1)
                            attn_maps_list.append(attn_weights.detach().cpu())
                            
                            attn = self.attn_drop(attn_weights)
                            x = (attn @ v).transpose(1, 2).reshape(B, N, -1)
                            x = self.proj(x)
                            x = self.proj_drop(x)
                            
                            return x
                        return patched_forward
                    
                    import types
                    attn_module.forward = types.MethodType(make_patched_forward(attn_module.forward, idx, attention_maps), attn_module)
            
            # Forward pass
            with torch.no_grad():
                _ = self.model(tensor)
            
            # Restore forwards
            for idx, block in enumerate(self.model.blocks):
                if hasattr(block, 'attn') and idx in original_forwards:
                    import types
                    block.attn.forward = types.MethodType(original_forwards[idx], block.attn)
            
            # Compute rollout
            rollout = torch.eye(attention_maps[0].shape[-1]).to(attention_maps[0].device)
            for attn in attention_maps:
                attn_avg = attn.mean(dim=1)[0]
                rollout = rollout @ attn_avg
            
            # Extract CLS attention to patches
            cls_attention = rollout[0, 1:].cpu().numpy()
            heatmap = cls_attention.reshape(14, 14)
            heatmap = (heatmap - heatmap.min()) / (heatmap.max() - heatmap.min() + 1e-8)
            
            # Generate visualization
            heatmap_colored = cv2.applyColorMap((heatmap * 255).astype(np.uint8), cv2.COLORMAP_JET)
            heatmap_rgb = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
            
            # Resize to original
            original_size = image.size[::-1]
            heatmap_resized = cv2.resize(heatmap_rgb, (original_size[1], original_size[0]))
            
            # Generate overlay
            overlay = self._generate_overlay(image, heatmap_resized)
            
            # Save
            heatmap_path = os.path.join(output_dir, f"{analysis_id}_heatmap.png")
            overlay_path = os.path.join(output_dir, f"{analysis_id}_overlay.png")
            
            Image.fromarray(heatmap_resized).save(heatmap_path)
            Image.fromarray(overlay).save(overlay_path)
            
            return {
                "available": True,
                "method": "attention_rollout",
                "heatmap_path": heatmap_path.replace('\\', '/'),
                "overlay_path": overlay_path.replace('\\', '/')
            }
            
        except Exception as e:
            logger.error(f"Attention rollout failed: {e}")
            return {"available": False, "reason": str(e)}
    
    def _saliency_attribution(
        self,
        image: Image,
        tensor: torch.Tensor,
        predicted_class_idx: int,
        output_dir: str,
        analysis_id: str
    ) -> Dict[str, Any]:
        """Compute simple saliency (gradient magnitude)."""
        try:
            tensor.requires_grad_(True)
            
            outputs = self.model(tensor)
            target_logit = outputs[0, predicted_class_idx]
            
            self.model.zero_grad()
            target_logit.backward(retain_graph=True)
            
            gradients = tensor.grad
            grad_magnitude = torch.sqrt(torch.sum(gradients ** 2, dim=1))[0]
            
            tensor.requires_grad_(False)
            
            # Normalize
            grad_magnitude = (grad_magnitude - grad_magnitude.min()) / (grad_magnitude.max() - grad_magnitude.min() + 1e-8)
            
            # Generate visualization
            heatmap_colored = cv2.applyColorMap((grad_magnitude * 255).astype(np.uint8), cv2.COLORMAP_JET)
            heatmap_rgb = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
            
            # Resize to original
            original_size = image.size[::-1]
            heatmap_resized = cv2.resize(heatmap_rgb, (original_size[1], original_size[0]))
            
            # Generate overlay
            overlay = self._generate_overlay(image, heatmap_resized)
            
            # Save
            heatmap_path = os.path.join(output_dir, f"{analysis_id}_heatmap.png")
            overlay_path = os.path.join(output_dir, f"{analysis_id}_overlay.png")
            
            Image.fromarray(heatmap_resized).save(heatmap_path)
            Image.fromarray(overlay).save(overlay_path)
            
            return {
                "available": True,
                "method": "saliency",
                "heatmap_path": heatmap_path.replace('\\', '/'),
                "overlay_path": overlay_path.replace('\\', '/')
            }
            
        except Exception as e:
            logger.error(f"Saliency attribution failed: {e}")
            return {"available": False, "reason": str(e)}
    
    def _generate_overlay(self, image: Image, heatmap: np.ndarray, alpha: float = 0.4) -> np.ndarray:
        """Generate overlay."""
        original_np = np.array(image)
        if heatmap.shape[:2] != original_np.shape[:2]:
            heatmap = cv2.resize(heatmap, (original_np.shape[1], original_np.shape[0]))
        overlay = (original_np * (1 - alpha) + heatmap * alpha).astype(np.uint8)
        return overlay
    
    def analyze_classification(
        self,
        image: Image,
        tensor: torch.Tensor,
        true_class: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze classification result in detail.
        
        Args:
            image: Original PIL Image
            tensor: Preprocessed tensor
            true_class: Ground truth class (if available)
            
        Returns:
            Detailed classification analysis
        """
        self.model.eval()
        
        with torch.no_grad():
            outputs = self.model(tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, pred_idx = torch.max(probabilities, 1)
            
            # Get all probabilities
            all_probs = {
                self.class_names[i]: round(probabilities[0][i].item(), 4)
                for i in range(len(self.class_names))
            }
            
            # Get top-k
            top_k = min(3, len(self.class_names))
            top_k_conf, top_k_idx = torch.topk(probabilities, top_k)
            
            top_predictions = [
                {
                    "class": self.class_names[idx.item()],
                    "probability": round(conf.item(), 4)
                }
                for conf, idx in zip(top_k_conf[0], top_k_idx[0])
            ]
        
        predicted_class = self.class_names[pred_idx.item()]
        
        analysis = {
            "predicted_class": predicted_class,
            "predicted_index": pred_idx.item(),
            "confidence": round(confidence.item(), 4),
            "top_predictions": top_predictions,
            "all_probabilities": all_probs,
            "true_class": true_class,
            "is_correct": predicted_class == true_class if true_class else None
        }
        
        return analysis


def run_diagnostics(
    model: nn.Module,
    device: str,
    image: Image,
    true_class: Optional[str] = None,
    output_dir: str = "diagnostics_output",
    analysis_id: str = "diagnostic"
) -> Dict[str, Any]:
    """
    Run comprehensive diagnostics on an image.
    
    Args:
        model: PanDerm model
        device: Device
        image: PIL Image
        true_class: Ground truth (optional)
        output_dir: Output directory
        analysis_id: Unique identifier
        
    Returns:
        Comprehensive diagnostic results
    """
    diagnostics = PanDermDiagnostics(model, device)
    
    from torchvision import transforms
    
    # Preprocess image
    crop_pct = 224 / 256
    size = int(224 / crop_pct)
    transform = transforms.Compose([
        transforms.Resize(size, interpolation=3),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    tensor = transform(image).unsqueeze(0).to(device)
    
    # Run classification analysis
    classification_analysis = diagnostics.analyze_classification(image, tensor, true_class)
    
    # Visualize preprocessing
    preprocessing_viz = diagnostics.visualize_preprocessing(image, output_dir, analysis_id)
    
    # Compare attribution methods
    attribution_comparison = diagnostics.compare_attribution_methods(
        image, tensor, classification_analysis["predicted_index"], output_dir, analysis_id
    )
    
    return {
        "classification": classification_analysis,
        "preprocessing": preprocessing_viz,
        "attribution_comparison": attribution_comparison
    }
