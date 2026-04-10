"""
Resting heart rate report plot.
"""
from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.plot_style import apply_style


def plot_resting_heart_rate(
    data: list[tuple[date_type, float]],
    output_path: Path | None,
    title: str = "Resting heart rate",
    unit: str = "bpm",
    target_resting_heart_rate: float | None = None,
) -> "plt.Figure | None":
    """
    Plot daily mean resting heart rate over time and save to *output_path*.
    A dashed line shows the average over the plotted period.
    An optional dotted goal line is drawn when *target_resting_heart_rate* is given.
    """
    if not data:
        raise ValueError("No resting heart rate data found — nothing to plot.")

    apply_style()
    dates, values = zip(*data)
    avg = mean(values)

    fig, ax = plt.subplots(figsize=(14, 4))

    ax.plot(dates, values, color="#C44E52", linewidth=1.5, alpha=0.9)
    ax.scatter(dates, values, color="#C44E52", s=18, zorder=3, alpha=0.7)
    ax.axhline(avg, color="#C44E52", linewidth=0.9, linestyle="--", alpha=0.5,
               label=f"avg {avg:.0f} {unit}")
    if target_resting_heart_rate is not None:
        ax.axhline(target_resting_heart_rate, color="#C44E52", linewidth=0.9,
                   linestyle=":", alpha=0.7,
                   label=f"goal {target_resting_heart_rate:.0f} {unit}")
    ax.legend(frameon=False)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel(f"resting heart rate ({unit})")
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
