# Loan Approval Agent

An autonomous AI agent built with UiPath Coded Agents and LangGraph that processes loan applications end-to-end: document ingestion → classification → data extraction → policy evaluation → decision → human-in-the-loop review.

## Architecture

```
Portal (HTML) → API Trigger → Agent
  fetch_document     downloads PDF from UiPath Storage Bucket
  classify           identifies document type (Docling)
  extract            pulls credit score, income, debts, LTV (Docling + regex)
  validate           calculates DTI and LTV ratios
  retrieve_policies  queries Context Grounding (RAG) for lending rules
  generate_decision  applies rule engine → GREEN / YELLOW / RED
  create_hitl        creates Action Center task, emails reviewer, suspends
                     → resumes with reviewer decision, emails applicant
```

## Quick Start

```bash
# Install dependencies
uv sync

# Authenticate with UiPath
uv run uipath auth

# Run the agent locally
uv run uipath run main.py '{"document_path": "report.pdf", "bucket_name": "loan-applications"}'

# Run tests
uv run pytest
```

## Project Structure

```
src/loan_approval_agent/
  agent.py          LangGraph graph definition and all node functions
  models/           Pydantic data models (documents, applicant, decision)
  tools/
    classifier.py   Document type classification (Docling)
    extractor.py    Field extraction from PDF (Docling + regex)
    validator.py    DTI / LTV calculation and rule validation
    decision_generator.py  Rule engine (GREEN / YELLOW / RED)
    policy_retriever.py    Context Grounding RAG queries
tests/              Pytest suite for tools and agent
docs/
  loan_portal_demo.html   Demo submission portal (Meridian Lending)
```

## Configuration

Copy `.env.example` to `.env` and fill in your UiPath credentials:

```
UIPATH_URL=https://cloud.uipath.com/{org}/{tenant}
UIPATH_TENANT_ID=...
UIPATH_ORGANIZATION_ID=...
```

## Demo Portal

Open `docs/loan_portal_demo.html` in a browser (served via `python3 -m http.server 8080` from `docs/`).
Fill in `TRIGGER_URL`, `ACCESS_TOKEN`, `BUCKET_ID`, and `FOLDER_PATH` in the `CONFIG` block before use.

## Tech Stack

- [UiPath Coded Agents](https://docs.uipath.com) — orchestration, HITL, storage, email
- [LangGraph](https://langchain-ai.github.io/langgraph/) — stateful agent graph with checkpointing
- [Docling](https://github.com/DS4SD/docling) — PDF parsing and text extraction
- Python 3.11+, managed with [uv](https://github.com/astral-sh/uv)
