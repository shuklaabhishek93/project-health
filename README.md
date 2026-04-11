# project-health
To monitor and analyze daily health and fitness routine

## Features

- **Health Habits Tracking** - Water intake, sleep, steps, diet, meditation, and more
- **Workout Logging** - 15+ workout types with duration, intensity, distance, sets/reps
- **Calorie Burn Calculation** - MET-based calorie estimation with age adjustment
- **Heart Rate Monitoring** - Track readings with zone analysis (fat burn, cardio, aerobic, etc.)
- **Daily Summary** - Comprehensive report with health score and age-based insights
- **Age-Based Recommendations** - Personalized exercise, sleep, and hydration targets

## How to Run

```bash
python main.py
```

Requires Python 3.10+. No external dependencies needed.

## Project Structure

```
project-health/
├── main.py                    # CLI entry point
├── health_tracker/
│   ├── __init__.py
│   ├── models.py              # Data models (UserProfile, Workout, etc.)
│   ├── calculator.py          # Calorie burn & heart rate calculations
│   ├── storage.py             # JSON-based data persistence
│   └── summary.py             # Daily summary generation
├── data/                      # Auto-created for storing records
└── requirements.txt
```

## Usage

1. Run `python main.py` and set up your profile (age, weight, height, gender)
2. Log daily health habits (water, sleep, steps, etc.)
3. Log workouts with type, duration, and intensity
4. Record heart rate readings throughout the day
5. View your daily summary with calorie totals and health score
