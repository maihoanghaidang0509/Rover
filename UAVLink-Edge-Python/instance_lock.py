"""Prevent multiple UAVLink-Edge instances (split MAVLink UDP on :14550)."""

from __future__ import annotations

import fcntl
import logging
import os
from pathlib import Path

from paths import project_path

logger = logging.getLogger("InstanceLock")

_lock_handle = None


def acquire_instance_lock() -> None:
    global _lock_handle
    lock_dir = project_path("data")
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "uavlink-edge.lock"
    handle = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        pid = _read_lock_pid(lock_path)
        hint = f" (pid {pid})" if pid else ""
        logger.fatal(
            "UAVLink-Edge đã chạy%s. Dừng instance cũ: pkill -f 'UAVLink-Edge-Python.*main.py'",
            hint,
        )
        raise SystemExit(1)

    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    _lock_handle = handle


def _read_lock_pid(lock_path: Path) -> str:
    try:
        return lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
