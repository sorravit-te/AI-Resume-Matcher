"""Deterministic quote and page provenance validation for LLM evidence."""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_document import ResumeDocument


class EvidenceValidationErrorCode(StrEnum):
    """Stable failures exposed by evidence provenance validation."""

    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
    EVIDENCE_PAGE_NOT_FOUND = "EVIDENCE_PAGE_NOT_FOUND"


class EvidenceValidationError(ValueError):
    """A safe error for evidence that cannot be proven against the resume."""

    def __init__(
        self,
        code: EvidenceValidationErrorCode,
        message: str,
    ) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def normalize_evidence_text(text: str) -> str:
    """Normalize Unicode and whitespace without changing case or punctuation."""

    return " ".join(unicodedata.normalize("NFKC", text).split())


def validate_resume_evidence(
    analysis: ResumeAnalysis,
    resume: ResumeDocument,
) -> ResumeAnalysis:
    """Return *analysis* only when every claimed quote exists on its claimed page."""

    pages_by_number = {page.page_number: page for page in resume.pages}

    for criterion in analysis.criteria:
        for evidence in criterion.evidence:
            page = pages_by_number.get(evidence.page)
            if page is None:
                raise EvidenceValidationError(
                    EvidenceValidationErrorCode.EVIDENCE_PAGE_NOT_FOUND,
                    f"Evidence page {evidence.page} was not found for {criterion.criterion_id}.",
                )

            normalized_evidence = normalize_evidence_text(evidence.text)
            normalized_page_text = normalize_evidence_text(page.text)
            if not normalized_evidence or normalized_evidence not in normalized_page_text:
                raise EvidenceValidationError(
                    EvidenceValidationErrorCode.EVIDENCE_NOT_FOUND,
                    f"Evidence was not found on page {evidence.page} for {criterion.criterion_id}.",
                )

    return analysis
