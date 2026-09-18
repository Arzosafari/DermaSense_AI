"""
Analysis History Service - Stores and retrieves skin analysis history for comparison.

This service enables users to track their skin analyses over time, allowing for
comparison of predictions and monitoring of changes in lesions.
"""
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

logger = logging.getLogger(__name__)


class AnalysisHistoryService:
    """Service for managing skin analysis history for users."""
    
    def __init__(self):
        self.logger = logger
        self.history_dir = "backend/analysis_history"
        os.makedirs(self.history_dir, exist_ok=True)
    
    def _get_user_history_path(self, user_id: str) -> str:
        """Get the file path for a user's analysis history."""
        return os.path.join(self.history_dir, f"{user_id}.json")
    
    def _load_user_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Load analysis history for a user."""
        path = self._get_user_history_path(user_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load history for user {user_id}: {e}")
        return []
    
    def _save_user_history(self, user_id: str, history: List[Dict[str, Any]]) -> bool:
        """Save analysis history for a user."""
        path = self._get_user_history_path(user_id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save history for user {user_id}: {e}")
            return False
    
    def save_analysis(
        self,
        user_id: str,
        analysis_data: Dict[str, Any],
        image_base64: Optional[str] = None
    ) -> str:
        """
        Save a new analysis to the user's history.
        
        Args:
            user_id: User identifier
            analysis_data: Analysis results including prediction, confidence, etc.
            image_base64: Base64 encoded image (optional, for storage)
            
        Returns:
            Analysis ID
        """
        logger.info(f"save_analysis called - explainability: {analysis_data.get('explainability', {})}")
        
        history = self._load_user_history(user_id)
        
        analysis_id = str(uuid.uuid4())
        
        analysis_record = {
            "analysis_id": analysis_id,
            "timestamp": analysis_data.get("timestamp", datetime.now().isoformat()),
            "predicted_class": analysis_data.get("model", {}).get("predicted_class"),
            "confidence": analysis_data.get("model", {}).get("confidence"),
            "top3_predictions": analysis_data.get("model", {}).get("top3_predictions", []),
            "screening_score": analysis_data.get("risk_assessment", {}).get("screening_score"),
            "screening_level": analysis_data.get("risk_assessment", {}).get("screening_level"),
            "user_symptoms": analysis_data.get("input", {}).get("message"),
            "medical_context": analysis_data.get("profile_context"),
            "image_stored": image_base64 is not None,
            "structured_analysis": analysis_data,  # Store the full structured analysis
            # Note: We don't store the full image by default to save space
            # In production, this would use proper image storage
        }
        
        logger.info(f"analysis_record created with explainability: {analysis_record.get('structured_analysis', {}).get('explainability', {})}")
        
        # Add to history (most recent first)
        history.insert(0, analysis_record)
        
        # Limit history size (keep last 50 analyses)
        if len(history) > 50:
            history = history[:50]
        
        if self._save_user_history(user_id, history):
            logger.info(f"Saved analysis {analysis_id} for user {user_id}")
            return analysis_id
        else:
            logger.error(f"Failed to save analysis for user {user_id}")
            return ""
    
    def get_user_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get analysis history for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of records to return
            
        Returns:
            List of analysis records
        """
        history = self._load_user_history(user_id)
        return history[:limit]
    
    def get_analysis(self, user_id: str, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific analysis by ID.
        
        Args:
            user_id: User identifier
            analysis_id: Analysis ID
            
        Returns:
            Analysis record or None if not found
        """
        history = self._load_user_history(user_id)
        for analysis in history:
            if analysis.get("analysis_id") == analysis_id:
                return analysis
        return None
    
    def compare_analyses(
        self, 
        user_id: str, 
        analysis_id_1: str, 
        analysis_id_2: str
    ) -> Optional[Dict[str, Any]]:
        """
        Compare two analyses and highlight differences.
        
        Args:
            user_id: User identifier
            analysis_id_1: First analysis ID
            analysis_id_2: Second analysis ID
            
        Returns:
            Comparison result or None if analyses not found
        """
        analysis_1 = self.get_analysis(user_id, analysis_id_1)
        analysis_2 = self.get_analysis(user_id, analysis_id_2)
        
        if not analysis_1 or not analysis_2:
            return None
        
        comparison = {
            "analysis_1": {
                "id": analysis_id_1,
                "timestamp": analysis_1.get("timestamp"),
                "predicted_class": analysis_1.get("predicted_class") or analysis_1.get("model", {}).get("predicted_class"),
                "confidence": analysis_1.get("confidence") or analysis_1.get("model", {}).get("confidence", 0),
                "screening_level": analysis_1.get("screening_level") or analysis_1.get("risk_assessment", {}).get("screening_level")
            },
            "analysis_2": {
                "id": analysis_id_2,
                "timestamp": analysis_2.get("timestamp"),
                "predicted_class": analysis_2.get("predicted_class") or analysis_2.get("model", {}).get("predicted_class"),
                "confidence": analysis_2.get("confidence") or analysis_2.get("model", {}).get("confidence", 0),
                "screening_level": analysis_2.get("screening_level") or analysis_2.get("risk_assessment", {}).get("screening_level")
            },
            "differences": []
        }
        
        # Check for class change
        predicted_class_1 = analysis_1.get("predicted_class") or analysis_1.get("model", {}).get("predicted_class")
        predicted_class_2 = analysis_2.get("predicted_class") or analysis_2.get("model", {}).get("predicted_class")
        
        if predicted_class_1 != predicted_class_2:
            comparison["differences"].append({
                "type": "class_change",
                "from": predicted_class_1,
                "to": predicted_class_2,
                "significance": "high" if self._is_malignant_change(
                    predicted_class_1,
                    predicted_class_2
                ) else "medium"
            })
        
        # Check for confidence change
        confidence_1 = analysis_1.get("confidence") or analysis_1.get("model", {}).get("confidence", 0)
        confidence_2 = analysis_2.get("confidence") or analysis_2.get("model", {}).get("confidence", 0)
        
        conf_diff = abs(confidence_1 - confidence_2)
        if conf_diff > 0.2:  # More than 20% difference
            comparison["differences"].append({
                "type": "confidence_change",
                "from": f"{confidence_1:.2%}",
                "to": f"{confidence_2:.2%}",
                "difference": f"{conf_diff:.2%}"
            })
        
        # Check for screening level change
        screening_level_1 = analysis_1.get("screening_level") or analysis_1.get("risk_assessment", {}).get("screening_level")
        screening_level_2 = analysis_2.get("screening_level") or analysis_2.get("risk_assessment", {}).get("screening_level")
        
        if screening_level_1 != screening_level_2:
            comparison["differences"].append({
                "type": "screening_level_change",
                "from": screening_level_1,
                "to": screening_level_2
            })
        
        # Time difference
        try:
            time1 = datetime.fromisoformat(analysis_1.get("timestamp", ""))
            time2 = datetime.fromisoformat(analysis_2.get("timestamp", ""))
            time_diff = abs((time2 - time1).days)
            comparison["time_difference_days"] = time_diff
        except:
            pass
        
        return comparison
    
    def _is_malignant_change(self, class1: str, class2: str) -> bool:
        """Check if the class change involves malignancy."""
        malignant_keywords = ["melanoma", "carcinoma", "malignant"]
        class1_malignant = any(kw in class1.lower() for kw in malignant_keywords)
        class2_malignant = any(kw in class2.lower() for kw in malignant_keywords)
        return class1_malignant != class2_malignant
    
    def get_trend_analysis(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Analyze trends in user's analyses over time.
        
        Args:
            user_id: User identifier
            days: Number of days to look back
            
        Returns:
            Trend analysis results
        """
        history = self._load_user_history(user_id)
        
        # Filter by date
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        recent_analyses = [
            a for a in history 
            if datetime.fromisoformat(a.get("timestamp", "")).timestamp() > cutoff_date
        ]
        
        if not recent_analyses:
            return {
                "message": f"No analyses found in the last {days} days",
                "total_analyses": len(history)
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
            "trend": self._calculate_trend(screening_scores),
            "recommendation": self._get_trend_recommendation(screening_scores, classes)
        }
    
    def _calculate_trend(self, scores: List[float]) -> str:
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
    
    def _get_trend_recommendation(self, scores: List[float], classes: List[str]) -> str:
        """Get recommendation based on trend."""
        trend = self._calculate_trend(scores)
        
        if trend == "increasing":
            return "Screening scores have been increasing. Consider professional evaluation if this trend continues."
        elif trend == "decreasing":
            return "Screening scores have been decreasing. Continue regular monitoring."
        else:
            return "Screening scores have been stable. Continue regular monitoring and report any changes."
    
    def delete_analysis(self, user_id: str, analysis_id: str) -> bool:
        """
        Delete a specific analysis from history.
        
        Args:
            user_id: User identifier
            analysis_id: Analysis ID to delete
            
        Returns:
            True if deleted, False otherwise
        """
        history = self._load_user_history(user_id)
        original_length = len(history)
        
        history = [a for a in history if a.get("analysis_id") != analysis_id]
        
        if len(history) < original_length:
            return self._save_user_history(user_id, history)
        
        return False
    
    def clear_user_history(self, user_id: str) -> bool:
        """
        Clear all analysis history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if cleared, False otherwise
        """
        path = self._get_user_history_path(user_id)
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception as e:
            logger.error(f"Failed to clear history for user {user_id}: {e}")
            return False


# Global instance
analysis_history_service = AnalysisHistoryService()