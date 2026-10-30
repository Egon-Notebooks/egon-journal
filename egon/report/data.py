"""
Collect everything a report needs for one period — once, with no plotting.

Slow model scores (Big Five, MBTI, emotion, cognitive bias, stress,
loneliness) and the local-LLM health text are cached as JSON in
``cache_dir`` so re-running a report is fast.  Delete a cache file to force
re-scoring.  The demo-data generator writes these same cache files, which is
how demo reports are built without running any model.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path
from typing import Any, NamedTuple

from egon.analytics.correlation import Signals
from egon.analytics.loader import JournalEntry
from egon.config import ReportConfig
from egon.health.apple_health import daily_mean, daily_sum, filter_by_date, infer_unit, load_records
from egon.health.sleep import filter_sleep_by_date, load_sleep_onset, load_sleep_records
from egon.limbic.bigfive import BigFiveScores
from egon.limbic.cognitive_bias import CognitiveBiasScores
from egon.limbic.emotion import EMOTIONS, EmotionScores
from egon.limbic.loneliness import LonelinessScore
from egon.limbic.mbti import MBTIScores
from egon.limbic.stress import StressScore

Series = list[tuple[date_type, float]]


def _log(msg: str) -> None:
    print(f"  [report] {msg}")


# ---------------------------------------------------------------------------
# Model scores (cached)
# ---------------------------------------------------------------------------

# Cache file per model score — also written directly by the demo-data generator.

SCORE_CACHE_FILES: dict[str, str] = {
    "bigfive": "bigfive_data.json",
    "mbti": "mbti_data.json",
    "emotion": "emotion_data.json",
    "cognitive_bias": "cognitive_bias_data.json",
    "stress": "stress_data.json",
    "loneliness": "loneliness_data.json",
}


class Scorer(NamedTuple):
    cache_file: str
    score_type: type
    run: Callable[[list[JournalEntry]], list]  # entries -> [(date, scores)]
    config_key: str | None  # None: always scored (feeds correlations)


def _scorers() -> dict[str, Scorer]:
    # Imported lazily so that importing this module never loads model code.
    from egon.limbic.bigfive import bigfive_by_day
    from egon.limbic.cognitive_bias import cognitive_bias_by_day
    from egon.limbic.emotion import emotion_by_day
    from egon.limbic.loneliness import loneliness_by_day
    from egon.limbic.mbti import mbti_by_day
    from egon.limbic.stress import stress_by_day

    return {
        "bigfive": Scorer(SCORE_CACHE_FILES["bigfive"], BigFiveScores, bigfive_by_day, None),
        "mbti": Scorer(SCORE_CACHE_FILES["mbti"], MBTIScores, mbti_by_day, None),
        "emotion": Scorer(SCORE_CACHE_FILES["emotion"], EmotionScores, emotion_by_day, "emotion"),
        "cognitive_bias": Scorer(
            SCORE_CACHE_FILES["cognitive_bias"],
            CognitiveBiasScores,
            cognitive_bias_by_day,
            "cognitive_bias",
        ),
        "stress": Scorer(SCORE_CACHE_FILES["stress"], StressScore, stress_by_day, "stress"),
        "loneliness": Scorer(
            SCORE_CACHE_FILES["loneliness"], LonelinessScore, loneliness_by_day, "loneliness"
        ),
    }


def save_scores(data: list[tuple[date_type, tuple]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([[d.isoformat(), list(s)] for d, s in data]))


def load_scores(path: Path, score_type: type) -> list[tuple[date_type, Any]]:
    return [(date_type.fromisoformat(d), score_type(*s)) for d, s in json.loads(path.read_text())]


def cached_scores(
    name: str, scorer: Scorer, entries: list[JournalEntry], cache_dir: Path
) -> list | None:
    """Load *name* scores from cache, or run the model and cache the result.

    Returns None (and logs why) when the model is unavailable.
    """
    path = cache_dir / scorer.cache_file
    if path.exists():
        try:
            data = load_scores(path, scorer.score_type)
            _log(f"{name}: loaded cached scores")
            return data
        except Exception as exc:
            _log(f"{name}: cache unreadable, re-scoring ({exc})")
    try:
        data = scorer.run(entries)
    except Exception as exc:
        _log(f"{name}: scoring unavailable ({exc})")
        return None
    save_scores(data, path)
    return data


# ---------------------------------------------------------------------------
# Report data
# ---------------------------------------------------------------------------


@dataclass
class HealthSeries:
    data: Series
    unit: str


@dataclass
class ReportData:
    label: str
    start: date_type
    end: date_type
    entries: list[JournalEntry] = field(default_factory=list)
    scores: dict[str, list] = field(default_factory=dict)  # name -> [(date, scores)]
    health: dict[str, HealthSeries] = field(default_factory=dict)  # weight, hrv, ...
    sleep_hours: Series = field(default_factory=list)
    sleep_onset: Series = field(default_factory=list)
    llm_summary: str | None = None
    llm_commentary: dict[str, str] = field(default_factory=dict)
    signals: Signals = field(default_factory=dict)


# Apple Health record type -> (report key, daily aggregate)
HEALTH_METRICS: dict[str, tuple[str, Callable]] = {
    "BodyMass": ("weight", daily_mean),
    "LeanBodyMass": ("lean_mass", daily_mean),
    "RestingHeartRate": ("resting_heart_rate", daily_mean),
    "HeartRateVariabilitySDNN": ("hrv", daily_mean),
    "StepCount": ("steps", daily_sum),
    "AppleExerciseTime": ("exercise", daily_sum),
    "VO2Max": ("vo2max", daily_mean),
}


def health_series(records: dict, start: date_type, end: date_type) -> dict[str, HealthSeries]:
    out: dict[str, HealthSeries] = {}
    for record_type, (key, aggregate) in HEALTH_METRICS.items():
        if recs := records.get(record_type):
            if data := filter_by_date(aggregate(recs), start, end):
                out[key] = HealthSeries(data, infer_unit(recs))
    return out


def build_signals(
    *,
    journal_entries: list[JournalEntry],
    health: dict[str, HealthSeries],
    sleep_hours: Series | None = None,
    sleep_onset: Series | None = None,
    scores: dict[str, list] | None = None,
) -> Signals:
    """All available daily time series, by display name, for correlation analysis."""
    from egon.analytics.word_count import word_counts_by_day
    from egon.limbic.sentiment import sentiment_by_day

    scores = scores or {}
    signals: Signals = {}

    if journal_entries:
        signals["word count"] = [(d, float(v)) for d, v in word_counts_by_day(journal_entries)]
        try:
            signals["sentiment"] = sentiment_by_day(journal_entries)
        except Exception:
            pass

    if data := scores.get("stress"):
        signals["stress"] = [(d, s.stress) for d, s in data]
    if data := scores.get("loneliness"):
        signals["loneliness"] = [(d, s.lonely) for d, s in data]
    if data := scores.get("bigfive"):
        for i, name in enumerate(["B5-O", "B5-C", "B5-E", "B5-A", "B5-N"]):
            signals[name] = [(d, s[i]) for d, s in data]
    if data := scores.get("mbti"):
        for i, name in enumerate(["MBTI E/I", "MBTI N/S", "MBTI T/F", "MBTI J/P"]):
            signals[name] = [(d, float(s[i])) for d, s in data]
    if data := scores.get("emotion"):
        for i, name in enumerate(EMOTIONS):
            signals[f"emo-{name}"] = [(d, s[i]) for d, s in data]

    names = {
        "weight": "weight",
        "lean_mass": "lean mass",
        "resting_heart_rate": "resting HR",
        "hrv": "HRV",
        "steps": "steps",
        "exercise": "exercise (min)",
        "vo2max": "VO₂ max",
    }
    for key, name in names.items():
        if key in health:
            signals[name] = health[key].data
    if sleep_hours:
        signals["sleep (h)"] = sleep_hours
    if sleep_onset:
        signals["sleep onset"] = sleep_onset
    return signals


def _llm_health_text(
    cfg: ReportConfig,
    records: dict,
    xml_path: Path | None,
    start: date_type,
    end: date_type,
    label: str,
    cache_dir: Path,
) -> tuple[str | None, dict[str, str]]:
    want_summary = cfg.enabled("llm_health_summary")
    want_commentary = cfg.enabled("llm_health_commentary")
    if not (want_summary or want_commentary) or not records:
        return None, {}
    cache = cache_dir / "llm_health.json"
    if cache.exists():
        try:
            cached = json.loads(cache.read_text())
            _log("LLM health text: loaded from cache")
            return cached.get("summary"), cached.get("commentary", {})
        except Exception as exc:
            _log(f"LLM cache unreadable, regenerating ({exc})")
    try:
        from egon.config import load_local_llm_config
        from egon.health.llm_summary import (
            build_health_stats,
            format_health_stats,
            generate_health_summary,
            generate_metric_commentary,
        )
        from egon.local_llm import ensure_model

        stats = build_health_stats(records, xml_path, start, end)
        if not stats:
            return None, {}
        model = load_local_llm_config().model
        ensure_model(model)
        summary = None
        commentary: dict[str, str] = {}
        if want_summary:
            _log(f"LLM health summary: generating with {model} …")
            summary = generate_health_summary(format_health_stats(stats, label, start, end), model)
        if want_commentary:
            for s in stats:
                _log(f"LLM commentary: {s.name} …")
                commentary[s.key] = generate_metric_commentary(s, label, model)
        cache.write_text(json.dumps({"summary": summary, "commentary": commentary}))
        return summary, commentary
    except (ImportError, RuntimeError) as exc:
        _log(f"LLM health text unavailable, using placeholders ({exc})")
        return None, {}


def collect_report_data(
    *,
    journal_entries: list[JournalEntry],
    xml_path: Path | None,
    start: date_type,
    end: date_type,
    label: str,
    cache_dir: Path,
    config: ReportConfig,
) -> ReportData:
    cache_dir.mkdir(parents=True, exist_ok=True)
    data = ReportData(label=label, start=start, end=end, entries=journal_entries)

    if journal_entries:
        for name, scorer in _scorers().items():
            if scorer.config_key is None or config.enabled(scorer.config_key):
                if (scores := cached_scores(name, scorer, journal_entries, cache_dir)) is not None:
                    data.scores[name] = scores

    records: dict = {}
    if xml_path and xml_path.is_file():
        try:
            records = load_records(xml_path)
        except Exception as exc:
            _log(f"failed to load Apple Health data ({exc})")
        try:
            data.sleep_hours = filter_sleep_by_date(load_sleep_records(xml_path), start, end)
            data.sleep_onset = filter_sleep_by_date(load_sleep_onset(xml_path), start, end)
        except Exception as exc:
            _log(f"sleep data unavailable ({exc})")
    data.health = health_series(records, start, end)

    data.llm_summary, data.llm_commentary = _llm_health_text(
        config, records, xml_path, start, end, label, cache_dir
    )
    data.signals = build_signals(
        journal_entries=journal_entries,
        health=data.health,
        sleep_hours=data.sleep_hours,
        sleep_onset=data.sleep_onset,
        scores=data.scores,
    )
    return data
