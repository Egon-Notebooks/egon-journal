"""
First-person pronoun ratio.

Tracks the fraction of words that are first-person pronouns (I, me, my, mine,
myself) per journal entry over time.  High pronoun density is associated with
self-focused processing, which in turn correlates with depressive rumination in
psycholinguistics research (Pennebaker et al. 2003).
"""

import re
from datetime import date as date_type

from egon.analytics.loader import JournalEntry

_FIRST_PERSON = re.compile(r"\b(I|me|my|mine|myself)\b")
_WORD = re.compile(r"\b\w+\b")


def pronoun_ratio_by_day(
    entries: list[JournalEntry],
) -> list[tuple[date_type, float]]:
    """
    Return daily first-person pronoun ratio (pronouns / total words).
    Entries with zero words return 0.0.
    """
    result: list[tuple[date_type, float]] = []
    for entry in entries:
        words = _WORD.findall(entry.body)
        n = len(words)
        if n == 0:
            result.append((entry.date, 0.0))
            continue
        pronouns = len(_FIRST_PERSON.findall(entry.body))
        result.append((entry.date, pronouns / n))
    return sorted(result, key=lambda x: x[0])
