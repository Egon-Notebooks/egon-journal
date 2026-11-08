"""Tests for egon.analytics.export (all journal entries in one Markdown file)."""

from datetime import date
from pathlib import Path

from egon.analytics.export import entries_with_text, journal_markdown
from egon.analytics.loader import JournalEntry, load_journal_entries


def _entry(d: date, body: str, meta: dict | None = None) -> JournalEntry:
    return JournalEntry(date=d, body=body, path=Path(f"{d}.md"), meta=meta)


class TestJournalMarkdown:
    def test_one_dated_section_per_entry_oldest_first(self):
        md = journal_markdown(
            [_entry(date(2026, 4, 1), "First."), _entry(date(2026, 4, 3), "Second.")],
            "Journal entries — 2026-04",
        )
        assert md.startswith("# Journal entries — 2026-04\n")
        assert "2 journal entries from 2026-04-01 to 2026-04-03" in md
        assert md.index("## 2026-04-01 (Wednesday)") < md.index("## 2026-04-03 (Friday)")
        assert "First." in md and "Second." in md
        assert md.endswith("Second.\n")

    def test_keeps_mood_energy_and_tags(self):
        meta = {"mood": "3/5 - calm", "energy": "low", "tags": ["sleep", "work"]}
        md = journal_markdown([_entry(date(2026, 4, 1), "Text.", meta)], "T")
        assert "Mood: 3/5 - calm · Energy: low · Tags: sleep, work" in md

    def test_empty_metadata_is_left_out(self):
        meta = {"mood": "", "energy": "", "tags": []}
        md = journal_markdown([_entry(date(2026, 4, 1), "Text.", meta)], "T")
        assert "Mood" not in md and "Tags" not in md

    def test_untouched_template_is_skipped(self):
        entries = [
            _entry(date(2026, 4, 1), "\n<!-- Write here. No required structure. -->\n"),
            _entry(date(2026, 4, 2), "Real text."),
        ]
        assert entries_with_text(entries) == entries[1:]
        md = journal_markdown(entries, "T")
        assert "2026-04-01" not in md
        assert "1 journal entry from 2026-04-02 to 2026-04-02" in md

    def test_headings_inside_entries_are_demoted(self):
        body = "# Morning\n\nText.\n\n```\n# not a heading\n```\n#tag stays"
        md = journal_markdown([_entry(date(2026, 4, 1), body)], "T")
        assert "### Morning" in md
        assert "\n# not a heading" in md
        assert "\n#tag stays" in md

    def test_no_entries(self):
        assert "No journal entries" in journal_markdown([], "T")


def test_loader_keeps_frontmatter(tmp_path):
    (tmp_path / "Journal — 2026-04-01.md").write_text(
        "---\ndate: 2026-04-01\ntype: journal\nmood: good\n---\nText.", encoding="utf-8"
    )
    (tmp_path / "2026-04-02.md").write_text("No frontmatter.", encoding="utf-8")
    entries = load_journal_entries(tmp_path)
    assert entries[0].meta["mood"] == "good"
    assert entries[1].meta is None
