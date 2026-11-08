"""
Aggregate journal entries into one Markdown file.

Most AI chatbots accept only a handful of uploaded files, so ``egon report`` and
``egon export-context`` write a period's journal entries into a single file: one
level-2 heading per entry, oldest first.  The file is written locally only; the user decides whether to share it.
"""

import re

from egon.analytics.loader import JournalEntry

# The placeholder that `egon new-entry` writes into an empty entry.
_PLACEHOLDER = "<!-- Write here. No required structure. -->"
_HEADING = re.compile(r"^(#{1,6})(?=\s)")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _demote_headings(body: str, levels: int = 2) -> str:
    """Push headings inside an entry below its date heading (outside code fences)."""
    lines, in_fence = [], False
    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and (m := _HEADING.match(line)):
            hashes = "#" * min(len(m.group(1)) + levels, 6)
            line = hashes + line[m.end(1) :]
        lines.append(line)
    return "\n".join(lines)


def _meta_line(meta: dict) -> str:
    parts = []
    for key in ("mood", "energy"):
        value = meta.get(key)
        if value not in (None, ""):
            parts.append(f"{key.capitalize()}: {value}")
    tags = meta.get("tags")
    if isinstance(tags, str):
        tags = [tags]
    if tags:
        parts.append("Tags: " + ", ".join(str(t) for t in tags))
    return " · ".join(parts)


def _text(entry: JournalEntry) -> str:
    return entry.body.replace(_PLACEHOLDER, "").strip()


def entries_with_text(entries: list[JournalEntry]) -> list[JournalEntry]:
    """Entries :func:`journal_markdown` includes: an untouched template is left out."""
    return [e for e in entries if _text(e)]


def journal_markdown(entries: list[JournalEntry], title: str) -> str:
    """Return *entries* (oldest first) as one Markdown document headed *title*."""
    entries = entries_with_text(entries)
    sections = []
    for entry in entries:
        heading = f"## {entry.date.isoformat()} ({entry.date:%A})"
        meta = _meta_line(entry.meta or {})
        body = _demote_headings(_text(entry))
        sections.append("\n\n".join(p for p in (heading, meta, body) if p))

    if entries:
        noun = "journal entry" if len(entries) == 1 else "journal entries"
        intro = (
            f"{len(entries)} {noun} from {entries[0].date.isoformat()} to "
            f"{entries[-1].date.isoformat()}, oldest first. Each entry starts with a "
            "level-2 heading with its date."
        )
    else:
        intro = "No journal entries with text in this period."
    return "\n\n---\n\n".join([f"# {title}\n\n{intro}", *sections]) + "\n"
