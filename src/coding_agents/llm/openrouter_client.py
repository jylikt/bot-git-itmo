from typing import Any

from openai import OpenAI

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    def __init__(self, api_key: str, model: str):
        self._client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE)
        self._model = model

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""
