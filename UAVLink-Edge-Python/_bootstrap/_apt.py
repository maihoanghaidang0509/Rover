"""Gói hệ thống cài qua apt (dùng chung install.py và pip bootstrap)."""

import os
import shutil
import subprocess

APT_PACKAGES = [
    "wireguard-tools",
    "python3-picamera2",
    "python3-libcamera",
    "libcamera-apps",
    "v4l-utils",
    "ffmpeg",
    "gstreamer1.0-tools",
    "gstreamer1.0-plugins-good",
    "gstreamer1.0-plugins-bad",
    "gstreamer1.0-plugins-ugly",
    "gstreamer1.0-libav",
    "gstreamer1.0-rtsp",
]


def apt_install() -> bool:
    if os.environ.get("UAVLINK_SKIP_APT") == "1":
        return True
    if os.environ.get("UAVLINK_APT_DONE") == "1":
        return True
    if not shutil.which("apt-get"):
        print("[install] apt-get not found — bỏ qua cài gói hệ thống")
        return True
    print("[install] Cài gói hệ thống (apt)…")
    subprocess.run(["sudo", "apt-get", "update", "-qq"], check=False)
    result = subprocess.run(
        ["sudo", "apt-get", "install", "-y", *APT_PACKAGES],
    )
    if result.returncode == 0:
        os.environ["UAVLINK_APT_DONE"] = "1"
        print("[install] apt OK")
        return True
    print(
        "[install] apt thất bại — thử: sudo apt install -y "
        + " ".join(APT_PACKAGES)
    )
    return False
