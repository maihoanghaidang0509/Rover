"""Landing template and config API."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from paths import find_landing_path

logger = logging.getLogger("LandingAPI")

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def landing_config_path() -> Path:
    return find_landing_path("landing_config.json")


def templates_dir() -> Path:
    return find_landing_path("templates")


def list_templates() -> Tuple[dict, int]:
    tdir = templates_dir()
    if not tdir.is_dir():
        return {"success": False, "error": f"templates directory not found: {tdir}"}, 500
    names: List[str] = []
    for entry in sorted(tdir.iterdir()):
        if entry.is_file() and entry.suffix.lower() == ".png":
            names.append(entry.stem)
    return {"success": True, "templates": names}, 200


def template_file_path(name: str) -> Path:
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError("Invalid template name")
    safe = Path(name).name
    if not safe.lower().endswith(".png"):
        safe = f"{safe}.png"
    return templates_dir() / safe


def landing_config_load() -> Tuple[dict, int]:
    path = landing_config_path()
    if not path.exists():
        return {"success": False, "message": "Config file not found"}, 200
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        return {"success": True, "config": config}, 200
    except json.JSONDecodeError as exc:
        return {"success": False, "message": f"Invalid config JSON: {exc}"}, 500


def landing_config_save(config: Dict[str, Any]) -> Tuple[dict, int]:
    path = landing_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    logger.info("[WEB][LANDING] Config saved: %s", path)
    return {"success": True, "message": "Landing config saved successfully", "path": str(path)}, 200


def upload_template(filename: str, data: bytes) -> Tuple[dict, int]:
    stem = Path(filename).stem
    if not _SAFE_NAME.match(stem):
        return {"success": False, "message": "Invalid template name"}, 400
    tdir = templates_dir()
    tdir.mkdir(parents=True, exist_ok=True)
    dest = tdir / f"{stem}.png"
    dest.write_bytes(data)
    logger.info("[WEB][LANDING] Template uploaded: %s", dest)
    return {"success": True, "message": "Template uploaded", "template": stem}, 200
