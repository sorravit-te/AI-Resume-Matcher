"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.routes.health import router as health_router
from app.api.routes.resume import router as resume_router
from app.api.routes.web import register_web_routes
from app.core.config import settings

app = FastAPI(title=settings.app_name, version=settings.app_version)
register_error_handlers(app)
register_web_routes(app)
app.include_router(health_router)
app.include_router(resume_router)
