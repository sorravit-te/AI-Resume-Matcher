"""Central translation from typed application errors to safe HTTP responses."""

from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.models.api_error import ApiErrorDetail, ApiErrorResponse
from app.services.evidence_validation import (
    EvidenceValidationError,
    EvidenceValidationErrorCode,
)
from app.services.llm_analysis import LlmAnalysisError, LlmErrorCode
from app.services.pdf_processing import PdfErrorCode, PdfProcessingError
from app.services.scoring import ScoringError

NO_STORE_HEADERS = {"Cache-Control": "no-store"}

PDF_ERROR_STATUS: Mapping[PdfErrorCode, int] = {
    PdfErrorCode.EMPTY_FILE: 400,
    PdfErrorCode.FILE_TOO_LARGE: 413,
    PdfErrorCode.INVALID_FILE_EXTENSION: 415,
    PdfErrorCode.INVALID_PDF: 400,
    PdfErrorCode.PDF_ENCRYPTED: 422,
    PdfErrorCode.PAGE_LIMIT_EXCEEDED: 422,
    PdfErrorCode.NO_EXTRACTABLE_TEXT: 422,
}

PDF_ERROR_MESSAGES: Mapping[PdfErrorCode, str] = {
    PdfErrorCode.EMPTY_FILE: "The uploaded file is empty.",
    PdfErrorCode.FILE_TOO_LARGE: "The uploaded PDF exceeds the maximum allowed size.",
    PdfErrorCode.INVALID_FILE_EXTENSION: "The uploaded file must use a .pdf extension.",
    PdfErrorCode.INVALID_PDF: "The uploaded file is not a valid PDF.",
    PdfErrorCode.PDF_ENCRYPTED: "Password-protected PDFs are not supported.",
    PdfErrorCode.PAGE_LIMIT_EXCEEDED: "The uploaded PDF exceeds the maximum page count.",
    PdfErrorCode.NO_EXTRACTABLE_TEXT: (
        "The uploaded PDF does not contain extractable text."
    ),
}

LLM_ERROR_STATUS: Mapping[LlmErrorCode, int] = {
    LlmErrorCode.LLM_NOT_CONFIGURED: 503,
    LlmErrorCode.LLM_REQUEST_FAILED: 502,
    LlmErrorCode.LLM_INVALID_RESPONSE: 502,
}

LLM_ERROR_MESSAGES: Mapping[LlmErrorCode, str] = {
    LlmErrorCode.LLM_NOT_CONFIGURED: "Resume analysis is temporarily unavailable.",
    LlmErrorCode.LLM_REQUEST_FAILED: "The resume analysis request failed.",
    LlmErrorCode.LLM_INVALID_RESPONSE: (
        "The resume analysis service returned an invalid response."
    ),
}

EVIDENCE_ERROR_MESSAGE = "The resume analysis evidence could not be verified."
SCORING_ERROR_MESSAGE = "The resume score could not be calculated."


def _error_response(*, code: str, message: str, status_code: int) -> JSONResponse:
    body = ApiErrorResponse(error=ApiErrorDetail(code=code, message=message))
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=NO_STORE_HEADERS,
    )


async def handle_pdf_processing_error(
    _request: Request,
    exc: PdfProcessingError,
) -> JSONResponse:
    """Expose only the stable PDF code and its reviewed public message."""

    return _error_response(
        code=exc.code.value,
        message=PDF_ERROR_MESSAGES[exc.code],
        status_code=PDF_ERROR_STATUS[exc.code],
    )


async def handle_llm_analysis_error(
    _request: Request,
    exc: LlmAnalysisError,
) -> JSONResponse:
    """Hide provider details while preserving the stable analysis error code."""

    return _error_response(
        code=exc.code.value,
        message=LLM_ERROR_MESSAGES[exc.code],
        status_code=LLM_ERROR_STATUS[exc.code],
    )


async def handle_evidence_validation_error(
    _request: Request,
    exc: EvidenceValidationError,
) -> JSONResponse:
    """Hide rejected evidence text and return a safe upstream-failure response."""

    return _error_response(
        code=exc.code.value,
        message=EVIDENCE_ERROR_MESSAGE,
        status_code=502,
    )


async def handle_scoring_error(
    _request: Request,
    exc: ScoringError,
) -> JSONResponse:
    """Hide internal scoring-contract details."""

    return _error_response(
        code=exc.code.value,
        message=SCORING_ERROR_MESSAGE,
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register handlers only for the application's known typed failures."""

    app.add_exception_handler(PdfProcessingError, handle_pdf_processing_error)
    app.add_exception_handler(LlmAnalysisError, handle_llm_analysis_error)
    app.add_exception_handler(
        EvidenceValidationError,
        handle_evidence_validation_error,
    )
    app.add_exception_handler(ScoringError, handle_scoring_error)
