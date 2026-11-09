"""Tests for egon.limbic.stress. The model and its subprocess are mocked."""

import json
import subprocess
import sys
import types
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egon.analytics.loader import JournalEntry
from egon.limbic import stress
from egon.limbic.stress import StressScore

DAY = date(2026, 1, 1)


def _entry(body, day=DAY):
    return JournalEntry(day, body, Path("synthetic.md"))


@pytest.mark.parametrize(
    "output",
    [
        [{"label": "no stress", "score": 0.3}, {"label": "stress", "score": 0.7}],
        [{"label": "STRESS", "score": 0.7}, {"label": "NO STRESS", "score": 0.3}],
        [{"label": "not_calm", "score": 0.3}, {"label": "tense", "score": 0.7}],
        [
            {"label": "no", "score": 0.3},
            {"label": "not", "score": 0.3},
            {"label": "label_1", "score": 0.7},
        ],
    ],
    ids=["named", "upper-case", "other-names", "label-1-fallback"],
)
def test_extract_stress_prob_handles_label_conventions(output):
    score = stress._extract_stress_prob(output)
    assert score.stress == pytest.approx(0.7)
    assert score.no_stress + score.stress == pytest.approx(1.0)


def test_named_stress_label_is_used_directly():
    output = [{"label": "no stress", "score": 0.2}, {"label": "stress", "score": 0.8}]
    assert stress._extract_stress_prob(output) == pytest.approx(StressScore(0.2, 0.8))


def test_last_label_is_the_final_fallback():
    output = [{"label": "no_a", "score": 0.6}, {"label": "no_b", "score": 0.4}]
    assert stress._extract_stress_prob(output).stress == pytest.approx(0.4)


def test_as_list_keeps_field_order():
    assert StressScore(0.25, 0.75).as_list() == [0.25, 0.75]


def test_empty_text_is_no_stress_without_loading_a_model(monkeypatch):
    monkeypatch.setattr(stress, "_load_pipeline", MagicMock(side_effect=AssertionError))
    assert stress.score_text("   ") == StressScore(1.0, 0.0)


def test_score_text_uses_the_pipeline(monkeypatch):
    fake = MagicMock(return_value=[[{"label": "stress", "score": 0.9}]])
    monkeypatch.setattr(stress, "_pipeline", fake)
    assert stress.score_text("A long day.").stress == pytest.approx(0.9)
    fake.assert_called_once_with("A long day.")


def test_load_pipeline_explains_a_missing_extra(monkeypatch):
    monkeypatch.setattr(stress, "_pipeline", None)
    with pytest.raises(ImportError, match="uv sync --extra limbic"):
        stress._load_pipeline()


def test_load_pipeline_loads_once(monkeypatch):
    factory = MagicMock(return_value="classifier")
    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=factory))
    monkeypatch.setattr(stress, "_pipeline", None)
    stress._load_pipeline()
    stress._load_pipeline()
    assert stress._pipeline == "classifier"
    factory.assert_called_once()


@pytest.mark.parametrize(
    ("system", "machine", "has_venv", "expected"),
    [
        ("Darwin", "x86_64", True, True),
        ("Darwin", "arm64", True, False),
        ("Linux", "x86_64", True, False),
        ("Darwin", "x86_64", False, False),
    ],
)
def test_subprocess_only_on_intel_mac_with_the_venv(
    tmp_path, monkeypatch, system, machine, has_venv, expected
):
    import importlib

    # conftest replaces this function, so read the real one from a fresh copy.
    spec = importlib.util.spec_from_file_location("stress_copy", stress.__file__)
    real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real)
    real._LIMBIC_VENV = tmp_path if has_venv else tmp_path / "missing"
    with (
        patch.object(real.platform, "system", return_value=system),
        patch.object(real.platform, "machine", return_value=machine),
    ):
        assert real._use_subprocess_venv() is expected


def test_score_batch_via_subprocess_parses_results():
    done = MagicMock(stdout=json.dumps([[0.4, 0.6], [0.9, 0.1]]) + "\n")
    with patch("egon.limbic.stress.subprocess.run", return_value=done) as run:
        scores = stress._score_batch_via_subprocess(["a", "b"])
    assert scores == [StressScore(0.4, 0.6), StressScore(0.9, 0.1)]
    assert json.loads(run.call_args.kwargs["input"]) == ["a", "b"]


def test_score_batch_via_subprocess_reports_failure():
    error = subprocess.CalledProcessError(1, "python", stderr="out of memory")
    with patch("egon.limbic.stress.subprocess.run", side_effect=error):
        with pytest.raises(RuntimeError, match="out of memory"):
            stress._score_batch_via_subprocess(["a"])


def test_stress_by_day_averages_and_sorts(monkeypatch):
    values = {
        "calm": StressScore(0.9, 0.1),
        "tense": StressScore(0.5, 0.5),
        "busy": StressScore(0.2, 0.8),
    }
    monkeypatch.setattr(stress, "score_text", values.__getitem__)
    later = date(2026, 1, 2)
    result = stress.stress_by_day([_entry("busy", later), _entry("calm"), _entry("tense")])
    assert [day for day, _ in result] == [DAY, later]
    assert result[0][1].stress == pytest.approx(0.3)
    assert result[1][1].stress == pytest.approx(0.8)


def test_stress_by_day_in_subprocess_mode_skips_empty_entries(monkeypatch):
    monkeypatch.setattr(stress, "_use_subprocess_venv", lambda: True)
    batch = MagicMock(return_value=[StressScore(0.4, 0.6)])
    monkeypatch.setattr(stress, "_score_batch_via_subprocess", batch)
    later = date(2026, 1, 2)
    result = stress.stress_by_day([_entry("   "), _entry("Words.", later)])
    batch.assert_called_once_with(["Words."])
    assert result == [(DAY, StressScore(1.0, 0.0)), (later, StressScore(0.4, 0.6))]


def test_stress_by_day_in_subprocess_mode_with_only_empty_entries(monkeypatch):
    monkeypatch.setattr(stress, "_use_subprocess_venv", lambda: True)
    batch = MagicMock()
    monkeypatch.setattr(stress, "_score_batch_via_subprocess", batch)
    assert stress.stress_by_day([_entry("")]) == [(DAY, StressScore(1.0, 0.0))]
    batch.assert_not_called()
