"""Tests for deterministic quote and page provenance validation."""

from __future__ import annotations

import pytest

from app.models.resume_analysis import (
    AnalysisMatchType,
    CriterionAnalysis,
    EvidenceSourceType,
    ResumeAnalysis,
    ResumeEvidence,
)
from app.models.resume_document import ResumeDocument, ResumePage
from app.services.evidence_validation import (
    EvidenceValidationError,
    EvidenceValidationErrorCode,
    normalize_evidence_text,
    validate_resume_evidence,
)


def create_resume(*page_texts: str) -> ResumeDocument:
    pages = [
        ResumePage(page_number=index, text=text, character_count=len(text))
        for index, text in enumerate(page_texts, start=1)
    ]
    full_text = "\n\n".join(page_texts)
    return ResumeDocument(
        filename="synthetic.pdf",
        page_count=len(pages),
        pages=pages,
        full_text=full_text,
        character_count=len(full_text),
    )


def create_analysis(*evidence_items: ResumeEvidence) -> ResumeAnalysis:
    return ResumeAnalysis(
        education={},
        criteria=[
            CriterionAnalysis(
                criterion_id="skills.python",
                match_type=AnalysisMatchType.DIRECT,
                evidence_level=3,
                evidence=list(evidence_items),
                rationale="พบหลักฐานการใช้งาน Python ในเรซูเม่",
            )
        ],
    )


def create_evidence(text: str, page: int = 1) -> ResumeEvidence:
    return ResumeEvidence(
        text=text,
        page=page,
        source_type=EvidenceSourceType.PROJECT,
    )


def test_exact_evidence_on_claimed_page_succeeds() -> None:
    analysis = create_analysis(create_evidence("Built a FastAPI backend using Python."))
    resume = create_resume("Built a FastAPI backend using Python.")

    assert validate_resume_evidence(analysis, resume) is analysis


def test_whitespace_differences_are_normalized() -> None:
    analysis = create_analysis(create_evidence("Built a FastAPI backend using Python."))
    resume = create_resume("Built a FastAPI backend\nusing\tPython.")

    assert validate_resume_evidence(analysis, resume) is analysis


def test_paraphrased_evidence_is_rejected() -> None:
    analysis = create_analysis(create_evidence("Built several production Python backend systems."))
    resume = create_resume("Developed backend services with Python.")

    with pytest.raises(EvidenceValidationError) as exc_info:
        validate_resume_evidence(analysis, resume)

    assert exc_info.value.code == EvidenceValidationErrorCode.EVIDENCE_NOT_FOUND


def test_evidence_on_the_wrong_page_is_rejected() -> None:
    analysis = create_analysis(create_evidence("PostgreSQL", page=1))
    resume = create_resume("Python", "PostgreSQL")

    with pytest.raises(EvidenceValidationError) as exc_info:
        validate_resume_evidence(analysis, resume)

    assert exc_info.value.code == EvidenceValidationErrorCode.EVIDENCE_NOT_FOUND


def test_evidence_on_the_correct_page_succeeds() -> None:
    analysis = create_analysis(create_evidence("PostgreSQL", page=2))
    resume = create_resume("Python", "PostgreSQL")

    assert validate_resume_evidence(analysis, resume) is analysis


def test_missing_claimed_page_is_rejected() -> None:
    analysis = create_analysis(create_evidence("Python", page=3))
    resume = create_resume("Python")

    with pytest.raises(EvidenceValidationError) as exc_info:
        validate_resume_evidence(analysis, resume)

    assert exc_info.value.code == EvidenceValidationErrorCode.EVIDENCE_PAGE_NOT_FOUND


def test_all_multiple_evidence_items_must_validate() -> None:
    analysis = create_analysis(
        create_evidence("Built a FastAPI backend using Python."),
        create_evidence("Fabricated project result."),
    )
    resume = create_resume("Built a FastAPI backend using Python.")

    with pytest.raises(EvidenceValidationError) as exc_info:
        validate_resume_evidence(analysis, resume)

    assert exc_info.value.code == EvidenceValidationErrorCode.EVIDENCE_NOT_FOUND


def test_none_criterion_requires_no_evidence_lookup() -> None:
    analysis = ResumeAnalysis(
        education={},
        criteria=[
            CriterionAnalysis(
                criterion_id="skills.python",
                match_type=AnalysisMatchType.NONE,
                evidence_level=0,
                evidence=[],
                rationale="ไม่พบหลักฐานที่เพียงพอในเรซูเม่",
            )
        ],
    )

    assert validate_resume_evidence(analysis, create_resume("Python")) is analysis


def test_successful_validation_does_not_mutate_analysis() -> None:
    analysis = create_analysis(create_evidence("Built a FastAPI backend using Python."))
    original_data = analysis.model_dump()

    validated = validate_resume_evidence(
        analysis,
        create_resume("Built a FastAPI backend using Python."),
    )

    assert validated is analysis
    assert analysis.model_dump() == original_data


def test_thai_unicode_evidence_is_preserved_and_validated() -> None:
    analysis = create_analysis(create_evidence("พัฒนา FastAPI ด้วย Python"))
    resume = create_resume("โครงการ: พัฒนา FastAPI ด้วย Python สำหรับระบบภายใน")

    assert validate_resume_evidence(analysis, resume) is analysis


def test_normalization_preserves_case_and_punctuation() -> None:
    assert normalize_evidence_text(" FastAPI\u00a0Backend\n") == "FastAPI Backend"
    assert normalize_evidence_text("Python.") != normalize_evidence_text("python")
