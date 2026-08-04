from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from app.config.errors import ConfigurationError


@dataclass(frozen=True)
class TelegramConfig:
    """Validated Telegram delivery credentials kept out of logs and APIs."""

    bot_token: str
    chat_id: str

    def __repr__(self) -> str:
        return "TelegramConfig(bot_token='***', chat_id='***')"


def load_optional_telegram_config() -> Optional[TelegramConfig]:
    """Return Telegram delivery settings only when both secret values are present."""
    bot_token: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id: str = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token and not chat_id:
        return None
    if not bot_token or not chat_id:
        raise ConfigurationError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be configured together"
        )
    return TelegramConfig(bot_token=bot_token, chat_id=chat_id)
