# project-health
To monitor and analyze daily health and fitness routine

## Features

- **Health Habits Tracking** - Water intake, sleep, steps, diet, meditation, and more
- **Workout Logging** - 15+ workout types with duration, intensity, distance, sets/reps
- **Calorie Burn Calculation** - MET-based calorie estimation with age adjustment
- **Heart Rate Monitoring** - Track readings with zone analysis (fat burn, cardio, aerobic, etc.)
- **Daily Summary** - Comprehensive report with health score and age-based insights
- **Age-Based Recommendations** - Personalized exercise, sleep, and hydration targets
- **Automatic Daily Sync** - Hands-free import from all sources via background daemon

### Data Source Integrations

- **Apple Health (iPhone)** - Import steps, sleep, heart rate, energy, distance, flights climbed, and workouts from your iPhone Health app XML export
- **Apple Fitness** - Workout sessions recorded via Apple Fitness are imported through the Health export (they are embedded in the same XML)
- **Strava** - Connect via OAuth2 to import runs, rides, swims, and other activities with distance, duration, calories, and heart rate data

### Automatic Daily Sync (No Human Intervention)

- **Apple Health/Fitness** - An iOS Shortcut + Personal Automation queries HealthKit daily and pushes data to the tracker's HTTP server automatically
- **Apple Health XML Watcher** - Folder watcher monitors a directory (e.g., iCloud Drive) for new Health export files and imports them automatically
- **Strava** - Background scheduler polls the Strava API daily at a configured time for new activities

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
│   ├── __main__.py                      # python -m health_tracker (runs daemon)
│   ├── models.py                        # Data models (UserProfile, Workout, etc.)
│   ├── calculator.py                    # Calorie burn & heart rate calculations
│   ├── storage.py                       # JSON-based data persistence
│   ├── summary.py                       # Daily summary generation
│   ├── auto_sync.py                     # Auto-sync daemon orchestrator
│   └── integrations/
│       ├── __init__.py
│       ├── apple_health.py              # Apple Health XML export parser
│       ├── apple_health_server.py       # HTTP server for iOS Shortcut push
│       ├── folder_watcher.py            # Watch folder for Health exports
│       ├── shortcut_generator.py        # iOS Shortcut setup guide generator
│       ├── strava.py                    # Strava API (OAuth2) integration
│       └── sync.py                      # Merge logic to avoid duplicates
├── data/                                # Auto-created for storing records
│   ├── sync_config.json                 # Auto-sync configuration
│   └── auto_sync.log                    # Sync operation log
└── requirements.txt
```

## Usage

### Manual Entry
1. Run `python main.py` and set up your profile (age, weight, height, gender)
2. Log daily health habits (water, sleep, steps, etc.)
3. Log workouts with type, duration, and intensity
4. Record heart rate readings throughout the day
5. View your daily summary with calorie totals and health score

### Import from Apple Health (Manual)
1. On iPhone: Health app > Profile > Export All Health Data
2. Transfer and unzip the export on your computer
3. In the app: choose option 4 (Import from Apple Health)
4. Provide the path to `export.xml`
5. Choose date range (all, specific date, or range)

### Import from Strava (Manual)
1. Create a Strava API app at https://www.strava.com/settings/api
2. Set Authorization Callback Domain to `localhost`
3. In the app: choose option 5 (Import from Strava)
4. Enter your Client ID and Client Secret
5. Authorize in browser (opens automatically)
6. Choose date range to import

### Automatic Daily Sync (Hands-Free)

Set up once, then data flows automatically every day:

#### Step 1: Start the Auto-Sync Daemon
```
python main.py → Option 12 → Start Auto-Sync Daemon
```

Or run directly:
```bash
python -m health_tracker.auto_sync
```

#### Step 2: Set Up Apple Health Auto-Export (iPhone)

The app generates complete iOS Shortcut instructions:
```
python main.py → Option 12 → View iOS Shortcut Setup Guide
```

Summary of what happens:
1. You create an iOS Shortcut that reads HealthKit data (steps, HR, sleep, workouts, etc.)
2. The Shortcut sends the data via HTTP POST to your computer
3. You attach a **Personal Automation** (daily at 11 PM) so it runs without you touching anything
4. The daemon receives the data, merges it, and stores it

#### Step 3: Set Up Strava Auto-Sync
```
python main.py → Option 12 → Configure Strava Scheduler
```

Set the daily sync time (default: 11:00 PM). The daemon fetches new activities automatically.

#### Step 4: (Optional) Set Up Folder Watcher
```
python main.py → Option 12 → Configure Folder Watcher
```

Point it at a synced folder (iCloud Drive, Dropbox). Drop an Apple Health export ZIP/XML into the folder from any device — it gets imported automatically.

### Deduplication
Data from all sources is merged intelligently:
- Workouts are deduplicated by source ID (re-importing won't create duplicates)
- Steps and distances use the highest value across sources
- Manually-entered data (water, diet, meditation) is never overwritten by imports
- Device-reported calories are shown alongside estimated values in summaries
