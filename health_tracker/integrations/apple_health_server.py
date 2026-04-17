"""
HTTP server that receives Apple Health & Fitness data pushed from iOS Shortcuts.

This server runs in the background and listens for JSON payloads from an iOS
Shortcut that queries HealthKit on the iPhone. The Shortcut runs automatically
via iOS Personal Automation (e.g., daily at 11 PM) — no human intervention.

Expected JSON payload format (POST /sync):
{
  "date": "2026-04-12",
  "steps": 10500,
  "sleep_hours": 7.5,
  "heart_rate_readings": [
    {"time": "07:00", "bpm": 62, "context": "morning"},
    {"time": "14:00", "bpm": 78, "context": "resting"}
  ],
  "active_energy": 520.0,
  "resting_energy": 1700.0,
  "distance_km": 8.2,
  "flights_climbed": 12,
  "water_ml": 2500,
  "workouts": [
    {
      "type": "running",
      "duration_minutes": 35,
      "distance_km": 5.5,
      "calories": 380,
      "avg_heart_rate": 152,
      "start_time": "09:00"
    }
  ]
}
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


def parse_ios_payload(data: dict, record_date: str) -> DailyRecord:
    """Convert iOS Shortcut JSON payload into a DailyRecord."""
    record = DailyRecord(date=record_date)

    record.health_habits = HealthHabit(
        date=record_date,
        steps=_safe_int(data.get("steps")),
        sleep_hours=_safe_float(data.get("sleep_hours")),
        active_energy_burned=_safe_float(data.get("active_energy")),
        resting_energy_burned=_safe_float(data.get("resting_energy")),
        distance_walked_km=_safe_float(data.get("distance_km")),
        flights_climbed=_safe_int(data.get("flights_climbed")),
        water_intake_liters=_safe_float(data.get("water_ml")) / 1000.0,
    )

    # Parse workouts
    for i, w in enumerate(data.get("workouts", [])):
        workout_type = w.get("type", "other").lower().replace(" ", "_")
        mapped_type = IOS_WORKOUT_TYPE_MAP.get(workout_type, workout_type)
        start_time = w.get("start_time", "00:00")
        ext_id = f"apple_auto_{record_date}_{start_time}_{mapped_type}"

        dur = int(w.get("duration_minutes", 0))
        cal = float(w.get("calories", 0))

        # Infer intensity from cal/min ratio
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
            distance_km=float(w["distance_km"]) if w.get("distance_km") else None,
            calories_reported=cal if cal > 0 else None,
            avg_heart_rate=int(w["avg_heart_rate"]) if w.get("avg_heart_rate") else None,
            source="apple_health",
            external_id=ext_id,
        ))

    # Parse heart rate readings
    for hr in data.get("heart_rate_readings", []):
        hr_time = hr.get("time", "00:00")
        bpm = int(hr.get("bpm", 0))
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
