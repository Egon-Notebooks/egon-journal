#!/usr/bin/env bash
# Sets up a Python 3.12 venv for Big Five / MBTI / emotion / topic inference.
# Required on Intel Mac because PyTorch dropped Intel Mac support after 2.2,
# and torch 2.2 only ships wheels for Python ≤ 3.12.
#
# Run once:
#   bash scripts/setup_bigfive.sh
#
# After setup the bigfive venv lives at .venv-bigfive/ and all ML report
# commands will use it automatically.

set -euo pipefail

VENV=".venv-bigfive"
PYTHON="$(uv python find 3.12 2>/dev/null || echo "")"

if [ -z "$PYTHON" ]; then
  echo "Python 3.12 not found locally — downloading via uv..."
  uv python install 3.12
  PYTHON="$(uv python find 3.12)"
fi

echo "Using Python: $PYTHON"
echo "Creating venv at $VENV ..."
uv venv "$VENV" --python "$PYTHON" --seed

echo "Installing torch 2.2 + transformers + sentence-transformers ..."
# torch 2.2 was compiled against numpy 1.x — pin numpy<2 to avoid ABI crash.
# transformers 4.45+ requires torch>=2.4 — pin below that threshold.
uv pip install --quiet --python "$VENV/bin/python" \
  "torch==2.2.2" \
  "numpy<2" \
  "transformers>=4.40,<4.45" \
  "huggingface_hub>=0.23" \
  "sentencepiece" \
  "protobuf" \
  "sentence-transformers>=2.2,<3"

echo "Installing scikit-learn (for topic modelling) ..."
# Topic modelling on Intel Mac uses pure-sklearn NMF — no BERTopic, umap-learn,
# numba, or llvmlite required.
uv pip install --quiet --python "$VENV/bin/python" \
  "scikit-learn>=1.3"

echo ""
echo "Done. Big Five / MBTI / emotion / topics venv ready at $VENV"
echo "All report commands that need ML models will use it automatically."
