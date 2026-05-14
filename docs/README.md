# Intelligent Loan Approval Agent

An AI agent that analyzes loan documents, retrieves policies via RAG, and provides preliminary approval decisions (Green/Yellow/Red) with reasoning and policy citations.

## Quick Start

```bash
# Setup virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Run tests
uv run pytest
```

## Project Structure

```
├── src/loan_approval_agent/
│   ├── tools/           # Agent tools (classifier, extractor, validator, etc.)
│   ├── models/          # Data models
│   └── config/          # Configuration
├── tests/               # Test suite
├── policies/            # Policy documents for RAG knowledge base
├── data/                # Sample loan documents
└── Design_Doc.pdf       # Full design specifications
```

## Documentation

See [AGENTS.md](AGENTS.md) for development guidance and [Design_Doc.pdf](Design_Doc.pdf) for full design specifications.
