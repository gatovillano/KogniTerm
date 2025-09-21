import os
import time
import fnmatch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable, List, Optional

class FileSystemWatcher:
    def __init__(self, directory: str, callback: Callable[[str, str], None], ignore_patterns: Optional[List[str]] = None):
        self.directory = directory
        self.callback = callback
        self.ignore_patterns = ignore_patterns or []
        self.observer = Observer()
        self.event_handler = self._create_event_handler()

    def _create_event_handler(self):
        class Handler(FileSystemEventHandler):
            def __init__(self, callback, ignore_patterns):
                self.callback = callback
                self.ignore_patterns = ignore_patterns

            def on_any_event(self, event):
                if any(fnmatch.fnmatch(event.src_path, pattern) for pattern in self.ignore_patterns):
                    return
                # event.event_type: 'modified', 'created', 'deleted', 'moved'
                # event.src_path: path to the file/directory
                self.callback(event.event_type, event.src_path)
        return Handler(self.callback, self.ignore_patterns)

    def start(self):
        self.observer.schedule(self.event_handler, self.directory, recursive=True)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()

# Example Usage (for testing purposes, not part of the main application flow)
if __name__ == "__main__":
    def my_callback(event_type, path):
        print(f"Event: {event_type}, Path: {path}")

    # Create a dummy directory for testing
    test_dir = "test_watched_dir"
    os.makedirs(test_dir, exist_ok=True)
    print(f"Watching directory: {test_dir}")

    watcher = FileSystemWatcher(test_dir, my_callback)
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        print("Watcher stopped.")
    finally:
        # Clean up dummy directory
        if os.path.exists(test_dir):
            import shutil
            shutil.rmtree(test_dir)