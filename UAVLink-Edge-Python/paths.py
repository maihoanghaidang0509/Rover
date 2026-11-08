import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Network status: prefer runtime file from netmon, fallback to project data/
NETWORK_STATUS_CANDIDATES = [
    Path("/run/dronebridge/network_status.json"),
    PROJECT_ROOT / "data" / "connection_status.json",
]

CONNECTION_CONFIG_CANDIDATES = [
    Path("/home/pi/connection_config.json"),
    PROJECT_ROOT / "data" / "connection_config.json",
]


def project_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def module_4g_path(*parts: str) -> Path:
    return project_path("Module_4G", *parts)


def find_landing_path(*parts: str) -> Path:
    return project_path("Find_landing", *parts)


def resolve_network_status_file() -> Path:
    for candidate in NETWORK_STATUS_CANDIDATES:
        if candidate.exists():
            return candidate
    return NETWORK_STATUS_CANDIDATES[-1]


def resolve_connection_config_file() -> Path:
    for candidate in CONNECTION_CONFIG_CANDIDATES:
        if candidate.exists():
            return candidate
    return CONNECTION_CONFIG_CANDIDATES[-1]
