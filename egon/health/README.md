# egon/health — Apple Health integration

Parses an Apple Health `export.xml` file and provides per-metric data for report generation.

## How to export your data

1. Open the **Health** app on your iPhone.
2. Tap your profile picture → **Export All Health Data**.
3. Share the resulting `.zip` file to your Mac (AirDrop, Files, etc.).
4. Unzip it — you need `apple_health_export/export.xml`.
5. Set `EGON_APPLE_HEALTH_XML` in your `.env` to the full path of that file.

The export is a point-in-time snapshot. Re-export whenever you want fresh data.

---

## Available metrics

Apple Health records dozens of metrics.
The table below lists the ones most commonly present in an export.
The **Metric name** column is the string returned after the `HKQuantityTypeIdentifier` / `HKCategoryTypeIdentifier` prefix is stripped — this is what `load_records()` uses as the dict key.

### Body metrics

| Metric name | Unit | Description |
|---|---|---|
| `BodyMass` | kg or lb | Body weight (scale or manual entry) |
| `BodyMassIndex` | count | BMI |
| `BodyFatPercentage` | % | Body fat percentage |
| `LeanBodyMass` | kg or lb | Lean body mass |
| `Height` | m or in | Height |
| `WaistCircumference` | m or in | Waist circumference |

### Heart & cardiovascular

| Metric name | Unit | Description |
|---|---|---|
| `RestingHeartRate` | count/min | Resting heart rate (daily Apple Watch reading) |
| `HeartRate` | count/min | Instantaneous heart rate samples |
| `HeartRateVariabilitySDNN` | ms | HRV — standard deviation of NN intervals |
| `WalkingHeartRateAverage` | count/min | Average heart rate while walking |
| `BloodPressureSystolic` | mmHg | Systolic blood pressure |
| `BloodPressureDiastolic` | mmHg | Diastolic blood pressure |
| `VO2Max` | mL/min·kg | Cardio fitness (Apple Watch estimate) |

### Activity

| Metric name | Unit | Description |
|---|---|---|
| `StepCount` | count | Steps taken |
| `DistanceWalkingRunning` | km or mi | Walking and running distance |
| `DistanceCycling` | km or mi | Cycling distance |
| `DistanceSwimming` | km or mi | Swimming distance |
| `ActiveEnergyBurned` | kcal | Active calories burned |
| `BasalEnergyBurned` | kcal | Resting calories burned |
| `AppleExerciseTime` | min | Exercise minutes |
| `AppleStandHour` | count | Stand hours |
| `FlightsClimbed` | count | Flights of stairs climbed |
| `SwimmingStrokeCount` | count | Swimming stroke count |

### Sleep

| Metric name | Unit | Description |
|---|---|---|
| `SleepAnalysis` | — | Sleep stages (category type — value is 0/1/2/3) |

### Respiratory & oxygen

| Metric name | Unit | Description |
|---|---|---|
| `RespiratoryRate` | count/min | Breaths per minute |
| `OxygenSaturation` | % | Blood oxygen saturation (SpO₂) |

### Nutrition

| Metric name | Unit | Description |
|---|---|---|
| `DietaryEnergyConsumed` | kcal | Calories consumed |
| `DietaryProtein` | g | Protein |
| `DietaryCarbohydrates` | g | Carbohydrates |
| `DietaryFatTotal` | g | Total fat |
| `DietaryFiber` | g | Dietary fibre |
| `DietaryWater` | mL | Water intake |
| `DietaryCaffeine` | mg | Caffeine intake |

### Mindfulness

| Metric name | Unit | Description |
|---|---|---|
| `MindfulSession` | — | Mindfulness / meditation sessions (category type) |

---

## Notes

- Not all metrics are present in every export — it depends on which devices and apps you use.
- Run `uv run egon report-weight` (or any health report) to see exactly which metrics are in your export.
- `load_records()` skips non-numeric values silently, so category types like `SleepAnalysis` and `MindfulSession` require separate handling (planned for a future report).
- Two aggregation helpers are available: `daily_mean()` (for rates and measurements) and `daily_sum()` (for counts and distances).
