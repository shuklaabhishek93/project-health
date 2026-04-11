"""Health and Workout Tracker - CLI Application."""

import sys
from datetime import date

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
        water_intake_liters=get_input("Water intake (liters)", float, 0.0),
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
        dist = get_input("Distance in km (0 to skip)", float, 0.0)
        if dist > 0:
            workout.distance_km = dist

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
        print("-" * 50)
        print("  1. Log Health Habits")
        print("  2. Log Workout")
        print("  3. Log Heart Rate")
        print("  4. View Today's Summary")
        print("  5. View Summary for Another Date")
        print("  6. View Age-Based Recommendations")
        print("  7. View History")
        print("  8. Update Profile")
        print("  9. Exit")
        print("-" * 50)

        choice = get_input("Choose option (1-9)", str)

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
            view_summary(profile, today)

        elif choice == "5":
            record_date = get_input("Enter date (YYYY-MM-DD)", str)
            view_summary(profile, record_date)

        elif choice == "6":
            recommendations = get_age_based_recommendations(profile)
            print(f"\n  Recommendations for Age {profile.age}:")
            print(f"  Weekly Exercise: {recommendations['exercise_minutes_per_week']} min")
            print(f"  Recommended Workouts: {', '.join(recommendations['recommended_workouts'])}")
            print(f"  Sleep: {recommendations['sleep_hours']} hours")
            print(f"  Water: {recommendations['water_liters']}L/day")
            print(f"  Focus Areas:")
            for area in recommendations["focus_areas"]:
                print(f"    - {area}")
            print(f"  Note: {recommendations['caution']}")

        elif choice == "7":
            records = list_all_records()
            if records:
                print(f"\n  Records available ({len(records)} days):")
                for r in records[-10:]:  # Show last 10
                    print(f"    - {r}")
                if len(records) > 10:
                    print(f"    ... and {len(records) - 10} more")
            else:
                print("\n  No records found yet. Start logging!")

        elif choice == "8":
            profile = setup_profile()

        elif choice == "9":
            print("\n  Stay healthy! Goodbye!")
            sys.exit(0)

        else:
            print("\n  Invalid option. Please choose 1-9.")


if __name__ == "__main__":
    main_menu()
