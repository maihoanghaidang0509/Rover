# UAVLink-Edge (Python Version for Pi 5)

[Tiếng Việt](#tiếng-việt) | [English](#english)

**Repository:** [github.com/hbqtechnologycompany/UAVLink-Edge-Python](https://github.com/hbqtechnologycompany/UAVLink-Edge-Python)

---

## English

Python implementation of **UAVLink-Edge** — a MAVLink bridge between the flight controller (Pixhawk/Cube) and the **qcloudstation** fleet server at [http://qcloudcontrol.com/](http://qcloudcontrol.com/).

Aligned with **Pi_CM5_DroneBridgeService** (auth, MAVLink, camera/landing, web UI) but **user-run**: no systemd/PBR install — start with **`./run.sh`**.

![Cloud Control Interface](images/pilot-ui.jpg)

### System block diagram

```text
┌────────────────┐      MAVLink      ┌──────────────────────┐   UDP/VPN (WiFi/4G) ┌───────────────────────────┐
│ Flight         │◄─────────────────►│   UAVLink-Edge-Python │◄───────────────────►│   qcloudstation Server    │
│ Controller     │ Serial / Ethernet │   (Raspberry Pi 5)    │                     │ (http://qcloudcontrol.com)│
└────────────────┘                   └──────────────────────┘                     └───────────────────────────┘
```

---

## Quick start (each drone)

### 1. Clone and install

```bash
git clone https://github.com/hbqtechnologycompany/UAVLink-Edge-Python.git
cd UAVLink-Edge-Python
python3 install.py    # apt deps + venv + pip
```

### 2. One-time setup on this Pi

```bash
# Disable old DroneBridge Go autostart (avoids port 8080 conflict)
sudo systemctl disable --now dronebridge.service dronebridge-netmon.service dronebridge-4g-init.service

# Camera overlay / Reboot CM5 from web UI (user auto-detected — no hardcoded username)
sudo bash install_camera_sudoers.sh
```

`install_camera_sudoers.sh` picks the target user automatically:

1. CLI argument, if given: `sudo bash install_camera_sudoers.sh myuser`
2. `$SUDO_USER` (normal case: `sudo bash install_camera_sudoers.sh`)
3. `logname`, then owner of the project directory

Writes `/etc/sudoers.d/uavlink-edge-camera` so **Reboot CM5** in settings can run `sudo -n` without a password prompt.

### 3. Configure `config.yaml`

```yaml
auth:
  uuid: "YOUR-DRONE-UUID"
  shared_secret: "YOUR-SHARED-SECRET"   # request: hbqsolution@gmail.com
  vehicle_type: 0
  model: ""

network:
  connection_type: prefer_ethernet

ethernet:
  local_ip: "10.41.10.10"
  pixhawk_ip: "10.41.10.2"
  pixhawk_port: 14550
  auto_setup: true          # assigns static IP on eth0 before MAVLink bind

vpn:
  enabled: true
  server_endpoint: YOUR_SERVER:51820
  router_vpn_ip: 10.8.0.1
```

### 4. Register (first time)

```bash
./run.sh --register
```

Secret saved to `.drone_secret` (gitignored).

### 5. Run (every time)

```bash
./run.sh
```

| Command | When |
|---------|------|
| `./run.sh` | **Default** — uses `venv/bin/python`, correct dependencies |
| `sudo ./run.sh` | First VPN bring-up (`wg-quick`) or if `ip addr` on eth0 needs root |
| `./run.sh --register` | Register drone UUID with fleet server |

**Only one instance** may run (lock file `data/uavlink-edge.lock`). A second `./run.sh` exits with a clear error — do not run `nohup ./run.sh &` and `./run.sh` in another terminal at the same time.

**Web UI**

- Control Center: `http://<PI_IP>:8080/`
- MAVLink stats: `http://<PI_IP>:8080/mavlink.html`
- API: `http://<PI_IP>:8080/api/status`

---

## Camera boot overlay (web: Reboot CM5)

Scripts in project root (no `/opt/dronebridge` required):

| Script | Role |
|--------|------|
| `setup_camera.sh` | Write CSI overlays to `/boot/firmware/config.txt` from `Find_landing/camera_detected.json` |
| `apply_camera_overlay.sh` | Run setup + schedule reboot if config changed |
| `apply_host_reboot.sh` | Reboot host after overlay change |
| `install_camera_sudoers.sh` | One-time passwordless sudo for the above (per Pi, per user) |

Flow: **Settings → Hardware → Save sensor type → Reboot CM5**. Requires `install_camera_sudoers.sh` once on that Pi.

**Reboot CM5** always forces a host reboot (~2s) after writing overlay — even when `/boot/firmware/config.txt` already matches (previous versions skipped reboot in that case).

Manual:

```bash
sudo bash apply_camera_overlay.sh config.yaml --force-reboot
```

---

## What's included (2026-07 sync)

| Area | Updates |
|------|---------|
| **Run** | `run.sh`, single-instance lock, `ethernet_setup.py` (`auto_setup` before MAVLink bind) |
| **Auth** | `REGISTER_INIT` v2; `cloud_egress.py` — no 120s stall without 4G modem |
| **MAVLink** | `prefer_ethernet`, partner heartbeat, GPS filter, custom msgs 42998/42999 |
| **Camera / landing** | `camera_mavlink.py`, `landing_mavlink.py`, `Find_landing/` |
| **VPN** | UUID mismatch re-provision; existing `uavlink0` tolerated |
| **Web UI** | App-shell pages; `/api/camera/*`, `/api/network/mode`, hardware settings |
| **4G (optional)** | `Module_4G/` when netmon is used; WiFi-only works without modem |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| MAVLink **0 msg/s**, Auth OK | Two `main.py` on `:14550` | `pkill -f 'UAVLink-Edge-Python.*main.py'` then **one** `./run.sh` |
| `Cannot assign requested address` | `eth0` missing `ethernet.local_ip` | Set `ethernet.auto_setup: true` or `sudo ./run.sh` once |
| Auth **Initializing**, 0 msg/s | Old boot wait / DroneBridge on 8080 | Update code; disable `dronebridge.service` |
| **Reboot CM5** failed, script not found | Missing shell scripts | `git pull`; ensure `setup_camera.sh` exists in repo root |
| **Reboot CM5** sudo password | Sudoers not installed | `sudo bash install_camera_sudoers.sh` on this Pi |
| Port 8080 in use | Another process / old DroneBridge | `ss -tlnp \| grep 8080`; stop conflicting service |

Verify MAVLink:

```bash
ip -4 addr show eth0          # expect 10.41.10.10/24
ping -c2 10.41.10.2
curl -s http://127.0.0.1:8080/api/status | python3 -m json.tool | head -30
```

---

## Directory structure

```text
UAVLink-Edge-Python/
├── run.sh                      # Recommended entry: venv/bin/python main.py
├── main.py
├── instance_lock.py            # Single-instance guard
├── ethernet_setup.py           # eth0 static IP (auto_setup)
├── forwarder.py
├── cloud_egress.py
├── camera_mavlink.py
├── landing_mavlink.py
├── setup_camera.sh             # Boot overlay for CSI cameras
├── apply_camera_overlay.sh
├── install_camera_sudoers.sh   # One-time per Pi (auto user)
├── config.yaml
├── Module_4G/
├── Find_landing/
└── web/
    ├── server.py
    ├── camera_service.py
    └── static/
```

Further reading: [AUTHENTICATION_PROTOCOL.md](AUTHENTICATION_PROTOCOL.md), [STARTUP_FLOW.md](STARTUP_FLOW.md).

---

## Tiếng Việt

### Giới thiệu

**UAVLink-Edge-Python** — bridge MAVLink Pi 5 ↔ Pixhawk ↔ server **qcloudstation**. Đồng bộ tính năng **Pi_CM5_DroneBridgeService**, chạy tay bằng **`./run.sh`** (không cài systemd/PBR).

### Cài đặt một lần trên mỗi drone

```bash
git clone https://github.com/hbqtechnologycompany/UAVLink-Edge-Python.git
cd UAVLink-Edge-Python
python3 install.py

# Tắt DroneBridge Go cũ (tránh chiếm port 8080)
sudo systemctl disable --now dronebridge.service dronebridge-netmon.service dronebridge-4g-init.service

# Cho phép nút «Reboot CM5» trên web (tự nhận user — không cần sửa tên trong script)
sudo bash install_camera_sudoers.sh
```

Script `install_camera_sudoers.sh` tự chọn user theo thứ tự: tham số dòng lệnh → `$SUDO_USER` → `logname` → chủ thư mục project. Mỗi drone có user khác nhau vẫn chỉ cần:

```bash
sudo bash install_camera_sudoers.sh
```

### Chạy hàng ngày

```bash
# Sửa config.yaml (uuid, ethernet, vpn, camera)
./run.sh --register    # lần đầu
./run.sh               # các lần sau
```

- **`./run.sh`** là lệnh chính — luôn dùng đúng `venv`, tránh thiếu `pymavlink`.
- **`sudo ./run.sh`** chỉ khi VPN/`wg-quick` hoặc gán IP eth0 cần root lần đầu.
- **Chỉ một instance** — không chạy song song `nohup ./run.sh &` và `./run.sh` trong terminal khác.

Trình duyệt: `http://<IP_PI>:8080/`

### Ethernet Pi ↔ Pixhawk

Trong `config.yaml`:

```yaml
ethernet:
  local_ip: "10.41.10.10"
  pixhawk_ip: "10.41.10.2"
  auto_setup: true
```

App tự gán IP lên `eth0` trước khi bind MAVLink `:14550`. Kiểm tra:

```bash
ip -4 addr show eth0
ping -c2 10.41.10.2
```

### Camera — Reboot CM5 trên web

1. Cài sudoers một lần: `sudo bash install_camera_sudoers.sh`
2. Chọn sensor CAM0/CAM1 → **Save**
3. **Reboot CM5** → ghi overlay (nếu cần) và **luôn reboot Pi** (~2 phút offline)

`install_camera_sudoers.sh` **không** thay `./run.sh` — chỉ cấp quyền `sudo -n` cho tính năng camera khi app đang chạy bằng user thường.

### Xử lý sự cố thường gặp

| Triệu chứng | Cách xử lý |
|-------------|------------|
| MAVLink 0 msg/s | `pkill -f 'UAVLink-Edge-Python.*main.py'` → chạy lại **một** `./run.sh` |
| `Cannot assign requested address` | Bật `ethernet.auto_setup: true` hoặc `sudo ./run.sh` |
| Reboot CM5 lỗi sudo | `sudo bash install_camera_sudoers.sh` |
| Port 8080 bận | Tắt `dronebridge.service` |

### Liên hệ shared secret

Email: **hbqsolution@gmail.com**

---

## About

[hbqtechnologycompany.github.io/UAVLink-Edge-Python/](https://hbqtechnologycompany.github.io/UAVLink-Edge-Python/)
