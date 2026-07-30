from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ExternalServiceError(RuntimeError):
    """Safe error boundary for an external provider request."""


class JsonHttpClient(Protocol):
    """Minimal injected JSON transport used by external collection providers."""

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        """Fetch and decode one JSON object."""


class StdlibJsonHttpClient:
    """Async wrapper around the standard-library HTTP client."""

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request_url: str = f"{url}?{urlencode(dict(query))}" if query else url
        return await asyncio.to_thread(
            self._get_sync,
            request_url,
            dict(headers),
            timeout_seconds,
        )

    def _get_sync(
        self,
        request_url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request: Request = Request(request_url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload: object = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ExternalServiceError(f"HTTP status {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ExternalServiceError("Network request failed") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalServiceError("Response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ExternalServiceError("Response root must be a JSON object")
        return payload
