"""Tests for egon.analytics.loader and egon.analytics.word_count."""

from datetime import date
from pathlib import Path

import pytest

from egon.analytics.loader import JournalEntry, load_journal_entries
from egon.analytics.word_count import (
    count_words,
    filter_entries,
    parse_period_value,
    period_bounds,
    period_label,
    plot_word_count,
    word_counts_by_day,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_journal(path: Path, entry_date: date, body: str) -> None:
    date_str = entry_date.strftime("%Y-%m-%d")
    path.write_text(
        f"---\ntitle: 'Journal \u2014 {date_str}'\ndate: {date_str}\ntype: journal\n"
        f"tags: []\nmood: ''\nenergy: ''\negon_version: '1'\n---\n\n{body}",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# loader
# ---------------------------------------------------------------------------


class TestLoadJournalEntries:
    def test_loads_entries_sorted_by_date(self, tmp_path):
        _write_journal(tmp_path / "b.md", date(2026, 4, 2), "Second entry.")
        _write_journal(tmp_path / "a.md", date(2026, 4, 1), "First entry.")
        entries = load_journal_entries(tmp_path)
        assert [e.date for e in entries] == [date(2026, 4, 1), date(2026, 4, 2)]

    def test_skips_non_journal_nodes(self, tmp_path):
        # A program node should be ignored
        (tmp_path / "prog.md").write_text(
            "---\ntitle: 'Some Program'\ndate: 2026-04-01\ntype: program\n"
            "tags: []\nduration_days: 7\negon_version: '1'\n---\n\nBody.\n"
        )
        entries = load_journal_entries(tmp_path)
        assert entries == []

    def test_returns_empty_for_empty_dir(self, tmp_path):
        assert load_journal_entries(tmp_path) == []

    def test_body_excludes_frontmatter(self, tmp_path):
        _write_journal(tmp_path / "e.md", date(2026, 4, 3), "Hello world.")
        entries = load_journal_entries(tmp_path)
        assert len(entries) == 1
        assert "Hello world." in entries[0].body
        assert "egon_version" not in entries[0].body

    def test_falls_back_to_filename_date_hyphen(self, tmp_path):
        f = tmp_path / "Journal \u2014 2026-03-15.md"
        f.write_text("Just prose, no frontmatter.\n", encoding="utf-8")
        entries = load_journal_entries(tmp_path)
        assert len(entries) == 1
        assert entries[0].date == date(2026, 3, 15)

    def test_falls_back_to_filename_date_underscore(self, tmp_path):
        # Logseq filename format: YYYY_MM_DD.md, no frontmatter
        f = tmp_path / "2026_03_20.md"
        f.write_text("- Logseq entry with no frontmatter.\n", encoding="utf-8")
        entries = load_journal_entries(tmp_path)
        assert len(entries) == 1
        assert entries[0].date == date(2026, 3, 20)


# ---------------------------------------------------------------------------
# word_count
# ---------------------------------------------------------------------------


class TestCountWords:
    def test_simple_sentence(self):
        assert count_words("Hello world today") == 3

    def test_strips_html_comments(self):
        assert count_words("<!-- Write here. -->") == 0

    def test_empty_string(self):
        assert count_words("") == 0

    def test_mixed_content(self):
        text = "<!-- intro -->\nThis is real text with five words."
        assert count_words(text) == 7


class TestWordCountsByDay:
    def test_returns_list_of_tuples(self, tmp_path):
        _write_journal(tmp_path / "a.md", date(2026, 4, 1), "one two three")
        _write_journal(tmp_path / "b.md", date(2026, 4, 2), "four five")
        entries = load_journal_entries(tmp_path)
        result = word_counts_by_day(entries)
        assert result == [(date(2026, 4, 1), 3), (date(2026, 4, 2), 2)]


class TestPlotWordCount:
    def test_saves_pdf(self, tmp_path):
        entries = [
            JournalEntry(date=date(2026, 4, 1), body="one two three", path=tmp_path / "a.md"),
            JournalEntry(date=date(2026, 4, 2), body="four five six seven", path=tmp_path / "b.md"),
        ]
        out = tmp_path / "output.pdf"
        plot_word_count(entries, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        entries = [
            JournalEntry(date=date(2026, 4, 1), body="hello world", path=tmp_path / "a.md"),
        ]
        out = tmp_path / "nested" / "dir" / "plot.pdf"
        plot_word_count(entries, out)
        assert out.exists()

    def test_raises_on_empty_entries(self, tmp_path):
        with pytest.raises(ValueError, match="No journal entries"):
            plot_word_count([], tmp_path / "out.pdf")


# ---------------------------------------------------------------------------
# period helpers
# ---------------------------------------------------------------------------


class TestPeriodBounds:
    REF = date(2026, 4, 4)  # Saturday, ISO week 14, Q2

    def test_week(self):
        start, end = period_bounds("week", self.REF)
        assert start == date(2026, 3, 30)  # Monday
        assert end == date(2026, 4, 5)  # Sunday

    def test_month(self):
        start, end = period_bounds("month", self.REF)
        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 30)

    def test_month_december(self):
        start, end = period_bounds("month", date(2026, 12, 15))
        assert start == date(2026, 12, 1)
        assert end == date(2026, 12, 31)

    def test_quarter_q2(self):
        start, end = period_bounds("quarter", self.REF)
        assert start == date(2026, 4, 1)
        assert end == date(2026, 6, 30)

    def test_quarter_q4(self):
        start, end = period_bounds("quarter", date(2026, 11, 1))
        assert start == date(2026, 10, 1)
        assert end == date(2026, 12, 31)

    def test_year(self):
        start, end = period_bounds("year", self.REF)
        assert start == date(2026, 1, 1)
        assert end == date(2026, 12, 31)

    def test_all_time(self):
        start, end = period_bounds("all-time", self.REF)
        assert start == date.min
        assert end == date.max

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            period_bounds("decade", self.REF)


class TestPeriodLabel:
    REF = date(2026, 4, 4)

    def test_week(self):
        assert period_label("week", self.REF) == "2026-W14"

    def test_month(self):
        assert period_label("month", self.REF) == "2026-04"

    def test_quarter(self):
        assert period_label("quarter", self.REF) == "2026-Q2"

    def test_year(self):
        assert period_label("year", self.REF) == "2026"

    def test_all_time(self):
        assert period_label("all-time", self.REF) == "all-time"


class TestParsePeriodValue:
    def test_year(self):
        start, end, label = parse_period_value("2025")
        assert start == date(2025, 1, 1)
        assert end == date(2025, 12, 31)
        assert label == "2025"

    def test_month(self):
        start, end, label = parse_period_value("2026-02")
        assert start == date(2026, 2, 1)
        assert end == date(2026, 2, 28)
        assert label == "2026-02"

    def test_month_december(self):
        start, end, _ = parse_period_value("2026-12")
        assert start == date(2026, 12, 1)
        assert end == date(2026, 12, 31)

    def test_week(self):
        start, end, label = parse_period_value("2026-W14")
        assert start == date(2026, 3, 30)  # Monday of W14 2026
        assert end == date(2026, 4, 5)
        assert label == "2026-W14"

    def test_quarter(self):
        start, end, label = parse_period_value("2026-Q2")
        assert start == date(2026, 4, 1)
        assert end == date(2026, 6, 30)
        assert label == "2026-Q2"

    def test_quarter_q4(self):
        start, end, _ = parse_period_value("2026-Q4")
        assert start == date(2026, 10, 1)
        assert end == date(2026, 12, 31)

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_period_value("not-a-period")


class TestFilterEntries:
    def _entry(self, d: date) -> JournalEntry:
        return JournalEntry(date=d, body="text", path=Path(f"{d}.md"))

    def test_includes_entries_within_range(self):
        entries = [self._entry(date(2026, 4, d)) for d in range(1, 8)]
        result = filter_entries(entries, date(2026, 4, 3), date(2026, 4, 5))
        assert [e.date for e in result] == [date(2026, 4, 3), date(2026, 4, 4), date(2026, 4, 5)]

    def test_inclusive_bounds(self):
        entries = [self._entry(date(2026, 4, 1)), self._entry(date(2026, 4, 30))]
        result = filter_entries(entries, date(2026, 4, 1), date(2026, 4, 30))
        assert len(result) == 2

    def test_returns_empty_when_no_match(self):
        entries = [self._entry(date(2026, 3, 1))]
        result = filter_entries(entries, date(2026, 4, 1), date(2026, 4, 30))
        assert result == []
