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


def generate_shortcut_instructions(server_port: int = 8090) -> str:
    """
    Generate step-by-step instructions for creating the iOS Shortcut
    and Personal Automation for daily auto-sync.
    """
    local_ip = get_local_ip()
    server_url = f"http://{local_ip}:{server_port}/sync"

    instructions = f"""
================================================================================
  iOS SHORTCUT SETUP - Automatic Daily Health Data Sync
================================================================================

  This will set up your iPhone to automatically send health data to this
  tracker every day — no manual export needed.

  Server URL: {server_url}
  (Your computer and iPhone must be on the same Wi-Fi network)

================================================================================
  PART 1: CREATE THE SHORTCUT
================================================================================

  1. Open the "Shortcuts" app on your iPhone
  2. Tap the "+" button to create a new shortcut
  3. Tap the name at top and rename it to "Health Data Sync"

  Now add these actions IN ORDER (use the search bar to find each):

  --- ACTION 1: Get Today's Date ---
  Search: "Date"
  Choose: "Date" (under Dates)
  Set to: "Current Date"

  --- ACTION 2: Format Date ---
  Search: "Format Date"
  Set format to: "Custom"
  Set custom format to: yyyy-MM-dd

  --- ACTION 3: Find Health Samples - Steps ---
  Search: "Find Health Samples"
  Type: "Steps"
  Start Date: "is today"
  Group By: "Day"

  --- ACTION 4: Find Health Samples - Heart Rate ---
  Search: "Find Health Samples" (add another)
  Type: "Heart Rate"
  Start Date: "is today"
  Sort By: "Start Date"
  Limit: 24

  --- ACTION 5: Find Health Samples - Sleep ---
  Search: "Find Health Samples" (add another)
  Type: "Sleep Analysis"
  Start Date: "is in the last 1 day"

  --- ACTION 6: Find Health Samples - Active Energy ---
  Search: "Find Health Samples" (add another)
  Type: "Active Energy"
  Start Date: "is today"
  Group By: "Day"

  --- ACTION 7: Find Health Samples - Resting Energy ---
  Search: "Find Health Samples" (add another)
  Type: "Resting Energy"
  Start Date: "is today"
  Group By: "Day"

  --- ACTION 8: Find Health Samples - Walking Distance ---
  Search: "Find Health Samples" (add another)
  Type: "Walking + Running Distance"
  Start Date: "is today"
  Group By: "Day"

  --- ACTION 9: Find Health Samples - Flights Climbed ---
  Search: "Find Health Samples" (add another)
  Type: "Flights Climbed"
  Start Date: "is today"
  Group By: "Day"

  --- ACTION 10: Find Workouts ---
  Search: "Find Health Samples" (add another)
  Type: "Workout"
  Start Date: "is today"

  --- ACTION 11: Build JSON (Text Action) ---
  Search: "Text"
  Paste this template (the Shortcut will fill in the variables):

  {{
    "date": "[Formatted Date]",
    "steps": [Steps Value],
    "sleep_hours": [Sleep Duration in Hours],
    "active_energy": [Active Energy Value],
    "resting_energy": [Resting Energy Value],
    "distance_km": [Walking Distance Value],
    "flights_climbed": [Flights Value],
    "heart_rate_readings": [Heart Rate Samples as JSON],
    "workouts": [Workout Samples as JSON]
  }}

  NOTE: Tap on each placeholder like [Steps Value] and select the
  corresponding variable from the previous actions.

  --- ACTION 12: Get Contents of URL (HTTP POST) ---
  Search: "Get Contents of URL"
  URL: {server_url}
  Method: POST
  Headers:
    Content-Type: application/json
  Request Body: "File"
  File: Select the "Text" output from Action 11

================================================================================
  PART 2: SIMPLIFIED ALTERNATIVE SHORTCUT
================================================================================

  If the above is too complex, use this simpler version that sends the most
  important data points:

  1. Create new shortcut named "Health Sync Simple"

  2. Add action: "Text"
     Content (copy exactly):

  {{
    "date": "{{{{Current Date:yyyy-MM-dd}}}}",
    "steps": {{{{Health Samples: Steps (today, sum)}}}},
    "sleep_hours": {{{{Health Samples: Sleep Analysis (last 1 day, sum hours)}}}},
    "active_energy": {{{{Health Samples: Active Energy (today, sum)}}}},
    "resting_energy": {{{{Health Samples: Resting Energy (today, sum)}}}},
    "distance_km": {{{{Health Samples: Walking Distance (today, sum)}}}},
    "flights_climbed": {{{{Health Samples: Flights Climbed (today, sum)}}}},
    "heart_rate_readings": [],
    "workouts": []
  }}

  3. Add action: "Get Contents of URL"
     URL: {server_url}
     Method: POST
     Headers: Content-Type = application/json
     Body: File → select Text from step 2

================================================================================
  PART 3: SET UP DAILY AUTOMATION
================================================================================

  This makes the Shortcut run automatically every day:

  1. Open "Shortcuts" app → tap "Automation" tab at bottom
  2. Tap "+" → "Personal Automation"
  3. Choose "Time of Day"
  4. Set time to 11:00 PM (or whenever you want daily sync)
  5. Set repeat to "Daily"
  6. Tap "Next"
  7. Search and select "Run Shortcut"
  8. Choose "Health Data Sync" (the shortcut from Part 1 or 2)
  9. IMPORTANT: Toggle OFF "Ask Before Running"
     (This makes it fully automatic — no confirmation needed)
  10. Tap "Done"

================================================================================
  PART 4: VERIFY THE SETUP
================================================================================

  1. Make sure the auto-sync daemon is running on this computer:
     python main.py → Option 12 → Start Auto-Sync

  2. On your iPhone, open the "Health Data Sync" shortcut and run it manually
     once to test. You should see output like:
     {{"status": "success", "date": "2026-04-12", "steps": 10500, ...}}

  3. Check the sync log on your computer:
     View in app: Option 12 → View Sync Log
     Or directly: cat data/auto_sync.log

  4. From tomorrow, the shortcut will run daily at your scheduled time!

================================================================================
  TROUBLESHOOTING
================================================================================

  - "Could not connect to server":
    Make sure both devices are on the same Wi-Fi network.
    Check the server is running (Option 12 → Status).
    Try using your computer's IP: {local_ip}

  - "Health permission denied":
    Go to iPhone Settings → Privacy & Security → Health →
    Shortcuts → Enable all data types.

  - Shortcut doesn't run automatically:
    Check Automation → ensure "Ask Before Running" is OFF.
    Check Low Power Mode is off (it can delay automations).

  - No data appearing:
    Check data/auto_sync.log for errors.
    Try a manual POST: curl -X POST {server_url} \\
      -H "Content-Type: application/json" \\
      -d '{{"date":"2026-04-12","steps":5000,"sleep_hours":7}}'

================================================================================
"""
    return instructions


def generate_test_curl_command(server_port: int = 8090) -> str:
    """Generate a curl command to test the sync endpoint."""
    local_ip = get_local_ip()
    today = __import__("datetime").date.today().isoformat()

    return (
        f'curl -X POST http://{local_ip}:{server_port}/sync \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f'  -d \'{{\n'
        f'    "date": "{today}",\n'
        f'    "steps": 10500,\n'
        f'    "sleep_hours": 7.5,\n'
        f'    "active_energy": 520,\n'
        f'    "resting_energy": 1700,\n'
        f'    "distance_km": 8.2,\n'
        f'    "flights_climbed": 12,\n'
        f'    "water_ml": 2500,\n'
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
