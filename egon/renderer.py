"""
Shared Markdown rendering utilities.

Nodes are plain Markdown files with YAML frontmatter. This module provides
helpers for serializing frontmatter and writing complete node files.
"""
from pathlib import Path

import yaml


def render_frontmatter(fields: dict) -> str:
    """
    Serialize a dict as a YAML frontmatter block (with --- delimiters).
    Insertion order of keys is preserved.
    """
    body = yaml.dump(
        fields,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{body}---\n"


def render_node(frontmatter: dict, body: str) -> str:
    """Return a complete Markdown node string."""
    return render_frontmatter(frontmatter) + "\n" + body.strip() + "\n"


def write_node(path: Path, frontmatter: dict, body: str) -> None:
    """
    Write a rendered node to *path*.
    Creates parent directories if they do not exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_node(frontmatter, body), encoding="utf-8")
