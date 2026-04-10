"""
Wikilink injection for Egon nodes.

In V1, the combined topic list is loaded from a flat text file (TOPICS.txt),
one title per line.  The linker scans a Markdown body and wraps the first
occurrence of each topic title in [[double brackets]], skipping any that are
already wrapped.
"""

import re
from pathlib import Path

import yaml


def load_topics(topics_file: Path) -> list[str]:
    """Load topic titles from a flat text file, one title per line."""
    if not topics_file.exists():
        return []
    lines = topics_file.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def inject_wikilinks(body: str, topics: list[str]) -> str:
    """
    Inject [[title]] wikilinks into *body*.

    - Only the first bare occurrence of each topic is linked.
    - Topics already wrapped in [[ ]] are not re-wrapped.
    - Longer topic strings are matched before shorter ones to avoid partial
      matches (e.g. "Anxiety disorders" before "Anxiety").
    """
    for topic in sorted(topics, key=len, reverse=True):
        if f"[[{topic}]]" in body:
            continue
        escaped = re.escape(topic)
        # Negative lookbehind/ahead to avoid re-wrapping existing wikilinks
        pattern = rf"(?<!\[\[){escaped}(?!\]\])"
        body, _ = re.subn(pattern, f"[[{topic}]]", body, count=1)
    return body


def index_graph(graph_dir: Path) -> list[str]:
    """
    Scan *graph_dir* recursively for Markdown files and return their titles.

    Reads the ``title`` field from each file's YAML frontmatter.
    Files without a parseable frontmatter are silently skipped.
    """
    titles: list[str] = []
    for md_file in sorted(graph_dir.rglob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            frontmatter = yaml.safe_load(parts[1])
            if isinstance(frontmatter, dict) and "title" in frontmatter:
                titles.append(str(frontmatter["title"]))
        except Exception:
            pass
    return titles
