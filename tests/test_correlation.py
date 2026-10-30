"""Tests for egon.analytics.correlation."""

from datetime import date, timedelta

import pytest

from egon.analytics.correlation import (
    MENTAL_HEALTH_PAIRS,
    align_pairwise,
    correlation_matrix,
    highlighted_pairs,
    pair_stat,
    top_pairs,
    usable_signals,
)

START = date(2026, 1, 1)
N = 30


def _series(values: list[float]) -> list[tuple[date, float]]:
    return [(START + timedelta(days=i), v) for i, v in enumerate(values)]


def _ramp(n: int = N) -> list[tuple[date, float]]:
    return _series([float(i) for i in range(n)])


def _down(n: int = N) -> list[tuple[date, float]]:
    return _series([float(n - i) for i in range(n)])


class TestAlignPairwise:
    def test_fully_overlapping(self):
        dates, xs, ys = align_pairwise(_ramp(5), _series([10.0, 20.0, 30.0, 40.0, 50.0]))
        assert len(dates) == 5
        assert xs == [0.0, 1.0, 2.0, 3.0, 4.0]
        assert ys == [10.0, 20.0, 30.0, 40.0, 50.0]

    def test_partial_overlap(self):
        a = [(date(2026, 1, 1), 1.0), (date(2026, 1, 2), 2.0), (date(2026, 1, 3), 3.0)]
        b = [(date(2026, 1, 2), 20.0), (date(2026, 1, 3), 30.0), (date(2026, 1, 4), 40.0)]
        dates, xs, ys = align_pairwise(a, b)
        assert dates == [date(2026, 1, 2), date(2026, 1, 3)]
        assert xs == [2.0, 3.0]
        assert ys == [20.0, 30.0]

    def test_no_overlap(self):
        assert align_pairwise([(date(2026, 1, 1), 1.0)], [(date(2026, 2, 1), 2.0)]) == ([], [], [])


class TestPairStat:
    def test_perfect_negative(self):
        s = pair_stat({"a": _ramp(), "b": _down()}, "a", "b")
        assert s is not None
        assert s.r == pytest.approx(-1.0, abs=0.01)
        assert s.n == N
        assert s.significant

    def test_insufficient_overlap_is_none(self):
        a = [(date(2026, 1, i), float(i)) for i in range(1, 11)]
        b = [(date(2026, 2, i), float(i)) for i in range(1, 11)]
        assert pair_stat({"a": a, "b": b}, "a", "b") is None

    def test_constant_series_is_none(self):
        assert pair_stat({"a": _ramp(), "b": _series([1.0] * N)}, "a", "b") is None

    def test_missing_signal_is_none(self):
        assert pair_stat({"a": _ramp()}, "a", "b") is None


class TestCorrelationMatrix:
    def test_lower_triangle_pairs_sorted(self):
        stats = correlation_matrix({"c": _ramp(), "a": _down(), "b": _ramp()})
        assert [(s.a, s.b) for s in stats] == [("a", "b"), ("a", "c"), ("b", "c")]

    def test_short_signals_excluded(self):
        signals = {"long": _ramp(30), "short": _ramp(3)}
        assert usable_signals(signals) == ["long"]
        assert correlation_matrix(signals) == []


class TestTopPairs:
    def test_sorted_by_absolute_r_and_limited(self):
        noisy = _series([float(i % 5) for i in range(N)])
        stats = top_pairs({"a": _ramp(), "b": _down(), "c": noisy}, n=2)
        assert len(stats) == 2
        assert (stats[0].a, stats[0].b) == ("a", "b")

    def test_exclusions_are_order_insensitive(self):
        signals = {"a": _ramp(), "b": _down(), "c": _series([float(i % 5) for i in range(N)])}
        stats = top_pairs(signals, exclude_pairs=[("b", "a")])
        assert ("a", "b") not in [(s.a, s.b) for s in stats]

    def test_all_excluded_raises(self):
        with pytest.raises(ValueError):
            top_pairs({"a": _ramp(), "b": _down()}, exclude_pairs=[("a", "b")])


class TestHighlightedPairs:
    def test_available_pair_returned_with_title(self):
        a, b, title = MENTAL_HEALTH_PAIRS[0]
        out = highlighted_pairs({a: _ramp(), b: _down()})
        assert [t for t, _ in out] == [title]

    def test_none_available(self):
        assert highlighted_pairs({"x": _ramp()}) == []
