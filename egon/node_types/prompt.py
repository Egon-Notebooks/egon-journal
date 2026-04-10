"""
Prompt node renderer from YAML source (type: prompt).

Source YAML lives in content/prompts/*.yaml.
Filename convention: Prompt — {name}.md  (em dash, not hyphen)

YAML source schema:
    name: "Rumination"                  # Short display name (used in title/filename)
    topic: "Rumination and how to …"   # Exact title of the linked article
    tags: [rumination, thinking-patterns]
    prompt_text: |
        Describe a thought that has been repeating…
    starter: "A thought that kept coming back to me recently…"
    duration_minutes: 5
"""

from datetime import date as date_type
from pathlib import Path

import yaml

from egon.renderer import write_node


def load_prompt_yaml(yaml_path: Path) -> dict:
    """Load a prompt YAML source file."""
    with yaml_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_prompt_node(source: dict, generation_date: date_type) -> tuple[dict, str]:
    """Return (frontmatter, body) for a prompt node from a YAML source dict."""
    topic = source["topic"]
    name = source.get("name", topic)
    tags = source.get("tags", [])
    prompt_text = source["prompt_text"].strip()
    starter = source.get("starter", "")
    duration = source.get("duration_minutes", 5)

    title = f"Prompt \u2014 {name}"

    frontmatter = {
        "title": title,
        "date": generation_date,
        "type": "prompt",
        "tags": tags,
        "related_article": topic,
        "egon_version": "1",
    }

    lines: list[str] = [f"# {title}", ""]
    if starter:
        lines += [f"> {starter}", ""]
    lines.append(prompt_text)
    lines.append("")
    if duration:
        lines.append(f"There are no right answers. Write for {duration} minutes without stopping.")
        lines.append("")
    lines += ["---", "", f"[[{topic}]]"]

    body = "\n".join(lines) + "\n"
    return frontmatter, body


def prompt_filename(source: dict) -> str:
    """Return the canonical filename for a prompt node."""
    name = source.get("name", source["topic"])
    return f"Prompt \u2014 {name}.md"


def generate_prompt(source: dict, generation_date: date_type, output_dir: Path) -> Path:
    """
    Write a prompt node to *output_dir*.
    Returns the path of the written file.
    """
    frontmatter, body = make_prompt_node(source, generation_date)
    path = output_dir / prompt_filename(source)
    write_node(path, frontmatter, body)
    return path


def generate_prompts_from_dir(
    prompts_dir: Path, generation_date: date_type, output_dir: Path
) -> list[Path]:
    """
    Generate all prompt nodes from YAML files in *prompts_dir*.
    Returns list of generated file paths.
    """
    generated: list[Path] = []
    for yaml_path in sorted(prompts_dir.glob("*.yaml")):
        source = load_prompt_yaml(yaml_path)
        generated.append(generate_prompt(source, generation_date, output_dir))
    return generated
