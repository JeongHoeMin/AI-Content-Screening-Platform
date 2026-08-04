from __future__ import annotations

import io
import zipfile

import pytest

from app.providers.dart_document import DartDocumentExtractionError, DartDocumentExtractor


def build_zip(name: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, content)
    return buffer.getvalue()


def test_dart_document_extractor_returns_ordered_html_paragraphs() -> None:
    payload = build_zip("report.html", "<html><body><p>첫 문단</p><p>둘째 문단</p></body></html>")

    paragraphs = DartDocumentExtractor().extract(payload)

    assert paragraphs == ("첫 문단", "둘째 문단")


def test_dart_document_extractor_rejects_archive_path_traversal() -> None:
    payload = build_zip("../secret.html", "<p>노출되면 안 됩니다</p>")

    with pytest.raises(DartDocumentExtractionError):
        DartDocumentExtractor().extract(payload)


def test_dart_document_extractor_rejects_traversal_in_unselected_archive_member() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("report.html", "<p>정상 문단</p>")
        archive.writestr("../unexpected.txt", "unsafe")

    with pytest.raises(DartDocumentExtractionError):
        DartDocumentExtractor().extract(buffer.getvalue())


def test_dart_document_extractor_classifies_non_zip_payload_without_content() -> None:
    with pytest.raises(DartDocumentExtractionError) as error:
        DartDocumentExtractor().extract(b"not-a-zip")

    assert error.value.kind == "not_zip_archive"


def test_dart_document_extractor_classifies_opendart_error_status_without_payload() -> None:
    payload = b"<?xml version='1.0'?><result><status>020</status><message>safe</message></result>"

    with pytest.raises(DartDocumentExtractionError) as error:
        DartDocumentExtractor().extract(payload)

    assert error.value.kind == "opendart_status_020"
