import json
import socket
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from paths import resolve_network_status_file


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return ""


def _read_active_interface() -> str:
    status_file = resolve_network_status_file()
    if not status_file.exists():
        return ""
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        active = data.get("active_interface")
        return str(active) if active else ""
    except (json.JSONDecodeError, OSError):
        return ""


def detect_network_info() -> Tuple[str, str]:
    active = _read_active_interface().lower()
    if active in ("wwan0", "ppp0", "usb0") or "4g" in active:
        return "4G", ""
    if active in ("wlan0", "wl") or active.startswith("wl"):
        return "WiFi", ""
    if active in ("eth0", "end0", "enp", "eno") or active.startswith(("eth", "en")):
        return "Ethernet", ""

    ip = get_local_ip()
    if not ip:
        return "Unknown", "N/A"

    try:
        result = subprocess.run(
            ["ip", "-4", "route", "get", "8.8.8.8"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        output = result.stdout.lower()
        if "wwan" in output or "ppp" in output:
            return "4G", ""
        if "wlan" in output or "wl" in output:
            return "WiFi", ""
        if "eth" in output or " end" in output:
            return "Ethernet", ""
    except Exception:
        pass

    return "Unknown", "N/A"
