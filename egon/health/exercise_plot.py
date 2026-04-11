"""
Apple Exercise Time report plot — daily exercise minutes from Apple Health.

Apple Health records ``AppleExerciseTime`` as the number of minutes per day
that the user's heart rate was elevated above a brisk-walk threshold, matching
the Apple Watch "Exercise" ring.  The WHO recommends ≥ 30 minutes of
moderate-intensity activity per day (150 min/week).
"""

from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.plot_style import apply_style

_WHO_DAILY_TARGET = 30  # minutes — WHO moderate-intensity guideline


def plot_exercise(
    data: list[tuple[date_type, float]],
    output_path: Path | None,
    title: str = "Daily exercise time",
    unit: str = "min",
    target_exercise_minutes: float | None = None,
) -> "plt.Figure | None":
    """
    Plot daily exercise minutes as a bar chart and save to *output_path*.

    A dashed average line and a dotted WHO 30-min guideline (or custom target)
    are drawn for reference.
    """
    if not data:
        raise ValueError("No exercise time data found — nothing to plot.")

    apply_style()
    dates, values = zip(*data)
    avg = mean(values)

    _COLOUR = "#26A69A"
    target = target_exercise_minutes if target_exercise_minutes is not None else _WHO_DAILY_TARGET

    fig, ax = plt.subplots(figsize=(14, 4))

    ax.bar(dates, values, width=0.8, color=_COLOUR, alpha=0.80)
    ax.axhline(
        avg,
        color=_COLOUR,
        linewidth=0.9,
        linestyle="--",
        alpha=0.6,
        label=f"avg {avg:.0f} {unit}",
    )
    target_label = (
        f"{'goal' if target_exercise_minutes is not None else 'WHO guideline'} {target:.0f} {unit}"
    )
    ax.axhline(
        target,
        color="#888888",
        linewidth=0.9,
        linestyle=":",
        alpha=0.7,
        label=target_label,
    )
    ax.legend(frameon=False)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel(f"exercise time ({unit})")
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
