"""Public, privacy-safe API error response models."""

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorModel(BaseModel):
    """Strict immutable base for public API errors."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ApiErrorDetail(ApiErrorModel):
    """Stable machine-readable code and safe human-readable message."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ApiErrorResponse(ApiErrorModel):
    """Envelope used for known application failures."""

    error: ApiErrorDetail
