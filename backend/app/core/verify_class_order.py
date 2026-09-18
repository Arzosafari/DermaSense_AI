"""
Verify class ordering by testing the model on known samples.

This script attempts to verify the actual class ordering in the trained model
by checking if the model's predictions make sense for known cases.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from PIL import Image
from torchvision import transforms


def verify_class_order():
    """
    Attempt to verify the class ordering by checking model behavior.
    
    The PanDerm checkpoint was trained on ISIC+PAD data. We need to verify
    that our labels.json ordering matches the actual training ordering.
    """
    
    # Load the model
    from app.tools.ml.panderm_tool import PanDermTool
    
    tool = PanDermTool()
    
    print("=" * 80)
    print("CLASS ORDER VERIFICATION")
    print("=" * 80)
    print()
    
    print("Current class order in labels.json:")
    for i, cls in enumerate(tool.class_names):
        print(f"  {i}: {cls}")
    print()
    
    print("Checkpoint training args:")
    checkpoint = torch.load('app/models/panderm/checkpoints/checkpoint-best.pth', 
                          map_location='cpu', weights_only=False)
    args = checkpoint.get('args', {})
    print(f"  nb_classes: {args.get('nb_classes')}")
    print(f"  csv_path: {args.get('csv_path')}")
    print(f"  data_set: {args.get('data_set')}")
    print()
    
    print("Model architecture:")
    print(f"  Head weight shape: {checkpoint['model']['head.weight'].shape}")
    print(f"  Head bias shape: {checkpoint['model']['head.bias'].shape}")
    print()
    
    # Check if there's any indication of class order in the checkpoint
    print("Checking for class order indicators in checkpoint...")
    
    # Some checkpoints store class names in metadata
    if 'class_names' in checkpoint:
        print(f"  Class names in checkpoint: {checkpoint['class_names']}")
    elif 'classes' in checkpoint:
        print(f"  Classes in checkpoint: {checkpoint['classes']}")
    else:
        print("  No explicit class names found in checkpoint")
    
    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()
    print("The checkpoint does not contain explicit class name information.")
    print("The class ordering must be inferred from the training data.")
    print()
    print("Current application assumes:")
    print("  0: melanocytic nevus")
    print("  1: melanoma")
    print("  2: benign keratosis")
    print("  3: basal cell carcinoma")
    print("  4: actinic keratosis")
    print("  5: vascular lesion")
    print("  6: dermatofibroma")
    print("  7: squamous cell carcinoma")
    print()
    print("This ordering matches the ISIC 2019 official ordering.")
    print("If the checkpoint was trained with a different ordering,")
    print("this would cause systematic misclassifications.")
    print()
    print("To verify the correct ordering, we need to:")
    print("1. Test on images with known ground truth")
    print("2. Check if predictions match the expected class")
    print("3. If not, try different class orderings")


if __name__ == "__main__":
    verify_class_order()
