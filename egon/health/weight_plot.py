"""
Weight (BodyMass) report plot, with optional LeanBodyMass overlay.
"""
from datetime import date as date_type
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_weight(
    data: list[tuple[date_type, float]],
    output_path: Path,
    title: str = "Weight",
    unit: str = "kg",
    lean_data: list[tuple[date_type, float]] | None = None,
) -> None:
    """
    Plot daily mean weight over time and save to *output_path*.

    If *lean_data* is provided, lean body mass is overlaid as a second series.
    *data* and *lean_data* are lists of (date, value) tuples, already filtered
    to the desired period and sorted by date.
    """
    if not data:
        raise ValueError("No weight data found — nothing to plot.")

    dates, values = zip(*data)

    fig, ax = plt.subplots(figsize=(14, 4))

    ax.plot(dates, values, color="#4C72B0", linewidth=1.5, alpha=0.9,
            label=f"Body mass ({unit})")
    ax.scatter(dates, values, color="#4C72B0", s=18, zorder=3, alpha=0.7)

    if lean_data:
        lean_dates, lean_values = zip(*lean_data)
        ax.plot(lean_dates, lean_values, color="#DD8452", linewidth=1.5,
                alpha=0.9, label=f"Lean body mass ({unit})")
        ax.scatter(lean_dates, lean_values, color="#DD8452", s=18, zorder=3,
                   alpha=0.7)
        ax.legend(frameon=False, fontsize=9)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel(f"weight ({unit})")
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
