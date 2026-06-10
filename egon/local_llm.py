"""
Local LLM support via Ollama for journal prompt generation.

Requires the optional dependency group:
    uv sync --extra local-llm

Ollama must be installed and running:
    brew install ollama
    ollama serve
"""

from __future__ import annotations

from pathlib import Path

from egon.analytics.loader import JournalEntry

DEFAULT_MODEL = "qwen2.5:7b"

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_SYSTEM_PROMPT: str = (_PROMPTS_DIR / "reflection_question_system.txt").read_text(encoding="utf-8").strip()


def check_hardware(model: str) -> str:
    """
    Return a one-line hardware status string for *model*.

    Uses only stdlib — no psutil required. Falls back gracefully if RAM
    cannot be determined (e.g. on an unsupported platform).
    """
    ram_gb = _total_ram_gb()
    size_b = _model_size_b(model)

    if ram_gb is None:
        return "Hardware: RAM unknown — cannot verify headroom."

    ram_str = f"{ram_gb:.0f} GB RAM"

    if size_b is None:
        return f"Hardware: {ram_str} (model size unknown, cannot estimate headroom)."

    required_gb = size_b * 0.65 + 0.5  # rough 4-bit quant estimate

    if ram_gb < required_gb:
        return (
            f"Hardware: {ram_str} — {model} needs ~{required_gb:.0f} GB. "
            "It will likely fail to load; consider a smaller model."
        )
    if ram_gb < required_gb * 1.5:
        return (
            f"Hardware: {ram_str} — {model} needs ~{required_gb:.0f} GB. "
            "It should load but may be slow."
        )
    return f"Hardware: {ram_str} — {model} needs ~{required_gb:.0f} GB. OK."


def _total_ram_gb() -> float | None:
    """Return total physical RAM in GB using stdlib sysconf (macOS/Linux)."""
    try:
        import os
        page_size = os.sysconf("SC_PAGE_SIZE")
        num_pages = os.sysconf("SC_PHYS_PAGES")
        return (page_size * num_pages) / (1024 ** 3)
    except (AttributeError, ValueError, OSError):
        return None


def _model_size_b(model: str) -> float | None:
    """Parse the parameter count in billions from a model name, e.g. 'qwen2.5:7b' → 7.0."""
    import re
    m = re.search(r"(\d+(?:\.\d+)?)b", model.lower())
    return float(m.group(1)) if m else None


def _import_ollama():
    try:
        import ollama
        return ollama
    except ImportError:
        raise ImportError(
            "The 'ollama' package is not installed.\n"
            "Install it with:  uv sync --extra local-llm"
        )


def ensure_model(model: str) -> None:
    """Pull *model* from the Ollama library if it is not already available locally."""
    ollama = _import_ollama()

    try:
        local_names = {m.model for m in ollama.list().models}
    except Exception as exc:
        _raise_connection_error(exc)

    if model in local_names:
        return

    print(f"Model '{model}' not found locally — pulling from Ollama library…")
    last_status = ""
    try:
        for chunk in ollama.pull(model, stream=True):
            status = getattr(chunk, "status", "") or ""
            if status and status != last_status:
                total = getattr(chunk, "total", None)
                completed = getattr(chunk, "completed", None)
                if total and completed:
                    pct = int(100 * completed / total)
                    print(f"\r  {status} {pct}%", end="", flush=True)
                else:
                    print(f"\r  {status}        ", end="", flush=True)
                last_status = status
    except Exception as exc:
        _raise_connection_error(exc)
    print()


def build_context(entries: list[JournalEntry]) -> str:
    """Render *entries* into a single context block for the LLM."""
    parts = []
    for entry in entries:
        parts.append(f"## {entry.date}\n\n{entry.body.strip()}")
    return "\n\n---\n\n".join(parts)


def generate_journal_prompt(entries: list[JournalEntry], model: str) -> str:
    """
    Send recent journal *entries* to the local Ollama *model* and return a
    suggested introspective question for today's journal entry.
    """
    ollama = _import_ollama()
    context = build_context(entries)
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Here are my recent journal entries:\n\n{context}\n\nRespond with exactly one reflective question. Nothing else.",
                },
            ],
        )
    except Exception as exc:
        _raise_connection_error(exc)
    return response.message.content.strip()


def _raise_connection_error(exc: Exception) -> None:
    msg = str(exc).lower()
    if any(k in msg for k in ("connection", "refused", "connect", "socket")):
        raise RuntimeError(
            "Cannot connect to Ollama. Is it running?\n"
            "Start it with:  ollama serve"
        ) from exc
    raise exc
