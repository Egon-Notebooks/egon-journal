"""
Weekly and monthly summary template generator (type: summary).

Filename conventions:
  - Weekly:  Weekly Summary — YYYY-WNN.md
  - Monthly: Monthly Summary — YYYY-MM.md
"""

from datetime import date as date_type
from datetime import timedelta
from pathlib import Path

from egon.renderer import write_node


def _iso_week_label(d: date_type) -> str:
    """Return an ISO week label like '2026-W14'."""
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def _week_bounds(d: date_type) -> tuple[date_type, date_type]:
    """Return (Monday, Sunday) for the ISO week that contains *d*."""
    start = d - timedelta(days=d.weekday())
    return start, start + timedelta(days=6)


# ---------------------------------------------------------------------------
# Weekly summary
# ---------------------------------------------------------------------------


def make_weekly_summary(ref_date: date_type) -> tuple[dict, str]:
    """Return (frontmatter, body) for a weekly summary node."""
    period_label = _iso_week_label(ref_date)
    week_start, week_end = _week_bounds(ref_date)
    title = f"Weekly Summary \u2014 {period_label}"

    frontmatter = {
        "title": title,
        "date": ref_date,
        "type": "summary",
        "period": "week",
        "period_label": period_label,
        "tags": [],
        "egon_version": "1",
    }

    body = (
        f"# {title}\n"
        "\n"
        "## How the week felt\n"
        "\n"
        "<!-- One paragraph. Overall mood, energy, tone. -->\n"
        "\n"
        "## What came up\n"
        "\n"
        "<!-- Themes, situations, or feelings that appeared more than once. -->\n"
        "\n"
        "## One thing I noticed about myself\n"
        "\n"
        "<!-- A pattern, a reaction, something that surprised you. -->\n"
        "\n"
        "## Carry forward\n"
        "\n"
        "<!-- One thing to hold onto or pay attention to next week. -->\n"
        "\n"
        "---\n"
        "\n"
        f"_Week of {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}_\n"
    )
    return frontmatter, body


def weekly_summary_filename(ref_date: date_type) -> str:
    return f"Weekly Summary \u2014 {_iso_week_label(ref_date)}.md"


def generate_weekly_summary(ref_date: date_type, output_dir: Path) -> Path:
    """Write a weekly summary node. Returns the path of the written file."""
    fm, body = make_weekly_summary(ref_date)
    path = output_dir / weekly_summary_filename(ref_date)
    write_node(path, fm, body)
    return path


# ---------------------------------------------------------------------------
# Monthly summary
# ---------------------------------------------------------------------------


def make_monthly_summary(ref_date: date_type) -> tuple[dict, str]:
    """Return (frontmatter, body) for a monthly summary node."""
    period_label = ref_date.strftime("%Y-%m")
    month_name = ref_date.strftime("%B %Y")
    title = f"Monthly Summary \u2014 {period_label}"

    frontmatter = {
        "title": title,
        "date": ref_date,
        "type": "summary",
        "period": "month",
        "period_label": period_label,
        "tags": [],
        "egon_version": "1",
    }

    body = (
        f"# {title}\n"
        "\n"
        "## How the month felt\n"
        "\n"
        f"<!-- One paragraph. Overall mood, energy, tone for {month_name}. -->\n"
        "\n"
        "## Themes that came up\n"
        "\n"
        "<!-- Recurring situations, feelings, or patterns across the month. -->\n"
        "\n"
        "## What I noticed about myself\n"
        "\n"
        "<!-- A pattern, a reaction, or something that surprised you. -->\n"
        "\n"
        "## What I want to carry forward\n"
        "\n"
        "<!-- One or two things to hold onto or pay attention to next month. -->\n"
        "\n"
        "---\n"
        "\n"
        f"_{month_name}_\n"
    )
    return frontmatter, body


def monthly_summary_filename(ref_date: date_type) -> str:
    return f"Monthly Summary \u2014 {ref_date.strftime('%Y-%m')}.md"


def generate_monthly_summary(ref_date: date_type, output_dir: Path) -> Path:
    """Write a monthly summary node. Returns the path of the written file."""
    fm, body = make_monthly_summary(ref_date)
    path = output_dir / monthly_summary_filename(ref_date)
    write_node(path, fm, body)
    return path
