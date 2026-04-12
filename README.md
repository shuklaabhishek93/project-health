# project-health
To monitor and analyze daily health and fitness routine

## Features

- **Health Habits Tracking** - Water intake, sleep, steps, diet, meditation, and more
- **Workout Logging** - 15+ workout types with duration, intensity, distance, sets/reps
- **Calorie Burn Calculation** - MET-based calorie estimation with age adjustment
- **Heart Rate Monitoring** - Track readings with zone analysis (fat burn, cardio, aerobic, etc.)
- **Daily Summary** - Comprehensive report with health score and age-based insights
- **Age-Based Recommendations** - Personalized exercise, sleep, and hydration targets

### Data Source Integrations

- **Apple Health (iPhone)** - Import steps, sleep, heart rate, energy, distance, flights climbed, and workouts from your iPhone Health app XML export
- **Apple Fitness** - Workout sessions recorded via Apple Fitness are imported through the Health export (they are embedded in the same XML)
- **Strava** - Connect via OAuth2 to import runs, rides, swims, and other activities with distance, duration, calories, and heart rate data

## How to Run

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.10+.

## Project Structure

```
project-health/
├── main.py                              # CLI entry point
├── health_tracker/
│   ├── __init__.py
│   ├── models.py                        # Data models (UserProfile, Workout, etc.)
│   ├── calculator.py                    # Calorie burn & heart rate calculations
│   ├── storage.py                       # JSON-based data persistence
│   ├── summary.py                       # Daily summary generation
│   └── integrations/
│       ├── __init__.py
│       ├── apple_health.py              # Apple Health XML export parser
│       ├── strava.py                    # Strava API (OAuth2) integration
│       └── sync.py                      # Merge logic to avoid duplicates
├── data/                                # Auto-created for storing records
└── requirements.txt
```

## Usage

### Manual Entry
1. Run `python main.py` and set up your profile (age, weight, height, gender)
2. Log daily health habits (water, sleep, steps, etc.)
3. Log workouts with type, duration, and intensity
4. Record heart rate readings throughout the day
5. View your daily summary with calorie totals and health score

### Import from Apple Health
1. On iPhone: Health app > Profile > Export All Health Data
2. Transfer and unzip the export on your computer
3. In the app: choose option 4 (Import from Apple Health)
4. Provide the path to `export.xml`
5. Choose date range (all, specific date, or range)

### Import from Strava
1. Create a Strava API app at https://www.strava.com/settings/api
2. Set Authorization Callback Domain to `localhost`
3. In the app: choose option 5 (Import from Strava)
4. Enter your Client ID and Client Secret
5. Authorize in browser (opens automatically)
6. Choose date range to import

### Deduplication
Data from all sources is merged intelligently:
- Workouts are deduplicated by source ID (re-importing won't create duplicates)
- Steps and distances use the highest value across sources
- Manually-entered data (water, diet, meditation) is never overwritten by imports
- Device-reported calories are shown alongside estimated values in summaries
