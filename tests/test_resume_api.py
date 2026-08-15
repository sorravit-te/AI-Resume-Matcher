"""Deterministic API tests for the resume matching upload endpoint."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from app.api.routes import resume as resume_route
from app.main import app
from app.models.resume_analysis import AnalysisMatchType, CriterionAnalysis, ResumeAnalysis
from app.models.resume_match_result import ResumeMatchResult
from app.services.evidence_validation import (
    EvidenceValidationError,
    EvidenceValidationErrorCode,
)
from app.services.job_definition import load_job_definition
from app.services.llm_analysis import LlmAnalysisError, LlmErrorCode
from app.services.pdf_processing import (
    MAX_RESUME_FILE_BYTES,
    PdfErrorCode,
    PdfProcessingError,
)
from app.services.scoring import ScoringError, score_resume_analysis

client = TestClient(app)


def create_result() -> ResumeMatchResult:
    job = load_job_definition()
    analysis = ResumeAnalysis(
        education={},
        criteria=[
            CriterionAnalysis(
                criterion_id=criterion.id,
                match_type=AnalysisMatchType.NONE,
                evidence_level=0,
                evidence=[],
                rationale="ไม่พบหลักฐานที่เพียงพอในเรซูเม่",
            )
            for criterion in job.criteria
        ],
    )
    score = score_resume_analysis(analysis, job)
    return ResumeMatchResult(
        job_id=job.job_id,
        company=job.company,
        job_title=job.title,
        education=analysis.education,
        score_name=score.score_name,
        overall_score=score.overall_score,
        maximum_score=score.maximum_score,
        category_scores=score.category_scores,
        criterion_scores=score.criterion_scores,
    )


def test_successful_upload_forwards_bytes_and_filename_once(monkeypatch) -> None:
    expected_result = create_result()
    pipeline = Mock(return_value=expected_result)
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)
    file_bytes = b"%PDF-synthetic-api-test"

    response = client.post(
        "/api/v1/resume-match",
        files={"resume": ("Candidate.Resume.PDF", file_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == expected_result.model_dump(mode="json")
    assert response.headers["cache-control"] == "no-store"
    pipeline.assert_called_once_with(file_bytes, "Candidate.Resume.PDF")


def test_missing_resume_field_uses_fastapi_validation() -> None:
    response = client.post(
        "/api/v1/resume-match",
        files={"other": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
    )

    assert response.status_code == 422


def test_success_response_contract_excludes_private_pipeline_data(monkeypatch) -> None:
    pipeline = Mock(return_value=create_result())
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)

    response = client.post(
        "/api/v1/resume-match",
        files={"resume": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
    )
    response_fields = set(response.json())

    assert {
        "job_id",
        "company",
        "job_title",
        "score_name",
        "overall_score",
        "maximum_score",
        "category_scores",
        "criterion_scores",
    } <= response_fields
    assert response_fields.isdisjoint(
        {"file_bytes", "full_text", "pages", "api_key", "provider_response", "prompt"}
    )


def test_health_endpoint_remains_available() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_registers_multipart_post_operation() -> None:
    operation = app.openapi()["paths"]["/api/v1/resume-match"]["post"]

    assert "multipart/form-data" in operation["requestBody"]["content"]
    for status_code in (400, 413, 415, 500, 502, 503):
        schema = operation["responses"][str(status_code)]["content"][
            "application/json"
        ]["schema"]
        assert schema["$ref"] == "#/components/schemas/ApiErrorResponse"

    validation_response = operation["responses"]["422"]
    assert "content" not in validation_response
    assert "structured API error" in validation_response["description"]
    assert "FastAPI request validation" in validation_response["description"]


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        (PdfErrorCode.EMPTY_FILE, 400),
        (PdfErrorCode.FILE_TOO_LARGE, 413),
        (PdfErrorCode.INVALID_FILE_EXTENSION, 415),
        (PdfErrorCode.INVALID_PDF, 400),
        (PdfErrorCode.PDF_ENCRYPTED, 422),
        (PdfErrorCode.PAGE_LIMIT_EXCEEDED, 422),
        (PdfErrorCode.NO_EXTRACTABLE_TEXT, 422),
    ],
)
def test_pdf_errors_have_structured_status_mapping(
    monkeypatch,
    code: PdfErrorCode,
    status_code: int,
) -> None:
    pipeline = Mock(side_effect=PdfProcessingError(code, "private PDF detail"))
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)

    response = client.post(
        "/api/v1/resume-match",
        files={"resume": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
    )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code.value
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        (LlmErrorCode.LLM_NOT_CONFIGURED, 503),
        (LlmErrorCode.LLM_REQUEST_FAILED, 502),
        (LlmErrorCode.LLM_INVALID_RESPONSE, 502),
    ],
)
def test_llm_errors_have_safe_structured_status_mapping(
    monkeypatch,
    code: LlmErrorCode,
    status_code: int,
) -> None:
    provider_detail = "API_KEY=secret raw Gemini response and resume text"
    pipeline = Mock(side_effect=LlmAnalysisError(code, provider_detail))
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)

    response = client.post(
        "/api/v1/resume-match",
        files={"resume": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
    )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code.value
    assert provider_detail not in response.text
    assert "Gemini" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("code", list(EvidenceValidationErrorCode))
def test_evidence_errors_are_safe_502_responses(
    monkeypatch,
    code: EvidenceValidationErrorCode,
) -> None:
    rejected_quote = "secret rejected evidence quote from page 7"
    pipeline = Mock(side_effect=EvidenceValidationError(code, rejected_quote))
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)

    response = client.post(
        "/api/v1/resume-match",
        files={"resume": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
    )

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": code.value,
            "message": "The resume analysis evidence could not be verified.",
        }
    }
    assert rejected_quote not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_scoring_error_is_a_safe_500_response(monkeypatch) -> None:
    private_detail = r"Contract failure at C:\private\resume.pdf"
    pipeline = Mock(side_effect=ScoringError(private_detail))
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)

    response = client.post(
        "/api/v1/resume-match",
        files={"resume": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "SCORING_CONTRACT_INVALID",
            "message": "The resume score could not be calculated.",
        }
    }
    assert private_detail not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_exact_maximum_size_upload_reaches_pipeline(monkeypatch) -> None:
    expected_result = create_result()
    pipeline = Mock(return_value=expected_result)
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)
    file_bytes = b"P" * MAX_RESUME_FILE_BYTES

    response = client.post(
        "/api/v1/resume-match",
        files={"resume": ("resume.pdf", file_bytes, "application/octet-stream")},
    )

    assert response.status_code == 200
    pipeline.assert_called_once_with(file_bytes, "resume.pdf")


def test_maximum_plus_one_is_rejected_before_pipeline(monkeypatch) -> None:
    pipeline = Mock()
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)

    response = client.post(
        "/api/v1/resume-match",
        files={
            "resume": (
                "resume.pdf",
                b"P" * (MAX_RESUME_FILE_BYTES + 1),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert response.headers["cache-control"] == "no-store"
    pipeline.assert_not_called()


def test_pipeline_is_dispatched_through_threadpool(monkeypatch) -> None:
    expected_result = create_result()
    pipeline = Mock(return_value=expected_result)
    dispatches: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    async def fake_run_in_threadpool(function, *args, **kwargs):
        dispatches.append((function, args, kwargs))
        return function(*args, **kwargs)

    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)
    monkeypatch.setattr(resume_route, "run_in_threadpool", fake_run_in_threadpool)

    response = client.post(
        "/api/v1/resume-match",
        files={"resume": ("resume.pdf", b"%PDF-threadpool", "application/pdf")},
    )

    assert response.status_code == 200
    assert dispatches == [
        (pipeline, (b"%PDF-threadpool", "resume.pdf"), {}),
    ]


class TrackedUpload:
    """Minimal async upload double for testing route-owned closure."""

    filename = "resume.pdf"

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.offset = 0
        self.closed = False

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.content) - self.offset
        chunk = self.content[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    async def close(self) -> None:
        self.closed = True


def test_route_closes_upload_after_success(monkeypatch) -> None:
    upload = TrackedUpload(b"%PDF-success")
    expected_result = create_result()
    pipeline = Mock(return_value=expected_result)

    async def fake_run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)
    monkeypatch.setattr(resume_route, "run_in_threadpool", fake_run_in_threadpool)

    result = asyncio.run(resume_route.match_resume(Response(), upload))

    assert result is expected_result
    assert upload.closed is True


def test_route_closes_upload_after_failure(monkeypatch) -> None:
    upload = TrackedUpload(b"%PDF-failure")
    pipeline = Mock(side_effect=ScoringError("private scoring failure"))

    async def fake_run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)
    monkeypatch.setattr(resume_route, "run_in_threadpool", fake_run_in_threadpool)

    with pytest.raises(ScoringError):
        asyncio.run(resume_route.match_resume(Response(), upload))

    assert upload.closed is True
