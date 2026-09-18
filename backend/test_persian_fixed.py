"""
Test Persian PDF generation with fixed RTL handling
"""
import sys
sys.path.insert(0, "D:\\final-project\\v7-added edit profile\\v4\\SmartHealth-LLM\\backend")

from app.core.pdf_report_service import PDFReportService

# Create service
service = PDFReportService()

# Test data
test_data = {
    "analysis_id": "test_fixed_123",
    "timestamp": "2024-01-15 10:30:00",
    "user_id": "arj mahsa",
    "profile_context": {
        "age": 22,
        "skin_type": "oily",
        "medical_history": ["l", "a", "t", "e", "x"],
        "allergies": ["None"]
    },
    "model": {
        "name": "PanDerm",
        "predicted_class": "benign keratosis",
        "confidence": 0.8620,
        "top3_predictions": [
            {"class": "benign keratosis", "probability": 0.8620},
            {"class": "BCC", "probability": 0.05},
            {"class": "AK", "probability": 0.03}
        ],
        "all_probabilities": {
            "benign keratosis": 0.8620,
            "BCC": 0.05,
            "AK": 0.03
        }
    },
    "risk_assessment": {
        "screening_level": "low",
        "screening_score": 9,
        "urgency_message": "Routine skin check recommended; monitor for ABCDE changes"
    },
    "symptom_analysis": {
        "symptoms": ["دراد شراخ متسوپ", "کسیر یبایزرا"]
    },
    "abcde": {
        "available": True,
        "score": 4,
        "criteria": {
            "asymmetry": True,
            "border": True,
            "color": True,
            "diameter": False,
            "evolution": True
        }
    },
    "image_quality": {
        "acceptable": True
    },
    "recommendations": {
        "timeframe": "Within 1-2 weeks",
        "specialist": "Dermatologist",
        "visit_type": "Routine check"
    },
    "disclaimer": "This AI screening is for educational purposes only and is NOT a medical diagnosis."
}

# Generate Persian PDF
print("Generating Persian PDF with fixed RTL handling...")
result = service.generate_report(test_data, language="persian")

if result["success"]:
    print(f"✓ Persian PDF generated successfully!")
    print(f"  Path: {result['report_path']}")
    print(f"  Language: {result['language']}")
else:
    print(f"✗ Failed to generate Persian PDF: {result['error']}")
