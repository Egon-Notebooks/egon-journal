"""
Sleep: nightly time asleep, and how regular the time of falling asleep is.

Onset times arrive as hours after 18:00 (so 23:30 → 5.5 and 01:00 → 7.0),
which keeps nights that cross midnight on one continuous axis.  The axis and
tooltips convert back to clock time.
"""

from statistics import mean, stdev
from typing import Any

import altair as alt

from egon.report import theme
from egon.report.charts._common import TOOLTIP_DAY, X_MID, Series, bar_fields
from egon.report.charts.timeseries import series_layers, with_label_gutter

ONSET_REF_HOUR = 18  # must match egon.health.sleep

# Vega expression: hours-after-18:00 → "HH:MM"
_CLOCK_EXPR = (
    "format((floor({v}) + 18) % 24, '02d') + ':' + format(round(({v} % 1) * 60) % 60, '02d')"
)


def onset_clock(hours_after_6pm: float) -> str:
    total = round((hours_after_6pm + ONSET_REF_HOUR) * 60) % (24 * 60)
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}"


def format_duration(hours: float) -> str:
    total = round(hours * 60)
    h, m = divmod(total, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def sleep_chart(hours: Series, onset: Series | None = None) -> dict[str, Any]:
    asleep = series_layers(
        hours,
        label="Time asleep",
        unit="hours",
        color=theme.PLUM,
        decimals=1,
        mark="bar",
        references=[(7, "7 h"), (9, "9 h")],
        height=200,
        hover_name="sleep",
        zoom=not onset,
    )
    if not onset:
        return with_label_gutter(theme.to_spec(asleep))

    values = [v for _, v in onset]
    avg = mean(values)
    sd = stdev(values) if len(values) > 1 else 0.0
    rows = [
        {"date": d.isoformat(), **bar_fields(d), "onset": round(v, 3), "clock": onset_clock(v)}
        for d, v in onset
    ]
    y_scale = alt.Scale(reverse=True, zero=False, nice=False)
    y = alt.Y(
        "onset:Q",
        title="fell asleep",
        scale=y_scale,
        axis=alt.Axis(labelExpr=_CLOCK_EXPR.format(v="datum.value"), tickCount=5),
    )
    band = (
        alt.Chart(alt.Data(values=[{"lo": avg - sd, "hi": avg + sd}]))
        .mark_rect(color=theme.PLUM, opacity=0.08)
        .encode(y=alt.Y("lo:Q", scale=y_scale), y2="hi:Q")
    )
    avg_rule = (
        alt.Chart(alt.Data(values=[{"y": avg}]))
        .mark_rule(color=theme.INK_MUTED, strokeDash=[1, 3])
        .encode(y="y:Q")
    )
    avg_text = (
        alt.Chart(
            alt.Data(values=[{"y": avg, "t": f"avg {onset_clock(avg)}  ±{format_duration(sd)}"}])
        )
        .mark_text(align="left", dx=8, color=theme.INK_MUTED, clip=False)
        .encode(y="y:Q", x=alt.value("width"), text="t:N")
    )
    dots = (
        alt.Chart(alt.Data(values=rows))
        .mark_circle(size=theme.DOT_SIZE, color=theme.PLUM, stroke=theme.SURFACE, strokeWidth=1.5)
        .encode(
            # Day-centred, to line up with the middle of the sleep bars above.
            x=X_MID,
            y=y,
            tooltip=[TOOLTIP_DAY, alt.Tooltip("clock:N", title="Fell asleep")],
        )
    )
    onset_panel = alt.layer(band, avg_rule, dots, avg_text).properties(
        width="container", height=170
    )
    chart = alt.vconcat(asleep, onset_panel, spacing=24).resolve_scale(x="shared")
    return with_label_gutter(theme.to_spec(chart))
