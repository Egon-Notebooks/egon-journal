"""
Emotion detection from journal text.

Uses ``j-hartmann/emotion-english-distilroberta-base`` — a DistilRoBERTa model
fine-tuned on six emotion datasets.  It classifies text into one of seven
discrete emotions:

    anger · disgust · fear · joy · neutral · sadness · surprise

One probability score (0–1) per emotion is returned per entry, derived from the
softmax output over all classes.

Requires the ``bigfive`` optional dependency group (same venv):
  bash scripts/setup_bigfive.sh   # Intel Mac
  uv sync --extra bigfive         # Linux, Apple Silicon, Windows
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

_MODEL_ID = "j-hartmann/emotion-english-distilroberta-base"
_BIGFIVE_VENV = Path(__file__).resolve().parents[2] / ".venv-bigfive"

# Canonical emotion order (alphabetical, matches model label sort)
EMOTIONS: list[str] = ["anger", "disgust", "fear", "joy", "neutral", "sadness", "surprise"]

_pipeline = None


class EmotionScores(NamedTuple):
    """
    Softmax probability for each of the seven emotions (0–1, sum ≈ 1).
    Field order matches EMOTIONS.
    """

    anger: float
    disgust: float
    fear: float
    joy: float
    neutral: float
    sadness: float
    surprise: float

    def as_list(self) -> list[float]:
        return list(self)


_NEUTRAL = EmotionScores(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _use_subprocess_venv() -> bool:
    return (
        _BIGFIVE_VENV.is_dir() and platform.system() == "Darwin" and platform.machine() == "x86_64"
    )


def _score_batch_via_subprocess(texts: list[str]) -> list[EmotionScores]:
    """
    Score a batch of texts inside the .venv-bigfive Python 3.12 interpreter.

    Returns top-1 softmax probabilities for all seven classes per text.
    """
    python = _BIGFIVE_VENV / "bin" / "python"
    script = (
        "import json, sys\n"
        "from transformers import pipeline\n"
        f"clf = pipeline('text-classification', model='{_MODEL_ID}', "
        "return_all_scores=True)\n"
        "texts = json.loads(sys.stdin.read())\n"
        "results = []\n"
        "for scores in clf(texts, truncation=True, max_length=512):\n"
        "    by_label = {s['label']: s['score'] for s in scores}\n"
        f"    results.append([by_label.get(e, 0.0) for e in {EMOTIONS!r}])\n"
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
        raise RuntimeError(f"Emotion subprocess failed:\n{exc.stderr}") from exc
    return [EmotionScores(*row) for row in json.loads(result.stdout.strip())]


def _load_pipeline() -> None:
    global _pipeline
    if _pipeline is not None:
        return
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "The 'transformers' package is required for emotion scoring.\n"
            "On Linux/Apple Silicon/Windows: uv sync --extra bigfive\n"
            "On Intel Mac: bash scripts/setup_bigfive.sh"
        ) from exc

    print(
        f"Loading emotion model '{_MODEL_ID}' (first run downloads ~330 MB) …",
        file=sys.stderr,
    )
    _pipeline = pipeline(
        "text-classification",
        model=_MODEL_ID,
        return_all_scores=True,
        truncation=True,
        max_length=512,
    )


def score_text(text: str) -> EmotionScores:
    """
    Return emotion probability scores for *text*.
    Empty text returns neutral (1.0 for neutral, 0.0 for all others).
    """
    if not text.strip():
        return _NEUTRAL

    _load_pipeline()
    scores = _pipeline(text)[0]
    by_label = {s["label"]: s["score"] for s in scores}
    return EmotionScores(*[by_label.get(e, 0.0) for e in EMOTIONS])


def emotion_by_day(
    entries: list[JournalEntry],
) -> list[tuple[date_type, EmotionScores]]:
    """
    Score each journal entry and return one (date, EmotionScores) per day.

    Multiple entries on the same date are averaged.
    Results are sorted by date ascending.
    """
    by_date: dict[date_type, list[EmotionScores]] = defaultdict(list)

    if _use_subprocess_venv():
        all_dates = [e.date for e in entries]
        all_texts = [e.body for e in entries]
        non_empty_indices = [i for i, t in enumerate(all_texts) if t.strip()]
        non_empty_texts = [all_texts[i] for i in non_empty_indices]

        batch_scores: list[EmotionScores] = []
        if non_empty_texts:
            batch_scores = _score_batch_via_subprocess(non_empty_texts)

        batch_iter = iter(batch_scores)
        for i, (day, text) in enumerate(zip(all_dates, all_texts)):
            score = next(batch_iter) if i in non_empty_indices else _NEUTRAL
            by_date[day].append(score)
    else:
        for entry in entries:
            by_date[entry.date].append(score_text(entry.body))

    result = []
    for day in sorted(by_date):
        scores_list = by_date[day]
        n = len(scores_list)
        averaged = EmotionScores(*(sum(s[i] for s in scores_list) / n for i in range(7)))
        result.append((day, averaged))
    return result
