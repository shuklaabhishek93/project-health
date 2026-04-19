"""
HTTP server that receives Apple Health & Fitness data pushed from iOS Shortcuts.

Expected JSON payload from simplified iOS Shortcut (POST /sync):
{
  "date": "2026-04-18",
  "steps": 15788,
  "active_energy": 520.0,
  "resting_energy": 1700.0,
  "distance": 8.2,
  "flights_climbed": 12,
  "sleep_start": "2026-04-17 23:15",
  "sleep_end": "2026-04-18 06:45"
}

The server handles all conversions:
- sleep_start + sleep_end → sleep_hours (calculated server-side)
- distance/distance_miles → converted to km
- Any field name typos/variations accepted
"""

import json
import logging
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from ..models import HealthHabit, Workout, HeartRateEntry, DailyRecord
from ..storage import load_daily_record, save_daily_record
from .sync import merge_daily_records

logger = logging.getLogger("auto_sync.apple_health_server")

# Map iOS Shortcut workout type names to our types
IOS_WORKOUT_TYPE_MAP = {
    "running": "running",
    "cycling": "cycling",
    "swimming": "swimming",
    "walking": "walking",
    "hiking": "walking",
    "yoga": "yoga",
    "strength_training": "weightlifting",
    "functional_strength": "weightlifting",
    "traditional_strength": "weightlifting",
    "hiit": "hiit",
    "high_intensity_interval": "hiit",
    "dance": "dancing",
    "jump_rope": "jump_rope",
    "rowing": "rowing",
    "elliptical": "elliptical",
    "stair_climbing": "stair_climbing",
    "boxing": "boxing",
    "pilates": "pilates",
    "cooldown": "stretching",
    "core_training": "weightlifting",
    "cross_training": "hiit",
    "mixed_cardio": "hiit",
}


class HealthDataHandler(BaseHTTPRequestHandler):
    """HTTP handler for receiving health data from iOS Shortcuts."""

    def do_POST(self):
        if self.path == "/sync":
            self._handle_sync()
        elif self.path == "/ping":
            self._send_json(200, {"status": "ok", "service": "health-tracker"})
        else:
            self._send_json(404, {"error": "Not found. Use POST /sync"})

    def do_GET(self):
        if self.path == "/ping" or self.path == "/":
            self._send_json(200, {
                "status": "ok",
                "service": "health-tracker",
                "endpoint": "POST /sync",
            })
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_sync(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(400, {"error": "Empty request body"})
                return

            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            record_date = data.get("date")
            if not record_date:
                record_date = datetime.now().strftime("%Y-%m-%d")
            if "T" in record_date:
                record_date = record_date.split("T")[0]

            imported = parse_ios_payload(data, record_date)

            # Merge with existing record
            existing = load_daily_record(record_date)
            if existing:
                merged = merge_daily_records(existing, imported)
                save_daily_record(merged)
            else:
                save_daily_record(imported)

            workout_count = len(imported.workouts)
            hr_count = len(imported.heart_rate_readings)
            steps = imported.health_habits.steps if imported.health_habits else 0

            logger.info(
                f"Apple Health sync for {record_date}: "
                f"{steps} steps, {workout_count} workouts, {hr_count} HR readings"
            )

            self._send_json(200, {
                "status": "success",
                "date": record_date,
                "steps": steps,
                "workouts_imported": workout_count,
                "heart_rate_readings": hr_count,
            })

        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
            self._send_json(500, {"error": str(e)})

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        logger.debug(f"HTTP: {format % args}")


def _safe_int(val, default=0) -> int:
    """Convert a value to int, handling strings and floats from iOS Shortcuts."""
    if val is None or val == "" or val == []:
        return default
    try:
        return int(float(str(val).strip().replace(",", "")))
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0) -> float:
    """Convert a value to float, handling strings from iOS Shortcuts."""
    if val is None or val == "" or val == []:
        return default
    try:
        return float(str(val).strip().replace(",", ""))
    except (ValueError, TypeError):
        return default


def _first_of(data: dict, *keys) -> object:
    """Return the first non-empty value found for any of the given keys."""
    for k in keys:
        v = data.get(k)
        if v is not None and v != "" and v != []:
            return v
    return None


def _calc_sleep_hours(sleep_start, sleep_end) -> float:
    """Calculate sleep duration from start/end timestamps sent by iOS Shortcut."""
    if not sleep_start or not sleep_end:
        return 0.0
    try:
        start_str = str(sleep_start).strip()
        end_str = str(sleep_end).strip()
        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%b %d, %Y at %I:%M %p",
            "%b %d, %Y at %I:%M:%S %p",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y %I:%M %p",
            "%d/%m/%Y %H:%M",
        ]
        for fmt in formats:
            try:
                start = datetime.strptime(start_str, fmt)
                end = datetime.strptime(end_str, fmt)
                diff = (end - start).total_seconds() / 3600.0
                if 0 < diff <= 16:
                    return round(diff, 2)
                if diff > 16:
                    # Filter captured two nights; estimate last night only.
                    # Use sleep_end time as wake-up and assume ~sleep_end.hour + 6
                    # hours of sleep (e.g., woke at 6 AM → slept ~6h from midnight).
                    adjusted = diff % 24
                    if 2 < adjusted <= 16:
                        return round(adjusted, 2)
                    # Fallback: use wake-up hour as rough estimate
                    wake_hour = end.hour + end.minute / 60.0
                    if 0 < wake_hour <= 14:
                        return round(wake_hour, 2)
                return 0.0
            except ValueError:
                continue
    except Exception:
        pass
    return 0.0


def _parse_distance_km(data: dict) -> float:
    """Extract distance in km, accepting km, miles, or raw values."""
    km = _safe_float(_first_of(data, "distance_km"))
    if km > 0:
        return km

    miles = _safe_float(_first_of(data, "distance_miles"))
    if miles > 0:
        return round(miles * 1.60934, 2)

    raw = _safe_float(_first_of(data, "distance", "walking_running_distance"))
    if raw > 0:
        if raw > 100:
            return round(raw / 1000.0, 2)
        return raw

    return 0.0


def parse_ios_payload(data: dict, record_date: str) -> DailyRecord:
    """Convert iOS Shortcut JSON payload into a DailyRecord.

    Accepts flexible field names and does all conversions server-side.
    """
    record = DailyRecord(date=record_date)

    # Sleep: prefer explicit sleep_hours, otherwise calculate from timestamps
    sleep_hours = _safe_float(_first_of(data, "sleep_hours", "sleep"))
    if sleep_hours == 0:
        sleep_start = _first_of(data, "sleep_start", "sleepStart", "sleep_start_time")
        sleep_end = _first_of(data, "sleep_end", "sleepEnd", "sleep_end_time")
        sleep_hours = _calc_sleep_hours(sleep_start, sleep_end)

    record.health_habits = HealthHabit(
        date=record_date,
        steps=_safe_int(_first_of(data, "steps", "step_count")),
        sleep_hours=sleep_hours,
        active_energy_burned=_safe_float(
            _first_of(data, "active_energy", "active_calories", "active_energy_burned")
        ),
        resting_energy_burned=_safe_float(
            _first_of(data, "resting_energy", "resting_calories", "basal_energy", "resting_energy_burned")
        ),
        distance_walked_km=_parse_distance_km(data),
        flights_climbed=_safe_int(
            _first_of(data, "flights_climbed", "flights_climed", "flights", "floor_count")
        ),
        water_intake_liters=_safe_float(_first_of(data, "water_ml", "water")) / 1000.0
        if _first_of(data, "water_ml", "water") else 0.0,
    )

    # Parse workouts
    for w in data.get("workouts", []):
        workout_type = w.get("type", "other").lower().replace(" ", "_")
        mapped_type = IOS_WORKOUT_TYPE_MAP.get(workout_type, workout_type)
        start_time = w.get("start_time", "00:00")
        ext_id = f"apple_auto_{record_date}_{start_time}_{mapped_type}"

        dur = _safe_int(w.get("duration_minutes"))
        cal = _safe_float(w.get("calories"))

        if dur > 0 and cal > 0:
            cpm = cal / dur
            intensity = "vigorous" if cpm > 10 else ("moderate" if cpm > 5 else "light")
        else:
            intensity = "moderate"

        record.workouts.append(Workout(
            date=record_date,
            workout_type=mapped_type,
            duration_minutes=dur,
            intensity=intensity,
            distance_km=_safe_float(w.get("distance_km")) or None,
            calories_reported=cal if cal > 0 else None,
            avg_heart_rate=_safe_int(w.get("avg_heart_rate")) or None,
            source="apple_health",
            external_id=ext_id,
        ))

    # Parse heart rate readings
    for hr in data.get("heart_rate_readings", []):
        hr_time = hr.get("time", "00:00")
        bpm = _safe_int(hr.get("bpm"))
        if bpm <= 0:
            continue
        ext_id = f"apple_auto_hr_{record_date}_{hr_time}_{bpm}"

        record.heart_rate_readings.append(HeartRateEntry(
            date=record_date,
            time=hr_time,
            heart_rate_bpm=bpm,
            context=hr.get("context", "resting"),
            source="apple_health",
            external_id=ext_id,
        ))

    return record


class AppleHealthServer:
    """Manages the HTTP server for receiving iOS Shortcut data."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8090):
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the HTTP server in a background thread."""
        self._server = HTTPServer((self.host, self.port), HealthDataHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"Apple Health receiver started on http://{self.host}:{self.port}")

    def stop(self):
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None
            logger.info("Apple Health receiver stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
