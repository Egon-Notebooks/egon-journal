"""
Big Five personality trait scoring from journal text.

Uses `vladinc/bigfive-regression-model` — a DistilBERT-based regression model
trained on the Essays Big5 dataset. Outputs 5 continuous scores in [0, 1] for:
  O — Openness
  C — Conscientiousness
  E — Extraversion
  A — Agreeableness
  N — Neuroticism

Requires torch + transformers.  Two installation paths:

  Standard (Linux x86_64, Apple Silicon, Windows):
    uv sync --extra bigfive

  Intel Mac (PyTorch ≥2.3 dropped x86_64 Mac; torch 2.2 requires Python ≤3.12):
    bash scripts/setup_bigfive.sh   # creates .venv-bigfive/ with Python 3.12 + torch 2.2

When .venv-bigfive/ exists in the project root, scoring automatically delegates
to it via subprocess so the main project venv is unaffected.

The model is downloaded on first use (~270 MB) and cached at ~/.cache/huggingface/.
"""

import json
import platform
import subprocess
import sys
from collections import defaultdict
from datetime import date as date_type
from pathlib import Path
from typing import NamedTuple

from egon.analytics.loader import JournalEntry

_MODEL_ID = "vladinc/bigfive-regression-model"

# Path to the optional Python 3.12 venv used on Intel Mac
_BIGFIVE_VENV = Path(__file__).resolve().parents[2] / ".venv-bigfive"

# Trait order as returned by the model
TRAITS: list[tuple[str, str]] = [
    ("O", "Openness"),
    ("C", "Conscientiousness"),
    ("E", "Extraversion"),
    ("A", "Agreeableness"),
    ("N", "Neuroticism"),
]

# Lazy-loaded globals — initialised on first call to score_text()
_tokenizer = None
_model = None


class BigFiveScores(NamedTuple):
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float

    def as_list(self) -> list[float]:
        return list(self)


def _use_subprocess_venv() -> bool:
    """True when we should delegate to the .venv-bigfive subprocess venv."""
    return (
        _BIGFIVE_VENV.is_dir() and platform.system() == "Darwin" and platform.machine() == "x86_64"
    )


def _score_batch_via_subprocess(texts: list[str]) -> list[BigFiveScores]:
    """
    Score a batch of texts inside the .venv-bigfive Python 3.12 interpreter.

    The model is loaded **once** per call; all texts are scored in a single
    subprocess invocation.  Texts are passed as a JSON array via stdin;
    a JSON array of score lists is returned on stdout.
    """
    python = _BIGFIVE_VENV / "bin" / "python"
    script = (
        "import json, sys\n"
        "from transformers import AutoTokenizer, AutoModelForSequenceClassification\n"
        "import torch\n"
        f"tok = AutoTokenizer.from_pretrained('{_MODEL_ID}')\n"
        f"mdl = AutoModelForSequenceClassification.from_pretrained('{_MODEL_ID}')\n"
        "mdl.eval()\n"
        "texts = json.loads(sys.stdin.read())\n"
        "results = []\n"
        "for text in texts:\n"
        "    inp = tok(text, return_tensors='pt', truncation=True, max_length=512)\n"
        "    with torch.no_grad():\n"
        "        logits = mdl(**inp).logits.squeeze().tolist()\n"
        "    results.append(logits)\n"
        "print(json.dumps(results))\n"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", script],
            input=json.dumps(texts),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Big Five subprocess failed:\n{exc.stderr}") from exc
    return [BigFiveScores(*scores) for scores in json.loads(result.stdout.strip())]


def _load_model() -> None:
    global _tokenizer, _model
    if _tokenizer is not None:
        return
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise ImportError(
            "The 'transformers' package is required for Big Five scoring.\n"
            "On Linux/Apple Silicon/Windows: uv sync --extra bigfive\n"
            "On Intel Mac: bash scripts/setup_bigfive.sh"
        ) from exc

    import torch  # noqa: F401 — verify torch is available too

    print(f"Loading Big Five model '{_MODEL_ID}' (first run downloads ~270 MB) …", file=sys.stderr)
    _tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
    _model = AutoModelForSequenceClassification.from_pretrained(_MODEL_ID)
    _model.eval()


def score_text(text: str) -> BigFiveScores:
    """
    Return Big Five trait scores for *text* as a BigFiveScores namedtuple.
    Empty text returns 0.5 for all traits (neutral).
    Text is truncated to 512 tokens (model maximum).

    For batch scoring (the common case) prefer ``bigfive_by_day()``, which
    loads the model only once regardless of how many entries are processed.
    """
    if not text.strip():
        return BigFiveScores(0.5, 0.5, 0.5, 0.5, 0.5)

    _load_model()

    import torch

    inputs = _tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    with torch.no_grad():
        logits = _model(**inputs).logits.squeeze().tolist()

    # Raw logits are returned as-is. The model outputs values in roughly [2, 5]
    # rather than [0, 1] — relative day-to-day variation is more informative
    # than absolute values.
    return BigFiveScores(*logits)


def bigfive_by_day(
    entries: list[JournalEntry],
) -> list[tuple[date_type, BigFiveScores]]:
    """
    Score each journal entry and return one (date, BigFiveScores) per day.

    On Intel Mac (subprocess venv path) all entries are scored in a single
    subprocess call so the model is loaded only once.  On other platforms the
    model is loaded once via ``_load_model()`` and kept in memory.

    If multiple entries exist for the same date, their trait scores are averaged.
    Results are sorted by date ascending.
    """
    by_date: dict[date_type, list[BigFiveScores]] = defaultdict(list)

    if _use_subprocess_venv():
        # Batch path: one subprocess launch, one model load, all texts scored.
        _neutral = BigFiveScores(0.5, 0.5, 0.5, 0.5, 0.5)
        all_dates = [e.date for e in entries]
        all_texts = [e.body for e in entries]

        non_empty_indices = [i for i, t in enumerate(all_texts) if t.strip()]
        non_empty_texts = [all_texts[i] for i in non_empty_indices]

        batch_scores: list[BigFiveScores] = []
        if non_empty_texts:
            batch_scores = _score_batch_via_subprocess(non_empty_texts)

        batch_iter = iter(batch_scores)
        for i, (day, text) in enumerate(zip(all_dates, all_texts)):
            score = next(batch_iter) if i in non_empty_indices else _neutral
            by_date[day].append(score)
    else:
        for entry in entries:
            by_date[entry.date].append(score_text(entry.body))

    result = []
    for day in sorted(by_date):
        scores_list = by_date[day]
        n = len(scores_list)
        averaged = BigFiveScores(*(sum(s[i] for s in scores_list) / n for i in range(5)))
        result.append((day, averaged))
    return result
