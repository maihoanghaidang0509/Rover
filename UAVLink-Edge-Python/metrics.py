import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class Metrics:
  def __init__(self):
    self._lock = threading.RLock()
    self.sent_packets: Dict[str, int] = {}
    self.failed_packets: Dict[str, int] = {}
    self.failed_unhealthy: Dict[str, int] = {}
    self.failed_send: Dict[str, int] = {}
    self.current_ip = ""
    self.auth_status = "Initializing"
    self.last_auth: Optional[datetime] = None
    self.start_time = datetime.now(timezone.utc)
    self.session_expires_at: Optional[datetime] = None
    self.refresh_interval = 0.0
    self.network_type = ""
    self.network_speed = ""
    self.server_reachable = False
    self.udp_raw_in_per_sec = 0.0
    self.udp_accepted_per_sec = 0.0
    self.udp_msg_per_sec = 0.0
    self.udp_bytes_per_sec = 0.0
    self.recent_logs: List[Dict[str, Any]] = []

  def inc_sent(self, msg_type: str) -> None:
    with self._lock:
      self.sent_packets[msg_type] = self.sent_packets.get(msg_type, 0) + 1

  def inc_failed(self, msg_type: str) -> None:
    with self._lock:
      self.failed_packets[msg_type] = self.failed_packets.get(msg_type, 0) + 1

  def inc_failed_unhealthy(self, msg_type: str) -> None:
    with self._lock:
      self.failed_packets[msg_type] = self.failed_packets.get(msg_type, 0) + 1
      self.failed_unhealthy[msg_type] = self.failed_unhealthy.get(msg_type, 0) + 1

  def inc_failed_send(self, msg_type: str) -> None:
    with self._lock:
      self.failed_packets[msg_type] = self.failed_packets.get(msg_type, 0) + 1
      self.failed_send[msg_type] = self.failed_send.get(msg_type, 0) + 1

  def set_ip(self, ip: str) -> None:
    with self._lock:
      self.current_ip = ip

  def set_auth_status(self, status: str) -> None:
    with self._lock:
      self.auth_status = status
      self.server_reachable = status == "Authenticated"
      if status == "Authenticated":
        self.last_auth = datetime.now(timezone.utc)

  def set_udp_rates(
    self,
    raw_in: float,
    accepted: float,
    msg_out: float,
    bytes_out: float,
  ) -> None:
    with self._lock:
      self.udp_raw_in_per_sec = float(raw_in)
      self.udp_accepted_per_sec = float(accepted)
      self.udp_msg_per_sec = float(msg_out)
      self.udp_bytes_per_sec = float(bytes_out)

  def set_session_info(self, expires_at: float, refresh_interval: float) -> None:
    with self._lock:
      if expires_at:
        self.session_expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)
      self.refresh_interval = float(refresh_interval or 0)

  def set_network_info(self, network_type: str, network_speed: str = "") -> None:
    with self._lock:
      self.network_type = network_type
      self.network_speed = network_speed

  def add_log(self, level: str, message: str) -> None:
    with self._lock:
      entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
      }
      self.recent_logs.append(entry)
      if len(self.recent_logs) > 100:
        self.recent_logs = self.recent_logs[-100:]

  def get_snapshot(self) -> Dict[str, Any]:
    with self._lock:
      uptime = datetime.now(timezone.utc) - self.start_time
      uptime_str = str(uptime).split(".")[0]
      return {
        "sent_packets": dict(self.sent_packets),
        "failed_packets": dict(self.failed_packets),
        "failed_unhealthy": dict(self.failed_unhealthy),
        "failed_send": dict(self.failed_send),
        "current_ip": self.current_ip,
        "auth_status": self.auth_status,
        "last_auth": self.last_auth.isoformat() if self.last_auth else None,
        "uptime": uptime_str,
        "session_expires": self.session_expires_at.isoformat() if self.session_expires_at else None,
        "refresh_interval": self.refresh_interval,
        "network_type": self.network_type,
        "network_speed": self.network_speed,
        "server_reachable": self.server_reachable,
        "udp_raw_in_per_sec": self.udp_raw_in_per_sec,
        "udp_accepted_per_sec": self.udp_accepted_per_sec,
        "udp_msg_per_sec": self.udp_msg_per_sec,
        "udp_bytes_per_sec": self.udp_bytes_per_sec,
        "mavlink_uplink_msg_per_sec": self.udp_msg_per_sec,
        "mavlink_uplink_bytes_per_sec": self.udp_bytes_per_sec,
        "logs": list(self.recent_logs),
      }


global_metrics = Metrics()
