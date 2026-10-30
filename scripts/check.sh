#!/usr/bin/env bash
# Run the same checks as CI (.github/workflows/lint.yml and tests.yml), in a
# throwaway Python 3.13 environment with only the base and dev dependencies —
# no optional extras, no .env. Your project .venv is not touched.
#
#   bash scripts/check.sh             # lint, format check, tests (with coverage, as in CI)
#   bash scripts/check.sh -k report   # extra arguments are passed to pytest
set -euo pipefail
cd "$(dirname "$0")/.."

run() { uv run --isolated --python 3.13 --group dev "$@"; }

echo "→ ruff check"
run ruff check egon/ tests/
echo "→ ruff format --check"
run ruff format --check egon/ tests/
echo "→ pytest (Python 3.13, no optional extras)"
run pytest -q "$@"
