from __future__ import annotations

import pytest

from app.providers.dart_event_filter import (
    DEFAULT_DART_EVENT_TYPE_ALLOWLIST,
    DefaultDartEventTypeAllowlist,
)


@pytest.mark.parametrize(
    "report_name",
    [
        "단일판매ㆍ공급계약체결(자율공시)",
        "[기재정정]매출액또는손익구조30%(대규모법인은15%)이상변동",
        "가이던스 변경 안내",
        "신규시설투자등결정",
        "타법인주식및출자증권취득결정",
        "유상증자결정",
        "전환사채권발행결정",
        "자기주식취득결정",
        "[제재]불성실공시법인지정",
        "소송등의제기ㆍ신청(당사가원고)",
    ],
)
def test_allowlist_accepts_investment_relevant_report_titles(report_name: str) -> None:
    assert DEFAULT_DART_EVENT_TYPE_ALLOWLIST.is_allowed(report_name) is True


@pytest.mark.parametrize(
    "report_name",
    [
        "[기재정정]반기보고서",
        "사업보고서",
        "최대주주등소유주식변동신고서",
        "임원ㆍ주요주주특정증권등소유상황보고서",
        "분기보고서",
        "",
        "   ",
    ],
)
def test_allowlist_rejects_periodic_and_low_impact_report_titles(report_name: str) -> None:
    assert DEFAULT_DART_EVENT_TYPE_ALLOWLIST.is_allowed(report_name) is False


def test_allowlist_has_a_stable_version_identifier() -> None:
    assert DEFAULT_DART_EVENT_TYPE_ALLOWLIST.version == "dart-event-type-v1"
    assert DefaultDartEventTypeAllowlist().version == DEFAULT_DART_EVENT_TYPE_ALLOWLIST.version
