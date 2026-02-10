import hashlib
import threading
import time
from collections.abc import Callable
from pathlib import Path


class FileWatcher:
    """
    Watch files for changes and trigger callbacks.

    Uses file hashing to detect changes reliably across
    different file systems and editors.
    """

    def __init__(self, poll_interval: float = 1.0):
        """
        Initialize the file watcher.

        Args:
            poll_interval: Seconds between file checks
        """
        self.poll_interval = poll_interval
        self._watched_files: dict[Path, str] = {}  # path -> hash
        self._callbacks: dict[Path, Callable] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def watch(self, file_path: str, callback: Callable[[Path], None]):
        """
        Start watching a file for changes.

        Args:
            file_path: Path to the file to watch
            callback: Function to call when file changes
        """
        path = Path(file_path).resolve()

        with self._lock:
            # Calculate initial hash
            file_hash = self._get_file_hash(path)
            self._watched_files[path] = file_hash
            self._callbacks[path] = callback

        # Start watcher thread if not running
        if not self._running:
            self.start()

    def unwatch(self, file_path: str):
        """Stop watching a file"""
        path = Path(file_path).resolve()

        with self._lock:
            self._watched_files.pop(path, None)
            self._callbacks.pop(path, None)

    def start(self):
        """Start the file watcher thread"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the file watcher thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _watch_loop(self):
        """Main loop that checks for file changes"""
        while self._running:
            self._check_files()
            time.sleep(self.poll_interval)

    def _check_files(self):
        """Check all watched files for changes"""
        with self._lock:
            files_to_check = list(self._watched_files.items())

        for path, old_hash in files_to_check:
            try:
                new_hash = self._get_file_hash(path)

                if new_hash != old_hash:
                    # File changed - update hash and trigger callback
                    with self._lock:
                        self._watched_files[path] = new_hash
                        callback = self._callbacks.get(path)

                    if callback:
                        try:
                            callback(path)
                        except Exception as e:
                            # Log but don't crash the watcher
                            print(f"Error in file change callback: {e}")

            except FileNotFoundError:
                # File was deleted - could trigger callback or remove watch
                pass

    @staticmethod
    def _get_file_hash(path: Path) -> str:
        """Calculate MD5 hash of file contents"""
        if not path.exists():
            return ""

        hasher = hashlib.md5()
        with open(path, "rb") as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)

        return hasher.hexdigest()
