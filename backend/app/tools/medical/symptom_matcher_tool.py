# app/tools/medical/symptom_matcher_tool.py
import time
import logging
import csv
import os
from typing import List, Dict, Any
from langchain_community.vectorstores import FAISS
from app.utils.embedding_wrapper import LCEmbeddingWrapper
from app.tools.base_tool import BaseTool
from app.config import settings
from app.core.metrics_tracker import metrics_tracker

logger = logging.getLogger(__name__)


class SymptomDiseaseMatcherTool(BaseTool):
    """
    Matches symptoms to diseases using FAISS semantic similarity.
    Only returns skin-related diseases.
    """

    name = "symptom_disease_matcher"
    description = "Matches symptoms to possible skin diseases using FAISS vector search."

    def __init__(self, db_path: str = settings.FAISS_SYMPTOM_PATH):
        super().__init__()
        self.db_path = db_path

        # بررسی وجود فایل CSV
        csv_path = settings.DISEASE_INFO_PATH
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Disease CSV not found at: {csv_path}")

        self.embeddings = LCEmbeddingWrapper()
        self.vectorstore = self._load_or_rebuild_vectorstore()
        
        # 🆕 کلمات کلیدی علائم پوستی (برای تشخیص)
        self.skin_symptom_keywords = [
            # English
            "rash", "itch", "itching", "itchy", "red", "redness", "swollen",
            "swelling", "bump", "blister", "scale", "scaly", "scaling",
            "flake", "flaking", "peeling", "dry", "patch", "spot", "spots",
            "pimple", "acne", "lesion", "sore", "wound", "crust", "crusty",
            "ooze", "weep", "bleed", "pain", "burn", "sting", "skin",
            "dermatitis", "eczema", "psoriasis", "hives", "rashy",
            "discoloration", "pigmentation", "mole", "wart", "cyst",
            "abscess", "boil", "pustule", "nodule", "papule", "plaque",
            # Persian
            "تاول", "قرمز", "قرمزی", "خارش", "خارش‌دار", "پوسته", "پوسته‌پوسته",
            "لکه", "جوش", "زخم", "تورم", "متورم", "التهاب", "سوزش", "خشک",
            "پوسته‌ریزی", "دانه", "ضایعه", "خال", "زگیل", "کهیر", "آکنه",
            "تغییر رنگ", "حساسیت", "اگزما", "پسوریازیس", "درماتیت",
        ]
        
        # 🆕 کلمات کلیدی بیماری‌های غیرپوستی (برای رد کردن)
        self.non_skin_keywords = [
            # English
            "pubic", "lice", "crabs", "sti", "std", "sexually transmitted",
            "eye", "eyelid", "stye", "conjunctivitis", "cataract", "vision",
            "ear", "hearing", "tinnitus", "nasal", "sinus", "throat", "tonsil",
            "dental", "tooth", "toothache", "gum", "tongue", "mouth ulcer",
            "stomach", "abdominal", "diarrhea", "constipation", "nausea",
            "chest", "lung", "breath", "cough", "pneumonia", "bronchitis",
            "heart", "blood pressure", "pulse", "cardiac", "chest pain",
            "urinary", "bladder", "kidney", "prostate", "urine",
            "joint", "bone", "fracture", "arthritis", "gout", "back pain",
            "headache", "migraine", "dizziness", "seizure", "vertigo",
            "anxiety", "depression", "insomnia", "stress", "mental",
            "diabetes", "thyroid", "hormone", "metabolism", "blood sugar",
            "fever", "flu", "cold", "covid", "virus", "infection internal",
            # Persian
            "شپش", "شپشک", "موی زهار", "بیماری مقاربتی", "مقاربتی",
            "چشم", "پلک", "گوش", "دندان", "لثه", "زبان", "دهان",
            "معده", "شکم", "اسهال", "یبوست", "تهوع", "استفراغ",
            "قلب", "فشار خون", "کلیه", "مثانه", "ادرار", "پروستات",
            "مفصل", "استخوان", "شکستگی", "آرتروز", "نقرس", "کمر درد",
            "سردرد", "میگرن", "سرگیجه", "تشنج", "اضطراب", "افسردگی",
            "دیابت", "تیروئید", "هورمون", "قند خون", "تب", "سرماخوردگی",
            "آنفولانزا", "کرونا", "واکسن",
        ]
        
        logger.info(f"Symptom FAISS DB ready at {db_path}")

    def _load_or_rebuild_vectorstore(self) -> FAISS:
        """بارگذاری ایندکس موجود یا ساخت مجدد از CSV"""
        try:
            if os.path.exists(self.db_path) and os.path.exists(os.path.join(self.db_path, "index.faiss")):
                logger.info(f"Loading existing FAISS index from {self.db_path}")
                return FAISS.load_local(
                    self.db_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
            else:
                logger.warning(f"FAISS index not found at {self.db_path}, rebuilding from CSV...")
                return self._rebuild_vectorstore()
                
        except Exception as exc:
            logger.warning(f"Failed to load FAISS DB: {exc}. Rebuilding from CSV...")
            return self._rebuild_vectorstore()

    def _rebuild_vectorstore(self) -> FAISS:
        """ساخت ایندکس FAISS از فایل CSV"""
        csv_path = settings.DISEASE_INFO_PATH
        disease_symptoms: Dict[str, List[str]] = {}

        with open(csv_path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                disease = (row.get("disease") or "").strip()
                symptoms_str = (row.get("symptoms") or row.get("updated") or "").strip()
                if not disease or not symptoms_str:
                    continue
                symptoms = [s.strip() for s in symptoms_str.split(",") if s.strip()]
                if symptoms:
                    disease_symptoms[disease] = symptoms

        if not disease_symptoms:
            raise RuntimeError(f"No symptom data found in {csv_path}. Cannot build FAISS DB.")

        texts = ["; ".join(symptoms) for symptoms in disease_symptoms.values()]
        metadatas = [{"disease": name} for name in disease_symptoms.keys()]
        
        logger.info(f"Building FAISS index with {len(texts)} diseases")
        vectorstore = FAISS.from_texts(texts, self.embeddings, metadatas=metadatas)
        
        os.makedirs(self.db_path, exist_ok=True)
        vectorstore.save_local(self.db_path)
        logger.info(f"FAISS index saved to {self.db_path}")
        
        return vectorstore

    def _is_skin_related_query(self, symptoms: List[str]) -> bool:
        """
        بررسی می‌کند که آیا علائم به پوست مربوط هستند یا خیر.
        - اگر کلمات غیرپوستی داشته باشد → رد می‌شود
        - اگر کلمات پوستی داشته باشد → قبول می‌شود
        """
        if not symptoms:
            return True  # اجازه بده ادامه بده
        
        all_text = " ".join(symptoms).lower()
        
        # 🆕 اول چک کن کلمات غیرپوستی
        for keyword in self.non_skin_keywords:
            if keyword.lower() in all_text:
                logger.info(f"Query rejected: contains non-skin keyword '{keyword}'")
                return False
        
        # 🆕 بعد چک کن کلمات پوستی
        for keyword in self.skin_symptom_keywords:
            if keyword.lower() in all_text:
                return True
        
        # اگر هیچ کدام نبود، اجازه بده (ممکنه علائم عمومی باشه)
        return True

    def _is_valid_skin_disease(self, disease_name: str) -> bool:
        """
        بررسی می‌کند که آیا بیماری معتبر پوستی است.
        """
        disease_lower = disease_name.lower().strip()
        
        # 🆕 رد کردن بیماری‌های حاوی کلمات غیرپوستی
        for keyword in self.non_skin_keywords:
            if keyword.lower() in disease_lower:
                return False
        
        # 🆕 قبول کردن بیماری‌های حاوی کلمات پوستی
        skin_disease_indicators = [
            "dermatitis", "eczema", "psoriasis", "acne", "fungus",
            "fungal", "rash", "lesion", "skin", "cutaneous", "derm",
            "cellulitis", "impetigo", "ringworm", "tinea", "candidiasis",
            "rosacea", "folliculitis", "keratosis", "melanoma", "carcinoma",
            "vitiligo", "alopecia", "hives", "urticaria", "scabies",
            "lichen", "pityriasis", "erysipelas", "abscess", "boil",
            "warts", "molluscum", "herpes", "zoster", "chickenpox", "shingles",
        ]
        
        for indicator in skin_disease_indicators:
            if indicator in disease_lower:
                return True
        
        # اگر جزو ۸ کلاس مدل پوستی ماست
        valid_classes = [
            "cellulitis", "ba-impetigo", "fu-athlete-foot", "fu-nail-fungus",
            "fu-ringworm", "pa-cutaneous-larva-migrans", "vi-chickenpox", "vi-shingles",
            "impetigo", "athlete-foot", "nail-fungus", "ringworm",
            "cutaneous-larva-migrans", "chickenpox", "shingles",
        ]
        if disease_lower in valid_classes:
            return True
        
        # اگر نامشخص است، قبول نکن
        return False

    async def run(self, symptoms: List[str], k: int = 5, run_id: str = None) -> Dict[str, Any]:
        start_time = time.time()
        logger.info("Tool run started", extra={"run_id": run_id, "tool": self.name})
        logger.info(f"Input symptoms: {symptoms}")

        if not symptoms or not isinstance(symptoms, list):
            return {"error": "Input must be a non-empty list of symptoms."}

        # 🆕 چک کردن اینکه علائم پوستی هستند
        if not self._is_skin_related_query(symptoms):
            logger.warning(f"Query appears to be non-skin related: {symptoms}")
            return {
                "matched_diseases": [],
                "warning": "Your symptoms don't appear to be skin-related. Please describe skin-specific symptoms like rash, itching, redness, bumps, or skin discoloration."
            }

        query = ", ".join(symptoms)

        try:
            # 🆕 گرفتن نتایج بیشتر برای فیلتر کردن
            results = self.vectorstore.similarity_search_with_score(query, k=k * 3)

            matched = []
            seen_diseases = set()
            
            for doc, score in results:
                disease_name = doc.metadata.get("disease", "Unknown")
                
                # 🆕 حذف موارد تکراری
                disease_key = disease_name.lower().strip()
                if disease_key in seen_diseases:
                    continue
                
                # 🆕 فقط بیماری‌های معتبر پوستی
                if not self._is_valid_skin_disease(disease_name):
                    logger.info(f"Filtered out: '{disease_name}' (not a skin disease)")
                    continue
                
                seen_diseases.add(disease_key)
                
                matched.append({
                    "disease": disease_name,
                    "symptoms": doc.page_content,
                    "score": float(score)
                })
                
                # 🆕 حداکثر k نتیجه معتبر
                if len(matched) >= k:
                    break
            
            # 🆕 اگر هیچ نتیجه معتبری پیدا نشد
            if not matched:
                logger.warning(f"No valid skin diseases found for: {symptoms}")
                return {
                    "matched_diseases": [],
                    "message": "No matching skin conditions found. Please provide more specific skin symptoms."
                }
            
            logger.info(f"Matched {len(matched)} skin diseases: {[m['disease'] for m in matched]}")
            
            output = {"matched_diseases": matched}

            latency = time.time() - start_time
            logger.info("Tool run finished", extra={"run_id": run_id, "tool": self.name, "latency": latency})

            return output

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Tool run failed: {e}", extra={"run_id": run_id, "tool": self.name, "latency": latency})
            return {"error": f"Search failed: {e}"}