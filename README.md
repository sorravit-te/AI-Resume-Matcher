# AI Resume Matcher

AI Resume Matcher is an assignment project that will eventually compare PDF
resumes with the EDVISORY AI & Data Solution Intern role and produce
explainable scoring results.

## Current status

Step 2 extends the Step 1 foundation with:

- A machine-readable EDVISORY job definition
- A validated 100-point scoring rubric

Resume processing, LLM analysis, and actual candidate scoring are not
implemented yet.

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

Copy `.env.example` to `.env` and adjust application metadata for your
environment. No external provider credentials are configured at this stage.

```powershell
Copy-Item .env.example .env
```

The `.env` file is ignored by Git and must not contain credentials intended for
source control.

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
