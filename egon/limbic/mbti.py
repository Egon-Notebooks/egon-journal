"""
MBTI personality type classification from journal text.

Uses `JanSt/albert-base-v2_mbti-classification` — an ALBERT-based model that
predicts one of 16 MBTI types from free text.

The predicted type is decomposed into 4 binary dimensions for analysis:
  E/I — Extraversion (1) / Introversion (0)
  N/S — iNtuition (1) / Sensing (0)
  T/F — Thinking (1) / Feeling (0)
  J/P — Judging (1) / Perceiving (0)

Requires the `limbic` optional dependency group (same venv as Big Five):
  bash scripts/setup_limbic.sh   # Intel Mac
  uv sync --extra limbic         # Linux, Apple Silicon, Windows
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

_MODEL_ID = "JanSt/albert-base-v2_mbti-classification"
_LIMBIC_VENV = Path(__file__).resolve().parents[2] / ".venv-limbic"

# 4 MBTI dimensions: (positive_letter, negative_letter, display_label)
DIMENSIONS: list[tuple[str, str, str]] = [
    ("E", "I", "E / I"),
    ("N", "S", "N / S"),
    ("T", "F", "T / F"),
    ("J", "P", "J / P"),
]

# Lazy-loaded pipeline
_pipeline = None


class MBTIScores(NamedTuple):
    """
    4 binary dimension scores derived from a predicted MBTI type.
    Each value is 1 (first/positive pole) or 0 (second/negative pole):
      ei: E=1, I=0
      ns: N=1, S=0
      tf: T=1, F=0
      jp: J=1, P=0
    """

    ei: int
    ns: int
    tf: int
    jp: int

    def as_list(self) -> list[int]:
        return list(self)


def _type_to_scores(mbti_type: str) -> MBTIScores:
    """Convert a 4-letter MBTI type string to binary dimension scores."""
    mbti_type = mbti_type.strip().upper()
    return MBTIScores(
        ei=1 if mbti_type[0] == "E" else 0,
        ns=1 if mbti_type[1] == "N" else 0,
        tf=1 if mbti_type[2] == "T" else 0,
        jp=1 if mbti_type[3] == "J" else 0,
    )


def _use_subprocess_venv() -> bool:
    return (
        _LIMBIC_VENV.is_dir() and platform.system() == "Darwin" and platform.machine() == "x86_64"
    )


def _score_batch_via_subprocess(texts: list[str]) -> list[MBTIScores]:
    """
    Score a batch of texts inside the .venv-limbic Python 3.12 interpreter.

    The pipeline is loaded **once** per call; the transformers pipeline accepts
    a list of texts natively for efficient batch inference.  Texts are passed
    as a JSON array via stdin; a JSON array of MBTI type strings is returned.
    """
    python = _LIMBIC_VENV / "bin" / "python"
    script = (
        "import json, sys\n"
        "from transformers import pipeline\n"
        f"clf = pipeline('text-classification', model='{_MODEL_ID}')\n"
        "texts = json.loads(sys.stdin.read())\n"
        "labels = [r['label'] for r in clf(texts, truncation=True, max_length=512)]\n"
        "print(json.dumps(labels))\n"
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
        raise RuntimeError(f"MBTI subprocess failed:\n{exc.stderr}") from exc
    return [_type_to_scores(label) for label in json.loads(result.stdout.strip())]


def _load_pipeline() -> None:
    global _pipeline
    if _pipeline is not None:
        return
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "The 'transformers' package is required for MBTI scoring.\n"
            "On Linux/Apple Silicon/Windows: uv sync --extra limbic\n"
            "On Intel Mac: bash scripts/setup_limbic.sh"
        ) from exc

    print(f"Loading MBTI model '{_MODEL_ID}' (first run downloads ~45 MB) …", file=sys.stderr)
    _pipeline = pipeline(
        "text-classification",
        model=_MODEL_ID,
        truncation=True,
        max_length=512,
    )


def score_text(text: str) -> MBTIScores:
    """
    Return MBTI dimension scores for *text*.
    Empty text returns neutral (0 for all dimensions).

    For batch scoring (the common case) prefer ``mbti_by_day()``, which
    loads the model only once regardless of how many entries are processed.
    """
    if not text.strip():
        return MBTIScores(0, 0, 0, 0)

    _load_pipeline()
    result = _pipeline(text)
    return _type_to_scores(result[0]["label"])


def mbti_by_day(
    entries: list[JournalEntry],
) -> list[tuple[date_type, MBTIScores]]:
    """
    Score each journal entry and return one (date, MBTIScores) per day.

    On Intel Mac (subprocess venv path) all entries are scored in a single
    subprocess call so the model is loaded only once.  On other platforms the
    pipeline is loaded once via ``_load_pipeline()`` and kept in memory.

    When multiple entries exist for the same date, dimension scores are averaged
    (fractional values represent mixed signals within a day).
    Results are sorted by date ascending.
    """
    by_date: dict[date_type, list[MBTIScores]] = defaultdict(list)

    if _use_subprocess_venv():
        # Batch path: one subprocess launch, one model load, all texts scored.
        _neutral = MBTIScores(0, 0, 0, 0)
        all_dates = [e.date for e in entries]
        all_texts = [e.body for e in entries]

        non_empty_indices = [i for i, t in enumerate(all_texts) if t.strip()]
        non_empty_texts = [all_texts[i] for i in non_empty_indices]

        batch_scores: list[MBTIScores] = []
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
        averaged = MBTIScores(*(sum(s[i] for s in scores_list) / n for i in range(4)))
        result.append((day, averaged))
    return result
