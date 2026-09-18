"""
Classification Diagnostics Tool

Tests specific images to identify classification patterns and potential bugs.
"""
import logging
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)


class ClassificationDiagnostics:
    """
    Diagnostic tool for PanDerm classification.
    
    Tests specific images to identify:
    - Preprocessing issues
    - Class mapping issues
    - Model bias patterns
    - Systematic misclassifications
    """
    
    def __init__(self, model: nn.Module, device: str = "cpu"):
        self.model = model
        self.device = device
        
        # Class names
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
        
        # Preprocessing (matching official PanDerm)
        self.transform = transforms.Compose([
            transforms.Resize(256, interpolation=3),  # BICUBIC
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        
        logger.info("ClassificationDiagnostics initialized")
    
    def test_image(
        self,
        image_path: str,
        ground_truth: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Test a single image and return detailed analysis.
        
        Args:
            image_path: Path to image file
            ground_truth: Ground truth class (if known)
            
        Returns:
            Detailed classification analysis
        """
        try:
            # Load image
            image = Image.open(image_path).convert('RGB')
            original_size = image.size
            
            # Preprocess
            tensor = self.transform(image).unsqueeze(0).to(self.device)
            
            # Inference
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
                
                # Get top-3
                top_k_conf, top_k_idx = torch.topk(probabilities, 3)
                top_predictions = [
                    {
                        "class": self.class_names[idx.item()],
                        "probability": round(conf.item(), 4)
                    }
                    for conf, idx in zip(top_k_conf[0], top_k_idx[0])
                ]
            
            predicted_class = self.class_names[pred_idx.item()]
            
            result = {
                "image_path": image_path,
                "original_size": original_size,
                "ground_truth": ground_truth,
                "predicted_class": predicted_class,
                "predicted_index": pred_idx.item(),
                "confidence": round(confidence.item(), 4),
                "top_predictions": top_predictions,
                "all_probabilities": all_probs,
                "is_correct": predicted_class == ground_truth if ground_truth else None
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error testing image {image_path}: {e}", exc_info=True)
            return {
                "image_path": image_path,
                "error": str(e)
            }
    
    def test_batch(
        self,
        image_paths: List[str],
        ground_truths: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Test multiple images.
        
        Args:
            image_paths: List of image paths
            ground_truths: List of ground truth classes (optional)
            
        Returns:
            List of test results
        """
        results = []
        
        for i, image_path in enumerate(image_paths):
            ground_truth = ground_truths[i] if ground_truths and i < len(ground_truths) else None
            result = self.test_image(image_path, ground_truth)
            results.append(result)
        
        return results
    
    def analyze_class_confusion(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze class confusion patterns from test results.
        
        Args:
            results: List of test results
            
        Returns:
            Confusion analysis
        """
        confusion_matrix = {cls: {cls2: 0 for cls2 in self.class_names} for cls in self.class_names}
        class_counts = {cls: 0 for cls in self.class_names}
        correct_counts = {cls: 0 for cls in self.class_names}
        
        for result in results:
            if "error" in result:
                continue
            
            ground_truth = result.get("ground_truth")
            predicted = result.get("predicted_class")
            
            if ground_truth and predicted:
                confusion_matrix[ground_truth][predicted] += 1
                class_counts[ground_truth] += 1
                if ground_truth == predicted:
                    correct_counts[ground_truth] += 1
        
        # Calculate per-class accuracy
        class_accuracy = {}
        for cls in self.class_names:
            if class_counts[cls] > 0:
                class_accuracy[cls] = correct_counts[cls] / class_counts[cls]
            else:
                class_accuracy[cls] = None
        
        return {
            "confusion_matrix": confusion_matrix,
            "class_counts": class_counts,
            "correct_counts": correct_counts,
            "class_accuracy": class_accuracy
        }
    
    def print_detailed_report(
        self,
        results: List[Dict[str, Any]],
        output_file: Optional[str] = None
    ):
        """
        Print a detailed diagnostic report.
        
        Args:
            results: List of test results
            output_file: Optional file to save report
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("CLASSIFICATION DIAGNOSTICS REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        for i, result in enumerate(results, 1):
            report_lines.append(f"Image {i}: {result.get('image_path', 'Unknown')}")
            
            if "error" in result:
                report_lines.append(f"  ERROR: {result['error']}")
                report_lines.append("")
                continue
            
            report_lines.append(f"  Original Size: {result.get('original_size', 'Unknown')}")
            report_lines.append(f"  Ground Truth: {result.get('ground_truth', 'Unknown')}")
            report_lines.append(f"  Predicted: {result.get('predicted_class', 'Unknown')}")
            report_lines.append(f"  Confidence: {result.get('confidence', 'Unknown')}")
            report_lines.append(f"  Correct: {result.get('is_correct', 'Unknown')}")
            report_lines.append("")
            report_lines.append("  Top 3 Predictions:")
            for pred in result.get('top_predictions', []):
                report_lines.append(f"    - {pred['class']}: {pred['probability']:.4f}")
            report_lines.append("")
            report_lines.append("  All Probabilities:")
            for cls, prob in result.get('all_probabilities', {}).items():
                report_lines.append(f"    - {cls}: {prob:.4f}")
            report_lines.append("")
            report_lines.append("-" * 80)
            report_lines.append("")
        
        # Print analysis
        analysis = self.analyze_class_confusion(results)
        report_lines.append("CLASS CONFUSION ANALYSIS")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        for cls in self.class_names:
            if analysis['class_counts'][cls] > 0:
                report_lines.append(f"{cls}:")
                report_lines.append(f"  Total: {analysis['class_counts'][cls]}")
                report_lines.append(f"  Correct: {analysis['correct_counts'][cls]}")
                report_lines.append(f"  Accuracy: {analysis['class_accuracy'][cls]:.4f}")
                report_lines.append("")
                report_lines.append("  Confusion with:")
                for cls2, count in analysis['confusion_matrix'][cls].items():
                    if count > 0 and cls != cls2:
                        report_lines.append(f"    {cls2}: {count}")
                report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        print(report_text)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            logger.info(f"Report saved to {output_file}")


def run_classification_diagnostics(
    model: nn.Module,
    device: str,
    image_paths: List[str],
    ground_truths: Optional[List[str]] = None,
    output_file: Optional[str] = "classification_diagnostics_report.txt"
) -> List[Dict[str, Any]]:
    """
    Run comprehensive classification diagnostics.
    
    Args:
        model: PanDerm model
        device: Device
        image_paths: List of image paths to test
        ground_truths: Optional list of ground truth labels
        output_file: Optional output file for report
        
    Returns:
        List of test results
    """
    diagnostics = ClassificationDiagnostics(model, device)
    
    results = diagnostics.test_batch(image_paths, ground_truths)
    diagnostics.print_detailed_report(results, output_file)
    
    return results
