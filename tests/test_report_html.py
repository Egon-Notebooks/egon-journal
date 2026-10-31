"""Tests for the HTML report pipeline (egon.report)."""

import json
import re
from datetime import date, timedelta

import pytest

from egon.limbic.emotion import EMOTIONS, EmotionScores
from egon.report import theme
from egon.report.charts._common import rolling_mean
from egon.report.charts.emotion import STACK_ORDER, emotion_chart
from egon.report.charts.timeseries import daily_series_chart, series_summary
from egon.report.figures import emotion_figure, hrv_figure, hrv_stats
from egon.report.html import Report, Section, render_report, single_figure_report, write_report

START = date(2026, 1, 1)


def _series(n: int = 30, base: float = 50.0) -> list[tuple[date, float]]:
    return [(START + timedelta(days=i), base + (i % 7)) for i in range(n)]


def _emotions(n: int = 20) -> list[tuple[date, EmotionScores]]:
    return [(START + timedelta(days=i), EmotionScores(*([1 / 7] * 7))) for i in range(n)]


def _embedded_specs(html: str) -> dict:
    match = re.search(r'<script id="egon-specs" type="application/json">(.*?)</script>', html, re.S)
    assert match
    return json.loads(match.group(1))


# --- data helpers ----------------------------------------------------------------


def test_rolling_mean_is_trailing_calendar_window():
    data = [(START + timedelta(days=i), float(i)) for i in range(10)]
    out = rolling_mean(data, window_days=3)
    assert out[0] == 0
    assert out[2] == pytest.approx(1.0)  # mean(0, 1, 2)
    assert out[9] == pytest.approx(8.0)  # mean(7, 8, 9)


def test_rolling_mean_tolerates_gaps():
    data = [(START, 10.0), (START + timedelta(days=5), 20.0), (START + timedelta(days=6), 30.0)]
    assert rolling_mean(data, window_days=3) == [10.0, 20.0, 25.0]


def test_series_summary_formats_sign():
    rising = [(START + timedelta(days=i), float(i)) for i in range(40)]
    assert series_summary(rising)["delta"].startswith("+")
    falling = [(d, -v) for d, v in rising]
    assert series_summary(falling)["delta"].startswith("−")


# --- chart specs -----------------------------------------------------------------


def test_daily_series_chart_spec_is_themed_and_responsive():
    spec = daily_series_chart(_series(), label="HRV", unit="ms", target=55)
    assert spec["config"]["background"] is None
    assert spec["width"] == "container"
    assert spec["autosize"]["type"] == "fit-x"
    rows = spec["data"]["values"]
    assert rows[0].keys() >= {"date", "value", "avg7"}
    assert "target 55" in json.dumps(spec)


def test_daily_series_chart_rejects_empty():
    with pytest.raises(ValueError):
        daily_series_chart([], label="HRV", unit="ms")


def test_emotion_chart_covers_all_emotions_in_stack_order():
    spec = emotion_chart(_emotions())
    assert sorted(STACK_ORDER) == sorted(EMOTIONS)
    area = spec["hconcat"][0]
    assert area["encoding"]["color"]["scale"]["domain"] == STACK_ORDER
    assert len(area["data"]["values"]) == 20 * len(EMOTIONS)


def test_charts_use_only_palette_colours():
    """Every hex in a spec must have a dark-mode counterpart, or dark mode breaks."""
    for spec in (
        daily_series_chart(_series(), label="x", unit="u", target=1),
        emotion_chart(_emotions()),
    ):
        hexes = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}", json.dumps(spec))}
        known = {h.lower() for h in theme.DARK_MAP}
        assert hexes <= known, hexes - known


# --- HTML assembly -----------------------------------------------------------------


def test_single_figure_report_is_self_contained(tmp_path):
    fig = hrv_figure(_series())
    report = single_figure_report(
        fig,
        label="2026-01",
        start=START,
        end=START + timedelta(days=29),
        stats=hrv_stats(_series()),
    )
    out = write_report(report, tmp_path / "hrv.html")
    html = out.read_text()
    assert html.startswith("<!doctype html>")
    # no network references of any kind
    assert not re.search(r'(src|href)=["\']https?://', html)
    assert "@import" not in html
    assert "font/woff2;base64," in html
    assert "vegaEmbed" in html
    assert _embedded_specs(html)["hrv"]["config"]["font"] == theme.FONT_BODY
    assert 'content="personal"' in html
    assert "Demo report" not in html


def test_synthetic_report_is_marked():
    report = Report(
        title="Demo",
        start=START,
        end=START,
        sections=[Section(1, "Affect", figures=[emotion_figure(_emotions())])],
        synthetic=True,
        persona="Self-Directed Individual",
    )
    html = render_report(report)
    assert 'content="synthetic"' in html
    assert "Demo report" in html
    assert "Self-Directed Individual" in html


def test_commentary_is_escaped():
    fig = hrv_figure(_series(), commentary="<script>alert(1)</script>")
    html = render_report(single_figure_report(fig, label="x", start=START, end=START))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_spec_json_cannot_close_script_tag():
    fig = hrv_figure(_series())
    fig.spec["description"] = "</script><b>x</b>"
    html = render_report(single_figure_report(fig, label="x", start=START, end=START))
    assert "</script><b>x</b>" not in html
    assert _embedded_specs(html)["hrv"]["description"] == "</script><b>x</b>"


def test_series_summary_rounds_tiny_change_to_plus_minus_zero():
    flat = [(START + timedelta(days=i), 0.5 - 0.0001 * i) for i in range(40)]
    assert series_summary(flat, decimals=2)["delta"] == "±0.00"


def test_personal_report_is_marked_confidential_demo_is_not():
    fig = hrv_figure(_series())
    personal = render_report(single_figure_report(fig, label="x", start=START, end=START))
    assert ">Confidential<" in personal
    demo = Report(title="x", start=START, end=START, sections=[], synthetic=True)
    assert ">Confidential<" not in render_report(demo)
