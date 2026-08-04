from __future__ import annotations

import pytest

from app.models.news_event import EventEvidence


def test_event_evidence_limits_quote_length() -> None:
    evidence = EventEvidence(article_id="dart:1", paragraph_index=1, quote="근거 문장")

    assert evidence.quote == "근거 문장"

    with pytest.raises(ValueError):
        EventEvidence(article_id="dart:1", paragraph_index=1, quote="x" * 281)
