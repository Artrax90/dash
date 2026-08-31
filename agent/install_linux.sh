#!/bin/bash
# ==============================================================================
# Workstation Manager - Standalone Linux Agent Installer & Systemd Service
# ==============================================================================
set -e

# Configuration placeholders replaced dynamically by server
DEFAULT_SERVER_URL="__SERVER_URL__"
DEFAULT_TOKEN="__TOKEN__"
DEFAULT_GROUP="__GROUP__"

# Fallback to environment variables if provided, otherwise use server-embedded defaults
SERVER_URL="${WM_SERVER:-$DEFAULT_SERVER_URL}"
TOKEN="${WM_TOKEN:-$DEFAULT_TOKEN}"
GROUP="${WM_GROUP:-$DEFAULT_GROUP}"

SERVER_URL="${SERVER_URL%/}"
if [ -z "$SERVER_URL" ] || [ "$SERVER_URL" = "__SERVER_URL_RAW__" ]; then
    SERVER_URL="http://localhost:2301"
fi

echo "=============================================================================="
echo "    WORKSTATION MANAGER - УСТАНОВКА И ЗАПУСК LINUX АГЕНТА СЛУЖБЫ (v2.4.2)     "
echo "=============================================================================="
echo "  Целевой сервер: $SERVER_URL"
echo "  Токен:          ${TOKEN:0:12}..."
echo "  Группа:         ${GROUP:-Office}"
echo "=============================================================================="
echo ""

# Ensure root permissions
if [ "$(id -u)" -ne 0 ]; then
    echo "[!] Ошибка: Данный скрипт должен запускаться с правами root (sudo)."
    exit 1
fi

INSTALL_DIR="/opt/workstation-manager-agent"
mkdir -p "$INSTALL_DIR"

# 1. Check and install Python 3, curl & ethtool if missing
echo "[1/5] Проверка системных зависимостей (Python 3, curl, ethtool)..."
if ! command -v python3 &>/dev/null || ! command -v curl &>/dev/null; then
    echo "[*] Установка необходимых пакетов..."
    if command -v apt-get &>/dev/null; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y && apt-get install -y python3 python3-pip python3-psutil ethtool curl || apt-get install -y python3 curl
    elif command -v yum &>/dev/null; then
        yum install -y python3 python3-psutil ethtool curl || yum install -y python3 curl
    elif command -v dnf &>/dev/null; then
        dnf install -y python3 python3-psutil ethtool curl || dnf install -y python3 curl
    elif command -v pacman &>/dev/null; then
        pacman -Sy --noconfirm python python-psutil ethtool curl || pacman -Sy --noconfirm python curl
    fi
fi

# 2. Save Config
echo "[2/5] Сохранение конфигурации агента..."
cat <<EOF > "$INSTALL_DIR/config.json"
{
  "server_url": "$SERVER_URL/api/v1",
  "enrollment_token": "$TOKEN",
  "heartbeat_interval_seconds": 30,
  "default_group": "${GROUP:-Office}"
}
EOF
chmod 600 "$INSTALL_DIR/config.json"
echo "      [OK] Конфигурация сохранена: $INSTALL_DIR/config.json"

# 3. Download / write standalone agent payload
echo "[3/5] Получение исполняемого модуля агента..."
if ! curl -fsSL "$SERVER_URL/agent.py" -o "$INSTALL_DIR/agent.py"; then
    echo "[!] Не удалось скачать agent.py напрямую по HTTP, проверяем локальные источники..."
    if [ -f "./agent_standalone.py" ]; then
        cp ./agent_standalone.py "$INSTALL_DIR/agent.py"
    elif [ -f "./agent.py" ]; then
        cp ./agent.py "$INSTALL_DIR/agent.py"
    else
        echo "[!] Ошибка: Не удалось загрузить agent.py с сервера $SERVER_URL/agent.py"
        exit 1
    fi
fi
chmod 755 "$INSTALL_DIR/agent.py"
echo "      [OK] Модуль агента готов к работе: $INSTALL_DIR/agent.py"

# 4. Register Systemd Service
echo "[4/5] Регистрация и запуск системной службы (systemd)..."
cat <<EOF > /etc/systemd/system/workstation-manager-agent.service
[Unit]
Description=Workstation Manager Background Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=WM_CONFIG_PATH=$INSTALL_DIR/config.json
ExecStart=/usr/bin/python3 $INSTALL_DIR/agent.py
Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable workstation-manager-agent.service
systemctl restart workstation-manager-agent.service
echo "      [OK] Служба workstation-manager-agent.service успешно запущена!"

# 5. Activate Wake-on-LAN (Magic Packet) on Linux network interfaces
echo "[5/5] Настройка Wake-on-LAN (Magic Packet) на сетевых интерфейсах..."
if command -v ethtool &>/dev/null; then
    for iface in $(ls /sys/class/net | grep -v 'lo\|docker\|veth\|br-\|tun\|tap' || true); do
        ethtool -s "$iface" wol g 2>/dev/null || true
        echo "      [OK] Интерфейс $iface: WoL Magic Packet активирован."
    done
fi

echo ""
echo "=============================================================================="
echo "       УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА! ПК ПОДКЛЮЧЕН К WORKSTATION MANAGER        "
echo "=============================================================================="
