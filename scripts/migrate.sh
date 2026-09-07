#!/usr/bin/env bash
set -e

# Workstation Manager - SQLite to PostgreSQL migration wrapper for Linux/Ubuntu

# 1. Detect Python binary
if [ -f "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
elif [ -f "../venv/bin/python" ]; then
    PYTHON_BIN="../venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "❌ Ошибка: Python 3 не найден. Установите его командой: sudo apt update && sudo apt install -y python3 python3-pip"
    exit 1
fi

# 2. Run migration script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$PYTHON_BIN" "$SCRIPT_DIR/migrate_sqlite_to_postgres.py" "$@"
