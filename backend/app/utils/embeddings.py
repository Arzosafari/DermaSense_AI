# app/utils/embeddings.py
import os
import logging
import threading
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Global cache with thread lock
_EMBEDDING_MODEL = None
_lock = threading.Lock()

class EmbeddingSingleton:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingSingleton, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        global _EMBEDDING_MODEL
        
        # Double-checked locking pattern
        if _EMBEDDING_MODEL is not None:
            self.model = _EMBEDDING_MODEL
            return
        
        with _lock:
            if _EMBEDDING_MODEL is not None:
                self.model = _EMBEDDING_MODEL
                return
            
            # مسیرهای مختلف برای یافتن مدل
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            possible_paths = [
                os.path.join(current_dir, "utils", "models", "all-MiniLM-L6-v2"),
                r"D:\final-project\v2\SmartHealth-LLM\backend\app\utils\models\all-MiniLM-L6-v2",
            ]
            
            model_path = None
            for path in possible_paths:
                config_file = os.path.join(path, "config.json")
                if os.path.exists(path) and os.path.exists(config_file):
                    model_path = path
                    logger.info(f"✅ Found embedding model at: {model_path}")
                    break
            
            if model_path is None:
                # Try to find it recursively
                for root, dirs, files in os.walk(current_dir):
                    if "all-MiniLM-L6-v2" in dirs:
                        model_path = os.path.join(root, "all-MiniLM-L6-v2")
                        if os.path.exists(os.path.join(model_path, "config.json")):
                            logger.info(f"✅ Found embedding model at: {model_path}")
                            break
            
            if model_path is None:
                raise FileNotFoundError(
                    "❌ Embedding model 'all-MiniLM-L6-v2' not found!\n"
                    "Searched in:\n" + "\n".join(f"  - {p}" for p in possible_paths) + 
                    "\nPlease download the model from Hugging Face and place it in the correct directory."
                )
            
            logger.info(f"📦 Loading embedding model (one-time only)...")
            _EMBEDDING_MODEL = SentenceTransformer(model_path, device="cpu")
            self.model = _EMBEDDING_MODEL
            logger.info("✅ Embedding model loaded and cached globally")
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def embed_query(self, text: str):
        if self.model is None:
            raise RuntimeError("Embedding model not initialized")
        return self.model.encode(text)
    
    def embed_documents(self, texts: list):
        if self.model is None:
            raise RuntimeError("Embedding model not initialized")
        return self.model.encode(texts)