from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ChatRole(str, Enum):
    """Supported chat message roles for LLM calls."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    """Single chat message passed to an LLM client."""

    role: ChatRole
    content: str


@dataclass(frozen=True)
class GenerationConfig:
    """Provider-independent generation options."""

    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@dataclass(frozen=True)
class ChatResponse:
    """LLM response content."""

    content: str
