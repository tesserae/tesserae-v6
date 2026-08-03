"""Cross-worker cancellation primitives for long-running searches."""

import multiprocessing
import os
import threading
import time
import uuid


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANCELLATION_DIR = os.environ.get(
    'TESSERAE_CANCELLATION_DIR',
    os.path.join(_PROJECT_ROOT, 'tmp', 'search_cancellations'),
)
_POLL_INTERVAL = 0.1
_STALE_AFTER_SECONDS = 900


class SearchCancelled(Exception):
    """Raised when the user has cancelled an in-flight search."""


def _ensure_dir():
    os.makedirs(CANCELLATION_DIR, exist_ok=True)


def _validate_search_id(search_id):
    if not search_id:
        return None
    try:
        return str(uuid.UUID(str(search_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('search_id must be a UUID') from exc


def _path(search_id):
    return os.path.join(CANCELLATION_DIR, f'{search_id}.cancel')


def _prune_stale_markers():
    try:
        cutoff = time.time() - _STALE_AFTER_SECONDS
        for name in os.listdir(CANCELLATION_DIR):
            path = os.path.join(CANCELLATION_DIR, name)
            try:
                if name.endswith('.cancel') and os.path.getmtime(path) < cutoff:
                    os.unlink(path)
            except OSError:
                pass
    except OSError:
        pass


def request_cancellation(search_id):
    """Persist a best-effort cancellation request from any web worker."""
    search_id = _validate_search_id(search_id)
    if not search_id:
        raise ValueError('search_id is required')
    _ensure_dir()
    _prune_stale_markers()
    try:
        fd = os.open(_path(search_id), os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
    except OSError as exc:
        raise RuntimeError('Could not record search cancellation') from exc


class SearchCancellation:
    """Per-request signal backed by a short-lived shared cancellation file."""

    def __init__(self, search_id=None):
        self.search_id = _validate_search_id(search_id)
        self._event = threading.Event()
        self._last_file_check = 0.0

    @property
    def cancelled(self):
        if self._event.is_set() or not self.search_id:
            return self._event.is_set()
        now = time.monotonic()
        if now - self._last_file_check >= _POLL_INTERVAL:
            self._last_file_check = now
            if os.path.exists(_path(self.search_id)):
                self._event.set()
        return self._event.is_set()

    def cancel(self):
        self._event.set()
        if self.search_id:
            request_cancellation(self.search_id)

    def check(self):
        if self.cancelled:
            raise SearchCancelled()

    def close(self):
        """Remove this request's marker after its owner has stopped work."""
        if self.search_id:
            try:
                os.unlink(_path(self.search_id))
            except OSError:
                pass


def cancellable_pool_map(worker, items, processes, cancellation=None):
    """Map work in child processes and terminate active workers on cancel."""
    if cancellation:
        cancellation.check()
    pool = multiprocessing.Pool(processes=processes)
    try:
        iterator = pool.imap(worker, items)
        results = []
        while True:
            if cancellation:
                cancellation.check()
            try:
                results.append(iterator.next(timeout=0.25))
            except multiprocessing.TimeoutError:
                continue
            except StopIteration:
                break
        pool.close()
        return results
    except BaseException:
        pool.terminate()
        raise
    finally:
        pool.join()
