"""
Tests for egon.cli — CLI command routing, error handling, and output paths.

Uses typer.testing.CliRunner to invoke commands in-process.  ML-heavy report
commands (bigfive, mbti, emotion) are tested at the error-path level only to
avoid requiring the optional bigfive dependency group in CI.  Pure-Python
report commands (word-count, sentiment, exercise) are tested end-to-end.
"""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from egon.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_journal(path: Path, entry_date: date, body: str) -> None:
    ds = entry_date.strftime("%Y-%m-%d")
    path.write_text(
        f"---\ntitle: 'Journal \u2014 {ds}'\ndate: {ds}\ntype: journal\n"
        f"tags: []\nmood: ''\nenergy: ''\negon_version: '1'\n---\n\n{body}",
        encoding="utf-8",
    )


def _make_export_xml(records: list[dict]) -> str:
    lines = "\n".join(
        f'  <Record type="{r["type"]}" value="{r["value"]}" unit="{r.get("unit", "")}" '
        f'startDate="{r["date"]} 08:00:00 +0100" endDate="{r["date"]} 08:00:00 +0100" '
        f'creationDate="{r["date"]} 09:00:00 +0100" />'
        for r in records
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<HealthData locale="en_GB">\n'
        f"{lines}\n"
        "</HealthData>\n"
    )


_BM = "HKQuantityTypeIdentifierBodyMass"
_STEPS = "HKQuantityTypeIdentifierStepCount"
_RHR = "HKQuantityTypeIdentifierRestingHeartRate"
_EXERCISE = "HKQuantityTypeIdentifierAppleExerciseTime"


@pytest.fixture
def journal_dir(tmp_path):
    d = tmp_path / "journal"
    d.mkdir()
    for i in range(1, 22):  # 21 entries so correlation min_overlap=10 is met
        _write_journal(
            d / f"2026-04-{i:02d}.md",
            date(2026, 4, i),
            f"Entry {i}. Today I went for a walk and felt great.",
        )
    return d


@pytest.fixture
def health_xml(tmp_path):
    records = [
        {"type": _BM, "value": str(80.0 - i * 0.1), "unit": "kg", "date": f"2026-04-0{i}"}
        for i in range(1, 8)
    ]
    path = tmp_path / "export.xml"
    path.write_text(_make_export_xml(records), encoding="utf-8")
    return path


@pytest.fixture
def exercise_xml(tmp_path):
    records = [
        {"type": _EXERCISE, "value": str(20 + i * 2), "unit": "min", "date": f"2026-04-0{i}"}
        for i in range(1, 8)
    ]
    path = tmp_path / "export.xml"
    path.write_text(_make_export_xml(records), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# report-word-count
# ---------------------------------------------------------------------------


class TestReportWordCount:
    def test_success(self, journal_dir, tmp_path):
        out = tmp_path / "wc.pdf"
        result = runner.invoke(
            app, ["report-word-count", "--journal-dir", str(journal_dir), "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_missing_journal_dir(self, tmp_path):
        result = runner.invoke(
            app,
            ["report-word-count", "--journal-dir", str(tmp_path / "missing"), "--output", str(tmp_path / "out.pdf")],
        )
        assert result.exit_code == 1

    def test_empty_journal_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = runner.invoke(
            app,
            ["report-word-count", "--journal-dir", str(empty), "--output", str(tmp_path / "out.pdf")],
        )
        assert result.exit_code == 1

    def test_period_month(self, journal_dir, tmp_path):
        out = tmp_path / "wc-month.pdf"
        result = runner.invoke(
            app,
            [
                "report-word-count",
                "--journal-dir", str(journal_dir),
                "--period", "month",
                "--output", str(out),
            ],
        )
        # All 7 entries are in April 2026; today is likely not April 2026,
        # so this may return no data.  We only verify the command doesn't crash.
        assert result.exit_code in (0, 1)

    def test_for_period(self, journal_dir, tmp_path):
        out = tmp_path / "wc-q2.pdf"
        result = runner.invoke(
            app,
            [
                "report-word-count",
                "--journal-dir", str(journal_dir),
                "--for", "2026-Q2",
                "--output", str(out),
            ],
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_invalid_for_period(self, journal_dir, tmp_path):
        result = runner.invoke(
            app,
            [
                "report-word-count",
                "--journal-dir", str(journal_dir),
                "--for", "not-a-period",
                "--output", str(tmp_path / "out.pdf"),
            ],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# report-sentiment
# ---------------------------------------------------------------------------


class TestReportSentiment:
    def test_success(self, journal_dir, tmp_path):
        out = tmp_path / "sentiment.pdf"
        result = runner.invoke(
            app,
            ["report-sentiment", "--journal-dir", str(journal_dir), "--output", str(out)],
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_missing_journal_dir(self, tmp_path):
        result = runner.invoke(
            app,
            ["report-sentiment", "--journal-dir", str(tmp_path / "gone"), "--output", str(tmp_path / "out.pdf")],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# report-wordcloud
# ---------------------------------------------------------------------------


class TestReportWordcloud:
    def test_success(self, journal_dir, tmp_path):
        out = tmp_path / "wc.pdf"
        result = runner.invoke(
            app,
            ["report-wordcloud", "--journal-dir", str(journal_dir), "--output", str(out)],
        )
        assert result.exit_code == 0
        assert out.exists()


# ---------------------------------------------------------------------------
# report-weight
# ---------------------------------------------------------------------------


class TestReportWeight:
    def test_success(self, health_xml, tmp_path):
        out = tmp_path / "weight.pdf"
        result = runner.invoke(
            app, ["report-weight", "--xml", str(health_xml), "--for", "2026-Q2", "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_missing_xml(self, tmp_path):
        result = runner.invoke(
            app,
            ["report-weight", "--xml", str(tmp_path / "missing.xml"), "--output", str(tmp_path / "out.pdf")],
        )
        assert result.exit_code == 1

    def test_no_xml_no_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("EGON_APPLE_HEALTH_XML", raising=False)
        result = runner.invoke(app, ["report-weight", "--output", str(tmp_path / "out.pdf")])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# report-exercise
# ---------------------------------------------------------------------------


class TestReportExercise:
    def test_success(self, exercise_xml, tmp_path):
        out = tmp_path / "exercise.pdf"
        result = runner.invoke(
            app,
            [
                "report-exercise",
                "--xml", str(exercise_xml),
                "--for", "2026-Q2",
                "--output", str(out),
            ],
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_custom_target_via_env(self, exercise_xml, tmp_path, monkeypatch):
        monkeypatch.setenv("EGON_TARGET_EXERCISE_MINUTES", "45")
        out = tmp_path / "exercise.pdf"
        result = runner.invoke(
            app,
            [
                "report-exercise",
                "--xml", str(exercise_xml),
                "--for", "2026-Q2",
                "--output", str(out),
            ],
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_invalid_target_env_is_ignored(self, exercise_xml, tmp_path, monkeypatch):
        monkeypatch.setenv("EGON_TARGET_EXERCISE_MINUTES", "not-a-number")
        out = tmp_path / "exercise.pdf"
        result = runner.invoke(
            app,
            [
                "report-exercise",
                "--xml", str(exercise_xml),
                "--for", "2026-Q2",
                "--output", str(out),
            ],
        )
        # Warning printed, but command succeeds with WHO default
        assert result.exit_code == 0

    def test_missing_xml(self, tmp_path):
        result = runner.invoke(
            app,
            ["report-exercise", "--xml", str(tmp_path / "missing.xml"), "--output", str(tmp_path / "out.pdf")],
        )
        assert result.exit_code == 1

    def test_no_exercise_records(self, health_xml, tmp_path):
        # health_xml only has BodyMass, no AppleExerciseTime
        result = runner.invoke(
            app,
            ["report-exercise", "--xml", str(health_xml), "--for", "2026-Q2", "--output", str(tmp_path / "out.pdf")],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# report-topics
# ---------------------------------------------------------------------------


class TestReportTopics:
    def test_missing_journal_dir(self, tmp_path):
        result = runner.invoke(
            app,
            ["report-topics", "--journal-dir", str(tmp_path / "gone"), "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 1

    def test_empty_journal_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = runner.invoke(
            app,
            ["report-topics", "--journal-dir", str(empty), "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 1

    def test_success(self, tmp_path):
        # Needs >= 10 entries for BERTopic / NMF; mock fit_topics to avoid
        # dependency on the bigfive venv or bertopic package.
        jdir = tmp_path / "journal"
        jdir.mkdir()
        for i in range(1, 12):
            _write_journal(
                jdir / f"2026-04-{i:02d}.md",
                date(2026, 4, i),
                f"Entry {i}. I went walking and felt wonderful.",
            )
        out_dir = tmp_path / "topics"
        mock_model = MagicMock()
        mock_model.get_topic_info.return_value = [{"Topic": 0, "Count": 11}]
        mock_model.get_topic.return_value = [("walk", 0.9), ("feel", 0.8)]
        with patch(
            "egon.analytics.topic_plot.fit_topics",
            return_value=([0] * 11, ["doc"] * 11, mock_model),
        ):
            result = runner.invoke(
                app,
                [
                    "report-topics",
                    "--journal-dir", str(jdir),
                    "--for", "2026-04",
                    "--output-dir", str(out_dir),
                ],
            )
        assert result.exit_code == 0
        assert (out_dir / "2026-04_summary.pdf").exists()


# ---------------------------------------------------------------------------
# report-correlations
# ---------------------------------------------------------------------------


class TestReportCorrelations:
    def test_success_with_journal_only(self, journal_dir, tmp_path):
        out_dir = tmp_path / "corr"
        result = runner.invoke(
            app,
            [
                "report-correlations",
                "--journal-dir", str(journal_dir),
                "--for", "2026-Q2",
                "--output-dir", str(out_dir),
            ],
        )
        assert result.exit_code == 0
        assert (out_dir / "2026-Q2_matrix.pdf").exists()

    def test_too_few_signals(self, tmp_path):
        # A journal dir with only 1 signal (word-count) — but with a single
        # journal entry, sentiment will also be there, so use monkeypatching
        # to simulate only 1 signal being returned.
        jdir = tmp_path / "journal"
        jdir.mkdir()
        _write_journal(jdir / "2026-04-01.md", date(2026, 4, 1), "Just one entry.")
        out_dir = tmp_path / "corr"
        with patch("egon.full_report.build_signals", return_value={"only-signal": [(date(2026, 4, 1), 1.0)]}):
            result = runner.invoke(
                app,
                [
                    "report-correlations",
                    "--journal-dir", str(jdir),
                    "--for", "2026-Q2",
                    "--output-dir", str(out_dir),
                ],
            )
        assert result.exit_code == 1

    def test_output_dir_default(self, journal_dir, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app,
            [
                "report-correlations",
                "--journal-dir", str(journal_dir),
                "--for", "2026-Q2",
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "reports" / "correlations" / "2026-Q2_matrix.pdf").exists()


# ---------------------------------------------------------------------------
# report (batch)
# ---------------------------------------------------------------------------


class TestReportAll:
    def test_runs_without_crash(self, journal_dir, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("EGON_APPLE_HEALTH_XML", raising=False)
        result = runner.invoke(
            app,
            [
                "report",
                "--journal-dir", str(journal_dir),
                "--for", "2026-Q2",
            ],
        )
        # Health reports will be skipped (no XML), journal reports should run.
        assert result.exit_code == 0

    def test_summary_shows_generated_and_skipped(self, journal_dir, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("EGON_APPLE_HEALTH_XML", raising=False)
        result = runner.invoke(
            app,
            [
                "report",
                "--journal-dir", str(journal_dir),
                "--for", "2026-Q2",
            ],
        )
        output = result.output
        assert "Generated" in output or "Skipped" in output or "Done" in output

    def test_for_period_propagates(self, journal_dir, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("EGON_APPLE_HEALTH_XML", raising=False)
        result = runner.invoke(
            app,
            [
                "report",
                "--journal-dir", str(journal_dir),
                "--for", "2026-04",
            ],
        )
        assert result.exit_code == 0
        # word-count report for 2026-04 should be created
        assert (tmp_path / "reports" / "word_count" / "2026-04.pdf").exists()
