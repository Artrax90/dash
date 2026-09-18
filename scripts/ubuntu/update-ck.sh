#!/usr/bin/env bash
# ==============================================================================
# Workstation Manager - Обновление агентов ЦК B4 (Ubuntu / Linux)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Проверка наличия Python 3
if ! command -v python3 &>/dev/null; then
    echo "[!] Ошибка: Python 3 не найден в системе."
    echo "    Установите: sudo apt update && sudo apt install -y python3"
    exit 1
fi

# Запуск скрипта обновления Python
python3 "$SCRIPT_DIR/update_ck.py" "$@"
