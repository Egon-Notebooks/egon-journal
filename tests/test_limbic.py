"""Tests for egon.limbic.sentiment, sentiment_plot, emotion_plot, and cognitive_bias_plot."""

from datetime import date
from pathlib import Path

import pytest

from egon.analytics.loader import JournalEntry
from egon.limbic.cognitive_bias import BIASES, DISTORTION_TYPES, CognitiveBiasScores
from egon.limbic.cognitive_bias_plot import plot_cognitive_bias
from egon.limbic.emotion import EMOTIONS, EmotionScores
from egon.limbic.emotion_plot import plot_emotion
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
# plot_emotion
# ---------------------------------------------------------------------------


class TestPlotEmotion:
    DATA = [
        (date(2026, 4, d), EmotionScores(0.05, 0.02, 0.03, 0.5, 0.2, 0.15, 0.05))
        for d in range(1, 8)
    ]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "emotion.pdf"
        plot_emotion(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "emotion.pdf"
        plot_emotion(self.DATA, out)
        assert out.exists()

    def test_returns_figure_when_no_output_path(self):
        import matplotlib.pyplot as plt

        fig = plot_emotion(self.DATA, None)
        assert fig is not None
        plt.close(fig)

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No emotion data"):
            plot_emotion([], tmp_path / "out.pdf")


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


# ---------------------------------------------------------------------------
# plot_cognitive_bias
# ---------------------------------------------------------------------------


class TestPlotCognitiveBias:
    DATA = [
        (
            date(2026, 4, d),
            CognitiveBiasScores(0.6, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05),
        )
        for d in range(1, 8)
    ]

    def test_saves_pdf(self, tmp_path):
        out = tmp_path / "cognitive_bias.pdf"
        plot_cognitive_bias(self.DATA, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_creates_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "cognitive_bias.pdf"
        plot_cognitive_bias(self.DATA, out)
        assert out.exists()

    def test_returns_figure_when_no_output_path(self):
        import matplotlib.pyplot as plt

        fig = plot_cognitive_bias(self.DATA, None)
        assert fig is not None
        plt.close(fig)

    def test_raises_on_empty_data(self, tmp_path):
        with pytest.raises(ValueError, match="No cognitive bias data"):
            plot_cognitive_bias([], tmp_path / "out.pdf")
