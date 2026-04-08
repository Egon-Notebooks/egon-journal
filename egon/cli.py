"""
CLI entry point for egon-journal.

Run via:  uv run egon <command>
"""
import os
import subprocess
from datetime import date as date_type
from pathlib import Path
from typing import Optional

import typer
import yaml
from dotenv import load_dotenv

from egon.analytics.loader import load_journal_entries
from egon.analytics.wordcloud_plot import plot_wordcloud
from egon.health.apple_health import (
    daily_mean,
    daily_sum,
    filter_by_date,
    infer_unit,
    load_records,
)
from egon.health.hrv_plot import plot_hrv
from egon.health.sleep import filter_sleep_by_date, load_sleep_onset, load_sleep_records
from egon.health.sleep_plot import plot_sleep
from egon.health.resting_heart_rate_plot import plot_resting_heart_rate
from egon.health.step_count_plot import plot_step_count
from egon.health.vo2max_plot import plot_vo2max
from egon.health.weight_plot import plot_weight
from egon.limbic.bigfive import bigfive_by_day
from egon.limbic.bigfive_plot import plot_bigfive
from egon.limbic.mbti import mbti_by_day
from egon.limbic.mbti_plot import plot_mbti
from egon.limbic.sentiment_plot import plot_sentiment
from egon.analytics.word_count import (
    filter_entries,
    parse_period_value,
    period_bounds,
    period_label,
    plot_word_count,
)
from egon.linker import index_graph, inject_wikilinks, load_topics
from egon.node_types.journal_entry import generate_journal_entry
from egon.node_types.prompt import generate_prompts_from_dir
from egon.node_types.program import (
    generate_program as _generate_program,
    generate_programs_from_dir,
    load_program_yaml,
)
from egon.node_types.summary import generate_monthly_summary, generate_weekly_summary
from egon.schema import validate as _validate_frontmatter

load_dotenv()

app = typer.Typer(
    name="egon",
    help="egon-journal: structured journaling for the Egon graph.",
    no_args_is_help=True,
)

_REPO_ROOT = Path(__file__).parent.parent
_CONTENT_DIR = _REPO_ROOT / "content"
_GENERATED_DIR = _REPO_ROOT / "generated"


# ---------------------------------------------------------------------------
# Output directory helpers
# ---------------------------------------------------------------------------

def _resolve_output(cli_output: Optional[Path], env_var: str) -> Path:
    if cli_output:
        return cli_output
    env_dir = os.environ.get(env_var)
    if env_dir:
        return Path(env_dir)
    return _GENERATED_DIR


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def new_entry(
    date: Optional[str] = typer.Option(
        None, help="Entry date as YYYY-MM-DD (default: today)"
    ),
    open: bool = typer.Option(False, "--open", help="Open the file in $EDITOR after creating"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Create a journal entry for today (or a given date)."""
    entry_date = date_type.fromisoformat(date) if date else date_type.today()
    out_dir = _resolve_output(output, "EGON_JOURNAL_DIR")
    path = generate_journal_entry(entry_date, out_dir)
    typer.echo(f"Created: {path}")
    if open:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(path)])


@app.command()
def new_summary(
    period: str = typer.Option(..., help="'week' or 'month'"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Create a weekly or monthly summary template for the current period."""
    today = date_type.today()
    out_dir = _resolve_output(output, "EGON_SUMMARIES_DIR")
    if period == "week":
        path = generate_weekly_summary(today, out_dir)
    elif period == "month":
        path = generate_monthly_summary(today, out_dir)
    else:
        typer.echo(f"Error: --period must be 'week' or 'month', got '{period}'", err=True)
        raise typer.Exit(1)
    typer.echo(f"Created: {path}")


@app.command()
def generate_prompts(
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Generate all prompt nodes from YAML source files in content/prompts/."""
    prompts_dir = _CONTENT_DIR / "prompts"
    if not prompts_dir.exists():
        typer.echo(f"Error: prompts directory not found: {prompts_dir}", err=True)
        raise typer.Exit(1)
    out_dir = _resolve_output(output, "EGON_GRAPH_DIR")
    paths = generate_prompts_from_dir(prompts_dir, date_type.today(), out_dir)
    for p in paths:
        typer.echo(f"Generated: {p}")
    typer.echo(f"Done. {len(paths)} prompt(s) generated.")


@app.command(name="generate-program")
def generate_program(
    name: str = typer.Option(..., "--name", help="Program title (must match YAML 'title' field)"),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Generate all nodes for a specific program by title."""
    programs_dir = _CONTENT_DIR / "programs"
    source = _find_program(programs_dir, name)
    if source is None:
        typer.echo(f"Error: no program found with title '{name}'", err=True)
        raise typer.Exit(1)
    out_dir = _resolve_output(output, "EGON_GRAPH_DIR")
    paths = _generate_program(source, date_type.today(), out_dir)
    for p in paths:
        typer.echo(f"Generated: {p}")
    typer.echo(f"Done. {len(paths)} node(s) generated.")


@app.command()
def generate_all_programs(
    output: Optional[Path] = typer.Option(None, help="Output directory"),
) -> None:
    """Generate all program nodes from YAML source files in content/programs/."""
    programs_dir = _CONTENT_DIR / "programs"
    if not programs_dir.exists():
        typer.echo(f"Error: programs directory not found: {programs_dir}", err=True)
        raise typer.Exit(1)
    out_dir = _resolve_output(output, "EGON_GRAPH_DIR")
    paths = generate_programs_from_dir(programs_dir, date_type.today(), out_dir)
    for p in paths:
        typer.echo(f"Generated: {p}")
    typer.echo(f"Done. {len(paths)} node(s) generated.")


@app.command()
def list_programs() -> None:
    """List available programs from YAML source files."""
    programs_dir = _CONTENT_DIR / "programs"
    if not programs_dir.exists():
        typer.echo("No programs directory found.")
        return
    found = False
    for yaml_path in sorted(programs_dir.glob("*.yaml")):
        source = load_program_yaml(yaml_path)
        title = source.get("title", yaml_path.stem)
        duration = source.get("duration_days", "?")
        typer.echo(f"  {title} ({duration} days)")
        found = True
    if not found:
        typer.echo("No programs found.")


@app.command(name="validate")
def validate_nodes(
    path: Path = typer.Option(..., "--path", help="File or directory to validate"),
) -> None:
    """Validate the frontmatter of Egon Markdown nodes."""
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(path.rglob("*.md"))
    else:
        typer.echo(f"Error: path does not exist: {path}", err=True)
        raise typer.Exit(1)

    total = 0
    invalid = 0
    for md_file in files:
        content = md_file.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError as exc:
            typer.echo(f"YAML ERROR: {md_file}\n  {exc}", err=True)
            invalid += 1
            continue
        if not isinstance(fm, dict):
            continue
        total += 1
        errors = _validate_frontmatter(fm)
        if errors:
            invalid += 1
            typer.echo(f"INVALID: {md_file}")
            for err in errors:
                typer.echo(f"  - {err}")
        else:
            typer.echo(f"OK: {md_file}")

    if invalid:
        typer.echo(f"\n{invalid} file(s) with errors.", err=True)
        raise typer.Exit(1)
    else:
        typer.echo(f"\nAll {total} node(s) valid.")


@app.command(name="index")
def index_cmd(
    graph_dir: Path = typer.Option(..., "--graph-dir", help="Path to the Egon graph directory"),
) -> None:
    """Output all node titles in a graph directory (one per line, suitable for TOPICS.txt)."""
    if not graph_dir.is_dir():
        typer.echo(f"Error: directory not found: {graph_dir}", err=True)
        raise typer.Exit(1)
    for title in index_graph(graph_dir):
        typer.echo(title)


@app.command()
def link(
    file: Path = typer.Argument(..., help="Markdown file to inject wikilinks into"),
    topics_file: Path = typer.Option(
        Path("TOPICS.txt"), "--topics", help="Path to TOPICS.txt"
    ),
) -> None:
    """Inject wikilinks into a Markdown file based on TOPICS.txt."""
    if not file.is_file():
        typer.echo(f"Error: file not found: {file}", err=True)
        raise typer.Exit(1)
    topics = load_topics(topics_file)
    if not topics:
        typer.echo("No topics found. Run 'egon index --graph-dir <dir> > TOPICS.txt' first.")
        raise typer.Exit(1)

    content = file.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            new_body = inject_wikilinks(parts[2], topics)
            file.write_text(f"---{parts[1]}---{new_body}", encoding="utf-8")
            typer.echo(f"Linked: {file}")
            return

    file.write_text(inject_wikilinks(content, topics), encoding="utf-8")
    typer.echo(f"Linked: {file}")


@app.command(name="report-word-count")
def report_word_count(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files "
             "(default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/word_count/<period-label>.pdf)",
    ),
) -> None:
    """Plot journal word count by day and save as a PDF figure."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(
            f"No journal entries found for period '{period}' ({label}).", err=True
        )
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/word_count/{label}.pdf")
    title = f"Journal word count — {label}"

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    plot_word_count(entries, resolved_output, title=title)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-sentiment")
def report_sentiment(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files "
             "(default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/sentiment/<period-label>.pdf)",
    ),
) -> None:
    """Plot VADER sentiment score by day and save as a PDF figure."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(
            f"No journal entries found for period '{label}'.", err=True
        )
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/sentiment/{label}.pdf")
    title = f"Journal sentiment — {label}"

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    plot_sentiment(entries, resolved_output, title=title)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-wordcloud")
def report_wordcloud(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files "
             "(default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/wordcloud/<period-label>.pdf)",
    ),
) -> None:
    """Generate a word cloud from journal entries and save as a PDF figure."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/wordcloud/{label}.pdf")
    title = f"Journal word cloud — {label}"

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    plot_wordcloud(entries, resolved_output, title=title)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-bigfive")
def report_bigfive(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files "
             "(default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/bigfive/<period-label>.pdf)",
    ),
) -> None:
    """Plot Big Five personality trait scores from journal entries (requires --extra bigfive)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    typer.echo("Scoring Big Five traits (this may take a moment on first run) …")
    data = bigfive_by_day(entries)

    resolved_output = output or Path(f"reports/bigfive/{label}.pdf")
    title = f"Big Five personality traits — {label}"

    plot_bigfive(data, resolved_output, title=title)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-mbti")
def report_mbti(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files "
             "(default: $EGON_JOURNAL_DIR)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/mbti/<period-label>.pdf)",
    ),
) -> None:
    """Plot MBTI personality dimension scores from journal entries (requires --extra bigfive)."""
    resolved_dir = _resolve_output(journal_dir, "EGON_JOURNAL_DIR")
    if not resolved_dir.is_dir():
        typer.echo(
            f"Error: journal directory not found: {resolved_dir}\n"
            "Set EGON_JOURNAL_DIR in .env or pass --journal-dir.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    all_entries = load_journal_entries(resolved_dir)
    if not all_entries:
        typer.echo(f"No journal entries found in: {resolved_dir}", err=True)
        raise typer.Exit(1)

    entries = filter_entries(all_entries, start, end)
    if not entries:
        typer.echo(f"No journal entries found for period '{label}'.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Found {len(entries)} journal entries for {label}.")
    typer.echo("Classifying MBTI type per entry …")
    data = mbti_by_day(entries)

    resolved_output = output or Path(f"reports/mbti/{label}.pdf")
    title = f"MBTI personality dimensions — {label}"

    plot_mbti(data, resolved_output, title=title)
    typer.echo(f"Saved: {resolved_output}")


# ---------------------------------------------------------------------------
# Health reports
# ---------------------------------------------------------------------------

def _resolve_apple_health_xml(cli_path: Optional[Path]) -> Optional[Path]:
    if cli_path:
        return cli_path
    env_val = os.environ.get("EGON_APPLE_HEALTH_XML")
    return Path(env_val) if env_val else None


def _load_and_report(xml_path: Path) -> dict:
    """Parse export.xml and print the available metric names."""
    typer.echo(f"Parsing {xml_path.name} ...")
    records = load_records(xml_path)
    metrics = sorted(records.keys())
    typer.echo(f"Found {len(metrics)} metric(s): {', '.join(metrics)}")
    return records


@app.command(name="report-weight")
def report_weight(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/weight/<period-label>.pdf)",
    ),
) -> None:
    """Plot daily mean weight from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    weight_records = records.get("BodyMass", [])
    if not weight_records:
        typer.echo("Error: no BodyMass records found in export.", err=True)
        raise typer.Exit(1)

    unit = infer_unit(weight_records)
    data = filter_by_date(daily_mean(weight_records), start, end)
    if not data:
        typer.echo(f"No weight data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    lean_records = records.get("LeanBodyMass", [])
    lean_data = filter_by_date(daily_mean(lean_records), start, end) if lean_records else None
    if lean_data:
        typer.echo(f"Found {len(lean_data)} days of lean body mass data for {label}.")

    def _parse_target(env_key: str) -> float | None:
        raw = os.getenv(env_key, "").strip()
        try:
            return float(raw) if raw else None
        except ValueError:
            typer.echo(f"Warning: {env_key}={raw!r} is not a valid number — ignoring.", err=True)
            return None

    target_body_mass = _parse_target("EGON_TARGET_BODY_MASS")
    target_lean_body_mass = _parse_target("EGON_TARGET_LEAN_BODY_MASS")

    resolved_output = output or Path(f"reports/weight/{label}.pdf")
    title = f"Weight — {label}"

    typer.echo(f"Found {len(data)} days of weight data for {label}.")
    plot_weight(
        data, resolved_output, title=title, unit=unit,
        lean_data=lean_data,
        target_body_mass=target_body_mass,
        target_lean_body_mass=target_lean_body_mass,
    )
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-resting-heart-rate")
def report_resting_heart_rate(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/resting_heart_rate/<period-label>.pdf)",
    ),
) -> None:
    """Plot daily mean resting heart rate from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    rhr_records = records.get("RestingHeartRate", [])
    if not rhr_records:
        typer.echo("Error: no RestingHeartRate records found in export.", err=True)
        raise typer.Exit(1)

    unit = infer_unit(rhr_records)
    data = filter_by_date(daily_mean(rhr_records), start, end)
    if not data:
        typer.echo(f"No resting heart rate data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/resting_heart_rate/{label}.pdf")
    title = f"Resting heart rate — {label}"

    typer.echo(f"Found {len(data)} days of resting heart rate data for {label}.")
    plot_resting_heart_rate(data, resolved_output, title=title, unit=unit)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-hrv")
def report_hrv(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/hrv/<period-label>.pdf)",
    ),
) -> None:
    """Plot daily mean heart rate variability (HRV SDNN) from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    hrv_records = records.get("HeartRateVariabilitySDNN", [])
    if not hrv_records:
        typer.echo("Error: no HeartRateVariabilitySDNN records found in export.", err=True)
        raise typer.Exit(1)

    unit = infer_unit(hrv_records)
    data = filter_by_date(daily_mean(hrv_records), start, end)
    if not data:
        typer.echo(f"No HRV data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/hrv/{label}.pdf")
    title = f"Heart rate variability — {label}"

    typer.echo(f"Found {len(data)} days of HRV data for {label}.")
    plot_hrv(data, resolved_output, title=title, unit=unit)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-sleep")
def report_sleep(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/sleep/<period-label>.pdf)",
    ),
) -> None:
    """Plot nightly hours asleep from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Parsing {resolved_xml.name} ...")
    all_data = load_sleep_records(resolved_xml)
    if not all_data:
        typer.echo("Error: no SleepAnalysis records found in export.", err=True)
        raise typer.Exit(1)

    data = filter_sleep_by_date(all_data, start, end)
    if not data:
        typer.echo(f"No sleep data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    all_onset = load_sleep_onset(resolved_xml)
    onset_data = filter_sleep_by_date(all_onset, start, end) or None

    resolved_output = output or Path(f"reports/sleep/{label}.pdf")
    title = f"Time asleep — {label}"

    typer.echo(f"Found {len(data)} nights of sleep data for {label}.")
    plot_sleep(data, resolved_output, title=title, onset_data=onset_data)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-step-count")
def report_step_count(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/step_count/<period-label>.pdf)",
    ),
) -> None:
    """Plot daily step count from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    step_records = records.get("StepCount", [])
    if not step_records:
        typer.echo("Error: no StepCount records found in export.", err=True)
        raise typer.Exit(1)

    data = filter_by_date(daily_sum(step_records), start, end)
    if not data:
        typer.echo(f"No step count data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/step_count/{label}.pdf")
    title = f"Daily step count — {label}"

    typer.echo(f"Found {len(data)} days of step count data for {label}.")
    plot_step_count(data, resolved_output, title=title)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report-vo2max")
def report_vo2max(
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output path (default: reports/vo2max/<period-label>.pdf)",
    ),
) -> None:
    """Plot daily mean VO2 max from an Apple Health export."""
    resolved_xml = _resolve_apple_health_xml(xml_path)
    if not resolved_xml:
        typer.echo(
            "Error: no Apple Health export found.\n"
            "Set EGON_APPLE_HEALTH_XML in .env or pass --xml.",
            err=True,
        )
        raise typer.Exit(1)
    if not resolved_xml.is_file():
        typer.echo(f"Error: file not found: {resolved_xml}", err=True)
        raise typer.Exit(1)

    try:
        if for_period:
            start, end, label = parse_period_value(for_period)
        else:
            start, end = period_bounds(period, date_type.today())
            label = period_label(period, date_type.today())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    records = _load_and_report(resolved_xml)

    vo2max_records = records.get("VO2Max", [])
    if not vo2max_records:
        typer.echo("Error: no VO2Max records found in export.", err=True)
        raise typer.Exit(1)

    unit = infer_unit(vo2max_records)
    data = filter_by_date(daily_mean(vo2max_records), start, end)
    if not data:
        typer.echo(f"No VO2 max data found for period '{label}'.", err=True)
        raise typer.Exit(1)

    resolved_output = output or Path(f"reports/vo2max/{label}.pdf")
    title = f"VO2 max — {label}"

    typer.echo(f"Found {len(data)} days of VO2 max data for {label}.")
    plot_vo2max(data, resolved_output, title=title, unit=unit)
    typer.echo(f"Saved: {resolved_output}")


@app.command(name="report")
def report_all(
    journal_dir: Optional[Path] = typer.Option(
        None,
        "--journal-dir",
        help="Directory containing journal entry Markdown files "
             "(default: $EGON_JOURNAL_DIR)",
    ),
    xml_path: Optional[Path] = typer.Option(
        None,
        "--xml",
        help="Path to Apple Health export.xml (default: $EGON_APPLE_HEALTH_XML)",
    ),
    period: str = typer.Option(
        "all-time",
        "--period",
        help="Time period relative to today: week, month, quarter, year, all-time",
    ),
    for_period: Optional[str] = typer.Option(
        None,
        "--for",
        help="Specific period value, e.g. 2025, 2026-02, 2026-W14, 2026-Q2. "
             "Overrides --period.",
    ),
) -> None:
    """Generate all reports for the given period."""
    _journal_reports = [
        ("word-count",  lambda: report_word_count(journal_dir=journal_dir, period=period, for_period=for_period, output=None)),
        ("sentiment",   lambda: report_sentiment(journal_dir=journal_dir, period=period, for_period=for_period, output=None)),
        ("wordcloud",   lambda: report_wordcloud(journal_dir=journal_dir, period=period, for_period=for_period, output=None)),
        ("bigfive",     lambda: report_bigfive(journal_dir=journal_dir, period=period, for_period=for_period, output=None)),
        ("mbti",        lambda: report_mbti(journal_dir=journal_dir, period=period, for_period=for_period, output=None)),
    ]
    _health_reports = [
        ("weight",               lambda: report_weight(xml_path=xml_path, period=period, for_period=for_period, output=None)),
        ("resting-heart-rate",   lambda: report_resting_heart_rate(xml_path=xml_path, period=period, for_period=for_period, output=None)),
        ("hrv",                  lambda: report_hrv(xml_path=xml_path, period=period, for_period=for_period, output=None)),
        ("sleep",                lambda: report_sleep(xml_path=xml_path, period=period, for_period=for_period, output=None)),
        ("step-count",           lambda: report_step_count(xml_path=xml_path, period=period, for_period=for_period, output=None)),
        ("vo2max",               lambda: report_vo2max(xml_path=xml_path, period=period, for_period=for_period, output=None)),
    ]

    period_display = for_period or period
    typer.echo(f"Generating all reports for: {period_display}\n")

    ok: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for name, fn in [*_journal_reports, *_health_reports]:
        typer.echo(f"[ {name} ]")
        try:
            fn()
            ok.append(name)
        except typer.Exit:
            # Sub-command printed its own error and exited — treat as skipped
            skipped.append(name)
        except Exception as exc:
            typer.echo(f"  Error: {exc}", err=True)
            failed.append(name)
        typer.echo("")

    # Summary
    typer.echo("─" * 50)
    typer.echo(f"Done: {len(ok)} generated, {len(skipped)} skipped, {len(failed)} failed")
    if ok:
        typer.echo(f"  Generated : {', '.join(ok)}")
    if skipped:
        typer.echo(f"  Skipped   : {', '.join(skipped)}")
    if failed:
        typer.echo(f"  Failed    : {', '.join(failed)}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_program(programs_dir: Path, title: str) -> Optional[dict]:
    """Return the YAML source dict for the program whose title matches, or None."""
    if not programs_dir.exists():
        return None
    for yaml_path in sorted(programs_dir.glob("*.yaml")):
        source = load_program_yaml(yaml_path)
        if source.get("title") == title:
            return source
    return None
