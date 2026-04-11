"""
First-person pronoun ratio plot.

Tracks the fraction of words that are first-person pronouns (I, me, my, mine,
myself) per journal entry over time.  High pronoun density is associated with
self-focused processing, which in turn correlates with depressive rumination in
psycholinguistics research (Pennebaker et al. 2003).
"""

import re
from datetime import date as date_type
from pathlib import Path
from statistics import mean

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.analytics.loader import JournalEntry
from egon.plot_style import apply_style

_FIRST_PERSON = re.compile(r"\b(I|me|my|mine|myself)\b")
_WORD = re.compile(r"\b\w+\b")


def pronoun_ratio_by_day(
    entries: list[JournalEntry],
) -> list[tuple[date_type, float]]:
    """
    Return daily first-person pronoun ratio (pronouns / total words).
    Entries with zero words return 0.0.
    """
    result: list[tuple[date_type, float]] = []
    for entry in entries:
        words = _WORD.findall(entry.body)
        n = len(words)
        if n == 0:
            result.append((entry.date, 0.0))
            continue
        pronouns = len(_FIRST_PERSON.findall(entry.body))
        result.append((entry.date, pronouns / n))
    return sorted(result, key=lambda x: x[0])


def plot_pronoun_ratio(
    entries: list[JournalEntry],
    output_path: Path | None,
    title: str = "First-person pronoun ratio",
) -> "plt.Figure | None":
    """
    Plot the daily first-person pronoun ratio and save to *output_path*.

    A dashed average line is drawn.  The y-axis is shown as a percentage.
    """
    if not entries:
        raise ValueError("No journal entries found — nothing to plot.")

    apply_style()
    data = pronoun_ratio_by_day(entries)
    dates, values = zip(*data)
    pct = [v * 100 for v in values]
    avg_pct = mean(pct)

    _COLOUR = "#8172B3"

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(dates, pct, color=_COLOUR, linewidth=1.5, alpha=0.9)
    ax.scatter(dates, pct, color=_COLOUR, s=18, zorder=3, alpha=0.7)
    ax.axhline(
        avg_pct,
        color=_COLOUR,
        linewidth=0.9,
        linestyle="--",
        alpha=0.5,
        label=f"avg {avg_pct:.1f} %",
    )
    ax.legend(frameon=False)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel("pronoun ratio (%)")
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
