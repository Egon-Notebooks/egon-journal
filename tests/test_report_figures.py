"""Tests for the report figure builders, data collection and full-report assembly."""

import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from egon.analytics.loader import JournalEntry
from egon.config import ReportConfig
from egon.full_report import build_full_report
from egon.limbic.bigfive import BigFiveScores
from egon.limbic.cognitive_bias import CognitiveBiasScores
from egon.limbic.emotion import EmotionScores
from egon.limbic.loneliness import LonelinessScore
from egon.limbic.mbti import MBTIScores
from egon.limbic.stress import StressScore
from egon.report import figures as F
from egon.report import theme
from egon.report.data import (
    SCORE_CACHE_FILES,
    HealthSeries,
    ReportData,
    build_signals,
    collect_report_data,
    save_scores,
)
from egon.report.html import Figure, render_report

START = date(2026, 1, 1)
N = 40
DAYS = [START + timedelta(days=i) for i in range(N)]


def _wave(base: float, amp: float, period: float = 9.0) -> list[tuple[date, float]]:
    return [(d, base + amp * math.sin(i / period)) for i, d in enumerate(DAYS)]


def _entries() -> list[JournalEntry]:
    words = "work walk park friends sleep tired coffee garden reading music"
    return [
        JournalEntry(d, f"I wrote about {words} " * (2 + i % 5), Path(f"{d}.md"))
        for i, d in enumerate(DAYS)
    ]


def _scores() -> dict[str, list]:
    def norm(xs: list[float]) -> list[float]:
        t = sum(xs)
        return [x / t for x in xs]

    return {
        "emotion": [
            (d, EmotionScores(*norm([0.1, 0.05, 0.1, 0.3 + 0.1 * math.sin(i), 0.3, 0.1, 0.05])))
            for i, d in enumerate(DAYS)
        ],
        "stress": [(d, StressScore(1 - p, p)) for d, p in _wave(0.4, 0.2)],
        "loneliness": [(d, LonelinessScore(1 - p, p)) for d, p in _wave(0.3, 0.15)],
        "bigfive": [(d, BigFiveScores(0.6, 0.5, v, 0.6, 1 - v)) for d, v in _wave(0.5, 0.1)],
        "mbti": [
            (d, MBTIScores(float(i % 2), 1.0, 0.0, float(i % 3 == 0))) for i, d in enumerate(DAYS)
        ],
        "cognitive_bias": [
            (
                d,
                CognitiveBiasScores(
                    *norm([0.6, 0.05, 0.1, 0.05, 0.05, 0.05, 0.05 + 0.04 * (i % 4), 0.05])
                ),
            )
            for i, d in enumerate(DAYS)
        ],
    }


def _health() -> dict[str, HealthSeries]:
    return {
        "weight": HealthSeries(_wave(78, 0.5), "kg"),
        "lean_mass": HealthSeries(_wave(62, 0.3)[::3], "kg"),
        "resting_heart_rate": HealthSeries(_wave(56, 3), "count/min"),
        "hrv": HealthSeries(_wave(50, 8), "ms"),
        "steps": HealthSeries(_wave(8000, 2500), "count"),
        "exercise": HealthSeries(_wave(30, 15), "min"),
        "vo2max": HealthSeries(_wave(44, 0.5)[::5], "mL/min·kg"),
    }


def _report_data() -> ReportData:
    entries, scores, health = _entries(), _scores(), _health()
    sleep, onset = _wave(7.2, 0.8), _wave(5.5, 0.6, 5)
    data = ReportData(
        label="2026-01",
        start=START,
        end=DAYS[-1],
        entries=entries,
        scores=scores,
        health=health,
        sleep_hours=sleep,
        sleep_onset=onset,
        llm_summary="A short summary.",
        llm_commentary={"hrv": "HRV commentary from the LLM."},
    )
    data.signals = build_signals(
        journal_entries=entries, health=health, sleep_hours=sleep, sleep_onset=onset, scores=scores
    )
    return data


def _assert_figure(fig: Figure, key: str) -> None:
    assert fig.key == key
    assert fig.title and fig.caption
    assert len(fig.why) > 80, "every figure explains why it matters for wellbeing"
    assert fig.how_to_read
    assert fig.spec["config"]["font"] == theme.FONT_BODY
    assert fig.table is not None and fig.table.rows
    # every color in the spec must have a dark-mode counterpart
    hexes = {h.lower() for h in __import__("re").findall(r"#[0-9a-fA-F]{6}", json.dumps(fig.spec))}
    assert hexes <= {h.lower() for h in theme.DARK_MAP}, hexes - {h.lower() for h in theme.DARK_MAP}


# --- individual figures --------------------------------------------------------


@pytest.mark.parametrize(
    "key,build",
    [
        ("word-count", lambda: F.word_count_figure([(d, 100 + i) for i, d in enumerate(DAYS)])),
        ("sentiment", lambda: F.sentiment_figure(_wave(0.1, 0.6))),
        ("pronoun-ratio", lambda: F.pronoun_ratio_figure(_wave(0.06, 0.02))),
        ("wordcloud", lambda: F.frequent_words_figure([("walk", 12), ("work", 9)])),
        ("topic-summary", lambda: F.topic_summary_figure([("walk · park", 6), ("work", 4)])),
        (
            "topic-timeline",
            lambda: F.topic_timeline_figure(
                [("2026-01", "walk · park", 3), ("2026-02", "work", 2), ("2026-02", "other", 1)],
                [("walk · park · run", 3), ("work · deadline", 2)],
            ),
        ),
        ("stress", lambda: F.stress_figure(_scores()["stress"])),
        ("loneliness", lambda: F.loneliness_figure(_scores()["loneliness"])),
        ("emotion", lambda: F.emotion_figure(_scores()["emotion"])),
        ("bigfive", lambda: F.bigfive_figure(_scores()["bigfive"])),
        ("mbti", lambda: F.mbti_figure(_scores()["mbti"])),
        ("cognitive-bias", lambda: F.cognitive_bias_figure(_scores()["cognitive_bias"])),
        ("weight", lambda: F.weight_figure(_wave(78, 0.5), target=76)),
        ("resting-heart-rate", lambda: F.resting_heart_rate_figure(_wave(56, 3), target=55)),
        ("hrv", lambda: F.hrv_figure(_wave(50, 8))),
        ("sleep", lambda: F.sleep_figure(_wave(7.2, 0.8), _wave(5.5, 0.6))),
        ("step-count", lambda: F.step_count_figure(_wave(8000, 2500))),
        ("exercise", lambda: F.exercise_figure(_wave(30, 15))),
        ("vo2max", lambda: F.vo2max_figure(_wave(44, 0.5))),
        ("correlation-matrix", lambda: F.correlation_matrix_figure(_report_data().signals)),
        ("top-correlations", lambda: F.top_pairs_figure(_report_data().signals)),
        (
            "highlighted-correlations",
            lambda: F.highlighted_correlations_figure(_report_data().signals),
        ),
    ],
)
def test_figure_builders(key, build):
    _assert_figure(build(), key)


def test_weight_with_lean_mass_is_two_panels():
    fig = F.weight_figure(_wave(78, 0.5), lean_data=_wave(62, 0.3))
    assert len(fig.spec["vconcat"]) == 2


def test_sleep_without_onset_is_single_panel():
    fig = F.sleep_figure(_wave(7.2, 0.8))
    assert "vconcat" not in fig.spec
    assert "fell asleep" not in fig.caption


def test_exercise_custom_target_replaces_who_line():
    who = json.dumps(F.exercise_figure(_wave(30, 15)).spec)
    custom = json.dumps(F.exercise_figure(_wave(30, 15), target=45).spec)
    assert "WHO 30" in who and "WHO 30" not in custom
    assert "target 45" in custom


def test_bar_charts_have_explicit_bar_extents():
    rows = F.step_count_figure(_wave(8000, 2500)).spec["data"]["values"]
    assert rows[0]["x0"].endswith("T03:00:00Z") and rows[0]["x1"].endswith("T21:00:00Z")


def test_empty_series_raises():
    with pytest.raises(ValueError):
        F.hrv_figure([])


# --- full report ------------------------------------------------------------------


def test_full_report_contains_every_figure_numbered_per_section():
    report = build_full_report(
        _report_data(), config=ReportConfig(analyses={"wordcloud": True, "topics": False})
    )
    keys = {f.key for s in report.sections for f in s.figures}
    assert {
        "word-count",
        "wordcloud",
        "pronoun-ratio",
        "sentiment",
        "stress",
        "loneliness",
        "emotion",
        "cognitive-bias",
        "bigfive",
        "mbti",
        "weight",
        "resting-heart-rate",
        "hrv",
        "sleep",
        "step-count",
        "exercise",
        "vo2max",
        "correlation-matrix",
        "top-correlations",
        "highlighted-correlations",
    } <= keys
    for section in report.sections:
        assert [f.number for f in section.figures] == [
            f"{section.number}.{i}" for i in range(1, len(section.figures) + 1)
        ]
    hrv = next(f for s in report.sections for f in s.figures if f.key == "hrv")
    assert hrv.commentary == "HRV commentary from the LLM."
    assert any(
        heading.startswith("Health summary") for s in report.sections for heading, _ in s.notes
    )


def test_full_report_respects_config_and_skips_missing_data():
    data = _report_data()
    data.health = {}
    data.sleep_hours = []
    report = build_full_report(
        data, config=ReportConfig(analyses={"bigfive": False, "topics": False})
    )
    keys = {f.key for s in report.sections for f in s.figures}
    assert "bigfive" not in keys
    assert "hrv" not in keys and "sleep" not in keys
    assert "wordcloud" not in keys  # off by default


def test_full_report_renders_and_marks_demo():
    report = build_full_report(
        _report_data(),
        config=ReportConfig(analyses={"topics": False}),
        synthetic=True,
        persona="Demo",
    )
    html = render_report(report)
    assert report.kind == "Demo report"
    assert 'content="synthetic"' in html
    assert "Why it matters for wellbeing" in html


# --- data collection ---------------------------------------------------------------


def test_collect_report_data_uses_score_cache_without_models(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    scores = _scores()
    for name, filename in SCORE_CACHE_FILES.items():
        save_scores(scores[name], cache / filename)

    def _no_models(*_a, **_k):
        raise AssertionError("models must not run when scores are cached")

    for mod, fn in [
        ("egon.limbic.bigfive", "bigfive_by_day"),
        ("egon.limbic.mbti", "mbti_by_day"),
        ("egon.limbic.emotion", "emotion_by_day"),
        ("egon.limbic.stress", "stress_by_day"),
        ("egon.limbic.loneliness", "loneliness_by_day"),
        ("egon.limbic.cognitive_bias", "cognitive_bias_by_day"),
    ]:
        monkeypatch.setattr(f"{mod}.{fn}", _no_models)

    data = collect_report_data(
        journal_entries=_entries(),
        xml_path=None,
        start=START,
        end=DAYS[-1],
        label="2026-01",
        cache_dir=cache,
        config=ReportConfig(),
    )
    assert set(data.scores) == set(SCORE_CACHE_FILES)
    assert data.scores["stress"][0][1].stress == pytest.approx(scores["stress"][0][1].stress)
    assert {"word count", "sentiment", "stress", "B5-N", "emo-joy"} <= set(data.signals)


def test_unavailable_model_is_skipped(tmp_path, monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("model not installed")

    monkeypatch.setattr("egon.limbic.stress.stress_by_day", _boom)
    for mod, fn in [
        ("egon.limbic.bigfive", "bigfive_by_day"),
        ("egon.limbic.mbti", "mbti_by_day"),
        ("egon.limbic.emotion", "emotion_by_day"),
        ("egon.limbic.loneliness", "loneliness_by_day"),
        ("egon.limbic.cognitive_bias", "cognitive_bias_by_day"),
    ]:
        monkeypatch.setattr(f"{mod}.{fn}", _boom)
    data = collect_report_data(
        journal_entries=_entries(),
        xml_path=None,
        start=START,
        end=DAYS[-1],
        label="x",
        cache_dir=tmp_path,
        config=ReportConfig(),
    )
    assert data.scores == {}
    assert "word count" in data.signals


def test_mbti_figure_shows_period_type():
    fig = F.mbti_figure(_scores()["mbti"])
    labels = [s.label for s in fig.headline]
    assert labels[0] == "Type this period"
    assert len(fig.headline[0].value) == 4 and set(fig.headline[0].value) <= set("EINSTFJP")
    assert len(fig.headline) == 5
    assert "Type this period" in render_report(
        __import__("egon.report.html", fromlist=["x"]).single_figure_report(
            fig, label="x", start=START, end=START
        )
    )


def test_bigfive_figure_shows_trait_estimates():
    fig = F.bigfive_figure(_scores()["bigfive"])
    assert [s.label for s in fig.headline] == [
        "Openness",
        "Conscientiousness",
        "Extraversion",
        "Agreeableness",
        "Neuroticism",
    ]
    assert fig.headline[0].value == "0.60"
