"""Shared building blocks for Egon report charts."""

from datetime import date as date_type
from datetime import timedelta
from statistics import mean

import altair as alt

from egon.report import theme

Series = list[tuple[date_type, float]]

# Dates are serialized as ISO strings, which Vega parses as UTC midnight.  A
# UTC scale keeps every day on its own calendar date whatever the reader's time
# zone.  Two Vega-Lite 6 quirks shape the definitions below:
#   - formatType="utc" on the axis makes it ignore the format string, so the
#     axis relies on the UTC scale alone;
#   - nominal tooltip fields break on nearest-point (voronoi) layers, so the
#     tooltip date is a temporal field with a UTC time unit.
DATE_AXIS = alt.Axis(format="%-d %b", labelOverlap=True, tickCount=8)


def x_time(field: str, axis: bool = True) -> alt.X:
    """UTC time x-encoding; ``axis=False`` for upper panels of a stack."""
    return alt.X(
        f"{field}:T", title=None, scale=alt.Scale(type="utc"), axis=DATE_AXIS if axis else None
    )


X_DATE = x_time("date")

# Daily bars span 03:00–21:00 UTC of their day (the remainder is the gap between
# bars); anything drawn with a bar chart sits at the day's midpoint (12:00).
X_MID = x_time("mid")
X_BAR_START = x_time("x0")
X_BAR_END = alt.X2("x1:T")


def bar_fields(d: date_type) -> dict[str, str]:
    """Bar extent and midpoint for day *d*, as UTC timestamps."""
    iso = d.isoformat()
    return {"x0": f"{iso}T03:00:00Z", "x1": f"{iso}T21:00:00Z", "mid": f"{iso}T12:00:00Z"}


TOOLTIP_DAY = alt.Tooltip(
    "date:T", title="Date", timeUnit="utcyearmonthdate", format="%a %-d %b %Y"
)


def rolling_mean(data: Series, window_days: int = 7) -> list[float]:
    """Trailing mean over the previous *window_days* calendar days (inclusive).

    Gaps are tolerated: only days with an observation inside the window count.
    """
    out: list[float] = []
    start = 0
    for i, (d, _) in enumerate(data):
        while data[start][0] <= d - timedelta(days=window_days):
            start += 1
        out.append(mean(v for _, v in data[start : i + 1]))
    return out


def mean_rule(value: float, label: str, color: str = theme.INK_MUTED) -> alt.LayerChart:
    """A dotted hairline reference rule, labeled in the right-hand margin.

    The label sits outside the plot so it never collides with the data.
    """
    base = alt.Chart(alt.Data(values=[{"y": value, "label": label}]))
    rule = base.mark_rule(color=color, strokeWidth=1, strokeDash=[1, 3]).encode(y="y:Q")
    text = base.mark_text(
        align="left", baseline="middle", dx=8, color=color, fontSize=11, clip=False
    ).encode(y="y:Q", x=alt.value("width"), text="label:N")
    return rule + text
