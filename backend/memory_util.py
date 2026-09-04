"""Cross-platform memory detection utility.

Provides available-memory detection that works on Linux (/proc/meminfo)
and macOS (sysctl + vm_stat), with a safe fallback.
"""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def get_available_memory_gb():
    """Return available RAM in GB.

    Linux:  reads MemAvailable from /proc/meminfo.
    macOS:  uses sysctl hw.memsize for total RAM and vm_stat for free/inactive pages.
    Other:  returns float('inf') so callers fail open.
    """
    # Linux
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError):
        pass

    # macOS
    try:
        # Parse vm_stat for page counts
        vm = subprocess.run(
            ['vm_stat'],
            capture_output=True, text=True, timeout=5
        ).stdout

        page_size = 16384  # default
        for line in vm.splitlines():
            if 'page size of' in line:
                parts = line.split()
                for p in parts:
                    if p.isdigit():
                        page_size = int(p)
                        break
                break

        def _parse_pages(label):
            for line in vm.splitlines():
                if label in line:
                    val = line.split(':')[1].strip().rstrip('.')
                    return int(val)
            return 0

        free = _parse_pages('Pages free')
        inactive = _parse_pages('Pages inactive')
        # Available ~ free + inactive (conservative estimate)
        available_bytes = (free + inactive) * page_size
        available_gb = available_bytes / (1024 ** 3)
        logger.debug("macOS memory: available=%.1fGB", available_gb)
        return available_gb
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        logger.debug("macOS memory detection failed: %s", e)

    # Fallback: fail open
    return float('inf')


def get_total_memory_gb():
    """Return total physical RAM in GB.

    Linux:  reads MemTotal from /proc/meminfo.
    macOS:  uses sysctl hw.memsize.
    Other:  returns float('inf') so validation fails open.
    """
    # Linux
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError):
        pass

    # macOS
    try:
        total_bytes = int(subprocess.run(
            ['sysctl', '-n', 'hw.memsize'],
            capture_output=True, text=True, timeout=5
        ).stdout.strip())
        return total_bytes / (1024 ** 3)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass

    return float('inf')

