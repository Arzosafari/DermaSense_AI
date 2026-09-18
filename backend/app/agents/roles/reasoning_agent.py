# backend/app/agents/roles/reasoning_agent.py
import logging
import json
import time
import re
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
from app.agents.base.base_agent import BaseAgent
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class ReasoningState(TypedDict):
    user_message: str
    symptoms: list
    disease_matched: str
    disease_info: Dict[str, Any]
    final_output: str
    detected_language: str
    user_profile: Dict[str, Any]
    run_id: str
    chat_history: list


class ReasoningAgent(BaseAgent):
    agent_name = "reasoning_agent"

    def _detect_language(self, text: str) -> str:
        """تشخیص زبان متن کاربر"""
        if not text:
            return "en"
        
        persian_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
        persian_chars = len(persian_pattern.findall(text))
        
        english_pattern = re.compile(r'[a-zA-Z]')
        english_chars = len(english_pattern.findall(text))
        
        total_alpha = persian_chars + english_chars
        
        if total_alpha == 0:
            return "en"
        
        if persian_chars / total_alpha > 0.3:
            return "fa"
        
        return "en"

    def _clean_disease_info(self, disease_info: Dict[str, Any]) -> Dict[str, Any]:
        """پاکسازی disease_info از داده‌های غیرضروری"""
        if not disease_info or not isinstance(disease_info, dict):
            return {}
        
        keys_to_remove = [
            "error", "suggestion", "db_success", "status",
            "ner_entities", "llm_output", "run_id", "language"
        ]
        
        cleaned = {}
        
        for key, value in disease_info.items():
            if key in keys_to_remove:
                continue
            if value is None or value == "" or value == "N/A" or value == "None":
                continue
            if isinstance(value, str) and value.startswith("Error"):
                continue
            if isinstance(value, str) and len(value) > 500:
                value = value[:500] + "..."
            cleaned[key] = value
        
        return cleaned

    def _clean_response(self, text: str) -> str:
        """
        پاکسازی پاسخ نهایی از JSON خام، تکرارها، متن‌های متا،
        کلمات انگلیسی داخل پرانتز، و disclaimer زبان مخالف
        """
        if not text:
            return text
        
        # حذف کامل خطوط JSON
        text = re.sub(r'^\s*\{\s*"[^"]+"\s*:\s*\[?[^\]]*\]?\s*\}\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\[\s*"[^"]*"\s*\]\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', '', text, flags=re.DOTALL)
        text = re.sub(r'\{[^{}]*\}', '', text)
        
        # حذف کلمات انگلیسی داخل پرانتز: اگزما (Eczema) → اگزما
        text = re.sub(r'\s*\([A-Za-z][^)]*\)', '', text)
        
        # حذف header های لو رفته از prompt
        text = re.sub(r'^.*?CRITICAL LANGUAGE RULE:.*?\n', '', text, flags=re.DOTALL)
        text = re.sub(r'^.*?RESPONSE STRUCTURE.*?\n', '', text, flags=re.DOTALL)
        text = re.sub(r'^.*?DIFFERENTIAL DIAGNOSIS.*?\n', '', text, flags=re.DOTALL)
        text = re.sub(r'^.*?ABSOLUTE LANGUAGE RULE:.*?\n', '', text, flags=re.DOTALL)
        text = re.sub(r'^.*?Language code:.*?\n', '', text, flags=re.DOTALL)
        text = re.sub(r'^.*?If \{\{LANGUAGE\}\}.*?\n', '', text, flags=re.DOTALL)
        text = re.sub(r'^.*?Write 100%.*?\n', '', text, flags=re.DOTALL)
        
        lines = text.split('\n')
        cleaned_lines = []
        
        meta_prefixes = [
            '🚨',
            'اگر "en"',
            'اگر "fa"',
            'The detected language',
            'If LANGUAGE is',
            'If the user wrote in',
            'You MUST respond',
            '🚨 CRITICAL',
            'CRITICAL LANGUAGE',
            'User Message:',
            'Disease Information:',
            'Identified Symptoms:',
            'توضیح مختصر از آنچه کاربر',
            'بیماری پوستی احتمالی:',
            'Matched Disease:',
            'The user asked about',
            'Disease:',
            '🌐',
            'FORMAT YOUR RESPONSE',
            'IF LANGUAGE',
            'RESPONSE STRUCTURE',
            'IMPORTANT RULES',
            'CRITICAL RULES',
            'The user\'s language is:',
            'Language code:',
            'For {{LANGUAGE}}',
            'Write 100%',
            'If {{LANGUAGE}}',
            'RESPONSE FORMAT:',
            'ABSOLUTE LANGUAGE RULE:',
        ]
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                cleaned_lines.append(line)
                continue
            
            # حذف خطوط JSON
            if (stripped.startswith('{') and stripped.endswith('}')) or \
               (stripped.startswith('[') and stripped.endswith(']')):
                try:
                    json.loads(stripped)
                    continue
                except:
                    pass
            
            # حذف خطوط متا
            should_skip = False
            for prefix in meta_prefixes:
                if stripped.lower().startswith(prefix.lower()):
                    should_skip = True
                    break
            
            if should_skip:
                continue
            
            cleaned_lines.append(line)
        
        # حذف خطوط خالی متوالی
        result_lines = []
        prev_empty = False
        
        for line in cleaned_lines:
            if line.strip() == "":
                if not prev_empty:
                    result_lines.append(line)
                prev_empty = True
            else:
                result_lines.append(line)
                prev_empty = False
        
        result = '\n'.join(result_lines).strip()
        
        # پیدا کردن شروع پاسخ اصلی
        persian_start = result.find('**محتمل‌ترین')
        english_start = result.find('**Most Likely')
        
        start_idx = -1
        if persian_start >= 0 and english_start >= 0:
            start_idx = min(persian_start, english_start)
        elif persian_start >= 0:
            start_idx = persian_start
        elif english_start >= 0:
            start_idx = english_start
        
        if start_idx > 0:
            result = result[start_idx:]
        
        # حذف متن قبل از اولین **bold** اگر با محتمل‌ترین/Most Likely شروع نشده
        if not result.startswith('**محتمل‌ترین') and not result.startswith('**Most Likely'):
            first_bold = re.search(r'\*\*[^*]+\*\*', result)
            if first_bold and first_bold.start() > 0:
                result = result[first_bold.start():]
        
        # 🆕 تصحیح disclaimer بر اساس زبان پاسخ
        if result.startswith('**Most Likely'):
            # پاسخ انگلیسیه - حذف disclaimer فارسی
            result = re.sub(r'---\s*\n\s*⚠️\s*\*\*سلب مسئولیت پزشکی.*$', '', result, flags=re.DOTALL)
            result = re.sub(r'⚠️\s*\*\*سلب مسئولیت پزشکی.*$', '', result, flags=re.DOTALL)
            # اگر disclaimer انگلیسی وجود نداره، اضافه کن
            if '**Medical Disclaimer:**' not in result:
                result = result.rstrip() + '\n\n---\n⚠️ **Medical Disclaimer:** I am an AI assistant, not a doctor. This information is educational only. A dermatologist must examine your skin in person for accurate diagnosis.'
        
        elif result.startswith('**محتمل‌ترین'):
            # پاسخ فارسیه - حذف disclaimer انگلیسی
            result = re.sub(r'---\s*\n\s*⚠️\s*\*\*Medical Disclaimer.*$', '', result, flags=re.DOTALL)
            result = re.sub(r'⚠️\s*\*\*Medical Disclaimer.*$', '', result, flags=re.DOTALL)
            # اگر disclaimer فارسی وجود نداره، اضافه کن
            if '**سلب مسئولیت پزشکی:**' not in result:
                result = result.rstrip() + '\n\n---\n⚠️ **سلب مسئولیت پزشکی:** من یک دستیار هوش مصنوعی هستم، نه پزشک. این اطلاعات صرفاً آموزشی است. یک متخصص پوست باید پوست شما را شخصاً معاینه کند تا تشخیص دقیق ارائه دهد.'
        
        # حذف خطوط خالی اضافی در انتها
        result = result.rstrip() + '\n'
        
        return result

    def _build_personalization_context(self, user_profile: Dict[str, Any]) -> str:
        """ساخت متن شخصی‌سازی بر اساس پروفایل کاربر"""
        if not user_profile:
            return ""
        
        parts = []
        
        if user_profile.get("name"):
            parts.append(f"Patient Name: {user_profile['name']}")
        if user_profile.get("age"):
            parts.append(f"Age: {user_profile['age']}")
        if user_profile.get("gender"):
            parts.append(f"Gender: {user_profile['gender']}")
        if user_profile.get("skin_type"):
            parts.append(f"Skin Type: {user_profile['skin_type']}")
        if user_profile.get("allergies"):
            parts.append(f"Known Allergies: {user_profile['allergies']}")
        if user_profile.get("medical_conditions"):
            parts.append(f"Medical Conditions: {user_profile['medical_conditions']}")
        if user_profile.get("medications"):
            parts.append(f"Current Medications: {user_profile['medications']}")
        
        if not parts:
            return ""
        
        return "PATIENT PROFILE:\n" + "\n".join(parts) + "\n\n"

    async def llm_node(self, state: ReasoningState):
        run_id = state["run_id"]
        logger.info("Node: llm", extra={"run_id": run_id, "agent": self.agent_name})

        template = load_prompt("reasoning_prompt.txt")

        user_message = state.get("user_message", "")
        symptoms = state.get("symptoms", [])
        disease_matched = state.get("disease_matched", "unknown")
        disease_info = self._clean_disease_info(state.get("disease_info", {}))
        user_profile = state.get("user_profile", {})
        chat_history = state.get("chat_history", [])

        detected_language = state.get("detected_language", "")
        if not detected_language or detected_language == "unknown":
            detected_language = self._detect_language(user_message)
        
        logger.info(f"🌐 Detected language: {detected_language}")
        logger.info(f"👤 User profile available: {bool(user_profile)}")
        logger.info(f"📜 Chat history available: {len(chat_history)} messages")

        if not disease_info:
            disease_info = {"note": "No detailed information available in database"}

        personalization = self._build_personalization_context(user_profile)
        
        # Extract analysis context from chat history
        analysis_context = ""
        for m in chat_history:
            if m.get('analysis_data'):
                analysis = m['analysis_data']
                if isinstance(analysis, dict):
                    predicted_class = "Unknown"
                    confidence = 0
                    screening_level = "Unknown"
                    
                    if analysis.get('model', {}).get('predicted_class'):
                        predicted_class = analysis['model']['predicted_class']
                        confidence = analysis['model'].get('confidence', 0)
                        screening_level = analysis.get('risk_assessment', {}).get('screening_level', 'Unknown')
                    elif analysis.get('predicted_class'):
                        predicted_class = analysis['predicted_class']
                        confidence = analysis.get('confidence', 0)
                        screening_level = analysis.get('screening_level', 'Unknown')
                    
                    if predicted_class != "Unknown":
                        analysis_context += f"\n- Previous analysis: {predicted_class} ({confidence:.0%} confidence, {screening_level} risk)"
                        logger.info(f"🔍 Found analysis in reasoning_agent: {predicted_class}")
                        break
        
        if analysis_context:
            analysis_context = "\nPREVIOUS SKIN ANALYSES:" + analysis_context
            logger.info(f"🔍 Added analysis context to reasoning prompt")

        prompt = (
            template.replace("{{USER_MESSAGE}}", user_message)
            .replace("{{SYMPTOMS}}", json.dumps(symptoms, ensure_ascii=False))
            .replace("{{DISEASE}}", disease_matched)
            .replace("{{DISEASE_INFO}}", json.dumps(disease_info, ensure_ascii=False, indent=2))
            .replace("{{LANGUAGE}}", detected_language)
            .replace("{{PERSONALIZATION}}", personalization)
            .replace("{{ANALYSIS_CONTEXT}}", analysis_context)
        )

        logger.debug(f"Prompt length: {len(prompt)} chars")

        raw = await self.llm_call(
            prompt, 
            run_id=run_id,
            max_tokens=3000,
            temperature=0.7
        )

        # پاکسازی چند مرحله‌ای
        final_output = self._clean_response(raw)
        
        if not final_output or len(final_output) < 20:
            logger.warning("Response was empty after cleaning, using raw response")
            final_output = raw.strip()
            final_output = re.sub(r'\{[^{}]*\}', '', final_output)
            final_output = re.sub(r'\[[^\]]*\]', '', final_output)
            final_output = final_output.strip()
            final_output = self._clean_response(final_output)
        
        # حذف خط اول اگر برابر با user_message است
        lines = final_output.split('\n')
        if lines and lines[0].strip() == user_message.strip():
            final_output = '\n'.join(lines[1:]).strip()

        # بررسی زبان پاسخ
        persian_chars = sum(1 for c in final_output if '\u0600' <= c <= '\u06FF')
        total_chars = len(final_output.replace(' ', ''))
        
        if total_chars > 0:
            persian_ratio = persian_chars / total_chars
            
            if detected_language == "en" and persian_ratio > 0.3:
                logger.warning(f"⚠️ Response has Persian but user wrote in English! Ratio: {persian_ratio:.2%}")
            elif detected_language == "fa" and persian_ratio < 0.1:
                logger.warning(f"⚠️ Response has English but user wrote in Persian! Ratio: {persian_ratio:.2%}")
            else:
                logger.info(f"✅ Language OK. Persian ratio: {persian_ratio:.2%}")

        logger.info(f"Final output length: {len(final_output)} chars")
        logger.info(f"Output preview: {final_output[:150]}...")
        
        state["final_output"] = final_output
        state["detected_language"] = detected_language
        return state

    def build_graph(self):
        workflow = StateGraph(ReasoningState)
        workflow.add_node("llm", self.llm_node)
        workflow.set_entry_point("llm")
        workflow.add_edge("llm", END)
        return workflow.compile()

    async def run(self, user_message: str, run_id: str, **kwargs):
        start_time = time.time()
        logger.info("=" * 50)
        logger.info("Agent run started", extra={"run_id": run_id, "agent": self.agent_name})
        
        detected_language = kwargs.get("language", "")
        if not detected_language or detected_language == "unknown":
            detected_language = self._detect_language(user_message)
        
        user_profile = kwargs.get("user_profile", {})
        chat_history = kwargs.get("chat_history", [])
        
        logger.info(f"🌐 Language: {detected_language}")
        logger.info(f"👤 Profile: {bool(user_profile)}")
        logger.info(f"📜 Chat history: {len(chat_history)} messages")

        graph = self.build_graph()
        disease_info = self._clean_disease_info(kwargs.get("info", {}))

        try:
            result = await graph.ainvoke(
                {
                    "user_message": user_message,
                    "symptoms": kwargs.get("symptoms", []),
                    "disease_matched": kwargs.get("disease_matched", "unknown"),
                    "disease_info": disease_info,
                    "final_output": "",
                    "detected_language": detected_language,
                    "user_profile": user_profile,
                    "run_id": run_id,
                    "chat_history": chat_history,
                }
            )

            end_time = time.time()
            latency = end_time - start_time
            
            final_output = result.get("final_output", "")
            final_output = self._clean_response(final_output)
            
            logger.info("Agent run finished", extra={
                "run_id": run_id, 
                "agent": self.agent_name, 
                "latency": f"{latency:.2f}s",
                "output_length": len(final_output),
                "language": detected_language
            })

            return {"final_output": final_output}
            
        except Exception as e:
            logger.error(f"Agent run failed: {e}", exc_info=True)
            
            if detected_language == "fa":
                fallback = "متأسفانه در پردازش درخواست شما خطایی رخ داد. لطفاً دوباره تلاش کنید."
            else:
                fallback = "I apologize, but I encountered an error while processing your request. Please try again."
            
            return {"final_output": fallback}


# Manual debug runner
if __name__ == "__main__":
    import asyncio
    from app.core.agent_context import AgentContext

    async def test():
        context = AgentContext()
        context.debug = True

        agent = ReasoningAgent(context)
        
        # تست فارسی
        print("\n" + "=" * 60)
        print("TEST: Persian query with profile")
        print("=" * 60)
        result = await agent.run(
            user_message="من لکه‌های قرمز خارش‌دار روی صورتم دارم",
            run_id="debug-fa",
            symptoms=["قرمزی", "خارش", "پوسته‌پوسته"],
            disease_matched="impetigo",
            info={
                "disease": "impetigo",
                "description": "A highly contagious bacterial skin infection",
                "symptoms": "Red sores, blisters, honey-colored crusts",
                "treatment": "Topical or oral antibiotics"
            },
            user_profile={
                "name": "علی",
                "age": 30,
                "skin_type": "sensitive",
                "allergies": "گرده گل"
            }
        )
        print(result["final_output"][:500])

    asyncio.run(test())