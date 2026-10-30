"""
Figure builders: domain data in, a fully described report Figure out.

Each builder pairs a chart spec with its caption, a "why it matters for
wellbeing" note, a "how to read this" explainer and an accessible data table,
so the single-chart ``report-*`` commands and the full report present every
chart identically.  Figure numbers are assigned by the report that uses them.

The "why it matters" notes summarise well-replicated findings and name a key
source.  They describe associations at population level — they are context
for reflection, not a diagnosis.
"""

from datetime import date as date_type

from egon.analytics.correlation import (
    Signals,
    correlation_matrix,
    highlighted_pairs,
    top_pairs,
)
from egon.analytics.topics import TopicSummary, TopicTimeline
from egon.limbic.bigfive import TRAITS, BigFiveScores
from egon.limbic.cognitive_bias import BIASES, DISTORTION_TYPES, CognitiveBiasScores
from egon.limbic.emotion import EMOTIONS, EmotionScores
from egon.limbic.loneliness import LonelinessScore
from egon.limbic.mbti import DIMENSIONS, MBTIScores, period_type
from egon.limbic.stress import StressScore
from egon.report import theme
from egon.report.charts.affect import cognitive_bias_chart, mbti_chart, sentiment_chart
from egon.report.charts.correlation import (
    correlation_explorer_chart,
    highlighted_pairs_chart,
    top_pairs_chart,
)
from egon.report.charts.emotion import STACK_ORDER, emotion_chart
from egon.report.charts.sleep import format_duration, onset_clock, sleep_chart
from egon.report.charts.text import ranked_bars_chart, topic_timeline_chart
from egon.report.charts.timeseries import (
    daily_series_chart,
    series_summary,
    stacked_series_chart,
)
from egon.report.html import Figure, Stat, Table

Series = list[tuple[date_type, float]]

WHO_DAILY_EXERCISE_MIN = 30
STEPS_REFERENCE = 7_000

_DRAG_TO_ZOOM = "Drag across the chart to zoom into a stretch of time; double-click to reset."


def _table(header: list[str], data: Series, fmt: str) -> Table:
    return Table(header, [[d.isoformat(), f"{v:{fmt}}"] for d, v in data])


# =============================================================================
# Section 1 — Journal insights
# =============================================================================


def word_count_figure(data: list[tuple[date_type, int]], commentary: str = "") -> Figure:
    series = [(d, float(v)) for d, v in data]
    return Figure(
        key="word-count",
        title="How much you wrote",
        caption="Words per journal entry, with a 7-day trailing mean",
        spec=daily_series_chart(series, label="Words", unit="words", color=theme.BLUE, mark="bar"),
        why=(
            "Writing about thoughts and feelings is itself good for wellbeing: expressive-"
            "writing studies find small but consistent benefits for mood and stress "
            "(Pennebaker, 1997; Frattaroli, 2006). How much you write is also a quiet "
            "behavioural signal — withdrawing from routines you value is a common early "
            "sign of low mood, while bursts of writing often accompany periods with a lot to "
            "process."
        ),
        how_to_read=(
            "Each grey bar is one entry; the line is the 7-day average. Gaps are days without "
            "an entry. Look for changes in rhythm rather than the absolute number. " + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", "Words"], series, ",.0f"),
    )


def sentiment_figure(data: Series, commentary: str = "") -> Figure:
    return Figure(
        key="sentiment",
        title="Tone of your writing",
        caption="Daily sentiment (VADER compound score, −1 to +1), with a 7-day trend",
        spec=sentiment_chart(data),
        why=(
            "The emotional tone of the words we choose tracks how we feel. A single negative "
            "day says little; a tone that drifts downward over several weeks is one of the "
            "clearer language-based signals of low mood, and is worth noticing early — when "
            "small changes (sleep, contact with people, activity) are easiest to make."
        ),
        how_to_read=(
            "Blue bars lean positive, terracotta bars negative; the grey band around zero is "
            "neutral. The line is the 7-day average. VADER is a word-list method: it "
            "reads tone, not meaning, so it can miss sarcasm or context. " + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", "Sentiment"], data, "+.2f"),
    )


def pronoun_ratio_figure(data: Series, commentary: str = "") -> Figure:
    return Figure(
        key="pronoun-ratio",
        title="Self-focus in language",
        caption="First-person singular pronouns (I, me, my, mine, myself) as a share of all words",
        spec=daily_series_chart(
            data, label="Pronoun ratio", unit="", color=theme.PLUM, decimals=1, percent=True
        ),
        why=(
            "People who are depressed or distressed tend to use “I”, “me” and “my” more often, "
            "reflecting more self-focused attention and rumination (Pennebaker et al., 2003; "
            "meta-analysis: Edwards & Holtzman, 2017). The effect is small and varies by "
            "person and by what you write about, so your own trend over weeks matters far "
            "more than any comparison with others."
        ),
        how_to_read=(
            "Grey dots are single entries; the line is the 7-day average. A sustained rise "
            "can mean your writing turned inward — sometimes healthy reflection, sometimes "
            "rumination. " + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", "First-person share"], data, ".1%"),
    )


def frequent_words_figure(words: list[tuple[str, int]], commentary: str = "") -> Figure:
    return Figure(
        key="wordcloud",
        title="Words that came up most",
        caption="Most frequent meaningful words across all entries (common words removed)",
        spec=ranked_bars_chart(
            [(w, float(c)) for w, c in words], value_title="Times used", label_limit=200
        ),
        why=(
            "What we repeatedly write about is what occupies our attention. Seeing the "
            "people, places and concerns that dominate a period can make implicit "
            "priorities — or worries — explicit."
        ),
        how_to_read="Longer bars are words you used more often in this period.",
        commentary=commentary,
        table=Table(["Word", "Count"], [[w, str(c)] for w, c in words]),
    )


def topic_summary_figure(topics: TopicSummary, commentary: str = "") -> Figure:
    return Figure(
        key="topic-summary",
        title="Recurring themes",
        caption="Topics discovered in your entries (BERTopic), labelled by their top keywords",
        spec=ranked_bars_chart(
            [(label, float(c)) for label, c in topics], value_title="Entries", color=theme.SAGE
        ),
        why=(
            "Recurring themes show where your mental energy goes. Knowing which areas of life "
            "— work, relationships, health, meaning — fill your journal helps you see "
            "whether your attention matches what you value, and which stressors keep "
            "returning."
        ),
        how_to_read=(
            "Each bar is a theme found automatically by clustering similar entries; bar "
            "length is the number of entries in that theme. Keyword labels are a summary, "
            "not a title — read them as hints."
        ),
        commentary=commentary,
        table=Table(["Topic", "Entries"], [[t, str(c)] for t, c in topics]),
    )


def topic_timeline_figure(
    rows: TopicTimeline, topics: TopicSummary, commentary: str = ""
) -> Figure:
    order = [label for label, _ in topics]
    # Timeline labels use 4 keywords; match them to summary order by prefix.
    timeline_labels = list(dict.fromkeys(t for _, t, _ in rows if t != "other"))
    ordered = sorted(
        timeline_labels,
        key=lambda t: next((i for i, s in enumerate(order) if s.startswith(t)), len(order)),
    )
    return Figure(
        key="topic-timeline",
        title="How themes shifted",
        caption="Entries per theme per month",
        spec=topic_timeline_chart(rows, ordered),
        why=(
            "Themes that grow or fade over months often mark life events — a new job, a "
            "relationship change, an illness. A worry that keeps expanding is worth "
            "addressing directly; a source of meaning that has disappeared may be worth "
            "making room for again."
        ),
        how_to_read=(
            "Each column is a month, split by theme. Click a legend entry to focus on one "
            "theme; “other” collects smaller themes and entries that fit none."
        ),
        commentary=commentary,
        table=Table(["Month", "Topic", "Entries"], [[m, t, str(c)] for m, t, c in rows]),
    )


# =============================================================================
# Section 2 — Personality & affective patterns
# =============================================================================


def stress_figure(data: list[tuple[date_type, StressScore]], commentary: str = "") -> Figure:
    series = [(d, s.stress) for d, s in data]
    return Figure(
        key="stress",
        title="Stress in your writing",
        caption="Daily probability that an entry reads as stressed (DistilBERT, Dreaddit)",
        spec=daily_series_chart(
            series,
            label="Stress",
            unit="",
            color=theme.TERRACOTTA,
            percent=True,
            domain=(0, 1),
            wash=True,
        ),
        why=(
            "Short bursts of stress are normal and even useful. Stress that stays high for "
            "weeks is a major risk factor for anxiety, depression and burnout, and affects "
            "sleep, immunity and heart health. Seeing a sustained rise early gives you room "
            "to recover, set limits or ask for support before it becomes exhausting."
        ),
        how_to_read=(
            "Grey dots are single entries; the line is the 7-day average. Values near 100 % "
            "mean the language strongly resembles stressed writing. Model scores are "
            "estimates from wording and can be wrong. " + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", "Stress probability"], series, ".0%"),
    )


def loneliness_figure(
    data: list[tuple[date_type, LonelinessScore]], commentary: str = ""
) -> Figure:
    series = [(d, s.lonely) for d, s in data]
    return Figure(
        key="loneliness",
        title="Loneliness in your writing",
        caption="Daily probability that an entry expresses loneliness (MentalBERT)",
        spec=daily_series_chart(
            series,
            label="Loneliness",
            unit="",
            color=theme.PLUM,
            percent=True,
            domain=(0, 1),
            wash=True,
        ),
        why=(
            "Feeling disconnected is one of the strongest predictors of depression, and "
            "persistent loneliness is linked to poorer sleep and physical health — the size "
            "of the association with mortality is comparable to well-known risk factors "
            "such as smoking (Holt-Lunstad et al., 2010). Loneliness is about the quality "
            "of connection, not the number of people around you."
        ),
        how_to_read=(
            "Grey dots are single entries; the line is the 7-day average. Watch for "
            "stretches where the line stays high, especially together with lower mood or "
            "higher stress. " + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", "Loneliness probability"], series, ".0%"),
    )


def emotion_figure(data: list[tuple[date_type, EmotionScores]], commentary: str = "") -> Figure:
    order = [EMOTIONS.index(e) for e in STACK_ORDER]
    return Figure(
        key="emotion",
        title="Emotional tone",
        caption=(
            "Share of seven emotions in your writing, 7-day rolling mean · "
            "DistilRoBERTa emotion model (Hartmann et al., 2022)"
        ),
        spec=emotion_chart(data),
        why=(
            "Being able to tell emotions apart — sad versus anxious versus angry, not just "
            "“bad” — is linked to better emotion regulation and resilience (Kashdan, "
            "Barrett & McKnight, 2015). Negative emotions are a normal part of life; what "
            "matters is balance, and whether sadness or fear stays dominant for weeks."
        ),
        how_to_read=(
            "Each band is one emotion's share of the tone of your writing that week. "
            "Positive affect (joy, surprise) sits above the grey neutral band, negative "
            "affect below it, so a widening lower half means heavier weeks. Click a legend "
            "entry to isolate one emotion; hover for exact values."
        ),
        commentary=commentary,
        table=Table(
            ["Date", *STACK_ORDER],
            [[d.isoformat(), *(f"{s[i]:.0%}" for i in order)] for d, s in data],
        ),
    )


def bigfive_figure(data: list[tuple[date_type, BigFiveScores]], commentary: str = "") -> Figure:
    colors = [theme.BLUE, theme.TERRACOTTA, theme.SAGE, theme.OCHRE, theme.PLUM]
    panels = []
    for i, ((_, name), color) in enumerate(zip(TRAITS, colors, strict=True)):
        series = [(d, s[i]) for d, s in data]
        panels.append(
            (
                series,
                {
                    "label": name,
                    "unit": "",
                    "color": color,
                    "decimals": 2,
                    "domain": (0, 1),
                    "height": 120,
                },
            )
        )
    headline = []
    for i, (_, name) in enumerate(TRAITS):
        s = series_summary([(d, sc[i]) for d, sc in data], decimals=2)
        headline.append(Stat(name, s["mean"], "", f"{s['delta']} last vs first fortnight"))
    return Figure(
        key="bigfive",
        headline=headline,
        title="Personality in your writing (Big Five)",
        caption=(
            "Daily scores (0–1) for Openness, Conscientiousness, Extraversion, Agreeableness "
            "and Neuroticism, inferred from your entries"
        ),
        spec=stacked_series_chart(panels),
        why=(
            "The Big Five is the best-supported model of personality. Neuroticism — the "
            "tendency to experience negative emotion — is one of the most robust predictors "
            "of anxiety and depression, while extraversion and conscientiousness relate to "
            "higher wellbeing (Kotov et al., 2010). Scored from writing, these values "
            "reflect your state during this period more than fixed traits, so a shift can "
            "mirror how you have been rather than who you are."
        ),
        how_to_read=(
            "The numbers above are period averages (0–1) with the change from the first to "
            "the last fortnight. One panel per trait below: grey dots are single days, the "
            "line the 7-day average, the dotted line and margin label the period average. "
            "Compare a trait with itself over time, not across traits."
        ),
        commentary=commentary,
        table=Table(
            ["Date", *(name for _, name in TRAITS)],
            [[d.isoformat(), *(f"{v:.2f}" for v in s)] for d, s in data],
        ),
    )


def mbti_figure(data: list[tuple[date_type, MBTIScores]], commentary: str = "") -> Figure:
    mbti, letters = period_type(data)
    headline = [Stat("Type this period", mbti, "", "dominant pole per dimension")] + [
        Stat(label, letter, "", f"on {share:.0%} of days")
        for (_, _, label), (letter, share) in zip(DIMENSIONS, letters, strict=True)
    ]
    return Figure(
        key="mbti",
        headline=headline,
        title="Personality type lean (MBTI)",
        caption="Daily lean between the poles of four MBTI dimensions, inferred from your entries",
        spec=mbti_chart(data),
        why=(
            "MBTI is popular but has limited scientific support — people often get a "
            "different type when re-tested. Treat it as a playful lens rather than a "
            "measurement: it can still prompt useful reflection on whether your writing "
            "turned inward (I) or outward (E), or leaned on thinking (T) versus feeling (F) "
            "during a stressful stretch."
        ),
        how_to_read=(
            "The type above combines the pole that dominated each dimension over the "
            "period. Each panel runs from one pole (bottom) to the other (top); the dotted "
            "midline is a perfect balance, and the margin label shows how often the "
            "dominant pole won."
        ),
        commentary=commentary,
        table=Table(
            ["Date", *(label for _, _, label in DIMENSIONS)],
            [[d.isoformat(), *(f"{v:.2f}" for v in s)] for d, s in data],
        ),
    )


def cognitive_bias_figure(
    data: list[tuple[date_type, CognitiveBiasScores]], commentary: str = ""
) -> Figure:
    return Figure(
        key="cognitive-bias",
        title="Thinking traps",
        caption=(
            "Daily distortion signal (1 − probability of no distortion) and weekly mean "
            "probability of seven cognitive distortions (BERT-tiny classifier)"
        ),
        spec=cognitive_bias_chart(data),
        why=(
            "Cognitive distortions — catastrophizing, “should” statements, labelling "
            "yourself — are habitual ways of thinking that keep anxiety and low mood going. "
            "They are the core target of cognitive behavioural therapy (Beck, 1979), one of "
            "the best-evidenced treatments for depression and anxiety. Noticing which traps "
            "you fall into most is the first step of challenging them."
        ),
        how_to_read=(
            "Top: how much of your writing showed any distortion, as a 7-day average. "
            "Bottom: each row is one distortion type, each column a week; darker cells mean "
            "that distortion was more likely that week. Rows are sorted with the most "
            "common type on top. These are linguistic patterns, not a clinical assessment."
        ),
        commentary=commentary,
        table=Table(
            ["Date", "Distortion signal", *(t.capitalize() for t in DISTORTION_TYPES)],
            [
                [
                    d.isoformat(),
                    f"{s.distortion_score:.0%}",
                    *(f"{s[BIASES.index(t)]:.0%}" for t in DISTORTION_TYPES),
                ]
                for d, s in data
            ],
        ),
    )


# =============================================================================
# Section 3 — Physiological measures
# =============================================================================


def weight_figure(
    data: Series,
    *,
    unit: str = "kg",
    lean_data: Series | None = None,
    target: float | None = None,
    lean_target: float | None = None,
    commentary: str = "",
) -> Figure:
    weight_opts = {
        "label": "Weight",
        "unit": unit,
        "color": theme.BLUE,
        "decimals": 1,
        "target": target,
    }
    if lean_data:
        spec = stacked_series_chart(
            [
                (data, {**weight_opts, "height": 190}),
                (
                    lean_data,
                    {
                        "label": "Lean mass",
                        "unit": unit,
                        "color": theme.SAGE,
                        "decimals": 1,
                        "target": lean_target,
                        "height": 150,
                    },
                ),
            ]
        )
    else:
        spec = daily_series_chart(data, **weight_opts)
    return Figure(
        key="weight",
        title="Body weight",
        caption=f"Daily body weight ({unit})"
        + (" and lean body mass" if lean_data else "")
        + " from Apple Health, with a 7-day trailing mean",
        spec=spec,
        why=(
            "Weight is shaped by mood as much as by diet. A noticeable change in weight or "
            "appetite without trying is one of the recognised signs of depression, and "
            "chronic stress and poor sleep both shift appetite and how the body stores "
            "energy. Sudden changes over a few weeks are more informative than slow drift."
        ),
        how_to_read=(
            "Grey dots are single weigh-ins; the line is the 7-day average, which smooths out "
            "day-to-day water fluctuations." + ("" if lean_data else " " + _DRAG_TO_ZOOM)
        ),
        commentary=commentary,
        table=_table(["Date", f"Weight ({unit})"], data, ".1f"),
    )


def resting_heart_rate_figure(
    data: Series, *, unit: str = "bpm", target: float | None = None, commentary: str = ""
) -> Figure:
    return Figure(
        key="resting-heart-rate",
        title="Resting heart rate",
        caption=f"Daily resting heart rate ({unit}) from Apple Health, with a 7-day trailing mean",
        spec=daily_series_chart(
            data, label="Resting heart rate", unit=unit, color=theme.OXBLOOD, target=target
        ),
        why=(
            "Resting heart rate rises when the body is under strain — from stress, short "
            "sleep, illness, alcohol or overtraining — and falls as fitness improves. A rise "
            "of a few beats per minute above your usual baseline that lasts several days is "
            "a simple, early sign that you may need more recovery."
        ),
        how_to_read=(
            "Grey dots are single days; the line is the 7-day average. Lower is generally "
            "better; compare against your own baseline. " + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", f"Resting HR ({unit})"], data, ".0f"),
    )


def hrv_figure(data: Series, *, unit: str = "ms", commentary: str = "") -> Figure:
    return Figure(
        key="hrv",
        title="Heart rate variability",
        caption=f"Daily HRV (SDNN, {unit}) from Apple Health, with a 7-day trailing mean",
        spec=daily_series_chart(data, label="HRV", unit=unit),
        why=(
            "HRV — the variation in time between heartbeats — reflects how well your nervous "
            "system shifts between “fight or flight” and “rest and digest”. Lower HRV is "
            "associated with stress, anxiety and depression (Kemp et al., 2010), and it "
            "tends to recover with good sleep, regular exercise and lower stress, which "
            "makes it a useful mirror of recovery."
        ),
        how_to_read=(
            "Grey dots are single days; the line is the 7-day average. Higher generally "
            "means better recovery, but HRV varies a lot between people — compare yourself "
            "with yourself. " + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", f"HRV ({unit})"], data, ".0f"),
    )


def hrv_stats(data: Series, unit: str = "ms") -> list[Stat]:
    s = series_summary(data)
    return [
        Stat("HRV, period mean", s["mean"], unit, f"{s['delta']} {unit} last vs first fortnight"),
        Stat("Days measured", str(len(data))),
    ]


def sleep_figure(hours: Series, onset: Series | None = None, commentary: str = "") -> Figure:
    rows = [[d.isoformat(), format_duration(h), ""] for d, h in hours]
    if onset:
        onset_by_day = dict(onset)
        rows = [
            [r[0], r[1], onset_clock(onset_by_day[d]) if d in onset_by_day else ""]
            for r, (d, _) in zip(rows, hours, strict=True)
        ]
    return Figure(
        key="sleep",
        title="Sleep",
        caption="Nightly time asleep from Apple Health"
        + (", and the time you fell asleep" if onset else ""),
        spec=sleep_chart(hours, onset),
        why=(
            "Sleep and mental health work in both directions: insomnia roughly doubles the "
            "risk of later depression (Baglioni et al., 2011), and almost every mental "
            "health difficulty disturbs sleep. Timing matters as well as duration — "
            "irregular sleep schedules are associated with lower mood and wellbeing "
            "(Phillips et al., 2017). Most adults need 7–9 hours."
        ),
        how_to_read=(
            "Top: grey bars are nights, the line the 7-day average; dotted lines mark 7 and "
            "9 hours. "
            + (
                "Bottom: each dot is when you fell asleep (earlier at the top). The shaded "
                "band spans one standard deviation around your average — the narrower it "
                "is, the more regular your bedtime."
                if onset
                else ""
            )
        ),
        commentary=commentary,
        table=Table(["Night of", "Asleep", "Fell asleep"], rows),
    )


def step_count_figure(data: Series, commentary: str = "") -> Figure:
    return Figure(
        key="step-count",
        title="Daily steps",
        caption="Total steps per day from Apple Health, with a 7-day trailing mean",
        spec=daily_series_chart(
            data,
            label="Steps",
            unit="steps",
            color=theme.MOSS,
            mark="bar",
            references=[(STEPS_REFERENCE, "7k")],
        ),
        why=(
            "Everyday movement protects mood: people who walk more have fewer depressive "
            "symptoms, with benefits visible from around 5,000–7,500 steps a day "
            "(Bizzozero et al., 2024). The well-known 10,000 is a marketing number, not a "
            "threshold — any increase from your own baseline counts."
        ),
        how_to_read=(
            "Grey bars are days; the line is the 7-day average. The dotted line marks 7,000 "
            "steps. " + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", "Steps"], data, ",.0f"),
    )


def exercise_figure(data: Series, *, target: float | None = None, commentary: str = "") -> Figure:
    is_custom = target is not None
    goal = target if is_custom else WHO_DAILY_EXERCISE_MIN
    return Figure(
        key="exercise",
        title="Exercise",
        caption="Daily Apple Exercise Time (minutes of brisk activity), with a 7-day trailing mean",
        spec=daily_series_chart(
            data,
            label="Exercise",
            unit="min",
            color=theme.SAGE,
            mark="bar",
            target=goal if is_custom else None,
            references=None if is_custom else [(goal, "WHO 30")],
        ),
        why=(
            "Exercise is one of the most effective self-help tools for mood: in trials it "
            "reduces symptoms of depression about as much as psychotherapy for many people, "
            "with walking, jogging, yoga and strength training all helping (Noetel et al., "
            "2024). The WHO recommends at least 150 minutes of moderate activity a week — "
            "about 30 minutes on most days."
        ),
        how_to_read=(
            "Grey bars are days; the line is the 7-day average. The dotted line marks "
            + ("your target." if is_custom else "the WHO guideline of 30 minutes a day.")
            + " "
            + _DRAG_TO_ZOOM
        ),
        commentary=commentary,
        table=_table(["Date", "Exercise (min)"], data, ".0f"),
    )


def vo2max_figure(data: Series, *, unit: str = "mL/min·kg", commentary: str = "") -> Figure:
    return Figure(
        key="vo2max",
        title="Cardiorespiratory fitness (VO₂ max)",
        caption="VO₂ max estimates from Apple Health, with a 7-day trailing mean",
        spec=daily_series_chart(data, label="VO₂ max", unit=unit, color=theme.OCHRE, decimals=1),
        why=(
            "Higher cardiorespiratory fitness is associated with a lower risk of depression "
            "and anxiety (Kandola et al., 2019) as well as longer life. It changes slowly, "
            "so it is best read over months, as a reflection of sustained activity habits."
        ),
        how_to_read=(
            "Each dot is one estimate (the watch records these during outdoor walks and "
            "runs); the line is the 7-day average. Look at the direction over the period."
        ),
        commentary=commentary,
        table=_table(["Date", f"VO₂ max ({unit})"], data, ".1f"),
    )


# =============================================================================
# Section 4 — Cross-signal analysis
# =============================================================================

_CORRELATION_CAVEAT = (
    "Correlation is not causation, and with many signal pairs some strong-looking "
    "correlations will appear by chance — treat them as ideas to test, not conclusions."
)


def correlation_matrix_figure(signals: Signals, commentary: str = "") -> Figure:
    stats = correlation_matrix(signals)
    return Figure(
        key="correlation-matrix",
        title="How your signals move together",
        caption="Pearson correlation between every pair of daily signals · click a cell to see the pair",
        spec=correlation_explorer_chart(signals, stats),
        why=(
            "Mind and body are one system. General findings — sleep affects mood, exercise "
            "lowers stress — do not hold equally for everyone. Seeing which of your own "
            "signals rise and fall together suggests small personal experiments, such as "
            "protecting sleep before a demanding week. " + _CORRELATION_CAVEAT
        ),
        how_to_read=(
            "Blue cells: both signals tend to be high on the same days. Terracotta: one is "
            "high when the other is low. Faded cells are not statistically significant "
            "(p ≥ 0.05). Only days on which both signals were recorded count. Click any "
            "cell to show that pair's daily values on the right, with a fitted line."
        ),
        commentary=commentary,
        table=Table(
            ["Signal", "vs", "r", "p", "Days"],
            [[s.a, s.b, f"{s.r:+.2f}", f"{s.p:.3f}", str(s.n)] for s in stats],
        ),
    )


def top_pairs_figure(
    signals: Signals,
    exclude_pairs: list[tuple[str, str]] | None = None,
    commentary: str = "",
) -> Figure:
    stats = top_pairs(signals, exclude_pairs=exclude_pairs)
    return Figure(
        key="top-correlations",
        title="Strongest relationships",
        caption="The ten signal pairs with the largest absolute correlation",
        spec=top_pairs_chart(stats),
        why=(
            "The strongest co-movements in your data are the best starting points for "
            "self-experiments: if poor sleep and low mood move together for you, improving "
            "sleep is a promising lever. " + _CORRELATION_CAVEAT
        ),
        how_to_read=(
            "Bars to the right are positive correlations (blue), to the left negative "
            "(terracotta). Faded bars and “n.s.” are not statistically significant. "
            "Near-identical pairs (such as weight and lean mass) are left out; configure "
            "exclusions in egon.toml."
        ),
        commentary=commentary,
        table=Table(
            ["Pair", "r", "p", "Days"],
            [[f"{s.a} ↔ {s.b}", f"{s.r:+.2f}", f"{s.p:.3f}", str(s.n)] for s in stats],
        ),
    )


def highlighted_correlations_figure(signals: Signals, commentary: str = "") -> Figure:
    pairs = highlighted_pairs(signals)
    return Figure(
        key="highlighted-correlations",
        title="Relationships worth watching",
        caption="Signal pairs with well-documented links to mental health",
        spec=highlighted_pairs_chart(signals, pairs),
        why=(
            "These pairs connect body and mind through well-studied routes: sleep and "
            "mood; heart rate variability and resting heart rate as markers of stress "
            "physiology, alongside neuroticism; and physical activity alongside "
            "extraversion and energy. Seeing whether they hold for you turns general "
            "findings into personal ones."
        ),
        how_to_read=(
            "Each dot is one day; the line is a least-squares fit. r ranges from −1 to +1 "
            "(0 = no linear relationship); p below 0.05 means the pattern is unlikely to be "
            "chance alone. A faded line is not statistically significant."
        ),
        commentary=commentary,
        table=Table(
            ["Pair", "r", "p", "Days"],
            [[f"{t}: {s.a} ↔ {s.b}", f"{s.r:+.2f}", f"{s.p:.3f}", str(s.n)] for t, s in pairs],
        ),
    )
