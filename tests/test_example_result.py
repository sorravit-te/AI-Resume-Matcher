"""Validation for the deterministic synthetic example API result."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

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
    }
    assert _all_keys(raw_result).isdisjoint(forbidden_fields)

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
