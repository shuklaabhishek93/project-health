"""
Strava Integration - Fetch activities and heart rate data via Strava API.

Setup:
  1. Go to https://www.strava.com/settings/api and create an application
  2. Note your Client ID and Client Secret
  3. Run the authorization flow in this app to get an access token

This module fetches:
  - Activities (runs, rides, swims, etc.) with distance, duration, calories
  - Heart rate data from activity streams
  - Activity type mapping to our tracker types
"""

import json
import os
import time
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs

from ..models import Workout, HeartRateEntry, DailyRecord

# Try to import requests, provide helpful message if not installed
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

# Map Strava sport types to our workout types
STRAVA_SPORT_MAP = {
    "Run": "running",
    "Trail Run": "running",
    "Ride": "cycling",
    "Mountain Bike Ride": "cycling",
    "Gravel Ride": "cycling",
    "E-Bike Ride": "cycling",
    "Swim": "swimming",
    "Walk": "walking",
    "Hike": "walking",
    "Yoga": "yoga",
    "Weight Training": "weightlifting",
    "Workout": "hiit",
    "HIIT": "hiit",
    "CrossFit": "hiit",
    "Rowing": "rowing",
    "Elliptical": "elliptical",
    "Stair Stepper": "stair_climbing",
    "Pilates": "pilates",
    "Dance": "dancing",
    "Rock Climbing": "other",
    "Kayaking": "rowing",
    "Canoeing": "rowing",
    "Stand Up Paddling": "rowing",
    "Ice Skate": "other",
    "Inline Skate": "other",
    "Skateboard": "other",
    "Surf": "other",
    "Snowboard": "other",
    "Alpine Ski": "other",
    "Nordic Ski": "other",
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")


def get_token_path() -> str:
    """Get path to stored Strava token file."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "strava_token.json")


def check_requests_available() -> bool:
    """Check if the requests library is available."""
    if not HAS_REQUESTS:
        print("\n  ERROR: The 'requests' library is required for Strava integration.")
        print("  Install it with: pip install requests")
        return False
    return True


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to capture OAuth callback."""

    auth_code = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        OAuthCallbackHandler.auth_code = query.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h2>Authorization successful!</h2>"
                         b"<p>You can close this window and return to the terminal.</p>"
                         b"</body></html>")

    def log_message(self, format, *args):
        pass  # Suppress server logs


def authorize_strava(client_id: str, client_secret: str) -> Optional[dict]:
    """
    Run OAuth2 authorization flow for Strava.

    Opens browser for user consent, captures the callback, exchanges for tokens.
    """
    if not check_requests_available():
        return None

    redirect_uri = "http://localhost:8089/callback"
    scope = "read,activity:read_all"

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "approval_prompt": "auto",
    }

    auth_url = f"{STRAVA_AUTH_URL}?{urlencode(params)}"

    print(f"\n  Opening browser for Strava authorization...")
    print(f"  If the browser doesn't open, visit this URL:")
    print(f"  {auth_url}\n")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass  # Browser may not be available in all environments

    # Start local server to catch the callback
    print("  Waiting for authorization (listening on localhost:8089)...")
    server = HTTPServer(("localhost", 8089), OAuthCallbackHandler)
    server.timeout = 120  # 2 minute timeout
    server.handle_request()

    auth_code = OAuthCallbackHandler.auth_code
    if not auth_code:
        print("  ERROR: Did not receive authorization code.")
        return None

    # Exchange code for tokens
    print("  Exchanging authorization code for access token...")
    response = requests.post(STRAVA_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code",
    }, timeout=30)

    if response.status_code != 200:
        print(f"  ERROR: Token exchange failed: {response.text}")
        return None

    token_data = response.json()

    # Save token
    save_data = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_at": token_data["expires_at"],
        "client_id": client_id,
        "client_secret": client_secret,
    }
    with open(get_token_path(), "w") as f:
        json.dump(save_data, f, indent=2)

    print("  Authorization successful! Token saved.")
    return save_data


def save_strava_token(token_data: dict):
    """Persist a Strava token dict."""
    from ..db_storage import is_db_enabled, db_put
    if is_db_enabled():
        db_put("strava_token", token_data)
    else:
        with open(get_token_path(), "w") as f:
            json.dump(token_data, f, indent=2)


def load_strava_token() -> Optional[dict]:
    """Load saved Strava token, refreshing if expired."""
    if not check_requests_available():
        return None

    from ..db_storage import is_db_enabled, db_get
    if is_db_enabled():
        token_data = db_get("strava_token")
    else:
        token_path = get_token_path()
        if not os.path.exists(token_path):
            return None
        with open(token_path, "r") as f:
            token_data = json.load(f)

    if not token_data:
        return None

    # Check if token is expired
    if token_data.get("expires_at", 0) < time.time():
        response = requests.post(STRAVA_TOKEN_URL, data={
            "client_id": token_data["client_id"],
            "client_secret": token_data["client_secret"],
            "refresh_token": token_data["refresh_token"],
            "grant_type": "refresh_token",
        }, timeout=30)

        if response.status_code != 200:
            return None

        new_data = response.json()
        token_data["access_token"] = new_data["access_token"]
        token_data["refresh_token"] = new_data["refresh_token"]
        token_data["expires_at"] = new_data["expires_at"]

        save_strava_token(token_data)

    return token_data


def fetch_strava_activities(
    access_token: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    per_page: int = 50,
) -> list[dict]:
    """
    Fetch activities from Strava API.

    Args:
        access_token: Strava API access token
        after: Only activities after this date (YYYY-MM-DD)
        before: Only activities before this date (YYYY-MM-DD)
        per_page: Number of activities per page (max 200)

    Returns:
        List of activity dictionaries from Strava API
    """
    if not check_requests_available():
        return []

    headers = {"Authorization": f"Bearer {access_token}"}
    params: dict = {"per_page": min(per_page, 200)}

    if after:
        dt = datetime.strptime(after, "%Y-%m-%d")
        params["after"] = int(dt.timestamp())
    if before:
        dt = datetime.strptime(before, "%Y-%m-%d")
        params["before"] = int(dt.timestamp())

    all_activities = []
    page = 1

    while True:
        params["page"] = page
        response = requests.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code == 401:
            print("  ERROR: Strava token is invalid. Please re-authorize.")
            return []
        if response.status_code == 429:
            print("  Rate limited by Strava. Waiting 60 seconds...")
            time.sleep(60)
            continue
        if response.status_code != 200:
            print(f"  ERROR: Strava API error {response.status_code}: {response.text}")
            break

        activities = response.json()
        if not activities:
            break

        all_activities.extend(activities)
        print(f"    Fetched page {page} ({len(activities)} activities)")

        if len(activities) < per_page:
            break
        page += 1

    return all_activities


def fetch_activity_heart_rate(access_token: str, activity_id: int) -> list[dict]:
    """Fetch heart rate stream data for a specific activity."""
    if not check_requests_available():
        return []

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"keys": "heartrate,time", "key_type": "time"}

    response = requests.get(
        f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
        headers=headers,
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        return []

    streams = {s["type"]: s["data"] for s in response.json()}
    if "heartrate" not in streams:
        return []

    return streams["heartrate"]


def import_strava(
    access_token: str,
    date_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fetch_heart_rates: bool = True,
) -> dict[str, DailyRecord]:
    """
    Import activities from Strava and convert to DailyRecords.

    Args:
        access_token: Strava API access token
        date_filter: Import only this specific date
        start_date: Import activities on or after this date
        end_date: Import activities on or before this date
        fetch_heart_rates: Whether to fetch detailed HR data per activity

    Returns:
        Dictionary mapping date strings to DailyRecord objects
    """
    print("  Fetching activities from Strava...")

    effective_after = date_filter or start_date
    effective_before = date_filter or end_date

    activities = fetch_strava_activities(access_token, after=effective_after, before=effective_before)
    print(f"  Found {len(activities)} activities")

    records: dict[str, DailyRecord] = {}

    for i, activity in enumerate(activities):
        # Parse activity date
        start_time = activity.get("start_date_local", "")
        if not start_time:
            continue

        dt = datetime.strptime(start_time[:19], "%Y-%m-%dT%H:%M:%S")
        activity_date = dt.strftime("%Y-%m-%d")
        activity_time = dt.strftime("%H:%M")

        # Apply date filter
        if date_filter and activity_date != date_filter:
            continue

        # Get or create daily record
        if activity_date not in records:
            records[activity_date] = DailyRecord(date=activity_date)

        record = records[activity_date]

        # Map activity type
        sport_type = activity.get("sport_type", activity.get("type", "Workout"))
        mapped_type = STRAVA_SPORT_MAP.get(sport_type, "other")

        # Duration in minutes
        duration_seconds = activity.get("moving_time", activity.get("elapsed_time", 0))
        duration_minutes = int(duration_seconds / 60)

        # Distance in km
        distance_m = activity.get("distance", 0)
        distance_km = round(distance_m / 1000, 2) if distance_m > 0 else None

        # Calories (Strava provides kilojoules for rides, estimated calories otherwise)
        calories = activity.get("calories", 0)
        if not calories and activity.get("kilojoules"):
            calories = activity["kilojoules"] * 0.239  # kJ to kcal approximation

        # Average heart rate
        avg_hr = activity.get("average_heartrate")
        if avg_hr:
            avg_hr = int(avg_hr)

        # Determine intensity from average HR or speed
        if activity.get("average_heartrate"):
            hr = activity["average_heartrate"]
            if hr > 160:
                intensity = "vigorous"
            elif hr > 130:
                intensity = "moderate"
            else:
                intensity = "light"
        elif activity.get("average_speed", 0) > 0:
            # Rough speed-based estimate
            speed_kmh = activity["average_speed"] * 3.6
            if speed_kmh > 15:
                intensity = "vigorous"
            elif speed_kmh > 8:
                intensity = "moderate"
            else:
                intensity = "light"
        else:
            intensity = "moderate"

        strava_id = str(activity.get("id", ""))
        external_id = f"strava_{strava_id}"

        # Check for duplicates
        if any(w.external_id == external_id for w in record.workouts):
            continue

        workout = Workout(
            date=activity_date,
            workout_type=mapped_type,
            duration_minutes=duration_minutes,
            intensity=intensity,
            distance_km=distance_km,
            calories_reported=round(calories, 1) if calories else None,
            avg_heart_rate=avg_hr,
            source="strava",
            external_id=external_id,
            notes=activity.get("name", ""),
        )
        record.workouts.append(workout)

        # Fetch detailed heart rate data
        if fetch_heart_rates and activity.get("has_heartrate") and strava_id:
            print(f"    Fetching HR data for: {activity.get('name', 'activity')}...")
            hr_data = fetch_activity_heart_rate(access_token, int(strava_id))

            if hr_data:
                # Sample HR readings (take every Nth reading to get ~10 per workout)
                total_readings = len(hr_data)
                sample_step = max(1, total_readings // 10)
                sampled = hr_data[::sample_step][:10]

                for j, hr_bpm in enumerate(sampled):
                    # Calculate approximate time offset
                    offset_minutes = (j * sample_step * duration_seconds / total_readings) / 60
                    hr_dt = dt.replace(
                        minute=min(59, dt.minute + int(offset_minutes))
                    )
                    hr_time = hr_dt.strftime("%H:%M")

                    hr_id = f"strava_hr_{strava_id}_{j}"

                    if not any(h.external_id == hr_id for h in record.heart_rate_readings):
                        record.heart_rate_readings.append(HeartRateEntry(
                            date=activity_date,
                            time=hr_time,
                            heart_rate_bpm=int(hr_bpm),
                            context="during_workout",
                            source="strava",
                            external_id=hr_id,
                        ))

        print(f"    [{i + 1}/{len(activities)}] {activity.get('name', 'Activity')} - "
              f"{mapped_type}, {duration_minutes}min"
              f"{f', {round(distance_km * 0.621371, 2)}mi' if distance_km else ''}"
              f"{f', {avg_hr}bpm avg' if avg_hr else ''}")

    print(f"\n  Strava import complete!")
    print(f"    Activities imported: {len(activities)}")
    print(f"    Days with data:     {len(records)}")

    return records
