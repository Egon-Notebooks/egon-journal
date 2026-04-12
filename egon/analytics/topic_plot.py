"""
BERTopic topic modelling for journal entries.

Discovers latent themes in the journal corpus using BERTopic (Grootendorst 2022).
Two plots are produced:

  plot_topic_summary  — horizontal bar chart showing each topic's size and its
                        top keywords.  A good first overview of what you write about.

  plot_topic_timeline — stacked area chart showing how topic prevalence shifts
                        over time, binned by calendar month.

Requires the ``topics`` optional dependency group:

    uv sync --extra topics          # Linux / Apple Silicon / Windows
    bash scripts/setup_limbic.sh   # Intel Mac (uses .venv-limbic)
"""

import json
import platform
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from egon.analytics.loader import JournalEntry
from egon.plot_style import apply_style

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MIN_DOCS = 10  # minimum entries needed for meaningful topic modelling
_LIMBIC_VENV = Path(__file__).resolve().parents[2] / ".venv-limbic"


def _use_subprocess_venv() -> bool:
    return (
        _LIMBIC_VENV.is_dir() and platform.system() == "Darwin" and platform.machine() == "x86_64"
    )


def _clean(text: str) -> str:
    return _COMMENT_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Thin model wrapper — same interface whether fitted locally or via subprocess
# ---------------------------------------------------------------------------


class _TopicModel:
    """
    Holds BERTopic results in a plain-Python structure.

    Provides a minimal subset of the BERTopic API used by the plot functions
    so that the plots work identically regardless of how the model was fitted.
    """

    def __init__(
        self,
        topic_info: list[dict],  # [{"Topic": int, "Count": int}, ...], outlier row excluded
        topics: dict[str, list],  # str(topic_id) -> [[word, score], ...]
    ) -> None:
        self._topic_info = topic_info
        self._topics: dict[int, list[tuple[str, float]]] = {
            int(k): [(w, s) for w, s in v] for k, v in topics.items()
        }

    def get_topic_info(self) -> list[dict]:
        """Return list of {"Topic": int, "Count": int} dicts (outlier excluded)."""
        return self._topic_info

    def get_topic(self, tid: int) -> list[tuple[str, float]]:
        return self._topics.get(tid, [])


# ---------------------------------------------------------------------------
# Fitting — subprocess (Intel Mac) vs. in-process (everything else)
# ---------------------------------------------------------------------------

_SUBPROCESS_SCRIPT = """\
# Pure-sklearn NMF topic modelling — no umap-learn, numba, llvmlite, or BERTopic needed.
import json, sys
from collections import Counter
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

data = json.loads(sys.stdin.read())
docs = data["docs"]
nr_topics = data["nr_topics"]
n_docs = len(docs)
n_topics = nr_topics if isinstance(nr_topics, int) else min(10, max(2, n_docs // 5))

vectorizer = TfidfVectorizer(max_features=5000, stop_words="english", min_df=2)
tfidf = vectorizer.fit_transform(docs)
nmf = NMF(n_components=n_topics, random_state=42, max_iter=400)
W = nmf.fit_transform(tfidf)

topic_ids = W.argmax(axis=1).tolist()
feature_names = vectorizer.get_feature_names_out()

topics_data = {}
for idx, component in enumerate(nmf.components_):
    top_idx = component.argsort()[-10:][::-1]
    topics_data[str(idx)] = [[feature_names[i], float(component[i])] for i in top_idx]

counts = Counter(topic_ids)
topic_info = [
    {"Topic": int(tid), "Count": int(counts[tid])}
    for tid in sorted(counts, key=lambda t: -counts[t])
]
print(json.dumps({"topic_ids": topic_ids, "topic_info": topic_info, "topics": topics_data}))
"""


def _fit_via_subprocess(
    docs: list[str],
    nr_topics: int | str,
    min_topic_size: int,
) -> tuple[list[int], _TopicModel]:
    python = _LIMBIC_VENV / "bin" / "python"
    payload = json.dumps({"docs": docs, "nr_topics": nr_topics, "min_topic_size": min_topic_size})
    try:
        proc = subprocess.run(
            [str(python), "-c", _SUBPROCESS_SCRIPT],
            input=payload,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"BERTopic subprocess failed:\n{exc.stderr}") from exc
    data = json.loads(proc.stdout.strip())
    return data["topic_ids"], _TopicModel(data["topic_info"], data["topics"])


def _fit_locally(
    docs: list[str],
    nr_topics: int | str,
    min_topic_size: int,
) -> tuple[list[int], _TopicModel]:
    try:
        from bertopic import BERTopic
    except ImportError as exc:
        raise ImportError(
            "BERTopic is not installed.\n"
            "On Linux/Apple Silicon/Windows: uv sync --extra topics\n"
            "On Intel Mac: bash scripts/setup_limbic.sh"
        ) from exc

    model = BERTopic(
        nr_topics=nr_topics,
        min_topic_size=min_topic_size,
        verbose=False,
        calculate_probabilities=False,
    )
    topic_ids, _ = model.fit_transform(docs)
    ti = model.get_topic_info()
    ti_filtered = ti[ti["Topic"] != -1]
    topics_data: dict[str, list] = {}
    for tid in ti_filtered["Topic"].tolist():
        topics_data[str(tid)] = model.get_topic(tid)
    topic_info = [
        {"Topic": int(r["Topic"]), "Count": int(r["Count"])} for _, r in ti_filtered.iterrows()
    ]
    return [int(t) for t in topic_ids], _TopicModel(topic_info, topics_data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fit_topics(
    entries: list[JournalEntry],
    nr_topics: int | str = "auto",
    min_topic_size: int = 3,
) -> tuple[list[int], list[str], _TopicModel]:
    """
    Fit BERTopic on *entries* and return (topic_ids, docs, model).

    Topic id −1 means 'outlier / noise'.
    Uses .venv-limbic via subprocess on Intel Mac; fits in-process elsewhere.
    """
    if len(entries) < _MIN_DOCS:
        raise ValueError(
            f"Need at least {_MIN_DOCS} journal entries for topic modelling (got {len(entries)})."
        )
    docs = [_clean(e.body) for e in entries]
    if _use_subprocess_venv():
        topic_ids, model = _fit_via_subprocess(docs, nr_topics, min_topic_size)
    else:
        topic_ids, model = _fit_locally(docs, nr_topics, min_topic_size)
    return topic_ids, docs, model


def plot_topic_summary(
    entries: list[JournalEntry],
    output_path: Path | None,
    title: str = "Journal topic summary",
    nr_topics: int | str = "auto",
    min_topic_size: int = 3,
    top_n_topics: int = 12,
) -> "plt.Figure | None":
    """
    Horizontal bar chart: each bar is a discovered topic, sized by frequency,
    labelled with its top keywords.
    """
    if not entries:
        raise ValueError("No journal entries found — nothing to plot.")

    apply_style()
    topic_ids, _docs, model = fit_topics(entries, nr_topics, min_topic_size)

    topic_info_rows = model.get_topic_info()[:top_n_topics]

    if not topic_info_rows:
        raise ValueError("BERTopic found no coherent topics in the corpus.")

    labels, counts = [], []
    for row in topic_info_rows:
        tid = row["Topic"]
        words = [w for w, _ in model.get_topic(tid)[:6]]
        labels.append(" · ".join(words))
        counts.append(row["Count"])

    # Reverse so the largest topic is at the top.
    labels = labels[::-1]
    counts = counts[::-1]

    n = len(labels)
    palette = plt.colormaps["tab10"].resampled(max(n, 1))
    colours = [palette(i) for i in range(n)]

    fig, ax = plt.subplots(figsize=(14, max(4, n * 0.65)))
    bars = ax.barh(range(n), counts, color=colours[::-1], alpha=0.85)
    ax.bar_label(bars, padding=4, fontsize=8.5, color="#444444")

    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("number of entries", fontsize=10)
    ax.set_title(title, pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return None


def plot_topic_timeline(
    entries: list[JournalEntry],
    output_path: Path | None,
    title: str = "Journal topic timeline",
    nr_topics: int | str = "auto",
    min_topic_size: int = 3,
    top_n_topics: int = 8,
) -> "plt.Figure | None":
    """
    Stacked area chart of topic prevalence binned by calendar month.

    Only the top *top_n_topics* topics are shown; remaining entries are
    grouped into 'other'.
    """
    if not entries:
        raise ValueError("No journal entries found — nothing to plot.")

    apply_style()
    topic_ids, _docs, model = fit_topics(entries, nr_topics, min_topic_size)

    topic_info_rows = model.get_topic_info()

    if not topic_info_rows:
        raise ValueError("BERTopic found no coherent topics in the corpus.")

    # Build label map for the top N topics
    top_ids = [row["Topic"] for row in topic_info_rows[:top_n_topics]]
    label_map: dict[int, str] = {}
    for tid in top_ids:
        words = [w for w, _ in model.get_topic(tid)[:4]]
        label_map[tid] = " · ".join(words)

    # Assign each entry a (year-month, topic_label)
    month_topic: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for entry, tid in zip(entries, topic_ids):
        ym = entry.date.strftime("%Y-%m")
        lbl = label_map.get(tid, "other") if tid != -1 else "other"
        month_topic[ym][lbl] += 1

    months = sorted(month_topic.keys())
    if len(months) < 2:
        raise ValueError("Need entries spanning at least 2 months for a timeline.")

    all_labels = list(label_map.values()) + ["other"]
    matrix = np.zeros((len(all_labels), len(months)))
    for j, ym in enumerate(months):
        for i, lbl in enumerate(all_labels):
            matrix[i, j] = month_topic[ym].get(lbl, 0)

    # Drop 'other' row if it's all zeros
    other_idx = len(all_labels) - 1
    if matrix[other_idx].sum() == 0:
        matrix = matrix[:other_idx]
        all_labels = all_labels[:other_idx]

    palette = plt.colormaps["tab10"].resampled(max(len(all_labels), 1))
    colours = [palette(i) for i in range(len(all_labels))]

    x = np.arange(len(months))
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.stackplot(x, matrix, labels=all_labels, colors=colours, alpha=0.80)

    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha="right", fontsize=8.5)
    ax.set_ylabel("entries per month", fontsize=10)
    ax.set_title(title, pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        frameon=False,
        fontsize=8,
    )

    fig.tight_layout()
    if output_path is None:
        return fig
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return None
