"""In-memory orchestration of the complete resume matching workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.job_definition import JobDefinition
from app.models.resume_match_result import ResumeMatchResult
from app.services.evidence_validation import validate_resume_evidence
from app.services.job_definition import load_job_definition
from app.services.llm_analysis import analyze_resume
from app.services.pdf_processing import process_resume_pdf
from app.services.scoring import score_resume_analysis

if TYPE_CHECKING:
    from google.genai import Client


def run_resume_matching(
    file_bytes: bytes,
    filename: str | None = None,
    *,
    job: JobDefinition | None = None,
    llm_client: Client | None = None,
) -> ResumeMatchResult:
    """Run every matching stage in order and return a privacy-limited result."""

    resolved_job = job if job is not None else load_job_definition()
    resume = process_resume_pdf(file_bytes, filename)
    analysis = analyze_resume(resume, resolved_job, client=llm_client)
    validated_analysis = validate_resume_evidence(analysis, resume)
    score = score_resume_analysis(validated_analysis, resolved_job)

    return ResumeMatchResult(
        candidate_name=validated_analysis.candidate_name,
        job_id=resolved_job.job_id,
        company=resolved_job.company,
        job_title=resolved_job.title,
        education=validated_analysis.education,
        score_name=score.score_name,
        overall_score=score.overall_score,
        maximum_score=score.maximum_score,
        category_scores=score.category_scores,
        criterion_scores=score.criterion_scores,
    )
