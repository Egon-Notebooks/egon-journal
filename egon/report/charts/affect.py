"""
Charts for language-derived affect and personality signals.

- Sentiment: diverging daily bars around a neutral band, with a 7-day trend.
- MBTI: four small multiples, each a 0–1 lean between two poles.
- Cognitive distortions: daily distortion signal plus a week × type heatmap.
"""

from collections import defaultdict
from datetime import date as date_type
from datetime import timedelta
from statistics import mean
from typing import Any

import altair as alt

from egon.limbic.cognitive_bias import BIASES, DISTORTION_TYPES, CognitiveBiasScores
from egon.limbic.mbti import DIMENSIONS, MBTIScores
from egon.report import theme
from egon.report.charts._common import (
    TOOLTIP_DAY,
    X_BAR_END,
    X_BAR_START,
    X_MID,
    Series,
    bar_fields,
    mean_rule,
    rolling_mean,
    x_time,
)
from egon.report.charts.timeseries import series_layers, with_label_gutter

# Tone classes: negative (terracotta) · neutral (gray) · positive (ink blue).
TONE_DOMAIN = ["negative", "neutral", "positive"]
TONE_RANGE = [theme.TERRACOTTA, theme.NEUTRAL, theme.BLUE]
NEUTRAL_BAND = 0.05  # VADER's conventional neutral threshold


def sentiment_chart(data: Series) -> dict[str, Any]:
    if not data:
        raise ValueError("No sentiment data found — nothing to plot.")
    smooth = rolling_mean(data)
    rows = [
        {
            "date": d.isoformat(),
            **bar_fields(d),
            "value": round(v, 3),
            "avg7": round(s, 3),
            "tone": "positive"
            if v > NEUTRAL_BAND
            else "negative"
            if v < -NEUTRAL_BAND
            else "neutral",
        }
        for (d, v), s in zip(data, smooth, strict=True)
    ]
    y_scale = alt.Scale(domain=[-1, 1], nice=False)

    band = (
        alt.Chart(alt.Data(values=[{"lo": -NEUTRAL_BAND, "hi": NEUTRAL_BAND}]))
        .mark_rect(color=theme.GRID, opacity=0.9)
        .encode(y=alt.Y("lo:Q", scale=y_scale), y2="hi:Q")
    )
    bars = (
        alt.Chart()
        .mark_bar(cornerRadius=1, orient="vertical")
        .encode(
            x=X_BAR_START,
            x2=X_BAR_END,
            y=alt.Y(
                "value:Q",
                title="tone (VADER)",
                scale=y_scale,
                axis=alt.Axis(format="+.1f"),
                stack=None,
            ),
            color=alt.Color(
                "tone:N", scale=alt.Scale(domain=TONE_DOMAIN, range=TONE_RANGE), legend=None
            ),
            opacity=alt.value(0.55),
            tooltip=[
                TOOLTIP_DAY,
                alt.Tooltip("value:Q", title="Sentiment", format="+.2f"),
                alt.Tooltip("avg7:Q", title="7-day average", format="+.2f"),
            ],
        )
        .add_params(alt.selection_interval(encodings=["x"], bind="scales", name="sent_zoom"))
    )
    trend = (
        alt.Chart().mark_line(color=theme.INK, interpolate="monotone").encode(x=X_MID, y="avg7:Q")
    )
    chart = alt.layer(
        band,
        bars,
        trend,
        mean_rule(mean(v for _, v in data), f"avg {mean(v for _, v in data):+.2f}"),
        data=alt.Data(values=rows),
    ).properties(width="container", height=theme.CHART_HEIGHT)
    return with_label_gutter(theme.to_spec(chart))


def mbti_chart(data: list[tuple[date_type, MBTIScores]]) -> dict[str, Any]:
    """Four 0–1 panels: 1 = first pole (E, N, T, J), 0 = second pole."""
    if not data:
        raise ValueError("No MBTI data found — nothing to plot.")
    colors = [theme.BLUE, theme.TERRACOTTA, theme.SAGE, theme.PLUM]
    charts = []
    for i, ((pos, neg, label), color) in enumerate(zip(DIMENSIONS, colors, strict=True)):
        series = [(d, float(s[i])) for d, s in data]
        avg = mean(v for _, v in series)
        dominant, share = (pos, avg) if avg >= 0.5 else (neg, 1 - avg)
        layer = series_layers(
            series,
            label=label,
            unit="",
            color=color,
            percent=True,
            domain=(-0.05, 1.05),
            show_mean=False,
            references=[(0.5, ""), (avg, f"{dominant} {share:.0%}")],
            height=120,
            hover_name=f"mbti{i}",
            zoom=False,
            show_x_axis=i == len(DIMENSIONS) - 1,
        )
        # Label the two ends of the axis with the poles instead of 0% / 100%.
        layer.layer[0].encoding.y.axis = alt.Axis(
            values=[0, 1],
            labelExpr=f"datum.value == 1 ? '{pos}' : '{neg}'",
            labelFontSize=13,
            labelFontWeight=600,
            title=label,
        )
        charts.append(layer)
    chart = alt.vconcat(*charts, spacing=14).resolve_scale(x="shared")
    return with_label_gutter(theme.to_spec(chart))


def _week_start(d: date_type) -> date_type:
    return d - timedelta(days=d.weekday())


def cognitive_bias_chart(data: list[tuple[date_type, CognitiveBiasScores]]) -> dict[str, Any]:
    """Distortion signal over time, and which distortion types drive it week by week."""
    if not data:
        raise ValueError("No cognitive bias data found — nothing to plot.")

    signal = series_layers(
        [(d, s.distortion_score) for d, s in data],
        label="Distortion signal",
        unit="",
        color=theme.TERRACOTTA,
        percent=True,
        domain=(0, 1),
        wash=True,
        height=170,
        hover_name="distortion",
        zoom=False,
        show_x_axis=False,
    )

    # Week × type heatmap of mean probability.  Types are ordered by their
    # period mean so the dominant distortions sit on top.
    weekly: dict[date_type, list[CognitiveBiasScores]] = defaultdict(list)
    for d, s in data:
        weekly[_week_start(d)].append(s)
    type_means = {t: mean(s[BIASES.index(t)] for _, s in data) for t in DISTORTION_TYPES}
    order = [t.capitalize() for t in sorted(DISTORTION_TYPES, key=lambda t: -type_means[t])]
    period_start = min(d for d, _ in data)
    period_end = max(d for d, _ in data) + timedelta(days=1)
    cells = []
    for wk, scores in sorted(weekly.items()):
        # Clamp the first and last week to the period so columns align with the line above.
        x0 = max(wk, period_start)
        x1 = min(wk + timedelta(days=7), period_end)
        for t in DISTORTION_TYPES:
            cells.append(
                {
                    "x0": f"{x0.isoformat()}T00:00:00Z",
                    "x1": f"{x1.isoformat()}T00:00:00Z",
                    "week": wk.strftime("%-d %b"),
                    "type": t.capitalize(),
                    "value": round(mean(s[BIASES.index(t)] for s in scores), 4),
                    "days": len(scores),
                }
            )
    vmax = max((c["value"] for c in cells), default=0.0) or 1.0
    heat = (
        alt.Chart(alt.Data(values=cells))
        .mark_rect(cornerRadius=2, stroke=theme.SURFACE, strokeWidth=2)
        .encode(
            x=x_time("x0"),
            x2="x1:T",
            y=alt.Y(
                "type:N", title=None, sort=order, axis=alt.Axis(labelColor=theme.INK_SECONDARY)
            ),
            color=alt.Color(
                "value:Q",
                scale=alt.Scale(domain=[0, vmax], range=[theme.SEQ_LOW, theme.SEQ_HIGH]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("type:N", title="Distortion"),
                alt.Tooltip("week:N", title="Week of"),
                alt.Tooltip("value:Q", title="Mean probability", format=".1%"),
                alt.Tooltip("days:Q", title="Entries"),
            ],
        )
        .properties(width="container", height=26 * len(DISTORTION_TYPES))
    )
    chart = alt.vconcat(signal, heat, spacing=10).resolve_scale(x="shared")
    return with_label_gutter(theme.to_spec(chart))
