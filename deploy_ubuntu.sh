#!/usr/bin/env bash
# ==============================================================================
# Workstation Manager - Turnkey Ubuntu 22.04 / 24.04 Auto-Deploy Script
# ==============================================================================
set -e

# ANSI Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}==============================================================================${NC}"
echo -e "${CYAN}${BOLD}       Workstation Manager · Turnkey Ubuntu Auto-Deployment                   ${NC}"
echo -e "${CYAN}${BOLD}==============================================================================${NC}"

# Check for root / sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[!] This script requires root permissions to configure systemd and dependencies.${NC}"
    echo -e "${YELLOW}[*] Re-running with sudo...${NC}"
    exec sudo bash "$0" "$@"
fi

# Detect actual user running sudo
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

cd "$SCRIPT_DIR"

echo -e "${BLUE}[1/6] Installing system packages (Python 3, pip, venv, sqlite3, wakeonlan, curl)...${NC}"
apt-get update -y
apt-get install -y python3 python3-pip python3-venv sqlite3 wakeonlan curl git build-essential

echo -e "${BLUE}[2/6] Checking Node.js and npm...${NC}"
if ! command -v node &> /dev/null || [ "$(node -v | cut -d'.' -f1 | tr -d 'v')" -lt 18 ]; then
    echo -e "${YELLOW}[*] Installing Node.js 20 LTS via NodeSource...${NC}"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi
echo -e "${GREEN}[✓] Node.js version: $(node -v), npm version: $(npm -v)${NC}"

echo -e "${BLUE}[3/6] Setting up Python virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
echo -e "${GREEN}[✓] Python dependencies installed successfully.${NC}"

echo -e "${BLUE}[4/6] Building Frontend SPA Dashboard...${NC}"
# Run npm install and build as actual user if possible to avoid root permissions on node_modules
if [ -n "$ACTUAL_USER" ] && [ "$ACTUAL_USER" != "root" ]; then
    chown -R "$ACTUAL_USER:$ACTUAL_USER" "$SCRIPT_DIR"
    sudo -u "$ACTUAL_USER" npm install
    sudo -u "$ACTUAL_USER" npm run build
else
    npm install
    npm run build
fi
echo -e "${GREEN}[✓] Frontend build completed in ./dist${NC}"

# Configurable Application Port
APP_PORT="${PORT:-2301}"

echo -e "${BLUE}[5/6] Configuring systemd service on port ${APP_PORT}...${NC}"
SERVICE_FILE="/etc/systemd/system/workstation-manager.service"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Workstation Manager Server Daemon
After=network.target

[Service]
Type=simple
User=${ACTUAL_USER}
WorkingDirectory=${SCRIPT_DIR}
Environment="PATH=${SCRIPT_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PORT=${APP_PORT}"
ExecStart=${SCRIPT_DIR}/.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${APP_PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable workstation-manager.service
systemctl restart workstation-manager.service

echo -e "${GREEN}[✓] Systemd service 'workstation-manager' created and started on port ${APP_PORT}!${NC}"

# Detect IP address
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="localhost"
fi

echo -e "${BLUE}[6/6] Creating helper scripts (start.sh, stop.sh, update.sh, status.sh)...${NC}"

# start.sh
cat << 'EOF' > start.sh
#!/usr/bin/env bash
sudo systemctl start workstation-manager
echo "[✓] Workstation Manager service started."
EOF
chmod +x start.sh

# stop.sh
cat << 'EOF' > stop.sh
#!/usr/bin/env bash
sudo systemctl stop workstation-manager
echo "[✓] Workstation Manager service stopped."
EOF
chmod +x stop.sh

# status.sh
cat << 'EOF' > status.sh
#!/usr/bin/env bash
sudo systemctl status workstation-manager
EOF
chmod +x status.sh

# update.sh
cat << 'EOF' > update.sh
#!/usr/bin/env bash
set -e
echo "[*] Pulling latest updates from Git..."
git pull
echo "[*] Updating Python dependencies..."
source .venv/bin/activate
pip install -r requirements.txt
echo "[*] Building frontend..."
npm install
npm run build
echo "[*] Restarting Workstation Manager service..."
sudo systemctl restart workstation-manager
echo "[✓] Update complete and server restarted!"
EOF
chmod +x update.sh

# Set correct ownership
chown -R "$ACTUAL_USER:$ACTUAL_USER" "$SCRIPT_DIR"

echo ""
echo -e "${GREEN}${BOLD}==============================================================================${NC}"
echo -e "${GREEN}${BOLD}       ✔ WORKSTATION MANAGER SUCCESSFULLY DEPLOYED AND RUNNING!               ${NC}"
echo -e "${GREEN}${BOLD}==============================================================================${NC}"
echo ""
echo -e "${BOLD}Dashboard URL:${NC}    ${CYAN}${BOLD}http://${SERVER_IP}:${APP_PORT}${NC}"
echo -e "${BOLD}Swagger Docs:${NC}     ${CYAN}http://${SERVER_IP}:${APP_PORT}/docs${NC}"
echo ""
echo -e "${BOLD}Management commands:${NC}"
echo -e "  ${YELLOW}./status.sh${NC}       - Check service status and live logs"
echo -e "  ${YELLOW}./update.sh${NC}       - 1-click update from GitHub"
echo -e "  ${YELLOW}./stop.sh${NC}         - Stop server"
echo -e "  ${YELLOW}./start.sh${NC}        - Start server"
echo ""
echo -e "${CYAN}First time opening the dashboard? You will be greeted with the SuperAdmin setup window.${NC}"
echo -e "${GREEN}==============================================================================${NC}"
