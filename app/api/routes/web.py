"""Repository-owned web interface served by the FastAPI application."""

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_WEB_DIRECTORY = Path(__file__).resolve().parents[2] / "web"
_INDEX_FILE = _WEB_DIRECTORY / "index.html"

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=FileResponse)
def get_web_interface() -> FileResponse:
    """Return the static resume-matching interface."""

    return FileResponse(_INDEX_FILE, media_type="text/html")


def register_web_routes(app: FastAPI) -> None:
    """Register the web page and its same-origin static assets."""

    app.mount(
        "/static",
        StaticFiles(directory=_WEB_DIRECTORY),
        name="static",
    )
    app.include_router(router)
