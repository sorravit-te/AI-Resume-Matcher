"""Service health endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Public service health information."""

    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return local service health without contacting external systems."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )
