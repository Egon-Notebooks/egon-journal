# Reports

All reports are generated as PDFs (or other matplotlib-supported formats) and saved to subdirectories under `reports/`.

---

## Word count

Plots daily word count across all journal entries as a bar chart.

```bash
# Uses EGON_JOURNAL_DIR from .env
uv run egon report-word-count

# Specify the journal directory explicitly
uv run egon report-word-count --journal-dir ~/my-egon-graph/journal

# Specify a period
uv run egon report-word-count --period week       # current ISO week
uv run egon report-word-count --period month      # current month
uv run egon report-word-count --period quarter    # current quarter
uv run egon report-word-count --period year       # current year
uv run egon report-word-count --period all-time   # all entries (default)

# Specify a named period
uv run egon report-word-count --for 2025
uv run egon report-word-count --for 2026-02
uv run egon report-word-count --for 2026-W14
uv run egon report-word-count --for 2026-Q2

# Change the output path
uv run egon report-word-count --output ~/my-reports/word-count.pdf
```

Default output: `./reports/word_count/word-count.pdf`

---

## Sentiment

Plots daily sentiment score (VADER, range −1 to +1) as a scatter/line chart with a neutral band.

```bash
uv run egon report-sentiment

uv run egon report-sentiment --journal-dir ~/my-egon-graph/journal
uv run egon report-sentiment --period month
uv run egon report-sentiment --for 2026-Q1
uv run egon report-sentiment --output ~/my-reports/sentiment.pdf
```

Default output: `./reports/sentiment/sentiment.pdf`

---

## Word cloud

Generates a word cloud image from all journal entries in the selected period.

```bash
uv run egon report-wordcloud

uv run egon report-wordcloud --journal-dir ~/my-egon-graph/journal
uv run egon report-wordcloud --period month
uv run egon report-wordcloud --for 2026
uv run egon report-wordcloud --output ~/my-reports/wordcloud.pdf
```

Default output: `./reports/wordcloud/wordcloud.pdf`

---

## Weight

Plots daily body weight (kg) from an Apple Health export as a line chart.
Sudden changes in weight are particularly indicative of mental health risk.

```bash
# Uses EGON_APPLE_HEALTH_XML from .env
uv run egon report-weight

uv run egon report-weight --period month
uv run egon report-weight --for 2026-Q1
uv run egon report-weight --output ~/my-reports/weight.pdf
```

Default output: `./reports/weight/weight.pdf`

---

## Resting heart rate

Plots daily resting heart rate (bpm) from an Apple Health export as a line chart.

```bash
uv run egon report-resting-heart-rate

uv run egon report-resting-heart-rate --period month
uv run egon report-resting-heart-rate --for 2026
uv run egon report-resting-heart-rate --output ~/my-reports/rhr.pdf
```

Default output: `./reports/resting_heart_rate/resting-heart-rate.pdf`

---

## Heart rate variability (HRV)

Plots daily HRV (ms, SDNN) from an Apple Health export as a line chart.
HRV is associated with stress levels.

```bash
uv run egon report-hrv

uv run egon report-hrv --period month
uv run egon report-hrv --for 2026-W14
uv run egon report-hrv --output ~/my-reports/hrv.pdf
```

Default output: `./reports/hrv/hrv.pdf`

---

## Step count

Plots daily total steps from an Apple Health export as a bar chart with a 10,000-step reference line.

```bash
uv run egon report-step-count

uv run egon report-step-count --period month
uv run egon report-step-count --for 2026-Q1
uv run egon report-step-count --output ~/my-reports/steps.pdf
```

Default output: `./reports/step_count/step-count.pdf`

---

## VO2 max

Plots daily mean VO2 max (mL/min/kg) from an Apple Health export as a line chart with a period average.

```bash
uv run egon report-vo2max

uv run egon report-vo2max --period month
uv run egon report-vo2max --for 2026-Q1
uv run egon report-vo2max --output ~/my-reports/vo2max.pdf
```

Default output: `./reports/vo2max/<period>.pdf`

---

## Sleep

Plots nightly time asleep (hours) from an Apple Health export as a bar chart with 7h/9h reference lines.
Sleep quality is strongly associated with mental health symptoms.
Sleep onset rhythmicity--whether you sleep at the same time every day--has been shown to be associated with depressive symptoms.

```bash
uv run egon report-sleep

uv run egon report-sleep --period month
uv run egon report-sleep --for 2026-Q1
uv run egon report-sleep --output ~/my-reports/sleep.pdf
```

Default output: `./reports/sleep/sleep.pdf`

---

## Common options

All `report-*` commands share these options:

- **`--period`** — Relative period: `week`, `month`, `quarter`, `year`, `all-time`
- **`--for`** — Named period: `2025`, `2026-02`, `2026-W14`, `2026-Q2`
- **`--output`** — Output file path (matplotlib formats: `.pdf`, `.png`, `.svg`)

Health reports (`weight`, `resting-heart-rate`, `hrv`, `sleep`, `step-count`) also accept:

- **`--xml`** — Apple Health export path; falls back to `EGON_APPLE_HEALTH_XML` in `.env`

Journal reports (`word-count`, `sentiment`, `wordcloud`) also accept:

- **`--journal-dir`** — Override `EGON_JOURNAL_DIR` from `.env`
