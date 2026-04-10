"""
Sentiment-by-day plot for the Limbic engine.
"""
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from egon.analytics.loader import JournalEntry
from egon.limbic.sentiment import sentiment_by_day
from egon.plot_style import apply_style


def plot_sentiment(
    entries: list[JournalEntry],
    output_path: Path | None,
    title: str = "Journal sentiment by day",
) -> "plt.Figure | None":
    """
    Generate a sentiment-by-day bar chart and save it to *output_path*.

    Bars are coloured on a red–grey–green gradient based on the VADER
    compound score. The neutral band ([-0.05, +0.05]) is shown in grey.
    """
    apply_style()
    data = sentiment_by_day(entries)
    if not data:
        raise ValueError("No journal entries found — nothing to plot.")

    dates, scores = zip(*data)
    scores_arr = np.array(scores, dtype=float)

    # Map [-1, +1] → colour via a diverging red–grey–green palette
    cmap = plt.get_cmap("RdYlGn")
    colours = [cmap((s + 1) / 2) for s in scores_arr]

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.bar(dates, scores_arr, width=0.8, color=colours, alpha=0.9)

    # Neutral band reference lines
    ax.axhline(0.05,  color="grey", linewidth=0.6, linestyle="--", alpha=0.5)
    ax.axhline(-0.05, color="grey", linewidth=0.6, linestyle="--", alpha=0.5)
    ax.axhline(0.0,   color="grey", linewidth=0.8, linestyle="-",  alpha=0.3)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylim(-1.1, 1.1)
    ax.set_ylabel("sentiment (VADER compound)")
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
