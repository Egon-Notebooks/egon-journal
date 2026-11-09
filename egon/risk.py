"""
Signs of risk in journal entries (see docs/SAFETY.md).

A fixed list of phrases rather than a model, so the behavior is predictable. It
will miss some phrasings and catch some harmless ones. Egon is not a live service
and not a crisis tool: a match means a model does not write about that entry, and
the most recent entry can bring up one short, calm note.
"""

from __future__ import annotations

import re

from egon.analytics.loader import JournalEntry

RISK_NOTE = (
    "Some of what you wrote recently sounds very heavy. If you aren't already, "
    "you might consider talking it through with a professional."
)

_RISK_PHRASES = re.compile(
    r"\bsuicidal\b"
    r"|\b(kill|killing|hurt|hurting|harm|harming) myself\b"
    r"|\bself[- ]harm"
    r"|\bend(ing)? (my life|it all)\b"
    r"|\b(want|wanted) to die\b"
    r"|\bwish i (was|were|wasn't|weren't) (dead|alive|here)\b"
    r"|\bdon't want to (be here|be alive|live|wake up)\b"
    r"|\bbetter off without me\b"
    r"|\bno (reason|point) (to|in) (live|living|going on)\b",
    re.IGNORECASE,
)


def suggests_risk(text: str) -> bool:
    """Return True if *text* contains a phrase suggesting risk."""
    return bool(_RISK_PHRASES.search(text.replace("’", "'")))


def entries_for_reflection(entries: list[JournalEntry]) -> tuple[list[JournalEntry], str | None]:
    """
    Return (entries a model may use, note to show instead of a question).

    If the most recent entry suggests risk, no question is asked and the note is
    returned. Older entries that suggest risk are left out without comment, so the
    note does not follow someone around for months.
    """
    if suggests_risk(max(entries, key=lambda e: e.date).body):
        return [], RISK_NOTE
    return [e for e in entries if not suggests_risk(e.body)], None
