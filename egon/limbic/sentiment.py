"""
Sentiment analysis using VADER (Valence Aware Dictionary and sEntiment Reasoner).

VADER is a rule-based model tuned for social/informal text. It returns a
compound score in [-1, +1]: negative below -0.05, positive above +0.05,
neutral in between. Runs fully offline — no model download required.
"""

from datetime import date as date_type

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from egon.analytics.loader import JournalEntry

# Module-level analyser — initialised once, reused across calls
_analyser = SentimentIntensityAnalyzer()


def sentiment_score(text: str) -> float:
    """
    Return the VADER compound score for *text*, in [-1, +1].
    Empty text returns 0.0.
    """
    if not text.strip():
        return 0.0
    return _analyser.polarity_scores(text)["compound"]


def sentiment_by_day(entries: list[JournalEntry]) -> list[tuple[date_type, float]]:
    """Return a list of (date, compound_score) tuples sorted by date."""
    return [(e.date, sentiment_score(e.body)) for e in entries]
