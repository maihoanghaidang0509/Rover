import logging
import struct
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from pymavlink import mavutil

logger = logging.getLogger("MAVLinkBridge")

INT_PARAM_TYPES = {1, 2, 3, 4, 5, 6, 7}

PARAM_TYPE_MAP = {
    "FLOAT": mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    "float": mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    "REAL32": mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    "INT32": mavutil.mavlink.MAV_PARAM_TYPE_INT32,
    "int": mavutil.mavlink.MAV_PARAM_TYPE_INT32,
    "UINT32": mavutil.mavlink.MAV_PARAM_TYPE_UINT32,
    "INT16": mavutil.mavlink.MAV_PARAM_TYPE_INT16,
    "UINT16": mavutil.mavlink.MAV_PARAM_TYPE_UINT16,
    "INT8": mavutil.mavlink.MAV_PARAM_TYPE_INT8,
    "UINT8": mavutil.mavlink.MAV_PARAM_TYPE_UINT8,
    "bool": mavutil.mavlink.MAV_PARAM_TYPE_UINT8,
}


def _decode_param_value(value: float, param_type: int) -> float:
    if param_type in INT_PARAM_TYPES:
        bits = struct.unpack("I", struct.pack("f", float(value)))[0]
        return float(struct.unpack("i", struct.pack("I", bits))[0])
    return float(value)


def _encode_param_value(value: float, param_type: int) -> float:
    if param_type in INT_PARAM_TYPES:
        bits = struct.unpack("I", struct.pack("i", int(value)))[0]
        return struct.unpack("f", struct.pack("I", bits))[0]
    return float(value)


def _clean_param_id(param_id: Any) -> str:
    if isinstance(param_id, bytes):
        return param_id.decode("utf-8", errors="ignore").rstrip("\x00")
    return str(param_id).rstrip("\x00")


class MAVLinkBridge:
    def __init__(self, response_timeout: float = 5.0):
        self._conn = None
        self._lock = threading.RLock()
        self._connected = False
        self._pixhawk_sys_id = 0
        self._response_timeout = response_timeout
        self._param_cache: Dict[str, Dict[str, Any]] = {}
        self._param_lock = threading.RLock()
        self._param_total = 0
        self._param_loading = False
        self._param_last_update: Optional[datetime] = None
        self._active_path = ""
        self._ethernet_ok = False
        self._serial_ok = False
        self._path_lock = threading.RLock()

    def set_connection(self, conn) -> None:
        with self._lock:
            self._conn = conn

    def set_mavlink_path(self, path: str, ethernet_ok: bool, serial_ok: bool) -> None:
        with self._path_lock:
            self._active_path = path
            self._ethernet_ok = ethernet_ok
            self._serial_ok = serial_ok

    def get_mavlink_path(self) -> Tuple[str, bool, bool]:
        with self._path_lock:
            return self._active_path, self._ethernet_ok, self._serial_ok

    def handle_heartbeat(self, sys_id: int, path: str = "") -> None:
        with self._lock:
            if not self._connected:
                self._pixhawk_sys_id = sys_id
                self._connected = True
                logger.info("[WEB] Connected to Pixhawk (System ID: %d)", sys_id)

    def handle_param_value(self, msg) -> None:
        param_id = _clean_param_id(msg.param_id)
        decoded = _decode_param_value(msg.param_value, msg.param_type)

        with self._param_lock:
            self._param_cache[param_id] = {
                "paramId": param_id,
                "paramValue": decoded,
                "paramType": int(msg.param_type),
                "paramIndex": int(msg.param_index),
            }
            self._param_total = int(msg.param_count)
            self._param_last_update = datetime.now(timezone.utc)

            if self._param_loading and self._param_total > 0 and len(self._param_cache) >= self._param_total:
                self._param_loading = False
                logger.info(
                    "[WEB] Parameter loading complete: %d/%d parameters",
                    len(self._param_cache),
                    self._param_total,
                )

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def get_system_id(self) -> int:
        with self._lock:
            return self._pixhawk_sys_id or 1

    def _resolve_param_name(self, param_name: str) -> str:
        clean = _clean_param_id(param_name)
        with self._param_lock:
            if clean in self._param_cache:
                return clean
            upper = clean.upper()
            for key in self._param_cache:
                if key.upper() == upper:
                    return key
        return clean

    def request_parameter_list(self) -> Tuple[bool, str]:
        with self._lock:
            if self._conn is None:
                return False, "MAVLink bridge not initialized"
            if not self.is_connected():
                return False, "not connected to Pixhawk"
            conn = self._conn
            sys_id = self._pixhawk_sys_id

        with self._param_lock:
            self._param_cache.clear()
            self._param_total = 0
            self._param_loading = True

        try:
            conn.mav.param_request_list_send(sys_id, 1)
            logger.info("[WEB] Sending PARAM_REQUEST_LIST to system %d", sys_id)
            return True, "Parameter list request sent"
        except Exception as exc:
            with self._param_lock:
                self._param_loading = False
            return False, f"failed to send PARAM_REQUEST_LIST: {exc}"

    def request_parameter_read(self, param_name: str) -> Tuple[bool, str]:
        resolved = self._resolve_param_name(param_name)
        with self._lock:
            if self._conn is None:
                return False, "MAVLink bridge not initialized"
            if not self.is_connected():
                return False, "not connected to Pixhawk"
            conn = self._conn
            sys_id = self._pixhawk_sys_id

        try:
            conn.mav.param_request_read_send(sys_id, 1, resolved.encode("utf-8"), -1)
            logger.info("[WEB] Sending PARAM_REQUEST_READ for %s", resolved)
            return True, "Parameter read request sent"
        except Exception as exc:
            return False, f"failed to send PARAM_REQUEST_READ: {exc}"

    def get_parameter_list_status(self, include_params: bool = False) -> Dict[str, Any]:
        with self._param_lock:
            received = len(self._param_cache)
            status = {
                "loading": self._param_loading,
                "totalCount": self._param_total,
                "receivedCount": received,
                "progress": (received / self._param_total * 100) if self._param_total else 0.0,
            }
            if self._param_last_update:
                status["lastUpdated"] = self._param_last_update.isoformat()
            if include_params and self._param_cache:
                status["parameters"] = list(self._param_cache.values())
            return status

    def get_cached_parameter(self, param_name: str, wait_seconds: float = 2.0) -> Tuple[Optional[Dict[str, Any]], bool]:
        resolved = self._resolve_param_name(param_name)
        with self._param_lock:
            param = self._param_cache.get(resolved)
            if param:
                return param, True

        ok, _ = self.request_parameter_read(resolved)
        if not ok:
            return None, False

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            with self._param_lock:
                param = self._param_cache.get(resolved)
                if param:
                    return param, True
            time.sleep(0.1)
        return None, False

    def set_parameter(self, param_name: str, param_value: float, param_type: str) -> Dict[str, Any]:
        resolved = self._resolve_param_name(param_name)
        with self._lock:
            if self._conn is None:
                return {"success": False, "message": "MAVLink bridge not initialized", "paramName": resolved}
            if not self.is_connected():
                return {"success": False, "message": "Not connected to Pixhawk", "paramName": resolved}
            conn = self._conn
            sys_id = self._pixhawk_sys_id

        mav_type = PARAM_TYPE_MAP.get(param_type, mavutil.mavlink.MAV_PARAM_TYPE_INT32)
        encoded = _encode_param_value(param_value, mav_type)

        with self._param_lock:
            before_update = self._param_last_update

        try:
            conn.mav.param_set_send(sys_id, 1, resolved.encode("utf-8"), encoded, mav_type)
            logger.info("[WEB] Sending PARAM_SET: %s = %s (type: %s)", resolved, param_value, param_type)
        except Exception as exc:
            return {
                "success": False,
                "message": f"Failed to send PARAM_SET: {exc}",
                "paramName": resolved,
            }

        return self._wait_for_param_response(resolved, before_update)

    def _wait_for_param_response(self, param_name: str, since: Optional[datetime]) -> Dict[str, Any]:
        deadline = time.time() + self._response_timeout
        baseline = since or datetime.min.replace(tzinfo=timezone.utc)

        while time.time() < deadline:
            with self._param_lock:
                param = self._param_cache.get(param_name)
                last_update = self._param_last_update
            if param and last_update and last_update > baseline:
                logger.info("[WEB] PARAM_VALUE received: %s = %s", param_name, param["paramValue"])
                return {
                    "success": True,
                    "message": f"Parameter {param_name} successfully set",
                    "paramName": param_name,
                    "newValue": param["paramValue"],
                }
            time.sleep(0.1)

        return {
            "success": False,
            "message": "Timeout waiting for parameter confirmation",
            "paramName": param_name,
        }


bridge = MAVLinkBridge()
