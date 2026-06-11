# egon-journal

[![Tests](https://github.com/Egon-Notebooks/egon-journal/actions/workflows/tests.yml/badge.svg)](https://github.com/Egon-Notebooks/egon-journal/actions/workflows/tests.yml)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)
![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)

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

## Local LLM journal prompts

Generate a personalised journaling question from your recent entries using a local LLM via [Ollama](https://ollama.com).

### Prerequisites

```bash
# 1. Install Ollama (macOS) — use the Cask, not the formula
brew install --cask ollama

# 2. Launch the Ollama app (runs as a menu bar app; starts the server automatically)
open /Applications/Ollama.app

# 3. Install the Python client
uv sync --extra local-llm
```

### Usage

```bash
# Generate a prompt using the last 3 months of entries (default model: llama3.2:3b)
uv run egon suggest-prompt

# Use a different time window
uv run egon suggest-prompt --months 6

# Override the model for this run
uv run egon suggest-prompt --model gemma3:12b

# Specify a journal directory explicitly
uv run egon suggest-prompt --journal-dir ~/my-graph/journal --months 2
```

The model is downloaded automatically from the Ollama library on first use. Subsequent runs are instant (no re-download).

### Configuring the default model

Set your preferred model in `egon.toml` so you don't need `--model` every time:

```toml
[local_llm]
model = "llama3.2:3b"   # default — fast, good quality
# model = "qwen2.5:7b"  # better reasoning, needs ~6 GB RAM
# model = "gemma3:12b"  # best quality, needs ~10 GB RAM
```

See [Ollama's model library](https://ollama.com/library) for all available models.

---

## AI health summary

Generate a narrative summary of your Apple Health data for a time period using a local LLM via Ollama (inspired by [krumjahn/applehealth](https://github.com/krumjahn/applehealth)). Compact per-metric statistics — mean, min, max, trend, and a weekly or monthly breakdown — are computed locally and narrated by the model. No data leaves your device.

Prerequisites are the same as for journal prompts above (Ollama running, `uv sync --extra local-llm`), plus `EGON_APPLE_HEALTH_XML` set in `.env` (or pass `--xml`).

```bash
# Summarise the last complete month (default)
uv run egon health-summary

# A specific quarter, saved as Markdown
uv run egon health-summary --for 2026-Q1 --output ~/health-2026-Q1.md

# Just print the computed statistics without calling the LLM
# (useful for pasting into any LLM chat yourself)
uv run egon health-summary --for 2026-Q1 --stats-only

# Override the model for this run
uv run egon health-summary --model gemma3:12b
```

The full PDF report (`uv run egon report --full`) also uses this: it adds an AI-generated "Health Summary" page to the Physiological Measures section and writes per-figure commentary under each health chart. If Ollama is not running, the report falls back to placeholder text. Both behaviours can be toggled in `egon.toml`:

```toml
[report.analyses]
llm_health_summary    = true   # "Health Summary" page in the full report
llm_health_commentary = true   # per-figure commentary under each health chart
```

Generated text is cached per period alongside the other ML scores (`reports/full-report/.cache/<label>/llm_health.json`); delete that file to force regeneration.

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
