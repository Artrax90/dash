# Workstation Manager 🚀

**Workstation Manager** — современная масштабируемая система централизованного мониторинга, управления питанием (Wake-on-LAN / Shutdown / Reboot), инвентаризации аппаратного обеспечения и дистанционного обслуживания парка рабочих станций (Windows / Linux).

---

## 🌟 Основные возможности

- 🖥️ **Мониторинг парка в реальном времени**: Сбор телеметрии (CPU, RAM, Disks, GPU, активные сессии RDP, uptime, время загрузки).
- ⚡ **Управление питанием**: Одиночный и групповой Wake-on-LAN (WoL), мягкое выключение, принудительный ребут, переход в спящий режим.
- 🛡️ **Аппаратный контроль (Hardware Baseline)**: Автоматическая фиксация эталонной конфигурации ПК, мгновенные алерты при изъятии/замене ОЗУ, дисков, видеокарт или процессора.
- ⏰ **Многошаговый планировщик задач**: Автоматизация циклов включения/выключения ПК по дням недели и часам.
- 🔄 **Централизованное OTA-обновление агентов**: Дистанционное бесшовное обновление фоновых служб на всех ПК парка в 1 клик прямо из веб-панели с отображением живых логов.
- 📥 **Развертывание агентов в 1 клик**: Генерация готовых `.bat` и `.sh` установщиков, Enrollment-токены для автопривязки к группам, терминальные однострочники PowerShell/Bash.
- 🤖 **Интеграция с Telegram-ботом + SOCKS5/HTTP Прокси**: Оповещения об инцидентах, управление питанием и статусом через чат, встроенная поддержка обхода блокировок через защищенный SOCKS5/HTTP/HTTPS прокси.
- 🔐 **Безопасность и RBAC**: Ролевой доступ (Суперадминистратор, Администратор, Оператор, Аудитор), первоначальный мастер настройки SuperAdmin при чистом развертывании, JWT-аутентификация.
- 🌐 **Двуязычный интерфейс (RU / EN)**: Переключение языка в реальном времени, адаптивный дизайн, закрепленный эргономичный сайдбар.

---

## 🚀 Развертывание на сервере Ubuntu (22.04 / 24.04 LTS)

### 🐳 Вариант 1: Запуск в Docker Compose (Рекомендуется)

Все компоненты (React SPA, FastAPI бэкенд, SQLite БД, скрипты установщиков, WebSocket) упакованы в мультистейдж Docker-образ.

```bash
git clone https://github.com/Artrax90/dash.git workstation-manager
cd workstation-manager
docker compose up -d --build
```

**Готово!** Сервер соберется и запустится в изолированном контейнере с сохранением базы данных и настроек в директории `./data`.
👉 Откройте в браузере: **`http://<IP_СЕРВЕРА>:2301`**

---

### ⚡ Вариант 2: Автоматическая установка через systemd (без Docker)

```bash
git clone https://github.com/Artrax90/dash.git workstation-manager
cd workstation-manager
chmod +x deploy_ubuntu.sh
sudo ./deploy_ubuntu.sh
```

**Что делает скрипт:**
1. Устанавливает все системные пакеты (`python3`, `python3-pip`, `python3-venv`, `sqlite3`, `wakeonlan`, `nodejs 20 LTS`, `npm`).
2. Создает виртуальное окружение `.venv` и устанавливает Python-зависимости.
3. Собирает продакшн-бандл интерфейса (`npm run build`).
4. Настраивает и запускает фоновую системную службу `systemd` (`workstation-manager.service`) на порту **2301**.
5. Служба автоматически запускается при старте сервера и перезапускается при сбоях.

После завершения перейдите в браузере по адресу:
👉 **`http://<IP_СЕРВЕРА>:2301`**

---

### Вариант 2: Ручная пошаговая установка на Ubuntu

1. **Установка системных пакетов:**
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv sqlite3 wakeonlan curl git build-essential
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

2. **Клонирование и настройка окружения:**
```bash
git clone https://github.com/Artrax90/dash.git workstation-manager
cd workstation-manager

# Python venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Сборка веб-интерфейса
npm install
npm run build
```

3. **Запуск сервера:**
```bash
# Прямой запуск:
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 2301

# Или в фоновом режиме:
nohup .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 2301 > server.log 2>&1 &
```

---

### Вариант 3: Запуск через Docker Compose

```bash
docker compose up -d --build
```

---

## 🛠️ Управление сервером на Ubuntu

В папке проекта доступны готовые вспомогательные скрипты:

```bash
./status.sh   # Проверить статус службы и просмотреть логи
./update.sh   # Автоматическое обновление из GitHub и перезапуск
./stop.sh     # Остановить сервер
./start.sh    # Запустить сервер
```

---

## 💻 Установка агентов на клиентские ПК

### 🔹 Windows (10 / 11 / Server)
1. Откройте веб-панель **«Агенты и загрузки»**.
2. Скачайте файл **`Install-WorkstationAgent.bat`** (или сгенерируйте токен для нужной группы).
3. Запустите `.bat` файл от имени Администратора.
4. *Альтернатива через PowerShell от Администратора:*
   ```powershell
   irm "http://<IP_СЕРВЕРА>:2301/install.ps1" | iex
   ```

### 🔹 Linux (Ubuntu / Debian / Astra Linux / RedOS)
Выполните одну команду в терминале с правами `sudo`:
```bash
curl -fsSL "http://<IP_СЕРВЕРА>:2301/install.sh" | sudo bash
```

---

## 🛡️ Первый вход в систему

При первом развертывании системы на сервере с нуля панель автоматически откроет **Мастер создания суперадминистратора** (SuperAdmin Onboarding). Задайте имя, логин и надежный пароль для вашей учетной записи.

---

## 📁 Структура проекта

```
├── agent/                  # Исходный код и установщики агента (Windows / Linux)
│   ├── agent_standalone.py # Автономный агент телеметрии и OTA-обновления
│   ├── standalone_installer.ps1 # Установщик службы Windows
│   └── install_linux.sh    # Установщик службы Linux (systemd)
├── backend/                # FastAPI бэкенд
│   ├── app/
│   │   ├── api/v1/         # Эндпоинты (devices, agents, hardware, alerts, telegram, users, roles)
│   │   ├── core/           # Конфигурация и безопасность
│   │   ├── db/             # База данных SQLAlchemy / SQLite
│   │   ├── models/         # Модели БД
│   │   ├── schemas/        # Pydantic-схемы
│   │   └── services/       # Планировщик, WebSocket, OTA
│   └── requirements.txt    # Зависимости Python
├── src/                    # React + TypeScript SPA дашборд
│   ├── api/                # Клиентский слой API
│   ├── components/         # UI-компоненты
│   ├── i18n/               # Многоязычность (RU / EN)
│   └── App.tsx             # Главный модуль приложения
├── deploy_ubuntu.sh        # Скрипт 1-кликового развертывания на Ubuntu
├── requirements.txt        # Общий файл зависимостей
└── package.json            # Зависимости интерфейса
```

---

## 📄 Лицензия и авторство

© 2026 **Сергей Ерёмин**. Workstation Manager v2.0.3.
