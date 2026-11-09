"""Tests for the AI journal summary and the report to share. Model calls are mocked."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

from egon.analytics.loader import JournalEntry
from egon.config import ReportConfig, load_report_config, share_config
from egon.full_report import build_full_report
from egon.journal_summary import (
    _COMBINE_SYSTEM,
    JournalSummary,
    _merge_summaries,
    _stretches,
    generate_journal_summary,
)
from egon.report.data import ReportData, journal_summary_text
from egon.risk import RISK_NOTE

REPLY = "You wrote about the move to Leeds."


def _entry(day, body="A quiet day."):
    return JournalEntry(date(2026, 1, day), body, Path("synthetic.md"))


def _data(summary=None, model="test-model"):
    return ReportData(
        label="2026-01",
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        journal_summary=summary,
        journal_model=model,
    )


def test_short_period_is_one_model_call():
    with patch("egon.journal_summary.chat", return_value=REPLY) as chat:
        result = generate_journal_summary([_entry(1), _entry(2)], "test-model")
    assert chat.call_count == 1
    assert result == JournalSummary("You wrote about the move to Leeds.")


def test_long_period_is_summarized_in_stretches():
    entries = [_entry(day, "word " * 600) for day in range(1, 5)]
    assert len(_stretches(entries)) == 2
    with patch("egon.journal_summary.chat", return_value=REPLY) as chat:
        generate_journal_summary(entries, "test-model")
    assert chat.call_count == 3
    assert chat.call_args.args[1] == _COMBINE_SYSTEM


def test_risk_in_latest_entry_never_reaches_the_model():
    with patch("egon.journal_summary.chat") as chat:
        result = generate_journal_summary([_entry(1), _entry(2, "I want to die.")], "test-model")
    chat.assert_not_called()
    assert result == JournalSummary(risk_note=RISK_NOTE)


def test_older_risk_is_left_out_of_what_the_model_reads():
    entries = [_entry(1, "Everyone would be better off without me."), _entry(2)]
    with patch("egon.journal_summary.chat", return_value=REPLY) as chat:
        generate_journal_summary(entries, "test-model")
    assert "better off" not in chat.call_args.args[2]


def test_cached_summary_is_reused_until_entries_change(tmp_path):
    with (
        patch("egon.local_llm.ensure_model"),
        patch("egon.journal_summary.chat", return_value=REPLY) as chat,
    ):
        for entries in ([_entry(1)], [_entry(1)], [_entry(1, "Edited.")]):
            journal_summary_text(ReportConfig(), entries, tmp_path)
    assert chat.call_count == 2


def test_summary_can_be_turned_off(tmp_path):
    config = ReportConfig(analyses={"llm_journal_summary": False})
    assert journal_summary_text(config, [_entry(1)], tmp_path) == (None, None)


def test_summary_is_skipped_without_ollama(tmp_path):
    with patch("egon.local_llm.ensure_model", side_effect=RuntimeError("no ollama")):
        assert journal_summary_text(ReportConfig(), [_entry(1)], tmp_path) == (None, None)


def test_report_shows_the_summary_labeled_as_ai_and_no_events_list():
    report = build_full_report(_data(JournalSummary("You moved.")), config=ReportConfig())
    notes = dict(report.sections[0].notes)
    assert list(notes) == ["Journal summary (AI-generated)"]
    assert "You moved." in notes["Journal summary (AI-generated)"]
    assert "test-model" in notes["Journal summary (AI-generated)"]


def test_risk_note_replaces_the_summary_in_a_personal_report():
    report = build_full_report(_data(JournalSummary(risk_note=RISK_NOTE)), config=ReportConfig())
    assert dict(report.sections[0].notes) == {"A note": RISK_NOTE}


def test_risk_note_stays_out_of_a_report_to_share():
    report = build_full_report(
        _data(JournalSummary(risk_note=RISK_NOTE)), config=share_config(), share=True
    )
    assert report.sections[0].notes == []


def test_share_report_is_labeled_and_says_it_is_for_sharing():
    report = build_full_report(_data(), config=share_config(), share=True)
    assert report.kind == "Report to share"
    assert "someone involved in your care" in report.sections[0].intro


def test_share_config_leaves_out_personality_and_word_lists():
    config = share_config()
    for key in ("bigfive", "mbti", "wordcloud", "topics", "correlation_matrix"):
        assert not config.enabled(key)
    for key in ("llm_journal_summary", "sentiment", "stress", "sleep"):
        assert config.enabled(key)


def test_egon_toml_can_adjust_the_share_report(tmp_path):
    path = tmp_path / "egon.toml"
    path.write_text(
        "[report.analyses]\nmbti = true\n\n[report.share]\nstress = false\nhrv = true\n"
    )
    config = load_report_config(path, share=True)
    assert not config.enabled("stress")
    assert config.enabled("hrv")
    assert not config.enabled("mbti")


def test_overlong_merge_is_shortened_once():
    with patch("egon.journal_summary.chat", side_effect=["word " * 300, "Short."]) as chat:
        assert _merge_summaries(["a", "b"], "test-model") == "Short."
    assert chat.call_count == 2


def test_demo_summary_from_a_cloud_model_says_so():
    report = build_full_report(
        _data(JournalSummary("You moved."), "claude-opus-5-5"), config=ReportConfig()
    )
    note = dict(report.sections[0].notes)["Journal summary (AI-generated)"]
    assert "cloud model claude-opus-5-5" in note
    assert "no data left this device" not in note
