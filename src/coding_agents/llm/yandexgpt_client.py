from typing import Any

import requests

YANDEX_COMPLETION_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class YandexGPTClient:
    def __init__(self, folder_id: str, api_key: str = "", iam_token: str = ""):
        self._folder_id = folder_id
        self._api_key = api_key
        self._iam_token = iam_token
        self._model_uri = f"gpt://{folder_id}/yandexgpt-lite/latest"

    def _headers(self) -> dict[str, str]:
        if self._iam_token:
            return {"Authorization": f"Bearer {self._iam_token}"}
        return {"Authorization": f"Api-Key {self._api_key}"}

    def _to_yandex_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        out = []
        for m in messages:
            role = m.get("role", "user")
            if role == "system":
                out.append({"role": "user", "text": m.get("content", "")})
                out.append({"role": "assistant", "text": "OK."})
            else:
                out.append({"role": role, "text": m.get("content", "")})
        return out

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        body = {
            "modelUri": self._model_uri,
            "completionOptions": {
                "temperature": kwargs.get("temperature", 0.6),
                "maxTokens": str(kwargs.get("max_tokens", 2000)),
            },
            "messages": self._to_yandex_messages(messages),
        }
        resp = requests.post(
            YANDEX_COMPLETION_URL,
            headers=self._headers(),
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result", {})
        alternatives = result.get("alternatives", [])
        if not alternatives:
            return ""
        return alternatives[0].get("message", {}).get("text", "")
