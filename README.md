# egon-journal

[![Tests](https://github.com/Egon-Notebooks/egon-journal/actions/workflows/tests.yml/badge.svg)](https://github.com/Egon-Notebooks/egon-journal/actions/workflows/tests.yml)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)
![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)

Structured journaling support for the [Egon Notebooks](https://egonnotebooks.com) graph.

Two jobs, both fully local:

1. **Journaling nodes** — journal entries, prompts, structured programs and summary templates, as plain
   Markdown files with YAML frontmatter, ready to drop into an Obsidian or Logseq vault.
2. **Reports** — analyzes your journal and Apple Health export on your own device and produces
   interactive HTML reports on mood, stress, personality, sleep, activity and how they relate.

Code layout: `egon/node_types` (graph nodes), `egon/limbic` (the affective engine: emotion, stress,
loneliness, cognitive distortions and personality from local language models), `egon/analytics` and
`egon/health` (journal-text and Apple Health signals), and `egon/report` (the HTML reports).

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

# Configure your graph directories and Apple Health export (optional but recommended)
cp .env.example .env
# Edit .env — see "Environment variables" below
```

---

## Writing journal entries

```bash
# Create an entry for today (written to EGON_JOURNAL_DIR or ./generated/)
uv run egon new-entry

# Backdate an entry
uv run egon new-entry --date 2026-04-01

# Create and open immediately in $EDITOR
uv run egon new-entry --open

# Write to a specific directory
uv run egon new-entry --output ~/my-egon-graph/journal
```

Files are named `Journal — YYYY-MM-DD.md`.

---

## Generating prompts

```bash
# Generate all prompt nodes from content/prompts/*.yaml
uv run egon generate-prompts

# Write to a specific directory
uv run egon generate-prompts --output ~/my-egon-graph/prompts
```

---

## Generating programs

```bash
# List available programs
uv run egon list-programs

# Generate one program by title
uv run egon generate-program --name "14-Day Sleep Improvement"

# Generate all programs
uv run egon generate-all-programs

# Write to a specific directory
uv run egon generate-all-programs --output ~/my-egon-graph/programs
```

Each program produces one index node and one node per day.

---

## Summary templates

```bash
# Weekly summary for the current ISO week
uv run egon new-summary --period week

# Monthly summary for the current month
uv run egon new-summary --period month

# Write to a specific directory
uv run egon new-summary --period week --output ~/my-egon-graph/summaries
```

---

## Validation

```bash
# Validate all generated nodes
uv run egon validate --path ./generated

# Validate a single file
uv run egon validate --path ~/my-egon-graph/journal/Journal\ —\ 2026-04-03.md
```

---

## Local LLM journal prompts

Generate a personalized journaling question from your recent entries using a local LLM via [Ollama](https://ollama.com).

### Prerequisites

```bash
# 1. Install Ollama (macOS) — use the Cask, not the formula
brew install --cask ollama

# 2. Launch the Ollama app (runs as a menu bar app; starts the server automatically)
open /Applications/Ollama.app

# 3. Install the Python client
uv sync --extra local-llm
```

You need **both**: the Ollama app runs the language model on your machine, and the small
`ollama` Python client (installed by `--extra local-llm`) is how egon-journal talks to it.
A plain `uv sync` removes optional extras again, so keep using `uv sync --extra local-llm`
(add `--extra limbic` / `--extra topics` if you use those too).

### Usage

```bash
# Generate a prompt using the last 3 months of entries (default model: qwen2.5:7b)
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
model = "qwen2.5:7b"     # default — strong instruction-following, needs ~6 GB RAM
# model = "llama3.2:3b"  # faster, less RAM, weaker at following instructions
# model = "gemma3:12b"   # best quality, needs ~10 GB RAM
```

See [Ollama's model library](https://ollama.com/library) for all available models.

---

## AI health summary

Generate a narrative summary of your Apple Health data for a time period using a local LLM via Ollama (inspired by [krumjahn/applehealth](https://github.com/krumjahn/applehealth)). Compact per-metric statistics — mean, min, max, trend, and a weekly or monthly breakdown — are computed locally and narrated by the model. No data leaves your device.

Prerequisites are the same as for journal prompts above — the Ollama app running **and** the Python client installed (`uv sync --extra local-llm`) — plus `EGON_APPLE_HEALTH_XML` set in `.env` (or pass `--xml`).

```bash
# Summarize the last complete month (default)
uv run egon health-summary

# A specific quarter, saved as Markdown
uv run egon health-summary --for 2026-Q1 --output ~/health-2026-Q1.md

# Just print the computed statistics without calling the LLM
# (useful for pasting into any LLM chat yourself)
uv run egon health-summary --for 2026-Q1 --stats-only

# Override the model for this run
uv run egon health-summary --model gemma3:12b
```

The full report (`uv run egon report --full`) also uses this: it adds an AI-generated "Health summary" to the Physiological Measures section and writes "This period" commentary under each health chart. If the Ollama client isn't installed or the app isn't
running, these are left out and the terminal says which of the two is missing. Both behaviors can be toggled in `egon.toml`:

```toml
[report.analyses]
llm_health_summary    = true   # "Health summary" note in the full report
llm_health_commentary = true   # per-figure commentary under each health chart
```

Generated text is cached per period alongside the model scores (`reports/full_report/.cache/<period>/llm_health.json`); delete that file to force regeneration.

---

## LLM context export

```bash
# Export last 3 months of journal entries to stdout (paste into an LLM chat)
uv run egon export-context

# Export a specific number of months
uv run egon export-context --months 6

# Write to a file instead
uv run egon export-context --months 3 --output ~/context.md

# Use a specific journal directory
uv run egon export-context --journal-dir ~/my-egon-graph/journal --months 2
```

Output is a single Markdown file with a `## YYYY-MM-DD` heading before each entry, suitable for pasting directly into an LLM chat as context.

---

## Wikilink injection

```bash
# Index all titles in your graph (pipe to TOPICS.txt)
uv run egon index --graph-dir ~/my-egon-graph > TOPICS.txt

# Inject wikilinks into a journal entry
uv run egon link ~/my-egon-graph/journal/Journal\ —\ 2026-04-03.md
```

The linker matches topic titles from `TOPICS.txt` and wraps bare mentions in `[[double brackets]]`.

---

## Reports

Reports are **interactive, self-contained HTML pages** — one file per report with
every chart, its data and the fonts inlined. They open in any browser, work fully
offline and never make a network request, so your data stays on your device.
Hover for exact values, drag to zoom into a stretch of time, click legends to
isolate a series, and switch between light and dark mode. For a paper copy or to
share by email, use your browser's **Print → Save as PDF** (the layout is designed
for A4).

Every chart comes with a short note on **why it matters for mental health and
wellbeing**, how to read it, and a data table.

```bash
# Every chart for a quarter, plus one combined report
uv run egon report --for 2026-Q1 --full      # → reports/full_report/2026-Q1.html

# The last complete month
uv run egon report --period month --full
```

The terminal shows one line per report (✓ generated, – skipped with the reason),
which model scores were loaded from cache or computed, and where the combined
report was written. Model scores are cached per period in
`reports/full_report/.cache/<period>/` and shared by all report commands, so each
model runs at most once per period; delete a file there to re-score.

Available charts: word count, frequent words, first-person pronoun ratio, topics,
sentiment, stress, loneliness, emotion, cognitive distortions, Big Five, MBTI,
weight, resting heart rate, HRV, sleep, steps, exercise, VO₂ max, and cross-signal
correlations.

See [reports/README.md](reports/README.md) for full usage instructions. Charts are
built with [Vega-Lite](https://vega.github.io/vega-lite/) via
[Altair](https://altair-viz.github.io/); the visual language is described in the
product docs (`docs/DESIGN_LANGUAGE.md` → *Data visualization*).

---

## Environment variables

Set these in `.env` (copy from `.env.example`):

| Variable                          | Purpose                                                    |
|-----------------------------------|------------------------------------------------------------|
| `EGON_JOURNAL_DIR`                | Where `new-entry` writes and reports read journal entries  |
| `EGON_SUMMARIES_DIR`              | Where `new-summary` writes                                 |
| `EGON_GRAPH_DIR`                  | Root of your assembled graph (used by `index`)             |
| `EGON_APPLE_HEALTH_XML`           | Apple Health `export.xml`, used by health reports          |
| `EGON_TARGET_BODY_MASS`           | Optional target line on the weight chart                   |
| `EGON_TARGET_LEAN_BODY_MASS`      | Optional target line on the lean-mass panel                |
| `EGON_TARGET_RESTING_HEART_RATE`  | Optional target line on the resting heart rate chart       |
| `EGON_TARGET_EXERCISE_MINUTES`    | Daily exercise target (replaces the WHO 30-minute line)    |

All variables are optional.
Node commands fall back to `./generated/` if unset; health reports are skipped
without an Apple Health export.

---

## Optional extras

Three optional dependency groups add analysis features. Install them alongside the base package:

**Local language models (`limbic`)** — Hugging Face models that score journal text for
emotion, stress, loneliness, cognitive distortions, Big Five and MBTI:

```bash
uv sync --extra limbic         # Linux, Apple Silicon, Windows
bash scripts/setup_limbic.sh   # Intel Mac (creates .venv-limbic; used automatically)
```

Requires `transformers`, `torch`, `sentencepiece`, and `protobuf`. Models run locally and are
downloaded once on first use; no journal data leaves the device.

**Topic modeling** — uses BERTopic to cluster journal entries into recurring themes:

```bash
uv sync --extra topics
```

Requires `bertopic` and `sentence-transformers` (on Intel Macs topics run via `.venv-limbic`).
Turn off in `egon.toml` with `topics = false` under `[report.analyses]`.

**Local LLM (`local-llm`)** — the Ollama client for `suggest-prompt`, `health-summary` and the AI
commentary in reports (see above):

```bash
uv sync --extra local-llm
```

All extras are opt-in and not required for core journaling functionality.

---

## Development

```bash
# Install with dev dependencies (pytest, ruff)
uv sync --all-groups

# Run tests (the full suite takes ~5 minutes: some tests run the real models)
uv run pytest

# Lint
uv run ruff check egon/ tests/
uv run ruff format --check egon/ tests/
```

## References

[krumjahn/applehealth](https://github.com/krumjahn/applehealth)
