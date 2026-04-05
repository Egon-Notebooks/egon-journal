# egon-journal

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

