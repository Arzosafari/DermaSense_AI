"""Malignancy risk scoring combining model confidence, class, profile, and ABCDE."""
from typing import Any, Dict, List, Optional

from app.utils.isic_classes import is_malignant, normalize_class_name


def compute_malignancy_risk(
    predicted_class: str,
    confidence: float,
    user_profile: Optional[Dict[str, Any]] = None,
    abcde_score: Optional[int] = None,
    top3: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Returns structured AI screening indicator for skin cancer triage.
    
    IMPORTANT: This is an AI-generated screening indicator, NOT a clinically 
    validated cancer-risk score. It combines model confidence with user-reported
    factors to suggest urgency for professional evaluation.
    
    Score 0-100; levels: low | medium | high | urgent
    """
    profile = user_profile or {}
    normalized = normalize_class_name(predicted_class)
    malignant = is_malignant(normalized)

    score = 0.0
    factors: List[str] = []

    # Model prediction weight (0-40)
    if malignant:
        score += 20 + (confidence * 20)
        factors.append(f"Malignant class predicted: {normalized} ({confidence:.0%})")
    else:
        score += confidence * 10
        if confidence > 0.7:
            factors.append(f"Benign class with high confidence: {normalized}")

    # Secondary malignant in top-3 (0-15)
    if top3:
        for pred in top3[1:3]:
            cls = normalize_class_name(pred.get("class", ""))
            conf = pred.get("confidence", 0)
            if is_malignant(cls) and conf > 0.15:
                score += conf * 15
                factors.append(f"Secondary malignant possibility: {cls} ({conf:.0%})")

    # ABCDE checklist (0-25) - only if user actually reported these features
    if abcde_score is not None and abcde_score > 0:
        abcde_contrib = min(abcde_score / 5.0 * 25, 25)
        score += abcde_contrib
        if abcde_score >= 3:
            factors.append(f"ABCDE warning signs reported ({abcde_score}/5)")

    # Patient profile risk factors (0-20) - only if user provided this information
    age = profile.get("age")
    if age and int(age) > 50:
        score += 5
        factors.append("Age over 50 (from profile)")
    if profile.get("skin_type") in ("fair", "very_fair", "type_i", "type_ii"):
        score += 5
        factors.append("Fair skin type (from profile)")
    conditions = str(profile.get("medical_conditions", "") or profile.get("chronic_conditions", "")).lower()
    if any(k in conditions for k in ("melanoma", "skin cancer", "family history")):
        score += 10
        factors.append("Personal/family history of skin cancer (from profile)")

    score = min(round(score), 100)

    if score >= 75 or (malignant and confidence >= 0.7):
        level = "urgent"
        urgency = "See a dermatologist within 1-2 weeks (sooner if lesion is changing)"
    elif score >= 50 or malignant:
        level = "high"
        urgency = "Schedule a dermatologist appointment within 2-4 weeks"
    elif score >= 25:
        level = "medium"
        urgency = "Monitor the lesion and consult a dermatologist if it changes"
    else:
        level = "low"
        urgency = "Routine skin check recommended; monitor for ABCDE changes"

    return {
        "screening_score": score,  # Changed from "risk_score" to be clearer
        "screening_level": level,  # Changed from "risk_level"
        "score_type": "AI-generated screening indicator",
        "score_disclaimer": "This is an AI screening indicator, not a clinically validated cancer-risk score",
        "is_malignant_prediction": malignant,
        "predicted_class": normalized,
        "confidence": confidence,
        "urgency_message": urgency,
        "factors": factors,  # Changed from "risk_factors"
        "abcde_applicable": normalized == "melanoma" or malignant,
    }
