"use strict";

const fileInput = document.querySelector("#resume-file");
const dropZone = document.querySelector("#drop-zone");
const fileSummary = document.querySelector("#file-summary");
const fileName = document.querySelector("#file-name");
const fileSize = document.querySelector("#file-size");
const removeButton = document.querySelector("#remove-file");
const statusMessage = document.querySelector("#upload-status");
const analyzeButton = document.querySelector("#analyze-button");

let selectedFile = null;
let dragDepth = 0;

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

function clearSelectedFile(message = "") {
  selectedFile = null;
  fileInput.value = "";
  fileSummary.hidden = true;
  fileName.textContent = "";
  fileSize.textContent = "";
  analyzeButton.disabled = true;
  setStatus(message);
}

function selectFile(file) {
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
  fileInput.click();
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
  clearSelectedFile();
  dropZone.focus();
});

dropZone.addEventListener("dragenter", (event) => {
  event.preventDefault();
  dragDepth += 1;
  dropZone.classList.add("is-dragging");
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "copy";
  }
});

dropZone.addEventListener("dragleave", (event) => {
  event.preventDefault();
  dragDepth = Math.max(0, dragDepth - 1);
  if (dragDepth === 0) {
    dropZone.classList.remove("is-dragging");
  }
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dragDepth = 0;
  dropZone.classList.remove("is-dragging");
  selectFile(event.dataTransfer?.files[0]);
});

analyzeButton.addEventListener("click", () => {
  if (!selectedFile) {
    return;
  }

  // API submission is intentionally deferred to the next integration step.
});
