"""
Daily time-series chart — the workhorse for most report signals.

Raw daily observations are drawn quietly (small grey dots, or grey bars for
daily totals); the story is told by a 2 px trailing 7-day mean in the series
colour.  Dotted hairlines mark the period average and any reference values
(a personal target, a guideline), each labelled in the right-hand margin.
Hovering anywhere shows a crosshair and a tooltip for the nearest day;
dragging across the plot zooms in, and double-click resets.
"""

from statistics import mean
from typing import Any, Literal

import altair as alt

from egon.report import theme
from egon.report.charts._common import (
    TOOLTIP_DAY,
    X_BAR_END,
    Series,
    bar_fields,
    mean_rule,
    rolling_mean,
    x_time,
)


def number_format(decimals: int = 0, percent: bool = False) -> str:
    return f".{decimals}%" if percent else f",.{decimals}f"


def series_layers(
    data: Series,
    *,
    label: str,
    unit: str,
    color: str = theme.BLUE,
    decimals: int = 0,
    percent: bool = False,
    references: list[tuple[float, str]] | None = None,
    target: float | None = None,
    domain: tuple[float, float] | None = None,
    zero_baseline: bool = False,
    mark: Literal["line", "bar"] = "line",
    show_mean: bool = True,
    wash: bool = False,
    height: int = theme.CHART_HEIGHT,
    hover_name: str = "hover",
    zoom: bool = True,
    show_x_axis: bool = True,
    y_title: str | None = None,
) -> alt.LayerChart:
    """Build the layered chart (not yet a spec) — reused by multi-panel charts.

    Set ``zoom=False`` for panels inside a concatenation: scale-bound zoom on a
    shared axis can only be registered once.
    """
    if not data:
        raise ValueError(f"No {label} data found — nothing to plot.")

    smooth = rolling_mean(data)
    rows = [
        {
            "date": d.isoformat(),
            **(bar_fields(d) if mark == "bar" else {}),
            "value": round(v, 4),
            "avg7": round(s, 4),
        }
        for (d, v), s in zip(data, smooth, strict=True)
    ]
    fmt = number_format(decimals, percent)
    avg = mean(v for _, v in data)

    # With bars, lines, rules and dots sit at the day's midpoint so they line up
    # with the middle of each bar.
    x = x_time("mid" if mark == "bar" else "date", axis=show_x_axis)
    x_bar_start = x_time("x0", axis=show_x_axis)

    if domain is not None:
        scale = alt.Scale(domain=list(domain), nice=False, zero=False)
    else:
        scale = alt.Scale(zero=zero_baseline or mark == "bar", nice=True)
    ticks = 3 if height < 150 else 5
    y_props = {
        "title": y_title if y_title is not None else (unit or None),
        "scale": scale,
        "axis": alt.Axis(format=fmt, tickCount=ticks),
    }
    y = alt.Y("value:Q", **y_props)

    hover = alt.selection_point(
        name=hover_name,
        fields=["date"],
        nearest=True,
        on="pointerover",
        clear="pointerout",
        empty=False,
    )

    if mark == "bar":
        raw = (
            alt.Chart()
            # Not cornerRadiusEnd: with x/x2 bars it wraps each bar in a stack
            # group that loses the bar width (Vega-Lite 6).
            .mark_bar(
                color=theme.NEUTRAL,
                cornerRadiusTopLeft=2,
                cornerRadiusTopRight=2,
                orient="vertical",
            )
            .encode(x=x_bar_start, x2=X_BAR_END, y=alt.Y("value:Q", stack=None, **y_props))
        )
    else:
        raw = (
            alt.Chart()
            .mark_circle(size=theme.RAW_DOT_SIZE, color=theme.NEUTRAL, opacity=0.9)
            .encode(x=x, y=y)
        )

    if zoom:
        raw = raw.add_params(
            alt.selection_interval(encodings=["x"], bind="scales", name=f"{hover_name}_zoom")
        )
    layers: list[Any] = [raw]
    if wash:
        layers.append(
            alt.Chart()
            .mark_area(color=color, opacity=0.1, interpolate="monotone")
            .encode(x=x, y=alt.Y("avg7:Q"), y2=alt.datum(domain[0] if domain else 0))
        )
    layers.append(
        alt.Chart().mark_line(color=color, interpolate="monotone").encode(x=x, y=alt.Y("avg7:Q"))
    )
    if show_mean:
        layers.append(mean_rule(avg, f"avg {avg:{fmt}}"))
    for value, text in references or []:
        layers.append(mean_rule(value, text))
    if target is not None:
        layers.append(mean_rule(target, f"target {target:{fmt}}", color=theme.ACCENT))

    value_title = f"{label} ({unit})" if unit else label
    hits = (
        alt.Chart()
        .mark_point(opacity=0, size=400)
        .encode(
            x=x,
            tooltip=[
                TOOLTIP_DAY,
                alt.Tooltip("value:Q", title=value_title, format=fmt),
                alt.Tooltip("avg7:Q", title="7-day average", format=fmt),
            ],
        )
        .add_params(hover)
    )
    rule = (
        alt.Chart().mark_rule(color=theme.AXIS, strokeWidth=1).encode(x=x).transform_filter(hover)
    )
    focus = (
        alt.Chart()
        .mark_point(
            filled=True,
            size=theme.DOT_SIZE * 1.5,
            color=color,
            stroke=theme.SURFACE,
            strokeWidth=2,
        )
        .encode(x=x, y="avg7:Q")
        .transform_filter(hover)
    )
    layers += [rule, hits, focus]

    return alt.layer(*layers, data=alt.Data(values=rows)).properties(
        width="container", height=height
    )


def with_label_gutter(spec: dict[str, Any]) -> dict[str, Any]:
    """Reserve a right-hand gutter for reference-line labels."""
    spec["padding"] = {**spec["config"]["padding"], "right": theme.LABEL_GUTTER}
    return spec


def daily_series_chart(data: Series, **kwargs: Any) -> dict[str, Any]:
    """Vega-Lite spec for one daily signal with its 7-day trend.

    Accepts the keyword arguments of :func:`series_layers`.
    """
    return with_label_gutter(theme.to_spec(series_layers(data, **kwargs)))


def stacked_series_chart(panels: list[tuple[Series, dict[str, Any]]]) -> dict[str, Any]:
    """Several daily signals with different units, as vertically stacked small multiples.

    Each panel gets its own y-axis — never two scales on one plot.  Panels
    share the time axis so they read top to bottom.
    """
    charts = []
    last = len(panels) - 1
    for i, (data, kwargs) in enumerate(panels):
        opts = {"height": 170, "y_title": f"{kwargs['label']}", **kwargs}
        charts.append(
            series_layers(data, hover_name=f"hover{i}", zoom=False, show_x_axis=i == last, **opts)
        )
    chart = alt.vconcat(*charts, spacing=14).resolve_scale(x="shared")
    return with_label_gutter(theme.to_spec(chart))


def series_summary(data: Series, decimals: int = 0, percent: bool = False) -> dict[str, str]:
    """Headline numbers for a stat row: period mean and first-vs-last-fortnight change."""
    values = [v for _, v in data]
    fmt = number_format(decimals, percent)
    k = min(14, len(values))
    delta = mean(values[-k:]) - mean(values[:k])
    magnitude = f"{abs(delta):{fmt}}"
    if magnitude == f"{0:{fmt}}":  # rounds to zero: no direction to show
        return {"mean": f"{mean(values):{fmt}}", "delta": f"±{magnitude}"}
    sign = "+" if delta > 0 else "−"
    return {"mean": f"{mean(values):{fmt}}", "delta": f"{sign}{magnitude}"}
