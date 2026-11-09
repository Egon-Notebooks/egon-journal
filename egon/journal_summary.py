"""
AI summary of journal entries via a local model (Ollama).

Writes a short summary of a period, naming any particularly important events the
entries mention. Long periods are summarized in stretches first, because small local models
only read a few thousand words at a time.

All inference runs locally; no data leaves the device. Entries that suggest risk are
never sent to the model (egon.risk).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from egon.analytics.loader import JournalEntry
from egon.local_llm import build_context, chat
from egon.risk import entries_for_reflection

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_SYSTEM: str = (_PROMPTS_DIR / "journal_summary_system.txt").read_text(encoding="utf-8").strip()

_COMBINE_SYSTEM: str = (
    (_PROMPTS_DIR / "journal_summary_combine_system.txt").read_text(encoding="utf-8").strip()
)

_MAX_SUMMARY_WORDS = 200
_MAX_CONTEXT_CHARS = 8_000  # roughly what a default Ollama context holds with room to answer


@dataclass(frozen=True)
class JournalSummary:
    summary: str = ""
    risk_note: str | None = None


def _stretches(entries: list[JournalEntry]) -> list[list[JournalEntry]]:
    """Split date-sorted *entries* into stretches that each fit in the model's context."""
    stretches: list[list[JournalEntry]] = [[]]
    size = 0
    for entry in entries:
        if stretches[-1] and size + len(entry.body) > _MAX_CONTEXT_CHARS:
            stretches.append([])
            size = 0
        stretches[-1].append(entry)
        size += len(entry.body)
    return stretches


def _merge_summaries(summaries: list[str], model: str) -> str:
    """Merge stretch summaries, and shorten once more if small models overrun the limit."""
    merged = chat(model, _COMBINE_SYSTEM, "\n\n---\n\n".join(summaries))
    if len(merged.split()) > _MAX_SUMMARY_WORDS:
        merged = chat(model, _COMBINE_SYSTEM, merged)
    return merged


def generate_journal_summary(entries: list[JournalEntry], model: str) -> JournalSummary:
    """Return a summary of *entries*, or only a risk note if the latest entry suggests risk."""
    usable, risk_note = entries_for_reflection(entries)
    if risk_note:
        return JournalSummary(risk_note=risk_note)

    ask = "Here are my journal entries:\n\n{}\n\nWrite the summary as instructed."
    parts = [
        chat(model, _SYSTEM, ask.format(build_context(stretch)))
        for stretch in _stretches(sorted(usable, key=lambda e: e.date))
    ]
    return JournalSummary(summary=parts[0] if len(parts) == 1 else _merge_summaries(parts, model))
