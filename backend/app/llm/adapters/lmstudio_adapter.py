# app/llm/adapters/lmstudio_adapter.py
import httpx
import json
import logging
import re
import time
from app.llm.base.base_llm import BaseLLM

logger = logging.getLogger(__name__)


class LMStudioLLM(BaseLLM):
    """
    آداپتر اتصال به LM Studio برای استفاده از مدل Gemma
    بهبود یافته با:
    - پشتیبانی از max_tokens بالاتر
    - timeout طولانی‌تر
    - تشخیص خودکار نیاز به JSON
    - retry logic ساده
    """

    def __init__(self, model: str, host: str = None):
        from app.config import settings
        self.model = model
        self.host = host or settings.LM_STUDIO_HOST
        self.max_retries = 2  # تعداد تلاش‌های مجدد
        logger.info(f"LM Studio adapter initialized | host={self.host} | model={self.model}")
        logger.info(f"⚠️ IMPORTANT: Ensure this model name matches exactly what's loaded in LM Studio")

    def _extract_json(self, text: str) -> str:
        """استخراج JSON از پاسخ مدل"""
        if not text:
            return text
        
        # حذف markdown code blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # پیدا کردن اولین { و آخرین }
        start = text.find('{')
        end = text.rfind('}')
        
        if start != -1 and end != -1 and start < end:
            return text[start:end+1]
        return text

    def _needs_json_output(self, prompt: str) -> bool:
        """تشخیص اینکه آیا پرامپت نیاز به خروجی JSON دارد"""
        json_indicators = [
            "json", "JSON", 
            "intent", "agents",  # Decider prompt
            "symptoms", "disease",  # Symptom/Disease prompts
            "parse",  # Parse nodes
        ]
        return any(indicator in prompt.lower() for indicator in json_indicators)

    async def generate(self, prompt: str, **kwargs):
        """
        Generate response from LM Studio with improved error handling.
        """
        # SAFE DEBUG LOGGING - Never log secrets
        logger.info("=" * 80)
        logger.info("LM STUDIO REQUEST DIAGNOSTICS")
        logger.info("=" * 80)
        logger.info(f"Provider: LM Studio")
        logger.info(f"Model: {self.model}")
        logger.info(f"Host: {self.host}")
        logger.info(f"Messages: 1")
        logger.info(f"Message role: user")
        logger.info(f"Prompt character count: {len(prompt):,}")
        logger.info(f"Estimated payload size: ~{len(prompt) + 500} bytes (JSON overhead)")
        
        # Check for image/base64 in prompt
        has_base64 = "base64" in prompt.lower()
        logger.info(f"Image/base64 included: {has_base64}")
        
        # Estimate component sizes
        logger.info(f"System prompt chars: ~{len('You are a specialized AI skin cancer screening assistant')}")
        logger.info(f"Conversation history chars: 0 (single-turn request)")
        logger.info(f"Analysis context chars: {len(prompt)}")
        
        # Log warning if payload is suspiciously large
        if len(prompt) > 10000:
            logger.warning(f"⚠️ SUSPICIOUSLY LARGE PROMPT: {len(prompt):,} characters")
            logger.warning(f"⚠️ This may cause 400 Bad Request error")
        
        logger.info("=" * 80)
        
        # Check if LM Studio is running and has a model loaded
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0)) as client:
                # Try to get available models
                models_response = await client.get(f"{self.host}/v1/models")
                if models_response.status_code == 200:
                    models_data = models_response.json()
                    available_models = models_data.get("data", [])
                    logger.info(f"LM Studio available models: {len(available_models)}")
                    if available_models:
                        for model in available_models:
                            model_id = model.get('id', 'unknown')
                            logger.info(f"  - {model_id}")
                            # Check if our configured model is available
                            if model_id == self.model:
                                logger.info(f"✅ Configured model '{self.model}' is loaded")
                            else:
                                logger.warning(f"⚠️ Available model '{model_id}' does not match configured '{self.model}'")
                    else:
                        logger.error("🚨 LM Studio is running but NO MODELS are loaded!")
                        return "System error: LM Studio is running but no model is loaded. Please load a model in LM Studio and try again."
                else:
                    logger.warning(f"Could not check LM Studio models (status: {models_response.status_code})")
        except Exception as check_error:
            logger.warning(f"LM Studio model check failed: {check_error}")
            logger.warning("Proceeding with request anyway...")

        # Truncate prompt if too long to avoid 400 errors
        max_prompt_length = 6000  # More aggressive limit to ensure 400 doesn't occur
        if len(prompt) > max_prompt_length:
            original_length = len(prompt)
            prompt = prompt[:max_prompt_length] + "... [truncated]"
            logger.warning(f"⚠️ Prompt truncated from {original_length:,} to {max_prompt_length:,} characters to avoid payload errors")

        # تعیین max_tokens بر اساس نوع درخواست
        if kwargs.get("max_tokens"):
            max_tokens = kwargs["max_tokens"]
        elif self._needs_json_output(prompt):
            max_tokens = 500  # برای پاسخ‌های JSON کوتاه‌تر کافی است
        else:
            max_tokens = 1500  # برای پاسخ‌های بلند مثل ImageAgent، Conversation
        
        # تعیین temperature
        temperature = kwargs.get("temperature", 0.7)  # پیش‌فرض بالاتر برای خلاقیت بیشتر
        
        # اگر نیاز به JSON دقیق باشد، temperature پایین‌تر
        if self._needs_json_output(prompt):
            temperature = min(temperature, 0.2)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        # Only add stop tokens if provided and not empty
        stop_tokens = kwargs.get("stop", [])
        if stop_tokens:
            payload["stop"] = stop_tokens
        
        logger.debug(f"LM Studio request | max_tokens={max_tokens} | temperature={temperature} | prompt_len={len(prompt)}")

        last_error = None
        
        # Retry logic
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"🕒 Starting LM Studio request {attempt + 1}/{self.max_retries + 1} with timeout: connect=10.0s, read=180.0s")
                start_time = time.time()
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=10.0,    # timeout برای اتصال
                        read=180.0,      # timeout برای خواندن پاسخ (3 دقیقه)
                        write=10.0,      # timeout برای نوشتن
                        pool=10.0        # timeout برای pool
                    )
                ) as client:
                    response = await client.post(
                        f"{self.host}/v1/chat/completions",
                        json=payload
                    )
                    elapsed_time = time.time() - start_time
                    logger.info(f"LM Studio request {attempt + 1} completed in {elapsed_time:.2f} seconds")
                    response.raise_for_status()
                    result = response.json()
                    
                    # بررسی وجود choices در پاسخ
                    if "choices" not in result or len(result["choices"]) == 0:
                        logger.warning(f"Empty response from LM Studio on attempt {attempt + 1}")
                        if attempt < self.max_retries:
                            continue
                        return "I'm sorry, I received an empty response. Please try again."
                    
                    content = result["choices"][0]["message"]["content"].strip()
                    
                    # بررسی خالی نبودن محتوا
                    if not content:
                        logger.warning(f"Empty content on attempt {attempt + 1}")
                        if attempt < self.max_retries:
                            continue
                        return "I'm sorry, I couldn't generate a response. Please try again."
                    
                    logger.debug(f"LM Studio response received (length: {len(content)})")
                    
                    # اگر پرامپت نیاز به JSON دارد، آن را استخراج کن
                    if self._needs_json_output(prompt):
                        content = self._extract_json(content)
                        logger.debug(f"JSON extracted (length: {len(content)})")
                    
                    return content
                    
            except httpx.ConnectError:
                error_msg = (
                    "Cannot connect to LM Studio. "
                    "Please make sure:\n"
                    "1. LM Studio is running\n"
                    "2. The server is started (check the 'Local Server' tab)\n"
                    "3. The port is correct (default: 1234)\n"
                    "4. A model is loaded"
                )
                logger.error(error_msg)
                return "System error: LM Studio is not running. Please start the server and try again."
                
            except httpx.TimeoutException as e:
                logger.warning(f"LM Studio timeout on attempt {attempt + 1}: {str(e)}")
                last_error = e
                if attempt < self.max_retries:
                    logger.info(f"Retrying... (attempt {attempt + 2}/{self.max_retries + 1})")
                    # افزایش max_tokens در تلاش بعدی؟ نه، مشکل wo چیز دیگه‌ست
                    continue
                else:
                    logger.error("All retry attempts failed due to timeout")
                    return "The response took too long. Please try again with a shorter question."
                
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP {e.response.status_code}"
                if e.response.status_code == 400:
                    try:
                        error_body = e.response.text
                        logger.error(f"LM Studio 400 error details: {error_body[:1000]}")
                        logger.error(f"LM Studio 400 full error body: {error_body}")
                        
                        # Check if it's a "no models loaded" error - DO NOT RETRY
                        if "no models loaded" in error_body.lower() or "please load a model" in error_body.lower():
                            logger.error("🚨 FATAL: LM Studio has no models loaded - DO NOT RETRY")
                            return "System error: LM Studio is running but no model is loaded. Please load a model in LM Studio and try again."
                        
                        # Check if it's a payload size issue
                        if "payload" in error_body.lower() or "size" in error_body.lower():
                            error_msg = "Request payload too large - try with a smaller image or shorter text"
                        # Check if it's a model issue
                        if "model" in error_body.lower():
                            error_msg = f"Model error - the model '{self.model}' may not be loaded or supported"
                        # Check if it's a parameter issue
                        if "parameter" in error_body.lower() or "invalid" in error_body.lower():
                            error_msg = "Invalid request parameter - check request format"
                    except Exception as parse_error:
                        logger.error(f"Failed to parse LM Studio 400 error body: {parse_error}")
                logger.error(f"LM Studio API error on attempt {attempt + 1}: {error_msg}")
                logger.error(f"LM Studio request payload: model={self.model}, prompt_len={len(prompt)}, max_tokens={max_tokens}")
                last_error = e
                
                # DO NOT retry if it's a "no models loaded" error
                if e.response.status_code == 400 and "no models loaded" in str(e.response.text).lower():
                    logger.error("🚨 Not retrying 'no models loaded' error")
                    return "System error: LM Studio is running but no model is loaded. Please load a model in LM Studio and try again."
                
                if attempt < self.max_retries:
                    logger.info(f"Retrying... (attempt {attempt + 2}/{self.max_retries + 1})")
                    continue
                else:
                    return f"I encountered an error processing your request ({error_msg}). Please try again."
                
            except Exception as e:
                logger.error(f"LM Studio API error on attempt {attempt + 1}: {str(e)}")
                last_error = e
                if attempt < self.max_retries:
                    logger.info(f"Retrying... (attempt {attempt + 2}/{self.max_retries + 1})")
                    continue
                else:
                    return f"I encountered an error while processing your request. Please try again."
        
        # Should not reach here, but just in case
        return f"Failed after {self.max_retries + 1} attempts. Last error: {str(last_error)}"