"""Tests for egon.schema.validate()."""
import pytest
from datetime import date

from egon.schema import validate, VALID_NODE_TYPES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base(type_: str, **overrides) -> dict:
    """Return a minimal valid universal frontmatter dict for *type_*."""
    fm = {
        "title": f"Test — {type_}",
        "date": date(2026, 4, 3),
        "type": type_,
        "tags": [],
        "egon_version": "1",
    }
    fm.update(overrides)
    return fm


def _journal(**kw) -> dict:
    return _base("journal", **kw)


def _prompt(**kw) -> dict:
    return _base("prompt", related_article="Some article", **kw)


def _program(**kw) -> dict:
    defaults = {"duration_days": 7}
    defaults.update(kw)
    return _base("program", **defaults)


def _program_day(**kw) -> dict:
    defaults = {"program": "Some Program", "day": 1}
    defaults.update(kw)
    return _base("program-day", **defaults)


def _summary(period="week", **kw) -> dict:
    return _base(
        "summary",
        period=period,
        period_label="2026-W14" if period == "week" else "2026-04",
        **kw,
    )


# ---------------------------------------------------------------------------
# Universal field tests
# ---------------------------------------------------------------------------

class TestUniversalFields:
    def test_valid_journal_returns_no_errors(self):
        assert validate(_journal()) == []

    def test_missing_title(self):
        fm = _journal()
        del fm["title"]
        errors = validate(fm)
        assert any("title" in e for e in errors)

    def test_missing_date(self):
        fm = _journal()
        del fm["date"]
        errors = validate(fm)
        assert any("date" in e for e in errors)

    def test_missing_type(self):
        fm = _journal()
        del fm["type"]
        errors = validate(fm)
        assert any("type" in e for e in errors)

    def test_missing_tags(self):
        fm = _journal()
        del fm["tags"]
        errors = validate(fm)
        assert any("tags" in e for e in errors)

    def test_missing_egon_version(self):
        fm = _journal()
        del fm["egon_version"]
        errors = validate(fm)
        assert any("egon_version" in e for e in errors)

    def test_invalid_type_string(self):
        fm = _journal(type="not-a-type")
        errors = validate(fm)
        assert any("Invalid type" in e for e in errors)

    def test_all_valid_types_accepted(self):
        for node_type in VALID_NODE_TYPES:
            # Build a valid fm for each type without type-specific extras
            fm = {"title": "T", "date": date(2026, 1, 1), "type": node_type,
                  "tags": [], "egon_version": "1"}
            errors = validate(fm)
            # Should not report an "Invalid type" error
            assert not any("Invalid type" in e for e in errors)

    def test_date_as_string_valid(self):
        fm = _journal(date="2026-04-03")
        assert validate(fm) == []

    def test_date_as_string_invalid(self):
        fm = _journal(date="not-a-date")
        errors = validate(fm)
        assert any("date" in e for e in errors)

    def test_egon_version_wrong_value(self):
        fm = _journal(egon_version="2")
        errors = validate(fm)
        assert any("egon_version" in e for e in errors)

    def test_tags_must_be_list(self):
        fm = _journal(tags="sleep")
        errors = validate(fm)
        assert any("tags" in e for e in errors)

    def test_multiple_missing_fields_all_reported(self):
        errors = validate({})
        assert len(errors) >= 5  # all universal fields missing


# ---------------------------------------------------------------------------
# Type-specific field tests
# ---------------------------------------------------------------------------

class TestPromptNode:
    def test_valid(self):
        assert validate(_prompt()) == []

    def test_missing_related_article(self):
        fm = _base("prompt")  # no related_article
        errors = validate(fm)
        assert any("related_article" in e for e in errors)


class TestProgramNode:
    def test_valid(self):
        assert validate(_program()) == []

    def test_missing_duration_days(self):
        fm = _base("program")
        errors = validate(fm)
        assert any("duration_days" in e for e in errors)

    def test_duration_days_must_be_positive(self):
        fm = _program(duration_days=0)
        errors = validate(fm)
        assert any("duration_days" in e for e in errors)


class TestProgramDayNode:
    def test_valid(self):
        assert validate(_program_day()) == []

    def test_missing_program(self):
        fm = _base("program-day", day=1)
        errors = validate(fm)
        assert any("program" in e for e in errors)

    def test_missing_day(self):
        fm = _base("program-day", program="Some Program")
        errors = validate(fm)
        assert any("'day'" in e for e in errors)

    def test_day_must_be_positive(self):
        fm = _program_day(day=0)
        errors = validate(fm)
        assert any("day" in e for e in errors)


class TestSummaryNode:
    def test_valid_weekly(self):
        assert validate(_summary("week")) == []

    def test_valid_monthly(self):
        assert validate(_summary("month")) == []

    def test_missing_period(self):
        fm = _base("summary", period_label="2026-W14")
        errors = validate(fm)
        assert any("period" in e for e in errors)

    def test_missing_period_label(self):
        fm = _base("summary", period="week")
        errors = validate(fm)
        assert any("period_label" in e for e in errors)

    def test_invalid_period_value(self):
        fm = _summary(period="quarterly")
        errors = validate(fm)
        assert any("period" in e for e in errors)
