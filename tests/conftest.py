"""
Make every test run as it does in CI: isolated from personal data and without
the optional model extras.

Isolation: ``egon.cli`` loads ``.env`` on import, which on a developer machine
points at the real journal and Apple Health export.  Every test therefore runs
with all ``EGON_*`` variables removed and inside its own temporary working
directory, so relative paths such as ``reports/`` (and the model-score cache)
never touch real reports.  Tests that need a variable or directory set it
themselves.

Optional extras:
CI installs only the base package and dev tools (`uv sync --all-groups`), so the
local language models (`limbic`), BERTopic (`topics`) and the Ollama client
(`local-llm`) are unavailable there.  A developer machine may have them — on
Intel Macs through `.venv-limbic` — which used to make local and CI results
differ.  This autouse fixture hides them for every test, so a local
`uv run pytest` reproduces CI exactly (and runs in seconds instead of minutes).

To run the suite against the real models instead:

    EGON_TEST_MODELS=1 uv run pytest
"""

import os
import sys

import pytest

# Modules that can hand work to the separate .venv-limbic interpreter.
_SUBPROCESS_MODULES = [
    "egon.limbic.bigfive",
    "egon.limbic.cognitive_bias",
    "egon.limbic.emotion",
    "egon.limbic.loneliness",
    "egon.limbic.mbti",
    "egon.limbic.stress",
    "egon.analytics.topics",
]

# Packages from the optional extras; importing them raises ImportError in tests.
# (An import hook rather than ``sys.modules[name] = None``: scipy inspects
# ``sys.modules["torch"]`` and breaks on a None entry.)
_OPTIONAL_PACKAGES = [
    "torch",
    "transformers",
    "sentencepiece",
    "bertopic",
    "sentence_transformers",
    "ollama",
]


class _BlockOptionalExtras:
    """Meta-path finder that makes the optional packages look uninstalled."""

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in _OPTIONAL_PACKAGES:
            raise ModuleNotFoundError(f"No module named '{name}' (hidden in tests)", name=name)
        return None


@pytest.fixture(autouse=True)
def _isolated_from_personal_data(monkeypatch, tmp_path):
    for key in [k for k in os.environ if k.startswith("EGON_")]:
        monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def _without_optional_extras(monkeypatch):
    if os.environ.get("EGON_TEST_MODELS") == "1":
        yield
        return
    for module in _SUBPROCESS_MODULES:
        monkeypatch.setattr(f"{module}._use_subprocess_venv", lambda: False)
    for package in _OPTIONAL_PACKAGES:
        if package in sys.modules:
            monkeypatch.delitem(sys.modules, package)
    monkeypatch.setattr(sys, "meta_path", [_BlockOptionalExtras(), *sys.meta_path])
    yield
