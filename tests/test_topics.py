"""Tests for egon.analytics.topics."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from egon.analytics.loader import JournalEntry
from egon.analytics.topics import _TopicModel, fit_topics, topic_summary, topic_timeline


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
            patch("egon.analytics.topics._use_subprocess_venv", return_value=False),
            patch("egon.analytics.topics._fit_locally", return_value=([0] * 10, mock_model)),
        ):
            topic_ids, docs, model = fit_topics(entries)
        assert len(topic_ids) == 10
        assert len(docs) == 10


# ---------------------------------------------------------------------------
# topic_summary / topic_timeline
# ---------------------------------------------------------------------------


def _model() -> _TopicModel:
    return _TopicModel(
        topic_info=[{"Topic": 0, "Count": 6}, {"Topic": 1, "Count": 4}],
        topics={"0": [["walk", 0.9], ["park", 0.8]], "1": [["work", 0.7], ["deadline", 0.6]]},
    )


class TestTopicSummary:
    def test_labels_and_counts_largest_first(self):
        assert topic_summary(_model()) == [("walk · park", 6), ("work · deadline", 4)]

    def test_no_topics_raises(self):
        with pytest.raises(ValueError, match="no coherent topics"):
            topic_summary(_TopicModel(topic_info=[], topics={}))


class TestTopicTimeline:
    def test_counts_per_month_and_other(self):
        entries = [_entry(date(2026, 3, i), "x") for i in (1, 2)] + [
            _entry(date(2026, 4, i), "x") for i in (1, 2, 3)
        ]
        rows = topic_timeline(entries, [0, 1, 0, -1, 1], _model())
        assert ("2026-03", "walk · park", 1) in rows
        assert ("2026-04", "other", 1) in rows
        assert sum(c for _, _, c in rows) == 5

    def test_single_month_raises(self):
        entries = [_entry(date(2026, 3, i), "x") for i in (1, 2)]
        with pytest.raises(ValueError, match="2 months"):
            topic_timeline(entries, [0, 1], _model())
