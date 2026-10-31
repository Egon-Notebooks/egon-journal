"""Tests for egon.analytics.pronoun_ratio."""

from datetime import date
from pathlib import Path

import pytest

from egon.analytics.loader import JournalEntry
from egon.analytics.pronoun_ratio import pronoun_ratio_by_day


def _entry(d: date, body: str) -> JournalEntry:
    return JournalEntry(date=d, body=body, path=Path(f"{d}.md"))


class TestPronounRatioByDay:
    def test_basic_ratio(self):
        # "I went" → 1 pronoun out of 2 words → 0.5
        result = pronoun_ratio_by_day([_entry(date(2026, 4, 1), "I went")])
        assert len(result) == 1
        assert result[0][0] == date(2026, 4, 1)
        assert result[0][1] == pytest.approx(0.5)

    def test_no_pronouns(self):
        result = pronoun_ratio_by_day([_entry(date(2026, 4, 1), "the cat sat on the mat")])
        assert result[0][1] == pytest.approx(0.0)

    def test_all_pronouns(self):
        result = pronoun_ratio_by_day([_entry(date(2026, 4, 1), "I me my mine myself")])
        assert result[0][1] == pytest.approx(1.0)

    def test_empty_body_returns_zero(self):
        result = pronoun_ratio_by_day([_entry(date(2026, 4, 1), "")])
        assert result[0][1] == pytest.approx(0.0)

    def test_whitespace_only_returns_zero(self):
        result = pronoun_ratio_by_day([_entry(date(2026, 4, 1), "   \n\t  ")])
        assert result[0][1] == pytest.approx(0.0)

    def test_case_sensitive_capital_i(self):
        # Lowercase 'i' is not a pronoun match (regex uses \bI\b)
        result = pronoun_ratio_by_day([_entry(date(2026, 4, 1), "i went")])
        assert result[0][1] == pytest.approx(0.0)

    def test_sorted_by_date(self):
        entries = [
            _entry(date(2026, 4, 3), "I went"),
            _entry(date(2026, 4, 1), "I ran"),
            _entry(date(2026, 4, 2), "my day"),
        ]
        result = pronoun_ratio_by_day(entries)
        dates = [d for d, _ in result]
        assert dates == sorted(dates)

    def test_multiple_entries_same_semantics(self):
        entries = [
            _entry(date(2026, 4, 1), "I feel happy"),  # 1/3
            _entry(date(2026, 4, 2), "I love my dog"),  # 2/4
        ]
        result = pronoun_ratio_by_day(entries)
        assert len(result) == 2
        assert result[0][1] == pytest.approx(1 / 3)
        assert result[1][1] == pytest.approx(2 / 4)

    def test_partial_word_not_matched(self):
        # "mine" in "miner" should not match (word boundary)
        result = pronoun_ratio_by_day([_entry(date(2026, 4, 1), "the miner worked")])
        assert result[0][1] == pytest.approx(0.0)
