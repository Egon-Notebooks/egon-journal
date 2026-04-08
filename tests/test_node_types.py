"""Tests for egon.node_types.* generators."""
from datetime import date
from pathlib import Path

import pytest
import yaml

from egon.node_types.journal_entry import (
    generate_journal_entry,
    journal_entry_filename,
    make_journal_entry,
)
from egon.node_types.program import (
    generate_program,
    make_program_day,
    make_program_index,
)
from egon.node_types.prompt import generate_prompt, make_prompt_node, prompt_filename
from egon.node_types.summary import (
    generate_monthly_summary,
    generate_weekly_summary,
    make_monthly_summary,
    make_weekly_summary,
    monthly_summary_filename,
    weekly_summary_filename,
)
from egon.schema import validate

EM = "\u2014"  # em dash


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse(content: str) -> tuple[dict, str]:
    """Split rendered Markdown into (frontmatter_dict, body_str)."""
    assert content.startswith("---"), "Node must start with '---'"
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])
    return fm, parts[2]


# ---------------------------------------------------------------------------
# Journal entry
# ---------------------------------------------------------------------------

class TestJournalEntry:
    REF = date(2026, 4, 3)

    def test_filename_uses_em_dash(self):
        assert journal_entry_filename(self.REF) == f"Journal {EM} 2026-04-03.md"

    def test_frontmatter_fields(self):
        fm, _ = make_journal_entry(self.REF)
        assert fm["type"] == "journal"
        assert fm["title"] == f"Journal {EM} 2026-04-03"
        assert fm["egon_version"] == "1"
        assert fm["tags"] == []
        assert "mood" in fm
        assert "energy" in fm

    def test_frontmatter_valid(self):
        fm, _ = make_journal_entry(self.REF)
        # Convert date object to string for validation (as yaml.safe_load would)
        fm_copy = {**fm, "date": str(fm["date"])}
        assert validate(fm_copy) == []

    def test_generates_file(self, tmp_path):
        path = generate_journal_entry(self.REF, tmp_path)
        assert path.exists()
        assert path.name == f"Journal {EM} 2026-04-03.md"
        content = path.read_text()
        fm, body = _parse(content)
        assert fm["type"] == "journal"
        assert "Write here" in body

    def test_different_dates_produce_different_files(self, tmp_path):
        p1 = generate_journal_entry(date(2026, 1, 1), tmp_path)
        p2 = generate_journal_entry(date(2026, 1, 2), tmp_path)
        assert p1 != p2


# ---------------------------------------------------------------------------
# Prompt node
# ---------------------------------------------------------------------------

RUMINATION_SOURCE = {
    "name": "Rumination",
    "topic": "Rumination and how to interrupt it",
    "tags": ["rumination", "thinking-patterns"],
    "prompt_text": "Describe a thought that has been repeating.",
    "starter": "A thought that kept coming back...",
    "duration_minutes": 5,
}


class TestPromptNode:
    REF = date(2026, 4, 3)

    def test_filename(self):
        assert prompt_filename(RUMINATION_SOURCE) == f"Prompt {EM} Rumination.md"

    def test_frontmatter_type(self):
        fm, _ = make_prompt_node(RUMINATION_SOURCE, self.REF)
        assert fm["type"] == "prompt"

    def test_frontmatter_related_article(self):
        fm, _ = make_prompt_node(RUMINATION_SOURCE, self.REF)
        assert fm["related_article"] == "Rumination and how to interrupt it"

    def test_frontmatter_valid(self):
        fm, _ = make_prompt_node(RUMINATION_SOURCE, self.REF)
        fm_copy = {**fm, "date": str(fm["date"])}
        assert validate(fm_copy) == []

    def test_body_contains_wikilink(self):
        _, body = make_prompt_node(RUMINATION_SOURCE, self.REF)
        assert "[[Rumination and how to interrupt it]]" in body

    def test_body_contains_starter(self):
        _, body = make_prompt_node(RUMINATION_SOURCE, self.REF)
        assert "A thought that kept coming back" in body

    def test_body_contains_prompt_text(self):
        _, body = make_prompt_node(RUMINATION_SOURCE, self.REF)
        assert "Describe a thought that has been repeating" in body

    def test_generates_file(self, tmp_path):
        path = generate_prompt(RUMINATION_SOURCE, self.REF, tmp_path)
        assert path.exists()
        content = path.read_text()
        fm, _ = _parse(content)
        assert fm["type"] == "prompt"

    def test_generate_from_real_yaml(self, tmp_path):
        """Smoke test: generate from the actual YAML files in content/prompts/."""
        from egon.node_types.prompt import generate_prompts_from_dir
        content_dir = Path(__file__).parent.parent / "content" / "prompts"
        if not content_dir.exists():
            pytest.skip("content/prompts not found")
        paths = generate_prompts_from_dir(content_dir, self.REF, tmp_path)
        assert len(paths) >= 1
        for p in paths:
            assert p.exists()
            fm, _ = _parse(p.read_text())
            assert validate({**fm, "date": str(fm["date"])}) == []


# ---------------------------------------------------------------------------
# Program node
# ---------------------------------------------------------------------------

SLEEP_SOURCE = {
    "title": "14-Day Sleep Improvement",
    "duration_days": 3,  # shortened for tests
    "description": "A short track for testing.",
    "tags": ["sleep", "programs"],
    "related_articles": ["Sleep and mental health"],
    "days": [
        {
            "day": 1,
            "heading": "How sleep affects your mood",
            "related_article": "Sleep and mental health",
            "prompt_text": "How did you sleep last night?",
            "starter": "Last night I slept...",
        },
        {
            "day": 2,
            "heading": "What gets in the way",
            "related_article": "Sleep and mental health",
            "prompt_text": "What got in the way of sleep?",
            "starter": "The last time I struggled...",
        },
        {
            "day": 3,
            "heading": "Your pre-sleep routine",
            "related_article": "Building a daily routine",
            "prompt_text": "Describe what you usually do before bed.",
            "starter": "Before I go to sleep...",
        },
    ],
}


class TestProgramNode:
    REF = date(2026, 4, 3)

    def test_index_frontmatter_type(self):
        fm, _ = make_program_index(SLEEP_SOURCE, self.REF)
        assert fm["type"] == "program"

    def test_index_frontmatter_duration_days(self):
        fm, _ = make_program_index(SLEEP_SOURCE, self.REF)
        assert fm["duration_days"] == 3

    def test_index_frontmatter_valid(self):
        fm, _ = make_program_index(SLEEP_SOURCE, self.REF)
        fm_copy = {**fm, "date": str(fm["date"])}
        assert validate(fm_copy) == []

    def test_index_body_lists_all_days(self):
        _, body = make_program_index(SLEEP_SOURCE, self.REF)
        for n in range(1, 4):
            assert f"[[14-Day Sleep Improvement {EM} Day {n:02d}]]" in body

    def test_index_body_has_related_reading(self):
        _, body = make_program_index(SLEEP_SOURCE, self.REF)
        assert "[[Sleep and mental health]]" in body

    def test_day_frontmatter_type(self):
        fm, _ = make_program_day(SLEEP_SOURCE, SLEEP_SOURCE["days"][0], self.REF)
        assert fm["type"] == "program-day"

    def test_day_frontmatter_program_link(self):
        fm, _ = make_program_day(SLEEP_SOURCE, SLEEP_SOURCE["days"][0], self.REF)
        assert fm["program"] == "14-Day Sleep Improvement"

    def test_day_frontmatter_day_number(self):
        fm, _ = make_program_day(SLEEP_SOURCE, SLEEP_SOURCE["days"][1], self.REF)
        assert fm["day"] == 2

    def test_day_frontmatter_valid(self):
        fm, _ = make_program_day(SLEEP_SOURCE, SLEEP_SOURCE["days"][0], self.REF)
        fm_copy = {**fm, "date": str(fm["date"])}
        assert validate(fm_copy) == []

    def test_day_body_links_back_to_program(self):
        _, body = make_program_day(SLEEP_SOURCE, SLEEP_SOURCE["days"][0], self.REF)
        assert "[[14-Day Sleep Improvement]]" in body

    def test_day_body_has_article_link(self):
        _, body = make_program_day(SLEEP_SOURCE, SLEEP_SOURCE["days"][0], self.REF)
        assert "[[Sleep and mental health]]" in body

    def test_generate_program_produces_all_files(self, tmp_path):
        paths = generate_program(SLEEP_SOURCE, self.REF, tmp_path)
        # 1 index + 3 day nodes
        assert len(paths) == 4
        for p in paths:
            assert p.exists()

    def test_day_filenames_are_zero_padded(self, tmp_path):
        paths = generate_program(SLEEP_SOURCE, self.REF, tmp_path)
        day_names = [p.name for p in paths if "Day" in p.name]
        assert any("Day 01" in n for n in day_names)
        assert any("Day 02" in n for n in day_names)
        assert any("Day 03" in n for n in day_names)

    def test_generate_from_real_yaml(self, tmp_path):
        """Smoke test: generate from the actual 14-day sleep YAML."""
        from egon.node_types.program import generate_programs_from_dir
        content_dir = Path(__file__).parent.parent / "content" / "programs"
        if not content_dir.exists():
            pytest.skip("content/programs not found")
        paths = generate_programs_from_dir(content_dir, self.REF, tmp_path)
        # sleep (15 nodes) + anxiety (8 nodes) = 23
        assert len(paths) >= 1
        for p in paths:
            assert p.exists()
            fm, _ = _parse(p.read_text())
            assert validate({**fm, "date": str(fm["date"])}) == []


# ---------------------------------------------------------------------------
# Summary node
# ---------------------------------------------------------------------------

class TestWeeklySummary:
    REF = date(2026, 4, 3)  # ISO week 14

    def test_filename(self):
        assert weekly_summary_filename(self.REF) == f"Weekly Summary {EM} 2026-W14.md"

    def test_frontmatter_type(self):
        fm, _ = make_weekly_summary(self.REF)
        assert fm["type"] == "summary"
        assert fm["period"] == "week"

    def test_period_label(self):
        fm, _ = make_weekly_summary(self.REF)
        assert fm["period_label"] == "2026-W14"

    def test_frontmatter_valid(self):
        fm, _ = make_weekly_summary(self.REF)
        fm_copy = {**fm, "date": str(fm["date"])}
        assert validate(fm_copy) == []

    def test_body_contains_week_range(self):
        _, body = make_weekly_summary(self.REF)
        # Week 14 of 2026: Mon 30 Mar – Sun 5 Apr
        assert "2026-03-30" in body
        assert "2026-04-05" in body

    def test_body_has_all_sections(self):
        _, body = make_weekly_summary(self.REF)
        assert "## How the week felt" in body
        assert "## What came up" in body
        assert "## One thing I noticed about myself" in body
        assert "## Carry forward" in body

    def test_generates_file(self, tmp_path):
        path = generate_weekly_summary(self.REF, tmp_path)
        assert path.exists()
        assert "2026-W14" in path.name


class TestMonthlySummary:
    REF = date(2026, 4, 3)

    def test_filename(self):
        assert monthly_summary_filename(self.REF) == f"Monthly Summary {EM} 2026-04.md"

    def test_frontmatter_type(self):
        fm, _ = make_monthly_summary(self.REF)
        assert fm["type"] == "summary"
        assert fm["period"] == "month"

    def test_period_label(self):
        fm, _ = make_monthly_summary(self.REF)
        assert fm["period_label"] == "2026-04"

    def test_frontmatter_valid(self):
        fm, _ = make_monthly_summary(self.REF)
        fm_copy = {**fm, "date": str(fm["date"])}
        assert validate(fm_copy) == []

    def test_body_has_all_sections(self):
        _, body = make_monthly_summary(self.REF)
        assert "## How the month felt" in body
        assert "## Themes that came up" in body
        assert "## What I noticed about myself" in body
        assert "## What I want to carry forward" in body

    def test_generates_file(self, tmp_path):
        path = generate_monthly_summary(self.REF, tmp_path)
        assert path.exists()
        assert "2026-04" in path.name
