from __future__ import annotations

import pytest

from app.config.errors import ConfigurationError
from app.config.trusted_sources import load_trusted_source_config
from app.core.exceptions import ProviderNotFoundError
from app.market_data import create_market_collect_posts_skill
from app.models.community import CommunityType


def test_load_trusted_source_config_parses_ir_rss_feed_definitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "IR_RSS_FEEDS",
        '[{"id":"samsung-ir","url":"https://example.com/rss.xml","company_name":"삼성전자"}]',
    )
    monkeypatch.setenv("ARTICLE_MIN_BODY_LENGTH", "320")
    monkeypatch.setenv("ARTICLE_MAX_BODY_LENGTH", "12000")

    config = load_trusted_source_config()

    assert config.ir_rss_feeds[0].id == "samsung-ir"
    assert str(config.ir_rss_feeds[0].url) == "https://example.com/rss.xml"
    assert config.min_body_length == 320
    assert config.max_body_length == 12000


@pytest.mark.parametrize(
    ("feeds", "minimum", "maximum"),
    [
        ("not-json", "300", "10000"),
        ('[{"id":"x","url":"not-a-url"}]', "300", "10000"),
        ('[{"id":"x","url":"https://example.com/rss"}]', "10001", "10000"),
    ],
)
def test_load_trusted_source_config_rejects_invalid_settings(
    monkeypatch: pytest.MonkeyPatch,
    feeds: str,
    minimum: str,
    maximum: str,
) -> None:
    monkeypatch.setenv("IR_RSS_FEEDS", feeds)
    monkeypatch.setenv("ARTICLE_MIN_BODY_LENGTH", minimum)
    monkeypatch.setenv("ARTICLE_MAX_BODY_LENGTH", maximum)

    with pytest.raises(ConfigurationError):
        load_trusted_source_config()


def test_rss_only_collection_requires_an_operator_configured_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IR_RSS_FEEDS", "[]")

    with pytest.raises(ConfigurationError, match="IR_RSS_FEEDS"):
        create_market_collect_posts_skill([CommunityType.IR_RSS])


def test_dart_only_collection_does_not_require_ir_rss_feeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IR_RSS_FEEDS", "[]")
    monkeypatch.setenv("DART_API_KEY", "dart-key")

    skill = create_market_collect_posts_skill([CommunityType.DART, CommunityType.IR_RSS])

    skill._provider_registry.get(CommunityType.DART)
    with pytest.raises(ProviderNotFoundError):
        skill._provider_registry.get(CommunityType.IR_RSS)
