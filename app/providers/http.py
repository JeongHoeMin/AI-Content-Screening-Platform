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

    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        """Send one JSON request body and decode one JSON response object."""


class BytesHttpClient(Protocol):
    """Minimal injected transport for bounded binary provider responses."""

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> bytes:
        """Fetch one response body without exposing it to provider logs."""


class TextHttpClient(Protocol):
    """Minimal injected transport for trusted RSS or Atom feed text."""

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> str:
        """Fetch one feed response without logging the full payload."""


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

    async def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request_headers: dict[str, str] = dict(headers)
        request_headers["Content-Type"] = "application/json"
        request_body: bytes = json.dumps(body).encode("utf-8")
        return await asyncio.to_thread(
            self._post_sync,
            url,
            request_headers,
            request_body,
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

    def _post_sync(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request: Request = Request(url, data=body, headers=dict(headers), method="POST")
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


class StdlibBytesHttpClient:
    """Async standard-library transport for OpenDART original-document ZIP files."""

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> bytes:
        request_url: str = f"{url}?{urlencode(dict(query))}" if query else url
        return await asyncio.to_thread(
            self._get_sync,
            request_url,
            dict(headers),
            timeout_seconds,
        )

    @staticmethod
    def _get_sync(
        request_url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> bytes:
        request: Request = Request(request_url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            raise ExternalServiceError(f"HTTP status {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ExternalServiceError("Network request failed") from exc


class StdlibTextHttpClient:
    """Async standard-library transport for configured RSS and Atom feeds."""

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> str:
        request_url: str = f"{url}?{urlencode(dict(query))}" if query else url
        return await asyncio.to_thread(
            self._get_sync,
            request_url,
            dict(headers),
            timeout_seconds,
        )

    @staticmethod
    def _get_sync(
        request_url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> str:
        request: Request = Request(request_url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise ExternalServiceError(f"HTTP status {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ExternalServiceError("Network request failed") from exc
