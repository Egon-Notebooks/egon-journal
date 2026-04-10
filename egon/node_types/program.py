"""
Program index and program-day node renderer from YAML source.

Node types produced:
  - program      → one index node per program
  - program-day  → one node per day in the program

Filename conventions:
  - Index:  {Program title}.md
  - Day:    {Program title} — Day {NN}.md   (NN zero-padded to 2 digits)

YAML source schema (content/programs/*.yaml):
    title: "14-Day Sleep Improvement"
    duration_days: 14
    description: "A two-week track for…"      # Intro paragraph for index body
    tags: [sleep, programs]
    related_articles:                          # For "Related reading" section
      - "Sleep and mental health"
      - "Building a daily routine"
    days:
      - day: 1
        heading: "How sleep affects your mood"
        related_article: "Sleep and mental health"
        prompt_text: |
          How did you sleep last night?…
        starter: "Last night I slept…"
      - day: 2
        …
"""

from datetime import date as date_type
from pathlib import Path

import yaml

from egon.renderer import write_node


def load_program_yaml(yaml_path: Path) -> dict:
    """Load a program YAML source file."""
    with yaml_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _day_title(program_title: str, day_num: int) -> str:
    return f"{program_title} \u2014 Day {day_num:02d}"


def _day_filename(program_title: str, day_num: int) -> str:
    return f"{_day_title(program_title, day_num)}.md"


def make_program_index(source: dict, generation_date: date_type) -> tuple[dict, str]:
    """Return (frontmatter, body) for a program index node."""
    title = source["title"]
    duration_days: int = source["duration_days"]
    tags = source.get("tags", [])
    description = source.get("description", "")
    related_articles: list[str] = source.get("related_articles", [])

    frontmatter = {
        "title": title,
        "date": generation_date,
        "type": "program",
        "tags": tags,
        "duration_days": duration_days,
        "egon_version": "1",
    }

    lines: list[str] = [f"# {title}", ""]
    if description:
        lines += [description, ""]
    lines += [
        "You do not have to start on any particular date. Work through the",
        "days in order, but skip and return if you need to.",
        "",
        "## Days",
        "",
    ]
    for n in range(1, duration_days + 1):
        lines.append(f"- [[{_day_title(title, n)}]]")

    if related_articles:
        lines += ["", "## Related reading", ""]
        for article in related_articles:
            lines.append(f"- [[{article}]]")

    body = "\n".join(lines) + "\n"
    return frontmatter, body


def make_program_day(source: dict, day_data: dict, generation_date: date_type) -> tuple[dict, str]:
    """Return (frontmatter, body) for a program-day node."""
    program_title = source["title"]
    tags = source.get("tags", [])
    day_num: int = day_data["day"]
    heading: str = day_data["heading"]
    related_article: str = day_data.get("related_article", "")
    prompt_text: str = day_data.get("prompt_text", "").strip()
    starter: str = day_data.get("starter", "")

    title = _day_title(program_title, day_num)

    frontmatter = {
        "title": title,
        "date": generation_date,
        "type": "program-day",
        "tags": tags,
        "program": program_title,
        "day": day_num,
        "egon_version": "1",
    }

    lines: list[str] = [f"# Day {day_num} \u2014 {heading}", ""]

    if related_article:
        lines += [
            "## Today's reading",
            "",
            f"[[{related_article}]]",
            "",
            "Read the article above before continuing.",
            "",
        ]

    lines += ["## Reflection", ""]
    if starter:
        lines += [f"> {starter}", ""]
    if prompt_text:
        lines += [prompt_text, ""]
    lines += ["---", "", f"[[{program_title}]]"]

    body = "\n".join(lines) + "\n"
    return frontmatter, body


def generate_program(source: dict, generation_date: date_type, output_dir: Path) -> list[Path]:
    """
    Generate all nodes for a program (index + every day node).
    Returns the list of written file paths.
    """
    title = source["title"]
    generated: list[Path] = []

    # Index node
    fm, body = make_program_index(source, generation_date)
    index_path = output_dir / f"{title}.md"
    write_node(index_path, fm, body)
    generated.append(index_path)

    # Day nodes
    for day_data in source.get("days", []):
        fm, body = make_program_day(source, day_data, generation_date)
        day_path = output_dir / _day_filename(title, day_data["day"])
        write_node(day_path, fm, body)
        generated.append(day_path)

    return generated


def generate_programs_from_dir(
    programs_dir: Path, generation_date: date_type, output_dir: Path
) -> list[Path]:
    """
    Generate all program nodes from YAML files in *programs_dir*.
    Returns list of generated file paths.
    """
    generated: list[Path] = []
    for yaml_path in sorted(programs_dir.glob("*.yaml")):
        source = load_program_yaml(yaml_path)
        generated.extend(generate_program(source, generation_date, output_dir))
    return generated
