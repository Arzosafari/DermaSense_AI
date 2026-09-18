"""
Medical Context Service - Extracts relevant user profile information for personalized analysis.

This service safely extracts medical context from user profiles while ensuring:
- Only user-provided information is used (never invented)
- Clear distinction between profile history and current symptoms
- Privacy-preserving context extraction
- Relevance filtering for specific medical queries
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class MedicalContextService:
    """Service for extracting and formatting relevant medical context from user profiles."""
    
    def __init__(self):
        self.logger = logger
    
    def extract_relevant_context(
        self, 
        user_profile: Dict[str, Any], 
        current_query: str = "",
        predicted_class: str = ""
    ) -> Dict[str, Any]:
        """
        Extract medically relevant context from user profile.
        
        Args:
            user_profile: User's medical profile data
            current_query: Current user message/symptoms
            predicted_class: Predicted lesion class (if applicable)
            
        Returns:
            Dictionary with relevant medical context, clearly labeled as user-provided
        """
        if not user_profile:
            return {
                "has_context": False,
                "message": "No relevant medical history was provided in your profile."
            }
        
        context_parts = []
        sources = []
        
        # Extract medical history (including chronic conditions from auth profile)
        medical_history = self._extract_medical_history(user_profile)
        if medical_history:
            context_parts.append(f"Medical history: {', '.join(medical_history)}")
            sources.append("previously reported medical history")
        
        # Extract allergies
        allergies = self._extract_allergies(user_profile)
        if allergies:
            context_parts.append(f"Allergies: {', '.join(allergies)}")
            sources.append("previously reported allergies")
        
        # Extract medications
        medications = self._extract_medications(user_profile)
        if medications:
            context_parts.append(f"Current medications: {', '.join(medications)}")
            sources.append("reported medications")
        
        # Extract skin-specific risk factors
        skin_factors = self._extract_skin_risk_factors(user_profile)
        if skin_factors:
            context_parts.append(f"Skin risk factors: {', '.join(skin_factors)}")
            sources.append("skin-related profile information")
        
        # Extract chronic conditions (may be duplicate of medical_history, but handle anyway)
        chronic_conditions = self._extract_chronic_conditions(user_profile)
        if chronic_conditions:
            # Only add if not already in medical_history
            chronic_unique = [c for c in chronic_conditions if c not in medical_history]
            if chronic_unique:
                context_parts.append(f"Chronic conditions: {', '.join(chronic_unique)}")
                sources.append("reported chronic conditions")
        
        if not context_parts:
            return {
                "has_context": False,
                "message": "No relevant medical history was provided in your profile."
            }
        
        return {
            "has_context": True,
            "context_summary": ". ".join(context_parts),
            "context_parts": context_parts,
            "sources": sources,
            "disclaimer": "This information was previously provided by you in your profile.",
            "raw_context": {
                "medical_history": medical_history,
                "allergies": allergies,
                "medications": medications,
                "skin_factors": skin_factors,
                "chronic_conditions": chronic_conditions
            }
        }
    
    def _extract_medical_history(self, profile: Dict[str, Any]) -> List[str]:
        """Extract medical history conditions."""
        history = []
        
        # Check various possible field names (both patient profile and auth profile formats)
        # Priority: patient profile fields first, then auth profile fields
        for field in ["previous_skin_conditions", "medical_history", "medical_conditions", "chronic_conditions"]:
            if field in profile and profile[field]:
                if isinstance(profile[field], list):
                    history.extend([str(h) for h in profile[field] if h])
                elif isinstance(profile[field], str):
                    parts = [h.strip() for h in profile[field].split(",") if h.strip()]
                    history.extend(parts)
        
        # Check for specific conditions
        if profile.get("previous_melanoma"):
            history.append("previous melanoma")
        if profile.get("previous_skin_cancer"):
            history.append("previous skin cancer")
        if profile.get("family_history_melanoma"):
            history.append("family history of melanoma")
        if profile.get("family_history_skin_cancer"):
            history.append("family history of skin cancer")
        
        return list(set(history))  # Remove duplicates
    
    def _extract_allergies(self, profile: Dict[str, Any]) -> List[str]:
        """Extract allergy information."""
        allergies = []
        
        for field in ["allergies", "known_allergies"]:
            if field in profile and profile[field]:
                if isinstance(profile[field], list):
                    allergies.extend([str(a) for a in profile[field] if a])
                elif isinstance(profile[field], str):
                    parts = [a.strip() for a in profile[field].split(",") if a.strip()]
                    allergies.extend(parts)
        
        return list(set(allergies))
    
    def _extract_medications(self, profile: Dict[str, Any]) -> List[str]:
        """Extract current medications."""
        medications = []
        
        for field in ["current_medications", "medications", "current_medication"]:
            if field in profile and profile[field]:
                if isinstance(profile[field], list):
                    medications.extend([str(m) for m in profile[field] if m])
                elif isinstance(profile[field], str):
                    parts = [m.strip() for m in profile[field].split(",") if m.strip()]
                    medications.extend(parts)
        
        return list(set(medications))
    
    def _extract_skin_risk_factors(self, profile: Dict[str, Any]) -> List[str]:
        """Extract skin-specific risk factors."""
        factors = []
        
        # Skin type (from both auth and patient profiles)
        skin_type = profile.get("skin_type")
        if skin_type:
            if skin_type.lower() in ["fair", "very fair", "type_i", "type_ii"]:
                factors.append("fair skin type (higher UV sensitivity)")
            else:
                factors.append(f"skin type: {skin_type}")
        
        # Sun exposure
        sun_exposure = profile.get("sun_exposure")
        if sun_exposure and sun_exposure.lower() == "high":
            factors.append("high sun exposure")
        
        # Sunburn history
        if profile.get("sunburn_history"):
            factors.append("history of sunburns")
        
        # Tanning bed use
        if profile.get("tanning_bed_use"):
            factors.append("tanning bed use")
        
        # Skin concerns
        skin_concerns = profile.get("skin_concerns")
        if skin_concerns:
            if isinstance(skin_concerns, list):
                factors.extend([str(c) for c in skin_concerns if c])
            elif isinstance(skin_concerns, str):
                parts = [c.strip() for c in skin_concerns.split(",") if c.strip()]
                factors.extend(parts)
        
        return list(set(factors))
    
    def _extract_chronic_conditions(self, profile: Dict[str, Any]) -> List[str]:
        """Extract chronic conditions that may be relevant."""
        conditions = []
        
        for field in ["chronic_conditions", "chronic_diseases", "ongoing_conditions"]:
            if field in profile and profile[field]:
                if isinstance(profile[field], list):
                    conditions.extend([str(c) for c in profile[field] if c])
                elif isinstance(profile[field], str):
                    parts = [c.strip() for c in profile[field].split(",") if c.strip()]
                    conditions.extend(parts)
        
        return list(set(conditions))
    
    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format medical context for inclusion in LLM prompt.
        
        This ensures clear attribution that information came from user's profile.
        """
        if not context.get("has_context"):
            return "No relevant medical history was provided in your profile."
        
        formatted = [
            "RELEVANT INFORMATION YOU PREVIOUSLY PROVIDED IN YOUR PROFILE:",
            ""
        ]
        
        if context.get("context_parts"):
            for part in context["context_parts"]:
                formatted.append(f"- {part}")
        
        formatted.append("")
        formatted.append("NOTE: This information comes from your profile. It represents what you previously reported, not a current diagnosis.")
        
        return "\n".join(formatted)
    
    def format_symptoms_context(self, user_message: str) -> str:
        """
        Format user symptoms from the current message.
        
        This ensures symptoms are always included when provided.
        """
        if not user_message or not user_message.strip():
            return "No symptoms were described in your message."
        
        return f"CURRENT SYMPTOMS YOU REPORTED: {user_message.strip()}"
    
    def get_profile_completeness(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess how complete the user's medical profile is.
        
        Returns guidance on what additional information might be helpful.
        """
        if not profile:
            return {
                "completeness_score": 0,
                "missing_fields": ["all profile information"],
                "suggestions": ["Consider completing your medical profile for more personalized analysis"]
            }
        
        checked_fields = [
            "age", "gender", "skin_type", "allergies", 
            "previous_skin_conditions", "current_medications",
            "chronic_conditions", "sun_exposure"
        ]
        
        filled_fields = sum(1 for field in checked_fields if profile.get(field))
        completeness = (filled_fields / len(checked_fields)) * 100
        
        missing = [field for field in checked_fields if not profile.get(field)]
        
        suggestions = []
        if not profile.get("age"):
            suggestions.append("Adding your age can help with risk assessment")
        if not profile.get("skin_type"):
            suggestions.append("Skin type information helps assess UV sensitivity")
        if not profile.get("allergies"):
            suggestions.append("Allergy information can help identify potential triggers")
        if not profile.get("previous_skin_conditions"):
            suggestions.append("Previous skin conditions can provide important context")
        
        return {
            "completeness_score": round(completeness),
            "filled_fields": filled_fields,
            "total_fields": len(checked_fields),
            "missing_fields": missing,
            "suggestions": suggestions
        }


# Global instance
medical_context_service = MedicalContextService()