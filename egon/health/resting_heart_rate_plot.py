"""
Resting heart rate report plot.
"""
from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_resting_heart_rate(
    data: list[tuple[date_type, float]],
    output_path: Path,
    title: str = "Resting heart rate",
    unit: str = "bpm",
) -> None:
    """
    Plot daily mean resting heart rate over time and save to *output_path*.
    A dashed line shows the average over the plotted period.
    """
    if not data:
        raise ValueError("No resting heart rate data found — nothing to plot.")

    dates, values = zip(*data)
    avg = mean(values)

    fig, ax = plt.subplots(figsize=(14, 4))

    ax.plot(dates, values, color="#C44E52", linewidth=1.5, alpha=0.9)
    ax.scatter(dates, values, color="#C44E52", s=18, zorder=3, alpha=0.7)
    ax.axhline(avg, color="#C44E52", linewidth=0.9, linestyle="--", alpha=0.5,
               label=f"avg {avg:.0f} {unit}")
    ax.legend(frameon=False, fontsize=9)

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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
