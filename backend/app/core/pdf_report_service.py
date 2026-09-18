"""
PDF Report Service - Generates medical screening reports from analysis data.

This service creates professional PDF reports for skin lesion analysis,
generating them deterministically from stored analysis data to avoid
multiple LLM calls and ensure consistency.

Note: PDF reports are generated in English for technical consistency and 
font compatibility. 
and analysis text.
"""
import logging
import os
import base64
import io
from datetime import datetime
from typing import Dict, Any, Optional
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

logger = logging.getLogger(__name__)

# Register Persian font globally if available
try:
    tahoma_path = "C:\\Windows\\Fonts\\tahoma.ttf"
    if os.path.exists(tahoma_path):
        pdfmetrics.registerFont(TTFont('Tahoma', tahoma_path))
        logger.info("Tahoma font registered globally for Persian support")
except Exception as e:
    logger.warning(f"Failed to register Tahoma font globally: {e}")

# Text translations
PERSIAN_TRANSLATIONS = {
    "title": "گزارش هوش مصنوعی غربالگری پوست SmartHealth",
    "report_information": "اطلاعات گزارش",
    "report_id": "شناسه گزارش:",
    "date_time": "تاریخ/زمان:",
    "user_id": "شناسه کاربر:",
    "patient_information": "اطلاعات بیمار/کاربر",
    "age": "سن:",
    "skin_type": "نوع پوست:",
    "medical_history": "سابقه پزشکی:",
    "allergies": "آلرژی‌ها:",
    "no_patient_info": "اطلاعات بیماری در دسترس نیست.",
    "ai_model_information": "اطلاعات مدل هوش مصنوعی",
    "model_name": "نام مدل:",
    "predicted_class": "کلاس پیش‌بینی شده:",
    "model_confidence": "اطمینان مدل:",
    "important_confidence": "مهم: این نامه اطمینان نشان‌دهنده قطعیت مدل در پیش‌بینی خود است، نه احتمال سرطان.",
    "top_3_predictions": "۳ پیش‌بینی برتر",
    "rank": "رتبه",
    "class": "کلاس",
    "probability": "احتمال",
    "all_model_probabilities": "تمام احتمالات مدل",
    "explainability_visualization": "تصویرسازی قابلیت تفسیر",
    "explainability_disclaimer": "سلب مسئولیت قابلیت تفسیر: نقشه حرارتی یک تصویرسازی قابلیت تفسیر هوش مصنوعی است که نشان می‌دهد کدام مناطق تصویر بیشتر به پیش‌بینی مدل کمک کرده‌اند. این یک محلی‌سازی بالینی تأیید شده از سرطان نیست و نباید به عنوان یافته تشخیصی تفسیر شود.",
    "heatmap_not_available": "تصویرسازی قابلیت تفسیر در دسترس نیست.",
    "heatmap_failed": "تصویرسازی قابلیت تفسیر نمی‌تواند نمایش داده شود.",
    "user_symptoms": "علائم کاربر",
    "no_symptoms": "هیچ علامتی توصیف نشده بود.",
    "no_symptoms_reported": "هیچ علامتی گزارش نشده است.",
    "risk_assessment": "ارزیابی ریسک",
    "ai_screening_indicator": "شاخص غربالگری هوش مصنوعی:",
    "screening_score": "امتیاز غربالگری:",
    "urgency": "فوریت:",
    "important_risk": "مهم: این یک شاخص غربالگری تولید شده توسط هوش مصنوعی است، نه امتیاز ریسک سرطان تأیید شده بالینی.",
    "abcde_assessment": "ارزیابی ABCDE",
    "abcde_score": "امتیاز ABCDE:",
    "present": "موجود",
    "not_reported": "گزارش نشده",
    "abcde_not_available": "ارزیابی ABCDE: به طور قابل اعتمادی توسط تحلیل خودکار فعلی ارزیابی نشده است.",
    "abcde_clinical": "معیارهای ABCDE باید در معاینه بالینی توسط متخصص پوست ارزیابی شوند.",
    "image_quality_assessment": "ارزیابی کیفیت تصویر",
    "image_quality_acceptable": "کیفیت تصویر: قابل قبول برای تحلیل",
    "image_quality_issue": "کیفیت تصویر:",
    "recommended_next_steps": "مراحل بعدی توصیه شده",
    "no_recommendations": "هیچ توصیه خاصی در دسترس نیست.",
    "medical_disclaimer": "سلب مسئولیت پزشکی",
    "disclaimer": "این غربالگری هوش مصنوعی فقط برای اهداف آموزشی است و یک تشخیص پزشکی نیست.",
    "dermatologist_note": "فقط یک متخصص پوست تأیید شده می‌تواند سرطان پوست را از طریق معاینه بالینی تشخیص دهد.",
    "when_in_doubt": "در صورت تردید، همیشه مراقبت حرفه‌ای را جستجو کنید.",
}


class PDFReportService:
    """Service for generating PDF medical screening reports."""
    
    def __init__(self):
        self.logger = logger
        self.reports_dir = "reports"
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def _get_report_path(self, analysis_id: str) -> str:
        """Get the file path for a report."""
        return os.path.join(self.reports_dir, f"{analysis_id}.pdf")
    
    def _get_text(self, key: str, language: str = "english") -> str:
        """Get text in the specified language."""
        if language == "persian" and key in PERSIAN_TRANSLATIONS:
            return PERSIAN_TRANSLATIONS[key]
        # English defaults
        english_defaults = {
            "title": "SmartHealth AI Skin Screening Report",
            "report_information": "Report Information",
            "report_id": "Report ID:",
            "date_time": "Date/Time:",
            "user_id": "User ID:",
            "patient_information": "Patient/User Information",
            "age": "Age:",
            "skin_type": "Skin Type:",
            "medical_history": "Medical History:",
            "allergies": "Allergies:",
            "no_patient_info": "No patient information available.",
            "ai_model_information": "AI Model Information",
            "model_name": "Model Name:",
            "predicted_class": "Predicted Class:",
            "model_confidence": "Model Confidence:",
            "important_confidence": "IMPORTANT: This confidence score represents the model's certainty in its prediction, NOT the probability of cancer.",
            "top_3_predictions": "Top 3 Predictions",
            "rank": "Rank",
            "class": "Class",
            "probability": "Probability",
            "all_model_probabilities": "All Model Probabilities",
            "explainability_visualization": "Explainability Visualization",
            "explainability_disclaimer": "Explainability Disclaimer: The heatmap is an AI explainability visualization showing image regions that contributed more strongly to the model prediction. It is not a clinically validated localization of cancer and should not be interpreted as a diagnostic finding.",
            "heatmap_not_available": "Explainability visualization not available.",
            "heatmap_failed": "Explainability visualization could not be displayed.",
            "user_symptoms": "User Symptoms",
            "no_symptoms": "No symptoms were described.",
            "no_symptoms_reported": "No symptoms were reported.",
            "risk_assessment": "Risk Assessment",
            "ai_screening_indicator": "AI Screening Indicator:",
            "screening_score": "Screening Score:",
            "urgency": "Urgency:",
            "important_risk": "IMPORTANT: This is an AI-generated screening indicator, NOT a clinically validated cancer-risk score.",
            "abcde_assessment": "ABCDE Assessment",
            "abcde_score": "ABCDE Score:",
            "present": "Present",
            "not_reported": "Not reported",
            "abcde_not_available": "ABCDE Assessment: Not reliably assessed by the current automated analysis.",
            "abcde_clinical": "ABCDE criteria should be evaluated by a dermatologist during clinical examination.",
            "image_quality_assessment": "Image Quality Assessment",
            "image_quality_acceptable": "Image Quality: Acceptable for analysis",
            "image_quality_issue": "Image Quality:",
            "recommended_next_steps": "Recommended Next Steps",
            "no_recommendations": "No specific recommendations available.",
            "medical_disclaimer": "Medical Disclaimer",
            "disclaimer": "This AI screening is for educational purposes only and is NOT a medical diagnosis.",
            "dermatologist_note": "Only a board-certified dermatologist can diagnose skin cancer through clinical examination.",
            "when_in_doubt": "When in doubt, always seek professional care."
        }
        return english_defaults.get(key, key)
    
    def _fix_rtl_text(self, text: str, language: str = "english") -> str:
        """Fix RTL text direction for Persian/Arabic using arabic-reshaper and python-bidi."""
        if language != "persian":
            return text
        try:
            # Check if text contains Persian/Arabic characters
            # If it's mostly English/Latin, don't process it
            persian_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F' or '\u08A0' <= c <= '\u08FF')
            total_chars = len(text)
            
            # If less than 30% Persian chars, treat as English/Latin
            if total_chars > 0 and persian_chars / total_chars < 0.3:
                return text
            
            # First reshape the text for proper character forms
            reshaped_text = arabic_reshaper.reshape(text)
            # Then apply bidi algorithm for proper text direction
            return get_display(reshaped_text)
        except Exception as e:
            logger.warning(f"Failed to apply RTL processing to text: {e}")
            return text
    
    def generate_report(
        self, 
        analysis_data: Dict[str, Any],
        image_base64: Optional[str] = None,
        language: str = "english"
    ) -> Dict[str, Any]:
        """
        Generate a PDF report from structured analysis data.
        
        Args:
            analysis_data: Structured analysis result from image_agent
            image_base64: Optional base64 encoded image
            language: Language for the report ('english' or 'persian')
            
        Returns:
            Dictionary with report information
        """
        try:
            # DEBUG: Log what we received
            model_data = analysis_data.get("model", {})
            all_probs = model_data.get("all_probabilities", {})
            top3 = model_data.get("top3_predictions", [])
            logger.info(f"=== PDF GENERATION INPUT ===")
            logger.info(f"PDF all_probabilities count: {len(all_probs)}")
            logger.info(f"PDF top3_predictions count: {len(top3)}")
            if all_probs:
                logger.info(f"PDF probability classes: {list(all_probs.keys())}")
            
            # Use the language parameter to determine PDF language
            detected_language = language
            logger.info(f"🔥🔥🔥 PDF report language: {detected_language}")
            logger.info(f"🔥🔥🔥 Analysis data keys: {list(analysis_data.keys())}")
            
            # Check if report already exists (with language suffix)
            analysis_id = analysis_data.get("analysis_id", "")
            if analysis_id:
                # Use language suffix for cache key
                cache_suffix = f"_{language}" if language != "english" else ""
                cache_id = f"{analysis_id}{cache_suffix}"
                existing_path = self._get_report_path(cache_id)
                logger.info(f"PDF: Checking for cached report at: {existing_path}")
                if os.path.exists(existing_path):
                    logger.info(f"PDF: Found cached report, returning it")
                    return {
                        "success": True,
                        "report_path": existing_path,
                        "report_id": analysis_id,  # Return original ID without suffix
                        "generated_at": datetime.fromtimestamp(os.path.getmtime(existing_path)).isoformat(),
                        "cached": True,
                        "language": language
                    }
            
            # Generate new PDF
            if not analysis_id:
                from uuid import uuid4
                analysis_id = str(uuid4())
            
            # Use language suffix for file naming
            cache_suffix = f"_{language}" if language != "english" else ""
            cache_id = f"{analysis_id}{cache_suffix}"
            report_path = self._get_report_path(cache_id)
            
            # Create PDF
            doc = SimpleDocTemplate(report_path, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Set font and alignment based on language
            if language == "persian":
                # Use Tahoma font (registered globally)
                normal_font_name = "Tahoma"
                bold_font_name = "Tahoma"
                text_alignment = TA_RIGHT  # RTL alignment
            else:
                normal_font_name = "Helvetica"
                bold_font_name = "Helvetica-Bold"
                text_alignment = TA_LEFT
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#0d9488'),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName=bold_font_name,
                wordWrap='CJK' if language == 'persian' else None
            )
            
            header_style = ParagraphStyle(
                'CustomHeader',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#0d9488'),
                spaceAfter=12,
                spaceBefore=20,
                alignment=text_alignment,
                fontName=bold_font_name,
                wordWrap='CJK' if language == 'persian' else None
            )
            
            normal_style = ParagraphStyle(
                'Normal',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                alignment=text_alignment,
                fontName=normal_font_name,
                wordWrap='CJK' if language == 'persian' else None
            )
            
            # Title
            title_text = self._get_text("title", language)
            story.append(Paragraph(self._fix_rtl_text(title_text, language), title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Report Information
            story.append(Paragraph(self._fix_rtl_text(self._get_text("report_information", language), language), header_style))
            if language == 'persian':
                # Reverse column order for Persian: value first, then label
                report_info = [
                    [analysis_id, self._fix_rtl_text(self._get_text("report_id", language), language)],
                    [analysis_data.get("timestamp", "N/A"), self._fix_rtl_text(self._get_text("date_time", language), language)],
                    [analysis_data.get("user_id", "N/A"), self._fix_rtl_text(self._get_text("user_id", language), language)]
                ]
            else:
                report_info = [
                    [self._fix_rtl_text(self._get_text("report_id", language), language), analysis_id],
                    [self._fix_rtl_text(self._get_text("date_time", language), language), analysis_data.get("timestamp", "N/A")],
                    [self._fix_rtl_text(self._get_text("user_id", language), language), analysis_data.get("user_id", "N/A")]
                ]
            report_table = Table(report_info, colWidths=[1.5*inch, 4*inch])
            if language == 'persian':
                report_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.white),  # Changed from lightgrey to white
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),   # Value column: left aligned
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Label column: right aligned
                    ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                ]))
            else:
                report_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (1, 0), (1, -1), colors.white),
                ]))
            story.append(report_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Patient Information
            story.append(Paragraph(self._fix_rtl_text(self._get_text("patient_information", language), language), header_style))
            profile_context = analysis_data.get("profile_context", {})
            patient_info = []
            if profile_context.get("age"):
                if language == 'persian':
                    patient_info.append([str(profile_context["age"]), self._fix_rtl_text(self._get_text("age", language), language)])
                else:
                    patient_info.append([self._fix_rtl_text(self._get_text("age", language), language), str(profile_context["age"])])
            if profile_context.get("skin_type"):
                # Clean potential text
                skin_type = profile_context["skin_type"]
                if language == 'persian':
                    patient_info.append([skin_type, self._fix_rtl_text(self._get_text("skin_type", language), language)])
                else:
                    patient_info.append([self._fix_rtl_text(self._get_text("skin_type", language), language), skin_type])
            if profile_context.get("medical_history"):
                # Clean potential text in medical history
                medical_history = profile_context["medical_history"]
                # Convert list format like ["l", "a", "t", "e", "x"] to "latex"
                if isinstance(medical_history, list) and len(medical_history) > 1:
                    # Check if it's a letter-by-letter list
                    if all(len(item) == 1 for item in medical_history):
                        medical_history = [''.join(medical_history)]
                if language == 'persian':
                    patient_info.append([", ".join(medical_history), self._fix_rtl_text(self._get_text("medical_history", language), language)])
                else:
                    patient_info.append([self._fix_rtl_text(self._get_text("medical_history", language), language), ", ".join(medical_history)])
            if profile_context.get("allergies"):
                # Clean potential text in allergies
                allergies = profile_context["allergies"]
                # Convert list format like ["l", "a", "t", "e", "x"] to "latex"
                if isinstance(allergies, list) and len(allergies) > 1:
                    # Check if it's a letter-by-letter list
                    if all(len(item) == 1 for item in allergies):
                        allergies = [''.join(allergies)]
                if language == 'persian':
                    patient_info.append([", ".join(allergies), self._fix_rtl_text(self._get_text("allergies", language), language)])
                else:
                    patient_info.append([self._fix_rtl_text(self._get_text("allergies", language), language), ", ".join(allergies)])
            
            user_id = analysis_data.get("user_id", "N/A")
            
            if patient_info:
                patient_table = Table(patient_info, colWidths=[1.5*inch, 4*inch])
                if language == 'persian':
                    patient_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.white),  # Changed from lightgrey to white
                        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),   # Value column: left aligned
                        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Label column: right aligned
                        ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (1, 0), (1, -1), colors.white),
                        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                    ]))
                else:
                    patient_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ]))
                story.append(patient_table)
            else:
                story.append(Paragraph(self._fix_rtl_text(self._get_text("no_patient_info", language), language), normal_style))
            story.append(Spacer(1, 0.2*inch))
            
            # AI Model Information
            story.append(Paragraph(self._fix_rtl_text(self._get_text("ai_model_information", language), language), header_style))
            model_data = analysis_data.get("model", {})
            if language == 'persian':
                model_info = [
                    [model_data.get("name", "N/A"), self._fix_rtl_text(self._get_text("model_name", language), language)],
                    [model_data.get("predicted_class", "N/A"), self._fix_rtl_text(self._get_text("predicted_class", language), language)],
                    [f"{model_data.get('confidence', 0):.2%}", self._fix_rtl_text(self._get_text("model_confidence", language), language)]
                ]
            else:
                model_info = [
                    [self._fix_rtl_text(self._get_text("model_name", language), language), model_data.get("name", "N/A")],
                    [self._fix_rtl_text(self._get_text("predicted_class", language), language), model_data.get("predicted_class", "N/A")],
                    [self._fix_rtl_text(self._get_text("model_confidence", language), language), f"{model_data.get('confidence', 0):.2%}"],
                    ["", ""],
                    [self._fix_rtl_text("مهم:" if language == 'persian' else "IMPORTANT:", language), self._fix_rtl_text(self._get_text("important_confidence", language), language)]
                ]
            model_table = Table(model_info, colWidths=[1.5*inch, 4*inch])
            if language == 'persian':
                model_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.white),  # Changed from lightgrey to white
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),   # Value column: left aligned
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Label column: right aligned
                    ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ('TEXTCOLOR', (0, 4), (1, 4), colors.red),
                    ('FONTNAME', (0, 4), (1, 4), bold_font_name),
                    ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                ]))
            else:
                model_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ('TEXTCOLOR', (0, 4), (1, 4), colors.red),
                    ('FONTNAME', (0, 4), (1, 4), bold_font_name),
                ]))
            story.append(model_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Alternative Predictions
            top3 = model_data.get("top3_predictions", [])
            if top3:
                story.append(Paragraph(self._fix_rtl_text(self._get_text("top_3_predictions", language), language), header_style))
                if language == 'persian':
                    # Reverse column order for Persian: probability, class, rank
                    predictions = [[f"{pred.get('probability', 0):.2%}", pred.get("class", "N/A"), f"{i+1}."] for i, pred in enumerate(top3)]
                    pred_table = Table([[self._fix_rtl_text(self._get_text("probability", language), language), self._fix_rtl_text(self._get_text("class", language), language), self._fix_rtl_text(self._get_text("rank", language), language)]] + predictions, colWidths=[2*inch, 3*inch, 0.5*inch])
                else:
                    predictions = [[f"{i+1}.", pred.get("class", "N/A"), f"{pred.get('probability', 0):.2%}"] for i, pred in enumerate(top3)]
                    pred_table = Table([[self._fix_rtl_text(self._get_text("rank", language), language), self._fix_rtl_text(self._get_text("class", language), language), self._fix_rtl_text(self._get_text("probability", language), language)]] + predictions, colWidths=[0.5*inch, 3*inch, 2*inch])
                if language == 'persian':
                    pred_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d9488')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                        ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                    ]))
                else:
                    pred_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d9488')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ]))
                story.append(pred_table)
                story.append(Spacer(1, 0.2*inch))
            
            # All Model Probabilities
            all_probs = model_data.get("all_probabilities", {})
            if all_probs:
                story.append(Paragraph(self._fix_rtl_text(self._get_text("all_model_probabilities", language), language), header_style))
                # Sort by probability descending
                sorted_probs = sorted(all_probs.items(), key=lambda x: x[1], reverse=True)
                if language == 'persian':
                    # Reverse column order for Persian: probability, class
                    prob_data = [[f"{prob:.2%}", class_name] for class_name, prob in sorted_probs]
                    prob_table = Table([[self._fix_rtl_text(self._get_text("probability", language), language), self._fix_rtl_text(self._get_text("class", language), language)]] + prob_data, colWidths=[2*inch, 3*inch])
                else:
                    prob_data = [[class_name, f"{prob:.2%}"] for class_name, prob in sorted_probs]
                    prob_table = Table([[self._fix_rtl_text(self._get_text("class", language), language), self._fix_rtl_text(self._get_text("probability", language), language)]] + prob_data, colWidths=[3*inch, 2*inch])
                if language == 'persian':
                    prob_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d9488')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                        ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                    ]))
                else:
                    prob_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d9488')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ]))
                story.append(prob_table)
                story.append(Spacer(1, 0.2*inch))
            
            # Explainability Visualization
            explainability = analysis_data.get("explainability", {})
            logger.info(f"PDF: Explainability data check: {explainability}")
            
            if explainability.get("available"):
                story.append(Paragraph(self._fix_rtl_text(self._get_text("explainability_visualization", language), language), header_style))
                
                # Load and embed the overlay image
                overlay_path = explainability.get("overlay_path")
                logger.info(f"PDF: Looking for heatmap overlay at: {overlay_path}")
                
                if overlay_path and os.path.exists(overlay_path):
                    try:
                        from PIL import Image as PILImage
                        img = PILImage.open(overlay_path)
                        # Resize to fit PDF width
                        img_width, img_height = img.size
                        max_width = 5 * inch  # 5 inches
                        if img_width > max_width:
                            ratio = max_width / img_width
                            new_height = img_height * ratio
                            img = img.resize((int(max_width), int(new_height)))
                        
                        img_bytes = io.BytesIO()
                        img.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        
                        img_pdf = Image(img_bytes, width=img.size[0], height=img.size[1])
                        story.append(img_pdf)
                        
                        # Add disclaimer
                        disclaimer_text = self._get_text("explainability_disclaimer", language)
                        disclaimer_style = ParagraphStyle(
                            'Helvetica',
                            parent=styles['Normal'],
                            fontSize=8,
                            textColor=colors.gray,
                            spaceAfter=12,
                            alignment=text_alignment,
                            fontName=normal_font_name,
                            wordWrap='CJK' if language == 'persian' else None
                        )
                        story.append(Paragraph(disclaimer_text, disclaimer_style))
                        story.append(Spacer(1, 0.2*inch))
                        logger.info(f"PDF: Successfully embedded heatmap overlay")
                    except Exception as img_error:
                        logger.warning(f"Failed to embed heatmap image: {img_error}")
                        story.append(Paragraph(self._fix_rtl_text(self._get_text("heatmap_failed", language), language), normal_style))
                        story.append(Spacer(1, 0.2*inch))
                else:
                    logger.warning(f"PDF: Heatmap overlay file not found at: {overlay_path}")
                    story.append(Paragraph(self._fix_rtl_text(self._get_text("heatmap_not_available", language), language), normal_style))
                    story.append(Spacer(1, 0.2*inch))
            else:
                logger.info("PDF: Explainability not available in analysis data (this may be an old analysis)")
            
            # User Symptoms
            story.append(Paragraph(self._fix_rtl_text(self._get_text("user_symptoms", language), language), header_style))
            symptom_data = analysis_data.get("symptom_analysis", {})
            symptoms = symptom_data.get("symptoms", [])
            if symptoms:
                for symptom in symptoms:
                    cleaned_symptom = symptom
                    story.append(Paragraph(self._fix_rtl_text(f"• {cleaned_symptom}", language), normal_style))
            else:
                story.append(Paragraph(self._fix_rtl_text(self._get_text("no_symptoms_reported", language), language), normal_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Risk Assessment
            story.append(Paragraph(self._fix_rtl_text(self._get_text("risk_assessment", language), language), header_style))
            risk_data = analysis_data.get("risk_assessment", {})
            urgency_message = risk_data.get("urgency_message", "N/A")
            if language == 'persian':
                risk_info = [
                    [risk_data.get("screening_level", "N/A"), self._fix_rtl_text(self._get_text("ai_screening_indicator", language), language)],
                    [f"{risk_data.get('screening_score', 0)}/100", self._fix_rtl_text(self._get_text("screening_score", language), language)],
                    [urgency_message, self._fix_rtl_text(self._get_text("urgency", language), language)]
                ]
            else:
                risk_info = [
                    [self._fix_rtl_text(self._get_text("ai_screening_indicator", language), language), risk_data.get("screening_level", "N/A")],
                    [self._fix_rtl_text(self._get_text("screening_score", language), language), f"{risk_data.get('screening_score', 0)}/100"],
                    [self._fix_rtl_text(self._get_text("urgency", language), language), urgency_message],
                    ["", ""],
                    [self._fix_rtl_text("مهم:", language), self._fix_rtl_text(self._get_text("important_risk", language), language)]
                ]
            risk_table = Table(risk_info, colWidths=[1.5*inch, 4*inch])
            if language == 'persian':
                risk_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.white),  # Changed from lightgrey to white
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),   # Value column: left aligned
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Label column: right aligned
                    ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ('TEXTCOLOR', (0, 4), (1, 4), colors.red),
                    ('FONTNAME', (0, 4), (1, 4), bold_font_name),
                    ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                ]))
            else:
                risk_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ('TEXTCOLOR', (0, 4), (1, 4), colors.red),
                    ('FONTNAME', (0, 4), (1, 4), bold_font_name),
                ]))
            story.append(risk_table)
            story.append(Spacer(1, 0.2*inch))
            
            # ABCDE Assessment
            story.append(Paragraph(self._fix_rtl_text(self._get_text("abcde_assessment", language), language), header_style))
            abcde_data = analysis_data.get("abcde", {})
            if abcde_data.get("available"):
                if language == 'persian':
                    abcde_info = [
                        [f"{abcde_data.get('score', 0)}/5", self._fix_rtl_text(self._get_text("abcde_score", language), language)]
                    ]
                else:
                    abcde_info = [
                        [self._fix_rtl_text(self._get_text("abcde_score", language), language), f"{abcde_data.get('score', 0)}/5"]
                    ]
                criteria = abcde_data.get("criteria", {})
                for criterion, present in criteria.items():
                    cleaned_criterion = criterion.capitalize()
                    if language == 'persian':
                        abcde_info.append([self._fix_rtl_text(self._get_text("present", language), language) if present else self._fix_rtl_text(self._get_text("not_reported", language), language), cleaned_criterion])
                    else:
                        abcde_info.append([cleaned_criterion, self._fix_rtl_text(self._get_text("present", language), language) if present else self._fix_rtl_text(self._get_text("not_reported", language), language)])
                abcde_table = Table(abcde_info, colWidths=[1.5*inch, 4*inch])
                if language == 'persian':
                    abcde_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.white),  # Changed from lightgrey to white
                        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),   # Value column: left aligned
                        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Label column: right aligned
                        ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (1, 0), (1, -1), colors.white),
                        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                    ]))
                else:
                    abcde_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), normal_font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BACKGROUND', (1, 0), (1, -1), colors.white),
                    ]))
                story.append(abcde_table)
            else:
                story.append(Paragraph(self._fix_rtl_text(self._get_text("abcde_not_available", language), language), normal_style))
                story.append(Paragraph(self._fix_rtl_text(self._get_text("abcde_clinical", language), language), normal_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Image Quality
            story.append(Paragraph(self._fix_rtl_text(self._get_text("image_quality_assessment", language), language), header_style))
            quality_data = analysis_data.get("image_quality", {})
            if quality_data.get("acceptable", True):
                story.append(Paragraph(self._fix_rtl_text(self._get_text("image_quality_acceptable", language), language), normal_style))
            else:
                story.append(Paragraph(self._fix_rtl_text(f"{self._get_text('image_quality_issue', language)} {quality_data.get('recommendation', 'Quality issues detected')}", language), normal_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Recommendations
            story.append(Paragraph(self._fix_rtl_text(self._get_text("recommended_next_steps", language), language), header_style))
            recommendations = analysis_data.get("recommendations", {})
            if isinstance(recommendations, dict):
                for key, value in recommendations.items():
                    cleaned_key = str(key)
                    cleaned_value = str(value)
                    story.append(Paragraph(self._fix_rtl_text(f"• {cleaned_key}: {cleaned_value}", language), normal_style))
            elif isinstance(recommendations, str):
                cleaned_recommendations = recommendations
                story.append(Paragraph(self._fix_rtl_text(f"• {cleaned_recommendations}", language), normal_style))
            else:
                story.append(Paragraph(self._fix_rtl_text(self._get_text("no_recommendations", language), language), normal_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Medical Disclaimer
            story.append(Paragraph(self._fix_rtl_text(self._get_text("medical_disclaimer", language), language), header_style))
            if language == 'persian':
                # Use full Persian disclaimer without "بیوپسی"
                persian_disclaimer = "این غربالگری هوش مصنوعی فقط برای اهداف آموزشی است و یک تشخیص پزشکی نیست."
                story.append(Paragraph(self._fix_rtl_text(persian_disclaimer, language), normal_style))
                story.append(Spacer(1, 0.1*inch))
                story.append(Paragraph(self._fix_rtl_text(self._get_text("dermatologist_note", language), language), normal_style))
                story.append(Paragraph(self._fix_rtl_text(self._get_text("when_in_doubt", language), language), normal_style))
            else:
                disclaimer = analysis_data.get("disclaimer", self._get_text("disclaimer", language))
                story.append(Paragraph(disclaimer, normal_style))
                story.append(Paragraph(self._get_text("dermatologist_note", language), normal_style))
                story.append(Paragraph(self._get_text("when_in_doubt", language), normal_style))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"PDF report generated: {report_path}")
            
            return {
                "success": True,
                "report_path": report_path,
                "report_id": analysis_id,  # Return original ID without suffix
                "generated_at": datetime.now().isoformat(),
                "cached": False,
                "format": "pdf",
                "language": language
            }
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_report(self, analysis_id: str, language: str = "english") -> Optional[Dict[str, Any]]:
        """
        Get an existing report by analysis ID.
        
        Args:
            analysis_id: Analysis identifier
            language: Language to look for ('english' or 'persian')
            
        Returns:
            Report information or None if not found
        """
        # Try with language suffix first
        cache_suffix = f"_{language}" if language != "english" else ""
        cache_id = f"{analysis_id}{cache_suffix}"
        report_path = self._get_report_path(cache_id)
        
        if os.path.exists(report_path):
            return {
                "report_id": analysis_id,
                "report_path": report_path,
                "exists": True,
                "format": "pdf",
                "language": language,
                "generated_at": datetime.fromtimestamp(os.path.getmtime(report_path)).isoformat()
            }
        
        # Fallback to try English version if Persian not found
        if language == "persian":
            english_path = self._get_report_path(analysis_id)
            if os.path.exists(english_path):
                return {
                    "report_id": analysis_id,
                    "report_path": english_path,
                    "exists": True,
                    "format": "pdf",
                    "language": "english",
                    "generated_at": datetime.fromtimestamp(os.path.getmtime(english_path)).isoformat()
                }
        
        return None
    
    def delete_report(self, analysis_id: str) -> bool:
        """
        Delete a report by analysis ID.
        
        Args:
            analysis_id: Analysis identifier
            
        Returns:
            True if deleted, False otherwise
        """
        report_path = self._get_report_path(analysis_id)
        
        if os.path.exists(report_path):
            os.remove(report_path)
            return True
        
        return False


# Global instance
pdf_report_service = PDFReportService()