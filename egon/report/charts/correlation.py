"""
Cross-signal correlation charts.

- Explorer: lower-triangle correlation matrix; clicking a cell shows that
  pair's daily scatter (with a least-squares line) beside it.  The scatter is
  assembled in the browser from the raw daily series, so every pair is
  explorable without precomputing all of them.
- Top pairs: the strongest relationships as diverging bars of Pearson r.
- Highlighted pairs: small multiples for pairs with documented relevance to
  mental health.
"""

from typing import Any

import altair as alt

from egon.analytics.correlation import PairStat, Signals, align_pairwise, usable_signals
from egon.report import theme

# Lab interpolation keeps the arms on their own hue (no purple drift through the gray midpoint).
_R_SCALE = alt.Scale(
    domain=[-1, 0, 1], range=[theme.TERRACOTTA, theme.NEUTRAL, theme.BLUE], interpolate="lab"
)
_FADED = 0.35  # opacity for pairs that are not statistically significant (p ≥ 0.05)


def _p_text(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _cell(s: PairStat) -> dict[str, Any]:
    return {
        "a": s.a,
        "b": s.b,
        "r": round(s.r, 3),
        "p": round(s.p, 4),
        "n": s.n,
        "sig": s.significant,
        "label": f"{s.r:+.2f}".replace("+0.", "+.").replace("-0.", "−."),
    }


def correlation_explorer_chart(signals: Signals, stats: list[PairStat]) -> dict[str, Any]:
    if not stats:
        raise ValueError("Not enough overlapping signals for a correlation matrix.")
    names = usable_signals(signals)
    # Matrix axes: a on x (all but last name), b on y (all but first) → lower triangle.
    cells = [_cell(s) for s in stats]
    first = max(stats, key=lambda s: abs(s.r))

    points = [
        {"s": name, "d": d.isoformat(), "v": round(v, 4), "k": f"{name}|{d.isoformat()}"}
        for name in names
        for d, v in signals[name]
    ]

    pick = alt.selection_point(
        name="pick",
        fields=["a", "b"],
        value=[{"a": first.a, "b": first.b}],
        toggle=False,
        clear=False,
        on="click",
    )
    step = 18
    base = alt.Chart(alt.Data(values=cells)).encode(
        x=alt.X(
            "a:N",
            sort=names,
            title=None,
            axis=alt.Axis(labelAngle=-50, labelLimit=110, orient="bottom"),
        ),
        y=alt.Y("b:N", sort=names, title=None, axis=alt.Axis(labelLimit=110)),
    )
    heat = (
        base.mark_rect(cornerRadius=2, stroke=theme.SURFACE, strokeWidth=1.5, cursor="pointer")
        .encode(
            color=alt.Color(
                "r:Q",
                scale=_R_SCALE,
                legend=alt.Legend(
                    title="Pearson r",
                    orient="top",
                    direction="horizontal",
                    gradientLength=160,
                    format="+.1f",
                ),
            ),
            opacity=alt.condition("datum.sig", alt.value(1), alt.value(_FADED)),
            tooltip=[
                alt.Tooltip("a:N", title="Signal"),
                alt.Tooltip("b:N", title="vs"),
                alt.Tooltip("r:Q", title="Pearson r", format="+.2f"),
                alt.Tooltip("p:Q", title="p-value", format=".3f"),
                alt.Tooltip("n:Q", title="Days"),
            ],
        )
        .add_params(pick)
    )
    selected = base.mark_rect(
        fill=None, stroke=theme.INK, strokeWidth=2, cornerRadius=2
    ).transform_filter(pick)
    matrix = alt.layer(heat, selected).properties(
        width=step * (len(names) - 1), height=step * (len(names) - 1)
    )

    # Scatter for the selected pair: x = signal a, y = signal b, joined on date.
    pair = (
        alt.Chart(alt.Data(values=points))
        .transform_filter("datum.s == pick.a[0]")
        .transform_calculate(k2="pick.b[0] + '|' + datum.d")
        .transform_lookup(
            lookup="k2",
            from_=alt.LookupData(data=alt.Data(values=points), key="k", fields=["v"]),
            as_=["y"],
        )
        .transform_filter("isValid(datum.y)")
    )
    dots = pair.mark_circle(
        size=theme.DOT_SIZE, color=theme.BLUE, opacity=0.7, stroke=theme.SURFACE, strokeWidth=1
    ).encode(
        x=alt.X("v:Q", title=None, scale=alt.Scale(zero=False, nice=True)),
        y=alt.Y("y:Q", title=None, scale=alt.Scale(zero=False, nice=True)),
        tooltip=[
            alt.Tooltip("d:N", title="Date"),
            alt.Tooltip("v:Q", title="x", format=",.2f"),
            alt.Tooltip("y:Q", title="y", format=",.2f"),
        ],
    )
    fit = (
        pair.transform_regression("v", "y")
        .mark_line(color=theme.INK, strokeWidth=1.5)
        .encode(x="v:Q", y="y:Q")
    )
    caption = (
        alt.Chart(alt.Data(values=cells))
        .transform_filter(pick)
        .transform_calculate(
            t="datum.b + ' (↑)  vs  ' + datum.a + ' (→)'",
            s="'r = ' + format(datum.r, '+.2f') + ' · ' + "
            "(datum.p < 0.001 ? 'p < 0.001' : 'p = ' + format(datum.p, '.3f')) + "
            "' · ' + datum.n + ' days'",
        )
    )
    title = caption.mark_text(
        align="left", baseline="bottom", dy=-22, fontSize=13, fontWeight=600, color=theme.INK
    ).encode(x=alt.value(0), y=alt.value(0), text="t:N")
    subtitle = caption.mark_text(
        align="left", baseline="bottom", dy=-6, fontSize=11, color=theme.INK_MUTED
    ).encode(x=alt.value(0), y=alt.value(0), text="s:N")
    scatter = alt.layer(dots, fit, title, subtitle).properties(
        width="container", height=step * (len(names) - 1)
    )
    chart = alt.hconcat(matrix, scatter, spacing=48)
    spec = theme.to_spec(chart)
    spec["padding"] = {**spec["config"]["padding"], "top": 40}
    return spec


def top_pairs_chart(stats: list[PairStat]) -> dict[str, Any]:
    if not stats:
        raise ValueError("No signal pairs to rank.")
    rows = [
        {
            **_cell(s),
            "pair": f"{s.a}  ↔  {s.b}",
            "tip": f"{s.r:+.2f}" + ("" if s.significant else "  n.s."),
        }
        for s in stats
    ]
    order = [r["pair"] for r in rows]
    base = alt.Chart(alt.Data(values=rows)).encode(
        y=alt.Y("pair:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=12)),
    )
    zero = alt.Chart(alt.Data(values=[{"x": 0}])).mark_rule(color=theme.AXIS).encode(x="x:Q")
    bars = base.mark_bar(size=14).encode(
        x=alt.X(
            "r:Q",
            title="Pearson r",
            scale=alt.Scale(domain=[-1, 1]),
            axis=alt.Axis(format="+.1f", values=[-1, -0.5, 0, 0.5, 1], grid=True),
        ),
        color=alt.Color("r:Q", scale=_R_SCALE, legend=None),
        opacity=alt.condition("datum.sig", alt.value(1), alt.value(_FADED)),
        tooltip=[
            alt.Tooltip("pair:N", title="Pair"),
            alt.Tooltip("r:Q", title="Pearson r", format="+.2f"),
            alt.Tooltip("p:Q", title="p-value", format=".3f"),
            alt.Tooltip("n:Q", title="Days"),
        ],
    )
    # Value labels sit just beyond the bar tip, on whichever side the bar points.
    pos = (
        base.transform_filter("datum.r >= 0")
        .mark_text(align="left", dx=6, fontSize=11, color=theme.INK_SECONDARY)
        .encode(x="r:Q", text="tip:N")
    )
    neg = (
        base.transform_filter("datum.r < 0")
        .mark_text(align="right", dx=-6, fontSize=11, color=theme.INK_SECONDARY)
        .encode(x="r:Q", text="tip:N")
    )
    chart = alt.layer(zero, bars, pos, neg).properties(width="container", height=28 * len(rows))
    return theme.to_spec(chart)


def highlighted_pairs_chart(signals: Signals, pairs: list[tuple[str, PairStat]]) -> dict[str, Any]:
    if not pairs:
        raise ValueError("None of the highlighted signal pairs are available.")
    panels = []
    for i, (title, s) in enumerate(pairs):
        dates, xs, ys = align_pairwise(signals[s.a], signals[s.b])
        rows = [
            {"date": d.isoformat(), "x": round(x, 4), "y": round(y, 4)}
            for d, x, y in zip(dates, xs, ys, strict=True)
        ]
        base = alt.Chart(alt.Data(values=rows))
        dots = base.mark_circle(
            size=theme.DOT_SIZE * 0.8,
            color=theme.BLUE,
            opacity=0.65,
            stroke=theme.SURFACE,
            strokeWidth=1,
        ).encode(
            x=alt.X("x:Q", title=s.a, scale=alt.Scale(zero=False, nice=True)),
            y=alt.Y("y:Q", title=s.b, scale=alt.Scale(zero=False, nice=True)),
            tooltip=[
                alt.Tooltip("date:N", title="Date"),
                alt.Tooltip("x:Q", title=s.a, format=",.2f"),
                alt.Tooltip("y:Q", title=s.b, format=",.2f"),
            ],
        )
        fit = (
            base.transform_regression("x", "y")
            .mark_line(color=theme.INK, strokeWidth=1.5, opacity=1 if s.significant else _FADED)
            .encode(x="x:Q", y="y:Q")
        )
        panels.append(
            alt.layer(dots, fit).properties(
                width="container",
                height=200,
                title=alt.Title(
                    title,
                    subtitle=f"r = {s.r:+.2f} · {_p_text(s.p)} · {s.n} days",
                    anchor="start",
                    fontSize=13,
                    subtitleColor=theme.INK_MUTED,
                    subtitleFontSize=11,
                    offset=10,
                ),
                name=f"pair{i}",
            )
        )
    chart = alt.concat(*panels, columns=2, spacing=36)
    return theme.to_spec(chart)
