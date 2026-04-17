"""Data persistence for health tracking.

Uses PostgreSQL when DATABASE_URL is set (Render / cloud), otherwise
falls back to local JSON files.
"""

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
from .db_storage import is_db_enabled, db_put, db_get, db_get_many, db_list_keys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def _profile_to_dict(profile: UserProfile) -> dict:
    return {
        "name": profile.name,
        "age": profile.age,
        "weight_kg": profile.weight_kg,
        "height_cm": profile.height_cm,
        "gender": profile.gender,
    }


def _dict_to_profile(data: dict) -> UserProfile:
    return UserProfile(**data)


def save_profile(profile: UserProfile):
    data = _profile_to_dict(profile)
    if is_db_enabled():
        db_put("profile", data)
    else:
        ensure_data_dir()
        with open(os.path.join(DATA_DIR, "profile.json"), "w") as f:
            json.dump(data, f, indent=2)


def load_profile() -> Optional[UserProfile]:
    if is_db_enabled():
        data = db_get("profile")
        return _dict_to_profile(data) if data else None
    filepath = os.path.join(DATA_DIR, "profile.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        data = json.load(f)
    return _dict_to_profile(data)


# ---------------------------------------------------------------------------
# Daily records
# ---------------------------------------------------------------------------

def _record_to_json(record: DailyRecord) -> dict:
    data: dict = {
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
            "active_energy_burned": record.health_habits.active_energy_burned,
            "resting_energy_burned": record.health_habits.resting_energy_burned,
            "flights_climbed": record.health_habits.flights_climbed,
            "distance_walked_km": record.health_habits.distance_walked_km,
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
            "calories_reported": workout.calories_reported,
            "avg_heart_rate": workout.avg_heart_rate,
            "source": workout.source,
            "external_id": workout.external_id,
            "notes": workout.notes,
        })

    for hr in record.heart_rate_readings:
        data["heart_rate_readings"].append({
            "date": hr.date,
            "time": hr.time,
            "heart_rate_bpm": hr.heart_rate_bpm,
            "context": hr.context,
            "source": hr.source,
            "external_id": hr.external_id,
        })

    return data


def _json_to_record(data: dict) -> DailyRecord:
    record = DailyRecord(date=data["date"])
    record.total_calories_burned = data.get("total_calories_burned", 0.0)

    if data.get("health_habits"):
        h = data["health_habits"]
        record.health_habits = HealthHabit(
            date=h["date"],
            water_intake_liters=h.get("water_intake_liters", 0.0),
            sleep_hours=h.get("sleep_hours", 0.0),
            steps=h.get("steps", 0),
            fruits_vegetables_servings=h.get("fruits_vegetables_servings", 0),
            meditation_minutes=h.get("meditation_minutes", 0),
            alcohol_drinks=h.get("alcohol_drinks", 0),
            smoking=h.get("smoking", False),
            active_energy_burned=h.get("active_energy_burned", 0.0),
            resting_energy_burned=h.get("resting_energy_burned", 0.0),
            flights_climbed=h.get("flights_climbed", 0),
            distance_walked_km=h.get("distance_walked_km", 0.0),
            notes=h.get("notes", ""),
        )

    for w in data.get("workouts", []):
        record.workouts.append(Workout(
            date=w["date"],
            workout_type=w["workout_type"],
            duration_minutes=w.get("duration_minutes", 0),
            intensity=w.get("intensity", "moderate"),
            distance_km=w.get("distance_km"),
            sets=w.get("sets"),
            reps=w.get("reps"),
            weight_lifted_kg=w.get("weight_lifted_kg"),
            calories_reported=w.get("calories_reported"),
            avg_heart_rate=w.get("avg_heart_rate"),
            source=w.get("source", "manual"),
            external_id=w.get("external_id"),
            notes=w.get("notes", ""),
        ))

    for hr in data.get("heart_rate_readings", []):
        record.heart_rate_readings.append(HeartRateEntry(
            date=hr["date"],
            time=hr["time"],
            heart_rate_bpm=hr["heart_rate_bpm"],
            context=hr.get("context", "resting"),
            source=hr.get("source", "manual"),
            external_id=hr.get("external_id"),
        ))

    return record


def get_daily_record_path(record_date: str) -> str:
    return os.path.join(DATA_DIR, f"record_{record_date}.json")


def save_daily_record(record: DailyRecord):
    data = _record_to_json(record)
    if is_db_enabled():
        db_put(f"record_{record.date}", data)
    else:
        ensure_data_dir()
        with open(get_daily_record_path(record.date), "w") as f:
            json.dump(data, f, indent=2)


def load_daily_record(record_date: str) -> Optional[DailyRecord]:
    if is_db_enabled():
        data = db_get(f"record_{record_date}")
        return _json_to_record(data) if data else None
    filepath = get_daily_record_path(record_date)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        data = json.load(f)
    return _json_to_record(data)


def load_daily_records_batch(dates: list[str]) -> dict[str, Optional[DailyRecord]]:
    """Load multiple daily records in one database round-trip."""
    if is_db_enabled():
        keys = [f"record_{d}" for d in dates]
        raw = db_get_many(keys)
        return {
            d: _json_to_record(raw[f"record_{d}"]) if f"record_{d}" in raw else None
            for d in dates
        }
    return {d: load_daily_record(d) for d in dates}


def list_all_records() -> list[str]:
    if is_db_enabled():
        keys = db_list_keys("record_")
        return sorted(k.replace("record_", "", 1) for k in keys)
    ensure_data_dir()
    records = []
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("record_") and filename.endswith(".json"):
            date_str = filename[7:-5]
            records.append(date_str)
    return sorted(records)
