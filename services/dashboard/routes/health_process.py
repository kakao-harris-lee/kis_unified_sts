"""Process-health helpers for dashboard health routes."""

from __future__ import annotations

import os
import time
from pathlib import Path

_PID_FILES: dict[str, Path] = {
    "futures": Path("/home/deploy/project/kis_unified_sts/pids/futures_trading.pid"),
    "stock": Path("/home/deploy/project/kis_unified_sts/pids/stock_trading.pid"),
}


def _read_pid_file(path: Path) -> int | None:
    """Read a PID file. Returns the PID as int, or None on any failure."""
    try:
        if not path.exists():
            return None
        pid = int(path.read_text().strip())
        return pid if pid > 0 else None
    except (OSError, ValueError):
        return None


def _is_alive(pid: int) -> bool:
    """Check whether the given PID is alive via ``kill(pid, 0)``."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _proc_uptime_seconds(pid: int) -> int:
    """Return process uptime in seconds via ``/proc/<pid>`` ctime. 0 on failure."""
    try:
        ctime = Path(f"/proc/{pid}").stat().st_ctime
        return int(time.time() - ctime)
    except (OSError, IndexError, ValueError):
        return 0
