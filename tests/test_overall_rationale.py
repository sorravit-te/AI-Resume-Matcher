"""Deterministic tests for the overall score rationale service."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.job_definition import JobDefinition
from app.models.resume_analysis import (
    AnalysisMatchType,
    CriterionAnalysis,
    EvidenceSourceType,
    ResumeAnalysis,
    ResumeEvidence,
)
from app.models.resume_match_result import ResumeMatchResult
from app.services.job_definition import load_job_definition
from app.services.overall_rationale import build_overall_rationale
from app.services.scoring import score_resume_analysis


def _create_analysis(
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


def _score_and_rationale(
    job: JobDefinition,
    overrides: dict[str, tuple[AnalysisMatchType, int]] | None = None,
) -> tuple:
    analysis = _create_analysis(job, overrides)
    score = score_resume_analysis(analysis, job)
    rationale = build_overall_rationale(score, job)
    return score, rationale


# ---------------------------------------------------------------------------
# 1. ResumeMatchResult requires non-empty overall_rationale
# ---------------------------------------------------------------------------


def test_result_requires_non_empty_overall_rationale() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(job)
    # Valid construction succeeds
    result = ResumeMatchResult(
        job_id=job.job_id,
        company=job.company,
        job_title=job.title,
        education={},
        score_name=score.score_name,
        overall_score=score.overall_score,
        maximum_score=score.maximum_score,
        overall_rationale=rationale,
        category_scores=score.category_scores,
        criterion_scores=score.criterion_scores,
    )
    assert isinstance(result.overall_rationale, str)
    assert len(result.overall_rationale) > 0


def test_result_rejects_empty_overall_rationale() -> None:
    job = load_job_definition()
    score, _ = _score_and_rationale(job)
    with pytest.raises(ValidationError):
        ResumeMatchResult(
            job_id=job.job_id,
            company=job.company,
            job_title=job.title,
            education={},
            score_name=score.score_name,
            overall_score=score.overall_score,
            maximum_score=score.maximum_score,
            overall_rationale="",
            category_scores=score.category_scores,
            criterion_scores=score.criterion_scores,
        )


def test_result_rejects_whitespace_only_overall_rationale() -> None:
    job = load_job_definition()
    score, _ = _score_and_rationale(job)
    with pytest.raises(ValidationError):
        ResumeMatchResult(
            job_id=job.job_id,
            company=job.company,
            job_title=job.title,
            education={},
            score_name=score.score_name,
            overall_score=score.overall_score,
            maximum_score=score.maximum_score,
            overall_rationale="   \n\t  ",
            category_scores=score.category_scores,
            criterion_scores=score.criterion_scores,
        )


# ---------------------------------------------------------------------------
# 2. Category breakdown values are represented correctly
# ---------------------------------------------------------------------------


def test_category_breakdown_values_appear_in_rationale() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(
        job,
        {"skills.python": (AnalysisMatchType.DIRECT, 3)},
    )
    for cat_score in score.category_scores:
        display_name = next(
            (c.name for c in job.categories if c.id == cat_score.category),
            cat_score.category,
        )
        assert display_name in rationale

    assert score.score_name in rationale


# ---------------------------------------------------------------------------
# 3. Criterion names come from JobDefinition, not raw criterion IDs
# ---------------------------------------------------------------------------


def test_criterion_names_come_from_job_definition() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(
        job,
        {"skills.python": (AnalysisMatchType.DIRECT, 4)},
    )
    python_criterion = next(c for c in job.criteria if c.id == "skills.python")
    assert python_criterion.name in rationale
    assert python_criterion.id not in rationale


# ---------------------------------------------------------------------------
# 4. High-contribution criteria can appear as supporting criteria
# ---------------------------------------------------------------------------


def test_high_contribution_criteria_appear_as_supporting() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(
        job,
        {
            "skills.python": (AnalysisMatchType.DIRECT, 4),
            "tools.api": (AnalysisMatchType.DIRECT, 3),
        },
    )
    python_name = next(c.name for c in job.criteria if c.id == "skills.python")
    assert python_name in rationale
    assert "พบหลักฐานที่สนับสนุนคะแนนอย่างชัดเจน" in rationale


# ---------------------------------------------------------------------------
# 5. Zero-evidence criteria are described as insufficient evidence
# ---------------------------------------------------------------------------


def test_zero_evidence_described_as_insufficient() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(
        job,
        {"skills.python": (AnalysisMatchType.DIRECT, 4)},
    )
    assert "ยังไม่พบหลักฐานเพียงพอ" in rationale
    # Must NOT say the candidate lacks the skill
    assert "ไม่มีความสามารถ" not in rationale
    assert "ไม่เก่ง" not in rationale


# ---------------------------------------------------------------------------
# 6. Low-but-nonzero evidence is described as limited evidence
# ---------------------------------------------------------------------------


def test_low_evidence_described_as_limited() -> None:
    job = load_job_definition()
    # All perfect except one with rating 1 (limited evidence)
    overrides = {
        c.id: (AnalysisMatchType.DIRECT, 4) for c in job.criteria
    }
    first_id = job.criteria[0].id
    overrides[first_id] = (AnalysisMatchType.DIRECT, 1)

    score, rationale = _score_and_rationale(job, overrides)

    assert "หลักฐานในระดับจำกัด" in rationale
    assert "ยังไม่พบหลักฐานเพียงพอ" not in rationale


# ---------------------------------------------------------------------------
# 6.5. Effective rating 3 is NOT limited evidence
# ---------------------------------------------------------------------------


def test_effective_rating_three_is_not_limited_evidence() -> None:
    job = load_job_definition()
    # All perfect except one with rating 3 (which loses score, but is not "limited")
    overrides = {
        c.id: (AnalysisMatchType.DIRECT, 4) for c in job.criteria
    }
    first_id = job.criteria[0].id
    overrides[first_id] = (AnalysisMatchType.DIRECT, 3)

    score, rationale = _score_and_rationale(job, overrides)

    assert "หลักฐานในระดับจำกัด" not in rationale
    assert "ยังไม่พบหลักฐานเพียงพอ" not in rationale
    assert "เกณฑ์ที่มีคะแนนไม่เต็มยังมีหลักฐานสนับสนุนที่ชัดเจน แต่ยังไม่ถึงระดับสูงสุดตาม rubric" in rationale


# ---------------------------------------------------------------------------
# 7. Maximum number of highlighted supporting criteria is bounded
# ---------------------------------------------------------------------------


def test_supporting_criteria_bounded_to_three() -> None:
    job = load_job_definition()
    # Give many criteria high scores
    overrides = {
        criterion.id: (AnalysisMatchType.DIRECT, 4) for criterion in job.criteria
    }
    score, rationale = _score_and_rationale(job, overrides)
    # The supporting section should mention at most 3 criterion names
    supporting_marker = "พบหลักฐานที่สนับสนุนคะแนนอย่างชัดเจนใน "
    if supporting_marker in rationale:
        supporting_text = rationale.split(supporting_marker)[1].split(" โดย")[0].split(" ขณะ")[0].split(" คะแนนนี้")[0]
        # Count how many criterion names appear (they're joined by ", " and " และ ")
        parts = supporting_text.replace(" และ ", ", ").split(", ")
        assert len(parts) <= 3


# ---------------------------------------------------------------------------
# 8. Maximum number of highlighted limiting criteria is bounded
# ---------------------------------------------------------------------------


def test_limiting_criteria_bounded_to_three() -> None:
    job = load_job_definition()
    # All zero evidence -> many limiting criteria, but should be bounded
    score, rationale = _score_and_rationale(job)
    insufficient_marker = "ยังไม่พบหลักฐานเพียงพอ เช่น "
    if insufficient_marker in rationale:
        limiting_text = rationale.split(insufficient_marker)[1].split(" รวมถึง")[0].split(" คะแนนนี้")[0]
        parts = limiting_text.replace(" และ ", ", ").split(", ")
        assert len(parts) <= 3


# ---------------------------------------------------------------------------
# 9. Ordering is deterministic
# ---------------------------------------------------------------------------


def test_ordering_is_deterministic() -> None:
    job = load_job_definition()
    overrides = {
        "skills.python": (AnalysisMatchType.DIRECT, 4),
        "tools.api": (AnalysisMatchType.DIRECT, 3),
    }
    score1, rationale1 = _score_and_rationale(job, overrides)
    score2, rationale2 = _score_and_rationale(job, overrides)
    assert rationale1 == rationale2


# ---------------------------------------------------------------------------
# 10. No hiring/reject language or probability is introduced
# ---------------------------------------------------------------------------


def test_no_hiring_language_in_rationale() -> None:
    job = load_job_definition()
    for overrides in [
        None,
        {c.id: (AnalysisMatchType.DIRECT, 4) for c in job.criteria},
        {"skills.python": (AnalysisMatchType.DIRECT, 3)},
    ]:
        _, rationale = _score_and_rationale(job, overrides)
        forbidden_terms = [
            "expert", "excellent", "highly capable", "strong candidate",
            "outstanding", "มีศักยภาพสูง", "เชี่ยวชาญ", "เก่ง",
            "เหมาะสมที่จะรับเข้าทำงาน", "MATCH", "NOT MATCH",
            "hire", "reject", "probability",
        ]
        for term in forbidden_terms:
            assert term not in rationale, f"Forbidden term '{term}' found in rationale"


# ---------------------------------------------------------------------------
# 11. Perfect-score edge case
# ---------------------------------------------------------------------------


def test_perfect_score_edge_case() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(
        job,
        {c.id: (AnalysisMatchType.DIRECT, 4) for c in job.criteria},
    )
    assert score.overall_score == score.maximum_score
    # Should NOT say "limited" or "ไม่พบหลักฐานเพียงพอ"
    assert "ถูกจำกัด" not in rationale
    assert "ยังไม่พบหลักฐานเพียงพอ เช่น" not in rationale
    assert "ครบถ้วน" in rationale
    # Disclaimer must still be present
    assert "ไม่ใช่การตัดสินรับหรือไม่รับเข้าทำงาน" in rationale


# ---------------------------------------------------------------------------
# 12. Zero-score edge case
# ---------------------------------------------------------------------------


def test_zero_score_edge_case() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(job)
    assert score.overall_score == Decimal("0")
    assert "ยังไม่พบหลักฐานเพียงพอ" in rationale
    assert "ไม่ได้หมายความว่าผู้สมัครไม่มีความสามารถ" in rationale
    assert "ไม่ใช่การตัดสินรับหรือไม่รับเข้าทำงาน" in rationale


# ---------------------------------------------------------------------------
# 13. Result pipeline includes overall_rationale
# (tested implicitly by pipeline tests, but explicit coverage here)
# ---------------------------------------------------------------------------


def test_result_pipeline_integration() -> None:
    job = load_job_definition()
    analysis = _create_analysis(
        job,
        {"skills.python": (AnalysisMatchType.DIRECT, 4)},
    )
    score = score_resume_analysis(analysis, job)
    rationale = build_overall_rationale(score, job)
    result = ResumeMatchResult(
        job_id=job.job_id,
        company=job.company,
        job_title=job.title,
        education={},
        score_name=score.score_name,
        overall_score=score.overall_score,
        maximum_score=score.maximum_score,
        overall_rationale=rationale,
        category_scores=score.category_scores,
        criterion_scores=score.criterion_scores,
    )
    assert result.overall_rationale == rationale
    assert len(result.overall_rationale) > 0


# ---------------------------------------------------------------------------
# 14. API JSON includes overall_rationale
# ---------------------------------------------------------------------------


def test_api_json_includes_overall_rationale() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(job)
    result = ResumeMatchResult(
        job_id=job.job_id,
        company=job.company,
        job_title=job.title,
        education={},
        score_name=score.score_name,
        overall_score=score.overall_score,
        maximum_score=score.maximum_score,
        overall_rationale=rationale,
        category_scores=score.category_scores,
        criterion_scores=score.criterion_scores,
    )
    import json
    serialized = json.loads(result.model_dump_json())
    assert "overall_rationale" in serialized
    assert isinstance(serialized["overall_rationale"], str)
    assert len(serialized["overall_rationale"]) > 0


# ---------------------------------------------------------------------------
# 15. Web UI accepts and renders overall_rationale
# (tested via static assertions on app.js)
# ---------------------------------------------------------------------------


def test_web_ui_references_overall_rationale() -> None:
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    js_response = client.get("/static/app.js")
    assert js_response.status_code == 200
    assert "overall_rationale" in js_response.text
    assert "overallRationaleText" in js_response.text
    assert "overallRationaleSection" in js_response.text
    assert "overall-rationale-text" in js_response.text

    html_response = client.get("/")
    assert html_response.status_code == 200
    assert 'id="overall-rationale-section"' in html_response.text
    assert 'id="overall-rationale-text"' in html_response.text
    assert "Overall Analysis" in html_response.text


# ---------------------------------------------------------------------------
# 16. Downloaded JSON retains overall_rationale
# ---------------------------------------------------------------------------


def test_downloaded_json_retains_overall_rationale() -> None:
    job = load_job_definition()
    score, rationale = _score_and_rationale(
        job,
        {"skills.python": (AnalysisMatchType.DIRECT, 3)},
    )
    result = ResumeMatchResult(
        job_id=job.job_id,
        company=job.company,
        job_title=job.title,
        education={},
        score_name=score.score_name,
        overall_score=score.overall_score,
        maximum_score=score.maximum_score,
        overall_rationale=rationale,
        category_scores=score.category_scores,
        criterion_scores=score.criterion_scores,
    )
    import json
    # Simulate the download flow: JSON.stringify(latestResult, null, 2)
    serialized = json.dumps(result.model_dump(mode="json"), indent=2)
    parsed = json.loads(serialized)
    assert "overall_rationale" in parsed
    assert parsed["overall_rationale"] == rationale


# ---------------------------------------------------------------------------
# Edge case: no criteria with effective_rating >= 3
# ---------------------------------------------------------------------------


def test_no_high_rating_criteria_produces_appropriate_text() -> None:
    job = load_job_definition()
    # Give all criteria low evidence levels (1-2) but not zero
    overrides = {
        c.id: (AnalysisMatchType.DIRECT, 2) for c in job.criteria
    }
    score, rationale = _score_and_rationale(job, overrides)
    assert "ยังไม่มีเกณฑ์ที่มี effective rating ตั้งแต่ 3 ขึ้นไป" in rationale


# ---------------------------------------------------------------------------
# Disclaimer is always present
# ---------------------------------------------------------------------------


def test_disclaimer_always_present() -> None:
    job = load_job_definition()
    for overrides in [
        None,
        {c.id: (AnalysisMatchType.DIRECT, 4) for c in job.criteria},
        {"skills.python": (AnalysisMatchType.DIRECT, 3)},
    ]:
        _, rationale = _score_and_rationale(job, overrides)
        assert "ไม่ใช่การตัดสินรับหรือไม่รับเข้าทำงาน" in rationale
