"""Tests for ordered, short-circuiting resume pipeline orchestration."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, ANY

import pytest

from app.models.resume_analysis import (
    AnalysisMatchType,
    CriterionAnalysis,
    EducationMetadata,
    ResumeAnalysis,
)
from app.models.resume_document import ResumeDocument, ResumePage
from app.models.resume_match_result import ResumeMatchResult
from app.services import resume_pipeline
from app.services.evidence_validation import (
    EvidenceValidationError,
    EvidenceValidationErrorCode,
)
from app.services.job_definition import load_job_definition
from app.services.llm_analysis import LlmAnalysisError, LlmErrorCode
from app.services.pdf_processing import PdfErrorCode, PdfProcessingError
from app.services.overall_rationale import build_overall_rationale
from app.services.scoring import ScoringError, score_resume_analysis


def create_resume() -> ResumeDocument:
    text = "Synthetic resume text"
    return ResumeDocument(
        filename="synthetic.pdf",
        page_count=1,
        pages=[ResumePage(page_number=1, text=text, character_count=len(text))],
        full_text=text,
        character_count=len(text),
    )


def create_analysis(job) -> ResumeAnalysis:
    return ResumeAnalysis(
        education=EducationMetadata(
            degree="Bachelor of Science",
            field_or_major="Computer Science",
        ),
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


def patch_successful_stages(monkeypatch, job, resume, analysis, score):
    overall_rationale = build_overall_rationale(score, job)
    stages = {
        "pdf": Mock(return_value=resume),
        "analysis": Mock(return_value=analysis),
        "evidence": Mock(return_value=analysis),
        "scoring": Mock(return_value=score),
        "rationale": Mock(return_value=overall_rationale),
    }
    monkeypatch.setattr(resume_pipeline, "process_resume_pdf", stages["pdf"])
    monkeypatch.setattr(resume_pipeline, "analyze_resume", stages["analysis"])
    monkeypatch.setattr(resume_pipeline, "validate_resume_evidence", stages["evidence"])
    monkeypatch.setattr(resume_pipeline, "score_resume_analysis", stages["scoring"])
    monkeypatch.setattr(resume_pipeline, "build_overall_rationale", stages["rationale"])
    return stages


def test_successful_pipeline_returns_complete_privacy_limited_result(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    score = score_resume_analysis(analysis, job)
    patch_successful_stages(monkeypatch, job, resume, analysis, score)

    result = resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf", job=job)

    assert isinstance(result, ResumeMatchResult)
    assert (result.job_id, result.company, result.job_title) == (
        job.job_id,
        job.company,
        job.title,
    )
    assert result.education == analysis.education
    assert result.score_name == score.score_name == "JD Match Score"
    assert result.overall_score == score.overall_score
    assert result.maximum_score == score.maximum_score
    assert isinstance(result.overall_rationale, str)
    assert len(result.overall_rationale) > 0
    assert result.category_scores == score.category_scores
    assert result.criterion_scores == score.criterion_scores


def test_scoring_and_result_use_the_validated_analysis_object(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    original_analysis = create_analysis(job)
    validated_analysis = original_analysis.model_copy(
        update={
            "candidate_name": "Validated Synthetic Candidate",
            "education": EducationMetadata(
                degree="Validated Bachelor Degree",
                field_or_major="Artificial Intelligence",
            )
        }
    )
    score = score_resume_analysis(validated_analysis, job)
    stages = patch_successful_stages(
        monkeypatch,
        job,
        resume,
        original_analysis,
        score,
    )
    stages["evidence"].return_value = validated_analysis

    result = resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf", job=job)

    stages["analysis"].assert_called_once_with(resume, job, client=None, metrics=ANY)
    stages["evidence"].assert_called_once_with(original_analysis, resume)
    stages["scoring"].assert_called_once_with(validated_analysis, job)
    assert stages["scoring"].call_args.args[0] is validated_analysis
    assert stages["scoring"].call_args.args[0] is not original_analysis
    assert result.candidate_name == validated_analysis.candidate_name
    assert result.candidate_name != original_analysis.candidate_name
    assert result.education == validated_analysis.education
    assert result.education != original_analysis.education


def test_pipeline_executes_stages_in_exact_order(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    score = score_resume_analysis(analysis, job)
    overall_rationale = build_overall_rationale(score, job)
    calls: list[str] = []

    def process_stage(file_bytes, filename):
        calls.append("process_pdf")
        return resume

    def analysis_stage(resume_document, job_definition, *, client=None, metrics=None):
        calls.append("analyze_resume")
        return analysis

    def evidence_stage(resume_analysis, resume_document):
        calls.append("validate_evidence")
        return analysis

    def scoring_stage(resume_analysis, job_definition):
        calls.append("score_analysis")
        return score

    def rationale_stage(resume_score, job_definition):
        calls.append("build_rationale")
        return overall_rationale

    monkeypatch.setattr(resume_pipeline, "process_resume_pdf", process_stage)
    monkeypatch.setattr(resume_pipeline, "analyze_resume", analysis_stage)
    monkeypatch.setattr(resume_pipeline, "validate_resume_evidence", evidence_stage)
    monkeypatch.setattr(resume_pipeline, "score_resume_analysis", scoring_stage)
    monkeypatch.setattr(resume_pipeline, "build_overall_rationale", rationale_stage)

    resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf", job=job)

    assert calls == ["process_pdf", "analyze_resume", "validate_evidence", "score_analysis", "build_rationale"]


def test_invalid_pdf_short_circuits_all_later_stages(monkeypatch) -> None:
    job = load_job_definition()
    pdf_error = PdfProcessingError(PdfErrorCode.INVALID_PDF, "Invalid PDF.")
    process_stage = Mock(side_effect=pdf_error)
    analysis_stage = Mock()
    evidence_stage = Mock()
    scoring_stage = Mock()
    monkeypatch.setattr(resume_pipeline, "process_resume_pdf", process_stage)
    monkeypatch.setattr(resume_pipeline, "analyze_resume", analysis_stage)
    monkeypatch.setattr(resume_pipeline, "validate_resume_evidence", evidence_stage)
    monkeypatch.setattr(resume_pipeline, "score_resume_analysis", scoring_stage)

    with pytest.raises(PdfProcessingError) as exc_info:
        resume_pipeline.run_resume_matching(b"invalid", "resume.pdf", job=job)

    assert exc_info.value is pdf_error
    analysis_stage.assert_not_called()
    evidence_stage.assert_not_called()
    scoring_stage.assert_not_called()


def test_llm_failure_short_circuits_validation_and_scoring(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    llm_error = LlmAnalysisError(LlmErrorCode.LLM_REQUEST_FAILED, "Request failed.")
    process_stage = Mock(return_value=resume)
    analysis_stage = Mock(side_effect=llm_error)
    evidence_stage = Mock()
    scoring_stage = Mock()
    monkeypatch.setattr(resume_pipeline, "process_resume_pdf", process_stage)
    monkeypatch.setattr(resume_pipeline, "analyze_resume", analysis_stage)
    monkeypatch.setattr(resume_pipeline, "validate_resume_evidence", evidence_stage)
    monkeypatch.setattr(resume_pipeline, "score_resume_analysis", scoring_stage)

    with pytest.raises(LlmAnalysisError) as exc_info:
        resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf", job=job)

    assert exc_info.value is llm_error
    evidence_stage.assert_not_called()
    scoring_stage.assert_not_called()


def test_evidence_failure_prevents_scoring(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    validation_error = EvidenceValidationError(
        EvidenceValidationErrorCode.EVIDENCE_NOT_FOUND,
        "Evidence was not found.",
    )
    stages = patch_successful_stages(
        monkeypatch,
        job,
        resume,
        analysis,
        score_resume_analysis(analysis, job),
    )
    stages["evidence"].side_effect = validation_error

    with pytest.raises(EvidenceValidationError) as exc_info:
        resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf", job=job)

    assert exc_info.value is validation_error
    stages["scoring"].assert_not_called()


def test_scoring_error_propagates_unchanged(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    score = score_resume_analysis(analysis, job)
    scoring_error = ScoringError("Invalid scoring contract.")
    stages = patch_successful_stages(monkeypatch, job, resume, analysis, score)
    stages["scoring"].side_effect = scoring_error

    with pytest.raises(ScoringError) as exc_info:
        resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf", job=job)

    assert exc_info.value is scoring_error


def test_default_job_definition_is_loaded(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    score = score_resume_analysis(analysis, job)
    loader = Mock(return_value=job)
    stages = patch_successful_stages(monkeypatch, job, resume, analysis, score)
    monkeypatch.setattr(resume_pipeline, "load_job_definition", loader)

    result = resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf")

    loader.assert_called_once_with()
    assert stages["analysis"].call_args.args[1] is job
    assert result.job_id == job.job_id


def test_explicit_job_does_not_reload_default(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    score = score_resume_analysis(analysis, job)
    loader = Mock()
    patch_successful_stages(monkeypatch, job, resume, analysis, score)
    monkeypatch.setattr(resume_pipeline, "load_job_definition", loader)

    resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf", job=job)

    loader.assert_not_called()


def test_injected_llm_client_is_passed_to_analysis_service(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    score = score_resume_analysis(analysis, job)
    stages = patch_successful_stages(monkeypatch, job, resume, analysis, score)
    llm_client = Mock(name="llm_client")

    resume_pipeline.run_resume_matching(
        b"synthetic",
        "resume.pdf",
        job=job,
        llm_client=llm_client,
    )

    from unittest.mock import ANY
    stages["analysis"].assert_called_once_with(resume, job, client=llm_client, metrics=ANY)


def test_result_excludes_resume_and_provider_internals(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    score = score_resume_analysis(analysis, job)
    patch_successful_stages(monkeypatch, job, resume, analysis, score)

    result = resume_pipeline.run_resume_matching(b"private bytes", "resume.pdf", job=job)
    result_fields = set(ResumeMatchResult.model_fields)

    assert "candidate_name" in result_fields
    assert "overall_rationale" in result_fields
    assert result_fields.isdisjoint(
        {"file_bytes", "full_text", "pages", "api_key", "provider_response", "prompt"}
    )
    serialized_result = result.model_dump_json()
    assert "private bytes" not in serialized_result
    assert resume.full_text not in serialized_result


def test_pipeline_does_not_mutate_mocked_analysis_or_score(monkeypatch) -> None:
    job = load_job_definition()
    resume = create_resume()
    analysis = create_analysis(job)
    score = score_resume_analysis(analysis, job)
    analysis_before = analysis.model_dump()
    score_before = score.model_dump()
    patch_successful_stages(monkeypatch, job, resume, analysis, score)

    resume_pipeline.run_resume_matching(b"synthetic", "resume.pdf", job=job)

    assert analysis.model_dump() == analysis_before
    assert score.model_dump() == score_before
