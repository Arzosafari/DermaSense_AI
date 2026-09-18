"""ISIC 2019 HAM10000 class definitions and normalization."""
from typing import Dict, List, Optional

from app.config import settings

# Short code → display name
ISIC_CODE_TO_NAME: Dict[str, str] = settings.ISIC_CLASS_CODES

# Display name → short code
ISIC_NAME_TO_CODE: Dict[str, str] = {v: k for k, v in ISIC_CODE_TO_NAME.items()}

# Also map common aliases
_ALIASES: Dict[str, str] = {
    "melanoma": "melanoma",
    "mel": "melanoma",
    "nevus": "melanocytic nevus",
    "nv": "melanocytic nevus",
    "mole": "melanocytic nevus",
    "bcc": "basal cell carcinoma",
    "basal cell": "basal cell carcinoma",
    "akiec": "actinic keratosis",
    "actinic keratoses": "actinic keratosis",
    "bkl": "benign keratosis",
    "seborrheic keratosis": "benign keratosis",
    "df": "dermatofibroma",
    "vasc": "vascular lesion",
    "hemangioma": "vascular lesion",
    "scc": "squamous cell carcinoma",
    "squamous": "squamous cell carcinoma",
}


def normalize_class_name(raw: str) -> str:
    """Normalize model output or user input to a canonical ISIC display name."""
    if not raw:
        return "unknown"
    key = raw.lower().strip().replace("_", " ").replace("-", " ")
    
    # First try exact match with aliases
    if key in _ALIASES:
        return _ALIASES[key]
    
    # Then try exact match with class names
    for name in settings.ISIC_CLASS_LABELS:
        if key == name.lower():
            return name
    
    # Finally try substring matching (but be careful)
    for alias, name in _ALIASES.items():
        if key == alias.lower():
            return name
    
    return raw.strip()


def is_malignant(class_name: str) -> bool:
    normalized = normalize_class_name(class_name).lower()
    malignant_names = {
        "melanoma",
        "basal cell carcinoma",
        "actinic keratosis",
        "squamous cell carcinoma",
    }
    # Note: melanocytic nevus is benign, not malignant
    # Use exact match to avoid substring matching issues
    return normalized in malignant_names


def get_isic_code(class_name: str) -> Optional[str]:
    normalized = normalize_class_name(class_name)
    return ISIC_NAME_TO_CODE.get(normalized)


def all_class_names() -> List[str]:
    return list(settings.ISIC_CLASS_LABELS)
