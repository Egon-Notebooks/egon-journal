"""
Full combined report for egon-journal, as one self-contained HTML file.

``collect_report_data`` (egon.report.data) gathers every signal for the period
once; ``build_full_report`` turns that into report sections with numbered
figures; ``generate_full_report`` does both and writes the file.  Each figure
is skipped (with a note on stdout) when its data is unavailable.

Usage:
    from egon.full_report import generate_full_report
    generate_full_report(
        journal_entries=entries,
        xml_path=xml,
        start=start, end=end, label="2026-Q1",
        output_path=Path("reports/full_report/2026-Q1.html"),
    )
"""

from collections.abc import Callable
from datetime import date as date_type
from pathlib import Path
from statistics import mean

from egon.analytics.correlation import correlation_matrix, top_pairs
from egon.analytics.loader import JournalEntry
from egon.config import ReportConfig, load_report_config
from egon.report import figures as F
from egon.report.charts.sleep import format_duration
from egon.report.data import ReportData, build_signals, collect_report_data
from egon.report.html import Figure, Report, Section, Stat, write_report

__all__ = ["build_full_report", "build_signals", "generate_full_report"]

# ---------------------------------------------------------------------------
# Section copy
# ---------------------------------------------------------------------------

_EXEC_SUMMARY = (
    "This report covers the selected period and draws on your written journal "
    "entries alongside Apple Health data to provide a structured overview of "
    "your psychological and physical wellbeing. The goal is to surface patterns "
    "that are difficult to perceive day-to-day and to give you — and anyone you "
    "choose to share this with — a common language for discussing how you have been."
    "\n\n"
    "The pages that follow are arranged from the most subjective signals (what you "
    "wrote, how you expressed yourself) through to more objective physiological "
    "markers (what your body recorded). Reading them together may reveal connections "
    "between your inner world and your physical state: for instance, whether nights "
    "of poor sleep precede days of lower-sentiment writing, or whether high activity "
    "correlates with a more open, positive tone."
    "\n\n"
    "Personality trait scores (Big Five, MBTI) reflect the emotional and cognitive "
    "tone of your writing during this period rather than fixed character traits. "
    "They should be interpreted as a snapshot of how you expressed yourself. Sudden "
    "shifts in physiological metrics — weight, resting heart rate, or sleep — are "
    "worth noting and may be worth discussing with a healthcare professional."
)

_JOURNAL_INTRO = (
    "Journal insights are derived directly from your written entries. Word count "
    "captures your daily expressive output and engagement with the journaling "
    "practice. Sentiment reflects the overall emotional valence of your language "
    "on each day — whether your words tended toward the positive, neutral, or "
    "negative. Frequent words and discovered topics show what was on your mind "
    "across the period."
    "\n\n"
    "Together these three views give a picture of your expressive rhythm: how much "
    "you wrote, how you felt as you wrote, and what was on your mind. Gaps in the "
    "word count chart may indicate days without an entry and are worth noting as "
    "part of the broader picture."
)

_PERSONALITY_INTRO = (
    "Personality and affective pattern scores are inferred from the language you "
    "used in your journal entries: stress, loneliness, emotional tone and thinking "
    "patterns, alongside personality. The Big Five model scores your writing on five "
    "dimensions — Openness, Conscientiousness, Extraversion, Agreeableness, and "
    "Neuroticism — that are widely used in psychological research. The MBTI model "
    "classifies entries across four binary dimensions (E/I, N/S, T/F, J/P)."
    "\n\n"
    "Day-to-day variation is typically more meaningful than absolute values; look "
    "for trends and shifts over time rather than interpreting individual data points "
    "as fixed personality markers. A prolonged shift in Neuroticism or a sustained "
    "drop in Extraversion, for example, may be worth reflecting on."
)

_PHYSIO_INTRO = (
    "Physiological measures are drawn from your Apple Health data. Each metric has "
    "known associations with mental health and wellbeing: resting heart rate and "
    "heart rate variability (HRV) reflect autonomic nervous system state and "
    "recovery; sleep duration and onset regularity are strongly linked to mood "
    "regulation and depressive symptoms; body weight changes can signal stress or "
    "lifestyle shifts; step count captures daily physical activity; and VO\u2082 max "
    "tracks aerobic fitness over time."
    "\n\n"
    "Not all metrics may be present — data availability depends on your Apple Health "
    "export and the devices you use. Metrics that were not recorded during the "
    "selected period are omitted from this section."
)

_CROSS_SIGNAL_INTRO = (
    "This section examines relationships between the time series collected "
    "across the other three sections. Rather than looking at each signal in "
    "isolation, it asks: on days when one metric was higher than usual, were "
    "other metrics systematically higher or lower too? Strong correlations do "
    "not prove causation, but they can surface patterns worth exploring — for "
    "example, whether poor sleep reliably precedes lower mood, or whether "
    "physical activity aligns with a more positive tone in your writing."
    "\n\n"
    "Only days on which both signals in a pair were recorded contribute to that "
    "pair\u2019s correlation, so pairs involving infrequently recorded metrics "
    "(e.g. VO\u2082 max, lean body mass) may rest on fewer data points."
)

_LLM_NOTE = (
    "This summary was generated locally by an on-device language model via "
    "Ollama; no data left this device. Verify any figures against the charts "
    "that follow."
)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


class _SectionBuilder:
    """Collects figures for one section, numbering them and skipping failures."""

    def __init__(self, number: int, title: str, intro: str, commentary: dict[str, str]):
        self.section = Section(number=number, title=title, intro=intro)
        self._commentary = commentary

    def add(self, enabled: bool, name: str, build: Callable[[], Figure]) -> None:
        if not enabled:
            return
        try:
            fig = build()
        except Exception as exc:  # missing data, too few points, optional extra absent …
            print(f"  [full report] skipping '{name}': {exc}")
            return
        fig.number = f"{self.section.number}.{len(self.section.figures) + 1}"
        if not fig.commentary:
            fig.commentary = self._commentary.get(fig.key, "")
        self.section.figures.append(fig)


def _pct(v: float) -> str:
    return f"{v * 100:.0f}"


def _journal_stats(data: ReportData) -> list[Stat]:
    if not data.entries:
        return []
    from egon.analytics.word_count import word_counts_by_day

    words = [w for _, w in word_counts_by_day(data.entries)]
    days = (data.end - data.start).days + 1
    stats = [
        Stat(
            "Entries",
            str(len(data.entries)),
            "",
            f"on {len({e.date for e in data.entries})} of {days} days",
        ),
        Stat("Words per entry", f"{mean(words):,.0f}", "", f"{sum(words):,} words in total"),
    ]
    if sent := data.signals.get("sentiment"):
        stats.append(
            Stat("Average tone", f"{mean(v for _, v in sent):+.2f}", "", "VADER, −1 to +1")
        )
    return stats


def _affect_stats(data: ReportData) -> list[Stat]:
    stats = []
    if s := data.scores.get("stress"):
        stats.append(
            Stat("Stress signal", _pct(mean(x.stress for _, x in s)), "%", "average probability")
        )
    if s := data.scores.get("loneliness"):
        stats.append(
            Stat(
                "Loneliness signal", _pct(mean(x.lonely for _, x in s)), "%", "average probability"
            )
        )
    if s := data.scores.get("emotion"):
        from egon.limbic.emotion import EMOTIONS

        means = {e: mean(x[i] for _, x in s) for i, e in enumerate(EMOTIONS) if e != "neutral"}
        top = max(means, key=means.get)
        stats.append(
            Stat("Most present emotion", top, "", f"{means[top]:.0%} of tone, besides neutral")
        )
    if s := data.scores.get("cognitive_bias"):
        stats.append(
            Stat("Distortion signal", _pct(mean(x.distortion_score for _, x in s)), "%", "average")
        )
    return stats


def _physio_stats(data: ReportData) -> list[Stat]:
    stats = []
    if data.sleep_hours:
        stats.append(
            Stat(
                "Sleep",
                format_duration(mean(v for _, v in data.sleep_hours)),
                "",
                "average per night",
            )
        )
    if s := data.health.get("steps"):
        stats.append(Stat("Steps", f"{mean(v for _, v in s.data):,.0f}", "", "average per day"))
    if s := data.health.get("resting_heart_rate"):
        stats.append(Stat("Resting HR", f"{mean(v for _, v in s.data):.0f}", s.unit, "average"))
    if s := data.health.get("hrv"):
        stats.append(Stat("HRV", f"{mean(v for _, v in s.data):.0f}", s.unit, "average"))
    return stats


def _cross_stats(data: ReportData, cfg: ReportConfig) -> list[Stat]:
    if len(data.signals) < 2:
        return []
    pairs = correlation_matrix(data.signals)
    stats = [
        Stat("Signals compared", str(len(data.signals))),
        Stat(
            "Pairs",
            str(len(pairs)),
            "",
            f"{sum(p.significant for p in pairs)} significant at p < 0.05",
        ),
    ]
    try:
        best = top_pairs(data.signals, n=1, exclude_pairs=cfg.excluded_correlation_pairs)[0]
        stats.append(Stat("Strongest pair", f"{best.r:+.2f}", "r", f"{best.a} ↔ {best.b}"))
    except ValueError:
        pass
    return stats


def build_full_report(
    data: ReportData,
    *,
    config: ReportConfig,
    target_body_mass: float | None = None,
    target_lean_body_mass: float | None = None,
    target_resting_heart_rate: float | None = None,
    target_exercise_minutes: float | None = None,
    synthetic: bool = False,
    persona: str | None = None,
) -> Report:
    cfg = config
    note = data.llm_commentary
    entries = data.entries
    sc = data.scores
    hl = data.health

    # --- Section 1: Journal insights ------------------------------------------
    s1 = _SectionBuilder(1, "Journal Insights", _JOURNAL_INTRO, note)
    s1.section.stats = _journal_stats(data)
    s1.add(
        cfg.enabled("word_count"), "word-count", lambda: F.word_count_figure(_word_counts(entries))
    )
    s1.add(
        cfg.enabled("wordcloud"), "wordcloud", lambda: F.frequent_words_figure(_frequent(entries))
    )
    s1.add(
        cfg.enabled("pronoun_ratio"),
        "pronoun-ratio",
        lambda: F.pronoun_ratio_figure(_pronoun_ratio(entries)),
    )
    if cfg.enabled("topics") and entries:
        try:
            from egon.analytics.topics import fit_topics, topic_summary, topic_timeline

            topic_ids, _docs, model = fit_topics(entries)
            summary = topic_summary(model)
            s1.add(True, "topic-summary", lambda: F.topic_summary_figure(summary))
            s1.add(
                True,
                "topic-timeline",
                lambda: F.topic_timeline_figure(topic_timeline(entries, topic_ids, model), summary),
            )
        except ImportError:
            print(
                "  [full report] skipping 'topics': BERTopic not installed (uv sync --extra topics)"
            )
        except Exception as exc:
            print(f"  [full report] skipping 'topics': {exc}")

    # --- Section 2: Personality & affective patterns ----------------------------
    s2 = _SectionBuilder(2, "Personality & Affective Patterns", _PERSONALITY_INTRO, note)
    s2.section.stats = _affect_stats(data)
    s2.add(
        cfg.enabled("sentiment") and "sentiment" in data.signals,
        "sentiment",
        lambda: F.sentiment_figure(data.signals["sentiment"]),
    )
    s2.add(
        cfg.enabled("stress") and "stress" in sc, "stress", lambda: F.stress_figure(sc["stress"])
    )
    s2.add(
        cfg.enabled("loneliness") and "loneliness" in sc,
        "loneliness",
        lambda: F.loneliness_figure(sc["loneliness"]),
    )
    s2.add(
        cfg.enabled("emotion") and "emotion" in sc,
        "emotion",
        lambda: F.emotion_figure(sc["emotion"]),
    )
    s2.add(
        cfg.enabled("cognitive_bias") and "cognitive_bias" in sc,
        "cognitive-bias",
        lambda: F.cognitive_bias_figure(sc["cognitive_bias"]),
    )
    s2.add(
        cfg.enabled("bigfive") and "bigfive" in sc,
        "bigfive",
        lambda: F.bigfive_figure(sc["bigfive"]),
    )
    s2.add(cfg.enabled("mbti") and "mbti" in sc, "mbti", lambda: F.mbti_figure(sc["mbti"]))

    # --- Section 3: Physiological measures -------------------------------------
    s3 = _SectionBuilder(3, "Physiological Measures", _PHYSIO_INTRO, note)
    s3.section.stats = _physio_stats(data)
    if data.llm_summary:
        s3.section.notes.append(
            ("Health summary (AI-generated)", data.llm_summary + "\n\n" + _LLM_NOTE)
        )
    s3.add(
        cfg.enabled("weight") and "weight" in hl,
        "weight",
        lambda: F.weight_figure(
            hl["weight"].data,
            unit=hl["weight"].unit,
            lean_data=hl["lean_mass"].data if "lean_mass" in hl else None,
            target=target_body_mass,
            lean_target=target_lean_body_mass,
        ),
    )
    s3.add(
        cfg.enabled("resting_heart_rate") and "resting_heart_rate" in hl,
        "resting-heart-rate",
        lambda: F.resting_heart_rate_figure(
            hl["resting_heart_rate"].data,
            unit=hl["resting_heart_rate"].unit,
            target=target_resting_heart_rate,
        ),
    )
    s3.add(
        cfg.enabled("hrv") and "hrv" in hl,
        "hrv",
        lambda: F.hrv_figure(hl["hrv"].data, unit=hl["hrv"].unit),
    )
    s3.add(
        cfg.enabled("sleep") and bool(data.sleep_hours),
        "sleep",
        lambda: F.sleep_figure(data.sleep_hours, data.sleep_onset or None),
    )
    s3.add(
        cfg.enabled("step_count") and "steps" in hl,
        "step-count",
        lambda: F.step_count_figure(hl["steps"].data),
    )
    s3.add(
        cfg.enabled("exercise") and "exercise" in hl,
        "exercise",
        lambda: F.exercise_figure(hl["exercise"].data, target=target_exercise_minutes),
    )
    s3.add(
        cfg.enabled("vo2max") and "vo2max" in hl,
        "vo2max",
        lambda: F.vo2max_figure(hl["vo2max"].data, unit=hl["vo2max"].unit),
    )

    # --- Section 4: Cross-signal analysis --------------------------------------
    s4 = _SectionBuilder(4, "Cross-Signal Analysis", _CROSS_SIGNAL_INTRO, note)
    s4.section.stats = _cross_stats(data, cfg)
    enough = len(data.signals) >= 2
    s4.add(
        enough and cfg.enabled("correlation_matrix"),
        "correlation-matrix",
        lambda: F.correlation_matrix_figure(data.signals),
    )
    s4.add(
        enough and cfg.enabled("top_correlations"),
        "top-correlations",
        lambda: F.top_pairs_figure(data.signals, cfg.excluded_correlation_pairs),
    )
    s4.add(
        enough and cfg.enabled("highlighted_correlations"),
        "highlighted-correlations",
        lambda: F.highlighted_correlations_figure(data.signals),
    )

    overview = Section(number=0, title="Overview", intro=_EXEC_SUMMARY)
    sections = [overview] + [
        s.section for s in (s1, s2, s3, s4) if s.section.figures or s.section.notes
    ]
    return Report(
        title=data.label,
        start=data.start,
        end=data.end,
        sections=sections,
        kind="Demo report" if synthetic else "Personal report",
        synthetic=synthetic,
        persona=persona,
    )


def _word_counts(entries: list[JournalEntry]) -> list[tuple[date_type, int]]:
    from egon.analytics.word_count import word_counts_by_day

    return word_counts_by_day(entries)


def _frequent(entries: list[JournalEntry]) -> list[tuple[str, int]]:
    from egon.analytics.words import frequent_words

    return frequent_words(entries)


def _pronoun_ratio(entries: list[JournalEntry]) -> list[tuple[date_type, float]]:
    from egon.analytics.pronoun_ratio import pronoun_ratio_by_day

    return pronoun_ratio_by_day(entries)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_full_report(
    *,
    journal_entries: list[JournalEntry],
    xml_path: Path | None,
    start: date_type,
    end: date_type,
    label: str,
    target_body_mass: float | None = None,
    target_lean_body_mass: float | None = None,
    target_resting_heart_rate: float | None = None,
    target_exercise_minutes: float | None = None,
    output_path: Path,
    config: ReportConfig | None = None,
    cache_dir: Path | None = None,
) -> Path:
    """Collect all data for the period and write the full HTML report to *output_path*.

    Model scores and LLM text are cached in ``<output dir>/.cache/<label>/``
    (or *cache_dir*); delete those files to force re-scoring.
    """
    cfg = config if config is not None else load_report_config()
    data = collect_report_data(
        journal_entries=journal_entries,
        xml_path=xml_path,
        start=start,
        end=end,
        label=label,
        cache_dir=cache_dir or output_path.parent / ".cache" / label,
        config=cfg,
    )
    report = build_full_report(
        data,
        config=cfg,
        target_body_mass=target_body_mass,
        target_lean_body_mass=target_lean_body_mass,
        target_resting_heart_rate=target_resting_heart_rate,
        target_exercise_minutes=target_exercise_minutes,
    )
    return write_report(report, output_path)
