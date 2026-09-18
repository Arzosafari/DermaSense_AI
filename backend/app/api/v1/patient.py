# backend/app/api/v1/patient.py - MySQL Database Version
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import logging
import json
import os
from datetime import datetime

from app.api.v1.auth import require_user, get_current_user
from app.core.database_service import database_service
from app.core.pdf_report_service import pdf_report_service
from app.core.database import is_database_initialized
from app.core.analysis_history_service import AnalysisHistoryService
from app.core.domain_filter import detect_language

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patient", tags=["Patient Profile"])

# Initialize analysis history service
analysis_history_service = AnalysisHistoryService()

PROFILES_DIR = "backend/patient_profiles"
os.makedirs(PROFILES_DIR, exist_ok=True)

USE_DATABASE = is_database_initialized()

# Fallback functions for file-based storage
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

def _compute_risk_factors(profile: dict) -> List[str]:
    """Compute relevant risk factors for skin conditions based on profile."""
    import json
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
    chronic_conditions = profile.get("chronic_conditions", [])
    if chronic_conditions:
        if isinstance(chronic_conditions, str):
            try:
                chronic_conditions = json.loads(chronic_conditions)
            except:
                chronic_conditions = []
        if "diabetes" in [c.lower() for c in chronic_conditions]:
            risk_factors.append("Diabetes - higher risk of skin infections")
    
    # Skin type considerations
    if profile.get("skin_type") in ["fair", "very fair"]:
        risk_factors.append("Fair skin - higher UV sensitivity")
    
    return risk_factors

def _convert_list_to_string(value):
    """Convert list to JSON string for database storage."""
    if isinstance(value, list):
        import json
        return json.dumps(value)
    return value

def _convert_string_to_list(value):
    """Convert JSON string to list for API response."""
    if isinstance(value, str):
        try:
            import json
            return json.loads(value)
        except:
            return value
    return value

@router.post("/profile")
async def save_profile(data: ProfileRequest, user: dict = Depends(require_user)):
    """Save or update user profile."""
    user_id = user["username"]
    
    if USE_DATABASE:
        # Get existing profile
        existing_profile = database_service.get_user_profile(user_id) or {}
        
        # Convert profile data to dict and handle list fields
        profile_dict = data.profile.dict(exclude_unset=True)
        profile_dict_for_db = {}
        for key, value in profile_dict.items():
            profile_dict_for_db[key] = _convert_list_to_string(value)
        
        # Merge with existing profile
        merged_profile = {**existing_profile, **profile_dict_for_db}
        merged_profile["username"] = user_id
        
        # Compute risk factors
        risk_factors = _compute_risk_factors(merged_profile)
        merged_profile["computed_risk_factors"] = json.dumps(risk_factors)
        
        # Update profile in database
        updated_profile = database_service.update_user_profile(user_id, merged_profile)
        
        # Convert list fields back for response
        response_profile = updated_profile.copy()
        for key in response_profile:
            if key in ['previous_skin_conditions', 'chronic_conditions', 'current_medications', 
                       'allergies', 'skin_concerns', 'previous_examinations', 'computed_risk_factors']:
                response_profile[key] = _convert_string_to_list(response_profile[key])
    else:
        # File-based storage fallback
        existing = _load_profile(user_id) or {}
        profile_dict = data.profile.dict(exclude_unset=True)
        merged_profile = {**existing, **profile_dict}
        merged_profile["user_id"] = user_id
        merged_profile["updated_at"] = datetime.now().isoformat()
        merged_profile["created_at"] = existing.get("created_at", datetime.now().isoformat())
        
        risk_factors = _compute_risk_factors(merged_profile)
        merged_profile["computed_risk_factors"] = risk_factors
        
        _save_profile(user_id, merged_profile)
        response_profile = merged_profile
    
    # Convert profile data to dict and handle list fields
    profile_dict = data.profile.dict(exclude_unset=True)
    profile_dict_for_db = {}
    for key, value in profile_dict.items():
        profile_dict_for_db[key] = _convert_list_to_string(value)
    
    # Merge with existing profile
    merged_profile = {**existing_profile, **profile_dict_for_db}
    merged_profile["username"] = user_id
    
    # Compute risk factors
    risk_factors = _compute_risk_factors(merged_profile)
    import json
    merged_profile["computed_risk_factors"] = json.dumps(risk_factors)
    
    # Update profile in database
    updated_profile = database_service.update_user_profile(user_id, merged_profile)
    
    # Convert list fields back for response
    response_profile = updated_profile.copy()
    for key in response_profile:
        if key in ['previous_skin_conditions', 'chronic_conditions', 'current_medications', 
                   'allergies', 'skin_concerns', 'previous_examinations', 'computed_risk_factors']:
            response_profile[key] = _convert_string_to_list(response_profile[key])
    
    return {
        "message": "Profile saved successfully",
        "profile": response_profile,
        "risk_factors": risk_factors
    }

@router.get("/profile")
async def get_profile(user: dict = Depends(require_user)):
    """Get current user's profile."""
    user_id = user["username"]
    
    if USE_DATABASE:
        profile = database_service.get_user_profile(user_id)
    else:
        profile = _load_profile(user_id)
    
    if not profile:
        return {
            "profile": None,
            "message": "No profile found",
            "user_id": user_id
        }
    
    # Convert list fields for response
    response_profile = profile.copy()
    for key in response_profile:
        if key in ['previous_skin_conditions', 'chronic_conditions', 'current_medications', 
                   'allergies', 'skin_concerns', 'previous_examinations', 'computed_risk_factors']:
            response_profile[key] = _convert_string_to_list(response_profile[key])
    
    return {
        "profile": response_profile,
        "user_id": user_id
    }

@router.put("/profile")
async def update_profile(data: ProfileRequest, user: dict = Depends(require_user)):
    """Update user profile (partial update)."""
    user_id = user["username"]
    
    if USE_DATABASE:
        # Get existing profile
        existing_profile = database_service.get_user_profile(user_id) or {}
        
        # Convert profile data to dict and handle list fields
        profile_dict = data.profile.dict(exclude_unset=True)
        profile_dict_for_db = {}
        for key, value in profile_dict.items():
            profile_dict_for_db[key] = _convert_list_to_string(value)
        
        # Merge with existing profile
        merged_profile = {**existing_profile, **profile_dict_for_db}
        merged_profile["username"] = user_id
        
        # Recompute risk factors
        risk_factors = _compute_risk_factors(merged_profile)
        merged_profile["computed_risk_factors"] = json.dumps(risk_factors)
        
        # Update profile in database
        updated_profile = database_service.update_user_profile(user_id, merged_profile)
        
        # Convert list fields back for response
        response_profile = updated_profile.copy()
        for key in response_profile:
            if key in ['previous_skin_conditions', 'chronic_conditions', 'current_medications', 
                       'allergies', 'skin_concerns', 'previous_examinations', 'computed_risk_factors']:
                response_profile[key] = _convert_string_to_list(response_profile[key])
    else:
        # File-based storage fallback
        existing = _load_profile(user_id) or {}
        profile_dict = data.profile.dict(exclude_unset=True)
        merged_profile = {**existing, **profile_dict}
        merged_profile["user_id"] = user_id
        merged_profile["updated_at"] = datetime.now().isoformat()
        merged_profile["created_at"] = existing.get("created_at", datetime.now().isoformat())
        
        risk_factors = _compute_risk_factors(merged_profile)
        merged_profile["computed_risk_factors"] = risk_factors
        
        _save_profile(user_id, merged_profile)
        response_profile = merged_profile
    
    return {
        "message": "Profile updated successfully",
        "profile": response_profile,
        "risk_factors": risk_factors
    }
    
    return {
        "message": "Profile updated successfully",
        "profile": response_profile,
        "risk_factors": risk_factors
    }

@router.delete("/profile")
async def delete_profile(user: dict = Depends(require_user)):
    """Delete user profile."""
    user_id = user["username"]
    
    # Set profile to empty by updating with empty dict
    database_service.update_user_profile(user_id, {"username": user_id})
    
    return {"message": "Profile deleted successfully", "user_id": user_id}


@router.get("/debug/database-status")
async def debug_database_status():
    """Debug endpoint to check database status"""
    from app.core.database import is_database_initialized
    return {
        "USE_DATABASE": USE_DATABASE,
        "database_initialized": is_database_initialized(),
        "message": "Database fallback mechanism active" if not USE_DATABASE else "MySQL database connected"
    }


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
        logger.info(f"Fetching analysis history for user: {user_id}, USE_DATABASE: {USE_DATABASE}")
        history = analysis_history_service.get_user_history(user_id, limit)
        logger.info(f"Retrieved {len(history)} history records for user {user_id}")
        logger.info(f"History sample: {history[:2] if history else 'Empty'}")
        return {
            "user_id": user_id,
            "history": history,
            "total": len(history)
        }
    except Exception as e:
        logger.error(f"Error fetching history for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis-history/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    user: dict = Depends(require_user)
):
    """Get a specific analysis by ID."""
    user_id = user["username"]
    
    if USE_DATABASE:
        analysis = database_service.get_screening_by_id(user_id, analysis_id)
    else:
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
    
    analysis_1 = database_service.get_screening_by_id(user_id, request.analysis_id_1)
    analysis_2 = database_service.get_screening_by_id(user_id, request.analysis_id_2)
    
    if not analysis_1 or not analysis_2:
        raise HTTPException(status_code=404, detail="One or both analyses not found")
    
    # Build comparison
    comparison = {
        "analysis_1": {
            "id": request.analysis_id_1,
            "timestamp": analysis_1.get("timestamp"),
            "predicted_class": analysis_1.get("predicted_class") or analysis_1.get("structured_analysis", {}).get("model", {}).get("predicted_class"),
            "confidence": analysis_1.get("confidence") or analysis_1.get("structured_analysis", {}).get("model", {}).get("confidence", 0),
            "screening_level": analysis_1.get("screening_level") or analysis_1.get("structured_analysis", {}).get("risk_assessment", {}).get("screening_level")
        },
        "analysis_2": {
            "id": request.analysis_id_2,
            "timestamp": analysis_2.get("timestamp"),
            "predicted_class": analysis_2.get("predicted_class") or analysis_2.get("structured_analysis", {}).get("model", {}).get("predicted_class"),
            "confidence": analysis_2.get("confidence") or analysis_2.get("structured_analysis", {}).get("model", {}).get("confidence", 0),
            "screening_level": analysis_2.get("screening_level") or analysis_2.get("structured_analysis", {}).get("risk_assessment", {}).get("screening_level")
        },
        "differences": []
    }
    
    # Check for class change
    predicted_class_1 = analysis_1.get("predicted_class") or analysis_1.get("structured_analysis", {}).get("model", {}).get("predicted_class")
    predicted_class_2 = analysis_2.get("predicted_class") or analysis_2.get("structured_analysis", {}).get("model", {}).get("predicted_class")
    
    if predicted_class_1 != predicted_class_2:
        comparison["differences"].append({
            "type": "class_change",
            "from": predicted_class_1,
            "to": predicted_class_2,
            "significance": "high" if _is_malignant_change(predicted_class_1, predicted_class_2) else "medium"
        })
    
    # Check for confidence change
    confidence_1 = analysis_1.get("confidence") or analysis_1.get("structured_analysis", {}).get("model", {}).get("confidence", 0)
    confidence_2 = analysis_2.get("confidence") or analysis_2.get("structured_analysis", {}).get("model", {}).get("confidence", 0)
    
    conf_diff = abs(confidence_1 - confidence_2)
    if conf_diff > 0.2:  # More than 20% difference
        comparison["differences"].append({
            "type": "confidence_change",
            "from": f"{confidence_1:.2%}",
            "to": f"{confidence_2:.2%}",
            "difference": f"{conf_diff:.2%}"
        })
    
    # Check for screening level change
    screening_level_1 = analysis_1.get("screening_level") or analysis_1.get("structured_analysis", {}).get("risk_assessment", {}).get("screening_level")
    screening_level_2 = analysis_2.get("screening_level") or analysis_2.get("structured_analysis", {}).get("risk_assessment", {}).get("screening_level")
    
    if screening_level_1 != screening_level_2:
        comparison["differences"].append({
            "type": "screening_level_change",
            "from": screening_level_1,
            "to": screening_level_2
        })
    
    # Time difference
    try:
        from datetime import datetime
        time1 = datetime.fromisoformat(analysis_1.get("timestamp", ""))
        time2 = datetime.fromisoformat(analysis_2.get("timestamp", ""))
        time_diff = abs((time2 - time1).days)
        comparison["time_difference_days"] = time_diff
    except:
        pass
    
    return comparison

def _is_malignant_change(class1: str, class2: str) -> bool:
    """Check if the class change involves malignancy."""
    malignant_keywords = ["melanoma", "carcinoma", "malignant"]
    class1_malignant = any(kw in class1.lower() for kw in malignant_keywords)
    class2_malignant = any(kw in class2.lower() for kw in malignant_keywords)
    return class1_malignant != class2_malignant

@router.get("/analysis-history/trend")
async def get_trend_analysis(
    days: int = 30,
    user: dict = Depends(require_user)
):
    """Get trend analysis for user's analyses."""
    user_id = user["username"]
    try:
        # Get all history (not limited) for trend analysis
        all_history = database_service.get_screening_history(user_id, limit=1000)
        
        # Filter by date
        from datetime import datetime
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        recent_analyses = [
            a for a in all_history 
            if datetime.fromisoformat(a.get("timestamp", "")).timestamp() > cutoff_date
        ]
        
        if not recent_analyses:
            return {
                "message": f"No analyses found in the last {days} days",
                "total_analyses": len(all_history)
            }
        
        # Calculate statistics
        classes = [a.get("predicted_class") for a in recent_analyses]
        confidences = [a.get("confidence", 0) for a in recent_analyses]
        screening_scores = [a.get("screening_score", 0) for a in recent_analyses]
        
        # Most common predictions
        from collections import Counter
        class_counts = Counter(classes)
        
        return {
            "period_days": days,
            "total_analyses": len(recent_analyses),
            "average_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "average_screening_score": sum(screening_scores) / len(screening_scores) if screening_scores else 0,
            "most_common_classes": class_counts.most_common(3),
            "trend": _calculate_trend(screening_scores),
            "recommendation": _get_trend_recommendation(screening_scores, classes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _calculate_trend(scores: List[float]) -> str:
    """Calculate trend direction from scores."""
    if len(scores) < 2:
        return "insufficient_data"
    
    # Simple linear trend
    recent_avg = sum(scores[-3:]) / min(3, len(scores))
    earlier_avg = sum(scores[:-3]) / max(1, len(scores) - 3) if len(scores) > 3 else scores[0]
    
    if recent_avg > earlier_avg + 5:
        return "increasing"
    elif recent_avg < earlier_avg - 5:
        return "decreasing"
    else:
        return "stable"

def _get_trend_recommendation(scores: List[float], classes: List[str]) -> str:
    """Get recommendation based on trend."""
    trend = _calculate_trend(scores)
    
    if trend == "increasing":
        return "Screening scores have been increasing. Consider professional evaluation if this trend continues."
    elif trend == "decreasing":
        return "Screening scores have been decreasing. Continue regular monitoring."
    else:
        return "Screening scores have been stable. Continue regular monitoring and report any changes."

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
    success = database_service.clear_screening_history(user_id)
    
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
    analysis = database_service.get_screening_by_id(user_id, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Skip database cache check to allow language regeneration
    # Reports will be regenerated based on detected language
    
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
    
    # Detect language from user message
    user_message = analysis.get("user_symptoms", "")
    language = "english"
    if user_message:
        language = detect_language(user_message)
        logger.info(f"PDF language detected from user message: {language}")
    
    report_result = pdf_report_service.generate_report(analysis_data, language=language)
    
    if report_result.get("success"):
        # Save report record to database
        database_service.save_pdf_report(analysis_id, user_id, report_result.get("report_path"))
        
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
    
    print(f"DEBUG: PDF download request for user={user_id}, analysis_id={analysis_id}")
    
    # Verify analysis ownership
    if USE_DATABASE:
        print(f"DEBUG: Using database to lookup analysis")
        analysis = database_service.get_screening_by_id(user_id, analysis_id)
        print(f"DEBUG: Database lookup result: {analysis is not None}")
    else:
        print(f"DEBUG: Using file storage to lookup analysis")
        analysis = analysis_history_service.get_analysis(user_id, analysis_id)
        print(f"DEBUG: File lookup result: {analysis is not None}")
    
    if not analysis:
        print(f"DEBUG: Analysis not found: user_id={user_id}, analysis_id={analysis_id}")
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get or generate report
    if USE_DATABASE:
        report_info = database_service.get_pdf_report(analysis_id)
    else:
        report_info = None  # File-based doesn't store report metadata
    
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
        
        # Detect language from user message
        user_message = analysis.get("user_symptoms", "")
        language = "english"
        if user_message:
            language = detect_language(user_message)
            logger.info(f"PDF language detected from user message: {language}")
        
        report_result = pdf_report_service.generate_report(analysis_data, language=language)
        if not report_result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to generate report")
        
        # Save report record if using database
        if USE_DATABASE:
            try:
                database_service.save_pdf_report(analysis_id, user_id, report_result.get("report_path"))
                report_info = database_service.get_pdf_report(analysis_id)
                if not report_info:
                    # Fallback to use generated path directly
                    report_info = {"report_path": report_result.get("report_path")}
            except Exception as e:
                logger.warning(f"Database save failed: {e}, using generated path directly")
                report_info = {"report_path": report_result.get("report_path")}
        else:
            # For file-based, use the generated report path directly
            report_info = {"report_path": report_result.get("report_path")}
    
    # Return file with proper headers
    report_path = report_info["report_path"]
    filename = f"SmartHealth_Analysis_{analysis_id}.pdf"
    
    return FileResponse(
        path=report_path,
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )
