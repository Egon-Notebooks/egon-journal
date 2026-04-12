"""
Cognitive bias detection from journal text.

Uses ``amedvedev/bert-tiny-cognitive-bias`` — a BERT-tiny model trained to classify
text into one of eight cognitive distortion categories:

    NO DISTORTION · PERSONALIZATION · EMOTIONAL REASONING · OVERGENERALIZING
    LABELING · SHOULD STATEMENTS · CATASTROPHIZING · REWARD FALLACY

One probability score (0–1) per class is returned per entry, derived from the
softmax output over all classes.

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

_MODEL_ID = "amedvedev/bert-tiny-cognitive-bias"
_LIMBIC_VENV = Path(__file__).resolve().parents[2] / ".venv-limbic"

# Canonical label order — matches the model's id2label mapping.
BIASES: list[str] = [
    "NO DISTORTION",
    "PERSONALIZATION",
    "EMOTIONAL REASONING",
    "OVERGENERALIZING",
    "LABELING",
    "SHOULD STATEMENTS",
    "CATASTROPHIZING",
    "REWARD FALLACY",
]

# The 7 distortion types (all except NO DISTORTION), used for plotting.
DISTORTION_TYPES: list[str] = BIASES[1:]

_pipeline = None


class CognitiveBiasScores(NamedTuple):
    """
    Softmax probability for each of the eight cognitive bias classes (0–1, sum ≈ 1).
    Field order matches BIASES.
    """

    no_distortion: float
    personalization: float
    emotional_reasoning: float
    overgeneralizing: float
    labeling: float
    should_statements: float
    catastrophizing: float
    reward_fallacy: float

    def as_list(self) -> list[float]:
        return list(self)

    @property
    def distortion_score(self) -> float:
        """Overall distortion signal: 1 − no_distortion probability."""
        return 1.0 - self.no_distortion


_NO_DISTORTION = CognitiveBiasScores(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def _use_subprocess_venv() -> bool:
    return (
        _LIMBIC_VENV.is_dir() and platform.system() == "Darwin" and platform.machine() == "x86_64"
    )


def _score_batch_via_subprocess(texts: list[str]) -> list[CognitiveBiasScores]:
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
        "    by_label = {s['label']: s['score'] for s in scores}\n"
        f"    results.append([by_label.get(b, 0.0) for b in {BIASES!r}])\n"
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
        raise RuntimeError(f"Cognitive bias subprocess failed:\n{exc.stderr}") from exc
    return [CognitiveBiasScores(*row) for row in json.loads(result.stdout.strip())]


def _load_pipeline() -> None:
    global _pipeline
    if _pipeline is not None:
        return
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "The 'transformers' package is required for cognitive bias scoring.\n"
            "On Linux/Apple Silicon/Windows: uv sync --extra limbic\n"
            "On Intel Mac: bash scripts/setup_limbic.sh"
        ) from exc

    print(
        f"Loading cognitive bias model '{_MODEL_ID}' (first run downloads ~17 MB) …",
        file=sys.stderr,
    )
    _pipeline = pipeline(
        "text-classification",
        model=_MODEL_ID,
        return_all_scores=True,
        truncation=True,
        max_length=512,
    )


def score_text(text: str) -> CognitiveBiasScores:
    """
    Return cognitive bias probability scores for *text*.
    Empty text returns no-distortion (1.0 for no_distortion, 0.0 for all others).
    """
    if not text.strip():
        return _NO_DISTORTION

    _load_pipeline()
    scores = _pipeline(text)[0]
    by_label = {s["label"]: s["score"] for s in scores}
    return CognitiveBiasScores(*[by_label.get(b, 0.0) for b in BIASES])


def cognitive_bias_by_day(
    entries: list[JournalEntry],
) -> list[tuple[date_type, CognitiveBiasScores]]:
    """
    Score each journal entry and return one (date, CognitiveBiasScores) per day.

    Multiple entries on the same date are averaged.
    Results are sorted by date ascending.
    """
    by_date: dict[date_type, list[CognitiveBiasScores]] = defaultdict(list)

    if _use_subprocess_venv():
        all_dates = [e.date for e in entries]
        all_texts = [e.body for e in entries]
        non_empty_indices = [i for i, t in enumerate(all_texts) if t.strip()]
        non_empty_texts = [all_texts[i] for i in non_empty_indices]

        batch_scores: list[CognitiveBiasScores] = []
        if non_empty_texts:
            batch_scores = _score_batch_via_subprocess(non_empty_texts)

        batch_iter = iter(batch_scores)
        for i, (day, text) in enumerate(zip(all_dates, all_texts)):
            score = next(batch_iter) if i in non_empty_indices else _NO_DISTORTION
            by_date[day].append(score)
    else:
        for entry in entries:
            by_date[entry.date].append(score_text(entry.body))

    result = []
    for day in sorted(by_date):
        scores_list = by_date[day]
        n = len(scores_list)
        averaged = CognitiveBiasScores(*(sum(s[i] for s in scores_list) / n for i in range(8)))
        result.append((day, averaged))
    return result
