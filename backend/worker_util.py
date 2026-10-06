"""Memory-aware worker count for multiprocessing pools."""

import os
from backend.memory_util import get_available_memory_gb

MAX_WORKERS = 4
MIN_WORKERS = 2
LOW_MEMORY_GB = 16


def safe_worker_count(max_workers=MAX_WORKERS):
    """Return a worker count that respects available memory.

    Caps at MAX_WORKERS (4) by default. Drops to MIN_WORKERS (2)
    when available RAM is below LOW_MEMORY_GB (16 GB).
    """
    # TESSERAE_MAX_WORKERS lets a memory-capped test copy run the parallel
    # channels with fewer processes (each fork of the server counts against
    # its cap); it changes speed only, never results.
    env_cap = os.environ.get('TESSERAE_MAX_WORKERS')
    if env_cap and env_cap.isdigit():
        max_workers = max(1, min(max_workers, int(env_cap)))
    avail_gb = get_available_memory_gb()
    if avail_gb < LOW_MEMORY_GB and avail_gb != float('inf'):
        return min(MIN_WORKERS, max_workers)
    return min(max_workers, os.cpu_count() or 2)
