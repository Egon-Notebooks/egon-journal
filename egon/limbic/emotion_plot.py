"""
Emotion detection report plot — stacked area chart of daily emotion probabilities.

Seven emotions are shown as stacked areas (anger, disgust, fear, joy, neutral,
sadness, surprise) so the balance between positive and negative affect is
immediately visible.  A separate line chart below shows just joy and sadness
for easy day-to-day reading.
"""

from datetime import date as date_type
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from egon.limbic.emotion import EMOTIONS, EmotionScores
from egon.plot_style import apply_style

# Colours aligned with emotional valence:
# warm (anger/disgust/fear/sadness) → reds/purples; positive → gold/green; neutral → grey
_COLOURS = {
    "anger": "#C44E52",
    "disgust": "#8172B3",
    "fear": "#DD8452",
    "joy": "#55A868",
    "neutral": "#CCCCCC",
    "sadness": "#4C72B0",
    "surprise": "#F0C05A",
}


def plot_emotion(
    data: list[tuple[date_type, EmotionScores]],
    output_path: Path | None,
    title: str = "Daily emotion profile",
) -> "plt.Figure | None":
    """
    Two-panel figure:
      Top  — stacked area chart of all 7 emotion scores (sum ≈ 1 per day).
      Bottom — line chart of joy vs. sadness for easy comparison.
    """
    if not data:
        raise ValueError("No emotion data found — nothing to plot.")

    apply_style()
    dates, scores = zip(*data)

    emotion_series = {e: [s[i] for s in scores] for i, e in enumerate(EMOTIONS)}

    fig, (ax_stack, ax_line) = plt.subplots(
        2, 1, figsize=(14, 7), sharex=True, layout="constrained"
    )

    # --- Stacked area ---
    ys = [emotion_series[e] for e in EMOTIONS]
    colours = [_COLOURS[e] for e in EMOTIONS]
    ax_stack.stackplot(dates, ys, labels=EMOTIONS, colors=colours, alpha=0.80)
    ax_stack.set_ylabel("emotion probability")
    ax_stack.set_ylim(0, 1)
    ax_stack.set_title(title)
    ax_stack.spines["top"].set_visible(False)
    ax_stack.spines["right"].set_visible(False)
    ax_stack.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        frameon=False,
        fontsize=8.5,
    )

    # --- Joy vs sadness line ---
    ax_line.plot(
        dates,
        emotion_series["joy"],
        color=_COLOURS["joy"],
        linewidth=1.5,
        alpha=0.9,
        label="joy",
    )
    ax_line.plot(
        dates,
        emotion_series["sadness"],
        color=_COLOURS["sadness"],
        linewidth=1.5,
        alpha=0.9,
        label="sadness",
    )
    ax_line.set_ylabel("probability")
    ax_line.set_ylim(0, None)
    ax_line.legend(frameon=False, fontsize=9)
    ax_line.spines["top"].set_visible(False)
    ax_line.spines["right"].set_visible(False)

    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    formatter = mdates.ConciseDateFormatter(locator)
    ax_line.xaxis.set_major_locator(locator)
    ax_line.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate(rotation=30)

    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return None
