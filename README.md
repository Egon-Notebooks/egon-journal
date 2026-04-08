# egon-journal

![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)

Structured journaling support for the [Egon Notebooks](https://egonnotebooks.com) graph.

Generates journal entry nodes, prompt nodes, structured program nodes, and summary templates — all as plain Markdown files with YAML frontmatter, ready to drop into an Obsidian or Logseq vault.

All scripts and notebooks in this repository are meant as *proof-of-concept*.

---

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
# Clone and install
git clone <repo>
cd egon-journal
uv sync

# Configure your graph directories (optional but recommended)
cp .env.example .env
# Edit .env and set EGON_JOURNAL_DIR, EGON_SUMMARIES_DIR, EGON_GRAPH_DIR
```

---

## Reports

Available reports: word count, sentiment, word cloud, weight, resting heart rate, HRV, sleep.

See [reports/README.md](reports/README.md) for full usage instructions.

---

## Environment variables

Set these in `.env` (copy from `.env.example`):

| Variable             | Purpose                                               |
|----------------------|-------------------------------------------------------|
| `EGON_JOURNAL_DIR`   | Where `new-entry` and `report-*` commands read/write  |
| `EGON_SUMMARIES_DIR` | Where `new-summary` writes                            |
| `EGON_GRAPH_DIR`     | Root of your assembled graph (used by `index`)        |

All variables are optional.
Commands fall back to `./generated/` if unset.

---

## Development

```bash
# Install with dev dependencies (pytest, ruff)
uv sync --extra dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=egon --cov-report=term-missing

# Lint
uv run ruff check egon/ tests/
uv run ruff format --check egon/ tests/
```
