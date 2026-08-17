"use strict";

const RESUME_MATCH_ENDPOINT = "/api/v1/resume-match";
const DEFAULT_RESULT_FILENAME = "resume_match_result.json";
const GENERIC_ANALYSIS_ERROR = "Unable to analyze the resume. Please try again.";
const NETWORK_ANALYSIS_ERROR =
  "Could not reach the analysis service. Please try again.";

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
const analyzeSpinner = document.querySelector("#analyze-spinner");

let selectedFile = null;
let dragDepth = 0;
let isAnalyzing = false;
let latestResult = null;
let latestResultFilename = DEFAULT_RESULT_FILENAME;

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
  analyzeSpinner.hidden = !analyzing;

  if (analyzing) {
    dragDepth = 0;
    dropZone.classList.remove("is-dragging");
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

function resultFilenameFromHeader(contentDisposition) {
  if (typeof contentDisposition !== "string") {
    return DEFAULT_RESULT_FILENAME;
  }

  const filenameMatch =
    /(?:^|;)\s*filename=(?:"([^"]+)"|([^;\s]+))/i.exec(contentDisposition);
  const candidate = (filenameMatch?.[1] ?? filenameMatch?.[2] ?? "").trim();

  if (!/^[A-Za-z0-9_-]+\.json$/i.test(candidate)) {
    return DEFAULT_RESULT_FILENAME;
  }

  return candidate;
}

async function analyzeSelectedResume() {
  if (isAnalyzing || !selectedFile) {
    return;
  }

  clearLatestResult();
  const formData = new FormData();
  formData.append("resume", selectedFile, selectedFile.name);

  setAnalyzingState(true);
  setStatus("Analyzing resume. This may take a moment.");

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
