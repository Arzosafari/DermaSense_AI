# backend/app/agents/roles/image_agent.py
import logging
import json
import time
import base64
import io
from datetime import datetime
from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from PIL import Image

from app.agents.base.base_agent import BaseAgent
from app.tools.ml.panderm_skin_cancer_tool import PanDermSkinCancerTool
from app.tools.medical.skin_cancer_knowledge_tool import SkinCancerKnowledgeTool
from app.tools.medical.doctor_recommender_tool import DoctorRecommenderTool
from app.utils.abcde_analyzer import analyze_abcde
from app.utils.malignancy_scorer import compute_malignancy_risk
from app.utils.prompt_loader import load_prompt
from app.core.domain_filter import is_skin_related_image, out_of_scope_message, detect_language
from app.core.medical_context_service import medical_context_service
from app.core.panderm_explainability import generate_panderm_heatmap
from app.core.analysis_history_service import analysis_history_service
from app.core.image_quality_service import image_quality_service
from app.core.heatmap_service import heatmap_service
from app.core.pdf_report_service import pdf_report_service
from app.core.panderm_explainability import generate_panderm_heatmap
from app.core.supported_lesion_gate import SupportedLesionGate
from app.config import settings

logger = logging.getLogger(__name__)


def check_prediction_safety(all_scores: dict) -> tuple[bool, str]:
    """
    OOD detection using probability distribution similarity.
    
    Uses the concentration of probability in top classes as a proxy for 
    embedding similarity to known lesion patterns. Valid lesions typically
    show characteristic distribution patterns.
    
    Args:
        all_scores: Dictionary of {class_name: probability} from model
        
    Returns:
        tuple: (is_safe, reason) where is_safe=True means prediction is reliable
    """
    if not settings.PREDICTION_SAFETY_ENABLED:
        return True, "Safety gate disabled"
    
    if not all_scores or len(all_scores) < 2:
        return False, "Insufficient probability data"
    
    # Convert to sorted list of (class, probability) tuples
    sorted_probs = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Top-3 probabilities
    top1_prob = sorted_probs[0][1]
    top2_prob = sorted_probs[1][1] if len(sorted_probs) > 1 else 0.0
    top3_prob = sorted_probs[2][1] if len(sorted_probs) > 2 else 0.0
    
    # Calculate probability concentration in top-3 classes
    # This is a proxy for how "typical" the distribution is for known lesions
    top3_concentration = top1_prob + top2_prob + top3_prob
    
    # Valid lesions typically have >50% probability in top-3 classes
    # This captures the idea that the model is "confidently uncertain" among related classes
    # rather than being uniformly uncertain across all classes
    similarity_score = top3_concentration
    
    if similarity_score < settings.OOD_SIMILARITY_THRESHOLD:
        return False, f"low distribution similarity ({similarity_score:.2%} < {settings.OOD_SIMILARITY_THRESHOLD:.2%})"
    
    return True, f"distribution similarity acceptable ({similarity_score:.2%})"


class ImageAgentState(TypedDict):
    user_message: str
    image_base64: Optional[str]
    predicted_class: str
    confidence: float
    filtered: bool
    disease_info: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    abcde_analysis: Dict[str, Any]
    doctor_guidance: Dict[str, Any]
    final_output: str
    run_id: str
    user_profile: Dict[str, Any]
    image_quality: Dict[str, Any]
    top3_predictions: list  # 🆕 Add to state definition
    all_scores: dict  # 🆕 Add to state definition
    heatmap: Dict[str, Any]  # 🆕 Add heatmap to state definition


class ImageAgent(BaseAgent):
    agent_name = "image_agent"

    def __init__(self, context):
        super().__init__(context)
        
        # بارگذاری ابزارهای مورد نیاز
        if not hasattr(self, "tools") or self.tools is None:
            self.tools = {}
        
        if "skin_disease_predictor" not in self.tools:
            logger.info("Loading PanDermSkinCancerTool...")
            self.tools["skin_disease_predictor"] = PanDermSkinCancerTool()

        if "skin_cancer_knowledge" not in self.tools:
            logger.info("Loading SkinCancerKnowledgeTool...")
            self.tools["skin_cancer_knowledge"] = SkinCancerKnowledgeTool()

        if "doctor_recommender" not in self.tools:
            self.tools["doctor_recommender"] = DoctorRecommenderTool()

        self.predictor = self.tools["skin_disease_predictor"]
        self.knowledge_tool = self.tools["skin_cancer_knowledge"]
        self.doctor_tool = self.tools["doctor_recommender"]
        
        # Initialize supported lesion gate
        self.supported_lesion_gate = SupportedLesionGate()
        
        logger.info(f"✅ ImageAgent initialized successfully")

    def _decode_image(self, base64_str: str) -> Image.Image:
        """decode a base64 string into a PIL Image with compression."""
        try:
            if "base64," in base64_str:
                base64_str = base64_str.split("base64,")[1]
            
            image_bytes = base64.b64decode(base64_str)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            # Compress image to reduce size while maintaining quality
            max_size = (1024, 1024)  # Limit to 1024x1024
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                logger.info(f"🔄 Image compressed from original to {image.size}")
            
            logger.info(f"✅ Image decoded successfully | size={image.size}")
            return image
        except Exception as e:
            logger.error(f"❌ Failed to decode image: {e}")
            raise ValueError(f"Invalid image data: {e}")

    async def predict_node(self, state: ImageAgentState):
        """گام ۱: پیش‌بینی کلاس بیماری پوستی از روی تصویر + فیلتر اعتبارسنجی"""
        run_id = state["run_id"]
        logger.info("=" * 50)
        logger.info("🔍 Node: predict", extra={"run_id": run_id, "agent": self.agent_name})
        logger.info("=" * 50)

        state["filtered"] = False
        state["confidence"] = 0.0

        image_base64 = state.get("image_base64")
        if not image_base64:
            logger.error("❌ No image provided")
            state["predicted_class"] = "unknown"
            state["filtered"] = True
            lang = detect_language(state.get("user_message", ""))
            state["final_output"] = out_of_scope_message(lang)
            return state

        try:
            logger.info("📸 Decoding image...")
            image = self._decode_image(image_base64)
            
            # Assess image quality before running prediction
            logger.info("🔍 Assessing image quality...")
            quality_assessment = image_quality_service.assess_image_quality(image)
            state["image_quality"] = quality_assessment
            
            if not quality_assessment.get("acceptable", True):
                logger.warning(f"⚠️ Image quality issue: {quality_assessment.get('recommendation', 'Unknown issue')}")
                # Don't block analysis, but note the quality issue
                # The LLM can provide guidance based on quality assessment
            
            # NEW: Supported lesion gate - check if image is suitable for skin lesion analysis
            logger.info("🛡️ Running supported lesion gate...")
            is_supported, lesion_reason = self.supported_lesion_gate.is_supported_lesion(image)
            logger.info(f"🛡️ Supported lesion gate result: is_supported={is_supported}, reason={lesion_reason}")
            
            if not is_supported:
                logger.warning(f"⛔ Image REJECTED by supported lesion gate: {lesion_reason}")
                state["filtered"] = True
                state["predicted_class"] = "unknown"
                state["confidence"] = 0.0
                lang = detect_language(state.get("user_message", ""))
                state["final_output"] = "Unable to classify this image reliably. Please upload a clear close-up image of a supported skin lesion."
                return state
            
            logger.info(f"✅ Image ACCEPTED by supported lesion gate")
            
            logger.info("🤖 Running disease prediction...")
            prediction_start = time.time()
            prediction_result = await self.predictor.run(image)
            prediction_time = time.time() - prediction_start
            
            # DEBUG: Log PanDerm prediction result structure
            logger.info(f"=== PAN DERM PREDICTION RESULT ===")
            logger.info(f"PanDerm result type: {type(prediction_result)}")
            logger.info(f"PanDerm result: {prediction_result}")
            if isinstance(prediction_result, dict):
                logger.info(f"PanDerm result keys: {list(prediction_result.keys())}")
                logger.info(f"PanDerm all_scores: {prediction_result.get('all_scores', {})}")
                logger.info(f"PanDerm top3_predictions: {prediction_result.get('top3_predictions', [])}")
                logger.info(f"PanDerm top_predictions: {prediction_result.get('top_predictions', [])}")
            
            state["predicted_class"] = prediction_result.get("predicted_class", "unknown")
            state["confidence"] = prediction_result.get("confidence", 0.0)
            
            # Handle both naming conventions: top3_predictions (old) and top_predictions (new)
            top3 = prediction_result.get("top3_predictions") or prediction_result.get("top_predictions", [])
            state["top3_predictions"] = top3
            state["all_scores"] = prediction_result.get("all_scores", {})  # Store all class probabilities
            
            # NEW: Safety gate for OOD/unknown detection
            logger.info("🛡️ Running prediction safety gate...")
            is_safe, safety_reason = check_prediction_safety(state["all_scores"])
            logger.info(f"🛡️ Safety gate result: is_safe={is_safe}, reason={safety_reason}")
            
            if not is_safe:
                logger.warning(f"⛔ Prediction REJECTED by safety gate: {safety_reason}")
                state["filtered"] = True
                state["predicted_class"] = "unknown"
                state["confidence"] = 0.0
                lang = detect_language(state.get("user_message", ""))
                state["final_output"] = "Unable to classify this image reliably. Please upload a clear close-up image of a single skin lesion."
                return state
            
            logger.info(f"✅ Prediction ACCEPTED by safety gate")
            
            # Generate explainability heatmap using Attention Rollout
            state["heatmap"] = {"available": False, "reason": "Not attempted"}
            try:
                from app.config import settings
                output_dir = getattr(settings, 'HEATMAP_OUTPUT_DIR', 'generated_heatmaps')
                
                # Get predicted class index for explainability
                class_names = self.predictor.panderm_tool.class_names
                predicted_class_idx = class_names.index(state["predicted_class"]) if state["predicted_class"] in class_names else 0
                
                # Get transformed tensor
                tensor = self.predictor.panderm_tool.transform(image).unsqueeze(0).to(self.predictor.panderm_tool.device)
                
                # Generate heatmap
                heatmap_result = generate_panderm_heatmap(
                    model=self.predictor.panderm_tool.model,
                    device=self.predictor.panderm_tool.device,
                    image=image,
                    tensor=tensor,
                    predicted_class_idx=predicted_class_idx,
                    output_dir=output_dir,
                    analysis_id=run_id
                )
                
                state["heatmap"] = heatmap_result
                logger.info(f"Heatmap generation: {heatmap_result.get('available', False)}")
                
            except Exception as heatmap_error:
                logger.error(f"Heatmap generation failed: {heatmap_error}", exc_info=True)
                state["heatmap"] = {
                    "available": False,
                    "reason": f"Heatmap generation error: {str(heatmap_error)}"
                }
            
            # 🆕 لاگ دقیق prediction
            logger.info(
                f"🎯 Predicted: {state['predicted_class']} "
                f"(confidence={state['confidence']:.4f}, time={prediction_time:.2f}s)"
            )
            
            # 🆕 نمایش top-3 predictions اگه موجود باشه
            if "top3_predictions" in state:
                logger.info(f"📊 Top-3: {state['top3_predictions']}")
            
            if "all_scores" in state:
                logger.info(f"📊 All scores in state: {state['all_scores']}")
            else:
                logger.warning("⚠️ all_scores NOT in state!")
            
            # 🆕 فیلتر اعتبارسنجی تصویر (جدید با لایه‌های چندگانه) - قبل از heatmap و تحلیل‌های دیگر
            ok, reason = is_skin_related_image(
                state.get("user_message", ""),
                state["predicted_class"],
                state["confidence"],
                image_base64=state.get("image_base64"),  # 🆕 برای color check

            )
            
            logger.info(f"🔍 Filter result: ok={ok}, reason={reason}")
            logger.info(f"   Class: {state['predicted_class']}")
            logger.info(f"   Confidence: {state['confidence']:.4f}")
            logger.info(f"   User message: '{state.get('user_message', '')[:100]}'")
            
            if not ok:
                lang = detect_language(state.get("user_message", ""))
                state["filtered"] = True
                state["final_output"] = out_of_scope_message(lang)
                state["heatmap"] = {"available": False, "reason": "Image filtered as non-skin related"}
                logger.info(f"⛔ Image REJECTED: {reason}")
                return state  # برگشت زودهنگام بدون heatmap و تحلیل‌های دیگر
            
            logger.info(f"✅ Image ACCEPTED: {reason}")
            
            # Generate explainability heatmap using Attention Rollout (فقط برای تصاویر پوستی)
            state["heatmap"] = {"available": False, "reason": "Not attempted"}
            try:
                from app.config import settings
                output_dir = getattr(settings, 'HEATMAP_OUTPUT_DIR', 'generated_heatmaps')
                
                # Get predicted class index for explainability
                class_names = self.predictor.panderm_tool.class_names
                predicted_class_idx = class_names.index(state["predicted_class"]) if state["predicted_class"] in class_names else 0
                
                # Get transformed tensor
                tensor = self.predictor.panderm_tool.transform(image).unsqueeze(0).to(self.predictor.panderm_tool.device)
                
                # Generate heatmap
                heatmap_result = generate_panderm_heatmap(
                    model=self.predictor.panderm_tool.model,
                    device=self.predictor.panderm_tool.device,
                    image=image,
                    tensor=tensor,
                    predicted_class_idx=predicted_class_idx,
                    output_dir=output_dir,
                    analysis_id=run_id
                )
                
                state["heatmap"] = heatmap_result
                logger.info(f"Heatmap generation: {heatmap_result.get('available', False)}")
                
            except Exception as heatmap_error:
                logger.error(f"Heatmap generation failed: {heatmap_error}", exc_info=True)
                state["heatmap"] = {
                    "available": False,
                    "reason": f"Heatmap generation error: {str(heatmap_error)}"
                }
            
            state["risk_assessment"] = compute_malignancy_risk(
                predicted_class=state["predicted_class"],
                confidence=state["confidence"],
                user_profile=state.get("user_profile"),
                abcde_score=state.get("abcde_analysis", {}).get("abcde_score"),
                top3=prediction_result.get("top3_predictions", []),
            )
            
            # Update field names for clarity (backward compatibility)
            risk_assessment = state["risk_assessment"]
            if "screening_score" in risk_assessment:
                # Ensure backward compatibility by keeping old field names
                risk_assessment["risk_score"] = risk_assessment.get("screening_score")
                risk_assessment["risk_level"] = risk_assessment.get("screening_level")
                risk_assessment["risk_factors"] = risk_assessment.get("factors")
                
        except Exception as e:
            logger.error(f"❌ Image prediction failed: {e}", exc_info=True)
            state["predicted_class"] = "error"
            state["confidence"] = 0.0
            state["filtered"] = True
            lang = detect_language(state.get("user_message", ""))
            state["final_output"] = out_of_scope_message(lang)
        
        return state

    async def lookup_node(self, state: ImageAgentState):
        """گام ۲: دریافت اطلاعات بیماری از پایگاه داده."""
        run_id = state["run_id"]
        logger.info("-" * 40)
        logger.info("📚 Node: lookup", extra={"run_id": run_id, "agent": self.agent_name})
        logger.info("-" * 40)

        predicted_class = state.get("predicted_class")
        
        if not predicted_class or predicted_class in ["unknown", "error"]:
            logger.warning(f"⚠️ No valid prediction to look up (class={predicted_class})")
            state["disease_info"] = {}
            return state

        # تبدیل نام کلاس به نام قابل جستجو
        if "-" in predicted_class:
            disease_name = predicted_class.split("-")[-1]
        else:
            disease_name = predicted_class
        
        logger.info(f"🔎 Looking up disease: {disease_name} (from class: {predicted_class})")
        
        try:
            lookup_start = time.time()
            retrieved = await self.knowledge_tool.run(disease_name, run_id=run_id)
            lookup_time = time.time() - lookup_start
            
            if retrieved and isinstance(retrieved, dict):
                if "error" in retrieved:
                    logger.warning(f"⚠️ No info found for {disease_name}: {retrieved['error']}")
                    state["disease_info"] = {}
                else:
                    info = retrieved.get("info", retrieved)
                    state["disease_info"] = info if isinstance(info, dict) else {}
                    logger.info(f"✅ Disease info retrieved | fields={list(state['disease_info'].keys())} | time={lookup_time:.2f}s")
            else:
                state["disease_info"] = {}
                
        except Exception as e:
            logger.error(f"❌ Disease lookup failed: {e}", exc_info=True)
            state["disease_info"] = {}
        
        return state

    async def assess_node(self, state: ImageAgentState):
        """Run ABCDE text analysis and doctor visit guidance."""
        run_id = state["run_id"]
        state["abcde_analysis"] = analyze_abcde(state.get("user_message", ""))
        risk = state.get("risk_assessment") or {}
        state["risk_assessment"] = compute_malignancy_risk(
            predicted_class=state.get("predicted_class", "unknown"),
            confidence=state.get("confidence", 0.0),
            user_profile=state.get("user_profile"),
            abcde_score=state["abcde_analysis"].get("abcde_score"),
        )
        profile = state.get("user_profile") or {}
        location = profile.get("city") or profile.get("location")
        state["doctor_guidance"] = await self.doctor_tool.run(
            risk_level=risk.get("risk_level") or state["risk_assessment"].get("risk_level", "medium"),
            location=location,
            predicted_class=state.get("predicted_class"),
            run_id=run_id,
        )
        return state

    def build_compact_explanation_context(self, state: ImageAgentState) -> dict:
        """Build a compact but semantically complete context for Groq explanation."""
        risk = state.get("risk_assessment") or {}
        image_quality = state.get("image_quality", {})
        top3 = state.get("top3_predictions", [])
        abcde = state.get("abcde_analysis", {})
        doctor = state.get("doctor_guidance", {})
        disease_info = state.get("disease_info", {})
        detected_language = detect_language(state.get("user_message", ""))
        user_profile = state.get("user_profile", {})
        user_message = state.get("user_message", "")

        # Extract key symptoms from user message (simple extraction)
        symptoms = self._extract_symptoms_from_message(user_message)

        # Build compact disease info (only essential fields)
        compact_disease_info = {}
        if disease_info:
            for key in ["disease", "description", "symptoms", "treatment", "cause", "prevention"]:
                if key in disease_info:
                    compact_disease_info[key] = disease_info[key]

        # Extract risk factors (compact)
        risk_factors = risk.get("factors", [])[:3]  # Limit to top 3

        # Extract doctor guidance (compact)
        visit_guidance = doctor.get("visit_guidance", {})
        recommendations = doctor.get("recommendations", [])[:2]  # Limit

        # ABCDE info (only if applicable)
        abcde_applicable = risk.get("abcde_applicable", False) or abcde.get("abcde_score", 0) > 0
        abcde_score = abcde.get("abcde_score", 0)
        abcde_criteria = abcde.get("criteria", {})
        abcde_warnings = abcde.get("warnings", [])

        # Extract age only if medically relevant
        age = user_profile.get("age")
        age_valid = age if age and isinstance(age, (int, float)) and 0 < age < 120 else None

        # Extract relevant user context from profile
        user_context = self._build_user_context(user_profile, symptoms)

        return {
            "language": detected_language,
            "user_request": user_message[:300],
            "prediction": {
                "class": state.get("predicted_class", "unknown"),
                "confidence": round(state.get("confidence", 0.0), 4),
            },
            "top3": [
                {"class": p.get("class"), "probability": round(p.get("confidence", 0.0), 4)}
                for p in top3[:3] if p.get("class")
            ],
            "risk": {
                "level": risk.get("screening_level", risk.get("risk_level", "unknown")),
                "score": risk.get("screening_score", risk.get("risk_score", 0)),
                "is_malignant_prediction": risk.get("is_malignant_prediction", False),
                "urgency": risk.get("urgency_message", ""),
                "factors": risk_factors,
            },
            "image_quality": {
                "acceptable": image_quality.get("acceptable", True),
                "recommendation": image_quality.get("recommendation") if not image_quality.get("acceptable", True) else None,
            },
            "symptoms": symptoms,
            "recommendations": {
                "specialist": visit_guidance.get("specialist", "dermatologist"),
                "timeframe": visit_guidance.get("timeframe", ""),
                "visit_type": visit_guidance.get("visit_type", ""),
                "bring": visit_guidance.get("bring", [])[:3],
                "questions": visit_guidance.get("questions", [])[:2],
            },
            "abcde": {
                "applicable": abcde_applicable,
                "score": abcde_score,
                "criteria_met": [k for k, v in abcde_criteria.items() if v],
                "warnings": abcde_warnings,
            },
            "disease_info": compact_disease_info,
            "user_context": user_context,
        }

    def _build_user_context(self, user_profile: dict, current_symptoms: list) -> dict:
        """Build compact user context from profile - only relevant, available fields."""
        context = {}
        
        # Age
        age = user_profile.get("age")
        if age and isinstance(age, (int, float)) and 0 < age < 120:
            context["age"] = int(age)
        
        # Skin type
        skin_type = user_profile.get("skin_type")
        if skin_type:
            context["skin_type"] = skin_type
        
        # Allergies (compact)
        allergies = user_profile.get("allergies") or user_profile.get("allergy")
        if allergies:
            if isinstance(allergies, list):
                context["allergies"] = allergies[:5]
            elif isinstance(allergies, str) and allergies.strip():
                context["allergies"] = [a.strip() for a in allergies.split(",")[:5]]
        
        # Medical conditions (compact - only relevant ones)
        conditions = user_profile.get("medical_conditions") or user_profile.get("chronic_conditions") or user_profile.get("medical_history")
        if conditions:
            if isinstance(conditions, list):
                context["conditions"] = conditions[:5]
            elif isinstance(conditions, str) and conditions.strip():
                context["conditions"] = [c.strip() for c in conditions.split(",")[:5]]
        
        # Previously reported symptoms from profile
        prev_symptoms = user_profile.get("reported_symptoms") or user_profile.get("previous_symptoms")
        if prev_symptoms:
            if isinstance(prev_symptoms, list):
                context["previous_symptoms"] = prev_symptoms[:5]
            elif isinstance(prev_symptoms, str) and prev_symptoms.strip():
                context["previous_symptoms"] = [s.strip() for s in prev_symptoms.split(",")[:5]]
        
        # Current symptoms from message
        if current_symptoms:
            context["current_symptoms"] = current_symptoms
        
        # Only return if we have any data
        return context if context else {}

    def _extract_symptoms_from_message(self, message: str) -> list:
        """Simple symptom extraction from user message."""
        if not message:
            return []
        symptom_keywords = [
            "itch", "itching", "scratch", "pain", "hurt", "bleed", "bleeding",
            "grow", "growing", "change", "changing", "enlarg", "new",
            "bump", "lump", "spot", "mole", "lesion", "rash",
            "\u062e\u0627\u0631\u0634", "\u062f\u0631\u062f", "\u062e\u0648\u0646", "\u0631\u0634\u062f",
            "\u062a\u063a\u06cc\u06cc\u0631", "\u0646\u0648", "\u06a9\u0634\u0646", "\u062e\u0627\u0644", "\u0622\u0644\u0631\u0698\u06cc"
        ]
        found = []
        lower = message.lower()
        for kw in symptom_keywords:
            if kw in lower and kw not in found:
                found.append(kw)
        return found[:5]  # Limit

    def build_compact_prompt(self, state: ImageAgentState) -> str:
        """Build an ultra-compact prompt for Groq - minimal tokens, max quality."""
        ctx = self.build_compact_explanation_context(state)
        lang = ctx["language"]

        # Build ultra-compact data
        top3_str = "; ".join(f"{p['class']}: {p['probability']:.2%}" for p in ctx["top3"] if p.get("class")) or "N/A"
        symptoms_str = ", ".join(ctx["symptoms"]) if ctx["symptoms"] else "None"
        risk_factors_str = "; ".join(ctx["risk"]["factors"]) if ctx["risk"]["factors"] else "None"
        disease_desc = ctx["disease_info"].get("description", "")[:180]
        risk = ctx["risk"]
        img_q = ctx["image_quality"]
        rec = ctx["recommendations"]
        abcde = ctx["abcde"]
        user_ctx = json.dumps(ctx.get("user_context", {}), ensure_ascii=False)

        # Minimal system prompt (~400 tokens)
        system_prompt = (
            f"You are a dermatology AI screening explainer. Output in {lang} only.\n"
            f"Use model output EXACTLY: class={ctx['prediction']['class']} conf={ctx['prediction']['confidence']:.2%}."
            f"NEVER change probabilities, invent findings, or claim confidence=cancer probability.\n"
            f"If conf low, state prediction uncertain. Show top 3 alternatives sorted by prob.\n"
            f"User context (use if relevant): {user_ctx}. Current symptoms: {symptoms_str}.\n"
            f"Message: {ctx['user_request']}. If 'Analyze this image', do not invent symptoms.\n"
            f"REQUIRED STRUCTURE:\n"
            f"1) **AI Screening Result**: class, confidence (clarify != cancer prob)\n"
            f"2) **Alternative Predictions**: top 3 with probabilities\n"
            f"3) **Information You Provided**: only relevant provided info\n"
            f"4) **AI Interpretation**: cautious 'may be consistent with', no 'you have'\n"
            f"5) **ABCDE**: if applicable explain, else 'could not be reliably performed'\n"
            f"6) **Recommended Next Steps**: proportional to risk level {risk['level']}\n"
            f"7) **Disclaimer**: educational only, not medical diagnosis.\n"
            f"Target 350-550 words. No repetition. No architecture explanation."
        )

        # Ultra-compact user data
        user_prompt = (
            f"class={ctx['prediction']['class']} conf={ctx['prediction']['confidence']:.2%}"
            f" top3={top3_str}"
            f" risk={risk['level']} score={risk['score']}/100 malignant={risk['is_malignant_prediction']}"
            f" factors={risk_factors_str}"
            f" img_ok={img_q['acceptable']} note={img_q['recommendation'] or 'ok'}"
            f" abcde_app={abcde['applicable']} sc={abcde['score']}/5 crit={','.join(abcde['criteria_met']) or 'none'}"
            f" disease={disease_desc}"
            f" rec={rec['specialist']} time={rec['timeframe']} type={rec['visit_type']}"
        )

        return system_prompt + "\n" + user_prompt

    async def llm_node(self, state: ImageAgentState):
        """گام ۳: تولید پاسخ نهایی با LLM - Compact version"""
        run_id = state["run_id"]
        logger.info("-" * 40)
        logger.info("🤖 Node: llm (compact)", extra={"run_id": run_id, "agent": self.agent_name})
        logger.info("-" * 40)

        # Detect language from user message
        detected_language = detect_language(state.get("user_message", ""))
        logger.info(f"Detected language for image analysis: {detected_language}", extra={"run_id": run_id, "agent": self.agent_name})

        # Build compact prompt
        prompt = self.build_compact_prompt(state)

        # SAFE DEBUG LOGGING - Analyze prompt composition
        logger.info("=" * 80)
        logger.info("IMAGE AGENT COMPACT PROMPT DIAGNOSTICS")
        logger.info("=" * 80)
        logger.info(f"Total prompt length: {len(prompt):,} characters")
        logger.info(f"User message: '{state.get('user_message', 'No message')[:100]}'")
        logger.info(f"Predicted class: {state.get('predicted_class', 'unknown')}")
        logger.info(f"Confidence: {state.get('confidence', 0.0):.4f}")
        logger.info(f"Top3 count: {len(state.get('top3_predictions', []))}")

        # CRITICAL: Check for image data in prompt
        has_base64 = "base64" in prompt.lower()
        has_data_url = "data:image" in prompt
        logger.info(f"Has base64 in prompt: {has_base64}")
        logger.info(f"Has data:image URL in prompt: {has_data_url}")

        if has_base64 or has_data_url:
            logger.error("🚨 CRITICAL: Image data detected in LLM prompt!")
            logger.error("🚨 This should NOT happen - image is for PanDerm only, not LLM")

        logger.info("=" * 80)

        logger.info(f"📤 Sending compact prompt to LLM | prompt_len={len(prompt)}")

        try:
            llm_start = time.time()
            logger.info(f"🕒 Starting LLM call for image explanation with max_tokens=500")

            raw = await self.llm_call(
                prompt,
                run_id=run_id,
                max_tokens=500,  # Ultra-compact for token efficiency
                temperature=0.7
            )

            llm_time = time.time() - llm_start
            logger.info(f"📥 LLM response received | length={len(raw)} | time={llm_time:.2f}s")

            state["final_output"] = raw.strip()

        except Exception as e:
            logger.error(f"❌ LLM call failed: {e}", exc_info=True)
            # Provide a structured fallback with the analysis data
            predicted_class = state.get("predicted_class", "unknown")
            confidence = state.get("confidence", 0)
            top3 = state.get("top3_predictions", [])
            risk = state.get("risk_assessment") or {}
            disease_info = state.get("disease_info", {})
            doctor = state.get("doctor_guidance", {})
            visit_guidance = doctor.get("visit_guidance", {})

            # Build top3 string for fallback
            top3_str = ""
            for i, pred in enumerate(top3[:3], 1):
                top3_str += f"{i}. {pred.get('class', 'unknown')} — {pred.get('confidence', 0):.2%}\n"

            # Check language for fallback response
            if detected_language == "persian":
                desc = disease_info.get("description", "توضیح در دسترس نیست")[:200]
                fallback_text = (
                    f"**احتمال بیشتر: {predicted_class}**\n\n"
                    f"**چرا مطابقت دارد:**\n"
                    f"مدل PanDerm این ضایعه را با احتمال {confidence:.2%} در گروه {predicted_class} قرار داده است. "
                    f"این عدد نشان‌دهنده میزان اطمینان مدل در طبقه‌بندی تصویر است و به معنی تشخیص قطعی پزشکی نیست.\n\n"
                    f"**چرا ممکن است مطابقت نکند:**\n"
                    f"طبقه‌بندی تصویر توسط هوش مصنوعی احتمالی است و برخی ضایعات پوستی می‌توانند از نظر ظاهری شباهت داشته باشند. "
                    f"بنابراین نتیجه باید در کنار معاینه بالینی تفسیر شود.\n\n"
                    f"**آن چیست:**\n{desc}\n\n"
                    f"**احتمال‌های دیگر:**\n{top3_str if top3_str else 'پیش‌بینی‌های جایگزین در دسترس نیست'}\n\n"
                    f"**ارزیابی غربالگری:**\n"
                    f"شاخص غربالگری هوش مصنوعی در این تحلیل «{risk.get('screening_level', risk.get('risk_level', 'نامشخص'))}» "
                    f"و امتیاز آن {risk.get('screening_score', risk.get('risk_score', 0))} از ۱۰۰ است. "
                    f"این شاخص یک ابزار غربالگری هوش مصنوعی است و یک امتیاز بالینی معتبر برای تعیین خطر سرطان محسوب نمی‌شود.\n\n"
                    f"**چه زمانی به متخصص پوست مراجعه کنید:**\n"
                    f"{visit_guidance.get('timeframe', 'به متخصص پوست مراجعه کنید')}\n\n"
                    f"**پایش در خانه:**\n"
                    f"از ضایعه در فواصل منظم عکس بگیرید و تغییرات احتمالی آن را ثبت کنید. "
                    f"در صورت مشاهده تغییرات قابل توجه، ارزیابی پزشکی انجام دهید.\n\n"
                    f"**توجه:** این نتیجه صرفاً یک غربالگری هوش مصنوعی است و جایگزین تشخیص پزشکی توسط متخصص پوست "
                    f"با معاینه بالینی و بیوپسی نیست. در صورت شک، همیشه مراجعه پزشکی کنید."
                )
            else:
                desc = disease_info.get("description", "No description available")[:200]
                fallback_text = (
                    f"**Most likely: {predicted_class}**\n\n"
                    f"**Why it may fit:**\n"
                    f"The PanDerm model assigned {confidence:.2%} probability to {predicted_class}. "
                    f"This is a model confidence score and does not represent a definitive medical diagnosis.\n\n"
                    f"**Why it may not fit:**\n"
                    f"Image classification is probabilistic and visually similar lesions can receive different predictions. "
                    f"Clinical correlation is recommended.\n\n"
                    f"**What it is:**\n{desc}\n\n"
                    f"**Other possibilities:**\n{top3_str if top3_str else 'Alternative predictions not available'}\n\n"
                    f"**Screening assessment:**\n"
                    f"The AI screening indicator is {risk.get('screening_level', risk.get('risk_level', 'unknown'))} "
                    f"with a score of {risk.get('screening_score', risk.get('risk_score', 0))}/100. "
                    f"This is an AI screening score, not a clinically validated cancer-risk score. "
                    f"It cannot rule out or confirm malignancy.\n\n"
                    f"**When to see a dermatologist:**\n"
                    f"{visit_guidance.get('timeframe', 'Consult a dermatologist')}\n\n"
                    f"**Home monitoring:**\n"
                    f"Take periodic photos of the lesion and track any changes. "
                    f"If you notice significant changes, seek medical evaluation.\n\n"
                    f"**Disclaimer:** This AI screening is for educational purposes only and is NOT a medical diagnosis. "
                    f"Only a board-certified dermatologist can diagnose skin cancer through clinical examination and biopsy. "
                    f"When in doubt, always seek professional care."
                )
            state["final_output"] = fallback_text

        logger.info(f"✅ Final output ready | length={len(state['final_output'])}")
        return state

    async def reject_node(self, state: ImageAgentState):
        """گام رد: تصویر خارج از حوزه تخصص"""
        run_id = state["run_id"]
        logger.info("-" * 40)
        logger.info("⛔ Node: reject", extra={"run_id": run_id, "agent": self.agent_name})
        logger.info("-" * 40)
        # final_output قبلاً در predict_node تنظیم شده
        return state

    def build_graph(self):
        """ساخت گراف LangGraph برای ImageAgent با conditional routing"""
        workflow = StateGraph(ImageAgentState)
        
        workflow.add_node("predict", self.predict_node)
        workflow.add_node("reject", self.reject_node)
        workflow.add_node("lookup", self.lookup_node)
        workflow.add_node("assess", self.assess_node)
        workflow.add_node("llm", self.llm_node)

        workflow.set_entry_point("predict")

        # روتینگ شرطی: اگر فیلتر شد → reject، در غیر این صورت → lookup
        def _route_after_predict(state: ImageAgentState):
            if state.get("filtered"):
                return "reject"
            return "lookup"

        workflow.add_conditional_edges(
            "predict",
            _route_after_predict,
            {
                "reject": "reject",
                "lookup": "lookup"
            }
        )
        
        workflow.add_edge("reject", END)
        workflow.add_edge("lookup", "assess")
        workflow.add_edge("assess", "llm")
        workflow.add_edge("llm", END)

        return workflow.compile()

    async def run(self, user_message: str, run_id: str, **kwargs):
        """Execute ImageAgent skin cancer screening pipeline."""
        start_time = time.time()
        user_profile = kwargs.get("user_profile") or {}
        
        # SAFE DEBUG LOGGING - Check what's being passed to ImageAgent
        logger.info("=" * 80)
        logger.info("IMAGE AGENT RUN DIAGNOSTICS")
        logger.info("=" * 80)
        logger.info(f"User message: '{user_message[:100]}'")
        logger.info(f"User profile keys: {list(user_profile.keys())}")
        logger.info(f"User profile size: {len(json.dumps(user_profile)):,} characters")
        logger.info(f"Has chat_history in kwargs: {'chat_history' in kwargs}")
        if 'chat_history' in kwargs:
            chat_history = kwargs['chat_history']
            logger.info(f"Chat history length: {len(chat_history)} messages")
            logger.info(f"Chat history size: {len(json.dumps(chat_history)):,} characters")
            # Log sample of chat history
            if chat_history:
                logger.info(f"Chat history sample: {json.dumps(chat_history[0])[:500]}")
        logger.info(f"Has image_base64: {bool(kwargs.get('image_base64'))}")
        if kwargs.get('image_base64'):
            logger.info(f"Image base64 size: {len(kwargs.get('image_base64')):,} characters")
        logger.info("=" * 80)
        
        # Try multiple possible user_id field names
        user_id = (user_profile.get("username") or 
                   user_profile.get("user_id") or 
                   user_profile.get("userId") or 
                   user_profile.get("id") or 
                   "guest")
        logger.info(f"ImageAgent.run - user_id: {user_id}")

        graph = self.build_graph()
        image_base64 = kwargs.get("image_base64")

        try:
            result = await graph.ainvoke({
                "user_message": user_message,
                "image_base64": image_base64,
                "predicted_class": "",
                "confidence": 0.0,
                "filtered": False,
                "disease_info": {},
                "risk_assessment": {},
                "abcde_analysis": {},
                "doctor_guidance": {},
                "final_output": "",
                "run_id": run_id,
                "user_profile": user_profile,
                "image_quality": {},
                "top3_predictions": [],  # 🆕 Initialize in state
                "all_scores": {},  # 🆕 Initialize in state
                "heatmap": {"available": False, "reason": "Not generated"},  # 🆕 Initialize heatmap in state
            })

            # DEBUG: Log final graph state before structured analysis
            logger.info(f"=== FINAL GRAPH STATE ===")
            logger.info(f"Graph result type: {type(result)}")
            if isinstance(result, dict):
                logger.info(f"Graph result keys: {list(result.keys())}")
                logger.info(f"Graph state all_scores count: {len(result.get('all_scores', {}))}")
                logger.info(f"Graph state top3_predictions count: {len(result.get('top3_predictions', []))}")
                logger.info(f"Graph state heatmap: {result.get('heatmap', 'NOT FOUND')}")

            # Prepare structured analysis data for history and API response
            analysis_timestamp = datetime.now().isoformat()
            
            # برای تصاویر فیلتر شده، analysis_data ساده‌سازی شده برگردان
            if result.get("filtered"):
                analysis_data = {
                    "timestamp": analysis_timestamp,
                    "user_id": user_id,
                    "input": {
                        "image": bool(image_base64),
                        "message": user_message,
                    },
                    "filtered": True,
                    "filter_reason": "Image detected as non-skin related",
                    "disclaimer": "This AI screening is for educational purposes only and is NOT a medical diagnosis.",
                }
            else:
                # Convert top3_predictions from 'confidence' to 'probability' for canonical format
                top3_raw = result.get("top3_predictions", [])
                top3_canonical = [
                    {
                        "class": pred.get("class"),
                        "probability": pred.get("confidence", 0.0)  # Convert confidence to probability
                    }
                    for pred in top3_raw
                ]
                
                analysis_data = {
                    "timestamp": analysis_timestamp,
                    "user_id": user_id,
                    "input": {
                        "image": bool(image_base64),
                        "message": user_message,
                    },
                    "user_message_language": detect_language(user_message),
                    "profile_context": {
                        "age": user_profile.get("age"),
                        "medical_history": user_profile.get("medical_history") or user_profile.get("previous_skin_conditions"),
                        "allergies": user_profile.get("allergies"),
                        "skin_type": user_profile.get("skin_type"),
                    },
                    "model": {
                        "name": "PanDerm",
                        "predicted_class": result.get("predicted_class"),
                        "confidence": result.get("confidence"),
                        "top3_predictions": top3_canonical,  # Use canonical format with 'probability'
                        "all_probabilities": result.get("all_scores", {}),  # All class probabilities from state
                    },
                    "visual_analysis": {
                        "available": False,
                        "findings": []
                    },
                    "abcde": {
                        "available": bool(result.get("abcde_analysis", {}).get("abcde_score", 0) > 0),
                        "score": result.get("abcde_analysis", {}).get("abcde_score", 0),
                        "criteria": result.get("abcde_analysis", {}).get("criteria", {}),
                    },
                    "risk_assessment": result.get("risk_assessment", {}),
                    "symptom_analysis": {
                        "symptoms": [user_message] if user_message else [],
                        "possible_conditions": []
                    },
                    "image_quality": result.get("image_quality", {}),
                    "recommendations": result.get("doctor_guidance", {}).get("visit_guidance", {}),
                    "explainability": result.get("heatmap", {"available": False, "reason": "Not generated"}),
                    "disclaimer": "This AI screening is for educational purposes only and is NOT a medical diagnosis.",
                }
            
            logger.info(f"🔥🔥🔥 explainability in analysis_data: {analysis_data.get('explainability', {})}")

            # DEBUG: Verify structured analysis data
            logger.info(f"=== STRUCTURED ANALYSIS DATA ===")
            logger.info(f"Structured analysis all_probabilities count: {len(analysis_data.get('model', {}).get('all_probabilities', {}))}")
            logger.info(f"Structured analysis top3_predictions count: {len(analysis_data.get('model', {}).get('top3_predictions', []))}")
            logger.info(f"🔥 Explainability data in analysis_data: {analysis_data.get('explainability', {})}")

            # Save analysis to history (if not filtered and user is authenticated)
            analysis_id = ""
            if not result.get("filtered") and user_id != "guest":
                try:
                    analysis_id = analysis_history_service.save_analysis(
                        user_id=user_id,
                        analysis_data=analysis_data,
                        image_base64=image_base64  # Note: storing base64, consider proper image storage in production
                    )
                    if analysis_id:
                        logger.info(f"Analysis saved to history: {analysis_id}")
                        analysis_data["analysis_id"] = analysis_id
                        
                        # Generate PDF report automatically
                        try:
                            # Detect language from user message to match user's intent
                            detected_language = analysis_data.get("user_message_language", "english")
                            logger.info(f"PDF language detected from user message: {detected_language}")
                            
                            report_result = pdf_report_service.generate_report(analysis_data, image_base64, language=detected_language)
                            if report_result.get("success"):
                                logger.info(f"PDF report generated: {report_result.get('report_path')}")
                                analysis_data["report"] = {
                                    "available": True,
                                    "report_id": analysis_id,
                                    "generated_at": report_result.get("generated_at"),
                                    "language": detected_language
                                }
                            else:
                                analysis_data["report"] = {"available": False}
                                logger.warning(f"PDF report generation failed: {report_result.get('error')}")
                        except Exception as report_error:
                            logger.warning(f"Failed to generate PDF report: {report_error}")
                            analysis_data["report"] = {"available": False}
                except Exception as save_error:
                    logger.warning(f"Failed to save analysis to history: {save_error}")
            else:
                logger.warning(f"Save skipped: filtered={result.get('filtered')}, user_id={user_id}")
            return {
                "final_output": result["final_output"],
                "filtered": result.get("filtered", False),
                "analysis": analysis_data,
            }
            
        except Exception as e:
            logger.error(f"❌ ImageAgent run failed: {e}", exc_info=True)
            
            return {
                "final_output": (
                    "I apologize, but I encountered an error while analyzing your image. "
                    "Please try again with a clear photo of the skin area you're concerned about."
                ),
                "filtered": False
            }


# Manual debug runner
if __name__ == "__main__":
    import asyncio
    from app.core.agent_context import AgentContext

    async def test():
        context = AgentContext()
        context.debug = True

        agent = ImageAgent(context)
        result = await agent.run(
            "Analyze this image",
            run_id="debug",
            image_base64="BASE64_STRING_HERE"
        )
        print(result["final_output"])

    asyncio.run(test())
