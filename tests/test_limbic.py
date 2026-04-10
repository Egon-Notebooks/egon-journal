"""Tests for egon.limbic.sentiment and egon.limbic.sentiment_plot."""

from datetime import date
from pathlib import Path

import pytest

from egon.analytics.loader import JournalEntry
from egon.limbic.sentiment import sentiment_by_day, sentiment_score
from egon.limbic.sentiment_plot import plot_sentiment


def _entry(d: date, body: str) -> JournalEntry:
    return JournalEntry(date=d, body=body, path=Path(f"{d}.md"))


class TestSentimentScore:
    def test_clearly_positive(self):
        score = sentiment_score("I feel wonderful, happy and grateful today.")
        assert score > 0.05

    def test_clearly_negative(self):
        score = sentiment_score("I feel terrible, miserable and hopeless.")
        assert score < -0.05

    def test_empty_text_returns_zero(self):
        assert sentiment_score("") == 0.0
        assert sentiment_score("   ") == 0.0

    def test_returns_float_in_range(self):
        score = sentiment_score("Something happened today.")
        assert -1.0 <= score <= 1.0


class TestSentimentByDay:
    def test_returns_list_of_tuples(self):
        entries = [
            _entry(date(2026, 4, 1), "Great day, feeling good!"),
            _entry(date(2026, 4, 2), "Awful and exhausting."),
        ]
        result = sentiment_by_day(entries)
        assert len(result) == 2
        assert result[0][0] == date(2026, 4, 1)
        assert result[1][0] == date(2026, 4, 2)
        assert result[0][1] > result[1][1]  # positive > negative

    def test_returns_empty_for_no_entries(self):
        assert sentiment_by_day([]) == []


class TestPlotSentiment:
    def test_saves_pdf(self, tmp_path):
        entries = [
            _entry(date(2026, 4, 1), "Feeling happy and energised."),
            _entry(date(2026, 4, 2), "A tough day, feeling low."),
            _entry(date(2026, 4, 3), "Okay, nothing special."),
        ]
        out = tmp_path / "sentiment.pdf"
        plot_sentiment(entries, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        entries = [_entry(date(2026, 4, 1), "Good day.")]
        out = tmp_path / "nested" / "sentiment.pdf"
        plot_sentiment(entries, out)
        assert out.exists()

    def test_raises_on_empty_entries(self, tmp_path):
        with pytest.raises(ValueError, match="No journal entries"):
            plot_sentiment([], tmp_path / "out.pdf")
