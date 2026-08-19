"""Gemini-backed structured semantic analysis of extracted resume evidence."""

from __future__ import annotations

import json
import time
from enum import StrEnum
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.core.config import settings
from app.models.job_definition import JobDefinition
from app.models.resume_analysis import (
    ResumeAnalysis,
    ResumeAnalysisContractError,
    validate_resume_analysis,
)
from app.models.resume_document import ResumeDocument
from app.prompts.resume_analysis import ResumeAnalysisPrompt, build_resume_analysis_prompt


class LlmErrorCode(StrEnum):
    """Stable failures exposed by the LLM application boundary."""

    LLM_NOT_CONFIGURED = "LLM_NOT_CONFIGURED"
    LLM_REQUEST_FAILED = "LLM_REQUEST_FAILED"
    LLM_INVALID_RESPONSE = "LLM_INVALID_RESPONSE"


class LlmAnalysisError(RuntimeError):
    """A safe LLM-analysis failure that does not expose provider details."""

    def __init__(self, code: LlmErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def analyze_resume(
    resume: ResumeDocument,
    job: JobDefinition,
    *,
    client: genai.Client | None = None,
    metrics: dict[str, float] | None = None,
) -> ResumeAnalysis:
    """Request structured evidence analysis and validate it against local inputs."""

    t0 = time.perf_counter()
    prompt = build_resume_analysis_prompt(job, resume)
    if metrics is not None:
        metrics["prompt_build_ms"] = (time.perf_counter() - t0) * 1000

    owned_client = client is None

    if client is None:
        api_key = _configured_api_key()
        if api_key is None:
            raise LlmAnalysisError(
                LlmErrorCode.LLM_NOT_CONFIGURED,
                "Gemini analysis is not configured. Set GEMINI_API_KEY to continue.",
            )
        client = genai.Client(api_key=api_key)

    t1 = time.perf_counter()
    try:
        response = _request_structured_analysis(client, prompt)

        if metrics is not None:
            usage = getattr(response, "usage_metadata", None)
            if usage:
                if (p := getattr(usage, "prompt_token_count", None)) is not None:
                    metrics["gemini_prompt_tokens"] = float(p)
                if (c := getattr(usage, "candidates_token_count", None)) is not None:
                    metrics["gemini_output_tokens"] = float(c)
                if (t := getattr(usage, "thoughts_token_count", None)) is not None:
                    metrics["gemini_thought_tokens"] = float(t)
                if (tt := getattr(usage, "total_token_count", None)) is not None:
                    metrics["gemini_total_tokens"] = float(tt)
    finally:
        if metrics is not None:
            metrics["gemini_request_ms"] = (time.perf_counter() - t1) * 1000
        if owned_client:
            client.close()

    t2 = time.perf_counter()
    try:
        analysis = _parse_structured_response(response)
        return validate_resume_analysis(analysis, job, resume)
    except (ValidationError, ResumeAnalysisContractError) as exc:
        raise LlmAnalysisError(
            LlmErrorCode.LLM_INVALID_RESPONSE,
            "Gemini returned a response that does not match the analysis contract.",
        ) from exc
    finally:
        if metrics is not None:
            metrics["gemini_parsing_validation_ms"] = (time.perf_counter() - t2) * 1000


def _request_structured_analysis(
    client: genai.Client,
    prompt: ResumeAnalysisPrompt,
) -> Any:
    """Call the external SDK at one mockable translation boundary."""

    try:
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt.user_content,
            config=types.GenerateContentConfig(
                system_instruction=prompt.system_instruction,
                response_mime_type="application/json",
                response_json_schema=ResumeAnalysis.model_json_schema(),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
                thinking_config=types.ThinkingConfig(
                    thinking_level="low"
                ),
            ),
        )
    except Exception as exc:
        raise LlmAnalysisError(
            LlmErrorCode.LLM_REQUEST_FAILED,
            "Gemini analysis request failed.",
        ) from exc


def _parse_structured_response(response: Any) -> ResumeAnalysis:
    """Translate SDK parsed output or JSON text into the strict local model."""

    parsed_response = getattr(response, "parsed", None)
    if parsed_response is not None:
        try:
            return (
                parsed_response
                if isinstance(parsed_response, ResumeAnalysis)
                else ResumeAnalysis.model_validate(parsed_response)
            )
        except ValidationError:
            pass

    try:
        response_text = response.text
    except (AttributeError, ValueError):
        response_text = None

    if not isinstance(response_text, str) or not response_text.strip():
        raise ResumeAnalysisContractError("Gemini response did not contain JSON")

    try:
        response_data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ResumeAnalysisContractError("Gemini response contained malformed JSON") from exc

    return ResumeAnalysis.model_validate(response_data)


def _configured_api_key() -> str | None:
    if settings.gemini_api_key is None:
        return None

    api_key = settings.gemini_api_key.get_secret_value().strip()
    return api_key or None
