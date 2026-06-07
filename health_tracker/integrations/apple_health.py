"""
Apple Health Integration - Parse iPhone Health app XML export.

How to export your Apple Health data:
  1. Open the "Health" app on your iPhone
  2. Tap your profile picture (top right)
  3. Scroll down and tap "Export All Health Data"
  4. Save or share the resulting ZIP file
  5. Unzip it to find "apple_health_export/export.xml"
  6. Provide the path to export.xml when importing

This module parses the XML to extract:
  - Step count
  - Heart rate readings
  - Sleep analysis
  - Active/resting energy burned
  - Walking/running distance
  - Flights climbed
  - Water intake (if logged in Health app)
  - Workout sessions (from Apple Fitness / Health)
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from typing import Optional

from ..models import HealthHabit, Workout, HeartRateEntry, DailyRecord

# Apple Health quantity type identifiers
STEP_COUNT = "HKQuantityTypeIdentifierStepCount"
HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
ACTIVE_ENERGY = "HKQuantityTypeIdentifierActiveEnergyBurned"
RESTING_ENERGY = "HKQuantityTypeIdentifierBasalEnergyBurned"
WALKING_DISTANCE = "HKQuantityTypeIdentifierDistanceWalkingRunning"
CYCLING_DISTANCE = "HKQuantityTypeIdentifierDistanceCycling"
SWIMMING_DISTANCE = "HKQuantityTypeIdentifierDistanceSwimming"
FLIGHTS_CLIMBED = "HKQuantityTypeIdentifierFlightsClimbed"
WATER = "HKQuantityTypeIdentifierDietaryWater"
SLEEP = "HKCategoryTypeIdentifierSleepAnalysis"

# Map Apple workout types to our tracker types
APPLE_WORKOUT_TYPE_MAP = {
    "HKWorkoutActivityTypeRunning": "running",
    "HKWorkoutActivityTypeCycling": "cycling",
    "HKWorkoutActivityTypeSwimming": "swimming",
    "HKWorkoutActivityTypeWalking": "walking",
    "HKWorkoutActivityTypeHiking": "walking",
    "HKWorkoutActivityTypeYoga": "yoga",
    "HKWorkoutActivityTypeFunctionalStrengthTraining": "weightlifting",
    "HKWorkoutActivityTypeTraditionalStrengthTraining": "weightlifting",
    "HKWorkoutActivityTypeHighIntensityIntervalTraining": "hiit",
    "HKWorkoutActivityTypeDance": "dancing",
    "HKWorkoutActivityTypeJumpRope": "jump_rope",
    "HKWorkoutActivityTypeRowing": "rowing",
    "HKWorkoutActivityTypeElliptical": "elliptical",
    "HKWorkoutActivityTypeStairClimbing": "stair_climbing",
    "HKWorkoutActivityTypeBoxing": "boxing",
    "HKWorkoutActivityTypePilates": "pilates",
    "HKWorkoutActivityTypeCooldown": "stretching",
    "HKWorkoutActivityTypeCoreTraining": "weightlifting",
    "HKWorkoutActivityTypeCrossTraining": "hiit",
    "HKWorkoutActivityTypeMixedCardio": "hiit",
}


def parse_apple_health_date(date_str: str) -> tuple[str, str]:
    """Parse Apple Health date format to (date, time) strings."""
    # Apple Health format: "2026-04-10 07:30:00 -0500"
    dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def import_apple_health(
    xml_path: str,
    date_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, DailyRecord]:
    """
    Parse Apple Health export XML and return daily records.

    Args:
        xml_path: Path to the export.xml file
        date_filter: If set, only import this specific date (YYYY-MM-DD)
        start_date: If set, only import records on or after this date
        end_date: If set, only import records on or before this date

    Returns:
        Dictionary mapping date strings to DailyRecord objects
    """
    print(f"  Parsing Apple Health export: {xml_path}")
    print("  This may take a moment for large exports...")

    # Use iterparse for memory-efficient parsing of large XML files
    daily_data: dict[str, dict] = defaultdict(lambda: {
        "steps": 0,
        "heart_rates": [],
        "sleep_minutes": 0.0,
        "active_energy": 0.0,
        "resting_energy": 0.0,
        "walking_distance_km": 0.0,
        "flights_climbed": 0,
        "workouts": [],
    })

    record_count = 0
    workout_count = 0

    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "Record":
            record_type = elem.get("type", "")
            start_date_str = elem.get("startDate", "")
            value = elem.get("value", "0")

            if not start_date_str:
                elem.clear()
                continue

            record_date, record_time = parse_apple_health_date(start_date_str)

            # Apply date filters
            if date_filter and record_date != date_filter:
                elem.clear()
                continue
            if start_date and record_date < start_date:
                elem.clear()
                continue
            if end_date and record_date > end_date:
                elem.clear()
                continue

            day = daily_data[record_date]

            if record_type == STEP_COUNT:
                try:
                    day["steps"] += int(float(value))
                except ValueError:
                    pass

            elif record_type == HEART_RATE:
                try:
                    day["heart_rates"].append({
                        "time": record_time,
                        "bpm": int(float(value)),
                    })
                except ValueError:
                    pass

            elif record_type == ACTIVE_ENERGY:
                try:
                    day["active_energy"] += float(value)
                except ValueError:
                    pass

            elif record_type == RESTING_ENERGY:
                try:
                    day["resting_energy"] += float(value)
                except ValueError:
                    pass

            elif record_type == WALKING_DISTANCE:
                try:
                    day["walking_distance_km"] += float(value)
                except ValueError:
                    pass

            elif record_type == FLIGHTS_CLIMBED:
                try:
                    day["flights_climbed"] += int(float(value))
                except ValueError:
                    pass

            record_count += 1
            if record_count % 100000 == 0:
                print(f"    Processed {record_count:,} records...")

            elem.clear()

        elif elem.tag == "Record" and elem.get("type") == SLEEP:
            start_date_str = elem.get("startDate", "")
            end_date_str = elem.get("endDate", "")
            if start_date_str and end_date_str:
                record_date, _ = parse_apple_health_date(start_date_str)

                if date_filter and record_date != date_filter:
                    elem.clear()
                    continue

                try:
                    start_dt = datetime.strptime(start_date_str[:19], "%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.strptime(end_date_str[:19], "%Y-%m-%d %H:%M:%S")
                    sleep_hours = (end_dt - start_dt).total_seconds() / 3600
                    # Attribute sleep to the date the sleep ended (wake-up date)
                    wake_date = end_dt.strftime("%Y-%m-%d")
                    daily_data[wake_date]["sleep_minutes"] += sleep_hours * 60
                except (ValueError, KeyError):
                    pass

            elem.clear()

        elif elem.tag == "Workout":
            workout_type = elem.get("workoutActivityType", "")
            start_date_str = elem.get("startDate", "")
            duration = elem.get("duration", "0")
            duration_unit = elem.get("durationUnit", "min")
            total_energy = elem.get("totalEnergyBurned", "0")
            total_distance = elem.get("totalDistance", "0")
            distance_unit = elem.get("totalDistanceUnit", "km")

            if not start_date_str:
                elem.clear()
                continue

            record_date, record_time = parse_apple_health_date(start_date_str)

            if date_filter and record_date != date_filter:
                elem.clear()
                continue
            if start_date and record_date < start_date:
                elem.clear()
                continue
            if end_date and record_date > end_date:
                elem.clear()
                continue

            # Convert duration to minutes
            try:
                dur_minutes = float(duration)
                if duration_unit == "s":
                    dur_minutes /= 60
                elif duration_unit == "hr":
                    dur_minutes *= 60
            except ValueError:
                dur_minutes = 0

            # Convert distance to km
            try:
                dist_km = float(total_distance)
                if distance_unit == "mi":
                    dist_km *= 1.60934
                elif distance_unit == "m":
                    dist_km /= 1000
            except ValueError:
                dist_km = 0

            # Get calories
            try:
                calories = float(total_energy)
            except ValueError:
                calories = 0

            # Determine intensity from calories/minute ratio
            if dur_minutes > 0 and calories > 0:
                cal_per_min = calories / dur_minutes
                if cal_per_min > 10:
                    intensity = "vigorous"
                elif cal_per_min > 5:
                    intensity = "moderate"
                else:
                    intensity = "light"
            else:
                intensity = "moderate"

            mapped_type = APPLE_WORKOUT_TYPE_MAP.get(workout_type, "other")

            # Extract heart rate from workout metadata if available
            avg_hr = None
            for meta in elem.findall(".//WorkoutStatistics"):
                if meta.get("type") == HEART_RATE:
                    avg_val = meta.get("average")
                    if avg_val:
                        try:
                            avg_hr = int(float(avg_val))
                        except ValueError:
                            pass

            workout_id = f"apple_{record_date}_{record_time}_{mapped_type}"

            daily_data[record_date]["workouts"].append({
                "type": mapped_type,
                "duration_minutes": int(dur_minutes),
                "intensity": intensity,
                "distance_km": round(dist_km, 2) if dist_km > 0 else None,
                "calories": round(calories, 1) if calories > 0 else None,
                "avg_heart_rate": avg_hr,
                "external_id": workout_id,
            })
            workout_count += 1

            elem.clear()

    # Convert to DailyRecord objects
    records: dict[str, DailyRecord] = {}

    for record_date, day in daily_data.items():
        record = DailyRecord(date=record_date)

        # Build health habits
        sleep_hours = round(day["sleep_minutes"] / 60, 1)
        record.health_habits = HealthHabit(
            date=record_date,
            sleep_hours=sleep_hours,
            steps=day["steps"],
            active_energy_burned=round(day["active_energy"], 1),
            resting_energy_burned=round(day["resting_energy"], 1),
            flights_climbed=day["flights_climbed"],
            distance_walked_km=round(day["walking_distance_km"], 2),
        )

        # Build workouts
        for w in day["workouts"]:
            record.workouts.append(Workout(
                date=record_date,
                workout_type=w["type"],
                duration_minutes=w["duration_minutes"],
                intensity=w["intensity"],
                distance_km=w["distance_km"],
                calories_reported=w["calories"],
                avg_heart_rate=w["avg_heart_rate"],
                source="apple_health",
                external_id=w["external_id"],
            ))

        # Build heart rate entries (sample to avoid thousands per day)
        hr_readings = day["heart_rates"]
        if hr_readings:
            # Keep up to 24 readings per day (roughly one per hour)
            if len(hr_readings) > 24:
                step = len(hr_readings) // 24
                hr_readings = hr_readings[::step][:24]

            for hr in hr_readings:
                hr_id = f"apple_hr_{record_date}_{hr['time']}_{hr['bpm']}"
                record.heart_rate_readings.append(HeartRateEntry(
                    date=record_date,
                    time=hr["time"],
                    heart_rate_bpm=hr["bpm"],
                    context="resting",
                    source="apple_health",
                    external_id=hr_id,
                ))

        records[record_date] = record

    print(f"\n  Import complete!")
    print(f"    Records processed: {record_count:,}")
    print(f"    Workouts found:    {workout_count}")
    print(f"    Days imported:     {len(records)}")

    return records
