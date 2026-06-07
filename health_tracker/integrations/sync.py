"""
Sync utilities - Merge imported data into existing daily records without duplicates.
"""

from ..models import DailyRecord, HealthHabit
from ..storage import load_daily_record, save_daily_record


def merge_daily_records(existing: DailyRecord, imported: DailyRecord) -> DailyRecord:
    """
    Merge an imported DailyRecord into an existing one.

    - Health habits: Merges device-reported fields (steps, energy, distance) without
      overwriting manually-entered fields (diet, meditation, etc.)
    - Workouts: Adds imported workouts, skipping duplicates by external_id
    - Heart rate: Adds imported readings, skipping duplicates by external_id
    """
    # Merge health habits
    if imported.health_habits:
        if existing.health_habits is None:
            existing.health_habits = HealthHabit(date=existing.date)

        h = existing.health_habits
        imp = imported.health_habits

        # Steps: always use Apple Health value (Strava doesn't report steps)
        if imp.steps > 0:
            h.steps = imp.steps
        if imp.sleep_hours > 0:
            h.sleep_hours = max(h.sleep_hours, imp.sleep_hours)
        if imp.active_energy_burned > 0:
            h.active_energy_burned = imp.active_energy_burned
        if imp.resting_energy_burned > 0:
            h.resting_energy_burned = imp.resting_energy_burned
        if imp.flights_climbed > 0:
            h.flights_climbed = max(h.flights_climbed, imp.flights_climbed)
        if imp.distance_walked_km > 0:
            h.distance_walked_km = max(h.distance_walked_km, imp.distance_walked_km)

    # Merge workouts (skip duplicates by external_id)
    existing_workout_ids = {w.external_id for w in existing.workouts if w.external_id}
    for workout in imported.workouts:
        if workout.external_id and workout.external_id in existing_workout_ids:
            continue
        if workout.external_id:
            existing_workout_ids.add(workout.external_id)
        existing.workouts.append(workout)

    # Merge heart rate readings (skip duplicates by external_id)
    existing_hr_ids = {hr.external_id for hr in existing.heart_rate_readings if hr.external_id}
    for hr in imported.heart_rate_readings:
        if hr.external_id and hr.external_id in existing_hr_ids:
            continue
        if hr.external_id:
            existing_hr_ids.add(hr.external_id)
        existing.heart_rate_readings.append(hr)

    # Sort heart rate readings by time
    existing.heart_rate_readings.sort(key=lambda h: h.time)

    return existing


def sync_imported_records(imported_records: dict[str, DailyRecord]) -> tuple[int, int]:
    """
    Sync all imported records into the local storage.

    Returns:
        Tuple of (days_updated, days_created)
    """
    days_updated = 0
    days_created = 0

    for record_date, imported in imported_records.items():
        existing = load_daily_record(record_date)

        if existing:
            merged = merge_daily_records(existing, imported)
            save_daily_record(merged)
            days_updated += 1
        else:
            save_daily_record(imported)
            days_created += 1

    return days_updated, days_created
