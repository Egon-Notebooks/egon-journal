"""
MBTI personality dimension report plot.

Four subplots stacked vertically (one per MBTI dimension), sharing a common x-axis.
Each subplot shows the daily binary dimension score (0 or 1) as a scatter chart.
A dashed average line shows the proportion of days leaning toward each pole.
To the right of each subplot the dominant pole letter and proportion are annotated.
"""
from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.limbic.mbti import DIMENSIONS, MBTIScores
from egon.plot_style import ANNOTATION_SIZE, apply_style

# One colour per dimension: E/I, N/S, T/F, J/P
_COLOURS = ["#4C72B0", "#55A868", "#DD8452", "#C44E52"]


def plot_mbti(
    data: list[tuple[date_type, MBTIScores]],
    output_path: Path | None,
    title: str = "MBTI personality dimensions",
) -> None:
    """
    Plot daily MBTI dimension scores and save to *output_path*.

    *data* is a list of (date, MBTIScores) tuples sorted by date.
    For each of the 4 dimensions:
      - scatter chart shows the daily binary value (0 or 1, or fractional
        average when multiple entries exist on the same day)
      - dashed line shows the period average (proportion toward positive pole)
      - y-axis is labelled with both poles at 0 and 1
      - right-side annotation shows the dominant pole letter and proportion
    """
    if not data:
        raise ValueError("No MBTI data found — nothing to plot.")

    apply_style()
    dates, scores = zip(*data)

    fig, axes = plt.subplots(
        4, 1,
        figsize=(14, 11),
        sharex=True,
        layout="constrained",
    )

    for i, (ax, (pos, neg, label), colour) in enumerate(
        zip(axes, DIMENSIONS, _COLOURS)
    ):
        values = [s[i] for s in scores]
        avg = mean(values)
        dominant = pos if avg >= 0.5 else neg
        dominant_pct = avg if avg >= 0.5 else 1 - avg

        ax.scatter(dates, values, color=colour, s=22, zorder=3, alpha=0.8)
        ax.axhline(avg, color=colour, linewidth=1.0, linestyle="--", alpha=0.7)

        ax.set_ylim(-0.25, 1.25)
        ax.set_yticks([0, 1])
        ax.set_yticklabels([neg, pos])
        ax.set_ylabel(label)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Dominant pole + proportion annotated to the right
        ax.annotate(
            f"{dominant}\n{dominant_pct:.0%}",
            xy=(1.02, 0.5),
            xycoords="axes fraction",
            fontsize=ANNOTATION_SIZE,
            fontweight="bold",
            color=colour,
            va="center",
            ha="left",
        )

    axes[0].set_title(title)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    axes[-1].xaxis.set_major_locator(locator)
    axes[-1].xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return None
