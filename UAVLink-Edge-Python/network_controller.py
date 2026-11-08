"""Network monitor control — priority/once/run daemon (replaces missing CLI subcommands)."""

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

from paths import module_4g_path, project_path, resolve_connection_config_file

logger = logging.getLogger("NetworkController")

STATUS_DIR = "/run/dronebridge"
_netmon_proc: Optional[subprocess.Popen] = None
_netmon_lock = threading.Lock()


def _has_wwan0() -> bool:
    return Path("/sys/class/net/wwan0").exists()


def _netmon_env() -> Dict[str, str]:
    log_dir = project_path("data", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DRONEBRIDGE_LOG_DIR"] = str(log_dir)
    # Lab/WiFi-only: don't spam 4G reinit when modem absent
    if not _has_wwan0():
        env["DRONEBRIDGE_FORCE_4G_ONLY"] = "0"
    return env


def _ensure_netmon_runtime() -> bool:
    """connection_manager.py needs /run/dronebridge and root for PBR routing."""
    try:
        os.makedirs(STATUS_DIR, exist_ok=True)
        return True
    except PermissionError:
        pass

    try:
        result = subprocess.run(
            ["sudo", "-n", "mkdir", "-p", STATUS_DIR],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.error(
                "Cannot create %s (need sudo): %s",
                STATUS_DIR,
                (result.stderr or result.stdout or "").strip(),
            )
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Failed to prepare %s: %s", STATUS_DIR, exc)
        return False


def _netmon_command(*args: str) -> list:
    script = module_4g_path("connection_manager.py")
    if os.geteuid() == 0:
        return [sys.executable, str(script), *args]
    return ["sudo", "-n", sys.executable, str(script), *args]


def set_priority(priority: str) -> bool:
    config_file = resolve_connection_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    data["priority"] = priority
    config_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.info("Network priority set to %s (%s)", priority, config_file)
    return True


def get_priority() -> str:
    config_file = resolve_connection_config_file()
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            return data.get("priority", "wifi")
        except json.JSONDecodeError:
            pass
    return "wifi"


def run_once() -> subprocess.CompletedProcess:
    script = module_4g_path("connection_manager.py")
    if not script.exists():
        raise FileNotFoundError("Module_4G not available")
    if not _ensure_netmon_runtime():
        raise PermissionError(f"Cannot access {STATUS_DIR}")

    code = (
        "import sys; sys.path.insert(0, '.'); "
        "from connection_manager import NetworkMonitor; "
        "NetworkMonitor().apply_routing_policy()"
    )
    cmd = [sys.executable, "-c", code]
    if os.geteuid() != 0:
        cmd = ["sudo", "-n", sys.executable, "-c", code]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=90,
        cwd=str(module_4g_path()),
        env=_netmon_env(),
    )


def start_network_monitor() -> None:
    global _netmon_proc
    script = module_4g_path("connection_manager.py")
    if not script.exists():
        logger.warning("Module_4G connection_manager not found — network monitor disabled")
        return

    if not _ensure_netmon_runtime():
        logger.warning(
            "Network monitor disabled — cannot create %s (run: sudo mkdir -p %s)",
            STATUS_DIR,
            STATUS_DIR,
        )
        return

    with _netmon_lock:
        if _netmon_proc is not None and _netmon_proc.poll() is None:
            logger.info("Network monitor already running (pid %s)", _netmon_proc.pid)
            return

        cmd = _netmon_command()
        logger.info("Starting network monitor daemon: %s", " ".join(cmd))
        log_file = project_path("data", "logs", "netmon.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_fp = open(log_file, "a", encoding="utf-8")
        try:
            _netmon_proc = subprocess.Popen(
                cmd,
                cwd=str(module_4g_path()),
                env=_netmon_env(),
                stdout=log_fp,
                stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            log_fp.close()
            logger.error("Failed to start network monitor: %s", exc)
            _netmon_proc = None
            return
        logger.info("Network monitor logs → %s", log_file)
