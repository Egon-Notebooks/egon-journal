"""
BERTopic topic modeling for journal entries.

Discovers latent themes in the journal corpus using BERTopic (Grootendorst 2022).
``topic_summary`` gives each topic's size and keywords; ``topic_timeline``
gives entries per topic per calendar month.  Charts for both live in
``egon.report.charts.text``.

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

from egon.analytics.loader import JournalEntry

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MIN_DOCS = 10  # minimum entries needed for meaningful topic modeling
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
# Pure-sklearn NMF topic modeling — no umap-learn, numba, llvmlite, or BERTopic needed.
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
            f"Need at least {_MIN_DOCS} journal entries for topic modeling (got {len(entries)})."
        )
    docs = [_clean(e.body) for e in entries]
    if _use_subprocess_venv():
        topic_ids, model = _fit_via_subprocess(docs, nr_topics, min_topic_size)
    else:
        topic_ids, model = _fit_locally(docs, nr_topics, min_topic_size)
    return topic_ids, docs, model


TopicSummary = list[tuple[str, int]]  # (keywords label, entry count), largest first
TopicTimeline = list[tuple[str, str, int]]  # (YYYY-MM, keywords label, entry count)


def topic_label(model: _TopicModel, tid: int, n_words: int = 5) -> str:
    return " · ".join(w for w, _ in model.get_topic(tid)[:n_words])


def topic_summary(model: _TopicModel, top_n: int = 12) -> TopicSummary:
    """Topics by size (outlier topic −1 excluded), labeled with their top keywords."""
    rows = [r for r in model.get_topic_info() if r["Topic"] != -1][:top_n]
    if not rows:
        raise ValueError("BERTopic found no coherent topics in the corpus.")
    return [(topic_label(model, r["Topic"]), int(r["Count"])) for r in rows]


def topic_timeline(
    entries: list[JournalEntry], topic_ids: list[int], model: _TopicModel, top_n: int = 7
) -> TopicTimeline:
    """Entries per topic per calendar month; topics beyond *top_n* become "other"."""
    rows = [r for r in model.get_topic_info() if r["Topic"] != -1][:top_n]
    labels = {r["Topic"]: topic_label(model, r["Topic"], 4) for r in rows}
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for entry, tid in zip(entries, topic_ids, strict=False):
        counts[(entry.date.strftime("%Y-%m"), labels.get(tid, "other"))] += 1
    if len({m for m, _ in counts}) < 2:
        raise ValueError("Need entries spanning at least 2 months for a timeline.")
    return [(m, t, c) for (m, t), c in sorted(counts.items())]
