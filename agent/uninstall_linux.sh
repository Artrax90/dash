#!/bin/bash
# ==============================================================================
# Workstation Manager - Standalone Linux Agent Uninstaller
# ==============================================================================
set -e

DEFAULT_SERVER_URL="__SERVER_URL_VALUE__"
if [ "$DEFAULT_SERVER_URL" = "__SERVER_URL_VALUE__" ] || [ "$DEFAULT_SERVER_URL" = "" ]; then
    DEFAULT_SERVER_URL="http://localhost:2301"
fi

echo "=============================================================================="
echo "      WORKSTATION MANAGER - ПОЛНОЕ УДАЛЕНИЕ АГЕНТА И СЛУЖБЫ LINUX             "
echo "=============================================================================="

# Ensure root permissions
if [ "$(id -u)" -ne 0 ]; then
    echo "[!] Ошибка: Данный скрипт должен запускаться с правами root (sudo)."
    exit 1
fi

SERVICE_NAME="workstation-manager-agent.service"
INSTALL_DIR="/opt/workstation-manager-agent"

# 1. Determine Server URL, Hostname, MAC and Device ID
SERVER_BASE="$DEFAULT_SERVER_URL"
if [ -f "$INSTALL_DIR/config.json" ]; then
    CFG_URL=$(grep -o '"server_url": *"[^"]*"' "$INSTALL_DIR/config.json" 2>/dev/null | cut -d'"' -f4 | sed 's|/api/v1||g' | sed 's|/$||' || true)
    if [ -n "$CFG_URL" ] && [ "$CFG_URL" != "http://localhost:2301" ]; then
        SERVER_BASE="$CFG_URL"
    fi
fi
SERVER_BASE=$(echo "$SERVER_BASE" | sed 's|/api/v1||g' | sed 's|/$||')

MAC=""
for iface in $(ls /sys/class/net 2>/dev/null | grep -v 'lo\|docker\|veth\|br-\|tun\|tap' || true); do
    m=$(cat "/sys/class/net/$iface/address" 2>/dev/null | tr '[:lower:]' '[:upper:]' || true)
    if [ -n "$m" ] && [ "$m" != "00:00:00:00:00:00" ]; then
        MAC="$m"
        break
    fi
done
if [ -z "$MAC" ]; then
    MAC=$(cat /sys/class/net/*/address 2>/dev/null | grep -v '00:00:00:00:00:00' | head -n 1 | tr '[:lower:]' '[:upper:]' || true)
fi

HOST_NAME=$(hostname)
DEVICE_ID=""
if [ -n "$MAC" ]; then
    CLEAN_MAC=$(echo "$MAC" | tr -d ':')
    DEVICE_ID="PC-${CLEAN_MAC: -4}"
fi

# 1. Notify Server to unenroll/deregister from database
echo "[1/4] Уведомление сервера и снятие станции с учета ($SERVER_BASE)..."
echo "      Хост: $HOST_NAME | MAC: $MAC | ID: $DEVICE_ID"

curl -s -k -X POST "$SERVER_BASE/api/v1/agents/uninstall" \
     -H "Content-Type: application/json" \
     -d "{\"deviceId\": \"$DEVICE_ID\", \"hostname\": \"$HOST_NAME\", \"mac\": \"$MAC\"}" \
     --max-time 5 >/dev/null 2>&1 || true

if [ -n "$DEVICE_ID" ]; then
    curl -s -k -X DELETE "$SERVER_BASE/api/v1/devices/$DEVICE_ID" --max-time 5 >/dev/null 2>&1 || true
fi
curl -s -k -X DELETE "$SERVER_BASE/api/v1/devices/$HOST_NAME" --max-time 5 >/dev/null 2>&1 || true

echo "      [OK] Запрос на удаление станции отправлен на сервер."

# 2. Stop and disable systemd service
echo "[2/4] Остановка и отключение системной службы $SERVICE_NAME..."
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME" || true
    echo "      [OK] Служба остановлена."
fi

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl disable "$SERVICE_NAME" || true
    echo "      [OK] Автозапуск службы отключен."
fi

# 3. Remove systemd unit file
echo "[3/4] Удаление конфигурации systemd..."
if [ -f "/etc/systemd/system/$SERVICE_NAME" ]; then
    rm -f "/etc/systemd/system/$SERVICE_NAME"
    systemctl daemon-reload
    systemctl reset-failed 2>/dev/null || true
    echo "      [OK] Файл службы удален: /etc/systemd/system/$SERVICE_NAME"
fi

# 4. Wipe agent installation directory
echo "[4/4] Очистка директории агента..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "      [OK] Папка $INSTALL_DIR полностью удалена."
fi

echo ""
echo "=============================================================================="
echo "           УДАЛЕНИЕ УСПЕШНО ЗАВЕРШЕНО! АГЕНТ ПОЛНОСТЬЮ СНЯТ С ПК              "
echo "=============================================================================="
