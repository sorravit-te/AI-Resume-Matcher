"""Privacy-limited result returned by the resume matching pipeline."""

from __future__ import annotations

from pydantic import Field

from app.models.resume_analysis import EducationMetadata
from app.models.resume_score import (
    CategoryScore,
    CriterionScore,
    JsonDecimal,
    ScoreModel,
)


class ResumeMatchResult(ScoreModel):
    """Final JD Match Score without raw resume or provider internals."""

    job_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    job_title: str = Field(min_length=1)
    education: EducationMetadata
    score_name: str = Field(min_length=1)
    overall_score: JsonDecimal = Field(ge=0)
    maximum_score: JsonDecimal = Field(gt=0)
    category_scores: list[CategoryScore] = Field(min_length=1)
    criterion_scores: list[CriterionScore] = Field(min_length=1)
