"""
Lightweight tests for SmartHealth-LLM backend
These tests do NOT load the heavy PanDerm model to avoid memory issues.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from app.config import settings
from app.utils.isic_classes import is_malignant, normalize_class_name
from app.llm.factories.llm_factory import LLMFactory
from app.api.v1.patient import MedicalProfile, _compute_risk_factors


class TestClassMapping:
    """Test ISIC class mapping and malignancy detection"""
    
    def test_class_labels_count(self):
        """Verify 8-class mapping"""
        assert len(settings.ISIC_CLASS_LABELS) == 8
    
    def test_class_labels_order(self):
        """Verify official training order"""
        expected = [
            "melanocytic nevus",
            "melanoma", 
            "benign keratosis",
            "basal cell carcinoma",
            "actinic keratosis",
            "vascular lesion",
            "dermatofibroma",
            "squamous cell carcinoma"
        ]
        assert settings.ISIC_CLASS_LABELS == expected
    
    def test_malignant_classes(self):
        """Test malignancy detection for all classes"""
        # Malignant classes
        assert is_malignant("melanoma") == True
        assert is_malignant("basal cell carcinoma") == True
        assert is_malignant("actinic keratosis") == True
        assert is_malignant("squamous cell carcinoma") == True
        
        # Benign classes
        assert is_malignant("melanocytic nevus") == False
        assert is_malignant("benign keratosis") == False
        assert is_malignant("vascular lesion") == False
        assert is_malignant("dermatofibroma") == False
    
    def test_melanocytic_nevus_not_melanoma(self):
        """Critical test: ensure nevus is not detected as melanoma"""
        assert is_malignant("melanocytic nevus") == False
        assert normalize_class_name("melanocytic nevus") == "melanocytic nevus"
    
    def test_class_normalization(self):
        """Test class name normalization"""
        assert normalize_class_name("melanoma") == "melanoma"
        assert normalize_class_name("MELANOMA") == "melanoma"
        assert normalize_class_name("melanoma ") == "melanoma"


class TestProfileSystem:
    """Test user profile system"""
    
    def test_medical_profile_creation(self):
        """Test medical profile model"""
        profile = MedicalProfile(
            age=45,
            gender="male",
            skin_type="fair",
            family_history_melanoma=True
        )
        assert profile.age == 45
        assert profile.family_history_melanoma == True
    
    def test_risk_factor_computation(self):
        """Test risk factor computation"""
        profile = {
            "family_history_melanoma": True,
            "sun_exposure": "high",
            "smoking": True
        }
        risk_factors = _compute_risk_factors(profile)
        assert len(risk_factors) >= 2
        assert any("melanoma" in factor.lower() for factor in risk_factors)
    
    def test_profile_with_skin_cancer_history(self):
        """Test profile with previous skin cancer"""
        profile = {
            "previous_melanoma": True,
            "previous_skin_cancer": True
        }
        risk_factors = _compute_risk_factors(profile)
        assert len(risk_factors) >= 2


class TestLLMFactory:
    """Test LLM factory and provider selection"""
    
    def test_llm_factory_creates_instances(self):
        """Test that LLM factory creates proper instances"""
        llm = LLMFactory.for_agent("decider_agent")
        assert llm is not None
        assert hasattr(llm, 'generate')
    
    def test_llm_factory_for_all_agents(self):
        """Test LLM factory for different agent types"""
        agents = ["decider_agent", "reasoning_agent", "image_agent", "conversation_agent"]
        for agent in agents:
            llm = LLMFactory.for_agent(agent)
            assert llm is not None
    
    def test_groq_api_key_configured(self):
        """Test that Groq API key is configured"""
        # This tests that the config system works, not that the key is valid
        assert hasattr(settings, 'GROQ_API_KEY')
    
    def test_fallback_model_configured(self):
        """Test that fallback model is configured"""
        assert hasattr(settings, 'LM_STUDIO_MODEL')
        assert hasattr(settings, 'LM_STUDIO_HOST')


class TestAgentModelMapping:
    """Test agent to model mapping"""
    
    def test_agent_model_map_exists(self):
        """Test that agent model mapping is defined"""
        assert hasattr(settings, 'AGENT_MODEL_MAP')
        assert len(settings.AGENT_MODEL_MAP) > 0
    
    def test_reasoning_agent_model(self):
        """Test that reasoning agent uses proper model"""
        provider, model = settings.AGENT_MODEL_MAP.get("reasoning_agent", ("", ""))
        assert provider == "groq"
        assert "70b" in model or "versatile" in model
    
    def test_fast_agent_model(self):
        """Test that fast agents use faster models"""
        provider, model = settings.AGENT_MODEL_MAP.get("decider_agent", ("", ""))
        assert provider == "groq"
        assert "8b" in model or "instant" in model


class TestPanDermConfig:
    """Test PanDerm configuration (without loading model)"""
    
    def test_panderm_paths_configured(self):
        """Test that PanDerm paths are configured"""
        assert hasattr(settings, 'PANDERM_CHECKPOINT_PATH')
        assert hasattr(settings, 'PANDERM_CONFIG_PATH')
        assert hasattr(settings, 'PANDERM_LABELS_PATH')
    
    def test_panderm_config_file_exists(self):
        """Test that PanDerm config file exists"""
        assert os.path.exists(settings.PANDERM_CONFIG_PATH)
    
    def test_panderm_labels_file_exists(self):
        """Test that PanDerm labels file exists"""
        assert os.path.exists(settings.PANDERM_LABELS_PATH)
    
    def test_panderm_labels_json_valid(self):
        """Test that PanDerm labels JSON is valid"""
        import json
        with open(settings.PANDERM_LABELS_PATH, 'r') as f:
            labels = json.load(f)
        assert isinstance(labels, list)
        assert len(labels) == 8


class TestSecurity:
    """Test security configurations"""
    
    def test_env_file_in_gitignore(self):
        """Test that .env is in .gitignore"""
        gitignore_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../.gitignore'))
        with open(gitignore_path, 'r') as f:
            gitignore = f.read()
        assert '.env' in gitignore
        assert 'backend/.env' in gitignore
    
    def test_tokens_ignored(self):
        """Test that tokens are ignored"""
        gitignore_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../.gitignore'))
        with open(gitignore_path, 'r') as f:
            gitignore = f.read()
        assert 'tokens.json' in gitignore
    
    def test_venv_ignored(self):
        """Test that virtual environments are ignored"""
        gitignore_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../.gitignore'))
        with open(gitignore_path, 'r') as f:
            gitignore = f.read()
        assert 'venv_clean/' in gitignore


class TestAPIEndpoints:
    """Test API endpoint configuration"""
    
    def test_patient_router_configured(self):
        """Test that patient router exists"""
        # This is a basic import test
        try:
            from app.api.v1 import patient
            assert patient is not None
        except ImportError:
            pytest.fail("Patient router not found")
    
    def test_auth_router_configured(self):
        """Test that auth router exists"""
        try:
            from app.api.v1 import auth
            assert auth is not None
        except ImportError:
            pytest.fail("Auth router not found")


class TestMedicalSafety:
    """Test medical safety configurations"""
    
    def test_malignant_classes_correct(self):
        """Test that malignant classes are correctly defined"""
        malignant = settings.MALIGNANT_CLASSES
        assert "melanoma" in malignant or "mel" in malignant
        assert "basal cell carcinoma" in malignant or "bcc" in malignant
        assert "actinic keratosis" in malignant or "akiec" in malignant
        assert "squamous cell carcinoma" in malignant or "scc" in malignant
    
    def test_benign_classes_not_malignant(self):
        """Test that benign classes are not in malignant list"""
        malignant = settings.MALIGNANT_CLASSES
        # These should NOT be in malignant list
        assert "melanocytic nevus" not in malignant
        assert "benign keratosis" not in malignant


if __name__ == "__main__":
    pytest.main([__file__, "-v"])