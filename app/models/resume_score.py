"""Immutable, deterministic scoring results for a validated resume analysis."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.models.resume_analysis import AnalysisMatchType, ResumeEvidence


JsonDecimal = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float, when_used="json"),
]


class ScoreModel(BaseModel):
    """Strict immutable result base for deterministic scoring output."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CriterionScore(ScoreModel):
    """The deterministic score and source analysis for one rubric criterion."""

    criterion_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    weight: JsonDecimal = Field(gt=0)
    match_type: AnalysisMatchType
    evidence_level: int = Field(ge=0, le=4)
    match_cap: int = Field(ge=0, le=4)
    effective_rating: int = Field(ge=0, le=4)
    score: JsonDecimal = Field(ge=0)
    max_score: JsonDecimal = Field(gt=0)
    evidence: list[ResumeEvidence]
    rationale: str = Field(min_length=1)


class CategoryScore(ScoreModel):
    """Aggregate deterministic score for one rubric category."""

    category: str = Field(min_length=1)
    score: JsonDecimal = Field(ge=0)
    max_score: JsonDecimal = Field(gt=0)


class ResumeScore(ScoreModel):
    """Complete deterministic JD Match Score output without recommendations."""

    score_name: str = Field(min_length=1)
    criterion_scores: list[CriterionScore] = Field(min_length=1)
    category_scores: list[CategoryScore] = Field(min_length=1)
    overall_score: JsonDecimal = Field(ge=0)
    maximum_score: JsonDecimal = Field(gt=0)
