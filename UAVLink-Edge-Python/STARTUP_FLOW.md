# UAVLink-Edge Startup Flow

> Phiên bản: 6.0 — `main.py` user-run (`./run.sh`)  
> Cập nhật: 2026-07-13

---

## Cách chạy

```bash
./run.sh              # khuyến nghị
./run.sh --register   # đăng ký lần đầu
sudo ./run.sh         # khi VPN / gán IP eth0 cần root lần đầu
```

Chỉ **một** instance được phép (`instance_lock.py` → `data/uavlink-edge.lock`).

---

## Boot order (user-run, không systemd)

```
Người dùng chạy ./run.sh
    │
    ├─ venv re-exec (nếu gọi nhầm system python / sudo python)
    ├─ acquire_instance_lock()
    ├─ Load config.yaml
    ├─ VPN start (nếu đã có vpn_config.json)
    ├─ Web server :8080
    ├─ Network monitor (Module_4G/connection_manager.py, optional)
    ├─ wait_for_cloud_egress() — ngắn nếu không có wwan0
    ├─ auth.start() — TCP HMAC
    ├─ VPN provision / rebind uplink socket
    ├─ ensure_ethernet_ready() — gán 10.41.10.10/24 nếu auto_setup
    ├─ fwd.start() — MAVLink listener + uplink/downlink
    ├─ camera_mavlink / landing_mavlink bridges
    └─ while True (chờ SIGINT)
```

*(Không cài `UAVLink-Edge.service` mặc định — tắt `dronebridge.service` nếu trùng port 8080.)*

---

## Startup diagram

```text
./run.sh → main.py
    │
    ▼
┌─────────────────────┐
│ instance_lock       │
│ Config + AuthClient │
│ VPNManager          │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ start_server :8080  │
│ start_network_monitor│
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ wait_for_cloud_egress│  ← 5–10s nếu không có 4G; bỏ qua netmon user-run
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ auth.start()        │  TCP :5770 → session token
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ VPN provision/start │
│ fwd.rebind_vpn_socket│
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ ensure_ethernet_ready│  ip addr trên eth0 (auto_setup)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ fwd.start()         │
│  udpin:local_ip:14550│
│  prefer_ethernet +   │
│  serial backup       │
│  partner HB 1 Hz     │
└──────────┬──────────┘
           ▼
     ✅ OPERATIONAL
```

---

## Threads khi OPERATIONAL

| Thread | Module | Mô tả |
|--------|--------|--------|
| `MainThread` | `main.py` | Giữ process, SIGINT/SIGTERM |
| Flask | `web/server.py` | HTTP API + static UI |
| `keepalive_loop` | `auth_client.py` | SESSION_REFRESH / re-auth |
| `uplink_loop` (×N) | `forwarder.py` | MAVLink từ Pixhawk → server UDP |
| `downlink_loop` | `forwarder.py` | Server → Pixhawk |
| `partner-heartbeat` | `forwarder.py` | HEARTBEAT 1 Hz → Pixhawk (chung socket UDP) |
| `connection_manager` | `Module_4G/` | Netmon JSON (optional, sudo) |

---

## Đăng ký (`--register`)

```bash
./run.sh --register
```

Gửi `REGISTER_INIT` / `REGISTER_RESPONSE`, lưu `.drone_secret`, **không** start forwarder.

---

## Log timeline — khởi động thành công

```text
[MAIN] Starting UAVLink-Edge (Python Version) on Pi 5
[VPN] Tunnel ready — assigned 10.8.x.x
[WebServer] Starting web server on http://0.0.0.0:8080
[CloudEgress] No 4G modem — WiFi available, skip long cloud_ready wait
[AuthClient] ✅ Authenticated!
[EthernetSetup] Ethernet eth0 already has 10.41.10.10
[Forwarder] Pixhawk UDP listener udpin:10.41.10.10:14550
[Forwarder] Forwarder started. Target: ('10.8.0.1', 14550)
[MAIN] UAVLink-Edge running. Press Ctrl+C to stop.
```

---

## Camera overlay (tách khỏi main loop)

Nút **Reboot CM5** trên web gọi `POST /api/camera/apply-overlay` → `apply_camera_overlay.sh` (cần `install_camera_sudoers.sh` một lần trên Pi).

Không chạy trong `./run.sh` — chỉ khi user lưu sensor và reboot từ UI.

---

## Ghi chú

- Cấu hình: `config.yaml` qua `config.py`.
- **Ethernet:** `ethernet.auto_setup: true` gán IP trước bind MAVLink; lỗi `Cannot assign requested address` = thiếu bước này.
- **MAVLink 0 msg/s:** thường do 2 instance cùng bind `:14550` — chỉ chạy một `./run.sh`.
- **4G:** `Module_4G` tùy chọn; WiFi-only vẫn auth và forward MAVLink qua VPN.

Xem thêm: [README.md](README.md), [AUTHENTICATION_PROTOCOL.md](AUTHENTICATION_PROTOCOL.md).
