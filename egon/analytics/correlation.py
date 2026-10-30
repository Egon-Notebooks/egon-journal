"""
Cross-signal correlation statistics.

Computes pairwise Pearson correlations between daily time series (journal
signals, model-derived affect scores and Apple Health metrics).  Only days on
which both signals were recorded contribute to a pair, and pairs with fewer
than ``min_overlap`` shared days are left out.

Charts for these statistics live in ``egon.report.charts.correlation``.
"""

from dataclasses import dataclass
from datetime import date as date_type

from scipy.stats import pearsonr

Signal = list[tuple[date_type, float]]
Signals = dict[str, Signal]

# Pairs with well-documented links to mental health — (signal_a, signal_b, title).
# Rendered only when both signals are present with sufficient overlap.
MENTAL_HEALTH_PAIRS: list[tuple[str, str, str]] = [
    ("sleep (h)", "sentiment", "Sleep & next-day mood"),
    ("HRV", "B5-N", "HRV & neuroticism"),
    ("steps", "B5-E", "Physical activity & extraversion"),
    ("resting HR", "B5-N", "Resting heart rate & neuroticism"),
]

MIN_OVERLAP = 10


@dataclass(frozen=True)
class PairStat:
    a: str
    b: str
    r: float
    p: float
    n: int

    @property
    def significant(self) -> bool:
        return self.p < 0.05


def align_pairwise(a: Signal, b: Signal) -> tuple[list[date_type], list[float], list[float]]:
    """Return (dates, xs, ys) restricted to dates present in both series."""
    b_dict = dict(b)
    dates, xs, ys = [], [], []
    for d, v in a:
        if d in b_dict:
            dates.append(d)
            xs.append(v)
            ys.append(b_dict[d])
    return dates, xs, ys


def pair_stat(signals: Signals, a: str, b: str, min_overlap: int = MIN_OVERLAP) -> PairStat | None:
    """Pearson r for one pair, or None when overlap is too small or a series is constant."""
    if a not in signals or b not in signals:
        return None
    _, xs, ys = align_pairwise(signals[a], signals[b])
    if len(xs) < min_overlap or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    r, p = pearsonr(xs, ys)
    return PairStat(a, b, float(r), float(p), len(xs))


def usable_signals(signals: Signals, min_overlap: int = MIN_OVERLAP) -> list[str]:
    """Signal names with at least *min_overlap* observations, sorted alphabetically."""
    return sorted(k for k, v in signals.items() if len(v) >= min_overlap)


def correlation_matrix(signals: Signals, min_overlap: int = MIN_OVERLAP) -> list[PairStat]:
    """All lower-triangle pairs (a < b alphabetically) with a defined correlation."""
    names = usable_signals(signals, min_overlap)
    stats = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if (s := pair_stat(signals, a, b, min_overlap)) is not None:
                stats.append(s)
    return stats


def top_pairs(
    signals: Signals,
    n: int = 10,
    min_overlap: int = MIN_OVERLAP,
    exclude_pairs: list[tuple[str, str]] | None = None,
) -> list[PairStat]:
    """The *n* pairs with the largest absolute r, skipping excluded pairs (order-insensitive)."""
    excluded = {frozenset(p) for p in (exclude_pairs or [])}
    stats = [
        s for s in correlation_matrix(signals, min_overlap) if frozenset((s.a, s.b)) not in excluded
    ]
    if not stats:
        raise ValueError("No valid signal pairs remain after exclusions.")
    return sorted(stats, key=lambda s: abs(s.r), reverse=True)[:n]


def highlighted_pairs(
    signals: Signals, min_overlap: int = MIN_OVERLAP
) -> list[tuple[str, PairStat]]:
    """The mental-health pairs that can be computed, as (title, stat)."""
    out = []
    for a, b, title in MENTAL_HEALTH_PAIRS:
        if (s := pair_stat(signals, a, b, min_overlap)) is not None:
            out.append((title, s))
    return out
