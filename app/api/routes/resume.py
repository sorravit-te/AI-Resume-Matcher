"""HTTP boundary for the in-memory resume matching pipeline."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from starlette.concurrency import run_in_threadpool

from app.models.resume_match_result import ResumeMatchResult
from app.services.resume_pipeline import run_resume_matching

router = APIRouter(prefix="/api/v1", tags=["resume matching"])


@router.post(
    "/resume-match",
    response_model=ResumeMatchResult,
    summary="Match a resume to the EDVISORY internship",
    description="Analyze one text-based PDF resume and return its JD Match Score.",
)
async def match_resume(
    resume: Annotated[UploadFile, File(description="Text-based PDF resume")],
) -> ResumeMatchResult:
    """Read an upload in memory and run the synchronous pipeline off the event loop."""

    file_bytes = await resume.read()
    return await run_in_threadpool(
        run_resume_matching,
        file_bytes,
        resume.filename,
    )
