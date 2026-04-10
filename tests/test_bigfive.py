"""Tests for egon.limbic.bigfive and egon.limbic.bigfive_plot."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egon.analytics.loader import JournalEntry
from egon.limbic.bigfive import BigFiveScores, bigfive_by_day, score_text
from egon.limbic.bigfive_plot import plot_bigfive

# ---------------------------------------------------------------------------
# BigFiveScores
# ---------------------------------------------------------------------------


class TestBigFiveScores:
    def test_as_list(self):
        s = BigFiveScores(0.1, 0.2, 0.3, 0.4, 0.5)
        assert s.as_list() == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_indexable(self):
        s = BigFiveScores(0.1, 0.2, 0.3, 0.4, 0.5)
        assert s[2] == 0.3  # extraversion


# ---------------------------------------------------------------------------
# score_text
# ---------------------------------------------------------------------------


def _mock_model_output(values: list[float]):
    """Return a mock that mimics transformers model output."""
    import torch

    logits = torch.tensor([values])

    output = MagicMock()
    output.logits = logits
    return output


class TestScoreText:
    def test_empty_text_returns_neutral(self):
        result = score_text("")
        assert result == BigFiveScores(0.5, 0.5, 0.5, 0.5, 0.5)

    def test_whitespace_only_returns_neutral(self):
        assert score_text("   ") == BigFiveScores(0.5, 0.5, 0.5, 0.5, 0.5)

    def test_scores_clamped_to_unit_interval(self):
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: F401
        except ImportError:
            pytest.skip("bigfive extra not installed")

        raw_values = [-0.1, 0.5, 1.2, 0.3, 0.8]
        mock_out = _mock_model_output(raw_values)

        with (
            patch("egon.limbic.bigfive._tokenizer", MagicMock(return_value={})),
            patch("egon.limbic.bigfive._model", MagicMock(return_value=mock_out)),
        ):
            result = score_text("some journal text")

        assert result.openness == 0.0  # clamped from -0.1
        assert result.conscientiousness == 0.5
        assert result.extraversion == 1.0  # clamped from 1.2


# ---------------------------------------------------------------------------
# bigfive_by_day
# ---------------------------------------------------------------------------


class TestBigFiveByDay:
    def _make_entries(self, dates_texts):
        return [JournalEntry(date=d, body=t, path=Path("test.md")) for d, t in dates_texts]

    def test_empty_text_entries_return_neutral(self):
        entries = self._make_entries([(date(2026, 4, 1), ""), (date(2026, 4, 2), "")])
        result = bigfive_by_day(entries)
        assert len(result) == 2
        for _, scores in result:
            assert scores == BigFiveScores(0.5, 0.5, 0.5, 0.5, 0.5)

    def test_multiple_entries_same_day_are_averaged(self):
        entries = self._make_entries(
            [
                (date(2026, 4, 1), ""),  # → all 0.5
                (date(2026, 4, 1), ""),  # → all 0.5
            ]
        )
        result = bigfive_by_day(entries)
        assert len(result) == 1
        assert result[0][1] == BigFiveScores(0.5, 0.5, 0.5, 0.5, 0.5)

    def test_sorted_by_date(self):
        entries = self._make_entries(
            [
                (date(2026, 4, 3), ""),
                (date(2026, 4, 1), ""),
                (date(2026, 4, 2), ""),
            ]
        )
        result = bigfive_by_day(entries)
        dates = [d for d, _ in result]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# plot_bigfive
# ---------------------------------------------------------------------------


class TestPlotBigFive:
    DATA = [(date(2026, 4, d), BigFiveScores(0.6, 0.5, 0.4, 0.7, 0.3)) for d in range(1, 8)]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "bigfive.pdf"
        plot_bigfive(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "bigfive.pdf"
        plot_bigfive(self.DATA, out)
        assert out.exists()

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No Big Five data"):
            plot_bigfive([], tmp_path / "out.pdf")
