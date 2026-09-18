"""Focused skin cancer knowledge base (ISIC 2019 classes)."""
import csv
import logging
import os
from typing import Any, Dict, Optional

from app.config import settings
from app.tools.base_tool import BaseTool
from app.utils.isic_classes import normalize_class_name

logger = logging.getLogger(__name__)


class SkinCancerKnowledgeTool(BaseTool):
    name = "skin_cancer_knowledge"
    description = "Returns structured info for ISIC 2019 skin cancer classes."

    def __init__(self):
        super().__init__()
        self.db_path = settings.SKIN_CANCER_DB_PATH
        self.db_map: Dict[str, Dict[str, str]] = {}
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self.db_map[row["disease"].lower()] = row
        else:
            logger.warning("Skin cancer DB not found at %s", self.db_path)

    async def run(self, disease_name: str, run_id: str = "") -> Dict[str, Any]:
        key = normalize_class_name(disease_name).lower()
        if key in self.db_map:
            return {"info": self.db_map[key], "source": "skin_cancer_db"}

        for db_key, row in self.db_map.items():
            if db_key in key or key in db_key:
                return {"info": row, "source": "skin_cancer_db"}

        return {"info": {}, "error": f"No cancer info for: {disease_name}"}
