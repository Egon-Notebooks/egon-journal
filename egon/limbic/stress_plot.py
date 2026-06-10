"""
Psychological stress report plot.

Single-panel line chart of daily stress probability (0–1) derived from
``jnyx74/stress-prediction``.  A dashed mean reference line and a light
fill-between highlight days above and below average.
"""

from datetime import date as date_type
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from egon.limbic.stress import StressScore
from egon.plot_style import apply_style

_COLOUR = "#C0392B"  # muted red — stress is a negative signal


def plot_stress(
    data: list[tuple[date_type, StressScore]],
    output_path: Path | None,
    title: str = "Psychological stress signal",
) -> "plt.Figure | None":
    """
    Single-panel line chart of daily stress probability.

    *data* is a list of (date, StressScore) tuples as returned by
    ``stress_by_day()``.  Pass *output_path=None* to return the figure
    instead of saving it.
    """
    if not data:
        raise ValueError("No stress data found — nothing to plot.")

    apply_style()
    dates, scores = zip(*data)
    stress_signal = [s.stress for s in scores]
    mean_val = float(np.mean(stress_signal))

    fig, ax = plt.subplots(figsize=(14, 4), layout="constrained")

    ax.plot(dates, stress_signal, color=_COLOUR, linewidth=1.5, alpha=0.9)
    ax.axhline(
        mean_val,
        color=_COLOUR,
        linewidth=0.8,
        linestyle="--",
        alpha=0.5,
        label=f"mean {mean_val:.2f}",
    )
    ax.fill_between(dates, stress_signal, alpha=0.12, color=_COLOUR)

    ax.set_ylabel("stress probability")
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
