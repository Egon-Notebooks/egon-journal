"""
Report configuration loader.

Reads ``egon.toml`` from the current working directory (i.e. the project root
where you run ``uv run egon``).  If the file is absent or a key is missing,
the hard-coded defaults below are used, so the config is fully optional.

Format example (egon.toml):

    [report.analyses]
    wordcloud   = false   # disabled by default
    topics      = true
    pronoun_ratio = true
    # ... any subset of keys; omitted keys keep their defaults
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, bool] = {
    # Section 1 — Journal Insights
    "word_count": True,
    "wordcloud": False,  # most frequent words (formerly a word cloud); opt-in
    "pronoun_ratio": True,
    "topics": True,
    # Section 2 — Personality & Affective Patterns
    "sentiment": True,
    "stress": True,
    "loneliness": True,
    "bigfive": True,
    "mbti": True,
    # Section 3 — Physiological Measures
    "weight": True,
    "resting_heart_rate": True,
    "hrv": True,
    "sleep": True,
    "step_count": True,
    "exercise": True,
    "vo2max": True,
    "daylight": True,
    "sleep_regularity": True,
    # Section 2 additions
    "emotion": True,
    "cognitive_bias": True,
    # Section 4 — Cross-Signal Analysis
    "correlation_matrix": True,
    "top_correlations": True,
    "highlighted_correlations": True,
    # Local LLM additions (require `uv sync --extra local-llm` and Ollama running;
    # skipped gracefully when Ollama is unavailable)
    "llm_health_summary": True,
    "llm_health_commentary": True,
    "llm_journal_summary": True,
}

# What `egon report --share` includes unless [report.share] in egon.toml says otherwise.
_SHARE_INCLUDED = frozenset(
    {
        "llm_journal_summary",
        "llm_health_summary",
        "sentiment",
        "stress",
        "sleep",
        "step_count",
        "exercise",
    }
)

# Default signal pairs to exclude from the top-correlations chart.
# These are typically tautological or near-identity relationships that add
# little interpretive value (e.g. body mass ↔ lean body mass).
_DEFAULT_EXCLUDED_CORRELATION_PAIRS: list[tuple[str, str]] = [
    ("weight", "lean mass"),
]


@dataclass
class ReportConfig:
    """Which analyses are enabled in the full report."""

    analyses: dict[str, bool] = field(default_factory=dict)
    excluded_correlation_pairs: list[tuple[str, str]] = field(
        default_factory=lambda: list(_DEFAULT_EXCLUDED_CORRELATION_PAIRS)
    )

    def enabled(self, key: str) -> bool:
        """Return True if *key* is enabled, falling back to the hard-coded default."""
        return self.analyses.get(key, _DEFAULTS.get(key, True))


def share_config(overrides: dict[str, bool] | None = None) -> ReportConfig:
    """Return the shorter set of analyses for a report to share, plus any *overrides*."""
    return ReportConfig(
        analyses={**{k: k in _SHARE_INCLUDED for k in _DEFAULTS}, **(overrides or {})}
    )


def load_report_config(config_path: Path | None = None, *, share: bool = False) -> ReportConfig:
    """
    Load ``egon.toml`` from *config_path* (or the cwd if None).

    Unknown keys under ``[report.analyses]`` are silently ignored so that
    old config files remain forward-compatible.
    """
    path = config_path or (Path.cwd() / "egon.toml")
    if not path.is_file():
        return share_config() if share else ReportConfig()

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    analyses_raw: dict = raw.get("report", {}).get("analyses", {})
    # Only accept keys we know about; cast to bool for safety.
    analyses = {k: bool(v) for k, v in analyses_raw.items() if k in _DEFAULTS}

    corr_raw: dict = raw.get("report", {}).get("correlations", {})
    raw_pairs = corr_raw.get("exclude_pairs", None)
    if raw_pairs is not None:
        excluded_pairs = [(str(p[0]), str(p[1])) for p in raw_pairs if len(p) == 2]
    else:
        excluded_pairs = list(_DEFAULT_EXCLUDED_CORRELATION_PAIRS)

    if share:
        share_raw: dict = raw.get("report", {}).get("share", {})
        analyses = share_config(
            {k: bool(v) for k, v in share_raw.items() if k in _DEFAULTS}
        ).analyses

    return ReportConfig(analyses=analyses, excluded_correlation_pairs=excluded_pairs)


# ---------------------------------------------------------------------------
# Where reports are written
# ---------------------------------------------------------------------------

DEFAULT_REPORTS_DIR = Path("reports")


def reports_dir() -> Path:
    """Folder for all reports and the model-score cache.

    ``$EGON_REPORTS_DIR`` (``~`` is expanded) if set, otherwise ``./reports`` in the
    current working directory.  Reports contain personal data, so keep this folder
    out of anything that syncs or shares publicly.
    """
    raw = os.environ.get("EGON_REPORTS_DIR", "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_REPORTS_DIR


# ---------------------------------------------------------------------------
# Local LLM config
# ---------------------------------------------------------------------------

_DEFAULT_LOCAL_LLM_MODEL = "qwen2.5:7b"


@dataclass
class LocalLlmConfig:
    model: str = _DEFAULT_LOCAL_LLM_MODEL


GRAPH_APPS = ("obsidian", "logseq")


def load_graph_app(config_path: Path | None = None) -> str:
    """Return ``app`` from ``[graph]`` in ``egon.toml``: "obsidian" (default) or "logseq"."""
    path = config_path or (Path.cwd() / "egon.toml")
    if not path.is_file():
        return "obsidian"
    with path.open("rb") as fh:
        app = str(tomllib.load(fh).get("graph", {}).get("app", "obsidian")).lower()
    if app not in GRAPH_APPS:
        raise ValueError(f"[graph] app in egon.toml must be 'obsidian' or 'logseq', got '{app}'")
    return app


def load_local_llm_config(config_path: Path | None = None) -> LocalLlmConfig:
    """Load ``[local_llm]`` section from ``egon.toml``, falling back to defaults."""
    path = config_path or (Path.cwd() / "egon.toml")
    if not path.is_file():
        return LocalLlmConfig()
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    model = raw.get("local_llm", {}).get("model", _DEFAULT_LOCAL_LLM_MODEL)
    return LocalLlmConfig(model=str(model))
