"""Loading of the versioned EDVISORY job-definition source of truth."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.job_definition import JobDefinition

DEFAULT_JOB_DEFINITION_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "jobs"
    / "edvisory_ai_data_solution_intern.json"
)


def load_job_definition(path: Path | None = None) -> JobDefinition:
    """Read UTF-8 JSON from *path* and return a validated job definition."""

    definition_path = path or DEFAULT_JOB_DEFINITION_PATH
    with definition_path.open("r", encoding="utf-8") as definition_file:
        raw_definition = json.load(definition_file)

    return JobDefinition.model_validate(raw_definition)
