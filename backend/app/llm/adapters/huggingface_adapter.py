import requests
from app.llm.base.base_llm import BaseLLM
from app.config import settings


class HuggingFaceLLM(BaseLLM):

    def __init__(self, model):
        self.model = model
        self.api_key = settings.HF_API_KEY
        self.api_url = f"https://api-inference.huggingface.co/models/{model}"

    async def generate(self, prompt: str, **kwargs):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": kwargs.get("max_tokens", 500),
                "temperature": kwargs.get("temperature", 0.7),
                "do_sample": True,
                "return_full_text": False
            }
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0:
                if 'generated_text' in result[0]:
                    return result[0]['generated_text'].strip()
            
            return str(result)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Hugging Face API error: {e}")
            return f"AI Service Error: {str(e)}"