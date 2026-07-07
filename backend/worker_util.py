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
    avail_gb = get_available_memory_gb()
    if avail_gb < LOW_MEMORY_GB and avail_gb != float('inf'):
        return MIN_WORKERS
    return min(max_workers, os.cpu_count() or 2)
