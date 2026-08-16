"""HTTP boundary for the in-memory resume matching pipeline."""

import re
from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.models.api_error import ApiErrorResponse
from app.models.resume_match_result import ResumeMatchResult
from app.services.pdf_processing import (
    MAX_RESUME_FILE_BYTES,
    PdfErrorCode,
    PdfProcessingError,
)
from app.services.resume_pipeline import run_resume_matching

router = APIRouter(prefix="/api/v1", tags=["resume matching"])
_UPLOAD_READ_CHUNK_BYTES = 64 * 1024
_DEFAULT_RESULT_FILENAME = "resume_match_result.json"
_INTERNAL_WHITESPACE = re.compile(r"\s+")
_UNSAFE_FILENAME_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]+")
_REPEATED_UNDERSCORES = re.compile(r"_+")

ERROR_RESPONSES = {
    400: {"model": ApiErrorResponse, "description": "Empty or invalid PDF"},
    413: {"model": ApiErrorResponse, "description": "PDF exceeds the size limit"},
    415: {"model": ApiErrorResponse, "description": "Invalid filename extension"},
    422: {
        "description": (
            "Unsupported PDF contents or page count (structured API error), "
            "or FastAPI request validation failure"
        ),
    },
    500: {"model": ApiErrorResponse, "description": "Scoring contract failure"},
    502: {"model": ApiErrorResponse, "description": "Analysis validation failure"},
    503: {"model": ApiErrorResponse, "description": "Analysis is not configured"},
}


@router.post(
    "/resume-match",
    response_model=ResumeMatchResult,
    responses=ERROR_RESPONSES,
    summary="Match a resume to the EDVISORY internship",
    description="Analyze one text-based PDF resume and return its JD Match Score.",
)
async def match_resume(
    response: Response,
    resume: Annotated[UploadFile, File(description="Text-based PDF resume")],
) -> ResumeMatchResult:
    """Read a bounded upload and run the synchronous pipeline off the event loop."""

    try:
        file_bytes = await _read_upload_bounded(resume)
        result = await run_in_threadpool(
            run_resume_matching,
            file_bytes,
            resume.filename,
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{_result_filename(result.candidate_name)}"'
        )
        return result
    finally:
        await resume.close()


def _result_filename(candidate_name: str | None) -> str:
    """Return a path-free ASCII filename derived only from candidate_name."""

    if candidate_name is None:
        return _DEFAULT_RESULT_FILENAME

    normalized = _INTERNAL_WHITESPACE.sub("_", candidate_name.strip())
    sanitized = _UNSAFE_FILENAME_CHARACTERS.sub("_", normalized)
    sanitized = _REPEATED_UNDERSCORES.sub("_", sanitized).strip("_-")
    if not sanitized or not any(character.isalnum() for character in sanitized):
        return _DEFAULT_RESULT_FILENAME
    return f"{sanitized}_resume_match.json"


async def _read_upload_bounded(resume: UploadFile) -> bytes:
    """Read at most the PDF service limit plus one detection byte."""

    chunks: list[bytes] = []
    total_bytes = 0

    while True:
        remaining_with_detection_byte = MAX_RESUME_FILE_BYTES - total_bytes + 1
        chunk = await resume.read(
            min(_UPLOAD_READ_CHUNK_BYTES, remaining_with_detection_byte)
        )
        if not chunk:
            return b"".join(chunks)

        total_bytes += len(chunk)
        if total_bytes > MAX_RESUME_FILE_BYTES:
            raise PdfProcessingError(
                PdfErrorCode.FILE_TOO_LARGE,
                f"PDFs are limited to {MAX_RESUME_FILE_BYTES} bytes.",
            )
        chunks.append(chunk)
