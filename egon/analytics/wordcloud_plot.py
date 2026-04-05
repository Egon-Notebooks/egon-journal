"""
Word cloud plot for journal entries.
"""
import re
from pathlib import Path

import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS

from egon.analytics.loader import JournalEntry

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Common Logseq/Markdown structural tokens that add no meaning
_EXTRA_STOPWORDS = {
    "will", "one", "also", "get", "got", "go", "went", "day", "time",
    "today", "yesterday", "week", "bit", "felt", "feel", "feeling",
    "think", "thinking", "thought", "know", "really", "quite", "much",
    "still", "like", "just", "little", "lot", "things", "thing",
    "back", "going", "way", "good", "made", "done", "said", "want",
    "need", "make", "see", "look", "come", "came", "something",
}


def _combined_text(entries: list[JournalEntry]) -> str:
    """Concatenate all entry bodies, stripping HTML comments."""
    parts = [_COMMENT_RE.sub("", e.body) for e in entries]
    return " ".join(parts)


def plot_wordcloud(
    entries: list[JournalEntry],
    output_path: Path,
    title: str = "Journal word cloud",
) -> None:
    """
    Generate a word cloud from all journal entry bodies and save to *output_path*.
    """
    if not entries:
        raise ValueError("No journal entries found — nothing to plot.")

    text = _combined_text(entries)
    stopwords = STOPWORDS | _EXTRA_STOPWORDS

    wc = WordCloud(
        width=2400,
        height=1200,
        background_color="white",
        colormap="Blues",
        collocations=False,
        stopwords=stopwords,
        max_words=200,
    ).generate(text)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(title, fontsize=14, pad=12)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
