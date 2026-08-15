"""Deterministic JD Match Score calculation from validated analysis and rubric data."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from app.models.job_definition import Criterion, JobDefinition
from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_score import CategoryScore, CriterionScore, ResumeScore


class ScoringErrorCode(StrEnum):
    """Stable failures for invalid scoring inputs."""

    SCORING_CONTRACT_INVALID = "SCORING_CONTRACT_INVALID"


class ScoringError(ValueError):
    """A safe deterministic error that never includes resume content."""

    def __init__(self, message: str) -> None:
        self.code = ScoringErrorCode.SCORING_CONTRACT_INVALID
        self.message = message
        super().__init__(message)


def score_resume_analysis(analysis: ResumeAnalysis, job: JobDefinition) -> ResumeScore:
    """Calculate the JD Match Score entirely from analysis judgments and the rubric."""

    criteria_by_id = _criteria_by_id(job)
    match_caps = _match_caps(job)
    _validate_analysis_coverage(analysis, criteria_by_id, match_caps)

    category_maximums = {
        category_id: Decimal(str(maximum))
        for category_id, maximum in job.rubric_validation_targets.category_totals.items()
    }
    category_scores = {category_id: Decimal("0") for category_id in category_maximums}
    criterion_scores: list[CriterionScore] = []

    for analysis_criterion in analysis.criteria:
        rubric_criterion = criteria_by_id[analysis_criterion.criterion_id]
        category = rubric_criterion.category
        if category not in category_scores:
            raise ScoringError(f"Unknown rubric category for {rubric_criterion.id}.")

        weight = Decimal(str(rubric_criterion.weight))
        match_cap = match_caps[analysis_criterion.match_type.value]
        effective_rating = min(analysis_criterion.evidence_level, match_cap)
        score = weight * Decimal(effective_rating) / Decimal("4")
        category_scores[category] += score

        criterion_scores.append(
            CriterionScore(
                criterion_id=rubric_criterion.id,
                category=category,
                weight=weight,
                match_type=analysis_criterion.match_type,
                evidence_level=analysis_criterion.evidence_level,
                match_cap=match_cap,
                effective_rating=effective_rating,
                score=score,
                max_score=weight,
                evidence=analysis_criterion.evidence,
                rationale=analysis_criterion.rationale,
            )
        )

    calculated_overall_score = sum(category_scores.values(), Decimal("0"))
    maximum_score = Decimal(str(job.rubric_validation_targets.maximum_score))
    if calculated_overall_score > maximum_score:
        raise ScoringError("Calculated score exceeds the rubric maximum.")

    return ResumeScore(
        score_name=job.scoring_semantics.score_name,
        criterion_scores=criterion_scores,
        category_scores=[
            CategoryScore(
                category=category.id,
                score=category_scores[category.id],
                max_score=category_maximums[category.id],
            )
            for category in job.categories
        ],
        overall_score=calculated_overall_score,
        maximum_score=maximum_score,
    )


def _criteria_by_id(job: JobDefinition) -> dict[str, Criterion]:
    criteria_by_id = {criterion.id: criterion for criterion in job.criteria}
    if len(criteria_by_id) != len(job.criteria):
        raise ScoringError("Rubric contains duplicate criterion IDs.")
    return criteria_by_id


def _match_caps(job: JobDefinition) -> dict[str, int]:
    match_caps = {match_type.id: match_type.max_rating for match_type in job.match_types}
    if len(match_caps) != len(job.match_types):
        raise ScoringError("Rubric contains duplicate match types.")
    return match_caps


def _validate_analysis_coverage(
    analysis: ResumeAnalysis,
    criteria_by_id: dict[str, Criterion],
    match_caps: dict[str, int],
) -> None:
    analysis_ids = [criterion.criterion_id for criterion in analysis.criteria]
    if len(analysis_ids) != len(set(analysis_ids)):
        raise ScoringError("Analysis contains duplicate criterion IDs.")

    unknown_ids = set(analysis_ids) - set(criteria_by_id)
    if unknown_ids:
        raise ScoringError("Analysis contains unknown criterion IDs.")

    missing_ids = set(criteria_by_id) - set(analysis_ids)
    if missing_ids:
        raise ScoringError("Analysis is missing criterion IDs.")

    if any(criterion.match_type.value not in match_caps for criterion in analysis.criteria):
        raise ScoringError("Analysis contains a match type missing from the rubric.")
