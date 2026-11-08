"""Network status normalization and 4G signal enrichment."""

import json
import re
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from paths import resolve_network_status_file

_signal_cache: Dict[str, Any] = {}
_signal_expires = 0.0
_signal_lock = threading.Lock()


def signal_dbm_to_bars(dbm: float) -> int:
    if dbm >= -75:
        return 5
    if dbm >= -85:
        return 4
    if dbm >= -95:
        return 3
    if dbm >= -105:
        return 2
    if dbm > -120:
        return 1
    return 0


def signal_dbm_to_quality(dbm: float) -> str:
    if dbm >= -75:
        return "Excellent"
    if dbm >= -85:
        return "Good"
    if dbm >= -95:
        return "Fair"
    if dbm >= -105:
        return "Weak"
    return "Poor"


def get_4g_signal_info() -> Dict[str, Any]:
    global _signal_expires
    now = time.time()
    with _signal_lock:
        if _signal_cache and now < _signal_expires:
            return dict(_signal_cache)

    result: Dict[str, Any] = {
        "signal_dbm": None,
        "signal_quality": "Unknown",
        "signal_bars": 0,
    }
    try:
        proc = subprocess.run(
            ["sudo", "qmicli", "-d", "/dev/cdc-wdm0", "--nas-get-signal-strength"],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if proc.returncode == 0:
            match = re.search(r"(-?\d+(?:\.\d+)?)\s*dBm", proc.stdout)
            if match:
                dbm = float(match.group(1))
                result["signal_dbm"] = dbm
                result["signal_quality"] = signal_dbm_to_quality(dbm)
                result["signal_bars"] = signal_dbm_to_bars(dbm)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass

    with _signal_lock:
        _signal_cache.clear()
        _signal_cache.update(result)
        _signal_expires = now + 10.0
    return dict(result)


def _iface_status(entry: Optional[dict]) -> str:
    if not entry:
        return "unavailable"
    if entry.get("status"):
        return str(entry["status"])
    if entry.get("online") is True:
        return "connected"
    if entry.get("ip"):
        return "available"
    return "unavailable"


def _normalize_iface(entry: Optional[dict]) -> dict:
    if not isinstance(entry, dict):
        return {"status": "unavailable"}
    out = dict(entry)
    out["status"] = _iface_status(entry)
    if entry.get("ip") and "ip_address" not in out:
        out["ip_address"] = entry["ip"]
    return out


def normalize_network_status(raw: dict) -> dict:
    result = dict(raw)
    result["4g"] = _normalize_iface(raw.get("4g"))
    result["wifi"] = _normalize_iface(raw.get("wifi"))
    result["ethernet"] = _normalize_iface(raw.get("ethernet"))

    active = raw.get("active_interface")
    if active and not result.get("active_interface"):
        result["active_interface"] = active

    four_g = result["4g"]
    if four_g.get("status") in ("connected", "available"):
        four_g.update(get_4g_signal_info())
        result["4g"] = four_g

    return result


def read_network_status() -> dict:
    status_file = resolve_network_status_file()
    if status_file.exists():
        try:
            raw = json.loads(status_file.read_text(encoding="utf-8"))
            return normalize_network_status(raw)
        except json.JSONDecodeError:
            pass
    return normalize_network_status(
        {
            "4g": {"status": "unavailable"},
            "wifi": {"status": "unavailable"},
            "ethernet": {"status": "unavailable"},
            "active_interface": None,
            "timestamp": int(time.time()),
        }
    )
