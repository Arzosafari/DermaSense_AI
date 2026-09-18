# backend/app/api/v1/patient.py
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import os
import logging
from datetime import datetime
from app.api.v1.auth import require_user, get_current_user
from app.core.analysis_history_service import analysis_history_service
from app.core.pdf_report_service import pdf_report_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patient", tags=["Patient Profile"])

PROFILES_DIR = "backend/patient_profiles"
os.makedirs(PROFILES_DIR, exist_ok=True)

class CompareAnalysesRequest(BaseModel):
    analysis_id_1: str
    analysis_id_2: str

class MedicalProfile(BaseModel):
    # Basic demographics
    age: Optional[int] = None
    gender: Optional[str] = None
    
    # Skin-related information
    skin_type: Optional[str] = None  # e.g., "fair", "medium", "dark", "very dark"
    sun_exposure: Optional[str] = None  # e.g., "minimal", "moderate", "high"
    sunburn_history: Optional[bool] = None
    tanning_bed_use: Optional[bool] = None
    
    # Medical history
    previous_skin_conditions: Optional[List[str]] = None  # e.g., ["eczema", "psoriasis"]
    previous_melanoma: Optional[bool] = None
    previous_skin_cancer: Optional[bool] = None
    family_history_melanoma: Optional[bool] = None
    family_history_skin_cancer: Optional[bool] = None
    
    # Current health
    chronic_conditions: Optional[List[str]] = None  # e.g., ["diabetes", "autoimmune"]
    current_medications: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    
    # Lifestyle factors
    smoking: Optional[bool] = None
    alcohol_consumption: Optional[str] = None  # e.g., "none", "moderate", "heavy"
    exercise_frequency: Optional[str] = None  # e.g., "sedentary", "moderate", "active"
    
    # Specific skin concerns
    skin_concerns: Optional[List[str]] = None  # e.g., ["changing mole", "new growth"]
    previous_examinations: Optional[List[str]] = None  # e.g., ["dermatologist visit 2023"]
    
    # Other relevant information
    other_medical_context: Optional[str] = None

class ProfileRequest(BaseModel):
    profile: MedicalProfile

def _get_profile_path(user_id: str) -> str:
    return os.path.join(PROFILES_DIR, f"{user_id}.json")

def _load_profile(user_id: str) -> dict | None:
    path = _get_profile_path(user_id)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def _save_profile(user_id: str, data: dict):
    path = _get_profile_path(user_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _compute_risk_factors(profile: dict) -> List[str]:
    """Compute relevant risk factors for skin conditions based on profile."""
    risk_factors = []
    
    # Melanoma risk factors
    if profile.get("family_history_melanoma"):
        risk_factors.append("Family history of melanoma")
    if profile.get("previous_melanoma"):
        risk_factors.append("Previous melanoma diagnosis")
    if profile.get("previous_skin_cancer"):
        risk_factors.append("Previous skin cancer diagnosis")
    if profile.get("sunburn_history"):
        risk_factors.append("History of sunburns")
    if profile.get("tanning_bed_use"):
        risk_factors.append("Tanning bed use")
    if profile.get("sun_exposure") == "high":
        risk_factors.append("High sun exposure")
    
    # General health factors
    if profile.get("smoking"):
        risk_factors.append("Smoking - may affect skin healing")
    if "diabetes" in [c.lower() for c in profile.get("chronic_conditions", [])]:
        risk_factors.append("Diabetes - higher risk of skin infections")
    
    # Skin type considerations
    if profile.get("skin_type") in ["fair", "very fair"]:
        risk_factors.append("Fair skin - higher UV sensitivity")
    
    return risk_factors

@router.post("/profile")
async def save_profile(data: ProfileRequest, user: dict = Depends(require_user)):
    """Save or update user profile."""
    user_id = user["username"]
    existing = _load_profile(user_id) or {}
    
    # Merge new data with existing profile
    profile_dict = data.profile.dict(exclude_unset=True)
    merged_profile = {**existing, **profile_dict}
    
    # Add metadata
    merged_profile["user_id"] = user_id
    merged_profile["updated_at"] = datetime.now().isoformat()
    merged_profile["created_at"] = existing.get("created_at", datetime.now().isoformat())
    
    # Compute risk factors
    risk_factors = _compute_risk_factors(merged_profile)
    merged_profile["computed_risk_factors"] = risk_factors
    
    _save_profile(user_id, merged_profile)
    
    return {
        "message": "Profile saved successfully",
        "profile": merged_profile,
        "risk_factors": risk_factors
    }

@router.get("/profile")
async def get_profile(user: dict = Depends(require_user)):
    """Get current user's profile."""
    user_id = user["username"]
    profile = _load_profile(user_id)
    
    if not profile:
        return {
            "profile": None,
            "message": "No profile found",
            "user_id": user_id
        }
    
    # Ensure user_id matches
    profile["user_id"] = user_id
    
    return {
        "profile": profile,
        "user_id": user_id
    }

@router.put("/profile")
async def update_profile(data: ProfileRequest, user: dict = Depends(require_user)):
    """Update user profile (partial update)."""
    user_id = user["username"]
    existing = _load_profile(user_id) or {}
    
    # Merge new data with existing profile
    profile_dict = data.profile.dict(exclude_unset=True)
    merged_profile = {**existing, **profile_dict}
    
    # Add metadata
    merged_profile["user_id"] = user_id
    merged_profile["updated_at"] = datetime.now().isoformat()
    merged_profile["created_at"] = existing.get("created_at", datetime.now().isoformat())
    
    # Recompute risk factors
    risk_factors = _compute_risk_factors(merged_profile)
    merged_profile["computed_risk_factors"] = risk_factors
    
    _save_profile(user_id, merged_profile)
    
    return {
        "message": "Profile updated successfully",
        "profile": merged_profile,
        "risk_factors": risk_factors
    }

@router.delete("/profile")
async def delete_profile(user: dict = Depends(require_user)):
    """Delete user profile."""
    user_id = user["username"]
    path = _get_profile_path(user_id)
    
    if os.path.exists(path):
        os.remove(path)
        return {"message": "Profile deleted successfully", "user_id": user_id}
    
    return {"message": "No profile to delete", "user_id": user_id}


# ============================================================
# Analysis History Endpoints
# ============================================================

@router.get("/analysis-history")
async def get_analysis_history(
    limit: int = 20,
    user: dict = Depends(require_user)
):
    """Get user's analysis history."""
    user_id = user["username"]
    try:
        history = analysis_history_service.get_user_history(user_id, limit)
        return {
            "user_id": user_id,
            "history": history,
            "total": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis-history/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    user: dict = Depends(require_user)
):
    """Get a specific analysis by ID."""
    user_id = user["username"]
    analysis = analysis_history_service.get_analysis(user_id, analysis_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return {
        "user_id": user_id,
        "analysis": analysis
    }


@router.post("/analysis-history/compare")
async def compare_analyses(
    request: CompareAnalysesRequest,
    user: dict = Depends(require_user)
):
    """Compare two analyses."""
    user_id = user["username"]
    comparison = analysis_history_service.compare_analyses(user_id, request.analysis_id_1, request.analysis_id_2)
    
    if not comparison:
        raise HTTPException(status_code=404, detail="One or both analyses not found")
    
    return comparison


@router.get("/analysis-history/trend")
async def get_trend_analysis(
    days: int = 30,
    user: dict = Depends(require_user)
):
    """Get trend analysis for user's analyses."""
    user_id = user["username"]
    try:
        trend = analysis_history_service.get_trend_analysis(user_id, days)
        return {
            "user_id": user_id,
            "trend": trend
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/analysis-history/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    user: dict = Depends(require_user)
):
    """Delete a specific analysis from history."""
    user_id = user["username"]
    success = analysis_history_service.delete_analysis(user_id, analysis_id)
    
    if success:
        return {"message": "Analysis deleted successfully", "analysis_id": analysis_id}
    else:
        raise HTTPException(status_code=404, detail="Analysis not found or already deleted")


@router.delete("/analysis-history")
async def clear_analysis_history(user: dict = Depends(require_user)):
    """Clear all analysis history for user."""
    user_id = user["username"]
    success = analysis_history_service.clear_user_history(user_id)
    
    if success:
        return {"message": "Analysis history cleared successfully", "user_id": user_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear history")


# ============================================================
# PDF Report Endpoints
# ============================================================

@router.get("/analysis-history/{analysis_id}/report")
async def get_analysis_report(
    analysis_id: str,
    user: dict = Depends(require_user)
):
    """Get or generate PDF report for a specific analysis."""
    user_id = user["username"]
    
    # Get the analysis first to verify ownership
    analysis = analysis_history_service.get_analysis(user_id, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Check if report already exists
    existing_report = pdf_report_service.get_report(analysis_id)
    if existing_report:
        return {
            "user_id": user_id,
            "analysis_id": analysis_id,
            "report": existing_report
        }
    
    # Generate new report from analysis data
    analysis_data = analysis.get("structured_analysis", {})
    if not analysis_data:
        # Try to construct from legacy format
        analysis_data = {
            "analysis_id": analysis_id,
            "timestamp": analysis.get("timestamp"),
            "user_id": user_id,
            "input": {
                "image": analysis.get("image_stored", False),
                "message": analysis.get("user_symptoms", "")
            },
            "profile_context": analysis.get("medical_context", {}),
            "model": {
                "name": "PanDerm",
                "predicted_class": analysis.get("predicted_class"),
                "confidence": analysis.get("confidence"),
                "top3_predictions": analysis.get("top3_predictions", [])
            },
            "visual_analysis": {"available": False, "findings": []},
            "abcde": {"available": False, "score": 0, "criteria": {}},
            "risk_assessment": {
                "screening_score": analysis.get("screening_score"),
                "screening_level": analysis.get("screening_level"),
                "urgency_message": "See a dermatologist for evaluation"
            },
            "symptom_analysis": {
                "symptoms": [analysis.get("user_symptoms")] if analysis.get("user_symptoms") else [],
                "possible_conditions": []
            },
            "image_quality": {},
            "recommendations": {},
            "disclaimer": "This AI screening is for educational purposes only and is NOT a medical diagnosis."
        }
    
    report_result = pdf_report_service.generate_report(analysis_data)
    
    if report_result.get("success"):
        return {
            "user_id": user_id,
            "analysis_id": analysis_id,
            "report": report_result
        }
    else:
        raise HTTPException(status_code=500, detail=report_result.get("error", "Failed to generate report"))


@router.get("/analysis-history/{analysis_id}/report/download")
async def download_analysis_report(
    analysis_id: str,
    user: dict = Depends(require_user)
):
    """Download PDF report for a specific analysis."""
    user_id = user["username"]
    
    # Verify analysis ownership
    analysis = analysis_history_service.get_analysis(user_id, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get or generate report
    report_info = pdf_report_service.get_report(analysis_id)
    if not report_info:
        # Generate report on-demand
        analysis_data = analysis.get("structured_analysis", {})
        if not analysis_data:
            # Construct from legacy format
            analysis_data = {
                "analysis_id": analysis_id,
                "timestamp": analysis.get("timestamp"),
                "user_id": user_id,
                "input": {
                    "image": analysis.get("image_stored", False),
                    "message": analysis.get("user_symptoms", "")
                },
                "profile_context": analysis.get("medical_context", {}),
                "model": {
                    "name": "PanDerm",
                    "predicted_class": analysis.get("predicted_class"),
                    "confidence": analysis.get("confidence"),
                    "top3_predictions": analysis.get("top3_predictions", []),
                    "all_probabilities": analysis.get("all_probabilities", {})
                },
                "visual_analysis": {"available": False, "findings": []},
                "abcde": {"available": False, "score": 0, "criteria": {}},
                "risk_assessment": {
                    "screening_score": analysis.get("screening_score"),
                    "screening_level": analysis.get("screening_level"),
                    "urgency_message": "See a dermatologist for evaluation"
                },
                "explainability": analysis.get("explainability", {"available": False, "reason": "Not available in legacy format"}),
                "symptom_analysis": {
                    "symptoms": [analysis.get("user_symptoms")] if analysis.get("user_symptoms") else [],
                    "possible_conditions": []
                },
                "image_quality": {},
                "recommendations": {},
                "disclaimer": "This AI screening is for educational purposes only and is NOT a medical diagnosis."
            }
        
        report_result = pdf_report_service.generate_report(analysis_data)
        if not report_result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to generate report")
        
        report_info = pdf_report_service.get_report(analysis_id)
        if not report_info:
            raise HTTPException(status_code=500, detail="Report generation failed")
    
    # Return file with proper headers
    report_path = report_info["report_path"]
    filename = f"SmartHealth_Analysis_{analysis_id}.pdf"
    
    return FileResponse(
        path=report_path,
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )