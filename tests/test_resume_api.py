"""Deterministic API tests for the resume matching upload endpoint."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.routes import resume as resume_route
from app.main import app
from app.models.resume_analysis import AnalysisMatchType, CriterionAnalysis, ResumeAnalysis
from app.models.resume_match_result import ResumeMatchResult
from app.services.job_definition import load_job_definition
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


def test_pipeline_error_is_not_converted_to_success(monkeypatch) -> None:
    pipeline = Mock(side_effect=ScoringError("Invalid scoring contract."))
    monkeypatch.setattr(resume_route, "run_resume_matching", pipeline)

    with pytest.raises(ScoringError):
        client.post(
            "/api/v1/resume-match",
            files={"resume": ("resume.pdf", b"%PDF-synthetic", "application/pdf")},
        )


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
