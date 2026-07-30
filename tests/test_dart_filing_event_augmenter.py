from __future__ import annotations

from datetime import datetime, timezone

from app.extractors import DartFilingEventAugmenter
from app.models import Article, EventFact, LLMExtractionResult, LLMInferenceResult


def build_article(*, source: str, title: str, content: str) -> Article:
    return Article(
        id="article-1",
        title=title,
        content=content,
        source=source,
        published_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260730800990",
    )


def build_result(article: Article) -> LLMExtractionResult:
    return LLMExtractionResult(
        inferences=(
            LLMInferenceResult(
                article=article,
                events=(),
                summary="LLM summary",
                reasoning="LLM found no event.",
                confidence=0.7,
            ),
        ),
        successful_batches=1,
    )


def test_augmenter_adds_explicit_dart_supply_contract_with_named_company() -> None:
    article: Article = build_article(
        source="dart",
        title="[기재정정]단일판매ㆍ공급계약체결(자회사의 주요경영사항)",
        content="HDC (종목코드: 012630)의 공시입니다.",
    )

    augmented: LLMExtractionResult = DartFilingEventAugmenter().augment(
        build_result(article)
    )

    event = augmented.inferences[0].events[0]
    assert event.event_facts == (EventFact.MAJOR_SUPPLY_CONTRACT,)
    assert event.companies[0].name == "HDC"
    assert event.companies[0].relation.value == "direct"


def test_augmenter_leaves_non_dart_and_non_contract_articles_unchanged() -> None:
    non_dart: Article = build_article(
        source="naver_news",
        title="단일판매ㆍ공급계약체결",
        content="HDC (종목코드: 012630)의 뉴스입니다.",
    )
    non_contract: Article = build_article(
        source="dart",
        title="최대주주등소유주식변동신고서",
        content="SK하이닉스 (종목코드: 000660)의 공시입니다.",
    )
    augmenter: DartFilingEventAugmenter = DartFilingEventAugmenter()

    assert augmenter.augment(build_result(non_dart)).inferences[0].events == ()
    assert augmenter.augment(build_result(non_contract)).inferences[0].events == ()
