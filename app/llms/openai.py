from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.llms.base import LLMClient
from app.llms.models import ChatMessage, ChatResponse, GenerationConfig


class OpenAIClient(LLMClient):
    """OpenAI SDK adapter for the project LLM client contract."""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client: AsyncOpenAI = client
        self._model: str = model

    async def chat(
        self,
        messages: List[ChatMessage],
        config: Optional[GenerationConfig] = None,
    ) -> ChatResponse:
        request_options: Dict[str, Any] = {
            "model": self._model,
            "messages": self._build_messages(messages),
        }
        self._apply_generation_config(request_options, config)

        response: Any = await self._client.chat.completions.create(**request_options)
        return ChatResponse(content=self._extract_content(response))

    @staticmethod
    def _build_messages(messages: List[ChatMessage]) -> List[Dict[str, str]]:
        return [
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in messages
        ]

    @staticmethod
    def _apply_generation_config(
        request_options: Dict[str, Any],
        config: Optional[GenerationConfig],
    ) -> None:
        if config is None:
            return

        if config.temperature is not None:
            request_options["temperature"] = config.temperature
        if config.max_tokens is not None:
            request_options["max_tokens"] = config.max_tokens

    @staticmethod
    def _extract_content(response: Any) -> str:
        content: Optional[str] = response.choices[0].message.content
        return content or ""
