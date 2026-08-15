# AI Resume Matcher

AI Resume Matcher is an assignment project that will eventually compare PDF
resumes with the EDVISORY AI & Data Solution Intern role and produce
explainable scoring results.

## Current status

The current implementation provides:

- A machine-readable EDVISORY job definition
- A validated 100-point scoring rubric
- Safe text extraction from supported resume PDFs
- Gemini-powered structured semantic evidence analysis
- Deterministic evidence quote and page verification

Deterministic scoring and the public resume-analysis API endpoint are not
implemented yet.

## PDF support

- PDF only; text-based English, Thai, and mixed-language PDFs
- Maximum file size: 10 MiB
- Maximum length: 10 pages
- OCR is not supported yet

Deterministic evidence verification, score calculation, and a public
resume-analysis API endpoint are not implemented yet.

## Requirements

- Python 3.12 or newer

## Installation

Create and activate a virtual environment, then install the project and its
development dependencies:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On macOS or Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Environment setup

Copy `.env.example` to `.env` and adjust values for your environment:

```powershell
Copy-Item .env.example .env
```

The `.env` file is ignored by Git and must not contain credentials intended for
source control.

Set `GEMINI_API_KEY` to enable structured semantic analysis. `GEMINI_MODEL`
defaults to `gemini-3.6-flash`. The API key is not required to start the
FastAPI application or run the deterministic test suite.

## Run the API

```bash
uvicorn app.main:app --reload
```

Open the Swagger UI at <http://127.0.0.1:8000/docs>.

Check service health at <http://127.0.0.1:8000/health> or with:

```bash
curl http://127.0.0.1:8000/health
```

## Run tests


```bash
python -m pytest
```
