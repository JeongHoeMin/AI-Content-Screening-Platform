from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Mapping

from app.config.telegram import TelegramConfig
from app.harness.telegram import TelegramBotReporter, TelegramRecommendationSummary
from app.providers.http import ExternalServiceError


class _RecordingHttpClient:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response: Mapping[str, Any] = response
        self.url: str = ""
        self.body: Mapping[str, Any] = {}

    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.url = url
        self.body = body
        return self.response


class _FailingHttpClient:
    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        raise ExternalServiceError("Network request failed")


def _summary() -> TelegramRecommendationSummary:
    return TelegramRecommendationSummary(
        execution_id="exec-1",
        scheduled_for=datetime(2026, 8, 5, 23, 0, tzinfo=timezone.utc),
        recommendation_count=1,
        recommendations=("반도체 · 분석 후보",),
    )


def test_telegram_reporter_posts_safe_summary_without_exposing_token() -> None:
    client = _RecordingHttpClient({"ok": True})
    reporter = TelegramBotReporter(
        TelegramConfig(bot_token="secret-token", chat_id="123"), client
    )

    assert asyncio.run(reporter.deliver(_summary())) is None
    assert client.url.endswith("/botsecret-token/sendMessage")
    assert client.body["chat_id"] == "123"
    assert "2026-08-06 08:00 KST" in str(client.body["text"])


def test_telegram_reporter_returns_safe_error_category() -> None:
    reporter = TelegramBotReporter(
        TelegramConfig(bot_token="secret-token", chat_id="123"), _FailingHttpClient()
    )

    assert asyncio.run(reporter.deliver(_summary())) == "telegram_delivery_failed"
