"""
Cognitive bias detection report plot.

Two-panel figure:
  Top    — daily distortion signal (1 − no-distortion probability) as a line chart.
           Shows on which days distorted thinking patterns appear most strongly.
  Bottom — stacked area of the seven distortion types (Personalization, Emotional
           Reasoning, Overgeneralizing, Labeling, Should Statements, Catastrophizing,
           Reward Fallacy), showing the composition of distorted writing over time.
"""

from datetime import date as date_type
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from egon.limbic.cognitive_bias import BIASES, DISTORTION_TYPES, CognitiveBiasScores
from egon.plot_style import apply_style

_COLOURS: dict[str, str] = {
    "PERSONALIZATION": "#C44E52",
    "EMOTIONAL REASONING": "#DD8452",
    "OVERGENERALIZING": "#8172B3",
    "LABELING": "#4C72B0",
    "SHOULD STATEMENTS": "#55A868",
    "CATASTROPHIZING": "#CC6677",
    "REWARD FALLACY": "#F0C05A",
}


def plot_cognitive_bias(
    data: list[tuple[date_type, CognitiveBiasScores]],
    output_path: Path | None,
    title: str = "Cognitive bias profile",
) -> "plt.Figure | None":
    """
    Two-panel figure:
      Top    — daily distortion signal (0–1 line).
      Bottom — stacked area of the 7 distortion types.
    """
    if not data:
        raise ValueError("No cognitive bias data found — nothing to plot.")

    apply_style()
    dates, scores = zip(*data)

    distortion_signal = [s.distortion_score for s in scores]
    distortion_series = {bias: [s[BIASES.index(bias)] for s in scores] for bias in DISTORTION_TYPES}

    fig, (ax_line, ax_stack) = plt.subplots(
        2, 1, figsize=(14, 7), sharex=True, layout="constrained"
    )

    # --- Top: overall distortion signal ---
    ax_line.plot(
        dates,
        distortion_signal,
        color="#B05050",
        linewidth=1.5,
        alpha=0.9,
    )
    ax_line.axhline(
        np.mean(distortion_signal),
        color="#B05050",
        linewidth=0.8,
        linestyle="--",
        alpha=0.5,
        label=f"mean {np.mean(distortion_signal):.2f}",
    )
    ax_line.fill_between(dates, distortion_signal, alpha=0.12, color="#B05050")
    ax_line.set_ylabel("distortion signal")
    ax_line.set_ylim(0, 1)
    ax_line.set_title(title)
    ax_line.legend(frameon=False, fontsize=8.5)
    ax_line.spines["top"].set_visible(False)
    ax_line.spines["right"].set_visible(False)

    # --- Bottom: stacked area by distortion type ---
    ys = [distortion_series[b] for b in DISTORTION_TYPES]
    colours = [_COLOURS[b] for b in DISTORTION_TYPES]
    labels = [b.title() for b in DISTORTION_TYPES]
    ax_stack.stackplot(dates, ys, labels=labels, colors=colours, alpha=0.80)
    ax_stack.set_ylabel("distortion type probability")
    ax_stack.set_ylim(0, None)
    ax_stack.spines["top"].set_visible(False)
    ax_stack.spines["right"].set_visible(False)
    ax_stack.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        frameon=False,
        fontsize=8.5,
    )

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax_stack.xaxis.set_major_locator(locator)
    ax_stack.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return None
