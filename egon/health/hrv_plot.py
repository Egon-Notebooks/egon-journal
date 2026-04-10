"""
Heart rate variability (HRV) report plot.

Apple Health records HRV as HeartRateVariabilitySDNN — the standard deviation
of beat-to-beat intervals, measured in milliseconds. Higher values generally
indicate better cardiovascular recovery.
"""
from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.plot_style import apply_style


def plot_hrv(
    data: list[tuple[date_type, float]],
    output_path: Path | None,
    title: str = "Heart rate variability (HRV)",
    unit: str = "ms",
) -> "plt.Figure | None":
    """
    Plot daily mean HRV over time and save to *output_path*.
    """
    if not data:
        raise ValueError("No HRV data found — nothing to plot.")

    apply_style()
    dates, values = zip(*data)
    avg = mean(values)

    fig, ax = plt.subplots(figsize=(14, 4))

    ax.plot(dates, values, color="#55A868", linewidth=1.5, alpha=0.9)
    ax.scatter(dates, values, color="#55A868", s=18, zorder=3, alpha=0.7)
    ax.axhline(avg, color="#55A868", linewidth=0.9, linestyle="--", alpha=0.5,
               label=f"avg {avg:.0f} {unit}")
    ax.legend(frameon=False)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel(f"HRV SDNN ({unit})")
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
