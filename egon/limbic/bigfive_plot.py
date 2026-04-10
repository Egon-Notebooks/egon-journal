"""
Big Five personality trait report plot.

Five subplots stacked vertically (one per trait), sharing a common x-axis.
Each subplot shows the daily trait score as a line+scatter chart.
To the right of each subplot the trait letter and period average are annotated.
"""

from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.limbic.bigfive import TRAITS, BigFiveScores
from egon.plot_style import ANNOTATION_SIZE, apply_style

# One colour per trait: O, C, E, A, N
_COLOURS = ["#4C72B0", "#55A868", "#DD8452", "#C44E52", "#8172B3"]

# Population norms (Schmitt et al. 2007 meta-analysis, 1–5 Likert scale).
# The regression model was trained on 1–5 BFI data so these values are
# directly comparable to its output range.
_POP_AVG: dict[str, float] = {
    "O": 3.9,
    "C": 3.5,
    "E": 3.2,
    "A": 3.7,
    "N": 3.1,
}


def plot_bigfive(
    data: list[tuple[date_type, BigFiveScores]],
    output_path: Path | None,
    title: str = "Big Five personality traits",
) -> None:
    """
    Plot daily Big Five trait scores and save to *output_path*.

    *data* is a list of (date, BigFiveScores) tuples sorted by date.
    For each of the 5 traits:
      - a line+scatter chart shows the daily score (0–1)
      - to the right, the trait letter and period average are annotated
    """
    if not data:
        raise ValueError("No Big Five data found — nothing to plot.")

    apply_style()
    dates, scores = zip(*data)

    fig, axes = plt.subplots(
        5,
        1,
        figsize=(14, 14),
        sharex=True,
        layout="constrained",
    )

    for i, (ax, (letter, name), colour) in enumerate(zip(axes, TRAITS, _COLOURS)):
        values = [s[i] for s in scores]
        avg = mean(values)

        ax.plot(dates, values, color=colour, linewidth=1.5, alpha=0.9)
        ax.scatter(dates, values, color=colour, s=18, zorder=3, alpha=0.7)
        ax.axhline(avg, color=colour, linewidth=0.9, linestyle="--", alpha=0.5)

        pop_avg = _POP_AVG[letter]
        ax.axhline(
            pop_avg,
            color="#888888",
            linewidth=0.9,
            linestyle=":",
            alpha=0.6,
            label=f"pop avg {pop_avg:.1f}",
        )

        ax.set_ylabel(name)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Trait letter + period average + population average annotated to the right
        ax.annotate(
            f"{letter}\n{avg:.2f}",
            xy=(1.02, 0.5),
            xycoords="axes fraction",
            fontsize=ANNOTATION_SIZE,
            fontweight="bold",
            color=colour,
            va="center",
            ha="left",
        )
        ax.annotate(
            f"pop {pop_avg:.1f}",
            xy=(1.02, 0.5),
            xycoords="axes fraction",
            xytext=(0, -ANNOTATION_SIZE * 1.4),
            textcoords="offset points",
            fontsize=ANNOTATION_SIZE * 0.55,
            color="#888888",
            va="top",
            ha="left",
        )

    axes[0].set_title(title)

    # x-axis formatting on the bottom panel
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
