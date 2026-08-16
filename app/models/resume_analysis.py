"""Score-free structured output models for semantic resume analysis."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.job_definition import JobDefinition
from app.models.resume_document import ResumeDocument


class AnalysisModel(BaseModel):
    """Strict immutable base for data returned by the LLM."""

    model_config = ConfigDict(extra="forbid", frozen=True)


CandidateName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class EvidenceSourceType(StrEnum):
    EDUCATION = "education"
    COURSEWORK = "coursework"
    PROJECT = "project"
    WORK_EXPERIENCE = "work_experience"
    SKILLS = "skills"
    CERTIFICATION = "certification"
    OTHER = "other"


class AnalysisMatchType(StrEnum):
    DIRECT = "direct"
    EQUIVALENT = "equivalent"
    TRANSFERABLE = "transferable"
    ADJACENT = "adjacent"
    NONE = "none"


class ResumeEvidence(AnalysisModel):
    """A resume excerpt associated with its original PDF page."""

    text: str = Field(min_length=1)
    page: int = Field(ge=1)
    source_type: EvidenceSourceType


class CriterionAnalysis(AnalysisModel):
    """Semantic evidence judgment for one rubric criterion, without a score."""

    criterion_id: str = Field(min_length=1)
    match_type: AnalysisMatchType
    evidence_level: int = Field(ge=0, le=4)
    evidence: list[ResumeEvidence]
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_no_evidence_state(self) -> "CriterionAnalysis":
        if self.match_type == AnalysisMatchType.NONE:
            if self.evidence_level != 0 or self.evidence:
                raise ValueError("none matches require evidence_level 0 and no evidence")
        elif self.evidence_level == 0 or not self.evidence:
            raise ValueError("non-none matches require evidence and evidence_level 1 through 4")
        return self


class EducationMetadata(AnalysisModel):
    """Descriptive education fields extracted only when explicitly provided."""

    degree: str | None = None
    field_or_major: str | None = None
    faculty: str | None = None
    university: str | None = None
    gpa: str | None = None
    current_study_year: str | None = None
    expected_graduation: str | None = None
    coursework: list[str] = Field(default_factory=list)


class ResumeAnalysis(AnalysisModel):
    """Complete score-free analysis returned by the structured LLM call."""

    candidate_name: CandidateName | None = None
    education: EducationMetadata
    criteria: list[CriterionAnalysis] = Field(min_length=1)


class ResumeAnalysisContractError(ValueError):
    """The parsed output does not match the requested job or resume contract."""


def validate_resume_analysis(
    analysis: ResumeAnalysis,
    job: JobDefinition,
    resume: ResumeDocument,
) -> ResumeAnalysis:
    """Require exact criterion coverage and structurally valid evidence pages."""

    expected_ids = {criterion.id for criterion in job.criteria}
    received_ids = [criterion.criterion_id for criterion in analysis.criteria]

    if len(received_ids) != len(set(received_ids)):
        raise ResumeAnalysisContractError("analysis contains duplicate criterion IDs")

    unknown_ids = set(received_ids) - expected_ids
    if unknown_ids:
        raise ResumeAnalysisContractError(
            f"analysis contains unknown criterion IDs: {sorted(unknown_ids)}"
        )

    missing_ids = expected_ids - set(received_ids)
    if missing_ids:
        raise ResumeAnalysisContractError(
            f"analysis is missing criterion IDs: {sorted(missing_ids)}"
        )

    if len(received_ids) != len(expected_ids):
        raise ResumeAnalysisContractError("analysis must contain one result per criterion")

    for criterion in analysis.criteria:
        if any(evidence.page > resume.page_count for evidence in criterion.evidence):
            raise ResumeAnalysisContractError("evidence page is outside the resume page range")

    return analysis
