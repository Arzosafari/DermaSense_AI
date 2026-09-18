import logging
from typing import Optional

from app.llm.adapters.groq_adapter import GroqLLM, GroqUnavailableError
from app.llm.adapters.lmstudio_adapter import LMStudioLLM
from app.llm.base.base_llm import BaseLLM
from app.config import settings

logger = logging.getLogger(__name__)


class FallbackLLM(BaseLLM):
    """Try Groq first; on failure fall back to local Gemma via LM Studio."""

    def __init__(self, primary_model: str, fallback_model: Optional[str] = None):
        self.primary = GroqLLM(primary_model)
        self.fallback = LMStudioLLM(
            fallback_model or settings.LM_STUDIO_MODEL,
            host=settings.LM_STUDIO_HOST,
        )
        self.last_provider = "unknown"

    async def generate(self, prompt: str, **kwargs) -> str:
        logger.info("=" * 80)
        logger.info("FALLBACK LLM DIAGNOSTICS")
        logger.info("=" * 80)
        logger.info(f"Attempting primary provider: Groq")
        logger.info(f"Prompt length: {len(prompt):,} characters")
        logger.info("=" * 80)
        
        try:
            result = await self.primary.generate(prompt, **kwargs)
            self.last_provider = "groq"
            logger.info(f"✅ Primary provider (Groq) succeeded")
            return result
        except GroqUnavailableError as exc:
            logger.warning(f"❌ Groq unavailable ({exc}). Falling back to LM Studio Gemma.")
            logger.info(f"Groq error type: {type(exc).__name__}")
            logger.info(f"Groq error message: {str(exc)}")
            
            # Classify Groq errors to determine if fallback is appropriate
            is_payload_error = "413" in str(exc) or "payload too large" in str(exc).lower()
            is_auth_error = "401" in str(exc) or "403" in str(exc) or "auth" in str(exc).lower()
            is_rate_limit = "429" in str(exc) or "rate limit" in str(exc).lower()
            is_server_error = any(code in str(exc) for code in ["500", "502", "503", "504"])
            
            # Detect language from prompt for appropriate error messages
            is_persian_prompt = any(char in prompt for char in "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنهو") or "فارسی" in prompt or "persian" in prompt.lower()
            
            if is_payload_error:
                logger.error("🚨 ERROR 413 DETECTED - Payload too large for Groq")
                logger.error("🚨 Fallback to LM Studio will likely also fail with same large payload")
                logger.error("🚨 The root cause must be fixed in prompt construction, not fallback logic")
                # DO NOT fallback to LM Studio with same payload - this is guaranteed to fail
                # Instead, return a specific error message explaining the payload issue
                if is_persian_prompt:
                    fallback_msg = "متأسفانه، حجم درخواست برای سرویس هوش مصنوعی بیش از حد مجاز است. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد، اما توضیحات متنی به دلیل محدودیت سرویس تولید نشد. لطفاً دوباره تلاش کنید."
                else:
                    fallback_msg = "I apologize, but the request payload is too large for the AI text service. The image analysis and prediction were completed successfully, but the detailed explanation could not be generated. Please try again with a simpler request."
                logger.info(f"Returning payload error fallback message (not retrying with LM Studio)")
                return fallback_msg
            elif is_rate_limit:
                logger.warning("⚠️ RATE LIMIT - Groq rate limited")
                # For rate limit, also don't fall back to LM Studio if it has no model
                # Instead return a clear rate limit message in the appropriate language
                if is_persian_prompt:
                    fallback_msg = "متأسفانه، سرویس هوش مصنوعی به دلیل محدودیت نرخ درخواست در دسترس نیست. لطفاً چند دقیقه دیگر دوباره تلاش کنید. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد."
                else:
                    fallback_msg = "I apologize, but the AI text service is currently rate-limited. Please try again in a few minutes. The image analysis and prediction were completed successfully."
                logger.info(f"Returning rate limit fallback message (not retrying with LM Studio)")
                return fallback_msg
            elif is_auth_error:
                logger.error("🚨 AUTH ERROR - Groq authentication failed")
                logger.error("🚨 Fallback to LM Studio (no auth required)")
            elif is_server_error:
                logger.warning("⚠️ SERVER ERROR - Groq server error, fallback to LM Studio")
            
            try:
                logger.info(f"Attempting fallback provider: LM Studio")
                result = await self.fallback.generate(prompt, **kwargs)
                self.last_provider = "gemma_local"
                logger.info(f"✅ Fallback provider (LM Studio) succeeded")
                return result
            except Exception as fallback_exc:
                logger.error(f"❌ Both Groq and LM Studio failed")
                logger.error(f"Groq error: {exc}")
                logger.error(f"LM Studio error: {fallback_exc}")
                logger.error(f"LM Studio error type: {type(fallback_exc).__name__}")
                
                # Classify LM Studio errors for better user messaging
                is_lm_400 = "400" in str(fallback_exc)
                is_lm_no_model = "no models loaded" in str(fallback_exc).lower()
                is_lm_connect = "connect" in str(fallback_exc).lower()
                is_lm_timeout = "timeout" in str(fallback_exc).lower()
                
                # Extract context from prompt for better fallback response
                if "Previous skin analyses:" in prompt:
                    context_part = prompt[prompt.find("Previous skin analyses:"):prompt.find("Previous skin analyses:")+500]
                    logger.info(f"Found analysis context in prompt, using context-aware fallback")
                    
                    if is_payload_error or is_lm_400:
                        if is_persian_prompt:
                            fallback_msg = f"متأسفانه، سرویس هوش مصنوعی با خطا مواجه شد. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد. بر اساس تحلیل قبلی، لطفاً به پایش پوست خود ادامه دهید و در صورت نیاز به متخصص پوست مراجعه کنید. {context_part}"
                        else:
                            fallback_msg = f"I apologize, but the AI text service encountered a payload size error. The image analysis and prediction were completed successfully, but the detailed explanation could not be generated. Based on your previous analysis, please continue monitoring your skin and consult a dermatologist as recommended. {context_part}"
                    elif is_lm_no_model:
                        if is_persian_prompt:
                            fallback_msg = "متأسفانه، سرویس هوش مصنوعی محلی (LM Studio) در حال اجراست اما هیچ مدلی لود نشده است. لطفاً مدلی را در LM Studio لود کنید. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد."
                        else:
                            fallback_msg = "I apologize, but the local AI service (LM Studio) is running but no model is loaded. Please load a model in LM Studio. The image analysis and prediction were completed successfully."
                    elif is_lm_connect:
                        if is_persian_prompt:
                            fallback_msg = "متأسفانه، سرویس هوش مصنوعی محلی (LM Studio) در حال اجرا نیست. لطفاً LM Studio را راه‌اندازی کنید و دوباره تلاش کنید. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد."
                        else:
                            fallback_msg = "I apologize, but the local AI service (LM Studio) is not running. Please start LM Studio and try again. The image analysis and prediction were completed successfully."
                    elif is_lm_timeout:
                        if is_persian_prompt:
                            fallback_msg = "متأسفانه، سرویس هوش مصنوعی زمان‌بر شد. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد، اما توضیحات متنی طول کشید. لطفاً دوباره تلاش کنید."
                        else:
                            fallback_msg = "I apologize, but the AI service timed out. The image analysis and prediction were completed successfully, but the detailed explanation took too long to generate. Please try again."
                    else:
                        if is_persian_prompt:
                            fallback_msg = f"متأسفانه، سرویس تولید متن هوش مصنوعی در دسترس نیست. بر اساس تحلیل قبلی، لطفاً به پایش پوست خود ادامه دهید و در صورت نیاز به متخصص پوست مراجعه کنید. {context_part}"
                        else:
                            fallback_msg = f"I apologize, but the AI text generation service is currently unavailable. Based on your previous analysis, please continue monitoring your skin and consult a dermatologist as recommended. {context_part}"
                else:
                    if is_payload_error or is_lm_400:
                        if is_persian_prompt:
                            fallback_msg = "متأسفانه، سرویس هوش مصنوعی با خطای حجم درخواست مواجه شد. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد، اما توضیحات متنی تولید نشد. لطفاً با درخواست ساده‌تر دوباره تلاش کنید."
                        else:
                            fallback_msg = "I apologize, but the AI text service encountered a payload size error. The image analysis and prediction were completed successfully, but the detailed explanation could not be generated. Please try again with a simpler request."
                    elif is_lm_no_model:
                        if is_persian_prompt:
                            fallback_msg = "متأسفانه، سرویس هوش مصنوعی محلی (LM Studio) در حال اجراست اما هیچ مدلی لود نشده است. لطفاً مدلی را در LM Studio لود کنید. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد."
                        else:
                            fallback_msg = "I apologize, but the local AI service (LM Studio) is running but no model is loaded. Please load a model in LM Studio. The image analysis and prediction were completed successfully."
                    elif is_lm_connect:
                        if is_persian_prompt:
                            fallback_msg = "متأسفانه، سرویس هوش مصنوعی محلی (LM Studio) در حال اجرا نیست. لطفاً LM Studio را راه‌اندازی کنید و دوباره تلاش کنید. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد."
                        else:
                            fallback_msg = "I apologize, but the local AI service (LM Studio) is not running. Please start LM Studio and try again. The image analysis and prediction were completed successfully."
                    elif is_lm_timeout:
                        if is_persian_prompt:
                            fallback_msg = "متأسفانه، سرویس هوش مصنوعی زمان‌بر شد. تحلیل تصویر و پیش‌بینی با موفقیت انجام شد، اما توضیحات متنی طول کشید. لطفاً دوباره تلاش کنید."
                        else:
                            fallback_msg = "I apologize, but the AI service timed out. The image analysis and prediction were completed successfully, but the detailed explanation took too long to generate. Please try again."
                    else:
                        if is_persian_prompt:
                            fallback_msg = "متأسفانه، سرویس تولید متن هوش مصنوعی در دسترس نیست. تحلیل تصویر و نقشه حرارتی با موفقیت انجام شد. لطفاً چند دقیقه دیگر دوباره تلاش کنید."
                        else:
                            fallback_msg = "I apologize, but the AI text generation service is currently unavailable. The image analysis and heatmap have been completed successfully. Please try again in a few minutes."
                
                logger.info(f"Returning fallback message, length: {len(fallback_msg)}")
                return fallback_msg
