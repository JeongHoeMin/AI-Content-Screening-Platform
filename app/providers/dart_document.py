from __future__ import annotations

import io
import zipfile
from typing import Tuple
from xml.etree import ElementTree

from bs4 import BeautifulSoup


class DartDocumentExtractionError(ValueError):
    """Raised when an OpenDART original-document archive is unsafe or unusable."""

    def __init__(self, kind: str) -> None:
        self.kind: str = kind
        super().__init__(kind)


class DartDocumentExtractor:
    """Extract bounded, ordered text paragraphs from an OpenDART ZIP response."""

    _MAX_ARCHIVE_MEMBERS: int = 20
    _MAX_UNCOMPRESSED_BYTES: int = 5_000_000

    def extract(self, payload: bytes) -> Tuple[str, ...]:
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = archive.infolist()
                if len(members) > self._MAX_ARCHIVE_MEMBERS:
                    raise DartDocumentExtractionError("too_many_members")
                if sum(member.file_size for member in members) > self._MAX_UNCOMPRESSED_BYTES:
                    raise DartDocumentExtractionError("content_too_large")
                if any(self._is_unsafe_path(member.filename) for member in members):
                    raise DartDocumentExtractionError("unsafe_path")
                selected = next(
                    (member for member in members if self._is_supported(member.filename)),
                    None,
                )
                if selected is None:
                    raise DartDocumentExtractionError("unsupported_document")
                content: str = archive.read(selected).decode("utf-8", errors="replace")
        except zipfile.BadZipFile as error:
            raise DartDocumentExtractionError(self._non_zip_error_kind(payload)) from error
        paragraphs: Tuple[str, ...] = self._paragraphs(content)
        if not paragraphs:
            raise DartDocumentExtractionError("no_text_paragraphs")
        return paragraphs

    @staticmethod
    def _is_supported(name: str) -> bool:
        return name.casefold().endswith((".html", ".htm", ".xml"))

    @staticmethod
    def _is_unsafe_path(name: str) -> bool:
        parts: Tuple[str, ...] = tuple(part for part in name.replace("\\", "/").split("/") if part)
        return name.startswith(("/", "\\")) or ".." in parts

    @staticmethod
    def _non_zip_error_kind(payload: bytes) -> str:
        """Classify only OpenDART's safe response status, never its message body."""
        try:
            root: ElementTree.Element = ElementTree.fromstring(payload)
        except ElementTree.ParseError:
            return "not_zip_archive"
        status: ElementTree.Element | None = root.find(".//status")
        status_value: str = "" if status is None or status.text is None else status.text.strip()
        if status_value.isdigit() and len(status_value) <= 8:
            return f"opendart_status_{status_value}"
        return "not_zip_archive"

    @staticmethod
    def _paragraphs(content: str) -> Tuple[str, ...]:
        soup = BeautifulSoup(content, "html.parser")
        candidates = soup.find_all(["p", "li", "td"])
        paragraphs: list[str] = []
        for candidate in candidates:
            value: str = " ".join(candidate.get_text(" ", strip=True).split())
            if value and value not in paragraphs:
                paragraphs.append(value)
        if not paragraphs:
            plain: str = " ".join(soup.get_text(" ", strip=True).split())
            if plain:
                paragraphs.append(plain)
        return tuple(paragraphs)
