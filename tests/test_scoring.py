"""Deterministic tests for JD Match Score calculation."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.models.job_definition import JobDefinition
from app.models.resume_analysis import (
    AnalysisMatchType,
    CriterionAnalysis,
    EvidenceSourceType,
    ResumeAnalysis,
    ResumeEvidence,
)
from app.services.job_definition import load_job_definition
from app.services.scoring import ScoringError, ScoringErrorCode, score_resume_analysis


def create_analysis(
    job: JobDefinition,
    overrides: dict[str, tuple[AnalysisMatchType, int]] | None = None,
) -> ResumeAnalysis:
    overrides = overrides or {}
    criteria = []
    for rubric_criterion in job.criteria:
        match_type, evidence_level = overrides.get(
            rubric_criterion.id,
            (AnalysisMatchType.NONE, 0),
        )
        evidence = (
            []
            if match_type == AnalysisMatchType.NONE
            else [
                ResumeEvidence(
                    text="Synthetic evidence",
                    page=1,
                    source_type=EvidenceSourceType.PROJECT,
                )
            ]
        )
        criteria.append(
            CriterionAnalysis(
                criterion_id=rubric_criterion.id,
                match_type=match_type,
                evidence_level=evidence_level,
                evidence=evidence,
                rationale="เหตุผลสำหรับการทดสอบ",
            )
        )

    return ResumeAnalysis(education={}, criteria=criteria)


def criterion_score_by_id(score, criterion_id: str):
    return next(item for item in score.criterion_scores if item.criterion_id == criterion_id)


def category_score_by_id(score, category_id: str):
    return next(item for item in score.category_scores if item.category == category_id)


def test_all_direct_level_four_reaches_authoritative_maximums() -> None:
    job = load_job_definition()
    analysis = create_analysis(
        job,
        {criterion.id: (AnalysisMatchType.DIRECT, 4) for criterion in job.criteria},
    )

    score = score_resume_analysis(analysis, job)

    assert [item.max_score for item in score.category_scores] == [
        Decimal("10.0"),
        Decimal("40.0"),
        Decimal("25.0"),
        Decimal("25.0"),
    ]
    assert [item.score for item in score.category_scores] == [
        Decimal("10.0"),
        Decimal("40.0"),
        Decimal("25.0"),
        Decimal("25.0"),
    ]
    assert score.overall_score == Decimal("100.0")
    assert score.maximum_score == Decimal("100.0")
    assert score.score_name == "JD Match Score"


def test_all_none_analysis_scores_zero() -> None:
    score = score_resume_analysis(create_analysis(load_job_definition()), load_job_definition())

    assert score.overall_score == Decimal("0")
    assert all(item.score == Decimal("0") for item in score.criterion_scores)


def test_direct_scoring_uses_the_criterion_weight() -> None:
    job = load_job_definition()
    score = score_resume_analysis(
        create_analysis(job, {"skills.python": (AnalysisMatchType.DIRECT, 3)}),
        job,
    )
    python_score = criterion_score_by_id(score, "skills.python")

    assert python_score.weight == Decimal("10.0")
    assert python_score.match_cap == 4
    assert python_score.effective_rating == 3
    assert python_score.score == Decimal("7.5")


def test_equivalent_evidence_can_reach_rating_four() -> None:
    job = load_job_definition()
    score = score_resume_analysis(
        create_analysis(job, {"skills.python": (AnalysisMatchType.EQUIVALENT, 4)}),
        job,
    )

    python_score = criterion_score_by_id(score, "skills.python")
    assert python_score.match_cap == 4
    assert python_score.effective_rating == 4
    assert python_score.score == Decimal("10.0")


def test_transferable_and_adjacent_caps_preserve_fractional_precision() -> None:
    job = load_job_definition()
    score = score_resume_analysis(
        create_analysis(
            job,
            {
                "tools.n8n": (AnalysisMatchType.TRANSFERABLE, 4),
                "tools.sql": (AnalysisMatchType.ADJACENT, 4),
            },
        ),
        job,
    )

    transferable = criterion_score_by_id(score, "tools.n8n")
    adjacent = criterion_score_by_id(score, "tools.sql")
    assert (transferable.match_cap, transferable.effective_rating, transferable.score) == (
        3,
        3,
        Decimal("1.875"),
    )
    assert (adjacent.match_cap, adjacent.effective_rating, adjacent.score) == (
        1,
        1,
        Decimal("0.625"),
    )


def test_fractional_scores_serialize_as_exact_json_numbers() -> None:
    job = load_job_definition()
    score = score_resume_analysis(
        create_analysis(
            job,
            {
                "tools.n8n": (AnalysisMatchType.TRANSFERABLE, 4),
                "tools.sql": (AnalysisMatchType.ADJACENT, 4),
            },
        ),
        job,
    )

    serialized_json = score.model_dump_json()
    serialized_scores = {
        item["criterion_id"]: item["score"]
        for item in json.loads(serialized_json)["criterion_scores"]
    }

    assert type(serialized_scores["tools.n8n"]) is float
    assert type(serialized_scores["tools.sql"]) is float
    assert serialized_scores["tools.n8n"] == 1.875
    assert serialized_scores["tools.sql"] == 0.625
    assert "1.874999" not in serialized_json
    assert "0.624999" not in serialized_json


def test_none_always_has_zero_cap_rating_and_score() -> None:
    score = score_resume_analysis(create_analysis(load_job_definition()), load_job_definition())
    none_score = criterion_score_by_id(score, "tools.n8n")

    assert (none_score.match_cap, none_score.effective_rating, none_score.score) == (
        0,
        0,
        Decimal("0"),
    )


def test_category_and_overall_scores_are_aggregated_from_criterion_scores() -> None:
    job = load_job_definition()
    score = score_resume_analysis(
        create_analysis(
            job,
            {
                "skills.python": (AnalysisMatchType.DIRECT, 3),
                "tools.n8n": (AnalysisMatchType.TRANSFERABLE, 4),
            },
        ),
        job,
    )

    for category_score in score.category_scores:
        criterion_total = sum(
            (
                item.score
                for item in score.criterion_scores
                if item.category == category_score.category
            ),
            Decimal("0"),
        )
        assert category_score.score == criterion_total

    assert score.overall_score == sum(
        (item.score for item in score.category_scores),
        Decimal("0"),
    )
    assert score.overall_score == sum(
        (item.score for item in score.criterion_scores),
        Decimal("0"),
    )
    assert category_score_by_id(score, "skills").score == Decimal("7.5")
    assert category_score_by_id(score, "tools").score == Decimal("1.875")


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown"])
def test_malformed_analysis_is_not_partially_scored(mutation: str) -> None:
    job = load_job_definition()
    analysis = create_analysis(job)

    if mutation == "missing":
        malformed_analysis = analysis.model_copy(update={"criteria": analysis.criteria[:-1]})
    elif mutation == "duplicate":
        malformed_analysis = analysis.model_copy(
            update={"criteria": analysis.criteria + [analysis.criteria[0]]}
        )
    else:
        unknown_criterion = analysis.criteria[0].model_copy(
            update={"criterion_id": "unknown.criterion"}
        )
        malformed_analysis = analysis.model_copy(
            update={"criteria": [unknown_criterion, *analysis.criteria[1:]]}
        )

    with pytest.raises(ScoringError) as exc_info:
        score_resume_analysis(malformed_analysis, job)

    assert exc_info.value.code == ScoringErrorCode.SCORING_CONTRACT_INVALID


def test_scoring_does_not_mutate_the_analysis_or_add_score_fields() -> None:
    job = load_job_definition()
    analysis = create_analysis(job, {"skills.python": (AnalysisMatchType.DIRECT, 3)})
    original_data = analysis.model_dump()

    score_resume_analysis(analysis, job)

    assert analysis.model_dump() == original_data
    assert "score" not in ResumeAnalysis.model_fields
