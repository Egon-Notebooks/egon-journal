"""Tests for egon.analytics.wordcloud_plot."""

from datetime import date
from pathlib import Path

import pytest

from egon.analytics.loader import JournalEntry
from egon.analytics.wordcloud_plot import plot_wordcloud


def _entry(d: date, body: str) -> JournalEntry:
    return JournalEntry(date=d, body=body, path=Path(f"{d}.md"))


class TestPlotWordcloud:
    ENTRIES = [
        _entry(date(2026, 4, 1), "Went for a long walk in the forest. Very peaceful."),
        _entry(date(2026, 4, 2), "Talked to a friend about anxiety and sleep."),
        _entry(date(2026, 4, 3), "Feeling better. Sleep was good. Walk helped."),
    ]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "wordcloud.pdf"
        plot_wordcloud(self.ENTRIES, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "dir" / "wordcloud.pdf"
        plot_wordcloud(self.ENTRIES, out)
        assert out.exists()

    def test_raises_on_empty_entries(self, tmp_path):
        with pytest.raises(ValueError, match="No journal entries"):
            plot_wordcloud([], tmp_path / "out.pdf")

    def test_strips_html_comments(self, tmp_path):
        entries = [_entry(date(2026, 4, 1), "<!-- Write here. --> Real words only.")]
        out = tmp_path / "wc.pdf"
        plot_wordcloud(entries, out)
        assert out.exists()
