"""
Journal entry node generator (type: journal).

Obsidian: ``Journal — YYYY-MM-DD.md`` (em dash) with YAML frontmatter.
Logseq: ``YYYY_MM_DD.md``, Logseq's own journal file name, with page properties, so
the entry is that day's journal page in Logseq.
"""

from datetime import date as date_type
from pathlib import Path

from egon.renderer import write_node
from egon.schema import EGON_VERSION

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
        "egon_version": EGON_VERSION,
    }
    return frontmatter, _BODY


def journal_entry_filename(entry_date: date_type) -> str:
    """Return the canonical filename for a journal entry."""
    return f"Journal \u2014 {entry_date.strftime('%Y-%m-%d')}.md"


def logseq_journal_filename(entry_date: date_type) -> str:
    """Return Logseq's file name for the journal page of *entry_date*."""
    return f"{entry_date.strftime('%Y_%m_%d')}.md"


def make_logseq_journal_entry() -> str:
    """Return the content of an empty Logseq journal page with Egon's page properties."""
    return f"type:: journal\negon_version:: {EGON_VERSION}\n\n- \n"


def generate_journal_entry(entry_date: date_type, output_dir: Path, app: str = "obsidian") -> Path:
    """
    Write a journal entry node for *entry_date* to *output_dir* and return its path.

    Raises FileExistsError rather than overwrite an entry that is already there.
    """
    if app == "logseq":
        path = output_dir / logseq_journal_filename(entry_date)
    else:
        path = output_dir / journal_entry_filename(entry_date)
    if path.exists():
        raise FileExistsError(path)
    if app == "logseq":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(make_logseq_journal_entry(), encoding="utf-8")
    else:
        frontmatter, body = make_journal_entry(entry_date)
        write_node(path, frontmatter, body)
    return path
