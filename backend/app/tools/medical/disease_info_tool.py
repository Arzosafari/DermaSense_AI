# نسخه اصلاح شده با پشتیبانی از مسیر محلی برای Embedding
import csv
import os
import time
import logging
from typing import List, Dict, Optional, Any
from app.tools.base_tool import BaseTool
from app.utils.embeddings import EmbeddingSingleton
import faiss
from app.config import settings
from app.core.metrics_tracker import metrics_tracker

logger = logging.getLogger(__name__)


class DiseaseInfoRetrieverTool(BaseTool):
    name = "disease_info_retriever"
    description = "Returns detailed disease info from the local CSV database."

    def __init__(self):
        super().__init__()

        self.csv_path = settings.DISEASE_INFO_PATH
        self.faiss_path = os.path.join(settings.FAISS_DISEASE_PATH, "index.faiss")
        self.pkl_path = os.path.join(settings.FAISS_DISEASE_PATH, "index.pkl")

        # بررسی وجود فایل‌های مورد نیاز
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"Disease CSV not found at: {self.csv_path}")
        
        if not os.path.exists(self.faiss_path):
            logger.warning(f"FAISS index not found at {self.faiss_path}. Will try to create it.")

        # Load embeddings (از مسیر محلی اگر تنظیم شده باشد)
        self.embedding_model = EmbeddingSingleton.get_instance()

        # Load CSV database
        self.db = self._load_csv()
        self.disease_list = [row["disease"].strip() for row in self.db]
        self.db_map = {row["disease"].lower().strip(): row for row in self.db}

        # Load FAISS index if exists
        if os.path.exists(self.faiss_path):
            self.index = faiss.read_index(self.faiss_path)
        else:
            logger.warning("FAISS index not available. Semantic search will be disabled.")
            self.index = None

    def _load_csv(self) -> List[Dict[str, str]]:
        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _normalize(self, x: str) -> str:
        return " ".join(x.replace("-", " ").replace("_", " ").split())

    def _find_best_match(self, disease_name: str, threshold: float = 0.80) -> Optional[str]:
        query = disease_name.lower().strip()

        # 1. exact match
        if query in self.db_map:
            return query

        # 2. normalized match
        for key in self.db_map:
            if self._normalize(key) == self._normalize(query):
                return key

        # 3. partial token containment
        query_tokens = set(query.split())
        for key in self.db_map:
            key_tokens = set(key.split())
            if query_tokens.issubset(key_tokens):
                return key

        # 4. semantic match (only if FAISS is available)
        if self.index is not None:
            try:
                emb = self.embedding_model.embed_query(disease_name).reshape(1, -1)
                scores, idx = self.index.search(emb, 1)
                
                if scores[0][0] >= threshold:
                    return self.disease_list[idx[0][0]].lower()
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}")

        return None

    async def run(self, disease_name: str, fields: Optional[List[str]] = None, run_id: str = None) -> Dict[str, Any]:
        start_time = time.time()
        logger.info("Tool run started", extra={"run_id": run_id, "tool": self.name})

        if not disease_name:
            return {"error": "No disease name provided"}

        match_key = self._find_best_match(disease_name)

        if not match_key:
            return {"error": f"No match found for '{disease_name}'. Please check the spelling."}

        info = self.db_map.get(match_key, {})

        if fields:
            output = {"info": {f: info.get(f, "N/A") for f in fields}}
        else:
            output = {"info": info}

        latency = time.time() - start_time
        logger.info("Tool run finished", extra={"run_id": run_id, "tool": self.name, "latency": latency})

        return output