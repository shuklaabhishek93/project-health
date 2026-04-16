"""
Folder watcher for automatic Apple Health XML export import.

Monitors a configured directory (e.g., iCloud Drive, Dropbox, or any synced
folder) for new Apple Health export files. When a new XML or ZIP file appears,
it is automatically parsed and imported.

Setup:
  1. Configure a folder path (e.g., ~/Library/Mobile Documents/com~apple~CloudDocs/HealthExports)
  2. On iPhone, use the iOS Shortcut to export Health data to that iCloud folder
  3. The watcher picks up new files and imports them automatically
"""

import logging
import os
import shutil
import threading
import time
import zipfile
from typing import Optional

from .apple_health import import_apple_health
from .sync import sync_imported_records

logger = logging.getLogger("auto_sync.folder_watcher")


class HealthExportWatcher:
    """Watches a folder for new Apple Health XML exports."""

    def __init__(self, watch_dir: str, poll_interval: int = 60, archive: bool = True):
        """
        Args:
            watch_dir: Directory to watch for export files
            poll_interval: Seconds between directory scans
            archive: Whether to move processed files to an archive subfolder
        """
        self.watch_dir = watch_dir
        self.poll_interval = poll_interval
        self.archive = archive
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._processed_files: set[str] = set()

    def start(self):
        """Start watching in a background thread."""
        if not os.path.isdir(self.watch_dir):
            os.makedirs(self.watch_dir, exist_ok=True)
            logger.info(f"Created watch directory: {self.watch_dir}")

        # Load list of already-processed files
        self._load_processed_log()

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"Folder watcher started: {self.watch_dir} (poll every {self.poll_interval}s)")

    def stop(self):
        """Stop the watcher."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Folder watcher stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _watch_loop(self):
        """Main polling loop."""
        while not self._stop_event.is_set():
            try:
                self._scan_directory()
            except Exception as e:
                logger.error(f"Folder watcher error: {e}", exc_info=True)
            self._stop_event.wait(timeout=self.poll_interval)

    def _scan_directory(self):
        """Scan the watch directory for new export files."""
        if not os.path.isdir(self.watch_dir):
            return

        for filename in os.listdir(self.watch_dir):
            filepath = os.path.join(self.watch_dir, filename)

            if not os.path.isfile(filepath):
                continue
            if filepath in self._processed_files:
                continue

            # Handle ZIP files (Apple Health export is a ZIP containing export.xml)
            if filename.lower().endswith(".zip"):
                xml_path = self._extract_zip(filepath)
                if xml_path:
                    self._import_file(xml_path, original_path=filepath)
                    # Clean up extracted XML after import
                    try:
                        os.unlink(xml_path)
                    except OSError:
                        pass

            # Handle XML files directly
            elif filename.lower().endswith(".xml"):
                self._import_file(filepath)

    def _extract_zip(self, zip_path: str) -> Optional[str]:
        """Extract export.xml from an Apple Health export ZIP."""
        try:
            extract_dir = os.path.join(self.watch_dir, "_extracted")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Look for export.xml in the ZIP
                xml_names = [
                    n for n in zf.namelist()
                    if n.endswith("export.xml") or n.endswith("Export.xml")
                ]
                if not xml_names:
                    logger.warning(f"No export.xml found in {zip_path}")
                    self._mark_processed(zip_path)
                    return None

                zf.extract(xml_names[0], extract_dir)
                return os.path.join(extract_dir, xml_names[0])

        except (zipfile.BadZipFile, Exception) as e:
            logger.error(f"Failed to extract {zip_path}: {e}")
            self._mark_processed(zip_path)
            return None

    def _import_file(self, xml_path: str, original_path: Optional[str] = None):
        """Import an Apple Health XML file."""
        source_path = original_path or xml_path
        logger.info(f"Importing Apple Health export: {source_path}")

        try:
            imported = import_apple_health(xml_path)

            if imported:
                updated, created = sync_imported_records(imported)
                logger.info(
                    f"Import complete: {len(imported)} days "
                    f"({updated} updated, {created} created)"
                )
            else:
                logger.info("No data found in export file")

            # Archive the processed file
            if self.archive:
                self._archive_file(source_path)

            self._mark_processed(source_path)

        except Exception as e:
            logger.error(f"Failed to import {source_path}: {e}", exc_info=True)

    def _archive_file(self, filepath: str):
        """Move a processed file to the archive subfolder."""
        archive_dir = os.path.join(self.watch_dir, "archive")
        os.makedirs(archive_dir, exist_ok=True)

        filename = os.path.basename(filepath)
        dest = os.path.join(archive_dir, filename)

        # Add timestamp suffix if file already exists in archive
        if os.path.exists(dest):
            name, ext = os.path.splitext(filename)
            timestamp = int(time.time())
            dest = os.path.join(archive_dir, f"{name}_{timestamp}{ext}")

        try:
            shutil.move(filepath, dest)
            logger.info(f"Archived: {filepath} -> {dest}")
        except OSError as e:
            logger.warning(f"Could not archive {filepath}: {e}")

    def _mark_processed(self, filepath: str):
        """Mark a file as processed to avoid re-importing."""
        self._processed_files.add(filepath)
        self._save_processed_log()

    def _get_log_path(self) -> str:
        return os.path.join(self.watch_dir, ".processed_files.log")

    def _load_processed_log(self):
        """Load the list of previously processed files."""
        log_path = self._get_log_path()
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                self._processed_files = {line.strip() for line in f if line.strip()}

    def _save_processed_log(self):
        """Save the list of processed files."""
        log_path = self._get_log_path()
        with open(log_path, "w") as f:
            for filepath in sorted(self._processed_files):
                f.write(filepath + "\n")
