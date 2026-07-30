from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional

from pydantic import ValidationError
import structlog

from app.config.market_data import DartConfig
from app.models.collect_posts import CollectPostsRequest
from app.models.raw_post import RawDartDisclosurePost, RawPost
from app.providers.base import CommunityProvider
from app.providers.http import JsonHttpClient, StdlibJsonHttpClient

logger = structlog.get_logger(__name__)

_DART_DISCLOSURE_LIST_URL: str = "https://opendart.fss.or.kr/api/list.json"


class DartDisclosureProvider(CommunityProvider):
    """Collect OpenDART disclosure-list metadata for the requested period."""

    def __init__(
        self,
        config: DartConfig,
        http_client: Optional[JsonHttpClient] = None,
    ) -> None:
        self._config: DartConfig = config
        self._http_client: JsonHttpClient = http_client or StdlibJsonHttpClient()

    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        now: datetime = datetime.now(timezone.utc)
        payload: Mapping[str, Any] = await self._http_client.get(
            url=_DART_DISCLOSURE_LIST_URL,
            headers={},
            query={
                "crtfc_key": self._config.api_key.get_secret_value(),
                "bgn_de": (now - request.period).strftime("%Y%m%d"),
                "end_de": now.strftime("%Y%m%d"),
                "page_no": "1",
                "page_count": str(min(request.limit, 100)),
                "sort": "date",
                "sort_mth": "desc",
            },
            timeout_seconds=self._config.timeout_seconds,
        )
        status: object = payload.get("status")
        if status != "000":
            raise ValueError("OpenDART disclosure list request was not accepted")
        items: object = payload.get("list", [])
        if not isinstance(items, list):
            raise ValueError("OpenDART response list must be a list")

        raw_posts: List[RawPost] = []
        for index, item in enumerate(items):
            raw_post: Optional[RawDartDisclosurePost] = self._parse_item(item, index)
            if raw_post is not None:
                raw_posts.append(raw_post)
        return raw_posts

    def _parse_item(self, item: object, index: int) -> Optional[RawDartDisclosurePost]:
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

    def _optional_string(self, value: object) -> Optional[str]:
        text: str = str(value or "").strip()
        return text or None
