"""Flask Web UI for Health & Workout Tracker."""

import json
import os
import threading
from datetime import date, timedelta

from flask import Flask, render_template, request, jsonify, redirect, url_for

from health_tracker.models import (
    UserProfile, HealthHabit, Workout, HeartRateEntry, DailyRecord,
)
from health_tracker.calculator import (
    calculate_calories_burned, calculate_bmr, calculate_steps_calories,
    analyze_heart_rate, get_age_based_recommendations,
)
from health_tracker.storage import (
    save_profile, load_profile, save_daily_record, load_daily_record,
    list_all_records, ensure_data_dir,
)
from health_tracker.summary import (
    generate_daily_summary, calculate_health_score, get_score_rating,
)
from health_tracker.auto_sync import (
    AutoSyncDaemon, load_config, save_config, is_daemon_running,
    get_daemon_pid, stop_daemon, LOG_PATH,
)
from health_tracker.integrations.sync import sync_imported_records
from health_tracker.integrations.shortcut_generator import (
    generate_shortcut_instructions, generate_test_curl_command, get_local_ip,
)
from health_tracker.integrations.strava import load_strava_token, import_strava

app = Flask(__name__)
ensure_data_dir()

# Keep a reference to the daemon when started from the web UI
_daemon_instance: AutoSyncDaemon | None = None


# ---------------------------------------------------------------------------
# Page Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    profile = load_profile()
    return render_template("index.html", profile=profile, today=date.today().isoformat())


# ---------------------------------------------------------------------------
# Profile API
# ---------------------------------------------------------------------------

@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    profile = load_profile()
    if not profile:
        return jsonify({"exists": False}), 200
    return jsonify({
        "exists": True,
        "name": profile.name,
        "age": profile.age,
        "weight_kg": profile.weight_kg,
        "height_cm": profile.height_cm,
        "gender": profile.gender,
        "bmi": profile.bmi,
        "max_heart_rate": profile.max_heart_rate,
    })


@app.route("/api/profile", methods=["POST"])
def api_save_profile():
    data = request.json
    profile = UserProfile(
        name=data["name"],
        age=int(data["age"]),
        weight_kg=float(data["weight_kg"]),
        height_cm=float(data["height_cm"]),
        gender=data["gender"],
    )
    save_profile(profile)
    return jsonify({"status": "ok", "bmi": profile.bmi, "max_heart_rate": profile.max_heart_rate})


# ---------------------------------------------------------------------------
# Daemon / Auto-Sync API
# ---------------------------------------------------------------------------

@app.route("/api/daemon/status", methods=["GET"])
def api_daemon_status():
    global _daemon_instance
    config = load_config()
    running = is_daemon_running()
    pid = get_daemon_pid()
    local_ip = get_local_ip()
    srv = config["apple_health_server"]
    fw = config["folder_watcher"]
    st = config["strava"]

    return jsonify({
        "running": running,
        "pid": pid,
        "apple_health_server": {
            "enabled": srv["enabled"],
            "port": srv["port"],
            "url": f"http://{local_ip}:{srv['port']}/sync",
        },
        "folder_watcher": {
            "enabled": fw["enabled"],
            "watch_dir": fw.get("watch_dir", ""),
            "poll_interval": fw.get("poll_interval_seconds", 60),
        },
        "strava": {
            "enabled": st["enabled"],
            "sync_time": f"{st['sync_hour']:02d}:{st['sync_minute']:02d}",
            "fetch_heart_rates": st.get("fetch_heart_rates", True),
            "last_sync": config.get("last_strava_sync"),
        },
    })


@app.route("/api/daemon/start", methods=["POST"])
def api_daemon_start():
    global _daemon_instance
    if is_daemon_running():
        return jsonify({"status": "already_running", "pid": get_daemon_pid()})

    config = load_config()
    config["enabled"] = True
    save_config(config)

    _daemon_instance = AutoSyncDaemon(config)
    t = threading.Thread(target=_daemon_instance.run_forever, daemon=True)
    t.start()

    import time
    time.sleep(1)
    return jsonify({"status": "started", "pid": get_daemon_pid()})


@app.route("/api/daemon/stop", methods=["POST"])
def api_daemon_stop():
    global _daemon_instance
    if _daemon_instance:
        _daemon_instance.stop()
        _daemon_instance = None
    else:
        stop_daemon()
    return jsonify({"status": "stopped"})


@app.route("/api/daemon/config", methods=["GET"])
def api_daemon_config_get():
    return jsonify(load_config())


@app.route("/api/daemon/config", methods=["POST"])
def api_daemon_config_save():
    data = request.json
    config = load_config()
    # Merge incoming data
    for key in ("apple_health_server", "folder_watcher", "strava"):
        if key in data:
            config[key].update(data[key])
    save_config(config)
    return jsonify({"status": "ok"})


@app.route("/api/daemon/log", methods=["GET"])
def api_daemon_log():
    lines_count = request.args.get("lines", 50, type=int)
    if not os.path.exists(LOG_PATH):
        return jsonify({"lines": [], "total": 0})
    with open(LOG_PATH, "r") as f:
        all_lines = f.readlines()
    return jsonify({
        "lines": [l.rstrip() for l in all_lines[-lines_count:]],
        "total": len(all_lines),
    })


# ---------------------------------------------------------------------------
# iOS Shortcut Guide
# ---------------------------------------------------------------------------

@app.route("/api/shortcut/instructions", methods=["GET"])
def api_shortcut_instructions():
    config = load_config()
    port = config["apple_health_server"]["port"]
    instructions = generate_shortcut_instructions(port)
    curl_cmd = generate_test_curl_command(port)
    local_ip = get_local_ip()
    return jsonify({
        "instructions": instructions,
        "curl_command": curl_cmd,
        "server_url": f"http://{local_ip}:{port}/sync",
        "local_ip": local_ip,
    })


# ---------------------------------------------------------------------------
# Strava API
# ---------------------------------------------------------------------------

@app.route("/api/strava/status", methods=["GET"])
def api_strava_status():
    token = load_strava_token()
    return jsonify({"connected": token is not None})


@app.route("/api/strava/sync", methods=["POST"])
def api_strava_sync():
    token_data = load_strava_token()
    if not token_data:
        return jsonify({"error": "Strava not connected"}), 400

    days = request.json.get("days", 7) if request.json else 7
    start = (date.today() - timedelta(days=days)).isoformat()

    imported = import_strava(
        token_data["access_token"],
        start_date=start,
        fetch_heart_rates=True,
    )
    if imported:
        updated, created = sync_imported_records(imported)
        config = load_config()
        config["last_strava_sync"] = date.today().isoformat()
        save_config(config)
        return jsonify({"status": "ok", "days_updated": updated, "days_created": created})
    return jsonify({"status": "ok", "days_updated": 0, "days_created": 0})


# ---------------------------------------------------------------------------
# Daily Records & Analytics API
# ---------------------------------------------------------------------------

@app.route("/api/records", methods=["GET"])
def api_list_records():
    return jsonify({"dates": list_all_records()})


@app.route("/api/records/<record_date>", methods=["GET"])
def api_get_record(record_date):
    record = load_daily_record(record_date)
    if not record:
        return jsonify({"error": "not found"}), 404
    return jsonify(_record_to_dict(record))


@app.route("/api/records/<record_date>/summary", methods=["GET"])
def api_get_summary(record_date):
    profile = load_profile()
    if not profile:
        return jsonify({"error": "No profile configured"}), 400
    record = load_daily_record(record_date)
    if not record:
        return jsonify({"error": "No record for this date"}), 404

    summary_text = generate_daily_summary(profile, record)
    save_daily_record(record)

    score = calculate_health_score(profile, record)
    rating = get_score_rating(score)
    bmr = calculate_bmr(profile)

    return jsonify({
        "date": record_date,
        "summary_text": summary_text,
        "score": score,
        "rating": rating,
        "bmr": bmr,
        "total_calories_burned": record.total_calories_burned,
    })


@app.route("/api/analytics/range", methods=["GET"])
def api_analytics_range():
    """Get analytics data for a date range (for charts)."""
    profile = load_profile()
    if not profile:
        return jsonify({"error": "No profile"}), 400

    days = request.args.get("days", 7, type=int)
    end = date.today()
    start = end - timedelta(days=days - 1)

    results = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        record = load_daily_record(d)
        if not record:
            results.append({"date": d, "has_data": False})
            continue

        # Compute metrics
        score = calculate_health_score(profile, record)
        bmr = calculate_bmr(profile)

        workout_calories = 0.0
        total_workout_min = 0
        workout_types = []
        for w in record.workouts:
            if w.calories_reported and w.calories_reported > 0:
                workout_calories += w.calories_reported
            else:
                workout_calories += calculate_calories_burned(profile, w)
            total_workout_min += w.duration_minutes
            workout_types.append(w.workout_type)

        step_cal = 0.0
        steps = 0
        sleep = 0.0
        water = 0.0
        active_energy = 0.0
        if record.health_habits:
            steps = record.health_habits.steps
            sleep = record.health_habits.sleep_hours
            water = record.health_habits.water_intake_liters
            active_energy = record.health_habits.active_energy_burned
            step_cal = calculate_steps_calories(profile, steps)

        hr_values = [r.heart_rate_bpm for r in record.heart_rate_readings]
        avg_hr = sum(hr_values) / len(hr_values) if hr_values else 0
        min_hr = min(hr_values) if hr_values else 0
        max_hr = max(hr_values) if hr_values else 0

        total_cal = bmr + workout_calories + step_cal

        sources = set()
        for w in record.workouts:
            sources.add(w.source)
        for hr in record.heart_rate_readings:
            sources.add(hr.source)

        results.append({
            "date": d,
            "has_data": True,
            "score": score,
            "steps": steps,
            "sleep_hours": sleep,
            "water_liters": water,
            "workout_minutes": total_workout_min,
            "workout_calories": round(workout_calories, 1),
            "workout_types": workout_types,
            "step_calories": round(step_cal, 1),
            "bmr": bmr,
            "total_calories": round(total_cal, 1),
            "active_energy_device": active_energy,
            "avg_heart_rate": round(avg_hr),
            "min_heart_rate": min_hr,
            "max_heart_rate": max_hr,
            "hr_readings_count": len(hr_values),
            "sources": list(sources),
            "num_workouts": len(record.workouts),
        })

    # Aggregate totals
    data_days = [r for r in results if r["has_data"]]
    totals = {
        "total_days": len(data_days),
        "avg_score": round(sum(r["score"] for r in data_days) / len(data_days), 1) if data_days else 0,
        "avg_steps": round(sum(r["steps"] for r in data_days) / len(data_days)) if data_days else 0,
        "avg_sleep": round(sum(r["sleep_hours"] for r in data_days) / len(data_days), 1) if data_days else 0,
        "total_workouts": sum(r["num_workouts"] for r in data_days),
        "total_workout_minutes": sum(r["workout_minutes"] for r in data_days),
        "total_calories_burned": round(sum(r["total_calories"] for r in data_days), 1),
    }

    recs = get_age_based_recommendations(profile)

    return jsonify({
        "profile": {
            "name": profile.name,
            "age": profile.age,
            "bmi": profile.bmi,
            "max_heart_rate": profile.max_heart_rate,
        },
        "recommendations": recs,
        "days": results,
        "totals": totals,
    })


@app.route("/api/analytics/heart_rate/<record_date>", methods=["GET"])
def api_heart_rate_detail(record_date):
    """Get detailed heart rate data for a specific day."""
    profile = load_profile()
    if not profile:
        return jsonify({"error": "No profile"}), 400
    record = load_daily_record(record_date)
    if not record:
        return jsonify({"error": "No record"}), 404

    readings = []
    for hr in record.heart_rate_readings:
        analysis = analyze_heart_rate(profile, hr)
        readings.append({
            "time": hr.time,
            "bpm": hr.heart_rate_bpm,
            "context": hr.context,
            "source": hr.source,
            "zone": analysis["zone"],
            "pct_of_max": analysis["percentage_of_max"],
            "status": analysis["status"],
            "recommendation": analysis["recommendation"],
        })
    return jsonify({
        "date": record_date,
        "max_hr": profile.max_heart_rate,
        "zones": profile.heart_rate_zones,
        "readings": readings,
    })


@app.route("/api/analytics/workouts/<record_date>", methods=["GET"])
def api_workout_detail(record_date):
    """Get detailed workout data for a specific day."""
    profile = load_profile()
    if not profile:
        return jsonify({"error": "No profile"}), 400
    record = load_daily_record(record_date)
    if not record:
        return jsonify({"error": "No record"}), 404

    workouts = []
    for w in record.workouts:
        cal = w.calories_reported if (w.calories_reported and w.calories_reported > 0) else calculate_calories_burned(profile, w)
        workouts.append({
            "type": w.workout_type,
            "duration_minutes": w.duration_minutes,
            "intensity": w.intensity,
            "distance_km": w.distance_km,
            "calories": round(cal, 1),
            "calories_source": "device" if w.calories_reported else "estimated",
            "avg_heart_rate": w.avg_heart_rate,
            "source": w.source,
            "notes": w.notes,
        })
    return jsonify({"date": record_date, "workouts": workouts})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_to_dict(record: DailyRecord) -> dict:
    d: dict = {"date": record.date, "total_calories_burned": record.total_calories_burned}
    if record.health_habits:
        h = record.health_habits
        d["health_habits"] = {
            "water_liters": h.water_intake_liters,
            "sleep_hours": h.sleep_hours,
            "steps": h.steps,
            "fruits_vegs": h.fruits_vegetables_servings,
            "meditation_min": h.meditation_minutes,
            "active_energy": h.active_energy_burned,
            "resting_energy": h.resting_energy_burned,
            "flights_climbed": h.flights_climbed,
            "distance_km": h.distance_walked_km,
        }
    d["workouts"] = [{
        "type": w.workout_type, "duration": w.duration_minutes,
        "intensity": w.intensity, "source": w.source,
        "calories": w.calories_reported, "distance_km": w.distance_km,
    } for w in record.workouts]
    d["heart_rate"] = [{
        "time": hr.time, "bpm": hr.heart_rate_bpm,
        "context": hr.context, "source": hr.source,
    } for hr in record.heart_rate_readings]
    return d


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
