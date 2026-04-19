"""Health and Workout Tracker - CLI Application."""

import os
import sys
from datetime import date, timedelta

from health_tracker.models import (
    UserProfile,
    HealthHabit,
    Workout,
    HeartRateEntry,
    DailyRecord,
)
from health_tracker.calculator import get_age_based_recommendations
from health_tracker.storage import (
    save_profile,
    load_profile,
    save_daily_record,
    load_daily_record,
    list_all_records,
)
from health_tracker.summary import generate_daily_summary
from health_tracker.integrations.sync import sync_imported_records


def get_input(prompt: str, type_fn=str, default=None):
    """Get user input with type conversion and optional default."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"  {prompt}{suffix}: ").strip()
        if not value and default is not None:
            return default
        try:
            return type_fn(value)
        except (ValueError, TypeError):
            print(f"  Invalid input. Please enter a valid {type_fn.__name__}.")


def setup_profile() -> UserProfile:
    """Set up or update user profile."""
    print("\n" + "=" * 50)
    print("  USER PROFILE SETUP")
    print("=" * 50)

    existing = load_profile()
    if existing:
        print(f"\n  Current profile: {existing.name}, Age {existing.age}")
        update = input("  Update profile? (y/n): ").strip().lower()
        if update != "y":
            return existing

    name = get_input("Name", str)
    age = get_input("Age", int)
    weight = get_input("Weight (kg)", float)
    height = get_input("Height (cm)", float)
    gender = get_input("Gender (male/female)", str)

    profile = UserProfile(
        name=name,
        age=age,
        weight_kg=weight,
        height_cm=height,
        gender=gender,
    )
    save_profile(profile)
    print(f"\n  Profile saved! BMI: {profile.bmi} | Max HR: {profile.max_heart_rate} bpm")
    return profile


def log_health_habits(today: str) -> HealthHabit:
    """Log daily health habits."""
    print("\n" + "-" * 50)
    print("  LOG HEALTH HABITS")
    print("-" * 50)

    return HealthHabit(
        date=today,
        sleep_hours=get_input("Sleep last night (hours)", float, 0.0),
        steps=get_input("Steps today", int, 0),
        fruits_vegetables_servings=get_input("Fruit/vegetable servings", int, 0),
        meditation_minutes=get_input("Meditation (minutes)", int, 0),
        alcohol_drinks=get_input("Alcoholic drinks", int, 0),
        smoking=get_input("Did you smoke? (yes/no)", str, "no").lower() in ("yes", "y"),
        notes=get_input("Any notes", str, ""),
    )


def log_workout(today: str) -> Workout:
    """Log a workout session."""
    print("\n  Available workout types:")
    types = ["running", "cycling", "swimming", "weightlifting", "yoga",
             "walking", "hiit", "dancing", "jump_rope", "rowing",
             "elliptical", "stair_climbing", "boxing", "pilates", "stretching"]
    for i, t in enumerate(types, 1):
        print(f"    {i:2}. {t.replace('_', ' ').title()}")

    workout_type = get_input("Workout type", str)
    duration = get_input("Duration (minutes)", int)
    intensity = get_input("Intensity (light/moderate/vigorous)", str, "moderate")

    workout = Workout(
        date=today,
        workout_type=workout_type.lower().replace(" ", "_"),
        duration_minutes=duration,
        intensity=intensity.lower(),
    )

    # Optional fields based on workout type
    if workout_type in ("running", "cycling", "swimming", "walking", "rowing"):
        dist = get_input("Distance in miles (0 to skip)", float, 0.0)
        if dist > 0:
            workout.distance_km = dist * 1.60934

    if workout_type in ("weightlifting",):
        workout.sets = get_input("Number of sets", int, 0)
        workout.reps = get_input("Reps per set", int, 0)
        workout.weight_lifted_kg = get_input("Weight lifted (kg)", float, 0.0)

    workout.notes = get_input("Workout notes", str, "")
    return workout


def log_heart_rate(today: str) -> HeartRateEntry:
    """Log a heart rate reading."""
    print("\n  Context options: resting, during_workout, post_workout, morning, evening")

    return HeartRateEntry(
        date=today,
        time=get_input("Time (HH:MM)", str),
        heart_rate_bpm=get_input("Heart rate (bpm)", int),
        context=get_input("Context", str, "resting"),
    )


def view_summary(profile: UserProfile, record_date: str):
    """View daily summary for a specific date."""
    record = load_daily_record(record_date)
    if not record:
        print(f"\n  No record found for {record_date}")
        return

    summary = generate_daily_summary(profile, record)
    print(summary)
    save_daily_record(record)  # Save updated calorie totals


def import_apple_health_data():
    """Import data from Apple Health XML export."""
    from health_tracker.integrations.apple_health import import_apple_health

    print("\n" + "=" * 50)
    print("  IMPORT FROM APPLE HEALTH")
    print("=" * 50)
    print("\n  How to export your Apple Health data:")
    print("    1. Open 'Health' app on iPhone")
    print("    2. Tap your profile picture (top right)")
    print("    3. Tap 'Export All Health Data'")
    print("    4. Unzip the file to get export.xml")
    print()

    xml_path = get_input("Path to export.xml", str)

    if not os.path.exists(xml_path):
        print(f"\n  ERROR: File not found: {xml_path}")
        return

    print("\n  Date range options:")
    print("    1. Import all data")
    print("    2. Import specific date")
    print("    3. Import date range")
    range_choice = get_input("Choose (1-3)", str, "1")

    date_filter = None
    start_date = None
    end_date = None

    if range_choice == "2":
        date_filter = get_input("Date (YYYY-MM-DD)", str)
    elif range_choice == "3":
        start_date = get_input("Start date (YYYY-MM-DD)", str)
        end_date = get_input("End date (YYYY-MM-DD)", str)

    imported = import_apple_health(
        xml_path,
        date_filter=date_filter,
        start_date=start_date,
        end_date=end_date,
    )

    if imported:
        print("\n  Syncing imported data with local records...")
        updated, created = sync_imported_records(imported)
        print(f"  Done! Days updated: {updated}, Days created: {created}")
    else:
        print("\n  No data found for the selected date range.")


def import_strava_data():
    """Import data from Strava."""
    from health_tracker.integrations.strava import (
        authorize_strava,
        load_strava_token,
        import_strava,
    )

    print("\n" + "=" * 50)
    print("  IMPORT FROM STRAVA")
    print("=" * 50)

    # Check for existing token
    token_data = load_strava_token()

    if not token_data:
        print("\n  No Strava connection found. Let's set it up.")
        print("\n  You need a Strava API application:")
        print("    1. Go to https://www.strava.com/settings/api")
        print("    2. Create an application")
        print("    3. Set 'Authorization Callback Domain' to 'localhost'")
        print()

        client_id = get_input("Strava Client ID", str)
        client_secret = get_input("Strava Client Secret", str)

        token_data = authorize_strava(client_id, client_secret)
        if not token_data:
            print("\n  Authorization failed. Please try again.")
            return

    access_token = token_data["access_token"]

    print("\n  Date range options:")
    print("    1. Last 7 days")
    print("    2. Last 30 days")
    print("    3. Specific date")
    print("    4. Custom date range")
    print("    5. All activities")
    range_choice = get_input("Choose (1-5)", str, "1")

    today = date.today()
    date_filter = None
    start_date = None
    end_date = None

    if range_choice == "1":
        start_date = (today - timedelta(days=7)).isoformat()
    elif range_choice == "2":
        start_date = (today - timedelta(days=30)).isoformat()
    elif range_choice == "3":
        date_filter = get_input("Date (YYYY-MM-DD)", str)
    elif range_choice == "4":
        start_date = get_input("Start date (YYYY-MM-DD)", str)
        end_date = get_input("End date (YYYY-MM-DD)", str)
    # Option 5: no filters, import all

    fetch_hr = get_input("Fetch detailed heart rate data? (yes/no)", str, "yes").lower() in ("yes", "y")

    imported = import_strava(
        access_token,
        date_filter=date_filter,
        start_date=start_date,
        end_date=end_date,
        fetch_heart_rates=fetch_hr,
    )

    if imported:
        print("\n  Syncing imported data with local records...")
        updated, created = sync_imported_records(imported)
        print(f"  Done! Days updated: {updated}, Days created: {created}")
    else:
        print("\n  No activities found for the selected date range.")


def show_data_sources():
    """Show connected data sources and their status."""
    from health_tracker.integrations.strava import load_strava_token

    print("\n" + "=" * 50)
    print("  DATA SOURCES")
    print("=" * 50)

    print("\n  1. Manual Entry          [Always available]")

    # Apple Health status
    print("  2. Apple Health (iPhone)  [Import via XML export]")
    print("     Export from: iPhone > Health > Profile > Export All Health Data")

    # Strava status
    token = load_strava_token()
    if token:
        print("  3. Strava                 [Connected]")
    else:
        print("  3. Strava                 [Not connected]")
        print("     Setup at: https://www.strava.com/settings/api")

    # Auto-sync status
    from health_tracker.auto_sync import is_daemon_running, load_config
    config = load_config()
    if is_daemon_running():
        print("  4. Auto-Sync Daemon       [Running]")
    elif config.get("enabled"):
        print("  4. Auto-Sync Daemon       [Configured but stopped]")
    else:
        print("  4. Auto-Sync Daemon       [Not configured]")

    # Show source breakdown for recent records
    records = list_all_records()
    if records:
        recent = records[-1]
        record = load_daily_record(recent)
        if record:
            sources = set()
            for w in record.workouts:
                sources.add(w.source)
            for hr in record.heart_rate_readings:
                sources.add(hr.source)
            if sources:
                print(f"\n  Latest record ({recent}) sources: {', '.join(sorted(sources))}")


def manage_auto_sync():
    """Auto-sync daemon management menu."""
    from health_tracker.auto_sync import (
        AutoSyncDaemon, load_config, save_config,
        is_daemon_running, get_daemon_pid, stop_daemon,
        LOG_PATH,
    )
    from health_tracker.integrations.shortcut_generator import (
        generate_shortcut_instructions,
        generate_test_curl_command,
        save_instructions_to_file,
        get_local_ip,
    )

    config = load_config()

    while True:
        running = is_daemon_running()
        pid = get_daemon_pid()

        print("\n" + "=" * 55)
        print("  AUTO-SYNC MANAGEMENT")
        print("=" * 55)

        status = "RUNNING" if running else "STOPPED"
        print(f"\n  Daemon Status: {status}" + (f" (PID {pid})" if pid else ""))

        # Component status
        srv = config["apple_health_server"]
        fw = config["folder_watcher"]
        st = config["strava"]
        local_ip = get_local_ip()

        print(f"\n  Components:")
        print(f"    Apple Health Server: {'ON' if srv['enabled'] else 'OFF'}"
              f"  (http://{local_ip}:{srv['port']}/sync)")
        print(f"    Folder Watcher:     {'ON' if fw['enabled'] else 'OFF'}"
              f"  ({fw['watch_dir'] or 'not configured'})")
        print(f"    Strava Scheduler:   {'ON' if st['enabled'] else 'OFF'}"
              f"  (daily at {st['sync_hour']:02d}:{st['sync_minute']:02d})")
        if config.get("last_strava_sync"):
            print(f"    Last Strava sync:   {config['last_strava_sync']}")

        print(f"\n  Actions:")
        if running:
            print("    1. Stop Auto-Sync Daemon")
        else:
            print("    1. Start Auto-Sync Daemon")
        print("    2. Configure Apple Health Server")
        print("    3. Configure Folder Watcher")
        print("    4. Configure Strava Scheduler")
        print("    5. View iOS Shortcut Setup Guide")
        print("    6. Test Server with curl command")
        print("    7. View Sync Log")
        print("    8. Run Strava Sync Now")
        print("    0. Back to Main Menu")
        print("-" * 55)

        choice = get_input("Choose option", str)

        if choice == "1":
            if running:
                stop_daemon()
                print("\n  Auto-Sync Daemon stopped.")
            else:
                config["enabled"] = True
                save_config(config)
                print("\n  Starting Auto-Sync Daemon in background...")
                daemon = AutoSyncDaemon(config)
                import threading
                t = threading.Thread(target=daemon.run_forever, daemon=True)
                t.start()
                import time
                time.sleep(1)
                if is_daemon_running():
                    print("  Daemon started successfully!")
                    print(f"  Apple Health endpoint: http://{local_ip}:{srv['port']}/sync")
                else:
                    print("  Daemon is initializing...")

        elif choice == "2":
            print("\n  Apple Health HTTP Server Configuration")
            srv["enabled"] = get_input(
                "Enable server? (yes/no)", str,
                "yes" if srv["enabled"] else "no"
            ).lower() in ("yes", "y")
            if srv["enabled"]:
                srv["port"] = get_input("Port", int, srv["port"])
            save_config(config)
            print("  Configuration saved!")
            if running:
                print("  Restart the daemon to apply changes.")

        elif choice == "3":
            print("\n  Folder Watcher Configuration")
            print("  This watches a directory for Apple Health XML exports")
            print("  (e.g., a folder synced via iCloud Drive)")
            fw["enabled"] = get_input(
                "Enable folder watcher? (yes/no)", str,
                "yes" if fw["enabled"] else "no"
            ).lower() in ("yes", "y")
            if fw["enabled"]:
                fw["watch_dir"] = get_input("Watch directory path", str, fw.get("watch_dir", ""))
                fw["poll_interval_seconds"] = get_input("Poll interval (seconds)", int, 60)
            save_config(config)
            print("  Configuration saved!")
            if running:
                print("  Restart the daemon to apply changes.")

        elif choice == "4":
            print("\n  Strava Scheduler Configuration")
            st["enabled"] = get_input(
                "Enable daily Strava sync? (yes/no)", str,
                "yes" if st["enabled"] else "no"
            ).lower() in ("yes", "y")
            if st["enabled"]:
                st["sync_hour"] = get_input("Sync hour (0-23)", int, st["sync_hour"])
                st["sync_minute"] = get_input("Sync minute (0-59)", int, st["sync_minute"])
                st["fetch_heart_rates"] = get_input(
                    "Fetch detailed HR data? (yes/no)", str,
                    "yes" if st["fetch_heart_rates"] else "no"
                ).lower() in ("yes", "y")
            save_config(config)
            print("  Configuration saved!")
            if running:
                print("  Restart the daemon to apply changes.")

        elif choice == "5":
            port = config["apple_health_server"]["port"]
            instructions = generate_shortcut_instructions(port)
            print(instructions)
            filepath = save_instructions_to_file(port)
            print(f"  Instructions also saved to: {filepath}")

        elif choice == "6":
            port = config["apple_health_server"]["port"]
            curl_cmd = generate_test_curl_command(port)
            print("\n  Test the sync endpoint with this curl command:\n")
            print(f"  {curl_cmd}")

        elif choice == "7":
            print(f"\n  Sync Log ({LOG_PATH}):")
            print("-" * 55)
            if os.path.exists(LOG_PATH):
                with open(LOG_PATH, "r") as f:
                    lines = f.readlines()
                # Show last 30 lines
                for line in lines[-30:]:
                    print(f"  {line.rstrip()}")
                if len(lines) > 30:
                    print(f"\n  ... showing last 30 of {len(lines)} lines")
            else:
                print("  No log file yet. Start the daemon first.")

        elif choice == "8":
            from health_tracker.integrations.strava import load_strava_token, import_strava
            token_data = load_strava_token()
            if not token_data:
                print("\n  Strava not connected. Use option 5 in main menu first.")
            else:
                print("\n  Running Strava sync...")
                start = (date.today() - timedelta(days=2)).isoformat()
                imported = import_strava(
                    token_data["access_token"],
                    start_date=start,
                    fetch_heart_rates=st.get("fetch_heart_rates", True),
                )
                if imported:
                    updated, created = sync_imported_records(imported)
                    print(f"  Done! {updated} days updated, {created} days created")
                    config["last_strava_sync"] = date.today().isoformat()
                    save_config(config)
                else:
                    print("  No new activities found.")

        elif choice == "0":
            break

        else:
            print("\n  Invalid option.")


def main_menu():
    """Display and handle main menu."""
    print("\n" + "=" * 50)
    print("  HEALTH & WORKOUT TRACKER")
    print("=" * 50)

    # Load or create profile
    profile = load_profile()
    if not profile:
        print("\n  Welcome! Let's set up your profile first.")
        profile = setup_profile()

    today = date.today().isoformat()

    while True:
        print(f"\n  Today: {today} | User: {profile.name} (Age {profile.age})")
        print("-" * 55)
        print("  MANUAL LOGGING")
        print("    1. Log Health Habits")
        print("    2. Log Workout")
        print("    3. Log Heart Rate")
        print("  IMPORT DATA")
        print("    4. Import from Apple Health (iPhone)")
        print("    5. Import from Strava")
        print("  VIEW & REPORTS")
        print("    6. View Today's Summary")
        print("    7. View Summary for Another Date")
        print("    8. View Age-Based Recommendations")
        print("    9. View History")
        print("  AUTO-SYNC & SETTINGS")
        print("   10. Data Sources & Connections")
        print("   11. Update Profile")
        print("   12. Auto-Sync (Daily Automatic Import)")
        print("    0. Exit")
        print("-" * 55)

        choice = get_input("Choose option", str)

        if choice == "1":
            # Load existing record or create new
            record = load_daily_record(today) or DailyRecord(date=today)
            record.health_habits = log_health_habits(today)
            save_daily_record(record)
            print("\n  Health habits saved!")

        elif choice == "2":
            record = load_daily_record(today) or DailyRecord(date=today)
            workout = log_workout(today)
            record.workouts.append(workout)
            save_daily_record(record)
            print("\n  Workout logged!")

        elif choice == "3":
            record = load_daily_record(today) or DailyRecord(date=today)
            hr_entry = log_heart_rate(today)
            record.heart_rate_readings.append(hr_entry)
            save_daily_record(record)
            print("\n  Heart rate logged!")

        elif choice == "4":
            import_apple_health_data()

        elif choice == "5":
            import_strava_data()

        elif choice == "6":
            view_summary(profile, today)

        elif choice == "7":
            record_date = get_input("Enter date (YYYY-MM-DD)", str)
            view_summary(profile, record_date)

        elif choice == "8":
            recommendations = get_age_based_recommendations(profile)
            print(f"\n  Recommendations for Age {profile.age}:")
            print(f"  Weekly Exercise: {recommendations['exercise_minutes_per_week']} min")
            print(f"  Recommended Workouts: {', '.join(recommendations['recommended_workouts'])}")
            print(f"  Sleep: {recommendations['sleep_hours']} hours")
            print(f"  Focus Areas:")
            for area in recommendations["focus_areas"]:
                print(f"    - {area}")
            print(f"  Note: {recommendations['caution']}")

        elif choice == "9":
            records = list_all_records()
            if records:
                print(f"\n  Records available ({len(records)} days):")
                for r in records[-10:]:  # Show last 10
                    record = load_daily_record(r)
                    sources = set()
                    if record:
                        for w in record.workouts:
                            sources.add(w.source)
                    source_tag = f" [{', '.join(sorted(sources))}]" if sources else ""
                    print(f"    - {r}{source_tag}")
                if len(records) > 10:
                    print(f"    ... and {len(records) - 10} more")
            else:
                print("\n  No records found yet. Start logging!")

        elif choice == "10":
            show_data_sources()

        elif choice == "11":
            profile = setup_profile()

        elif choice == "12":
            manage_auto_sync()

        elif choice == "0":
            print("\n  Stay healthy! Goodbye!")
            sys.exit(0)

        else:
            print("\n  Invalid option.")


if __name__ == "__main__":
    main_menu()
