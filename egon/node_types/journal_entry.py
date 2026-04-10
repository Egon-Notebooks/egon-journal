"""
Journal entry node generator (type: journal).

Filename convention: Journal — YYYY-MM-DD.md  (em dash, not hyphen)
"""

from datetime import date as date_type
from pathlib import Path

from egon.renderer import write_node

_BODY = "<!-- Write here. No required structure. -->\n"


def make_journal_entry(entry_date: date_type) -> tuple[dict, str]:
    """Return (frontmatter, body) for a journal entry node."""
    date_str = entry_date.strftime("%Y-%m-%d")
    frontmatter = {
        "title": f"Journal \u2014 {date_str}",
        "date": entry_date,
        "type": "journal",
        "tags": [],
        "mood": "",
        "energy": "",
        "egon_version": "1",
    }
    return frontmatter, _BODY


def journal_entry_filename(entry_date: date_type) -> str:
    """Return the canonical filename for a journal entry."""
    return f"Journal \u2014 {entry_date.strftime('%Y-%m-%d')}.md"


def generate_journal_entry(entry_date: date_type, output_dir: Path) -> Path:
    """
    Write a journal entry node for *entry_date* to *output_dir*.
    Returns the path of the written file.
    """
    frontmatter, body = make_journal_entry(entry_date)
    path = output_dir / journal_entry_filename(entry_date)
    write_node(path, frontmatter, body)
    return path
