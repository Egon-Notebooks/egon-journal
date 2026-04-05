"""
Journal entry loader for analytics.

Scans a directory for journal entry Markdown files (type: journal) and
returns their date and body text. Files are returned in chronological order.
"""
import re
from datetime import date as date_type
from pathlib import Path
from typing import NamedTuple

import yaml


class JournalEntry(NamedTuple):
    date: date_type
    body: str       # raw body text (after frontmatter)
    path: Path


def load_journal_entries(journal_dir: Path) -> list[JournalEntry]:
    """
    Load all journal entry nodes from *journal_dir*.

    Accepts both the new format (YAML frontmatter with type: journal) and
    falls back to parsing the date from the filename
    (``Journal — YYYY-MM-DD.md``) when frontmatter is absent or malformed.

    Returns entries sorted by date ascending.
    """
    entries: list[JournalEntry] = []

    for md_file in sorted(journal_dir.glob("*.md")):
        entry = _parse_file(md_file)
        if entry is not None:
            entries.append(entry)

    return sorted(entries, key=lambda e: e.date)


def _parse_file(path: Path) -> JournalEntry | None:
    """Parse a single Markdown file into a JournalEntry, or return None."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            try:
                fm = yaml.safe_load(parts[1])
            except yaml.YAMLError:
                fm = {}
            body = parts[2]
            if isinstance(fm, dict):
                # Only load nodes explicitly typed as journal (or untyped files
                # that match the filename pattern)
                node_type = fm.get("type")
                if node_type not in (None, "journal"):
                    return None
                raw_date = fm.get("date")
                if raw_date:
                    entry_date = _coerce_date(raw_date)
                    if entry_date:
                        return JournalEntry(date=entry_date, body=body, path=path)
    else:
        body = content

    # Fall back: try to extract date from filename  "Journal — YYYY-MM-DD.md"
    entry_date = _date_from_filename(path.stem)
    if entry_date:
        return JournalEntry(date=entry_date, body=body, path=path)

    return None


def _coerce_date(value: object) -> date_type | None:
    if isinstance(value, date_type):
        return value
    if isinstance(value, str):
        try:
            return date_type.fromisoformat(value)
        except ValueError:
            pass
    return None


# Matches YYYY-MM-DD (Egon) or YYYY_MM_DD (Logseq) anywhere in the stem
_DATE_PATTERN = re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})")


def _date_from_filename(stem: str) -> date_type | None:
    m = _DATE_PATTERN.search(stem)
    if m:
        try:
            return date_type(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None
