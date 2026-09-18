"""
Domain filter for skin cancer specialist (ISIC 2019 classes).
"""
import re
from typing import Optional, Tuple

_IMAGE_ANALYSIS_PHRASES = [
    "analyze", "check this", "look at this", "what is this",
    "تحلیل", "بررسی", "تشخیص", "این چیه", "این چیست", "ببین",
    "diagnose", "identify", "melanoma", "mole", "lesion",
    "skin cancer", "سرطان پوست", "خال", "ضایعه",
]

_SKIN_CANCER_KEYWORDS = {
    "melanoma", "mole", "nevus", "lesion", "skin cancer", "carcinoma",
    "basal cell", "bcc", "squamous", "scc", "actinic keratosis",
    "dermatofibroma", "keratosis", "spot", "patch", "growth",
    "changing mole", "asymmetry", "abcde",
    "ملانوم", "سرطان پوست", "خال", "ضایعه", "لکه", "تغییر رنگ",
    "skin", "rash", "itch", "redness", "پوست", "خارش", "قرمزی",
}

# ISIC 2019 + PAD-UFES canonical + short codes (8 classes)
_VALID_CANCER_CLASSES = {
    "melanoma", "mel", "melanocytic nevus", "nv", "nevus", "mole",
    "basal cell carcinoma", "bcc",
    "actinic keratosis", "akiec",
    "benign keratosis", "bkl", "seborrheic keratosis",
    "dermatofibroma", "df",
    "vascular lesion", "vasc",
    "squamous cell carcinoma", "scc",
    # Legacy classes (until PanDerm checkpoint replaces old model)
    "cellulitis", "ba-impetigo", "impetigo", "fu-athlete-foot",
    "fu-nail-fungus", "fu-ringworm", "pa-cutaneous-larva-migrans",
    "vi-chickenpox", "vi-shingles",
}

_MIN_CONFIDENCE_AUTO_ACCEPT = 0.80
_MIN_CONFIDENCE_WITH_SKIN_TEXT = 0.45


def _is_skin_colors(image_base64: Optional[str]) -> Tuple[bool, str]:
    if not image_base64:
        return False, "no_image"
    try:
        import base64
        import io
        from PIL import Image
        import numpy as np

        if "base64," in image_base64:
            image_base64 = image_base64.split("base64,")[1]
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image = image.resize((100, 100))
        pixels = np.array(image)

        skin_mask = (
            (pixels[:, :, 0] > pixels[:, :, 1]) &
            (pixels[:, :, 0] > pixels[:, :, 2]) &
            (pixels[:, :, 0] > 80) & (pixels[:, :, 0] < 240) &
            (pixels[:, :, 1] > 40) & (pixels[:, :, 1] < 220) &
            (pixels[:, :, 2] > 20) & (pixels[:, :, 2] < 200)
        )
        skin_pixel_ratio = skin_mask.sum() / (100 * 100)

        gray_mask = (
            (abs(pixels[:, :, 0].astype(float) - pixels[:, :, 1].astype(float)) < 30) &
            (abs(pixels[:, :, 1].astype(float) - pixels[:, :, 2].astype(float)) < 30)
        )
        if gray_mask.sum() / (100 * 100) > 0.70:
            return False, "too_much_gray"

        r, g, b = pixels.mean(axis=(0, 1))
        if g > r + 20 or b > r + 20:
            return False, f"non_skin_dominant: r={r:.0f} g={g:.0f} b={b:.0f}"
        if skin_pixel_ratio > 0.15:
            return True, f"skin_colors: ratio={skin_pixel_ratio:.2f}"
        if 100 < r < 230 and 60 < g < 200 and 30 < b < 180:
            return True, f"avg_skin_color"
        return False, f"low_skin_ratio: {skin_pixel_ratio:.2f}"
    except Exception as e:
        return True, f"color_check_error: {e}"


def is_skin_related_image(
    user_message: str,
    predicted_class: Optional[str] = None,
    confidence: Optional[float] = None,
    image_base64: Optional[str] = None,
    permissive_mode: bool = False,
) -> Tuple[bool, str]:
    """
    Check if image is skin-related.
    
    Args:
        user_message: User's text message
        predicted_class: Predicted class from model
        confidence: Prediction confidence
        image_base64: Base64-encoded image
        permissive_mode: If True, only check for skin colors (used by supported lesion gate)
    
    Returns:
        Tuple of (is_skin_related, reason)
    """
    msg = (user_message or "").lower().strip()
    has_keywords = any(kw in msg for kw in _SKIN_CANCER_KEYWORDS)
    is_analysis = any(p in msg for p in _IMAGE_ANALYSIS_PHRASES)

    # In permissive mode, only check for skin colors (used by supported lesion gate)
    if permissive_mode and image_base64:
        looks_like_skin, reason = _is_skin_colors(image_base64)
        return looks_like_skin, reason

    if not has_keywords and image_base64:
        looks_like_skin, reason = _is_skin_colors(image_base64)
        if not looks_like_skin:
            return False, f"COLOR_CHECK_FAIL: {reason}"

    if predicted_class and predicted_class not in ("unknown", "error"):
        pc = predicted_class.lower().strip()
        if pc in _VALID_CANCER_CLASSES or any(v in pc for v in _VALID_CANCER_CLASSES):
            if confidence and confidence >= _MIN_CONFIDENCE_AUTO_ACCEPT:
                return True, f"HIGH_CONF: {pc}"
            if has_keywords or is_analysis:
                return True, f"USER_CONTEXT: {pc}"
            if confidence and confidence >= _MIN_CONFIDENCE_WITH_SKIN_TEXT:
                return True, f"MED_CONF: {pc}"
        if has_keywords or is_analysis:
            return True, "USER_OVERRIDE"
        return False, f"LOW_CONF: {pc}"

    if has_keywords or is_analysis:
        return True, "USER_CONTEXT"
    return False, "NO_EVIDENCE"


def out_of_scope_message(language: str = "english") -> str:
    if language in ("persian", "fa"):
        return (
            "⚠️ **خارج از حوزه تخصص**\n\n"
            "من یک دستیار **تخصصی غربالگری سرطان پوست** هستم. "
            "لطفاً یک **عکس واضح از ضایعه پوستی** (خال، لکه، زخم) ارسال کنید.\n\n"
            "این سیستم جایگزین معاینه پزشکی نیست."
        )
    return (
        "⚠️ **Outside Scope**\n\n"
        "I am a **skin cancer screening assistant**. "
        "Please upload a **clear photo of a skin lesion** (mole, spot, sore, or patch).\n\n"
        "This tool does not replace a professional medical examination."
    )


def detect_language(text: str) -> str:
    persian = set("ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی")
    sample = (text or "")[:300]
    if sum(1 for c in sample if c in persian) > sum(1 for c in sample if c.isalpha() and c not in persian):
        return "persian"
    return "english"
