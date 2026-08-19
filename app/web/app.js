"use strict";

const RESUME_MATCH_ENDPOINT = "/api/v1/resume-match";
const DEFAULT_RESULT_FILENAME = "resume_match_result.json";
const DEFAULT_RESULT_CATEGORY = "education";
const GENERIC_ANALYSIS_ERROR = "Unable to analyze the resume. Please try again.";
const NETWORK_ANALYSIS_ERROR =
  "Could not reach the analysis service. Please try again.";
const DOWNLOAD_ERROR = "Unable to download the analysis result. Please try again.";

const CATEGORY_LABELS = Object.freeze({
  education: "Education",
  skills: "Skills",
  knowledge: "Knowledge",
  tools: "Tools",
});
const CRITERION_LABELS = Object.freeze({
  "education.academic_relevance": "Academic Relevance",
  "skills.python": "Python Programming",
  "skills.prompt_engineering": "Prompt Engineering",
  "skills.context_engineering": "Context Engineering",
  "skills.ai_system_workflow_design": "AI System / Workflow Design",
  "skills.analytical_problem_solving": "Analytical & Problem Solving",
  "skills.requirement_collaboration":
    "Requirement Understanding & Collaboration",
  "skills.testing_evaluation": "Testing & Evaluation",
  "knowledge.llm_generative_ai": "LLM / Generative AI",
  "knowledge.nlp": "Natural Language Processing",
  "knowledge.machine_learning": "Machine Learning Fundamentals",
  "tools.api": "API Integration",
  "tools.json_structured_data": "JSON / Structured Data",
  "tools.automation_pipeline": "Automation Pipeline / Integration",
  "tools.n8n": "n8n",
  "tools.sql": "SQL",
  "tools.docker": "Docker",
  "tools.cloud": "Cloud Platform",
});
const MATCH_TYPE_LABELS = Object.freeze({
  direct: "Direct",
  equivalent: "Equivalent",
  transferable: "Transferable",
  adjacent: "Adjacent",
  none: "No Match",
});
const MATCH_TYPE_CLASSES = Object.freeze({
  direct: "match-badge--direct",
  equivalent: "match-badge--equivalent",
  transferable: "match-badge--transferable",
  adjacent: "match-badge--adjacent",
  none: "match-badge--none",
});
const SOURCE_TYPE_LABELS = Object.freeze({
  education: "Education",
  coursework: "Coursework",
  project: "Project",
  work_experience: "Work Experience",
  skills: "Skills",
  certification: "Certification",
  other: "Other",
});
const EDUCATION_FIELDS = Object.freeze([
  ["degree", "Degree"],
  ["field_or_major", "Field or Major"],
  ["faculty", "Faculty"],
  ["university", "University"],
  ["gpa", "GPA"],
  ["current_study_year", "Current Study Year"],
  ["expected_graduation", "Expected Graduation"],
]);

const pageShell = document.querySelector(".page-shell");
const uploadPanel = document.querySelector("#upload-panel");
const fileInput = document.querySelector("#resume-file");
const dropZone = document.querySelector("#drop-zone");
const fileSummary = document.querySelector("#file-summary");
const fileName = document.querySelector("#file-name");
const fileSize = document.querySelector("#file-size");
const removeButton = document.querySelector("#remove-file");
const statusMessage = document.querySelector("#upload-status");
const analyzeButton = document.querySelector("#analyze-button");
const analyzeButtonLabel = document.querySelector("#analyze-button-label");
const resultSection = document.querySelector("#result-section");
const downloadButton = document.querySelector("#download-result");
const resultTitle = document.querySelector("#result-title");
const resultJobTitle = document.querySelector("#result-job-title");
const resultCompany = document.querySelector("#result-company");
const overallScoreName = document.querySelector("#overall-score-name");
const overallScoreValue = document.querySelector("#overall-score-value");
const overallScoreMaximum = document.querySelector("#overall-score-maximum");
const overallScoreProgress = document.querySelector("#overall-score-progress");
const overallScoreProgressFill = document.querySelector(
  "#overall-score-progress-fill",
);
const categoryScoreContainer = document.querySelector(
  "#category-score-container",
);
const overallRationaleSection = document.querySelector(
  "#overall-rationale-section",
);
const overallRationaleText = document.querySelector(
  "#overall-rationale-text",
);
const criterionDetailContainer = document.querySelector(
  "#criterion-detail-container",
);

let selectedFile = null;
let dragDepth = 0;
let isAnalyzing = false;
let latestResult = null;
let latestResultFilename = DEFAULT_RESULT_FILENAME;
let selectedResultCategory = null;

function isClearlyPdf(file) {
  return (
    file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
  );
}

function readableFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} bytes`;
  }

  const sizeInMiB = bytes / (1024 * 1024);
  if (sizeInMiB < 1) {
    return `${(bytes / 1024).toFixed(1)} KiB`;
  }

  return `${sizeInMiB.toFixed(1)} MiB`;
}

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("is-error", isError);
}

function clearLatestResult() {
  latestResult = null;
  latestResultFilename = DEFAULT_RESULT_FILENAME;
  selectedResultCategory = null;
  clearResultVisualization();
}

function setAnalyzingState(analyzing) {
  isAnalyzing = analyzing;
  uploadPanel.setAttribute("aria-busy", String(analyzing));
  dropZone.setAttribute("aria-disabled", String(analyzing));
  dropZone.classList.toggle("is-disabled", analyzing);
  fileInput.disabled = analyzing;
  removeButton.disabled = analyzing;
  analyzeButton.disabled = analyzing || !selectedFile;
  analyzeButton.classList.toggle("is-loading", analyzing);
  analyzeButtonLabel.textContent = analyzing ? "Analyzing..." : "Analyze Resume";

  if (analyzing) {
    dragDepth = 0;
    dropZone.classList.remove("is-dragging");
    resultSection.hidden = true;
  }
}

function clearSelectedFile(message = "") {
  clearLatestResult();
  selectedFile = null;
  fileInput.value = "";
  fileSummary.hidden = true;
  fileName.textContent = "";
  fileSize.textContent = "";
  analyzeButton.disabled = true;
  setStatus(message);
}

function selectFile(file) {
  if (isAnalyzing) {
    return;
  }

  clearLatestResult();
  if (!file || !isClearlyPdf(file)) {
    clearSelectedFile();
    setStatus("Please select a PDF file.", true);
    return;
  }

  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = readableFileSize(file.size);
  fileSummary.hidden = false;
  analyzeButton.disabled = false;
  setStatus("");
}

function openFilePicker() {
  if (!isAnalyzing) {
    fileInput.click();
  }
}

async function readJsonSafely(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function publicErrorMessage(responseBody) {
  const message = responseBody?.error?.message;
  if (
    typeof message === "string" &&
    message.trim().length > 0 &&
    message.length <= 500
  ) {
    return message.trim();
  }

  return GENERIC_ANALYSIS_ERROR;
}

function isResultObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function isUsableScore(score, maximum) {
  return (
    typeof score === "number" &&
    Number.isFinite(score) &&
    score >= 0 &&
    typeof maximum === "number" &&
    Number.isFinite(maximum) &&
    maximum > 0 &&
    score <= maximum
  );
}

function isUsableEvidence(evidence) {
  return (
    isResultObject(evidence) &&
    isNonEmptyString(evidence.text) &&
    Number.isInteger(evidence.page) &&
    evidence.page >= 1 &&
    isNonEmptyString(evidence.source_type)
  );
}

function isUsableCriterion(criterion) {
  return (
    isResultObject(criterion) &&
    isNonEmptyString(criterion.criterion_id) &&
    isNonEmptyString(criterion.category) &&
    isNonEmptyString(criterion.match_type) &&
    Number.isInteger(criterion.evidence_level) &&
    criterion.evidence_level >= 0 &&
    criterion.evidence_level <= 4 &&
    isUsableScore(criterion.score, criterion.max_score) &&
    Array.isArray(criterion.evidence) &&
    criterion.evidence.every(isUsableEvidence) &&
    isNonEmptyString(criterion.rationale)
  );
}

function isUsableResult(result) {
  return (
    isResultObject(result) &&
    isNonEmptyString(result.company) &&
    isNonEmptyString(result.job_title) &&
    isNonEmptyString(result.score_name) &&
    isUsableScore(result.overall_score, result.maximum_score) &&
    isNonEmptyString(result.overall_rationale) &&
    Array.isArray(result.category_scores) &&
    result.category_scores.length > 0 &&
    result.category_scores.every(
      (category) =>
        isResultObject(category) &&
        isNonEmptyString(category.category) &&
        isUsableScore(category.score, category.max_score),
    ) &&
    Array.isArray(result.criterion_scores) &&
    result.criterion_scores.length > 0 &&
    result.criterion_scores.every(isUsableCriterion)
  );
}

function formatScore(value) {
  return String(Math.round(value * 100) / 100);
}

function visualPercentage(score, maximum) {
  return Math.min(100, Math.max(0, (score / maximum) * 100));
}

function humanizeIdentifier(value) {
  const finalPart = value.trim().split(".").pop() || value.trim();
  return finalPart
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function presentationLabel(labels, value) {
  return Object.hasOwn(labels, value) ? labels[value] : humanizeIdentifier(value);
}

function createTextElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  element.textContent = text;
  return element;
}

function createScoreProgress(
  score,
  maximum,
  label,
  className = "",
  isDecorative = false,
) {
  const progress = document.createElement(isDecorative ? "span" : "div");
  progress.className = `score-progress ${className}`.trim();
  if (!isDecorative) {
    progress.setAttribute("role", "progressbar");
    progress.setAttribute(
      "aria-label",
      `${label}: ${formatScore(score)} of ${formatScore(maximum)}`,
    );
    progress.setAttribute("aria-valuemin", "0");
    progress.setAttribute("aria-valuenow", String(score));
    progress.setAttribute("aria-valuemax", String(maximum));
  }

  const fill = document.createElement("span");
  fill.style.width = `${visualPercentage(score, maximum)}%`;
  progress.append(fill);
  return progress;
}

function clearResultVisualization() {
  resultSection.hidden = true;
  pageShell.classList.remove("has-result");
  downloadButton.disabled = true;
  resultTitle.textContent = "";
  resultJobTitle.textContent = "";
  resultCompany.textContent = "";
  overallScoreName.textContent = "";
  overallScoreValue.textContent = "";
  overallScoreMaximum.textContent = "";
  overallScoreProgress.removeAttribute("aria-label");
  overallScoreProgress.removeAttribute("aria-valuemin");
  overallScoreProgress.removeAttribute("aria-valuenow");
  overallScoreProgress.removeAttribute("aria-valuemax");
  overallScoreProgressFill.style.width = "0%";
  overallRationaleSection.hidden = true;
  overallRationaleText.textContent = "";
  categoryScoreContainer.replaceChildren();
  criterionDetailContainer.removeAttribute("aria-labelledby");
  criterionDetailContainer.replaceChildren();
}

function isSafeResultFilename(filename) {
  return (
    typeof filename === "string" &&
    /^[A-Za-z0-9_-]+\.json$/i.test(filename)
  );
}

function updateDownloadAvailability() {
  downloadButton.disabled = !isUsableResult(latestResult);
}

function renderOverallScore(result) {
  overallScoreName.textContent = result.score_name;
  overallScoreValue.textContent = formatScore(result.overall_score);
  overallScoreMaximum.textContent = formatScore(result.maximum_score);
  overallScoreProgress.setAttribute(
    "aria-label",
    `${result.score_name}: ${formatScore(result.overall_score)} of ${formatScore(result.maximum_score)}`,
  );
  overallScoreProgress.setAttribute("aria-valuemin", "0");
  overallScoreProgress.setAttribute(
    "aria-valuenow",
    String(result.overall_score),
  );
  overallScoreProgress.setAttribute(
    "aria-valuemax",
    String(result.maximum_score),
  );
  overallScoreProgressFill.style.width = `${visualPercentage(
    result.overall_score,
    result.maximum_score,
  )}%`;
}

function renderCategoryScores(categoryScores) {
  const cards = categoryScores.map((category) => {
    const label = presentationLabel(CATEGORY_LABELS, category.category);
    const card = document.createElement("button");
    card.type = "button";
    card.className = "category-score-card";
    card.dataset.category = category.category;
    card.setAttribute("aria-pressed", "false");
    card.setAttribute("aria-controls", "criterion-detail-container");
    card.addEventListener("click", () => {
      selectResultCategory(category.category);
    });
    const selectedLabel = createTextElement(
      "span",
      "category-selected-label",
      "Selected",
    );
    selectedLabel.hidden = true;
    card.append(
      createTextElement("span", "category-score-name", label),
      selectedLabel,
      createTextElement(
        "span",
        "category-score-value",
        `${formatScore(category.score)} / ${formatScore(category.max_score)}`,
      ),
      createScoreProgress(category.score, category.max_score, label, "", true),
    );
    return card;
  });
  categoryScoreContainer.replaceChildren(...cards);
  updateCategorySelectionState();
}

function updateCategorySelectionState() {
  const cards = categoryScoreContainer.querySelectorAll(".category-score-card");
  for (const card of cards) {
    const isSelected = card.dataset.category === selectedResultCategory;
    card.setAttribute("aria-pressed", String(isSelected));
    card.classList.toggle("is-selected", isSelected);
    const selectedLabel = card.querySelector(".category-selected-label");
    if (selectedLabel) {
      selectedLabel.hidden = !isSelected;
    }
  }
}

function defaultResultCategory(categoryScores) {
  return categoryScores.some(
    (category) => category.category === DEFAULT_RESULT_CATEGORY,
  )
    ? DEFAULT_RESULT_CATEGORY
    : categoryScores[0].category;
}

function selectResultCategory(category) {
  if (
    !isUsableResult(latestResult) ||
    !latestResult.category_scores.some(
      (categoryScore) => categoryScore.category === category,
    )
  ) {
    return;
  }

  selectedResultCategory = category;
  updateCategorySelectionState();
  renderSelectedCategoryDetail(latestResult);
}

function appendEducationItem(container, label, value) {
  const item = document.createElement("div");
  item.className = "education-detail-item";
  item.append(
    createTextElement("dt", "education-detail-label", label),
    createTextElement("dd", "education-detail-value", value),
  );
  container.append(item);
}

function createEducationDetails(education) {
  if (!isResultObject(education)) {
    return null;
  }

  const detailsList = document.createElement("dl");
  detailsList.className = "education-details-list";
  for (const [field, label] of EDUCATION_FIELDS) {
    if (isNonEmptyString(education[field])) {
      appendEducationItem(detailsList, label, education[field]);
    }
  }

  const coursework = Array.isArray(education.coursework)
    ? education.coursework.filter(isNonEmptyString)
    : [];
  if (coursework.length > 0) {
    const item = document.createElement("div");
    item.className = "education-detail-item education-detail-item--coursework";
    const terms = document.createElement("dd");
    terms.className = "coursework-list";
    for (const course of coursework) {
      terms.append(createTextElement("span", "coursework-item", course));
    }
    item.append(
      createTextElement("dt", "education-detail-label", "Coursework"),
      terms,
    );
    detailsList.append(item);
  }

  if (detailsList.childElementCount === 0) {
    return null;
  }

  const details = document.createElement("section");
  details.className = "education-details";
  details.append(
    createTextElement("h5", "education-details-title", "Education Details"),
    detailsList,
    createTextElement(
      "p",
      "education-note",
      "Education metadata is shown as extracted information; scoring is based on the validated criterion evidence and rubric.",
    ),
  );
  return details;
}

function appendMetric(container, label, value) {
  const metric = document.createElement("div");
  metric.append(
    createTextElement("dt", "criterion-metric-label", label),
    createTextElement("dd", "criterion-metric-value", value),
  );
  container.append(metric);
}

function createMatchBadge(matchType) {
  const badge = createTextElement(
    "span",
    "match-badge",
    presentationLabel(MATCH_TYPE_LABELS, matchType),
  );
  badge.classList.add(
    Object.hasOwn(MATCH_TYPE_CLASSES, matchType)
      ? MATCH_TYPE_CLASSES[matchType]
      : "match-badge--neutral",
  );
  return badge;
}

function createEvidenceList(evidenceItems) {
  const list = document.createElement("div");
  list.className = "evidence-list";

  if (evidenceItems.length === 0) {
    list.append(createTextElement("p", "empty-evidence", "No evidence provided."));
    return list;
  }

  for (const evidence of evidenceItems) {
    const item = document.createElement("figure");
    item.className = "evidence-item";
    const quote = document.createElement("blockquote");
    quote.textContent = evidence.text;
    const sourceLabel = presentationLabel(
      SOURCE_TYPE_LABELS,
      evidence.source_type,
    );
    item.append(
      quote,
      createTextElement(
        "figcaption",
        "evidence-provenance",
        `Page ${evidence.page} · ${sourceLabel}`,
      ),
    );
    list.append(item);
  }
  return list;
}

function createCriterionCard(criterion) {
  const criterionLabel = presentationLabel(
    CRITERION_LABELS,
    criterion.criterion_id,
  );
  const matchLabel = presentationLabel(
    MATCH_TYPE_LABELS,
    criterion.match_type,
  );
  const details = document.createElement("details");
  details.className = "criterion-card";

  const summary = document.createElement("summary");
  const summaryBody = document.createElement("span");
  summaryBody.className = "criterion-summary-body";
  const summaryTop = document.createElement("span");
  summaryTop.className = "criterion-summary-top";
  summaryTop.append(
    createTextElement("span", "criterion-name", criterionLabel),
    createTextElement(
      "span",
      "criterion-score",
      `${formatScore(criterion.score)} / ${formatScore(criterion.max_score)}`,
    ),
  );
  const summaryMeta = document.createElement("span");
  summaryMeta.className = "criterion-summary-meta";
  summaryMeta.append(
    createMatchBadge(criterion.match_type),
    createTextElement(
      "span",
      "criterion-evidence-level",
      `Evidence ${criterion.evidence_level} / 4`,
    ),
  );
  summaryBody.append(summaryTop, summaryMeta);
  summary.append(summaryBody);

  const content = document.createElement("div");
  content.className = "criterion-content";
  const metrics = document.createElement("dl");
  metrics.className = "criterion-metrics";
  appendMetric(
    metrics,
    "Score",
    `${formatScore(criterion.score)} / ${formatScore(criterion.max_score)}`,
  );
  appendMetric(metrics, "Match", matchLabel);
  appendMetric(metrics, "Evidence level", `${criterion.evidence_level} / 4`);
  if (
    Number.isInteger(criterion.effective_rating) &&
    criterion.effective_rating >= 0 &&
    criterion.effective_rating <= 4
  ) {
    appendMetric(
      metrics,
      "Effective rating",
      `${criterion.effective_rating} / 4`,
    );
  }

  content.append(
    metrics,
    createTextElement("h5", "criterion-detail-heading", "Evidence"),
    createEvidenceList(criterion.evidence),
    createTextElement("h5", "criterion-detail-heading", "Rationale"),
    createTextElement("p", "criterion-rationale", criterion.rationale),
  );
  details.append(summary, content);
  return details;
}

function renderSelectedCategoryDetail(result) {
  const selectedCategory = result.category_scores.some(
    (category) => category.category === selectedResultCategory,
  )
    ? selectedResultCategory
    : defaultResultCategory(result.category_scores);
  selectedResultCategory = selectedCategory;

  const panel = document.createElement("section");
  panel.className = "selected-category-panel";
  const title = createTextElement(
    "h4",
    "selected-category-title",
    presentationLabel(CATEGORY_LABELS, selectedCategory),
  );
  title.id = "selected-category-title";
  panel.append(title);

  if (selectedCategory === "education") {
    const educationDetails = createEducationDetails(result.education);
    if (educationDetails) {
      panel.append(educationDetails);
    }
  }

  const criteria = result.criterion_scores.filter(
    (criterion) => criterion.category === selectedCategory,
  );
  panel.append(...criteria.map(createCriterionCard));
  criterionDetailContainer.replaceChildren(panel);
  criterionDetailContainer.setAttribute(
    "aria-labelledby",
    "selected-category-title",
  );
}

function renderResult(result) {
  clearResultVisualization();
  if (!isUsableResult(result)) {
    return false;
  }

  resultTitle.textContent = isNonEmptyString(result.candidate_name)
    ? result.candidate_name
    : "Candidate name not provided";
  resultJobTitle.textContent = result.job_title;
  resultCompany.textContent = result.company;
  renderOverallScore(result);
  if (isNonEmptyString(result.overall_rationale)) {
    overallRationaleText.textContent = result.overall_rationale;
    overallRationaleSection.hidden = false;
  }
  selectedResultCategory = defaultResultCategory(result.category_scores);
  renderCategoryScores(result.category_scores);
  renderSelectedCategoryDetail(result);

  resultSection.hidden = false;
  pageShell.classList.add("has-result");
  updateDownloadAvailability();
  const reducedMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  resultSection.scrollIntoView({
    behavior: reducedMotion ? "auto" : "smooth",
    block: "start",
  });
  return true;
}

function resultFilenameFromHeader(contentDisposition) {
  if (typeof contentDisposition !== "string") {
    return DEFAULT_RESULT_FILENAME;
  }

  const filenameMatch =
    /(?:^|;)\s*filename=(?:"([^"]+)"|([^;\s]+))/i.exec(contentDisposition);
  const candidate = (filenameMatch?.[1] ?? filenameMatch?.[2] ?? "").trim();

  if (!isSafeResultFilename(candidate)) {
    return DEFAULT_RESULT_FILENAME;
  }

  return candidate;
}

function downloadLatestResult() {
  if (!isUsableResult(latestResult)) {
    updateDownloadAvailability();
    setStatus(DOWNLOAD_ERROR, true);
    return;
  }

  let objectUrl = null;
  let anchor = null;
  try {
    const json = `${JSON.stringify(latestResult, null, 2)}\n`;
    const blob = new Blob([json], {
      type: "application/json;charset=utf-8",
    });
    objectUrl = URL.createObjectURL(blob);
    anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = isSafeResultFilename(latestResultFilename)
      ? latestResultFilename
      : DEFAULT_RESULT_FILENAME;
    anchor.hidden = true;
    document.body.append(anchor);
    anchor.click();
  } catch {
    setStatus(DOWNLOAD_ERROR, true);
  } finally {
    if (anchor) {
      anchor.remove();
    }
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
    }
  }
}

async function analyzeSelectedResume() {
  if (isAnalyzing || !selectedFile) {
    return;
  }

  clearLatestResult();
  const formData = new FormData();
  formData.append("resume", selectedFile, selectedFile.name);

  setAnalyzingState(true);
  setStatus("This may take around 15–30 seconds");

  try {
    let response;
    try {
      response = await fetch(RESUME_MATCH_ENDPOINT, {
        method: "POST",
        body: formData,
      });
    } catch {
      setStatus(NETWORK_ANALYSIS_ERROR, true);
      return;
    }

    const responseBody = await readJsonSafely(response);
    if (!response.ok) {
      setStatus(publicErrorMessage(responseBody), true);
      return;
    }

    if (!isResultObject(responseBody)) {
      setStatus(GENERIC_ANALYSIS_ERROR, true);
      return;
    }

    latestResult = responseBody;
    latestResultFilename = resultFilenameFromHeader(
      response.headers.get("Content-Disposition"),
    );
    if (!renderResult(latestResult)) {
      clearLatestResult();
      setStatus(GENERIC_ANALYSIS_ERROR, true);
      return;
    }
    setStatus("Analysis complete.");
  } finally {
    setAnalyzingState(false);
  }
}

dropZone.addEventListener("click", (event) => {
  if (event.target !== fileInput) {
    openFilePicker();
  }
});

dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    openFilePicker();
  }
});

fileInput.addEventListener("change", () => {
  selectFile(fileInput.files[0]);
});

removeButton.addEventListener("click", () => {
  if (isAnalyzing) {
    return;
  }

  clearSelectedFile();
  dropZone.focus();
});

dropZone.addEventListener("dragenter", (event) => {
  event.preventDefault();
  if (isAnalyzing) {
    return;
  }

  dragDepth += 1;
  dropZone.classList.add("is-dragging");
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = isAnalyzing ? "none" : "copy";
  }
});

dropZone.addEventListener("dragleave", (event) => {
  event.preventDefault();
  if (isAnalyzing) {
    return;
  }

  dragDepth = Math.max(0, dragDepth - 1);
  if (dragDepth === 0) {
    dropZone.classList.remove("is-dragging");
  }
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  if (isAnalyzing) {
    return;
  }

  dragDepth = 0;
  dropZone.classList.remove("is-dragging");
  selectFile(event.dataTransfer?.files[0]);
});

analyzeButton.addEventListener("click", () => {
  void analyzeSelectedResume();
});

downloadButton.addEventListener("click", downloadLatestResult);
