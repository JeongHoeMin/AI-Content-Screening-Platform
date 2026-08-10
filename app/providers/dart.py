from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Mapping, Optional
from zoneinfo import ZoneInfo

from pydantic import ValidationError
import structlog

from app.config.market_data import DartConfig
from app.models.collect_posts import CollectPostsRequest
from app.models.raw_post import RawDartDisclosurePost, RawPost
from app.providers.base import CommunityProvider
from app.providers.dart_document import DartDocumentExtractionError, DartDocumentExtractor
from app.providers.dart_event_filter import (
    DEFAULT_DART_EVENT_TYPE_ALLOWLIST,
    DartEventTypeAllowlist,
)
from app.providers.http import (
    BytesHttpClient,
    ExternalServiceError,
    JsonHttpClient,
    StdlibBytesHttpClient,
    StdlibJsonHttpClient,
)

logger = structlog.get_logger(__name__)

_DART_DISCLOSURE_LIST_URL: str = "https://opendart.fss.or.kr/api/list.json"
_DART_DOCUMENT_URL: str = "https://opendart.fss.or.kr/api/document.xml"
_KST: ZoneInfo = ZoneInfo("Asia/Seoul")
# Discovery scans the requested period at OpenDART's max page size, independent
# of CollectPostsRequest.limit (which bounds the dashboard's final display count,
# not how broadly DART should be scanned). Most disclosures are dropped by the
# event-type allowlist before any document is fetched, so a small display limit
# must not also starve discovery of raw candidates. Bounded by a fixed page cap
# so a long period cannot make one collect() call scan unboundedly.
_DISCOVERY_PAGE_SIZE: int = 100
_MAX_DISCOVERY_PAGES: int = 5


class DartDisclosureProvider(CommunityProvider):
    """Collect OpenDART disclosure-list metadata for the requested period."""

    def __init__(
        self,
        config: DartConfig,
        http_client: Optional[JsonHttpClient] = None,
        document_client: Optional[BytesHttpClient] = None,
        document_extractor: Optional[DartDocumentExtractor] = None,
        event_filter: Optional[DartEventTypeAllowlist] = None,
    ) -> None:
        self._config: DartConfig = config
        self._http_client: JsonHttpClient = http_client or StdlibJsonHttpClient()
        self._document_client: BytesHttpClient = document_client or StdlibBytesHttpClient()
        self._document_extractor: DartDocumentExtractor = (
            document_extractor or DartDocumentExtractor()
        )
        self._event_filter: DartEventTypeAllowlist = (
            event_filter or DEFAULT_DART_EVENT_TYPE_ALLOWLIST
        )

    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        now: datetime = request.ended_at or datetime.now(timezone.utc)
        ended_at_kst: datetime = now.astimezone(_KST)
        start_at_kst: datetime = ended_at_kst - request.period
        end_inclusive_kst: datetime = ended_at_kst - timedelta(microseconds=1)
        raw_posts: List[RawPost] = []
        page_no: int = 1
        while page_no <= _MAX_DISCOVERY_PAGES:
            payload: Mapping[str, Any] = await self._http_client.get(
                url=_DART_DISCLOSURE_LIST_URL,
                headers={},
                query={
                    "crtfc_key": self._config.api_key.get_secret_value(),
                    "bgn_de": start_at_kst.strftime("%Y%m%d"),
                    "end_de": end_inclusive_kst.strftime("%Y%m%d"),
                    "page_no": str(page_no),
                    "page_count": str(_DISCOVERY_PAGE_SIZE),
                    "sort": "date",
                    "sort_mth": "desc",
                },
                timeout_seconds=self._config.timeout_seconds,
            )
            status: object = payload.get("status")
            if status != "000":
                if page_no == 1:
                    raise ValueError("OpenDART disclosure list request was not accepted")
                break
            items: object = payload.get("list", [])
            if not isinstance(items, list):
                if page_no == 1:
                    raise ValueError("OpenDART response list must be a list")
                break
            for index, item in enumerate(items):
                raw_post: Optional[RawDartDisclosurePost] = self._parse_metadata(item, index)
                if raw_post is None:
                    continue
                if not self._event_filter.is_allowed(raw_post.report_name):
                    logger.info(
                        "dart_disclosure_filtered",
                        item_index=index,
                        page_no=page_no,
                        reason="event_type_not_allowed",
                        catalog_version=self._event_filter.version,
                    )
                    continue
                raw_posts.append(await self._with_document(raw_post, index))
            if not items or not self._has_next_page(payload, page_no):
                break
            page_no += 1
        return raw_posts

    @staticmethod
    def _has_next_page(payload: Mapping[str, Any], page_no: int) -> bool:
        total_page: object = payload.get("total_page")
        if isinstance(total_page, bool) or not isinstance(total_page, int):
            return False
        return page_no < total_page

    def _parse_metadata(
        self,
        item: object,
        index: int,
    ) -> Optional[RawDartDisclosurePost]:
        """Parse OpenDART list metadata only; does not fetch the filing document."""
        if not isinstance(item, dict):
            logger.warning("dart_disclosure_item_skipped", item_index=index, error_kind="invalid_type")
            return None
        try:
            receipt_number: str = str(item["rcept_no"])
            receipt_date: datetime = datetime.strptime(
                str(item["rcept_dt"]), "%Y%m%d"
            ).replace(tzinfo=timezone.utc)
            stock_code: Optional[str] = self._optional_string(item.get("stock_code"))
            market_class: Optional[str] = self._optional_string(item.get("corp_cls"))
            return RawDartDisclosurePost(
                raw_id=receipt_number,
                fetched_at=datetime.now(timezone.utc),
                corporation_code=str(item["corp_code"]),
                corporation_name=str(item["corp_name"]),
                stock_code=stock_code,
                market_class=market_class,
                report_name=str(item["report_nm"]),
                receipt_number=receipt_number,
                receipt_date=receipt_date,
                filer_name=self._optional_string(item.get("flr_nm")),
                disclosure_url=(
                    "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
                    f"{receipt_number}"
                ),
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            logger.warning("dart_disclosure_item_skipped", item_index=index, error_kind="invalid_item")
            return None

    async def _with_document(
        self,
        raw_post: RawDartDisclosurePost,
        index: int,
    ) -> RawDartDisclosurePost:
        try:
            archive: bytes = await self._document_client.get(
                url=_DART_DOCUMENT_URL,
                headers={},
                query={
                    "crtfc_key": self._config.api_key.get_secret_value(),
                    "rcept_no": raw_post.receipt_number,
                },
                timeout_seconds=self._config.timeout_seconds,
            )
            paragraphs: tuple[str, ...] = self._document_extractor.extract(archive)
        except DartDocumentExtractionError as error:
            logger.warning(
                "dart_document_unavailable",
                item_index=index,
                error_kind=error.kind,
            )
            return raw_post.model_copy(update={"document_error_kind": error.kind})
        except ExternalServiceError:
            logger.warning(
                "dart_document_unavailable",
                item_index=index,
                error_kind="transport_failure",
            )
            return raw_post.model_copy(update={"document_error_kind": "transport_failure"})
        return raw_post.model_copy(update={"document_paragraphs": paragraphs})

    def _optional_string(self, value: object) -> Optional[str]:
        text: str = str(value or "").strip()
        return text or None
