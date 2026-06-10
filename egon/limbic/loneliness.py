"""
Loneliness detection from journal text.

Uses ``Tianlin668/loneliness`` — a MentalBERT model fine-tuned on a binary
loneliness classification dataset (from arXiv:2309.13567).  Outputs two
softmax probabilities summing to 1:

    not lonely · lonely

The ``lonely`` probability (0–1) is used as the daily loneliness signal.

Requires the ``limbic`` optional dependency group (same venv as Big Five and Emotion):
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

_MODEL_ID = "Tianlin668/loneliness"
_LIMBIC_VENV = Path(__file__).resolve().parents[2] / ".venv-limbic"

_pipeline = None


class LonelinessScore(NamedTuple):
    """
    Softmax probability for each loneliness class (0–1, sum ≈ 1).
    Field order: not_lonely, lonely.
    """

    not_lonely: float
    lonely: float

    def as_list(self) -> list[float]:
        return list(self)


_NOT_LONELY = LonelinessScore(not_lonely=1.0, lonely=0.0)


def _extract_lonely_prob(pipeline_output: list[dict]) -> LonelinessScore:
    """
    Extract (not_lonely, lonely) from a pipeline output list.

    Handles multiple label naming conventions (e.g. 'lonely'/'not lonely',
    'LABEL_0'/'LABEL_1', '0'/'1').
    """
    by_label = {s["label"].lower(): s["score"] for s in pipeline_output}

    lonely_prob: float | None = None
    for key in ("lonely", "loneliness", "1"):
        if key in by_label:
            lonely_prob = by_label[key]
            break

    if lonely_prob is None:
        # Prefer the label that doesn't contain 'not', 'no', or 'non'
        for label, score in by_label.items():
            if "not" not in label and "no" not in label:
                lonely_prob = score
                break

    if lonely_prob is None:
        # Last resort: treat LABEL_1 or the second label as the positive class
        lonely_prob = by_label.get("label_1", list(by_label.values())[-1])

    not_lonely_prob = 1.0 - lonely_prob
    return LonelinessScore(not_lonely=not_lonely_prob, lonely=lonely_prob)


def _use_subprocess_venv() -> bool:
    return (
        _LIMBIC_VENV.is_dir() and platform.system() == "Darwin" and platform.machine() == "x86_64"
    )


def _score_batch_via_subprocess(texts: list[str]) -> list[LonelinessScore]:
    """Score a batch of texts inside the .venv-limbic Python 3.12 interpreter."""
    python = _LIMBIC_VENV / "bin" / "python"
    script = (
        "import json, sys\n"
        "from transformers import pipeline\n"
        f"clf = pipeline('text-classification', model='{_MODEL_ID}', "
        "return_all_scores=True)\n"
        "texts = json.loads(sys.stdin.read())\n"
        "results = []\n"
        "for scores in clf(texts, truncation=True, max_length=512):\n"
        "    by_label = {s['label'].lower(): s['score'] for s in scores}\n"
        "    lonely = by_label.get('lonely') or by_label.get('loneliness') or by_label.get('1')\n"
        "    if lonely is None:\n"
        "        for k, v in by_label.items():\n"
        "            if 'not' not in k and 'no' not in k:\n"
        "                lonely = v; break\n"
        "    if lonely is None:\n"
        "        lonely = list(by_label.values())[-1]\n"
        "    results.append([1.0 - lonely, lonely])\n"
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
        raise RuntimeError(f"Loneliness detection subprocess failed:\n{exc.stderr}") from exc
    return [LonelinessScore(*row) for row in json.loads(result.stdout.strip())]


def _load_pipeline() -> None:
    global _pipeline
    if _pipeline is not None:
        return
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "The 'transformers' package is required for loneliness scoring.\n"
            "On Linux/Apple Silicon/Windows: uv sync --extra limbic\n"
            "On Intel Mac: bash scripts/setup_limbic.sh"
        ) from exc

    print(
        f"Loading loneliness model '{_MODEL_ID}' (first run downloads ~440 MB) …",
        file=sys.stderr,
    )
    _pipeline = pipeline(
        "text-classification",
        model=_MODEL_ID,
        return_all_scores=True,
        truncation=True,
        max_length=512,
    )


def score_text(text: str) -> LonelinessScore:
    """
    Return a LonelinessScore for *text*.
    Empty text returns not-lonely (lonely=0.0).
    """
    if not text.strip():
        return _NOT_LONELY

    _load_pipeline()
    return _extract_lonely_prob(_pipeline(text)[0])


def loneliness_by_day(
    entries: list[JournalEntry],
) -> list[tuple[date_type, LonelinessScore]]:
    """
    Score each journal entry and return one (date, LonelinessScore) per day.

    Multiple entries on the same date are averaged.
    Results are sorted by date ascending.
    """
    by_date: dict[date_type, list[LonelinessScore]] = defaultdict(list)

    if _use_subprocess_venv():
        all_dates = [e.date for e in entries]
        all_texts = [e.body for e in entries]
        non_empty_indices = [i for i, t in enumerate(all_texts) if t.strip()]
        non_empty_texts = [all_texts[i] for i in non_empty_indices]

        batch_scores: list[LonelinessScore] = []
        if non_empty_texts:
            batch_scores = _score_batch_via_subprocess(non_empty_texts)

        batch_iter = iter(batch_scores)
        for i, (day, text) in enumerate(zip(all_dates, all_texts)):
            score = next(batch_iter) if i in non_empty_indices else _NOT_LONELY
            by_date[day].append(score)
    else:
        for entry in entries:
            by_date[entry.date].append(score_text(entry.body))

    result = []
    for day in sorted(by_date):
        scores_list = by_date[day]
        n = len(scores_list)
        averaged = LonelinessScore(*(sum(s[i] for s in scores_list) / n for i in range(2)))
        result.append((day, averaged))
    return result
