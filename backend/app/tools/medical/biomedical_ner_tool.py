# app/tools/medical/biomedical_ner_tool.py
import time
import logging
import os
import threading
from app.tools.base_tool import BaseTool
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

logger = logging.getLogger(__name__)

# Global cache
_NER_PIPELINE = None
_lock = threading.Lock()

def _get_or_create_ner_pipeline():
    global _NER_PIPELINE
    
    if _NER_PIPELINE is not None:
        return _NER_PIPELINE
    
    with _lock:
        if _NER_PIPELINE is not None:
            return _NER_PIPELINE
        
        # مسیرهای مختلف
        possible_paths = [
            r"D:\final-project\v2\SmartHealth-LLM\backend\app\utils\models\biomedical-ner",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                        "utils", "models", "biomedical-ner"),
        ]
        
        model_name = None
        use_local = False
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.exists(os.path.join(path, "config.json")):
                model_name = path
                use_local = True
                logger.info(f"✅ Found NER model at: {model_name}")
                break
        
        if model_name is None:
            logger.warning("Local NER model not found, using Hugging Face model (requires internet)")
            model_name = "d4data/biomedical-ner-all"
            use_local = False
        
        logger.info("📦 Loading NER model (one-time only)...")
        tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=use_local)
        model = AutoModelForTokenClassification.from_pretrained(model_name, local_files_only=use_local)
        _NER_PIPELINE = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="average")
        logger.info("✅ NER model loaded and cached globally")
    
    return _NER_PIPELINE


class BiomedicalNERTool(BaseTool):
    name = "biomedical_ner"
    description = "Extracts biomedical entities (symptoms, diseases) using local NER model."

    def __init__(self, model_name: str = None):
        super().__init__()
        # Pre-load at initialization
        _get_or_create_ner_pipeline()

    async def run(self, text: str, run_id: str = None):
        start_time = time.time()
        logger.info("Tool run started", extra={"run_id": run_id, "tool": self.name})

        if not text or not isinstance(text, str):
            logger.warning("Input text must be a non-empty string.", extra={"run_id": run_id, "tool": self.name})
            return {"error": "Input text must be a non-empty string."}

        try:
            pipe = _get_or_create_ner_pipeline()
            raw = pipe(text)
        except Exception as e:
            logger.error(f"Error during NER pipeline execution: {e}", extra={"run_id": run_id, "tool": self.name}, exc_info=True)
            return {"error": f"NER pipeline execution failed: {e}"}

        entities = [
            {"text": item["word"], "type": item["entity_group"]}
            for item in raw
        ]

        result = {
            "symptoms": [e["text"] for e in entities if e["type"] in ["SYMPTOM", "Sign_symptom"]],
            "diseases": [e["text"] for e in entities if e["type"] in ["DISEASE"]],
            "drugs": [e["text"] for e in entities if e["type"] in ["DRUG"]],
            "entities": entities
        }

        end_time = time.time()
        latency = end_time - start_time
        logger.info("Tool run finished", extra={"run_id": run_id, "tool": self.name, "latency": latency})

        return result