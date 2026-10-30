"""Tests for egon.limbic.mbti."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egon.analytics.loader import JournalEntry
from egon.limbic.mbti import MBTIScores, _type_to_scores, mbti_by_day, score_text

# ---------------------------------------------------------------------------
# _type_to_scores
# ---------------------------------------------------------------------------


class TestTypeToScores:
    def test_intj(self):
        s = _type_to_scores("INTJ")
        assert s == MBTIScores(ei=0, ns=1, tf=1, jp=1)

    def test_enfp(self):
        s = _type_to_scores("ENFP")
        assert s == MBTIScores(ei=1, ns=1, tf=0, jp=0)

    def test_istp(self):
        s = _type_to_scores("ISTP")
        assert s == MBTIScores(ei=0, ns=0, tf=1, jp=0)

    def test_esfj(self):
        s = _type_to_scores("ESFJ")
        assert s == MBTIScores(ei=1, ns=0, tf=0, jp=1)

    def test_lowercase(self):
        assert _type_to_scores("infj") == _type_to_scores("INFJ")

    def test_as_list(self):
        assert MBTIScores(1, 0, 1, 0).as_list() == [1, 0, 1, 0]


# ---------------------------------------------------------------------------
# score_text
# ---------------------------------------------------------------------------


class TestScoreText:
    def test_empty_text_returns_zeros(self):
        assert score_text("") == MBTIScores(0, 0, 0, 0)

    def test_whitespace_returns_zeros(self):
        assert score_text("   ") == MBTIScores(0, 0, 0, 0)

    def test_uses_pipeline_result(self):
        try:
            from transformers import pipeline  # noqa: F401
        except ImportError:
            pytest.skip("bigfive extra not installed")

        mock_pipeline = MagicMock(return_value=[{"label": "INFJ", "score": 0.9}])
        with patch("egon.limbic.mbti._pipeline", mock_pipeline):
            result = score_text("some journal text")

        assert result == MBTIScores(ei=0, ns=1, tf=0, jp=1)


# ---------------------------------------------------------------------------
# mbti_by_day
# ---------------------------------------------------------------------------


class TestMbtiByDay:
    def _entries(self, dates_texts):
        return [JournalEntry(date=d, body=t, path=Path("t.md")) for d, t in dates_texts]

    def test_empty_text_returns_zeros(self):
        entries = self._entries([(date(2026, 4, 1), "")])
        result = mbti_by_day(entries)
        assert result == [(date(2026, 4, 1), MBTIScores(0, 0, 0, 0))]

    def test_multiple_entries_same_day_averaged(self):
        # Two empty entries → still zeros
        entries = self._entries(
            [
                (date(2026, 4, 1), ""),
                (date(2026, 4, 1), ""),
            ]
        )
        result = mbti_by_day(entries)
        assert len(result) == 1

    def test_sorted_by_date(self):
        entries = self._entries(
            [
                (date(2026, 4, 3), ""),
                (date(2026, 4, 1), ""),
            ]
        )
        dates = [d for d, _ in mbti_by_day(entries)]
        assert dates == sorted(dates)
