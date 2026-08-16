"""Opt-in live Gemini evaluation over synthetic resume documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.core.config import settings
from app.models.job_definition import JobDefinition
from app.models.resume_analysis import CriterionAnalysis, ResumeAnalysis
from app.models.resume_score import ResumeScore
from app.services.evidence_validation import (
    EvidenceValidationError,
    validate_resume_evidence,
)
from app.services.job_definition import load_job_definition
from app.services.llm_analysis import LlmAnalysisError, LlmErrorCode, analyze_resume
from app.services.scoring import ScoringError, score_resume_analysis
from evals.synthetic_cases import (
    SYNTHETIC_CASES,
    CriterionExpectation,
    SyntheticCase,
)


@dataclass
class LiveCaseResult:
    """Outcome with an explicit failure category for readable reporting."""

    case: SyntheticCase
    analysis: ResumeAnalysis | None = None
    score: ResumeScore | None = None
    failure_kind: str | None = None
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.failure_kind is None and not self.failures


def _criterion_by_id(
    analysis: ResumeAnalysis,
    criterion_id: str,
) -> CriterionAnalysis:
    return next(
        criterion
        for criterion in analysis.criteria
        if criterion.criterion_id == criterion_id
    )


def _contains_thai(text: str) -> bool:
    return any("\u0e00" <= character <= "\u0e7f" for character in text)


def _check_criterion_expectation(
    analysis: ResumeAnalysis,
    expectation: CriterionExpectation,
) -> list[str]:
    criterion = _criterion_by_id(analysis, expectation.criterion_id)
    failures: list[str] = []

    if criterion.match_type not in expectation.allowed_match_types:
        allowed = ", ".join(item.value for item in expectation.allowed_match_types)
        failures.append(
            f"{expectation.criterion_id} match_type was {criterion.match_type.value}; "
            f"expected one of: {allowed}"
        )
    if not (
        expectation.minimum_evidence_level
        <= criterion.evidence_level
        <= expectation.maximum_evidence_level
    ):
        failures.append(
            f"{expectation.criterion_id} evidence_level was "
            f"{criterion.evidence_level}; expected "
            f"{expectation.minimum_evidence_level}-"
            f"{expectation.maximum_evidence_level}"
        )

    if expectation.evidence_contains_any:
        evidence_text = " ".join(item.text for item in criterion.evidence).casefold()
        if not any(
            term.casefold() in evidence_text
            for term in expectation.evidence_contains_any
        ):
            failures.append(
                f"{expectation.criterion_id} evidence did not cite any expected term"
            )

    if expectation.evidence_pages:
        actual_pages = {item.page for item in criterion.evidence}
        expected_pages = set(expectation.evidence_pages)
        if not actual_pages or not actual_pages <= expected_pages:
            failures.append(
                f"{expectation.criterion_id} evidence pages were "
                f"{sorted(actual_pages)}; expected only {sorted(expected_pages)}"
            )

    return failures


def _check_semantic_expectations(
    case: SyntheticCase,
    analysis: ResumeAnalysis,
    score: ResumeScore,
) -> list[str]:
    failures: list[str] = []
    for expectation in case.expectations:
        failures.extend(_check_criterion_expectation(analysis, expectation))

    for field_name in case.missing_education_fields:
        value = getattr(analysis.education, field_name)
        if value not in (None, []):
            failures.append(f"education.{field_name} should remain missing")

    none_count = sum(
        criterion.match_type.value == "none" for criterion in analysis.criteria
    )
    if none_count < case.minimum_none_criteria:
        failures.append(
            f"only {none_count} criteria were none; expected at least "
            f"{case.minimum_none_criteria}"
        )

    if case.maximum_overall_score is not None and score.overall_score > Decimal(
        str(case.maximum_overall_score)
    ):
        failures.append(
            f"overall score {score.overall_score} exceeded "
            f"{case.maximum_overall_score}"
        )

    if case.require_thai_rationales and any(
        not _contains_thai(criterion.rationale) for criterion in analysis.criteria
    ):
        failures.append("one or more rationales did not contain Thai text")

    if (
        "score" in ResumeAnalysis.model_fields
        or "score" in CriterionAnalysis.model_fields
    ):
        failures.append("semantic analysis unexpectedly contains a score field")

    return failures


def _run_case(case: SyntheticCase, job: JobDefinition) -> LiveCaseResult:
    resume = case.to_resume_document()
    result = LiveCaseResult(case=case)

    try:
        analysis = analyze_resume(resume, job)
        result.analysis = analysis
    except LlmAnalysisError as exc:
        if exc.code == LlmErrorCode.LLM_NOT_CONFIGURED:
            result.failure_kind = "configuration failure"
        elif exc.code == LlmErrorCode.LLM_REQUEST_FAILED:
            result.failure_kind = "API failure"
        else:
            result.failure_kind = "schema/contract failure"
        result.failures.append(exc.code.value)
        return result

    try:
        validated_analysis = validate_resume_evidence(analysis, resume)
    except EvidenceValidationError as exc:
        result.failure_kind = "evidence validation failure"
        result.failures.append(exc.code.value)
        return result

    try:
        score = score_resume_analysis(validated_analysis, job)
        result.score = score
    except ScoringError as exc:
        result.failure_kind = "schema/contract failure"
        result.failures.append(exc.code.value)
        return result

    result.failures.extend(
        _check_semantic_expectations(case, validated_analysis, score)
    )
    if result.failures:
        result.failure_kind = "semantic expectation failure"
    return result


def _add_cross_case_expectations(results: list[LiveCaseResult]) -> None:
    by_id = {result.case.case_id: result for result in results}
    strong = by_id["strong_direct_match"]
    weak = by_id["weak_keyword_only"]

    if strong.score is None or weak.score is None:
        return
    if strong.score.overall_score <= weak.score.overall_score:
        strong.failure_kind = "semantic expectation failure"
        strong.failures.append(
            "strong direct-match score did not exceed weak keyword-only score"
        )


def _print_result(result: LiveCaseResult) -> None:
    marker = "PASS" if result.passed else "FAIL"
    print(f"[{marker}] {result.case.case_id}")
    print(f"  language: {result.case.language}")

    if result.score is not None:
        print(f"  overall score: {result.score.overall_score}")
        print("  evidence valid: yes")
    if result.analysis is not None:
        for expectation in result.case.expectations:
            criterion = _criterion_by_id(
                result.analysis,
                expectation.criterion_id,
            )
            print(
                f"  {criterion.criterion_id}: {criterion.match_type.value}, "
                f"evidence level {criterion.evidence_level}"
            )

    if not result.passed:
        print(f"  failure type: {result.failure_kind}")
        for failure in result.failures:
            print(f"  expectation failed: {failure}")


def _api_key_is_configured() -> bool:
    api_key = settings.gemini_api_key
    return api_key is not None and bool(api_key.get_secret_value().strip())


def main() -> int:
    """Run every synthetic case once with the configured Gemini model."""

    if not _api_key_is_configured():
        print("Live evaluation configuration failure: GEMINI_API_KEY is not set.")
        print("No live requests were made.")
        return 2

    job = load_job_definition()
    results = [_run_case(case, job) for case in SYNTHETIC_CASES]
    _add_cross_case_expectations(results)

    for result in results:
        _print_result(result)

    passed = sum(result.passed for result in results)
    failed = len(results) - passed
    print("\nLive evaluation")
    print(f"Model: {settings.gemini_model}")
    print(f"Cases: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
