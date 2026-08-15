"""Tests for deterministic, text-based resume PDF processing."""

from __future__ import annotations

import pymupdf
import pytest

from app.services.pdf_processing import (
    MAX_RESUME_FILE_BYTES,
    PdfErrorCode,
    PdfProcessingError,
    normalize_extracted_text,
    process_resume_pdf,
)


def create_pdf(page_texts: list[str]) -> bytes:
    """Build a minimal in-memory text PDF for a test case."""

    document = pymupdf.open()
    try:
        for text in page_texts:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        return document.tobytes()
    finally:
        document.close()


def create_encrypted_pdf() -> bytes:
    """Build a minimal password-protected PDF without a disk fixture."""

    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "Protected resume")
        return document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password",
            user_pw="user-password",
        )
    finally:
        document.close()


def assert_error_code(error_code: PdfErrorCode, file_bytes: bytes, filename: str | None = None) -> None:
    with pytest.raises(PdfProcessingError) as exc_info:
        process_resume_pdf(file_bytes, filename)

    assert exc_info.value.code == error_code


def test_processes_a_valid_single_page_pdf() -> None:
    document = process_resume_pdf(
        create_pdf(["Python FastAPI\nMachine Learning"]),
        "resume.pdf",
    )

    assert document.page_count == 1
    assert document.pages[0].page_number == 1
    assert "Python FastAPI" in document.pages[0].text
    assert "Machine Learning" in document.full_text
    assert document.pages[0].character_count == len(document.pages[0].text)
    assert document.character_count == len(document.full_text)


def test_preserves_page_boundaries_and_order_for_multi_page_pdf() -> None:
    document = process_resume_pdf(create_pdf(["First page", "Second page"]))

    assert document.page_count == 2
    assert [page.page_number for page in document.pages] == [1, 2]
    assert document.pages[0].text == "First page"
    assert document.pages[1].text == "Second page"
    assert document.full_text == "First page\n\nSecond page"


def test_normalization_is_conservative_and_unicode_safe() -> None:
    text = "\r\n ภาษาไทย\r\nPython FastAPI  \r\n\r\n\r\n"

    assert normalize_extracted_text(text) == "ภาษาไทย\nPython FastAPI"


def test_rejects_empty_input() -> None:
    assert_error_code(PdfErrorCode.EMPTY_FILE, b"")


def test_rejects_oversized_input_before_pdf_parsing() -> None:
    oversized_bytes = b"%PDF-" + (b"0" * MAX_RESUME_FILE_BYTES)

    assert_error_code(PdfErrorCode.FILE_TOO_LARGE, oversized_bytes, "resume.pdf")


def test_rejects_valid_pdf_with_wrong_supplied_extension() -> None:
    assert_error_code(
        PdfErrorCode.INVALID_FILE_EXTENSION,
        create_pdf(["Python FastAPI"]),
        "resume.txt",
    )


def test_rejects_structurally_invalid_pdf_bytes() -> None:
    assert_error_code(PdfErrorCode.INVALID_PDF, b"%PDF-this-is-not-valid", "resume.pdf")


def test_rejects_encrypted_pdf() -> None:
    assert_error_code(PdfErrorCode.PDF_ENCRYPTED, create_encrypted_pdf(), "resume.pdf")


def test_rejects_pdf_over_page_limit() -> None:
    assert_error_code(
        PdfErrorCode.PAGE_LIMIT_EXCEEDED,
        create_pdf(["Page"] * 11),
        "resume.pdf",
    )


def test_rejects_valid_pdf_without_extractable_text() -> None:
    assert_error_code(PdfErrorCode.NO_EXTRACTABLE_TEXT, create_pdf([""]), "resume.pdf")
