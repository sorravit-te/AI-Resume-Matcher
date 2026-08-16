"""Validation for the deterministic synthetic example API result."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.resume_match_result import ResumeMatchResult
from examples.generate_example_result import build_example_result

EXAMPLE_RESULT_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "example_result.json"
)


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested_key
            for nested_value in value.values()
            for nested_key in _all_keys(nested_value)
        }
    if isinstance(value, list):
        return {
            nested_key
            for nested_value in value
            for nested_key in _all_keys(nested_value)
        }
    return set()


def test_example_result_matches_production_model_and_scoring() -> None:
    raw_result = json.loads(EXAMPLE_RESULT_PATH.read_text(encoding="utf-8"))
    result = ResumeMatchResult.model_validate(raw_result)

    assert result == build_example_result()
    assert result.candidate_name == "Synthetic Candidate"
    assert result.score_name == "JD Match Score"
    assert result.maximum_score == Decimal("100")
    assert {
        category.category: category.max_score for category in result.category_scores
    } == {
        "education": Decimal("10"),
        "skills": Decimal("40"),
        "knowledge": Decimal("25"),
        "tools": Decimal("25"),
    }
    assert result.overall_score == sum(
        (category.score for category in result.category_scores),
        Decimal("0"),
    )
    assert result.overall_score == sum(
        (criterion.score for criterion in result.criterion_scores),
        Decimal("0"),
    )
    assert {criterion.match_type.value for criterion in result.criterion_scores} == {
        "direct",
        "equivalent",
        "transferable",
        "adjacent",
        "none",
    }

    forbidden_fields = {
        "full_text",
        "pages",
        "file_bytes",
        "hire",
        "reject",
        "recommendation",
        "email",
        "phone",
        "phone_number",
        "address",
        "age",
        "gender",
        "nationality",
        "photo",
        "photo_metadata",
    }
    assert _all_keys(raw_result).isdisjoint(forbidden_fields)
    assert "candidate_name" in raw_result

    score_values = [raw_result["overall_score"], raw_result["maximum_score"]]
    score_values.extend(
        value
        for category in raw_result["category_scores"]
        for value in (category["score"], category["max_score"])
    )
    score_values.extend(
        value
        for criterion in raw_result["criterion_scores"]
        for value in (
            criterion["weight"],
            criterion["score"],
            criterion["max_score"],
        )
    )
    assert all(type(value) in (int, float) for value in score_values)


@pytest.mark.parametrize(
    ("candidate_name", "expected_name"),
    [
        (None, None),
        ("Synthetic Candidate", "Synthetic Candidate"),
        ("  Synthetic Candidate  ", "Synthetic Candidate"),
    ],
)
def test_result_candidate_name_accepts_null_and_strips_surrounding_whitespace(
    candidate_name: str | None,
    expected_name: str | None,
) -> None:
    raw_result = json.loads(EXAMPLE_RESULT_PATH.read_text(encoding="utf-8"))
    raw_result["candidate_name"] = candidate_name

    result = ResumeMatchResult.model_validate(raw_result)

    assert result.candidate_name == expected_name


@pytest.mark.parametrize("candidate_name", ["", "   \t\r\n"])
def test_result_candidate_name_rejects_empty_or_whitespace_only(
    candidate_name: str,
) -> None:
    raw_result = json.loads(EXAMPLE_RESULT_PATH.read_text(encoding="utf-8"))
    raw_result["candidate_name"] = candidate_name

    with pytest.raises(ValidationError):
        ResumeMatchResult.model_validate(raw_result)
