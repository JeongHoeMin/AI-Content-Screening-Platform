from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from pydantic import ValidationError
import structlog

from app.config.errors import ConfigurationError
from app.config.market_data import KrxConfig
from app.models.company_resolution import CanonicalCompany, CompanyDirectoryEntry, KRXExchange
from app.providers.http import ExternalServiceError, JsonHttpClient, StdlibJsonHttpClient
from app.resolvers.directory import StaticCompanyDirectory

logger = structlog.get_logger(__name__)

_KRX_ENDPOINTS: Tuple[Tuple[KRXExchange, str], ...] = (
    (KRXExchange.KOSPI, "https://data-dbg.krx.co.kr/svc/apis/sto/stk_isu_base_info"),
    (KRXExchange.KOSDAQ, "https://data-dbg.krx.co.kr/svc/apis/sto/ksq_isu_base_info"),
    (KRXExchange.KONEX, "https://data-dbg.krx.co.kr/svc/apis/sto/knx_isu_base_info"),
)


class KrxCompanyDirectoryLoader:
    """Build one immutable company-directory snapshot from three KRX markets."""

    def __init__(
        self,
        config: KrxConfig,
        http_client: Optional[JsonHttpClient] = None,
    ) -> None:
        self._config: KrxConfig = config
        self._http_client: JsonHttpClient = http_client or StdlibJsonHttpClient()

    async def load(self) -> StaticCompanyDirectory:
        results: Sequence[Optional[List[CompanyDirectoryEntry]]] = await asyncio.gather(
            *(self._load_exchange(exchange, url) for exchange, url in _KRX_ENDPOINTS)
        )
        entries: List[CompanyDirectoryEntry] = []
        for result in results:
            if result is not None:
                entries.extend(result)
        if not entries:
            raise ConfigurationError("KRX company directory could not load any market")
        version: str = self._config.directory_date.isoformat()
        try:
            return StaticCompanyDirectory(entries, version=version)
        except ValueError as error:
            raise ConfigurationError("KRX company directory contains invalid rows") from error

    async def _load_exchange(
        self,
        exchange: KRXExchange,
        url: str,
    ) -> Optional[List[CompanyDirectoryEntry]]:
        try:
            payload: Mapping[str, Any] = await self._http_client.post(
                url=url,
                headers={"AUTH_KEY": self._config.api_key.get_secret_value()},
                body={"basDd": self._config.directory_date.strftime("%Y%m%d")},
                timeout_seconds=self._config.timeout_seconds,
            )
            rows: object = payload.get("OutBlock_1")
            if not isinstance(rows, list):
                raise ValueError("KRX response OutBlock_1 must be a list")
            entries: List[CompanyDirectoryEntry] = []
            for index, row in enumerate(rows):
                entry: Optional[CompanyDirectoryEntry] = self._parse_row(row, exchange)
                if entry is None:
                    logger.warning(
                        "krx_company_row_skipped",
                        exchange=exchange.value,
                        row_index=index,
                        error_kind="invalid_row",
                    )
                    continue
                entries.append(entry)
            return entries
        except (ExternalServiceError, ValueError) as exc:
            logger.warning(
                "krx_market_load_failed",
                exchange=exchange.value,
                error_kind=type(exc).__name__,
            )
            return None

    def _parse_row(
        self,
        row: object,
        exchange: KRXExchange,
    ) -> Optional[CompanyDirectoryEntry]:
        if not isinstance(row, dict):
            return None
        try:
            company_id: str = str(row["ISU_CD"]).strip()
            canonical_name: str = str(row["ISU_NM"]).strip()
            ticker: str = str(row["ISU_SRT_CD"]).strip().zfill(6)
            aliases: Tuple[str, ...] = tuple(
                alias
                for alias in (
                    self._text_or_none(row.get("ISU_ABBRV")),
                    self._text_or_none(row.get("ISU_ENG_NM")),
                )
                if alias is not None and alias != canonical_name
            )
            company: CanonicalCompany = CanonicalCompany(
                company_id=company_id,
                canonical_name=canonical_name,
                ticker=ticker,
                exchange=exchange,
                directory_version=self._config.directory_date.isoformat(),
            )
            return CompanyDirectoryEntry(company=company, aliases=aliases)
        except (KeyError, TypeError, ValueError, ValidationError):
            return None

    def _text_or_none(self, value: object) -> Optional[str]:
        text: str = str(value or "").strip()
        return text or None
