"""Tests for egon.limbic.sentiment, emotion and cognitive_bias score types."""

from datetime import date
from pathlib import Path

import pytest

from egon.analytics.loader import JournalEntry
from egon.limbic.cognitive_bias import BIASES, DISTORTION_TYPES, CognitiveBiasScores
from egon.limbic.emotion import EMOTIONS, EmotionScores
from egon.limbic.sentiment import sentiment_by_day, sentiment_score


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


# ---------------------------------------------------------------------------
# EmotionScores
# ---------------------------------------------------------------------------


class TestEmotionScores:
    def test_field_names_match_emotions_list(self):
        assert list(EmotionScores._fields) == EMOTIONS

    def test_as_list(self):
        scores = EmotionScores(0.1, 0.0, 0.05, 0.6, 0.1, 0.1, 0.05)
        lst = scores.as_list()
        assert lst == list(scores)
        assert len(lst) == 7

    def test_indexing_by_position(self):
        scores = EmotionScores(
            anger=0.2, disgust=0.0, fear=0.0, joy=0.5, neutral=0.1, sadness=0.15, surprise=0.05
        )
        assert scores.joy == pytest.approx(0.5)
        assert scores.anger == pytest.approx(0.2)

    def test_neutral_sentinel(self):
        from egon.limbic.emotion import _NEUTRAL

        assert _NEUTRAL.neutral == pytest.approx(1.0)
        assert sum(_NEUTRAL) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# CognitiveBiasScores
# ---------------------------------------------------------------------------


class TestCognitiveBiasScores:
    def test_field_names_match_biases_list(self):
        expected = [b.lower().replace(" ", "_") for b in BIASES]
        assert list(CognitiveBiasScores._fields) == expected

    def test_distortion_types_excludes_no_distortion(self):
        assert "NO DISTORTION" not in DISTORTION_TYPES
        assert len(DISTORTION_TYPES) == len(BIASES) - 1
        assert DISTORTION_TYPES == BIASES[1:]

    def test_as_list(self):
        scores = CognitiveBiasScores(0.6, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05)
        lst = scores.as_list()
        assert lst == list(scores)
        assert len(lst) == 8

    def test_distortion_score(self):
        scores = CognitiveBiasScores(0.6, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05)
        assert scores.distortion_score == pytest.approx(0.4)

    def test_distortion_score_no_distortion_sentinel(self):
        from egon.limbic.cognitive_bias import _NO_DISTORTION

        assert _NO_DISTORTION.no_distortion == pytest.approx(1.0)
        assert _NO_DISTORTION.distortion_score == pytest.approx(0.0)
        assert sum(_NO_DISTORTION) == pytest.approx(1.0)

    def test_indexing_by_position(self):
        scores = CognitiveBiasScores(
            no_distortion=0.7,
            personalization=0.1,
            emotional_reasoning=0.05,
            overgeneralizing=0.05,
            labeling=0.025,
            should_statements=0.025,
            catastrophizing=0.025,
            reward_fallacy=0.025,
        )
        assert scores.no_distortion == pytest.approx(0.7)
        assert scores.personalization == pytest.approx(0.1)
