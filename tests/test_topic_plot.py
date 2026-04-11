"""Tests for egon.analytics.topic_plot."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from egon.analytics.loader import JournalEntry
from egon.analytics.topic_plot import _TopicModel, fit_topics, plot_topic_summary, plot_topic_timeline


def _entry(d: date, body: str) -> JournalEntry:
    return JournalEntry(date=d, body=body, path=Path(f"{d}.md"))


# ---------------------------------------------------------------------------
# _TopicModel
# ---------------------------------------------------------------------------


class TestTopicModel:
    def test_get_topic_info_returns_list(self):
        model = _TopicModel(
            topic_info=[{"Topic": 0, "Count": 10}, {"Topic": 1, "Count": 5}],
            topics={"0": [["walk", 0.9], ["run", 0.8]], "1": [["eat", 0.7]]},
        )
        info = model.get_topic_info()
        assert len(info) == 2
        assert info[0]["Topic"] == 0
        assert info[0]["Count"] == 10

    def test_get_topic_returns_word_score_tuples(self):
        model = _TopicModel(
            topic_info=[{"Topic": 0, "Count": 5}],
            topics={"0": [["hello", 0.9], ["world", 0.5]]},
        )
        words = model.get_topic(0)
        assert words == [("hello", 0.9), ("world", 0.5)]

    def test_get_topic_missing_id_returns_empty(self):
        model = _TopicModel(topic_info=[], topics={})
        assert model.get_topic(99) == []

    def test_topic_keys_converted_to_int(self):
        model = _TopicModel(
            topic_info=[{"Topic": 3, "Count": 2}],
            topics={"3": [["word", 0.8]]},
        )
        assert model.get_topic(3) == [("word", 0.8)]


# ---------------------------------------------------------------------------
# fit_topics — guard on too few entries
# ---------------------------------------------------------------------------


class TestFitTopics:
    def test_raises_with_too_few_entries(self, tmp_path):
        entries = [_entry(date(2026, 4, i), f"Entry {i}.") for i in range(1, 5)]
        with pytest.raises(ValueError, match="at least"):
            fit_topics(entries)

    def test_exactly_at_minimum_does_not_raise_guard(self):
        # The guard is 10; a list of 10 entries should pass the guard and
        # attempt to fit (we mock the actual fitting to avoid ML dep).
        entries = [_entry(date(2026, 4, i), f"Entry {i} with content.") for i in range(1, 11)]
        mock_model = _TopicModel(
            topic_info=[{"Topic": 0, "Count": 10}],
            topics={"0": [["entry", 0.9]]},
        )
        with (
            patch("egon.analytics.topic_plot._use_subprocess_venv", return_value=False),
            patch("egon.analytics.topic_plot._fit_locally", return_value=([0] * 10, mock_model)),
        ):
            topic_ids, docs, model = fit_topics(entries)
        assert len(topic_ids) == 10
        assert len(docs) == 10


# ---------------------------------------------------------------------------
# plot_topic_summary
# ---------------------------------------------------------------------------


class TestPlotTopicSummary:
    def _make_entries(self, n: int = 11) -> list[JournalEntry]:
        return [_entry(date(2026, 4, i), f"Entry {i} about walks and nature.") for i in range(1, n + 1)]

    def _mock_fit(self, n: int = 11):
        mock_model = _TopicModel(
            topic_info=[{"Topic": 0, "Count": n}],
            topics={"0": [["walk", 0.9], ["nature", 0.8], ["feel", 0.7]]},
        )
        return [0] * n, [f"doc{i}" for i in range(n)], mock_model

    def test_raises_on_empty_entries(self, tmp_path):
        with pytest.raises(ValueError, match="No journal entries"):
            plot_topic_summary([], tmp_path / "out.pdf")

    def test_saves_pdf(self, tmp_path):
        entries = self._make_entries()
        out = tmp_path / "summary.pdf"
        with (
            patch("egon.analytics.topic_plot._use_subprocess_venv", return_value=False),
            patch("egon.analytics.topic_plot._fit_locally", return_value=self._mock_fit()[1:]),
            patch("egon.analytics.topic_plot.fit_topics", return_value=self._mock_fit()),
        ):
            plot_topic_summary(entries, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_returns_figure_when_no_output_path(self):
        import matplotlib.pyplot as plt

        entries = self._make_entries()
        with patch("egon.analytics.topic_plot.fit_topics", return_value=self._mock_fit()):
            fig = plot_topic_summary(entries, None)
        assert fig is not None
        plt.close(fig)


# ---------------------------------------------------------------------------
# plot_topic_timeline
# ---------------------------------------------------------------------------


class TestPlotTopicTimeline:
    def _make_monthly_entries(self) -> list[JournalEntry]:
        """12 entries spanning 2 months — enough for a timeline."""
        entries = []
        for i in range(1, 7):
            entries.append(_entry(date(2026, 3, i), f"March entry {i} about running."))
        for i in range(1, 7):
            entries.append(_entry(date(2026, 4, i), f"April entry {i} about cycling."))
        return entries

    def _mock_fit(self, n: int = 12):
        mock_model = _TopicModel(
            topic_info=[{"Topic": 0, "Count": n // 2}, {"Topic": 1, "Count": n // 2}],
            topics={
                "0": [["run", 0.9], ["march", 0.8]],
                "1": [["cycle", 0.9], ["april", 0.8]],
            },
        )
        topic_ids = [0] * (n // 2) + [1] * (n // 2)
        return topic_ids, [f"doc{i}" for i in range(n)], mock_model

    def test_raises_on_empty_entries(self, tmp_path):
        with pytest.raises(ValueError, match="No journal entries"):
            plot_topic_timeline([], tmp_path / "out.pdf")

    def test_saves_pdf(self, tmp_path):
        entries = self._make_monthly_entries()
        out = tmp_path / "timeline.pdf"
        with patch("egon.analytics.topic_plot.fit_topics", return_value=self._mock_fit()):
            plot_topic_timeline(entries, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_returns_figure_when_no_output_path(self):
        import matplotlib.pyplot as plt

        entries = self._make_monthly_entries()
        with patch("egon.analytics.topic_plot.fit_topics", return_value=self._mock_fit()):
            fig = plot_topic_timeline(entries, None)
        assert fig is not None
        plt.close(fig)
