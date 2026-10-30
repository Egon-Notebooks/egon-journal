"""
Emotion profile — how the balance of seven emotions shifts across the period.

Left: a 100% stacked area of the trailing 7-day mean of each emotion's
probability.  Daily classifier output is too jittery to read stacked, so the
smoothing is what makes the shape legible.  Right: the period profile — each
emotion's average share, sorted.

Stack order groups positive affect (joy, surprise) above the neutral band and
negative affect below it, so the neutral band reads as the horizon line.  That
order is also the color-vision-validated adjacency order for these hues, so
do not reorder without re-running the palette validator.

Clicking a legend entry or a bar isolates one emotion across both panels.
"""

from datetime import date as date_type
from typing import Any

import altair as alt

from egon.limbic.emotion import EMOTIONS, EmotionScores
from egon.report import theme
from egon.report.charts._common import TOOLTIP_DAY, X_DATE, rolling_mean

STACK_ORDER: list[str] = ["joy", "surprise", "neutral", "sadness", "disgust", "fear", "anger"]

COLORS: dict[str, str] = {
    "joy": theme.SAGE,
    "surprise": theme.OCHRE,
    "neutral": theme.NEUTRAL,
    "sadness": theme.BLUE,
    "disgust": theme.MOSS,
    "fear": theme.PLUM,
    "anger": theme.TERRACOTTA,
}


def emotion_chart(data: list[tuple[date_type, EmotionScores]]) -> dict[str, Any]:
    if not data:
        raise ValueError("No emotion data found — nothing to plot.")

    dates = [d for d, _ in data]
    rows: list[dict[str, Any]] = []
    for idx, emotion in enumerate(EMOTIONS):
        series = [(d, s[idx]) for d, s in data]
        smooth = rolling_mean(series)
        for d, (_, raw), sm in zip(dates, series, smooth, strict=True):
            rows.append(
                {
                    "date": d.isoformat(),
                    "emotion": emotion,
                    "order": STACK_ORDER.index(emotion),
                    "value": round(sm, 4),
                    "raw": round(raw, 4),
                }
            )

    scale = alt.Scale(domain=STACK_ORDER, range=[COLORS[e] for e in STACK_ORDER])
    color = alt.Color(
        "emotion:N",
        title=None,
        scale=scale,
        legend=alt.Legend(orient="top", direction="horizontal"),
        sort=STACK_ORDER,
    )
    pick = alt.selection_point(fields=["emotion"], bind="legend", name="pick")
    faded = alt.condition(pick, alt.value(0.92), alt.value(0.12))

    area = (
        alt.Chart()
        .mark_area(stroke=theme.SURFACE, strokeWidth=1.5, interpolate="monotone")
        .encode(
            x=X_DATE,
            y=alt.Y(
                "value:Q",
                stack="normalize",
                title=None,
                axis=alt.Axis(format="%", tickCount=4),
            ),
            color=color,
            order=alt.Order("order:Q"),
            opacity=faded,
            tooltip=[
                TOOLTIP_DAY,
                alt.Tooltip("emotion:N", title="Emotion"),
                alt.Tooltip("value:Q", title="7-day mean", format=".0%"),
                alt.Tooltip("raw:Q", title="That day", format=".0%"),
            ],
        )
        .add_params(pick)
        .properties(width="container", height=theme.CHART_HEIGHT)
    )

    # Period profile: each emotion's mean daily probability, renormalized to 100%.
    means = {e: sum(s[i] for _, s in data) / len(data) for i, e in enumerate(EMOTIONS)}
    total = sum(means.values()) or 1.0
    shares = sorted(((e, m / total) for e, m in means.items()), key=lambda kv: -kv[1])
    profile = alt.Chart(
        alt.Data(values=[{"emotion": e, "share": round(v, 4)} for e, v in shares])
    ).encode(
        y=alt.Y(
            "emotion:N",
            sort=[e for e, _ in shares],
            title=None,
            axis=alt.Axis(labelColor=theme.INK_SECONDARY, labelFontSize=12),
        ),
        x=alt.X("share:Q", title=None, axis=None, scale=alt.Scale(domain=[0, 1])),
    )
    bars = profile.mark_bar(size=14).encode(
        color=alt.Color("emotion:N", scale=scale),
        opacity=faded,
        tooltip=[
            alt.Tooltip("emotion:N", title="Emotion"),
            alt.Tooltip("share:Q", title="Share of period", format=".0%"),
        ],
    )
    labels = profile.mark_text(align="left", dx=6, color=theme.INK_SECONDARY).encode(
        text=alt.Text("share:Q", format=".0%")
    )
    side = alt.layer(bars, labels).properties(
        width=170,
        height=theme.CHART_HEIGHT,
        title=alt.Title(
            "Period profile", anchor="start", fontSize=12, color=theme.INK_MUTED, fontWeight=500
        ),
    )

    chart = alt.hconcat(area.properties(data=alt.Data(values=rows)), side, spacing=28)
    return theme.to_spec(chart)
