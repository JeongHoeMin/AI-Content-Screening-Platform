from __future__ import annotations

from app.persistence.repository import DocumentIdentity


def test_document_identity_builds_stable_content_hash() -> None:
    first = DocumentIdentity.from_content(
        source="dart",
        external_id="20260804000001",
        canonical_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260804000001",
        content="공시 본문\n계약 체결",
    )
    second = DocumentIdentity.from_content(
        source="dart",
        external_id="20260804000001",
        canonical_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260804000001",
        content="공시 본문\n계약 체결",
    )

    assert first.content_sha256 == second.content_sha256
    assert len(first.content_sha256) == 64
