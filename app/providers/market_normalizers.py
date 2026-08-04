from __future__ import annotations

import re
from html import unescape

from app.core.error import SkillError
from app.core.stage import SkillStage
from app.models.normalize import NormalizeResult
from app.models.post import Post
from app.models.raw_post import RawDartDisclosurePost, RawNaverNewsPost, RawPost
from app.providers.base import CommunityNormalizer

_HTML_TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]*>")
_WHITESPACE_PATTERN: re.Pattern[str] = re.compile(r"\s+")


class NaverNewsNormalizer(CommunityNormalizer):
    """Normalize Naver search result fields into a common news post."""

    async def normalize(self, raw_post: RawPost) -> NormalizeResult:
        if not isinstance(raw_post, RawNaverNewsPost):
            return self._invalid_type_error(raw_post, "RawNaverNewsPost")
        return NormalizeResult(
            post=Post(
                id=raw_post.raw_id,
                source=raw_post.source,
                title=_plain_text(raw_post.title_html),
                content=_plain_text(raw_post.description_html),
                created_at=raw_post.published_at,
                url=raw_post.publisher_url,
            )
        )

    def _invalid_type_error(self, raw_post: RawPost, expected_type: str) -> NormalizeResult:
        return NormalizeResult(
            error=SkillError(
                code="invalid_raw_post_type",
                stage=SkillStage.NORMALIZE,
                message=f"Expected {expected_type}",
                source=raw_post.source.value,
            )
        )


class DartDisclosureNormalizer(CommunityNormalizer):
    """Normalize OpenDART disclosure metadata without fetching the filing body."""

    async def normalize(self, raw_post: RawPost) -> NormalizeResult:
        if not isinstance(raw_post, RawDartDisclosurePost):
            return NormalizeResult(
                error=SkillError(
                    code="invalid_raw_post_type",
                    stage=SkillStage.NORMALIZE,
                    message="Expected RawDartDisclosurePost",
                    source=raw_post.source.value,
                )
            )
        stock_suffix: str = f" (종목코드: {raw_post.stock_code})" if raw_post.stock_code else ""
        fallback_content: str = (
            f"{raw_post.corporation_name}{stock_suffix}의 공시입니다. "
            f"공시 제목: {raw_post.report_name}. "
            f"공시 접수일: {raw_post.receipt_date.date().isoformat()}."
        )
        content: str = "\n".join(raw_post.document_paragraphs) or fallback_content
        return NormalizeResult(
            post=Post(
                id=raw_post.raw_id,
                source=raw_post.source,
                title=raw_post.report_name,
                content=content,
                author=raw_post.filer_name,
                created_at=raw_post.receipt_date,
                url=raw_post.disclosure_url,
                paragraphs=raw_post.document_paragraphs,
            )
        )


def _plain_text(value: str) -> str:
    """Decode provider HTML and collapse whitespace for a normalized post field."""
    decoded: str = unescape(value)
    without_tags: str = _HTML_TAG_PATTERN.sub(" ", decoded)
    return _WHITESPACE_PATTERN.sub(" ", without_tags).strip()
