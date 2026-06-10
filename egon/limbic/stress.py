"""
Psychological stress detection from journal text.

Uses ``jnyx74/stress-prediction`` — a DistilBERT model fine-tuned on the
Dreaddit dataset (Reddit posts labelled for psychological stress).  Outputs
two softmax probabilities summing to 1:

    no stress · stress

The ``stress`` probability (0–1) is used as the daily stress signal.

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

_MODEL_ID = "jnyx74/stress-prediction"
_LIMBIC_VENV = Path(__file__).resolve().parents[2] / ".venv-limbic"

# Canonical label order — stress probability is always extracted by label name.
_STRESS_LABELS = ("no stress", "stress")

_pipeline = None


class StressScore(NamedTuple):
    """
    Softmax probability for each stress class (0–1, sum ≈ 1).
    Field order: no_stress, stress.
    """

    no_stress: float
    stress: float

    def as_list(self) -> list[float]:
        return list(self)


_NO_STRESS = StressScore(no_stress=1.0, stress=0.0)


def _extract_stress_prob(pipeline_output: list[dict]) -> StressScore:
    """
    Extract (no_stress, stress) from a pipeline output list.

    Handles multiple label naming conventions used by Dreaddit-trained models
    (e.g. 'stress'/'no stress', 'LABEL_0'/'LABEL_1', '0'/'1').
    """
    by_label = {s["label"].lower(): s["score"] for s in pipeline_output}

    # Try to find the stress probability directly
    stress_prob: float | None = None
    for key in ("stress",):
        if key in by_label:
            stress_prob = by_label[key]
            break

    if stress_prob is None:
        # Fallback: the label that doesn't contain 'no' or 'not' is the stress label
        for label, score in by_label.items():
            if "no" not in label and "not" not in label:
                stress_prob = score
                break

    if stress_prob is None:
        # Last resort: treat LABEL_1 or the second label as stress
        stress_prob = by_label.get("label_1", list(by_label.values())[-1])

    no_stress_prob = 1.0 - stress_prob
    return StressScore(no_stress=no_stress_prob, stress=stress_prob)


def _use_subprocess_venv() -> bool:
    return (
        _LIMBIC_VENV.is_dir() and platform.system() == "Darwin" and platform.machine() == "x86_64"
    )


def _score_batch_via_subprocess(texts: list[str]) -> list[StressScore]:
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
        "    stress = by_label.get('stress')\n"
        "    if stress is None:\n"
        "        for k, v in by_label.items():\n"
        "            if 'no' not in k and 'not' not in k:\n"
        "                stress = v; break\n"
        "    if stress is None:\n"
        "        stress = list(by_label.values())[-1]\n"
        "    results.append([1.0 - stress, stress])\n"
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
        raise RuntimeError(f"Stress detection subprocess failed:\n{exc.stderr}") from exc
    return [StressScore(*row) for row in json.loads(result.stdout.strip())]


def _load_pipeline() -> None:
    global _pipeline
    if _pipeline is not None:
        return
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "The 'transformers' package is required for stress scoring.\n"
            "On Linux/Apple Silicon/Windows: uv sync --extra limbic\n"
            "On Intel Mac: bash scripts/setup_limbic.sh"
        ) from exc

    print(
        f"Loading stress model '{_MODEL_ID}' (first run downloads ~250 MB) …",
        file=sys.stderr,
    )
    _pipeline = pipeline(
        "text-classification",
        model=_MODEL_ID,
        return_all_scores=True,
        truncation=True,
        max_length=512,
    )


def score_text(text: str) -> StressScore:
    """
    Return a StressScore for *text*.
    Empty text returns no-stress (stress=0.0).
    """
    if not text.strip():
        return _NO_STRESS

    _load_pipeline()
    return _extract_stress_prob(_pipeline(text)[0])


def stress_by_day(
    entries: list[JournalEntry],
) -> list[tuple[date_type, StressScore]]:
    """
    Score each journal entry and return one (date, StressScore) per day.

    Multiple entries on the same date are averaged.
    Results are sorted by date ascending.
    """
    by_date: dict[date_type, list[StressScore]] = defaultdict(list)

    if _use_subprocess_venv():
        all_dates = [e.date for e in entries]
        all_texts = [e.body for e in entries]
        non_empty_indices = [i for i, t in enumerate(all_texts) if t.strip()]
        non_empty_texts = [all_texts[i] for i in non_empty_indices]

        batch_scores: list[StressScore] = []
        if non_empty_texts:
            batch_scores = _score_batch_via_subprocess(non_empty_texts)

        batch_iter = iter(batch_scores)
        for i, (day, text) in enumerate(zip(all_dates, all_texts)):
            score = next(batch_iter) if i in non_empty_indices else _NO_STRESS
            by_date[day].append(score)
    else:
        for entry in entries:
            by_date[entry.date].append(score_text(entry.body))

    result = []
    for day in sorted(by_date):
        scores_list = by_date[day]
        n = len(scores_list)
        averaged = StressScore(*(sum(s[i] for s in scores_list) / n for i in range(2)))
        result.append((day, averaged))
    return result
