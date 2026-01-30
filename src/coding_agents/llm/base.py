from typing import Any, Protocol


class LLMClientProtocol(Protocol):
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...
