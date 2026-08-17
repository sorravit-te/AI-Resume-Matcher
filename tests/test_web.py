"""Deterministic tests for the static web interface foundation."""

import re

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
    assert "family=Noto+Sans+Thai:wght@300;400;500;600;700" in response.text
    assert 'type="file"' in response.text
    assert 'accept="application/pdf,.pdf"' in response.text
    assert 'id="upload-panel" aria-busy="false"' in response.text
    assert 'id="analyze-spinner"' in response.text
    assert 'id="result-section"' in response.text
    assert 'id="overall-score-progress"' in response.text
    assert 'id="category-score-container"' in response.text
    assert 'role="group"' in response.text
    assert 'aria-label="Result categories"' in response.text
    assert 'id="criterion-detail-container"' in response.text
    assert 'class="selected-category-detail"' in response.text
    assert 'role="region"' in response.text
    assert 'aria-live="polite"' in response.text
    assert 'aria-atomic="false"' in response.text
    assert 'id="download-result"' in response.text
    assert "Download JSON" in response.text


def test_root_referenced_stylesheet_is_available() -> None:
    page = client.get("/")
    assert 'href="/static/styles.css"' in page.text

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert "--app-content-width: 880px;" in response.text
    assert response.text.count("var(--app-content-width)") == 1
    assert '"Inter", "Noto Sans Thai", system-ui' in response.text
    assert '"Space Grotesk", "Noto Sans Thai", "Inter", sans-serif' in response.text

    selected_label_rule = re.search(
        r"\.category-selected-label\s*\{(?P<body>[^}]*)\}", response.text
    )
    assert selected_label_rule is not None
    assert "color: var(--text);" in selected_label_rule.group("body")
    assert "color: var(--category-accent);" not in selected_label_rule.group("body")

    reduced_motion_css = response.text.split(
        "@media (prefers-reduced-motion: reduce)", maxsplit=1
    )[1]
    transition_rule = re.search(
        r"(?P<selectors>[^{}]*\.category-score-card[^{}]*)"
        r"\{\s*transition: none;\s*animation: none;\s*\}",
        reduced_motion_css,
    )
    assert transition_rule is not None
    assert '.category-score-card:hover:not([aria-pressed="true"])' in reduced_motion_css
    assert "transform: none;" in reduced_motion_css


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
    assert "let selectedResultCategory = null;" in response.text
    assert 'const DEFAULT_RESULT_CATEGORY = "education"' in response.text
    assert "function defaultResultCategory(categoryScores)" in response.text
    assert "category.category === DEFAULT_RESULT_CATEGORY" in response.text
    assert ": categoryScores[0].category" in response.text
    assert "function selectResultCategory(category)" in response.text
    assert "function updateCategorySelectionState()" in response.text
    assert "function renderSelectedCategoryDetail(result)" in response.text
    assert "function createEducationDetails(education)" in response.text
    assert 'selectedCategory === "education"' in response.text
    assert "criterion.category === selectedCategory" in response.text
    assert 'document.createElement("button")' in response.text
    assert 'card.type = "button"' in response.text
    assert 'card.setAttribute("aria-pressed", String(isSelected))' in response.text
    assert 'card.setAttribute("aria-controls", "criterion-detail-container")' in response.text
    assert 'createTextElement("span", "category-score-name", label)' in response.text
    assert re.search(
        r'createTextElement\(\s*"span",\s*"category-score-value",',
        response.text,
    )
    assert 'document.createElement(isDecorative ? "span" : "div")' in response.text
    assert 'createScoreProgress(category.score, category.max_score, label, "", true)' in response.text
    assert 'progress.setAttribute("role", "progressbar")' in response.text
    assert 'progress.setAttribute("aria-valuemin", "0")' in response.text
    assert 'progress.setAttribute("aria-valuenow", String(score))' in response.text
    assert 'progress.setAttribute("aria-valuemax", String(maximum))' in response.text
    assert 'title.id = "selected-category-title"' in response.text
    assert 'criterionDetailContainer.setAttribute(' in response.text
    assert '"aria-labelledby"' in response.text
    assert "renderSelectedCategoryDetail(latestResult)" in response.text
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
    assert "function downloadLatestResult()" in response.text
    assert "JSON.stringify(latestResult, null, 2)" in response.text
    assert "new Blob" in response.text
    assert 'type: "application/json;charset=utf-8"' in response.text
    assert "URL.createObjectURL" in response.text
    assert "URL.revokeObjectURL" in response.text
    assert "anchor.download" in response.text
    assert "latestResultFilename" in response.text
    assert 'const DEFAULT_RESULT_FILENAME = "resume_match_result.json"' in response.text
    assert "isSafeResultFilename" in response.text
    assert "innerHTML" not in response.text
    assert "outerHTML =" not in response.text
    assert "insertAdjacentHTML" not in response.text
    assert "document.write" not in response.text
    assert "eval(" not in response.text
    assert "new Function" not in response.text
    assert '"Content-Type"' not in response.text
    assert response.text.count("fetch(") == 1
    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text
    assert "indexedDB" not in response.text


def test_category_score_button_presentation_uses_phrasing_elements() -> None:
    response = client.get("/static/app.js")
    assert response.status_code == 200

    category_start = response.text.index("function renderCategoryScores(")
    category_end = response.text.index(
        "\nfunction updateCategorySelectionState", category_start
    )
    category_code = response.text[category_start:category_end]
    assert 'createTextElement("h3", "category-score-name", label)' not in category_code
    assert re.search(
        r'createTextElement\(\s*"span",\s*"category-score-name",\s*label\)',
        category_code,
    )
    assert re.search(
        r'createTextElement\(\s*"span",\s*"category-score-value",',
        category_code,
    )
    assert 'createTextElement("p", "category-score-value",' not in category_code

    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    for selector in (".category-score-name", ".category-score-value", ".score-progress"):
        rule = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}", styles.text)
        assert rule is not None
        assert "display: block;" in rule.group("body")

    selection_start = response.text.index("function selectResultCategory(category)")
    selection_end = response.text.index(
        "\nfunction appendEducationItem", selection_start + 1
    )
    selection_code = response.text[selection_start:selection_end]
    assert "updateCategorySelectionState();" in selection_code
    assert "renderSelectedCategoryDetail(latestResult);" in selection_code
    assert "renderCategoryScores(" not in selection_code

    download_start = response.text.index("function downloadLatestResult()")
    download_end = response.text.index(
        "\nasync function analyzeSelectedResume()", download_start + 1
    )
    download_code = response.text[download_start:download_end]
    assert "fetch(" not in download_code
    assert "RESUME_MATCH_ENDPOINT" not in download_code
    assert "selectedFile" not in download_code


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
