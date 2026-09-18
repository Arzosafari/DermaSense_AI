"""
Tests for Medical Context Service - Ensures safe extraction and use of user profile information.
"""
import pytest
from app.core.medical_context_service import medical_context_service


class TestMedicalContextService:
    """Test medical context extraction and formatting."""
    
    def test_empty_profile_returns_no_context(self):
        """Empty profile should return appropriate message."""
        result = medical_context_service.extract_relevant_context({}, "skin irritation")
        
        assert result["has_context"] is False
        assert "No relevant medical history" in result["message"]
    
    def test_medical_history_extraction(self):
        """Should extract medical history from profile."""
        profile = {
            "previous_skin_conditions": ["eczema", "psoriasis"],
            "previous_melanoma": True
        }
        
        result = medical_context_service.extract_relevant_context(profile)
        
        assert result["has_context"] is True
        assert "eczema" in result["context_summary"].lower()
        assert "psoriasis" in result["context_summary"].lower()
        assert "previous melanoma" in result["context_summary"].lower()
    
    def test_allergies_extraction(self):
        """Should extract allergies from profile."""
        profile = {
            "allergies": ["latex", "penicillin"]
        }
        
        result = medical_context_service.extract_relevant_context(profile)
        
        assert result["has_context"] is True
        assert "latex" in result["context_summary"].lower()
        assert "penicillin" in result["context_summary"].lower()
    
    def test_medications_extraction(self):
        """Should extract medications from profile."""
        profile = {
            "current_medications": ["metformin", "ibuprofen"]
        }
        
        result = medical_context_service.extract_relevant_context(profile)
        
        assert result["has_context"] is True
        assert "metformin" in result["context_summary"].lower()
        assert "ibuprofen" in result["context_summary"].lower()
    
    def test_skin_risk_factors_extraction(self):
        """Should extract skin-specific risk factors."""
        profile = {
            "skin_type": "fair",
            "sun_exposure": "high",
            "sunburn_history": True
        }
        
        result = medical_context_service.extract_relevant_context(profile)
        
        assert result["has_context"] is True
        assert "fair skin" in result["context_summary"].lower()
        assert "sun exposure" in result["context_summary"].lower()
    
    def test_chronic_conditions_extraction(self):
        """Should extract chronic conditions."""
        profile = {
            "chronic_conditions": ["diabetes", "autoimmune"]
        }
        
        result = medical_context_service.extract_relevant_context(profile)
        
        assert result["has_context"] is True
        assert "diabetes" in result["context_summary"].lower()
        assert "autoimmune" in result["context_summary"].lower()
    
    def test_context_formatting_for_prompt(self):
        """Should format context with clear attribution."""
        profile = {
            "allergies": ["latex"],
            "previous_skin_conditions": ["eczema"]
        }
        
        context = medical_context_service.extract_relevant_context(profile)
        formatted = medical_context_service.format_context_for_prompt(context)
        
        assert "RELEVANT INFORMATION YOU PREVIOUSLY PROVIDED" in formatted
        assert "previously reported" in formatted.lower()
        assert "latex" in formatted.lower()
        assert "eczema" in formatted.lower()
    
    def test_profile_completeness_assessment(self):
        """Should assess profile completeness."""
        complete_profile = {
            "age": 45,
            "gender": "male",
            "skin_type": "fair",
            "allergies": ["latex"],
            "previous_skin_conditions": ["eczema"],
            "current_medications": ["metformin"],
            "chronic_conditions": ["diabetes"],
            "sun_exposure": "moderate"
        }
        
        result = medical_context_service.get_profile_completeness(complete_profile)
        
        assert result["completeness_score"] > 80
        assert len(result["missing_fields"]) < 3
    
    def test_empty_profile_completeness(self):
        """Empty profile should have low completeness score."""
        result = medical_context_service.get_profile_completeness({})
        
        assert result["completeness_score"] == 0
        assert len(result["missing_fields"]) >= 1  # At least the generic message
        assert len(result["suggestions"]) > 0
    
    def test_no_invention_of_information(self):
        """Service should never invent information not in profile."""
        profile = {"age": 30}
        
        result = medical_context_service.extract_relevant_context(profile)
        
        # Profile with only age should have no medical context
        assert result["has_context"] is False
        # Should not contain medical information not in profile
        if result.get("has_context"):
            assert "allerg" not in result["context_summary"].lower()
            assert "medication" not in result["context_summary"].lower()
            assert "eczema" not in result["context_summary"].lower()
    
    def test_string_vs_array_handling(self):
        """Should handle both string and array formats for fields."""
        profile_array = {
            "allergies": ["latex", "penicillin"]
        }
        
        profile_string = {
            "allergies": "latex, penicillin"
        }
        
        result_array = medical_context_service.extract_relevant_context(profile_array)
        result_string = medical_context_service.extract_relevant_context(profile_string)
        
        assert result_array["has_context"] is True
        assert result_string["has_context"] is True
        assert "latex" in result_array["context_summary"].lower()
        assert "latex" in result_string["context_summary"].lower()
    
    def test_context_sources_tracking(self):
        """Should track sources of extracted information."""
        profile = {
            "allergies": ["latex"],
            "previous_skin_conditions": ["eczema"]
        }
        
        result = medical_context_service.extract_relevant_context(profile)
        
        assert len(result["sources"]) > 0
        assert any("allerg" in source.lower() for source in result["sources"])
        assert any("medical" in source.lower() or "condition" in source.lower() for source in result["sources"])
    
    def test_disclaimer_inclusion(self):
        """Should include disclaimer about information source."""
        profile = {"allergies": ["latex"]}
        
        result = medical_context_service.extract_relevant_context(profile)
        
        assert "disclaimer" in result
        assert "previously provided" in result["disclaimer"].lower()
    
    def test_query_relevance_filtering(self):
        """Should consider query when extracting context (future enhancement)."""
        profile = {
            "allergies": ["latex"],
            "previous_skin_conditions": ["eczema"]
        }
        
        # For now, all relevant info is extracted regardless of query
        result_general = medical_context_service.extract_relevant_context(profile, "general question")
        result_skin = medical_context_service.extract_relevant_context(profile, "skin rash")
        
        # Both should return context since we don't filter by query yet
        assert result_general["has_context"] is True
        assert result_skin["has_context"] is True