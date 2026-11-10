# egon-journal

Journaling CLI for the Egon graph: entries, prompts, local language models
and interactive HTML reports. Workspace-wide rules (privacy, docs sync, American
English, git conventions) are in `../CLAUDE.md`; product docs are in `../docs/`.

## Commands

```bash
uv sync --all-groups --extra local-llm     # install (Python 3.13+); plain `uv sync` drops extras
bash scripts/check.sh                      # exactly what CI runs — do this before every push
uv run pytest --no-cov                     # quick local test run (~45 s)
uv run egon --help                         # all commands
```

- `scripts/check.sh` runs ruff, the format check and pytest in a throwaway Python 3.13
  environment with no optional extras and no `.env` — the same as CI. Your `.venv` is
  untouched. Enable the hooks once per clone with `git config core.hooksPath .githooks`: pre-commit
  blocks personal data (see `.githooks/pre-commit`), pre-push runs `check.sh`.
- `tests/conftest.py` makes every test hermetic: all `EGON_*` variables are removed,
  each test runs in its own temp directory (so real `reports/` and caches are never
  read or written), and the optional extras (models, BERTopic, Ollama) are hidden.
  Never weaken this — a test that passes only on a machine with personal data or
  models installed will fail in CI. `EGON_TEST_MODELS=1 uv run pytest` runs against
  the real models instead.
- CI (`.github/workflows/`) runs only on pushes and pull requests to `main`.

## Layout

- `egon/node_types/`, `schema.py`, `linker.py` — Markdown node generation.
- `egon/analytics/`, `egon/limbic/`, `egon/health/` — signals from journal text,
  local models and Apple Health. No plotting code here.
- `egon/report/` — the HTML report pipeline:
  - `data.py` collects all data for a period once and caches slow model scores and
    LLM text as JSON in `<reports dir>/full_report/.cache/<period>/` — shared with the
    single-chart model commands, so each model runs at most once per period.
  - `charts/` — one pure function per chart returning a Vega-Lite spec (Altair).
  - `figures.py` — pairs each chart with caption, *why it matters for wellbeing*,
    *how to read this* and a data table. Every figure needs all of these.
  - `html.py` + `templates/` + `static/` — the self-contained page shell.
  - `theme.py` — palette and chart config. Colors are authored in light mode; the
    page swaps them for dark mode via `DARK_MAP`, so every hex in a spec must be in it.
- `egon/full_report.py` — assembles the multi-section report.
- `egon/analytics/export.py` — all journal entries in one Markdown file, used by
  `export-context` and by `egon report` (`<reports dir>/journal_entries/<period>.md`).
- `egon/safety.py` — the synthetic safety test set. `egon safety-check` runs it against
  Ollama and writes a review file to `<reports dir>/safety/`; a person reviews it before
  each release. Add new model features to it. Not run in CI.
- `egon/journal_summary.py` — AI summary of a period's entries (`llm_journal_summary`), cached
  with a hash of the entries. `egon report --share` uses `[report.share]` in `egon.toml`.
- `egon/risk.py` — fixed phrase list and the short risk note. Any model feature that reads
  journal entries must go through `entries_for_reflection`.
- `egon report <name>` runs one analysis; the old `report-<name>` commands are hidden
  deprecated aliases. Add new ones to `_SINGLE_REPORTS` in `egon/cli.py`.
- `egon.toml` — which analyses the full report includes; `.env` — user paths and targets.
- Report locations: always go through `egon.config.reports_dir()` (`$EGON_REPORTS_DIR`,
  else `./reports`); never hard-code `reports/` paths.
- Demo reports: `egon demo-report --data ../egon-content/generated_content/demo/<persona>`
  (see reports/README.md → Demo reports). Never build a demo from anything but
  egon-content's synthetic personas; the command enforces the synthetic-data marker.

## Things to know

- **Privacy:** `.env`, `reports/` and `EGON_*` directories point at the user's real
  data. Never read them into commits, examples, screenshots or tests. `reports/` is
  git-ignored. Demo reports must use synthetic data.
- **Reports are offline:** never add CDN links or network requests to the HTML shell.
  Vega bundles and fonts are vendored in `egon/report/static/` (versions must match
  `altair.VEGALITE_VERSION`; see `THIRD_PARTY_NOTICES.md`).
- **Palette changes** must be re-validated for color-vision deficiency and contrast
  in both light and dark mode; slot order is part of the validation.
- **Vega-Lite 6 quirks** (each cost real debugging time; comments in `charts/_common.py`):
  - no `formatType: "utc"` on axes — use a UTC scale;
  - tooltips on nearest-point layers need temporal fields, not nominal ones;
  - daily bars use explicit `x`/`x2` timestamps with `orient="vertical"` and no
    `cornerRadiusEnd`;
  - only one scale-bound zoom per shared axis — pass `zoom=False` in stacked panels;
  - `width: "container"` works only for single views; `static/report.js` sizes
    concatenated views.
- **Verify charts visually:** render a report and look at it in a browser (light and
  dark) before calling chart work done; specs can validate and still draw nothing.
- Intel Macs run models through `.venv-limbic` (`bash scripts/setup_limbic.sh`);
  elsewhere `uv sync --extra limbic`.
