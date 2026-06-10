"""
Loneliness report plot.

Single-panel line chart of daily loneliness probability (0–1) derived from
``Tianlin668/loneliness``.  A dashed mean reference line and a light
fill-between highlight days above and below average.
"""

from datetime import date as date_type
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from egon.limbic.loneliness import LonelinessScore
from egon.plot_style import apply_style

_COLOUR = "#7B4EA6"  # muted purple — social/emotional dimension


def plot_loneliness(
    data: list[tuple[date_type, LonelinessScore]],
    output_path: Path | None,
    title: str = "Loneliness signal",
) -> "plt.Figure | None":
    """
    Single-panel line chart of daily loneliness probability.

    *data* is a list of (date, LonelinessScore) tuples as returned by
    ``loneliness_by_day()``.  Pass *output_path=None* to return the figure
    instead of saving it.
    """
    if not data:
        raise ValueError("No loneliness data found — nothing to plot.")

    apply_style()
    dates, scores = zip(*data)
    lonely_signal = [s.lonely for s in scores]
    mean_val = float(np.mean(lonely_signal))

    fig, ax = plt.subplots(figsize=(14, 4), layout="constrained")

    ax.plot(dates, lonely_signal, color=_COLOUR, linewidth=1.5, alpha=0.9)
    ax.axhline(
        mean_val,
        color=_COLOUR,
        linewidth=0.8,
        linestyle="--",
        alpha=0.5,
        label=f"mean {mean_val:.2f}",
    )
    ax.fill_between(dates, lonely_signal, alpha=0.12, color=_COLOUR)

    ax.set_ylabel("loneliness probability")
    ax.set_ylim(0, 1)
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return None
