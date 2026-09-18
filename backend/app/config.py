# app/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import ClassVar, Dict, List, Tuple, Optional


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- API KEYS ----------
    GROQ_API_KEY: str = ""
    HF_API_KEY: str = ""
    SERPER_API_KEY: Optional[str] = None

    # ---------- GENERAL ----------
    ENV: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "SkinCancer AI Backend"

    # ---------- LLM ----------
    LM_STUDIO_HOST: str = "http://localhost:1234"
    # IMPORTANT: LM_STUDIO_MODEL must match EXACTLY the model name shown in LM Studio's "Loaded Models" section
    # This is typically shown in LM Studio's UI under the "Server" tab when you load a model
    # Common model names: "gemma-2-9b-it", "llama-3-8b-instruct", "mistral-7b-instruct", "gemma-4-E2B-it-Q4_K_M", etc.
    # Set via environment variable: LM_STUDIO_MODEL=your_exact_model_name
    LM_STUDIO_MODEL: str = "gemma-4-E2B-it-Q4_K_M"  # Update this to match your LM Studio loaded model exactly
    OLLAMA_HOST: Optional[str] = None

    # Groq models per agent role (fallback to Gemma via LM Studio)
    GROQ_MODEL_FAST: str = "groq/compound-mini"
    GROQ_MODEL_REASONING: str = "groq/compound"
    LLM_USE_GROQ_FIRST: bool = True

    # ---------- LOCAL ML MODEL PATHS ----------
    LOCAL_NER_MODEL_PATH: str = "app/utils/models/biomedical-ner"
    LOCAL_EMBEDDING_MODEL_PATH: str = "app/utils/models/all-MiniLM-L6-v2"

    # PanDerm (ISIC 2019 + PAD-UFES) — fine-tuned checkpoint
    # These paths are relative to the backend directory
    PANDERM_CHECKPOINT_PATH: str = "app/models/panderm/checkpoints/checkpoint-best.pth"
    PANDERM_CONFIG_PATH: str = "app/models/panderm/config.json"
    PANDERM_LABELS_PATH: str = "app/models/panderm/labels.json"
    
    # Heatmap output directory for explainability visualizations
    HEATMAP_OUTPUT_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_heatmaps")
    
    # Legacy model paths (deprecated - ResNet no longer used)
    # SKIN_MODEL_PATH: str = "app/models/skin_disease_model.pth"
    # SKIN_MODEL_CLASS_PATH: str = "app/models/labels.json"
    # SKIN_CANCER_LABELS_PATH: str = "app/models/labels.json"

    # ---------- KNOWLEDGE BASES ----------
    DISEASE_INFO_PATH: str = "app/data/disease_db.csv"
    SKIN_CANCER_DB_PATH: str = "app/data/skin_cancer_db.csv"

    # ---------- MYSQL DATABASE ----------
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "skin_health"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # ---------- VECTOR DB ----------
    FAISS_SYMPTOM_PATH: str = "app/data/vector/symptom_faiss_db/"
    FAISS_DISEASE_PATH: str = "app/data/vector/disease_faiss_db/"

    # ---------- ISIC 2019 + PAD-UFES CLASS MAP (8 classes) - Official PanDerm Training Order ----------
    ISIC_CLASS_LABELS: ClassVar[List[str]] = [
        "melanocytic nevus",
        "melanoma",
        "benign keratosis",
        "basal cell carcinoma",
        "actinic keratosis",
        "vascular lesion",
        "dermatofibroma",
        "squamous cell carcinoma",
    ]
    ISIC_CLASS_CODES: ClassVar[Dict[str, str]] = {
        "nv": "melanocytic nevus",
        "mel": "melanoma",
        "bkl": "benign keratosis",
        "bcc": "basal cell carcinoma",
        "akiec": "actinic keratosis",
        "vasc": "vascular lesion",
        "df": "dermatofibroma",
        "scc": "squamous cell carcinoma",
    }
    MALIGNANT_CLASSES: ClassVar[List[str]] = [
        "melanoma",
        "mel",
        "basal cell carcinoma",
        "bcc",
        "actinic keratosis",
        "akiec",
        "squamous cell carcinoma",
        "scc",
    ]

    # ---------- AGENT MODEL MAP ----------
    AGENT_MODEL_MAP: ClassVar[Dict[str, Tuple[str, str]]] = {
        "decider_agent": ("groq", "groq/compound-mini"),
        "planner_agent": ("groq", "groq/compound-mini"),
        "reasoning_agent": ("groq", "groq/compound"),
        "symptom_matcher_agent": ("groq", "groq/compound-mini"),
        "disease_info_agent": ("groq", "groq/compound-mini"),
        "conversation_agent": ("groq", "groq/compound-mini"),
        "image_agent": ("groq", "groq/compound"),
    }

    # ---------- PREDICTION SAFETY GATE (OOD/Unknown Detection) ----------
    PREDICTION_SAFETY_ENABLED: bool = True
    OOD_SIMILARITY_THRESHOLD: float = 0.50
    
    # ---------- SUPPORTED LESION GATE (Image Suitability) ----------
    SUPPORTED_LESION_GATE_ENABLED: bool = True


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
