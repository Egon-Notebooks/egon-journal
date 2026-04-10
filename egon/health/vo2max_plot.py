"""
VO2 max report plot.

Apple Health records VO2 max as VO2Max — estimated maximal oxygen uptake
in mL/min/kg. Higher values indicate better aerobic fitness.
"""
from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.plot_style import apply_style


def plot_vo2max(
    data: list[tuple[date_type, float]],
    output_path: Path | None,
    title: str = "VO2 max",
    unit: str = "mL/min/kg",
) -> "plt.Figure | None":
    """
    Plot daily mean VO2 max over time and save to *output_path*.
    A dashed line shows the average over the plotted period.
    """
    if not data:
        raise ValueError("No VO2 max data found — nothing to plot.")

    apply_style()
    dates, values = zip(*data)
    avg = mean(values)

    fig, ax = plt.subplots(figsize=(14, 4))

    ax.plot(dates, values, color="#8172B3", linewidth=1.5, alpha=0.9)
    ax.scatter(dates, values, color="#8172B3", s=18, zorder=3, alpha=0.7)
    ax.axhline(avg, color="#8172B3", linewidth=0.9, linestyle="--", alpha=0.5,
               label=f"avg {avg:.1f} {unit}")
    ax.legend(frameon=False)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel(f"VO2 max ({unit})")
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
