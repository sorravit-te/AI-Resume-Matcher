"""Safe, deterministic extraction of text-based resume PDFs."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import pymupdf

from app.models.resume_document import ResumeDocument, ResumePage

MAX_RESUME_FILE_BYTES = 10 * 1024 * 1024
MAX_RESUME_PAGES = 10


class PdfErrorCode(StrEnum):
    """Stable errors exposed by the PDF processing domain boundary."""

    EMPTY_FILE = "EMPTY_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_EXTENSION = "INVALID_FILE_EXTENSION"
    INVALID_PDF = "INVALID_PDF"
    PDF_ENCRYPTED = "PDF_ENCRYPTED"
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"


class PdfProcessingError(ValueError):
    """A safe PDF-processing error with a stable code and public message."""

    def __init__(self, code: PdfErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def normalize_extracted_text(text: str) -> str:
    """Apply only traceability-preserving cleanup to extracted page text."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))

    while "\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n", "\n\n")

    return normalized.strip()


def process_resume_pdf(file_bytes: bytes, filename: str | None = None) -> ResumeDocument:
    """Validate and extract a text-based resume PDF held entirely in memory."""

    _validate_input(file_bytes, filename)

    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
    except (pymupdf.EmptyFileError, pymupdf.FileDataError) as exc:
        raise PdfProcessingError(
            PdfErrorCode.INVALID_PDF,
            "The file is not a valid PDF document.",
        ) from exc

    try:
        if document.needs_pass:
            raise PdfProcessingError(
                PdfErrorCode.PDF_ENCRYPTED,
                "Password-protected PDFs are not supported.",
            )

        if document.page_count == 0:
            raise PdfProcessingError(
                PdfErrorCode.INVALID_PDF,
                "The PDF does not contain any pages.",
            )
        if document.page_count > MAX_RESUME_PAGES:
            raise PdfProcessingError(
                PdfErrorCode.PAGE_LIMIT_EXCEEDED,
                f"PDFs are limited to {MAX_RESUME_PAGES} pages.",
            )

        pages: list[ResumePage] = []
        for page_index in range(document.page_count):
            page_text = normalize_extracted_text(
                document.load_page(page_index).get_text("text")
            )
            pages.append(
                ResumePage(
                    page_number=page_index + 1,
                    text=page_text,
                    character_count=len(page_text),
                )
            )
    finally:
        document.close()

    full_text = "\n\n".join(page.text for page in pages)
    if not full_text.strip():
        raise PdfProcessingError(
            PdfErrorCode.NO_EXTRACTABLE_TEXT,
            "The PDF does not contain extractable text. Scanned or image-only PDFs are not supported in the current MVP.",
        )

    return ResumeDocument(
        filename=filename,
        page_count=len(pages),
        pages=pages,
        full_text=full_text,
        character_count=len(full_text),
    )


def _validate_input(file_bytes: bytes, filename: str | None) -> None:
    """Reject invalid inputs before invoking the PDF parser."""

    if not file_bytes or not file_bytes.strip(b"\x00\t\n\r "):
        raise PdfProcessingError(PdfErrorCode.EMPTY_FILE, "The PDF file is empty.")
    if len(file_bytes) > MAX_RESUME_FILE_BYTES:
        raise PdfProcessingError(
            PdfErrorCode.FILE_TOO_LARGE,
            f"PDFs are limited to {MAX_RESUME_FILE_BYTES} bytes.",
        )
    if filename is not None and Path(filename).suffix.lower() != ".pdf":
        raise PdfProcessingError(
            PdfErrorCode.INVALID_FILE_EXTENSION,
            "The supplied filename must use a .pdf extension.",
        )
    if not file_bytes.startswith(b"%PDF-"):
        raise PdfProcessingError(
            PdfErrorCode.INVALID_PDF,
            "The file does not have a valid PDF signature.",
        )
