from __future__ import annotations

from app.workflows.screening.result import (
    WorkflowEvidenceQuote,
    WorkflowEventEvidenceProgress,
)


def test_workflow_event_evidence_progress_limits_visible_quotes() -> None:
    progress = WorkflowEventEvidenceProgress(
        event_title="공급 계약 체결",
        source_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=1",
        quotes=(
            WorkflowEvidenceQuote(
                paragraph_index=1,
                quote="계약 금액은 1조원입니다.",
            ),
            WorkflowEvidenceQuote(
                paragraph_index=2,
                quote="계약 기간은 3년입니다.",
            ),
        ),
    )

    assert progress.quotes[0].paragraph_index == 1
    assert len(progress.quotes) == 2
