"""
Charts for what the journal is about: topics and frequent words.

Ranked bars use a single colour (the categories have no order of their own);
the topic timeline uses the categorical palette in slot order, with
"other" folded into neutral grey.
"""

from typing import Any

import altair as alt

from egon.report import theme

MAX_TIMELINE_TOPICS = 7  # + "other" = 8 categorical slots at most


def ranked_bars_chart(
    items: list[tuple[str, float]],
    *,
    value_title: str,
    color: str = theme.BLUE,
    label_limit: int = 420,
    value_format: str = ",.0f",
) -> dict[str, Any]:
    """Horizontal bars, largest first, value labelled at the tip."""
    if not items:
        raise ValueError("Nothing to rank.")
    rows = [{"label": label, "value": value} for label, value in items]
    order = [label for label, _ in sorted(items, key=lambda kv: -kv[1])]
    base = alt.Chart(alt.Data(values=rows)).encode(
        y=alt.Y(
            "label:N",
            sort=order,
            title=None,
            axis=alt.Axis(labelLimit=label_limit, labelFontSize=12, labelColor=theme.INK_SECONDARY),
        ),
        x=alt.X("value:Q", title=None, axis=None),
    )
    bars = base.mark_bar(size=14, color=color).encode(
        tooltip=[
            alt.Tooltip("label:N", title="Item"),
            alt.Tooltip("value:Q", title=value_title, format=value_format),
        ]
    )
    labels = base.mark_text(align="left", dx=6, color=theme.INK_SECONDARY).encode(
        text=alt.Text("value:Q", format=value_format)
    )
    chart = alt.layer(bars, labels).properties(width="container", height=26 * len(rows))
    return theme.to_spec(chart)


def topic_timeline_chart(rows: list[tuple[str, str, int]], topics: list[str]) -> dict[str, Any]:
    """Stacked monthly bars of entries per topic.

    *rows* are (YYYY-MM, topic label, count); *topics* gives the slot order
    (largest topic first).  Anything else is shown as "other".
    """
    if not rows:
        raise ValueError("No topic data to plot.")
    named = topics[:MAX_TIMELINE_TOPICS]
    domain = [*named, "other"]
    data = [
        {
            "month": m + "-01",
            "topic": t if t in named else "other",
            "count": c,
            "order": domain.index(t if t in named else "other"),
        }
        for m, t, c in rows
    ]
    chart = (
        alt.Chart(alt.Data(values=data))
        .mark_bar(stroke=theme.SURFACE, strokeWidth=2, cornerRadius=2)
        .encode(
            x=alt.X(
                "month:O",
                title=None,
                axis=alt.Axis(
                    labelExpr="timeFormat(toDate(datum.value + 'T00:00:00'), '%b %Y')",
                    labelAngle=0,
                ),
            ),
            y=alt.Y("sum(count):Q", title="entries", stack="zero"),
            color=alt.Color(
                "topic:N",
                title=None,
                scale=alt.Scale(
                    domain=domain,
                    range=[*theme.SERIES_LIGHT[: len(named)], theme.NEUTRAL],
                ),
                legend=alt.Legend(orient="bottom", direction="vertical", columns=2, labelLimit=360),
            ),
            order=alt.Order("order:Q"),
            tooltip=[
                alt.Tooltip("month:N", title="Month"),
                alt.Tooltip("topic:N", title="Topic"),
                alt.Tooltip("sum(count):Q", title="Entries"),
            ],
        )
        .properties(width="container", height=theme.CHART_HEIGHT)
    )
    return theme.to_spec(chart)
