"""ABCDE melanoma criteria analyzer from free-text symptom descriptions."""
import re
from typing import Dict, List


_ABCDE_PATTERNS: Dict[str, List[str]] = {
    "asymmetry": [
        r"asymmetr", r"uneven shape", r"irregular shape", r"one half",
        r"نامتقارن", r"شکل نامنظم",
    ],
    "border": [
        r"irregular border", r"jagged", r"notched edge", r"blurry edge",
        r"حاشیه نامنظم", r"لبه نامنظم",
    ],
    "color": [
        r"multi.?color", r"different color", r"color variation", r"dark and light",
        r"چند رنگ", r"تغییر رنگ", r"رنگ‌های مختلف",
    ],
    "diameter": [
        r"larger than.*6", r"bigger than.*6", r"6mm", r"growing", r"enlarg",
        r"بزرگتر", r"در حال بزرگ", r"۶ میلی",
    ],
    "evolution": [
        r"chang", r"grow", r"evolv", r"new mole", r"different from before",
        r"تغییر", r"رشد", r"جدید", r"متفاوت",
    ],
}


def analyze_abcde(text: str) -> Dict:
    """Score ABCDE criteria from user text. Returns 0-5 score and per-criterion flags."""
    if not text:
        return {"abcde_score": 0, "criteria": {}, "warnings": []}

    lower = text.lower()
    criteria = {}
    warnings = []

    labels = {
        "asymmetry": "Asymmetry — lesion halves do not match",
        "border": "Border — irregular or poorly defined edges",
        "color": "Color — multiple colors or uneven pigmentation",
        "diameter": "Diameter — larger than 6mm or growing",
        "evolution": "Evolution — changing in size, shape, or color",
    }

    for key, patterns in _ABCDE_PATTERNS.items():
        matched = any(re.search(p, lower) for p in patterns)
        criteria[key] = matched
        if matched:
            warnings.append(labels[key])

    score = sum(1 for v in criteria.values() if v)
    return {
        "abcde_score": score,
        "criteria": criteria,
        "warnings": warnings,
        "interpretation": _interpret(score),
    }


def _interpret(score: int) -> str:
    if score >= 4:
        return "High ABCDE concern — urgent dermatologist evaluation recommended based on described features"
    if score >= 2:
        return "Moderate ABCDE concern — professional evaluation advised based on described features"
    if score == 1:
        return "One ABCDE sign noted — monitor closely"
    return "ABCDE features could not be reliably assessed from this description alone. A dermatologist should evaluate ABCDE characteristics during a clinical examination."
