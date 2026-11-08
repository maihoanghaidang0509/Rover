#!/bin/bash
# Cho phép user chạy UAVLink-Edge gọi setup camera + reboot không cần mật khẩu (chạy 1 lần bằng sudo)
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Chạy: sudo bash install_camera_sudoers.sh [username]" >&2
    exit 1
fi

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

_resolve_target_user() {
    if [ -n "${1:-}" ]; then
        echo "$1"
        return
    fi
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        echo "$SUDO_USER"
        return
    fi
    if command -v logname >/dev/null 2>&1; then
        local u
        u="$(logname 2>/dev/null || true)"
        if [ -n "$u" ] && [ "$u" != "root" ]; then
            echo "$u"
            return
        fi
    fi
    local owner
    owner="$(stat -c '%U' "$INSTALL_DIR" 2>/dev/null || true)"
    if [ -n "$owner" ] && [ "$owner" != "root" ]; then
        echo "$owner"
        return
    fi
    echo ""
}

USER_NAME="$(_resolve_target_user "${1:-}")"
if [ -z "$USER_NAME" ]; then
    echo "Không xác định được user. Chạy: sudo bash install_camera_sudoers.sh <username>" >&2
    exit 1
fi
if ! id "$USER_NAME" >/dev/null 2>&1; then
    echo "User không tồn tại: $USER_NAME" >&2
    exit 1
fi

DEST="/etc/sudoers.d/uavlink-edge-camera"

cat > "$DEST" <<EOF
# UAVLink-Edge — camera overlay + reboot (không mật khẩu)
${USER_NAME} ALL=(root) NOPASSWD: ${INSTALL_DIR}/setup_camera.sh, ${INSTALL_DIR}/apply_host_reboot.sh, ${INSTALL_DIR}/apply_camera_overlay.sh
EOF
chmod 440 "$DEST"
visudo -cf "$DEST"
echo "✓ Đã cài sudoers: $DEST"
echo "  User ${USER_NAME} có thể: sudo -n bash ${INSTALL_DIR}/apply_camera_overlay.sh"
