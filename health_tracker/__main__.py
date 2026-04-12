"""Allow running auto-sync daemon via: python -m health_tracker"""

from .auto_sync import AutoSyncDaemon

if __name__ == "__main__":
    daemon = AutoSyncDaemon()
    daemon.run_forever()
