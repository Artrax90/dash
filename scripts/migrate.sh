#!/usr/bin/env bash
set -e

# Workstation Manager - SQLite to PostgreSQL migration wrapper for Linux/Ubuntu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 1. Check if workstation-manager is running inside Docker
if command -v docker &>/dev/null && docker compose ps --services --filter "status=running" 2>/dev/null | grep -q "workstation-manager"; then
    echo "🐳 Обнаружен работающий контейнер Docker: workstation-manager"
    echo "📦 Синхронизация backend и scripts в контейнер..."
    docker cp "$REPO_DIR/backend" workstation-manager:/app/
    docker cp "$SCRIPT_DIR" workstation-manager:/app/
    echo "🚀 Запуск миграции внутри контейнера workstation-manager..."
    exec docker compose exec -T workstation-manager python3 /app/scripts/migrate_sqlite_to_postgres.py "$@"
fi

# 2. Host Python detection
if [ -f "$REPO_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$REPO_DIR/venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "❌ Ошибка: Python 3 не найден."
    echo "Установите Python 3 командой: sudo apt update && sudo apt install -y python3 python3-pip"
    exit 1
fi

# 3. Check if required dependencies are present in host Python
if ! "$PYTHON_BIN" -c "import sqlalchemy" &>/dev/null; then
    echo "⚠️ Внимание: библиотеки (SQLAlchemy, psycopg2-binary) не найдены в $PYTHON_BIN."
    echo ""
    echo "💡 Варианты решения:"
    echo "1) Если сервер работает в Docker, запустите через Docker:"
    echo "   docker cp scripts workstation-manager:/app/"
    echo "   docker compose exec workstation-manager python3 /app/scripts/migrate_sqlite_to_postgres.py $@"
    echo ""
    echo "2) Или установите зависимости на хосте:"
    echo "   pip3 install -r requirements.txt"
    exit 1
fi

"$PYTHON_BIN" "$SCRIPT_DIR/migrate_sqlite_to_postgres.py" "$@"
