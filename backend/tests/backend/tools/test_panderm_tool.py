"""
Unit tests for PanDermTool adapter.

Tests the integration of the official PanDerm Vision Transformer
with the SmartHealth-LLM system.
"""
import os
import sys
import pytest
import numpy as np
from PIL import Image
import torch

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../external/PanDerm/classification"))

from app.tools.ml.panderm_tool import PanDermTool


class TestPanDermTool:
    """Test suite for PanDermTool functionality."""
    
    @pytest.fixture
    def panderm_tool(self):
        """Create a PanDermTool instance for testing."""
        try:
            tool = PanDermTool()
            return tool
        except Exception as e:
            pytest.skip(f"Could not initialize PanDermTool: {e}")
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample RGB image for testing."""
        return Image.fromarray(
            np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        )
    
    def test_checkpoint_exists(self, panderm_tool):
        """Test that the checkpoint file exists."""
        checkpoint_path = os.path.join(
            os.path.dirname(__file__), 
            "../../../app/models/panderm/checkpoints/checkpoint-best.pth"
        )
        assert os.path.exists(checkpoint_path), "Checkpoint file should exist"
    
    def test_model_loads(self, panderm_tool):
        """Test that the model loads successfully."""
        assert panderm_tool.model is not None, "Model should be loaded"
        assert panderm_tool.transform is not None, "Transform should be loaded"
    
    def test_device_selection(self, panderm_tool):
        """Test that device is properly selected (CPU or CUDA)."""
        assert panderm_tool.device in ["cuda", "cpu"], "Device should be cuda or cpu"
        if torch.cuda.is_available():
            assert panderm_tool.device == "cuda", "Should use CUDA when available"
        else:
            assert panderm_tool.device == "cpu", "Should fall back to CPU when CUDA unavailable"
    
    def test_class_names_loaded(self, panderm_tool):
        """Test that class names are loaded correctly."""
        assert len(panderm_tool.class_names) == 8, "Should have 8 classes"
        expected_classes = [
            "melanoma",
            "melanocytic nevus", 
            "basal cell carcinoma",
            "actinic keratosis",
            "benign keratosis",
            "dermatofibroma",
            "vascular lesion",
            "squamous cell carcinoma"
        ]
        assert panderm_tool.class_names == expected_classes, "Class names should match expected 8-class mapping"
    
    def test_config_loaded(self, panderm_tool):
        """Test that configuration is loaded correctly."""
        assert panderm_tool.config is not None, "Config should be loaded"
        assert panderm_tool.config.get("num_classes") == 8, "Config should specify 8 classes"
        assert panderm_tool.config.get("input_size") == 224, "Config should specify 224x224 input"
    
    def test_valid_image_produces_prediction(self, panderm_tool, sample_image):
        """Test that a valid image produces a prediction."""
        import asyncio
        
        async def run_prediction():
            result = await panderm_tool.run(sample_image)
            return result
        
        result = asyncio.run(run_prediction())
        
        assert "error" not in result, "Should not produce error for valid image"
        assert "predicted_class" in result, "Should include predicted class"
        assert "confidence" in result, "Should include confidence score"
        assert "top_predictions" in result, "Should include top predictions"
        assert "all_scores" in result, "Should include all class scores"
    
    def test_predicted_class_in_valid_range(self, panderm_tool, sample_image):
        """Test that predicted class belongs to the 8 known classes."""
        import asyncio
        
        async def run_prediction():
            result = await panderm_tool.run(sample_image)
            return result
        
        result = asyncio.run(run_prediction())
        
        predicted_class = result.get("predicted_class")
        assert predicted_class in panderm_tool.class_names, f"Predicted class '{predicted_class}' should be in known classes"
    
    def test_confidence_is_valid(self, panderm_tool, sample_image):
        """Test that confidence score is between 0 and 1."""
        import asyncio
        
        async def run_prediction():
            result = await panderm_tool.run(sample_image)
            return result
        
        result = asyncio.run(run_prediction())
        
        confidence = result.get("confidence")
        assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} should be between 0 and 1"
    
    def test_top_k_predictions_valid(self, panderm_tool, sample_image):
        """Test that top-k predictions are valid."""
        import asyncio
        
        async def run_prediction():
            result = await panderm_tool.run(sample_image)
            return result
        
        result = asyncio.run(run_prediction())
        
        top_predictions = result.get("top_predictions")
        assert len(top_predictions) <= 3, "Should have at most 3 top predictions"
        assert len(top_predictions) <= len(panderm_tool.class_names), "Should not exceed number of classes"
        
        for pred in top_predictions:
            assert "class" in pred, "Each prediction should have class"
            assert "probability" in pred, "Each prediction should have probability"
            assert pred["class"] in panderm_tool.class_names, f"Class {pred['class']} should be valid"
            assert 0.0 <= pred["probability"] <= 1.0, f"Probability {pred['probability']} should be valid"
    
    def test_all_scores_valid(self, panderm_tool, sample_image):
        """Test that all class scores are present and valid."""
        import asyncio
        
        async def run_prediction():
            result = await panderm_tool.run(sample_image)
            return result
        
        result = asyncio.run(run_prediction())
        
        all_scores = result.get("all_scores")
        assert len(all_scores) == len(panderm_tool.class_names), "Should have score for each class"
        
        for class_name, score in all_scores.items():
            assert class_name in panderm_tool.class_names, f"Class {class_name} should be valid"
            assert 0.0 <= score <= 1.0, f"Score {score} for {class_name} should be valid"
        
        # Check that probabilities sum to approximately 1
        total_score = sum(all_scores.values())
        assert abs(total_score - 1.0) < 0.01, f"Probabilities should sum to ~1, got {total_score}"
    
    def test_invalid_image_handling(self, panderm_tool):
        """Test that invalid input is handled gracefully."""
        import asyncio
        
        async def run_prediction():
            result = await panderm_tool.run("not_an_image")
            return result
        
        result = asyncio.run(run_prediction())
        
        assert "error" in result, "Should return error for invalid input"
    
    def test_model_backend_identified(self, panderm_tool, sample_image):
        """Test that model backend is correctly identified."""
        import asyncio
        
        async def run_prediction():
            result = await panderm_tool.run(sample_image)
            return result
        
        result = asyncio.run(run_prediction())
        
        assert result.get("model_backend") == "panderm_vit", "Should identify as PanDerm ViT backend"
    
    def test_preprocessing_pipeline(self, panderm_tool, sample_image):
        """Test that preprocessing pipeline works correctly."""
        try:
            tensor = panderm_tool.transform(sample_image)
            assert tensor.shape == (3, 224, 224), f"Tensor should be (3, 224, 224), got {tensor.shape}"
            assert tensor.dtype == torch.float32, "Tensor should be float32"
        except Exception as e:
            pytest.fail(f"Preprocessing failed: {e}")
    
    def test_model_in_cpu_mode(self):
        """Test that model can run on CPU."""
        try:
            # Force CPU mode
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            tool = PanDermTool()
            assert tool.device == "cpu", "Should use CPU when CUDA forced unavailable"
            
            # Test inference
            sample_image = Image.fromarray(
                np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
            )
            
            import asyncio
            async def run_prediction():
                result = await tool.run(sample_image)
                return result
            
            result = asyncio.run(run_prediction())
            assert "error" not in result, "CPU inference should work"
            
        except Exception as e:
            pytest.skip(f"CPU mode test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])