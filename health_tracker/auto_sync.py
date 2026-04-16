"""
Auto-Sync Daemon - Automatically imports health data daily without human intervention.

Components:
  1. Apple Health HTTP Server - Receives data pushed from iOS Shortcuts
  2. Folder Watcher - Monitors a directory for Apple Health XML exports
  3. Strava Scheduler - Polls Strava API on a daily schedule

The daemon runs as a background process. It can be started from the CLI
(option 12) or via: python -m health_tracker.auto_sync

Configuration is stored in data/sync_config.json.
"""

import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import date, datetime, timedelta
from typing import Optional

from .storage import ensure_data_dir

logger = logging.getLogger("auto_sync")

# Base data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CONFIG_PATH = os.path.join(DATA_DIR, "sync_config.json")
PID_PATH = os.path.join(DATA_DIR, "auto_sync.pid")
LOG_PATH = os.path.join(DATA_DIR, "auto_sync.log")

DEFAULT_CONFIG = {
    "enabled": False,
    "apple_health_server": {
        "enabled": True,
        "host": "0.0.0.0",
        "port": 8090,
    },
    "folder_watcher": {
        "enabled": False,
        "watch_dir": "",
        "poll_interval_seconds": 60,
    },
    "strava": {
        "enabled": True,
        "sync_hour": 23,
        "sync_minute": 0,
        "fetch_heart_rates": True,
    },
    "last_strava_sync": None,
}


def load_config() -> dict:
    """Load sync configuration, creating defaults if needed."""
    ensure_data_dir()
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            saved = json.load(f)
        # Merge with defaults (in case new fields were added)
        config = DEFAULT_CONFIG.copy()
        for key, value in saved.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                config[key].update(value)
            else:
                config[key] = value
        return config
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save sync configuration."""
    ensure_data_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def setup_logging():
    """Configure logging to file and console."""
    ensure_data_dir()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH),
            logging.StreamHandler(sys.stdout),
        ],
    )


class AutoSyncDaemon:
    """Main daemon that orchestrates all auto-sync components."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        self._stop_event = threading.Event()
        self._apple_server = None
        self._folder_watcher = None
        self._strava_thread: Optional[threading.Thread] = None

    def start(self):
        """Start all enabled sync components."""
        setup_logging()
        logger.info("=" * 50)
        logger.info("Auto-Sync Daemon starting...")
        logger.info("=" * 50)

        self._write_pid()

        # Start Apple Health HTTP server
        if self.config["apple_health_server"]["enabled"]:
            self._start_apple_server()

        # Start folder watcher
        if self.config["folder_watcher"]["enabled"]:
            self._start_folder_watcher()

        # Start Strava scheduler
        if self.config["strava"]["enabled"]:
            self._start_strava_scheduler()

        logger.info("Auto-Sync Daemon is running. Press Ctrl+C to stop.")

    def run_forever(self):
        """Start and block until stopped."""
        self.start()

        # Handle signals for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Stop all sync components."""
        logger.info("Auto-Sync Daemon stopping...")
        self._stop_event.set()

        if self._apple_server:
            self._apple_server.stop()

        if self._folder_watcher:
            self._folder_watcher.stop()

        self._remove_pid()
        logger.info("Auto-Sync Daemon stopped.")

    def status(self) -> dict:
        """Get status of all components."""
        return {
            "running": not self._stop_event.is_set(),
            "apple_health_server": {
                "enabled": self.config["apple_health_server"]["enabled"],
                "running": self._apple_server.is_running if self._apple_server else False,
                "port": self.config["apple_health_server"]["port"],
            },
            "folder_watcher": {
                "enabled": self.config["folder_watcher"]["enabled"],
                "running": self._folder_watcher.is_running if self._folder_watcher else False,
                "watch_dir": self.config["folder_watcher"]["watch_dir"],
            },
            "strava": {
                "enabled": self.config["strava"]["enabled"],
                "running": self._strava_thread.is_alive() if self._strava_thread else False,
                "sync_time": f"{self.config['strava']['sync_hour']:02d}:{self.config['strava']['sync_minute']:02d}",
                "last_sync": self.config.get("last_strava_sync"),
            },
        }

    # --- Apple Health Server ---

    def _start_apple_server(self):
        from .integrations.apple_health_server import AppleHealthServer

        cfg = self.config["apple_health_server"]
        self._apple_server = AppleHealthServer(
            host=cfg.get("host", "0.0.0.0"),
            port=cfg.get("port", 8090),
        )
        self._apple_server.start()

    # --- Folder Watcher ---

    def _start_folder_watcher(self):
        from .integrations.folder_watcher import HealthExportWatcher

        cfg = self.config["folder_watcher"]
        watch_dir = cfg.get("watch_dir", "")

        if not watch_dir:
            logger.warning("Folder watcher enabled but no watch_dir configured. Skipping.")
            return

        self._folder_watcher = HealthExportWatcher(
            watch_dir=watch_dir,
            poll_interval=cfg.get("poll_interval_seconds", 60),
        )
        self._folder_watcher.start()

    # --- Strava Scheduler ---

    def _start_strava_scheduler(self):
        self._strava_thread = threading.Thread(target=self._strava_schedule_loop, daemon=True)
        self._strava_thread.start()

    def _strava_schedule_loop(self):
        """Run Strava sync at the configured daily time."""
        logger.info(
            f"Strava scheduler active. Will sync daily at "
            f"{self.config['strava']['sync_hour']:02d}:"
            f"{self.config['strava']['sync_minute']:02d}"
        )

        # Run an initial sync on startup if we haven't synced today
        last_sync = self.config.get("last_strava_sync")
        today = date.today().isoformat()
        if last_sync != today:
            logger.info("Running initial Strava sync (haven't synced today)...")
            self._run_strava_sync()

        while not self._stop_event.is_set():
            now = datetime.now()
            target_hour = self.config["strava"]["sync_hour"]
            target_minute = self.config["strava"]["sync_minute"]

            # Calculate next sync time
            target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logger.debug(f"Next Strava sync in {wait_seconds:.0f} seconds at {target}")

            # Wait until target time or stop event
            if self._stop_event.wait(timeout=min(wait_seconds, 300)):
                break  # Stop event was set

            # Check if it's time to sync
            now = datetime.now()
            if (now.hour == target_hour and
                    now.minute >= target_minute and
                    self.config.get("last_strava_sync") != now.strftime("%Y-%m-%d")):
                self._run_strava_sync()

    def _run_strava_sync(self):
        """Execute a Strava sync for today's data."""
        try:
            from .integrations.strava import load_strava_token, import_strava
            from .integrations.sync import sync_imported_records

            token_data = load_strava_token()
            if not token_data:
                logger.warning("Strava sync skipped: No token configured. Run manual setup first.")
                return

            access_token = token_data["access_token"]

            # Fetch activities from the last 2 days to catch any late-posted activities
            start_date = (date.today() - timedelta(days=2)).isoformat()

            logger.info(f"Fetching Strava activities since {start_date}...")
            imported = import_strava(
                access_token,
                start_date=start_date,
                fetch_heart_rates=self.config["strava"].get("fetch_heart_rates", True),
            )

            if imported:
                updated, created = sync_imported_records(imported)
                logger.info(f"Strava sync done: {updated} days updated, {created} days created")
            else:
                logger.info("Strava sync: No new activities")

            # Update last sync date
            self.config["last_strava_sync"] = date.today().isoformat()
            save_config(self.config)

        except Exception as e:
            logger.error(f"Strava sync failed: {e}", exc_info=True)

    # --- PID Management ---

    def _write_pid(self):
        ensure_data_dir()
        with open(PID_PATH, "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid(self):
        if os.path.exists(PID_PATH):
            try:
                os.unlink(PID_PATH)
            except OSError:
                pass


def _is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive (cross-platform)."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        SYNCHRONIZE = 0x00100000
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def is_daemon_running() -> bool:
    """Check if the auto-sync daemon is already running."""
    if not os.path.exists(PID_PATH):
        return False
    try:
        with open(PID_PATH, "r") as f:
            pid = int(f.read().strip())
        if _is_process_alive(pid):
            return True
        # Stale PID file
        try:
            os.unlink(PID_PATH)
        except OSError:
            pass
        return False
    except ValueError:
        return False


def get_daemon_pid() -> Optional[int]:
    """Get the PID of the running daemon, or None."""
    if not os.path.exists(PID_PATH):
        return None
    try:
        with open(PID_PATH, "r") as f:
            pid = int(f.read().strip())
        if _is_process_alive(pid):
            return pid
        return None
    except ValueError:
        return None


def stop_daemon():
    """Send stop signal to the running daemon."""
    pid = get_daemon_pid()
    if pid:
        if sys.platform == "win32":
            import ctypes
            PROCESS_TERMINATE = 0x0001
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                kernel32.TerminateProcess(handle, 1)
                kernel32.CloseHandle(handle)
        else:
            os.kill(pid, signal.SIGTERM)
        logger.info(f"Stop signal sent to daemon (PID {pid})")
        return True
    return False


# Allow running as: python -m health_tracker.auto_sync
if __name__ == "__main__":
    daemon = AutoSyncDaemon()
    daemon.run_forever()
