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

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, bool] = {
    # Section 1 — Journal Insights
    "word_count": True,
    "sentiment": True,
    "wordcloud": False,  # slow and space-heavy; opt-in
    "pronoun_ratio": True,
    "topics": True,
    # Section 2 — Personality & Affective Patterns
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
    # Section 2 additions
    "emotion": True,
    # Section 4 — Cross-Signal Analysis
    "correlation_matrix": True,
    "highlighted_correlations": True,
}


@dataclass
class ReportConfig:
    """Which analyses are enabled in the full report."""

    analyses: dict[str, bool] = field(default_factory=dict)

    def enabled(self, key: str) -> bool:
        """Return True if *key* is enabled, falling back to the hard-coded default."""
        return self.analyses.get(key, _DEFAULTS.get(key, True))


def load_report_config(config_path: Path | None = None) -> ReportConfig:
    """
    Load ``egon.toml`` from *config_path* (or the cwd if None).

    Unknown keys under ``[report.analyses]`` are silently ignored so that
    old config files remain forward-compatible.
    """
    path = config_path or (Path.cwd() / "egon.toml")
    if not path.is_file():
        return ReportConfig()

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    analyses_raw: dict = raw.get("report", {}).get("analyses", {})
    # Only accept keys we know about; cast to bool for safety.
    analyses = {k: bool(v) for k, v in analyses_raw.items() if k in _DEFAULTS}
    return ReportConfig(analyses=analyses)
