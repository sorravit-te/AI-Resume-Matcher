"""Tests for the EDVISORY job-definition source of truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.job_definition import DEFAULT_JOB_DEFINITION_PATH, load_job_definition


def write_definition(tmp_path: Path, definition_data: dict[str, Any]) -> Path:
    """Write a temporary definition fixture and return its path."""

    invalid_definition_path = tmp_path / "invalid_definition.json"
    invalid_definition_path.write_text(
        json.dumps(definition_data),
        encoding="utf-8",
    )
    return invalid_definition_path


def find_criterion(definition_data: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    """Return a mutable criterion fixture by its stable source-of-truth ID."""

    categories = definition_data["categories"]
    for category in categories:
        for criterion in category["criteria"]:
            if criterion["id"] == criterion_id:
                return criterion
    raise AssertionError(f"Missing criterion fixture: {criterion_id}")


def test_official_edvisory_definition_loads_with_expected_totals() -> None:
    job = load_job_definition()

    assert job.job_id == "edvisory_ai_data_solution_intern"
    assert job.category_weight_totals == {
        "education": 10,
        "skills": 40,
        "knowledge": 25,
        "tools": 25,
    }
    assert sum(job.category_weight_totals.values()) == 100


def test_criteria_are_unique_and_rating_scale_is_complete() -> None:
    job = load_job_definition()

    criterion_ids = [criterion.id for criterion in job.criteria]
    assert len(criterion_ids) == len(set(criterion_ids))
    assert [level.rating for level in job.rating_scale] == [0, 1, 2, 3, 4]


def test_match_types_and_caps_follow_the_agreed_policy() -> None:
    job = load_job_definition()

    assert {match_type.id: match_type.max_rating for match_type in job.match_types} == {
        "direct": 4,
        "equivalent": 4,
        "transferable": 3,
        "adjacent": 1,
        "none": 0,
    }


def test_loader_rejects_inconsistent_category_total(tmp_path) -> None:
    definition_data = json.loads(DEFAULT_JOB_DEFINITION_PATH.read_text(encoding="utf-8"))
    definition_data["rubric_validation_targets"]["category_totals"]["skills"] = 39

    with pytest.raises(ValidationError, match="criterion weights"):
        load_job_definition(write_definition(tmp_path, definition_data))


def test_loader_rejects_consistent_but_incorrect_skills_total(tmp_path) -> None:
    definition_data = json.loads(DEFAULT_JOB_DEFINITION_PATH.read_text(encoding="utf-8"))
    find_criterion(definition_data, "skills.testing_evaluation")["weight"] = 2
    definition_data["rubric_validation_targets"]["category_totals"]["skills"] = 39
    definition_data["rubric_validation_targets"]["maximum_score"] = 99

    with pytest.raises(ValidationError, match="category totals must match"):
        load_job_definition(write_definition(tmp_path, definition_data))


def test_loader_rejects_nonstandard_maximum_score(tmp_path) -> None:
    definition_data = json.loads(DEFAULT_JOB_DEFINITION_PATH.read_text(encoding="utf-8"))
    definition_data["rubric_validation_targets"]["maximum_score"] = 99

    with pytest.raises(ValidationError, match="maximum score must match"):
        load_job_definition(write_definition(tmp_path, definition_data))


def test_loader_rejects_consistent_but_incorrect_preferred_tools_total(tmp_path) -> None:
    definition_data = json.loads(DEFAULT_JOB_DEFINITION_PATH.read_text(encoding="utf-8"))
    find_criterion(definition_data, "tools.n8n")["weight"] = 2
    find_criterion(definition_data, "tools.api")["weight"] = 6.5
    definition_data["rubric_validation_targets"]["preferred_tools_total"] = 9.5

    with pytest.raises(ValidationError, match="preferred tools total must match"):
        load_job_definition(write_definition(tmp_path, definition_data))


def test_rating_scale_includes_strict_evidence_boundaries() -> None:
    job = load_job_definition()
    descriptions = [level.description for level in job.rating_scale]

    assert "No supporting evidence" in descriptions[0]
    assert "Mention only" in descriptions[1]
    assert "Limited practical evidence" in descriptions[2]
    assert "Clear hands-on evidence" in descriptions[3]
    assert "Strong demonstrated evidence" in descriptions[4]
    assert "Do not assign Level 4 merely because the evidence contains numbers" in descriptions[4]


def test_context_engineering_includes_strict_guidance() -> None:
    job = load_job_definition()
    context_eng = next(c for c in job.criteria if c.id == "skills.context_engineering")

    do_not_infer = context_eng.do_not_infer
    assert "sending document text/data to an LLM" in do_not_infer
    assert "OCR followed by LLM processing" in do_not_infer

    positive_examples = context_eng.positive_evidence_examples
    assert "context construction" in positive_examples
    assert "context selection" in positive_examples
    assert "RAG or retrieved context" not in positive_examples
    assert "RAG implemented with explicit context selection, preparation, or assembly" in positive_examples


def test_json_structured_data_includes_csv_clarification() -> None:
    job = load_job_definition()
    json_crit = next(c for c in job.criteria if c.id == "tools.json_structured_data")
    assert any("is direct evidence of the Structured Data portion" in ex for ex in json_crit.positive_evidence_examples)
    assert any("CSV" in rule for rule in json_crit.do_not_infer)
    assert any("Do not downgrade demonstrated structured-data work to equivalent" in rule for rule in json_crit.do_not_infer)
    assert any("unless JSON is actually supported" in rule for rule in json_crit.do_not_infer)


def test_sql_includes_strict_level_boundary() -> None:
    job = load_job_definition()
    sql_crit = next(c for c in job.criteria if c.id == "tools.sql")
    assert any("appearing only in a skills list" in ex for ex in sql_crit.weak_evidence_examples)
    assert any("Listing several related database technologies does not turn mention-only" in rule for rule in sql_crit.do_not_infer)

def test_cloud_includes_strict_level_boundary() -> None:
    job = load_job_definition()
    cloud_crit = next(c for c in job.criteria if c.id == "tools.cloud")
    assert any("Level 3 requires explicit cloud deployment/infrastructure/configuration/architecture responsibility" in ex for ex in cloud_crit.positive_evidence_examples)
    assert any("choose Level 2 rather than Level 3" in rule for rule in cloud_crit.do_not_infer)

def test_analytical_problem_solving_includes_strict_level_boundary() -> None:
    job = load_job_definition()
    aps_crit = next(c for c in job.criteria if c.id == "skills.analytical_problem_solving")
    assert any("Level 4: explicitly exceptional analytical depth" in ex for ex in aps_crit.positive_evidence_examples)
    assert any("alone are not enough for Level 4" in rule for rule in aps_crit.do_not_infer)
    assert any("must not be combined to manufacture Level 4" in rule for rule in aps_crit.do_not_infer)
    assert any("choose Level 3" in rule for rule in aps_crit.do_not_infer)
