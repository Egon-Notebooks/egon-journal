"""
Step count report plot — daily total steps as indicator of physical activity.
"""
from datetime import date as date_type
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.plot_style import apply_style

_STEPS_10K = 10_000


def plot_step_count(
    data: list[tuple[date_type, float]],
    output_path: Path | None,
    title: str = "Daily step count",
    unit: str = "count",
) -> "plt.Figure | None":
    """
    Plot daily total step count as a bar chart and save to *output_path*.

    A 10,000-step reference line is drawn as a guideline.
    *data* is a list of (date, steps) tuples, already filtered to the desired
    period and sorted by date.
    """
    if not data:
        raise ValueError("No step count data found — nothing to plot.")

    apply_style()
    dates, values = zip(*data)

    fig, ax = plt.subplots(figsize=(14, 4))

    ax.bar(dates, values, width=0.8, color="#4CAF50", alpha=0.85)
    ax.axhline(_STEPS_10K, color="grey", linewidth=0.8, linestyle="--", alpha=0.5)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel("steps")
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    return None
