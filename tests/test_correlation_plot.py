"""Tests for egon.analytics.correlation_plot."""

from datetime import date, timedelta

import numpy as np
import pytest

from egon.analytics.correlation_plot import (
    MENTAL_HEALTH_PAIRS,
    _align_pairwise,
    _build_matrix,
    plot_correlation_matrix,
    plot_highlighted_correlations,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

START = date(2026, 1, 1)
N = 30  # 30 days of synthetic data


def _series(values: list[float]) -> list[tuple[date, float]]:
    return [(START + timedelta(days=i), v) for i, v in enumerate(values)]


def _ramp(n: int = N) -> list[tuple[date, float]]:
    return _series(list(range(n)))


def _constant(val: float = 1.0, n: int = N) -> list[tuple[date, float]]:
    return _series([val] * n)


@pytest.fixture
def two_signals():
    return {"sentiment": _ramp(), "word count": _series([float(N - i) for i in range(N)])}


@pytest.fixture
def health_pair_signals():
    """Signals that include both members of at least one MENTAL_HEALTH_PAIRS entry."""
    a_name, b_name, _ = MENTAL_HEALTH_PAIRS[0]  # ("sleep (h)", "sentiment", ...)
    return {
        a_name: _ramp(),
        b_name: _series([float(N - i) for i in range(N)]),
    }


# ---------------------------------------------------------------------------
# _align_pairwise
# ---------------------------------------------------------------------------


class TestAlignPairwise:
    def test_fully_overlapping(self):
        a = _ramp(5)
        b = _series([10.0, 20.0, 30.0, 40.0, 50.0])
        xs, ys = _align_pairwise(a, b)
        assert len(xs) == 5
        assert xs == [float(i) for i in range(5)]
        assert ys == [10.0, 20.0, 30.0, 40.0, 50.0]

    def test_partial_overlap(self):
        a = [(date(2026, 1, 1), 1.0), (date(2026, 1, 2), 2.0), (date(2026, 1, 3), 3.0)]
        b = [(date(2026, 1, 2), 20.0), (date(2026, 1, 3), 30.0), (date(2026, 1, 4), 40.0)]
        xs, ys = _align_pairwise(a, b)
        assert len(xs) == 2
        assert xs == [2.0, 3.0]
        assert ys == [20.0, 30.0]

    def test_no_overlap(self):
        a = [(date(2026, 1, 1), 1.0)]
        b = [(date(2026, 2, 1), 2.0)]
        xs, ys = _align_pairwise(a, b)
        assert xs == []
        assert ys == []


# ---------------------------------------------------------------------------
# _build_matrix
# ---------------------------------------------------------------------------


class TestBuildMatrix:
    def test_shape(self, two_signals):
        names, r_mat, p_mat = _build_matrix(two_signals, min_overlap=5)
        assert len(names) == 2
        assert r_mat.shape == (2, 2)
        assert p_mat.shape == (2, 2)

    def test_diagonal_is_one(self, two_signals):
        names, r_mat, _ = _build_matrix(two_signals, min_overlap=5)
        for i in range(len(names)):
            assert r_mat[i, i] == pytest.approx(1.0)

    def test_perfect_negative_correlation(self, two_signals):
        names, r_mat, _ = _build_matrix(two_signals, min_overlap=5)
        # sentiment is ramp up, word count is ramp down → r ≈ -1
        assert r_mat[0, 1] == pytest.approx(-1.0, abs=0.01)

    def test_insufficient_overlap_gives_nan(self):
        # Both signals have >= min_overlap points so they pass the length filter,
        # but their dates don't overlap → pairwise cell should be NaN.
        a = [(date(2026, 1, i), float(i)) for i in range(1, 11)]   # Jan 1–10
        b = [(date(2026, 2, i), float(i)) for i in range(1, 11)]   # Feb 1–10, no overlap
        signals = {"a": a, "b": b}
        _, r_mat, _ = _build_matrix(signals, min_overlap=5)
        assert np.isnan(r_mat[0, 1])

    def test_names_sorted_alphabetically(self, two_signals):
        names, _, _ = _build_matrix(two_signals, min_overlap=5)
        assert names == sorted(names)

    def test_signals_below_min_overlap_excluded(self):
        signals = {
            "long": _ramp(30),
            "short": _ramp(3),  # fewer than min_overlap=10
        }
        names, r_mat, _ = _build_matrix(signals, min_overlap=10)
        assert "short" not in names


# ---------------------------------------------------------------------------
# plot_correlation_matrix
# ---------------------------------------------------------------------------


class TestPlotCorrelationMatrix:
    def test_saves_pdf(self, two_signals, tmp_path):
        out = tmp_path / "matrix.pdf"
        plot_correlation_matrix(two_signals, out, min_overlap=5)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, two_signals, tmp_path):
        out = tmp_path / "nested" / "matrix.pdf"
        plot_correlation_matrix(two_signals, out, min_overlap=5)
        assert out.exists()

    def test_returns_figure_when_no_output_path(self, two_signals):
        fig = plot_correlation_matrix(two_signals, None, min_overlap=5)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_raises_with_fewer_than_two_signals(self, tmp_path):
        with pytest.raises(ValueError, match="at least 2"):
            plot_correlation_matrix({"only": _ramp()}, tmp_path / "out.pdf")

    def test_raises_when_no_sufficient_overlap(self, tmp_path):
        signals = {
            "a": [(date(2026, 1, i), float(i)) for i in range(1, 4)],
            "b": [(date(2026, 2, i), float(i)) for i in range(1, 4)],
        }
        with pytest.raises(ValueError):
            plot_correlation_matrix(signals, tmp_path / "out.pdf", min_overlap=5)


# ---------------------------------------------------------------------------
# plot_highlighted_correlations
# ---------------------------------------------------------------------------


class TestPlotHighlightedCorrelations:
    def test_saves_pdf(self, health_pair_signals, tmp_path):
        out = tmp_path / "highlighted.pdf"
        plot_highlighted_correlations(health_pair_signals, out, min_overlap=5)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_returns_figure_when_no_output_path(self, health_pair_signals):
        fig = plot_highlighted_correlations(health_pair_signals, None, min_overlap=5)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_raises_when_no_matching_pairs(self, two_signals, tmp_path):
        # two_signals has "sentiment" + "word count" — "word count" is not in any pair
        # but "sentiment" matches ("sleep (h)", "sentiment") — only if "sleep (h)" present
        # Use signals with no matching pair names at all.
        signals = {"foo": _ramp(), "bar": _series([float(N - i) for i in range(N)])}
        with pytest.raises(ValueError, match="None of the highlighted"):
            plot_highlighted_correlations(signals, tmp_path / "out.pdf")

    def test_mental_health_pairs_defined(self):
        assert len(MENTAL_HEALTH_PAIRS) >= 1
        for entry in MENTAL_HEALTH_PAIRS:
            assert len(entry) == 3  # (signal_a, signal_b, title)
