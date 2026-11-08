#!/bin/bash
# Áp dụng overlay camera vào boot config + reboot CM5 (cần sudo, xem install_camera_sudoers.sh)
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="${1:-$INSTALL_DIR/config.yaml}"
FORCE_REBOOT=0

if [ "${1:-}" = "--force-reboot" ]; then
    FORCE_REBOOT=1
    CONFIG="${2:-$INSTALL_DIR/config.yaml}"
elif [ "${2:-}" = "--force-reboot" ]; then
    FORCE_REBOOT=1
fi

run_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo -n "$@"
    else
        echo "✗ Cần quyền root. Chạy: sudo bash $0" >&2
        exit 1
    fi
}

echo "▶ setup_camera.sh ..."
run_root bash "$INSTALL_DIR/setup_camera.sh" "$CONFIG"

if [ "$FORCE_REBOOT" = "1" ] || \
   [ -f "$INSTALL_DIR/.need_camera_reboot" ] || \
   { [ -f "$INSTALL_DIR/.need_host_reboot" ] && grep -q '^camera$' "$INSTALL_DIR/.need_host_reboot" 2>/dev/null; }; then
    echo "▶ apply_host_reboot.sh ..."
    if [ "$FORCE_REBOOT" = "1" ]; then
        run_root bash "$INSTALL_DIR/apply_host_reboot.sh" --force
    else
        run_root bash "$INSTALL_DIR/apply_host_reboot.sh"
    fi
else
    echo "ℹ️  Boot overlay không đổi — bỏ qua reboot (nhấn Reboot CM5 để reboot cưỡng bức)"
fi
