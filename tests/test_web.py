"""Deterministic tests for the static web interface foundation."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_root_returns_ai_resume_matcher_html() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>AI Resume Matcher</title>" in response.text
    assert '<p class="product-label">AI Resume Matcher</p>' in response.text
    assert '<h1 id="page-title">Upload your resume</h1>' in response.text
    assert 'type="file"' in response.text
    assert 'accept="application/pdf,.pdf"' in response.text
    assert 'id="upload-panel" aria-busy="false"' in response.text
    assert 'id="analyze-spinner"' in response.text
    assert 'id="result-section"' in response.text
    assert 'id="overall-score-progress"' in response.text
    assert 'id="category-score-container"' in response.text
    assert 'id="education-details"' in response.text
    assert 'id="criterion-detail-container"' in response.text


def test_root_referenced_stylesheet_is_available() -> None:
    page = client.get("/")
    assert 'href="/static/styles.css"' in page.text

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_root_referenced_javascript_is_available() -> None:
    page = client.get("/")
    assert 'src="/static/app.js"' in page.text

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert 'const RESUME_MATCH_ENDPOINT = "/api/v1/resume-match"' in response.text
    assert "new FormData()" in response.text
    assert 'formData.append("resume", selectedFile, selectedFile.name)' in response.text
    assert "isAnalyzing" in response.text
    assert 'setAttribute("aria-busy", String(analyzing))' in response.text
    assert 'analyzing ? "Analyzing..." : "Analyze Resume"' in response.text
    assert 'headers.get("Content-Disposition")' in response.text
    assert "function renderResult(result)" in response.text
    assert "const CRITERION_LABELS" in response.text
    assert '"knowledge.machine_learning"' in response.text
    assert '"tools.automation_pipeline"' in response.text
    assert 'document.createElement("details")' in response.text
    assert "document.createElement" in response.text
    assert ".textContent" in response.text
    assert ".replaceChildren" in response.text
    assert "function isUsableResult(result)" in response.text
    assert "clearResultVisualization();" in response.text
    assert "Object.hasOwn" in response.text
    assert "GENERIC_ANALYSIS_ERROR" in response.text
    assert "innerHTML" not in response.text
    assert '"Content-Type"' not in response.text
    assert response.text.count("fetch(") == 1
    assert "new Blob" not in response.text
    assert "URL.createObjectURL" not in response.text


def test_existing_docs_and_health_routes_remain_available() -> None:
    docs_response = client.get("/docs")
    health_response = client.get("/health")

    assert docs_response.status_code == 200
    assert docs_response.headers["content-type"].startswith("text/html")
    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }
