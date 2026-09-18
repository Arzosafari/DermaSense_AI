"""Dermatologist recommendation and triage guidance."""
from typing import Any, Dict, List, Optional

from app.tools.base_tool import BaseTool


class DoctorRecommenderTool(BaseTool):
    name = "doctor_recommender"
    description = "Provides dermatologist visit guidance based on risk level and location."

    _GENERAL_ADVICE = {
        "urgent": {
            "timeframe": "Within 1-2 weeks (sooner if rapidly changing)",
            "specialist": "Board-certified dermatologist",
            "visit_type": "Urgent skin cancer screening",
            "bring": [
                "Clear photos of the lesion (with dates if available)",
                "List of medications and allergies",
                "Family history of skin cancer",
                "ABCDE symptom notes",
            ],
            "questions": [
                "Could this be melanoma or another skin cancer?",
                "Do I need a biopsy?",
                "How urgently should this be treated?",
                "What follow-up schedule do you recommend?",
            ],
        },
        "high": {
            "timeframe": "Within 2-4 weeks",
            "specialist": "Dermatologist",
            "visit_type": "Skin lesion evaluation",
            "bring": ["Photos of the lesion", "Medication/allergy list"],
            "questions": [
                "Is this lesion cancerous or precancerous?",
                "What diagnostic tests are needed?",
                "What are my treatment options?",
            ],
        },
        "medium": {
            "timeframe": "Within 1-3 months or if changes occur",
            "specialist": "Dermatologist or primary care physician",
            "visit_type": "Routine skin check",
            "bring": ["Photos if monitoring at home"],
            "questions": [
                "Should I monitor this or have it removed?",
                "What changes should prompt an earlier visit?",
            ],
        },
        "low": {
            "timeframe": "At next routine checkup or annual skin exam",
            "specialist": "Primary care or dermatologist",
            "visit_type": "Preventive skin screening",
            "bring": [],
            "questions": [
                "How often should I have skin checks?",
                "What sun protection do you recommend for my skin type?",
            ],
        },
    }

    async def run(
        self,
        risk_level: str = "medium",
        location: Optional[str] = None,
        predicted_class: Optional[str] = None,
        run_id: str = "",
    ) -> Dict[str, Any]:
        advice = self._GENERAL_ADVICE.get(risk_level, self._GENERAL_ADVICE["medium"])

        recommendations: List[Dict[str, str]] = []
        if location:
            recommendations.append({
                "type": "search",
                "title": f"Find dermatologists near {location}",
                "action": f"Search Google Maps or your insurance portal for 'dermatologist near {location}'",
                "url_hint": f"https://www.google.com/maps/search/dermatologist+near+{location.replace(' ', '+')}",
            })
        recommendations.extend([
            {
                "type": "resource",
                "title": "American Academy of Dermatology — Find a Dermatologist",
                "action": "Visit aad.org to locate board-certified dermatologists",
                "url_hint": "https://find-a-derm.aad.org/",
            },
            {
                "type": "resource",
                "title": "Skin Cancer Foundation",
                "action": "Educational resources and screening information",
                "url_hint": "https://www.skincancer.org/",
            },
        ])

        return {
            "risk_level": risk_level,
            "predicted_class": predicted_class,
            "location": location,
            "visit_guidance": advice,
            "recommendations": recommendations,
            "disclaimer": (
                "This is educational guidance only. Always consult a licensed "
                "healthcare provider for medical decisions."
            ),
        }
