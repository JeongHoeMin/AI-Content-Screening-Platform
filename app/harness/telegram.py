from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Protocol, Tuple
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config.telegram import TelegramConfig
from app.providers.http import ExternalServiceError, JsonHttpClient, StdlibJsonHttpClient

_KST: ZoneInfo = ZoneInfo("Asia/Seoul")

RecommendationTrigger = Literal["scheduled", "dashboard"]

_TRIGGER_TITLES: dict[str, str] = {
    "scheduled": "AI 콘텐츠 스크리닝 정기 실행 완료",
    "dashboard": "AI 콘텐츠 스크리닝 실시간 추천 완료",
}


class TelegramRecommendationSummary(BaseModel):
    """Bounded, content-safe terminal observation for one recommendation run."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(min_length=1, max_length=64)
    scheduled_for: datetime
    recommendation_count: int = Field(ge=0)
    recommendations: Tuple[str, ...] = ()
    trigger: RecommendationTrigger = "scheduled"

    @field_validator("recommendations", mode="before")
    @classmethod
    def _limit_recommendations(cls, value: object) -> Tuple[str, ...]:
        """Keep the terminal message bounded even if an upstream caller sends more."""
        if not isinstance(value, tuple):
            raise ValueError("recommendations must be a tuple")
        return tuple(str(item) for item in value[:10])


class TelegramReporter(Protocol):
    """Best-effort terminal notifier that never affects the workflow outcome."""

    async def deliver(self, summary: TelegramRecommendationSummary) -> Optional[str]:
        """Return a safe delivery error category, when one occurs."""


class TelegramBotReporter:
    """Telegram Bot API adapter that sends only a concise operational report."""

    def __init__(
        self,
        config: TelegramConfig,
        http_client: Optional[JsonHttpClient] = None,
    ) -> None:
        self._config: TelegramConfig = config
        self._http_client: JsonHttpClient = http_client or StdlibJsonHttpClient()

    async def deliver(self, summary: TelegramRecommendationSummary) -> Optional[str]:
        try:
            response = await self._http_client.post(
                url=(
                    "https://api.telegram.org/bot"
                    f"{self._config.bot_token}/sendMessage"
                ),
                headers={},
                body={
                    "chat_id": self._config.chat_id,
                    "text": self._format_summary(summary),
                    "disable_web_page_preview": True,
                },
                timeout_seconds=10.0,
            )
        except ExternalServiceError:
            return "telegram_delivery_failed"
        if response.get("ok") is not True:
            return "telegram_delivery_failed"
        return None

    @staticmethod
    def _format_summary(summary: TelegramRecommendationSummary) -> str:
        scheduled_kst: str = summary.scheduled_for.astimezone(_KST).strftime(
            "%Y-%m-%d %H:%M KST"
        )
        lines: list[str] = [
            _TRIGGER_TITLES[summary.trigger],
            f"기준 시각: {scheduled_kst}",
            f"분석 후보: {summary.recommendation_count}건",
        ]
        if summary.recommendations:
            lines.append("후보: " + ", ".join(summary.recommendations))
        else:
            lines.append("후보: 정책 기준을 통과한 분석 후보가 없습니다.")
        return "\n".join(lines)
