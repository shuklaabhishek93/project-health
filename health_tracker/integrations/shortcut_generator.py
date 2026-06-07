"""
iOS Shortcut Generator - Produces step-by-step instructions and a ready-to-use
Apple Shortcut configuration for automatic daily health data export.

The generated Shortcut:
  1. Queries HealthKit for today's steps, heart rate, sleep, energy, etc.
  2. Queries HealthKit for today's workouts
  3. Builds a JSON payload
  4. Sends it via HTTP POST to the auto-sync server

The Shortcut is then attached to a Personal Automation that triggers daily
(e.g., at 11 PM), making the entire flow hands-free.
"""

import json
import os
import socket

from ..storage import ensure_data_dir


def get_local_ip() -> str:
    """Get the local network IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "YOUR_COMPUTER_IP"


def generate_shortcut_instructions(server_port: int = 8090, base_url: str | None = None) -> str:
    """
    Generate step-by-step instructions for creating the iOS Shortcut
    and Personal Automation for daily auto-sync.

    If *base_url* is provided (e.g. a Render URL), the /sync endpoint
    lives on that URL.  Otherwise it defaults to the local-network IP.
    """
    local_ip = get_local_ip()
    if base_url:
        server_url = f"{base_url.rstrip('/')}/sync"
    else:
        server_url = f"http://{local_ip}:{server_port}/sync"

    instructions = f"""
================================================================================
  iOS SHORTCUT SETUP — Simplified Health Sync
================================================================================

  Server URL: {server_url}

  Total actions: ~17.  The server handles all conversions (sleep
  calculation, distance units, field name mismatches).

================================================================================
  STEP-BY-STEP
================================================================================

  1. Open Shortcuts app → tap "+" → rename to "Health Sync"

  ── STEPS ─────────────────────────────────────────────────────────────────
  2. Add: Find Health Samples
       Type: Steps  |  Start Date: is today
  3. Add: Calculate Statistics
       Input: (auto-fills with Steps)  |  Operation: Sum

  ── ACTIVE ENERGY ─────────────────────────────────────────────────────────
  4. Add: Find Health Samples
       Type: Active Energy  |  Start Date: is today
  5. Add: Calculate Statistics → Sum

  ── RESTING ENERGY ────────────────────────────────────────────────────────
  6. Add: Find Health Samples
       Type: Resting Energy  |  Start Date: is today
  7. Add: Calculate Statistics → Sum

  ── WALKING + RUNNING DISTANCE ────────────────────────────────────────────
  8. Add: Find Health Samples
       Type: Walking + Running Distance  |  Start Date: is today
  9. Add: Calculate Statistics → Sum

  ── FLIGHTS CLIMBED ───────────────────────────────────────────────────────
  10. Add: Find Health Samples
        Type: Flights Climbed  |  Start Date: is today
  11. Add: Calculate Statistics → Sum

  ── SLEEP (server calculates hours from timestamps) ───────────────────────
  12. Add: Find Health Samples
        Type: Sleep Analysis  |  Start Date: is in the last 1 day
        Sort by: Start Date  |  Order: Oldest First  |  Limit: 1
  13. Add: Get Details of Health Sample → get Start Date
  14. Add: Format Date → Custom → yyyy-MM-dd HH:mm

  15. Add: Find Health Samples
        Type: Sleep Analysis  |  Start Date: is in the last 1 day
        Sort by: End Date  |  Order: Latest First  |  Limit: 1
  16. Add: Get Details of Health Sample → get End Date
  17. Add: Format Date → Custom → yyyy-MM-dd HH:mm

  ── BUILD & SEND ──────────────────────────────────────────────────────────
  18. Add: Dictionary
        Key              │ Value (tap field → pick variable)
        ─────────────────┼──────────────────────────────────
        date             │ (tap → Current Date, format yyyy-MM-dd)
        steps            │ (tap → Sum from action 3)
        active_energy    │ (tap → Sum from action 5)
        resting_energy   │ (tap → Sum from action 7)
        distance         │ (tap → Sum from action 9)
        flights_climbed  │ (tap → Sum from action 11)
        sleep_start      │ (tap → Formatted Date from action 14)
        sleep_end        │ (tap → Formatted Date from action 17)

  19. Add: Text (rename to "Server URL")
        Type ONLY: {server_url}

  20. Add: Get Contents of URL
        URL: tap field → pick "Server URL" variable (action 19)
        Method: POST
        Headers: Content-Type = application/json
        Request Body: File → pick Dictionary (action 18)

================================================================================
  DAILY AUTOMATION
================================================================================

  1. Shortcuts app → Automation tab → "+" → Personal Automation
  2. Choose "Time of Day" → 11:00 PM → Daily
  3. Run Shortcut → choose "Health Sync"
  4. Toggle OFF "Ask Before Running" → Done

================================================================================
  SETTINGS CHECK
================================================================================

  iPhone Settings → Shortcuts → turn ON "Allow Sharing Large Amounts of Data"
  iPhone Settings → Privacy → Health → Shortcuts → enable all data types

================================================================================
  TROUBLESHOOTING
================================================================================

  - "Rich Text to URL" error:
    Never paste the URL directly into "Get Contents of URL".
    Always use the Text variable from action 19.

  - Sleep shows 0:
    Make sure sleep Find action uses "is in the last 1 day" (not "is today")
    because sleep starts the previous night.

  - Flights/energy showing huge numbers:
    Check that "Start Date: is today" is set on that metric's Find action.

  - Test command:
    curl -X POST {server_url} -H "Content-Type: application/json" \\
      -d '{{"date":"2026-04-18","steps":5000,"sleep_start":"2026-04-17 23:00","sleep_end":"2026-04-18 06:30"}}'

================================================================================
"""
    return instructions


def generate_test_curl_command(server_port: int = 8090, base_url: str | None = None) -> str:
    """Generate a curl command to test the sync endpoint."""
    if base_url:
        url = f"{base_url.rstrip('/')}/sync"
    else:
        local_ip = get_local_ip()
        url = f"http://{local_ip}:{server_port}/sync"
    today = __import__("datetime").date.today().isoformat()

    return (
        f'curl -X POST {url} \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f'  -d \'{{\n'
        f'    "date": "{today}",\n'
        f'    "steps": 10500,\n'
        f'    "sleep_hours": 7.5,\n'
        f'    "active_energy": 520,\n'
        f'    "resting_energy": 1700,\n'
        f'    "distance_km": 8.2,\n'
        f'    "flights_climbed": 12,\n'
        f'    "heart_rate_readings": [\n'
        f'      {{"time": "07:00", "bpm": 62, "context": "morning"}},\n'
        f'      {{"time": "12:00", "bpm": 78, "context": "resting"}},\n'
        f'      {{"time": "18:00", "bpm": 85, "context": "evening"}}\n'
        f'    ],\n'
        f'    "workouts": [\n'
        f'      {{\n'
        f'        "type": "running",\n'
        f'        "duration_minutes": 35,\n'
        f'        "distance_km": 5.5,\n'
        f'        "calories": 380,\n'
        f'        "avg_heart_rate": 152,\n'
        f'        "start_time": "09:00"\n'
        f'      }}\n'
        f'    ]\n'
        f'  }}\'\n'
    )


def save_instructions_to_file(server_port: int = 8090) -> str:
    """Save the setup instructions to a file and return the path."""
    ensure_data_dir()
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
    filepath = os.path.join(data_dir, "ios_shortcut_setup.txt")

    instructions = generate_shortcut_instructions(server_port)
    with open(filepath, "w") as f:
        f.write(instructions)

    return os.path.abspath(filepath)
