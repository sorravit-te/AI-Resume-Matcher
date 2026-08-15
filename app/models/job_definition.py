"""Typed models for machine-readable job definitions and scoring rubrics."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DefinitionModel(BaseModel):
    """Base model with consistent string handling for definition data."""

    model_config = ConfigDict(str_strip_whitespace=True)


class JobDescription(DefinitionModel):
    responsibilities: list[str] = Field(min_length=1)
    qualifications: list[str] = Field(min_length=1)


class ScoringSemantics(DefinitionModel):
    score_name: str = Field(min_length=1)
    meaning: str = Field(min_length=1)
    decision_support_only: bool
    does_not_represent: list[str] = Field(min_length=1)


class EducationAnalysis(DefinitionModel):
    relevant_evidence: list[str] = Field(min_length=1)
    descriptive_fields: list[str] = Field(min_length=1)
    non_scoring_fields: list[str] = Field(min_length=1)
    missing_data_policy: str = Field(min_length=1)


class RatingLevel(DefinitionModel):
    rating: int = Field(ge=0, le=4)
    description: str = Field(min_length=1)


class MatchType(DefinitionModel):
    id: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    max_rating: int = Field(ge=0, le=4)


class EvidencePolicy(DefinitionModel):
    allowed_source_types: list[str] = Field(min_length=1)
    project_evidence_types: list[str] = Field(min_length=1)
    projects_are_evidence_not_scoring_category: bool
    certifications_are_supporting_evidence: bool
    work_experience_is_required: bool
    missing_information_principles: list[str] = Field(min_length=1)
    future_analysis_statuses: list[str] = Field(min_length=1)
    non_scoring_signals: dict[str, str] = Field(min_length=1)
    inference_rules: list[str] = Field(min_length=1)


class Criterion(DefinitionModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    weight: float = Field(gt=0)
    priority: str = Field(min_length=1)
    jd_basis: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    positive_evidence_examples: list[str] = Field(min_length=1)
    weak_evidence_examples: list[str] = Field(min_length=1)
    do_not_infer: list[str] = Field(min_length=1)


class Category(DefinitionModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    criteria: list[Criterion] = Field(min_length=1)


class RubricValidationTargets(DefinitionModel):
    maximum_score: float = Field(gt=0)
    category_totals: dict[str, float] = Field(min_length=1)
    preferred_tools_total: float = Field(ge=0)


class JobDefinition(DefinitionModel):
    """Validated EDVISORY job definition and its future scoring contract."""

    EXPECTED_CATEGORY_TOTALS: ClassVar[dict[str, int]] = {
        "education": 10,
        "skills": 40,
        "knowledge": 25,
        "tools": 25,
    }
    EXPECTED_MAXIMUM_SCORE: ClassVar[int] = 100
    EXPECTED_PREFERRED_TOOLS_TOTAL: ClassVar[int] = 10
    expected_match_type_caps: ClassVar[dict[str, int]] = {
        "direct": 4,
        "equivalent": 4,
        "transferable": 3,
        "adjacent": 1,
        "none": 0,
    }
    expected_evidence_sources: ClassVar[set[str]] = {
        "education",
        "coursework",
        "project",
        "work_experience",
        "skills",
        "certification",
        "other",
    }
    expected_future_statuses: ClassVar[set[str]] = {
        "not_provided",
        "insufficient_evidence",
        "no_match",
    }
    prohibited_criterion_id_parts: ClassVar[set[str]] = {
        "gpa",
        "university",
        "faculty",
        "study_year",
        "expected_graduation",
        "relevant_projects",
        "interest",
    }

    schema_version: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    job_description: JobDescription
    scoring_semantics: ScoringSemantics
    education_analysis: EducationAnalysis
    rating_scale: list[RatingLevel] = Field(min_length=1)
    match_types: list[MatchType] = Field(min_length=1)
    evidence_policy: EvidencePolicy
    rubric_validation_targets: RubricValidationTargets
    categories: list[Category] = Field(min_length=1)

    @property
    def criteria(self) -> list[Criterion]:
        """Return every scoring criterion in category order."""

        return [criterion for category in self.categories for criterion in category.criteria]

    @property
    def category_weight_totals(self) -> dict[str, float]:
        """Calculate rubric totals directly from criterion weights."""

        return {
            category.id: sum(criterion.weight for criterion in category.criteria)
            for category in self.categories
        }

    @model_validator(mode="after")
    def validate_rubric_consistency(self) -> JobDefinition:
        """Validate cross-field rules that make the rubric safe to use later."""

        category_ids = [category.id for category in self.categories]
        if len(category_ids) != len(set(category_ids)):
            raise ValueError("category IDs must be unique")

        declared_totals = self.rubric_validation_targets.category_totals
        if set(category_ids) != set(declared_totals):
            raise ValueError("category totals must exist for every category exactly once")

        for category in self.categories:
            if any(criterion.category != category.id for criterion in category.criteria):
                raise ValueError("each criterion category must match its containing category")

        criteria = self.criteria
        criterion_ids = [criterion.id for criterion in criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("criterion IDs must be globally unique")

        if any(
            prohibited in criterion.id.lower()
            for criterion in criteria
            for prohibited in self.prohibited_criterion_id_parts
        ):
            raise ValueError("the rubric contains a prohibited scoring criterion")

        calculated_totals = self.category_weight_totals
        if calculated_totals != declared_totals:
            raise ValueError("criterion weights must equal the declared category totals")

        if declared_totals != self.EXPECTED_CATEGORY_TOTALS:
            raise ValueError("category totals must match the agreed EDVISORY rubric")

        if self.rubric_validation_targets.maximum_score != self.EXPECTED_MAXIMUM_SCORE:
            raise ValueError("maximum score must match the agreed EDVISORY rubric")

        if sum(calculated_totals.values()) != self.rubric_validation_targets.maximum_score:
            raise ValueError("category totals must equal the maximum score")

        preferred_tools_total = sum(
            criterion.weight
            for criterion in criteria
            if criterion.category == "tools" and criterion.priority == "preferred"
        )
        if preferred_tools_total != self.rubric_validation_targets.preferred_tools_total:
            raise ValueError("preferred tools weights must equal the declared preferred total")
        if (
            self.rubric_validation_targets.preferred_tools_total
            != self.EXPECTED_PREFERRED_TOOLS_TOTAL
        ):
            raise ValueError("preferred tools total must match the agreed EDVISORY rubric")

        ratings = [level.rating for level in self.rating_scale]
        if ratings != [0, 1, 2, 3, 4]:
            raise ValueError("rating scale must contain ratings 0 through 4 in order")

        match_type_caps = {match_type.id: match_type.max_rating for match_type in self.match_types}
        if len(match_type_caps) != len(self.match_types):
            raise ValueError("match type IDs must be unique")
        if match_type_caps != self.expected_match_type_caps:
            raise ValueError("match types and rating caps must match the agreed policy")

        if set(self.evidence_policy.allowed_source_types) != self.expected_evidence_sources:
            raise ValueError("allowed evidence source types must match the agreed policy")
        if set(self.evidence_policy.future_analysis_statuses) != self.expected_future_statuses:
            raise ValueError("future analysis statuses must match the agreed policy")
        if not self.evidence_policy.projects_are_evidence_not_scoring_category:
            raise ValueError("projects must remain evidence, not a scoring category")
        if not self.evidence_policy.certifications_are_supporting_evidence:
            raise ValueError("certifications must remain supporting evidence")
        if self.evidence_policy.work_experience_is_required:
            raise ValueError("work experience must not be required for this internship role")

        return self
