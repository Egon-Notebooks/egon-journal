# Reports

All reports are generated as PDFs (or other matplotlib-supported formats) and saved to subdirectories under `reports/`.

---

## Full report

Generates a single multi-section PDF covering all enabled analyses.

```bash
uv run egon report

uv run egon report --period month
uv run egon report --for 2026-Q1
uv run egon report --output ~/my-reports/full-report.pdf
```

Default output: `./reports/full_report/<period>.pdf`

Which analyses appear in the report is controlled by `egon.toml` in the project root.
All analyses default to enabled except `wordcloud` (opt-in) and `topics` (requires the `topics` extra).
Omit a key to keep the default.

```toml
# egon.toml
[report.analyses]
wordcloud     = false   # decorative; opt in if you want it
topics        = true    # BERTopic (requires uv sync --extra topics)
pronoun_ratio = true
emotion       = true
exercise      = true
# ... any subset; omitted keys use their defaults
```

---

## Section 1 — Journal insights

### Word count

Plots daily word count across all journal entries as a bar chart.

```bash
uv run egon report-word-count

uv run egon report-word-count --period month
uv run egon report-word-count --for 2026-Q1
uv run egon report-word-count --output ~/my-reports/word-count.pdf
```

Default output: `./reports/word_count/<period>.pdf`

---

### Word cloud

Generates a word cloud image from all journal entries in the selected period.
Disabled by default in the full report (`egon.toml`: `wordcloud = false`).

```bash
uv run egon report-wordcloud

uv run egon report-wordcloud --period month
uv run egon report-wordcloud --for 2026
uv run egon report-wordcloud --output ~/my-reports/wordcloud.pdf
```

Default output: `./reports/wordcloud/<period>.pdf`

---

### Topics (BERTopic)

Discovers latent themes in the journal corpus. Produces two figures:
a horizontal bar chart of topics by size (with top keywords as labels) and
a stacked area chart of topic prevalence by calendar month.

On Linux / Apple Silicon / Windows, uses BERTopic with sentence-transformers embeddings:

```bash
uv sync --extra topics
```

On Intel Mac, uses pure-sklearn NMF automatically via `.venv-limbic` (no extra step needed beyond `bash scripts/setup_limbic.sh`).

```bash
uv run egon report-topics

uv run egon report-topics --period month
uv run egon report-topics --for 2026-Q1
uv run egon report-topics --output-dir ~/my-reports/topics/
```

Default output: `./reports/topics/<period>_summary.pdf` and `<period>_timeline.pdf`

---

### Cognitive distortions

Detects cognitive distortions in journal text using
`amedvedev/bert-tiny-cognitive-bias` — a BERT-tiny classifier trained on eight
categories: no distortion · personalization · emotional reasoning · overgeneralizing ·
labeling · should statements · catastrophizing · reward fallacy.

Produces a two-panel figure: a daily distortion signal line (1 − no-distortion
probability) and a stacked area chart showing the composition of distorted writing
by type over the period.

Requires the `limbic` setup (same model runtime):

```bash
bash scripts/setup_limbic.sh   # Intel Mac (once)
uv sync --extra limbic         # Linux / Apple Silicon / Windows
```

```bash
uv run egon report-cognitive-bias

uv run egon report-cognitive-bias --period month
uv run egon report-cognitive-bias --for 2026-Q1
uv run egon report-cognitive-bias --output ~/my-reports/cognitive-bias.pdf
```

Default output: `./reports/cognitive_bias/<period>.pdf`

---

## Section 2 — Personality & affective patterns

### Sentiment

Plots daily sentiment score (VADER, range −1 to +1) as a scatter/line chart with a neutral band.

```bash
uv run egon report-sentiment

uv run egon report-sentiment --period month
uv run egon report-sentiment --for 2026-Q1
uv run egon report-sentiment --output ~/my-reports/sentiment.pdf
```

Default output: `./reports/sentiment/<period>.pdf`

---

### Emotion

Plots daily emotion profile derived from journal text using
`j-hartmann/emotion-english-distilroberta-base` — a DistilRoBERTa model fine-tuned
on six emotion datasets. Produces a two-panel figure: a stacked area chart of all
seven emotion probabilities and a joy-vs-sadness overlay.

Seven emotions: anger · disgust · fear · joy · neutral · sadness · surprise.

Requires the same `limbic` setup (same model runtime):

```bash
bash scripts/setup_limbic.sh   # Intel Mac (once)
uv sync --extra limbic         # Linux / Apple Silicon / Windows
```

```bash
uv run egon report-emotion

uv run egon report-emotion --period month
uv run egon report-emotion --for 2026-Q1
uv run egon report-emotion --output ~/my-reports/emotion.pdf
```

Default output: `./reports/emotion/<period>.pdf`

---

### Big Five personality traits

Scores each journal entry on the Big Five personality dimensions (O, C, E, A, N)
using a DistilBERT regression model. Produces five stacked subplots — one per trait —
with the period average annotated to the right of each panel.

Requires the `limbic` optional dependency group (downloads ~270 MB on first run):

```bash
bash scripts/setup_limbic.sh   # Intel Mac (once)
uv sync --extra limbic         # Linux / Apple Silicon / Windows
```

```bash
uv run egon report-bigfive

uv run egon report-bigfive --period month
uv run egon report-bigfive --for 2026-Q1
uv run egon report-bigfive --output ~/my-reports/bigfive.pdf
```

Default output: `./reports/bigfive/<period>.pdf`

---

### MBTI personality dimensions

Classifies each journal entry as one of 16 MBTI types and decomposes the result
into 4 binary dimensions (E/I, N/S, T/F, J/P).
Produces four stacked subplots — one per dimension — with the dominant pole and proportion annotated to the right.

Requires the same `limbic` setup as Big Five (same `.venv-limbic`).

```bash
uv run egon report-mbti

uv run egon report-mbti --period month
uv run egon report-mbti --for 2026-Q1
uv run egon report-mbti --output ~/my-reports/mbti.pdf
```

Default output: `./reports/mbti/<period>.pdf`

---

## Section 3 — Physiological measures

### Weight

Plots daily body weight (kg) from an Apple Health export as a line chart.
Sudden changes in weight are particularly indicative of mental health risk.

Set an optional target line via `EGON_TARGET_BODY_MASS` in `.env`.

```bash
uv run egon report-weight

uv run egon report-weight --period month
uv run egon report-weight --for 2026-Q1
uv run egon report-weight --output ~/my-reports/weight.pdf
```

Default output: `./reports/weight/<period>.pdf`

---

### Resting heart rate

Plots daily resting heart rate (bpm) from an Apple Health export as a line chart.

Set an optional target line via `EGON_TARGET_RESTING_HEART_RATE` in `.env`.

```bash
uv run egon report-resting-heart-rate

uv run egon report-resting-heart-rate --period month
uv run egon report-resting-heart-rate --for 2026
uv run egon report-resting-heart-rate --output ~/my-reports/rhr.pdf
```

Default output: `./reports/resting_heart_rate/<period>.pdf`

---

### Heart rate variability (HRV)

Plots daily HRV (ms, SDNN) from an Apple Health export as a line chart.
HRV is associated with stress levels.

```bash
uv run egon report-hrv

uv run egon report-hrv --period month
uv run egon report-hrv --for 2026-W14
uv run egon report-hrv --output ~/my-reports/hrv.pdf
```

Default output: `./reports/hrv/<period>.pdf`

---

### Sleep

Plots nightly time asleep (hours) from an Apple Health export as a bar chart with 7 h/9 h reference lines.
Sleep quality is strongly associated with mental health symptoms.
Sleep onset rhythmicity — whether you sleep at the same time every day — has been shown to be associated with depressive symptoms.

```bash
uv run egon report-sleep

uv run egon report-sleep --period month
uv run egon report-sleep --for 2026-Q1
uv run egon report-sleep --output ~/my-reports/sleep.pdf
```

Default output: `./reports/sleep/<period>.pdf`

---

### Step count

Plots daily total steps from an Apple Health export as a bar chart with a 10,000-step reference line.

```bash
uv run egon report-step-count

uv run egon report-step-count --period month
uv run egon report-step-count --for 2026-Q1
uv run egon report-step-count --output ~/my-reports/steps.pdf
```

Default output: `./reports/step_count/<period>.pdf`

---

### Exercise time

Plots daily Apple Exercise Time (minutes) from an Apple Health export as a bar chart.
The WHO recommends ≥ 30 minutes of moderate-intensity activity per day (150 min/week);
this is drawn as the default reference line.

Set a custom target via `EGON_TARGET_EXERCISE_MINUTES` in `.env`.

```bash
uv run egon report-exercise

uv run egon report-exercise --period month
uv run egon report-exercise --for 2026-Q1
uv run egon report-exercise --output ~/my-reports/exercise.pdf
```

Default output: `./reports/exercise/<period>.pdf`

---

### VO2 max

Plots daily mean VO2 max (mL/min/kg) from an Apple Health export as a line chart with a period average.

```bash
uv run egon report-vo2max

uv run egon report-vo2max --period month
uv run egon report-vo2max --for 2026-Q1
uv run egon report-vo2max --output ~/my-reports/vo2max.pdf
```

Default output: `./reports/vo2max/<period>.pdf`

---

## Section 4 — Cross-signal analysis

### Correlations

Computes pairwise Pearson correlations across all available journal and health signals,
and saves two figures: a full correlation matrix heatmap and a highlighted top-pairs chart.

Requires at least two signals to be available (any combination of journal directory and
Apple Health export).

```bash
uv run egon report-correlations

uv run egon report-correlations --period month
uv run egon report-correlations --for 2026-Q1
uv run egon report-correlations --output-dir ~/my-reports/correlations/
```

Default output: `./reports/correlations/<period>_matrix.pdf` and `<period>_highlighted.pdf`

---

## Common options

All `report-*` commands share these options:

- **`--period`** — Relative period: `week`, `month`, `quarter`, `year`, `all-time`
- **`--for`** — Named period: `2025`, `2026-02`, `2026-W14`, `2026-Q2`
- **`--output`** — Output file path (matplotlib formats: `.pdf`, `.png`, `.svg`)

Health reports (`weight`, `resting-heart-rate`, `hrv`, `sleep`, `step-count`, `exercise`, `vo2max`) also accept:

- **`--xml`** — Apple Health export path; falls back to `EGON_APPLE_HEALTH_XML` in `.env`

Journal reports (`word-count`, `sentiment`, `wordcloud`, `emotion`) also accept:

- **`--journal-dir`** — Override `EGON_JOURNAL_DIR` from `.env`

`report-correlations` accepts both `--xml` and `--journal-dir`.
