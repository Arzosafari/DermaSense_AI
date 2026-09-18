"""
Test Persian PDF generation with arabic-reshaper + python-bidi
"""
import sys
sys.path.insert(0, "D:\\final-project\\v7-added edit profile\\v4\\SmartHealth-LLM\\backend")

from app.core.pdf_report_service import PDFReportService

# Create service
service = PDFReportService()

# Test data
test_data = {
    "analysis_id": "test_reshaper_123",
    "timestamp": "2024-01-15 10:30:00",
    "user_id": "user_123",
    "profile_context": {
        "age": 35,
        "skin_type": "Type II",
        "medical_history": ["None"],
        "allergies": ["None"]
    },
    "model": {
        "name": "PanDerm",
        "predicted_class": "Melanoma",
        "confidence": 0.92,
        "top3_predictions": [
            {"class": "Melanoma", "probability": 0.92},
            {"class": "BCC", "probability": 0.05},
            {"class": "AK", "probability": 0.03}
        ],
        "all_probabilities": {
            "Melanoma": 0.92,
            "BCC": 0.05,
            "AK": 0.03
        }
    },
    "risk_assessment": {
        "screening_level": "High Risk",
        "screening_score": 92,
        "urgency_message": "Requires immediate dermatologist consultation"
    },
    "symptom_analysis": {
        "symptoms": ["Irregular borders", "Color variation"]
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
        "timeframe": "Immediate consultation",
        "specialist": "Dermatologist",
        "visit_type": "Urgent examination"
    },
    "disclaimer": "This is a test disclaimer"
}

# Generate Persian PDF
print("Generating Persian PDF with arabic-reshaper + python-bidi...")
result = service.generate_report(test_data, language="persian")

if result["success"]:
    print(f"✓ Persian PDF generated successfully!")
    print(f"  Path: {result['report_path']}")
    print(f"  Language: {result['language']}")
else:
    print(f"✗ Failed to generate Persian PDF: {result['error']}")
