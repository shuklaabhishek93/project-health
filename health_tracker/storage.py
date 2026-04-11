"""JSON-based data persistence for health tracking."""

import json
import os
from datetime import date
from typing import Optional

from .models import (
    UserProfile,
    HealthHabit,
    Workout,
    HeartRateEntry,
    DailyRecord,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


def save_profile(profile: UserProfile):
    """Save user profile to JSON file."""
    ensure_data_dir()
    filepath = os.path.join(DATA_DIR, "profile.json")
    data = {
        "name": profile.name,
        "age": profile.age,
        "weight_kg": profile.weight_kg,
        "height_cm": profile.height_cm,
        "gender": profile.gender,
    }
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_profile() -> Optional[UserProfile]:
    """Load user profile from JSON file."""
    filepath = os.path.join(DATA_DIR, "profile.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        data = json.load(f)
    return UserProfile(**data)


def get_daily_record_path(record_date: str) -> str:
    """Get file path for a daily record."""
    return os.path.join(DATA_DIR, f"record_{record_date}.json")


def save_daily_record(record: DailyRecord):
    """Save a daily record to JSON file."""
    ensure_data_dir()
    filepath = get_daily_record_path(record.date)

    data = {
        "date": record.date,
        "health_habits": None,
        "workouts": [],
        "heart_rate_readings": [],
        "total_calories_burned": record.total_calories_burned,
    }

    if record.health_habits:
        data["health_habits"] = {
            "date": record.health_habits.date,
            "water_intake_liters": record.health_habits.water_intake_liters,
            "sleep_hours": record.health_habits.sleep_hours,
            "steps": record.health_habits.steps,
            "fruits_vegetables_servings": record.health_habits.fruits_vegetables_servings,
            "meditation_minutes": record.health_habits.meditation_minutes,
            "alcohol_drinks": record.health_habits.alcohol_drinks,
            "smoking": record.health_habits.smoking,
            "notes": record.health_habits.notes,
        }

    for workout in record.workouts:
        data["workouts"].append({
            "date": workout.date,
            "workout_type": workout.workout_type,
            "duration_minutes": workout.duration_minutes,
            "intensity": workout.intensity,
            "distance_km": workout.distance_km,
            "sets": workout.sets,
            "reps": workout.reps,
            "weight_lifted_kg": workout.weight_lifted_kg,
            "notes": workout.notes,
        })

    for hr in record.heart_rate_readings:
        data["heart_rate_readings"].append({
            "date": hr.date,
            "time": hr.time,
            "heart_rate_bpm": hr.heart_rate_bpm,
            "context": hr.context,
        })

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_daily_record(record_date: str) -> Optional[DailyRecord]:
    """Load a daily record from JSON file."""
    filepath = get_daily_record_path(record_date)
    if not os.path.exists(filepath):
        return None

    with open(filepath, "r") as f:
        data = json.load(f)

    record = DailyRecord(date=data["date"])
    record.total_calories_burned = data.get("total_calories_burned", 0.0)

    if data.get("health_habits"):
        record.health_habits = HealthHabit(**data["health_habits"])

    for w in data.get("workouts", []):
        record.workouts.append(Workout(**w))

    for hr in data.get("heart_rate_readings", []):
        record.heart_rate_readings.append(HeartRateEntry(**hr))

    return record


def list_all_records() -> list[str]:
    """List all record dates available."""
    ensure_data_dir()
    records = []
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("record_") and filename.endswith(".json"):
            date_str = filename[7:-5]  # Remove "record_" prefix and ".json" suffix
            records.append(date_str)
    return sorted(records)
