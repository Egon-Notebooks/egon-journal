"""
Most frequent meaningful words in a set of journal entries.

Replaces the former word cloud: a ranked list is easier to read and compare
than word sizes, and needs no image rendering.
"""

import re
from collections import Counter

from egon.analytics.loader import JournalEntry

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_WORD_RE = re.compile(r"[a-z][a-z'’-]+")

# Standard English stopwords (function words that carry no topic).
_STOPWORDS = set(
    """
    a about above after again against all am an and any are aren't as at be because been
    before being below between both but by can can't cannot could couldn't did didn't do
    does doesn't doing don't down during each few for from further had hadn't has hasn't
    have haven't having he he'd he'll he's her here here's hers herself him himself his how
    how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most
    mustn't my myself no nor not of off on once only or other ought our ours ourselves out
    over own same shan't she she'd she'll she's should shouldn't so some such than that
    that's the their theirs them themselves then there there's these they they'd they'll
    they're they've this those through to too under until up very was wasn't we we'd we'll
    we're we've were weren't what what's when when's where where's which while who who's
    whom why why's with won't would wouldn't you you'd you'll you're you've your yours
    yourself yourselves also just even ever every get gets im ive dont didnt cant wont
    really maybe though although yet since around many much well
    """.split()
)

# Common Logseq/Markdown structural tokens and journaling filler words
_EXTRA_STOPWORDS = {
    "will",
    "one",
    "also",
    "get",
    "got",
    "go",
    "went",
    "day",
    "time",
    "today",
    "yesterday",
    "week",
    "bit",
    "felt",
    "feel",
    "feeling",
    "think",
    "thinking",
    "thought",
    "know",
    "really",
    "quite",
    "much",
    "still",
    "like",
    "just",
    "little",
    "lot",
    "things",
    "thing",
    "back",
    "going",
    "way",
    "good",
    "made",
    "done",
    "said",
    "want",
    "need",
    "make",
    "see",
    "look",
    "come",
    "came",
    "something",
}

STOPWORDS = _STOPWORDS | _EXTRA_STOPWORDS


def frequent_words(entries: list[JournalEntry], n: int = 25) -> list[tuple[str, int]]:
    """The *n* most frequent non-stopword words (lower-cased) across *entries*."""
    counts: Counter[str] = Counter()
    for entry in entries:
        text = _COMMENT_RE.sub("", entry.body).lower().replace("’", "'")
        counts.update(w for w in _WORD_RE.findall(text) if w not in STOPWORDS and len(w) > 2)
    return counts.most_common(n)
