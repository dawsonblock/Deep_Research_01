from __future__ import annotations

from typing import Any

import httpx

from backend.config import get_settings
from backend.utils import normalize_text


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self.provider = settings.llm_provider.lower()
        self.base_url = settings.llm_api_base_url.rstrip('/')
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    def available(self) -> bool:
        return self.provider in {'openai', 'openrouter', 'compatible'} and bool(self.api_key)

    def complete_text(self, system_prompt: str, user_prompt: str, fallback: str) -> str:
        if not self.available():
            return normalize_text(fallback)
        headers = {'Authorization': f'Bearer {self.api_key}'}
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': 0.2,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f'{self.base_url}/chat/completions', headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            text = data['choices'][0]['message']['content']
            return normalize_text(text) if isinstance(text, str) else fallback
        except Exception:
            return normalize_text(fallback)

    def complete_json(self, system_prompt: str, user_prompt: str, fallback: dict[str, Any]) -> dict[str, Any]:
        if not self.available():
            return fallback
        headers = {'Authorization': f'Bearer {self.api_key}'}
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'response_format': {'type': 'json_object'},
            'temperature': 0.2,
        }
        try:
            import json
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f'{self.base_url}/chat/completions', headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            text = data['choices'][0]['message']['content']
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else fallback
        except Exception:
            return fallback


llm_service = LLMService()
