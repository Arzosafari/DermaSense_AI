import logging
from typing import Optional
import time
import asyncio

import httpx

from app.config import settings
from app.llm.base.base_llm import BaseLLM

logger = logging.getLogger(__name__)


class GroqUnavailableError(Exception):
    """Raised when Groq API is unreachable or returns a retryable error."""


class GroqLLM(BaseLLM):
    """Groq cloud LLM adapter (OpenAI-compatible chat completions API)."""

    def __init__(self, model: str = "groq/compound"):
        self.model = model or "groq/compound"
        self.api_key = settings.GROQ_API_KEY
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        
        # Debug logging (without exposing API key)
        logger.info(f"Groq adapter initialized - Model: {self.model}")
        logger.info(f"Groq API key present: {bool(self.api_key)}")
        logger.info(f"Groq API URL: {self.api_url}")

    async def generate(self, prompt: str, **kwargs) -> str:
        if not self.api_key:
            raise GroqUnavailableError("GROQ_API_KEY is not configured")

        # MANDATORY GROQ DIAGNOSTICS - Never log secrets
        logger.info("=" * 80)
        logger.info("GROQ REQUEST DIAGNOSTICS")
        logger.info("=" * 80)
        logger.info(f"Provider: Groq")
        logger.info(f"Model: {self.model}")
        logger.info(f"Number of messages: 1")
        logger.info(f"Message role: user")
        
        # Detailed payload analysis
        prompt_length = len(prompt)
        logger.info(f"User prompt length: {prompt_length:,} characters")
        
        # Check for image/base64 in prompt
        has_base64 = "base64" in prompt.lower()
        logger.info(f"Image included in prompt: {has_base64}")
        
        if has_base64:
            # Count base64 occurrences and estimate size
            base64_count = prompt.lower().count("base64")
            logger.info(f"Base64 occurrences in prompt: {base64_count}")
            
            # Estimate base64 size (rough approximation)
            if "data:image" in prompt:
                # Find all data:image segments
                import re
                data_urls = re.findall(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', prompt)
                logger.info(f"Data URL count: {len(data_urls)}")
                for i, url in enumerate(data_urls):
                    # Extract the base64 part
                    if ',' in url:
                        b64_part = url.split(',')[1]
                        logger.info(f"Data URL {i+1} base64 size: {len(b64_part):,} characters")
        
        # Check for common large patterns
        if "analysis_data" in prompt:
            logger.info(f"Analysis data present in prompt: YES")
            # Count JSON-like structures
            json_count = prompt.count('{')
            logger.info(f"JSON object count (approx): {json_count}")
        
        if "visual_analysis" in prompt:
            logger.info(f"Visual analysis present in prompt: YES")
        
        if "report" in prompt:
            logger.info(f"Report present in prompt: YES")
        
        if "conversation history" in prompt.lower() or "previous" in prompt.lower():
            logger.info(f"Conversation history present in prompt: YES")
        
        # Estimate total payload size
        estimated_json_size = len(prompt) + 500  # Base JSON overhead
        logger.info(f"Estimated JSON payload size: ~{estimated_json_size:,} bytes")
        
        # Log warning if payload is suspiciously large
        if prompt_length > 10000:
            logger.warning(f"⚠️ SUSPICIOUSLY LARGE PROMPT: {prompt_length:,} characters")
            logger.warning(f"⚠️ This will likely cause 413 Payload Too Large error")
        elif prompt_length > 6000:
            logger.warning(f"⚠️ Large prompt: {prompt_length:,} characters (approaching limits)")
        
        logger.info("=" * 80)

        # Log max_tokens for credit optimization
        max_tokens = kwargs.get("max_tokens", 1500)
        logger.info(f"Max output tokens: {max_tokens}")
        logger.info(f"Image attached to Groq: NO (PanDerm already processed image)")
        logger.info("=" * 80)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.4),
            "max_tokens": kwargs.get("max_tokens", 1500),
            "stream": False,
        }

        try:
            logger.info(f"🕒 Starting Groq request with timeout: connect=10.0s, read=120.0s")
            start_time = time.time()
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                elapsed_time = time.time() - start_time
                logger.info(f"Groq API response status: {response.status_code}")
                logger.info(f"Groq API endpoint: {self.api_url}")
                logger.info(f"Groq model used: {self.model}")
                logger.info(f"Groq request completed in {elapsed_time:.2f} seconds")
                
                if response.status_code == 404:
                    try:
                        error_body = response.text
                        logger.error(f"Groq 404 response body: {error_body[:500]}")
                    except:
                        logger.error("Groq 404 - could not read response body")
                
                if response.status_code in {401, 403}:
                    raise GroqUnavailableError(f"Groq auth failed: {response.status_code}")
                if response.status_code == 429:
                    # Rate limit - implement retry with exponential backoff instead of immediate fallback
                    import asyncio
                    logger.warning("Groq rate limited (429) - implementing retry with backoff")
                    max_retries = 3
                    for retry in range(max_retries):
                        backoff_time = 2 ** retry  # Exponential backoff: 2s, 4s, 8s
                        logger.info(f"Retry {retry + 1}/{max_retries} after {backoff_time}s backoff")
                        await asyncio.sleep(backoff_time)
                        
                        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)) as client:
                            response = await client.post(self.api_url, headers=headers, json=payload)
                            if response.status_code == 429:
                                continue  # Try again with longer backoff
                            elif response.status_code == 200:
                                logger.info(f"✅ Groq retry succeeded on attempt {retry + 1}")
                                result = response.json()
                                choices = result.get("choices") or []
                                if not choices:
                                    raise GroqUnavailableError("Groq returned an empty response")
                                content = (choices[0].get("message") or {}).get("content", "").strip()
                                if not content:
                                    raise GroqUnavailableError("Groq returned empty content")
                                return content
                            else:
                                # Other error, raise normally
                                break
                    
                    # If all retries failed, fall back to LM Studio
                    logger.error(f"All {max_retries} Groq retries failed due to rate limiting")
                    raise GroqUnavailableError(f"Groq rate limited (429) after {max_retries} retries with backoff.")
                if response.status_code == 413:
                    # Log details for debugging
                    logger.error(f"🚨 Groq 413 Payload Too Large")
                    logger.error(f"🚨 Prompt length: {len(prompt):,} characters")
                    logger.error(f"🚨 Estimated payload: {len(prompt) + 500:,} bytes")
                    logger.error(f"🚨 Model: {self.model}")
                    logger.error(f"🚨 Max tokens: {max_tokens}")
                    raise GroqUnavailableError(f"Groq payload too large (413). Prompt: {len(prompt):,} chars. Root cause must be fixed in prompt construction.")
                if response.status_code in {500, 502, 503, 504}:
                    raise GroqUnavailableError(f"Groq unavailable: {response.status_code}")
                response.raise_for_status()
                result = response.json()
        except httpx.TimeoutException as exc:
            logger.error(f"Groq request timed out: {exc}")
            raise GroqUnavailableError("Groq request timed out") from exc
        except httpx.RequestError as exc:
            logger.error(f"Groq connection error: {exc}")
            raise GroqUnavailableError(f"Groq connection error: {exc}") from exc
        except Exception as exc:
            logger.error(f"Groq unexpected error: {exc}")
            raise GroqUnavailableError(f"Groq unexpected error: {exc}") from exc

        choices = result.get("choices") or []
        if not choices:
            raise GroqUnavailableError("Groq returned an empty response")

        content = (choices[0].get("message") or {}).get("content", "").strip()
        if not content:
            raise GroqUnavailableError("Groq returned empty content")
        return content
