import os
import time
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings

# Configure process timezone for consistent logging and system datetime
tz_env = os.getenv("TZ") or getattr(settings, "TIMEZONE", "Europe/Moscow") or "Europe/Moscow"
os.environ["TZ"] = tz_env
if hasattr(time, "tzset"):
    try:
        time.tzset()
    except Exception:
        pass

import logging
from backend.app.db.session import engine, Base, AsyncSessionLocal, is_postgres_url
from backend.app.core.time_utils import get_local_now

logger = logging.getLogger("workstation_manager")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


import backend.app.models  # Register all models for SQLAlchemy
from backend.app.ws.manager import ws_manager

# Import API routers
from backend.app.api.v1.devices import router as devices_router
from backend.app.api.v1.agents import router as agents_router
from backend.app.api.v1.hardware import router as hardware_router
from backend.app.api.v1.alerts import router as alerts_router
from backend.app.api.v1.schedules import router as schedules_router
from backend.app.api.v1.roles import router as roles_router
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.audit import router as audit_router
from backend.app.api.v1.telegram import router as telegram_router
from backend.app.api.v1.groups import router as groups_router
from backend.app.api.v1.sessions import router as sessions_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.services.scheduler_service import scheduler_service

def safe_migrate_columns_sync(connection):
    """Safely and idempotently inspect and add missing columns to existing tables."""
    from sqlalchemy import inspect, text
    inspector = inspect(connection)
    try:
        tables = inspector.get_table_names()
    except Exception:
        tables = []
    
    if "devices" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("devices")}
        is_postgres = connection.dialect.name == "postgresql"
        dt_type = "TIMESTAMP" if is_postgres else "DATETIME"
        
        column_defs = [
            ("boot_time", f"ALTER TABLE devices ADD COLUMN boot_time {dt_type}"),
            ("uptime_seconds", "ALTER TABLE devices ADD COLUMN uptime_seconds INTEGER DEFAULT 0"),
            ("building", "ALTER TABLE devices ADD COLUMN building VARCHAR(100) DEFAULT ''"),
            ("floor", "ALTER TABLE devices ADD COLUMN floor VARCHAR(50) DEFAULT ''"),
            ("room", "ALTER TABLE devices ADD COLUMN room VARCHAR(100) DEFAULT ''"),
        ]
        
        for col_name, col_sql in column_defs:
            if col_name not in existing_cols:
                try:
                    connection.execute(text(col_sql))
                except Exception as ex:
                    logger.debug(f"Column migration notice for {col_name}: {ex}")

    if "hardware_changes" in tables:
        try:
            connection.execute(text("UPDATE hardware_changes SET diff_status = 'INFO', severity = 'Info' WHERE (component = 'USB-накопитель' OR id LIKE '%USB%' OR description LIKE '%Remote Display Adapter%' OR current_value LIKE '%Remote Display Adapter%') AND diff_status = 'MISMATCH'"))
        except Exception as ex:
            logger.debug(f"Hardware changes USB/VGPU cleanup notice: {ex}")

    if "alerts" in tables:
        try:
            connection.execute(text("UPDATE alerts SET state = 'Resolved', severity = 'Info' WHERE (alert_type IN ('USB_STORAGE_CHANGED', 'VIRTUAL_GPU_CHANGED') OR description LIKE '%Remote Display Adapter%') AND state = 'Open'"))
        except Exception as ex:
            logger.debug(f"Alerts USB/VGPU cleanup notice: {ex}")

    if "devices" in tables and "alerts" in tables and "hardware_changes" in tables:
        try:
            connection.execute(text("""
                UPDATE devices 
                SET health_status = 'HEALTHY' 
                WHERE (health_status = 'CRITICAL' OR health_status = 'WARNING' OR health_status = 'Critical' OR health_status = 'Warning')
                  AND id NOT IN (
                      SELECT DISTINCT device_id FROM alerts WHERE state = 'Open' AND device_id IS NOT NULL
                  )
                  AND id NOT IN (
                      SELECT DISTINCT device_id FROM hardware_changes WHERE diff_status = 'MISMATCH' AND (acknowledged = 0 OR acknowledged IS NULL) AND component NOT IN ('USB-накопитель', 'RDP-видеоадаптер') AND id NOT LIKE '%USB%' AND id NOT LIKE '%VGPU%' AND description NOT LIKE '%Remote Display Adapter%' AND device_id IS NOT NULL
                  )
            """))
        except Exception as ex:
            logger.debug(f"Device health auto-reconciliation notice: {ex}")

@app.on_event("startup")
async def startup_event():
    # Initialize DB schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(safe_migrate_columns_sync)

    # Identify and log database backend cleanly
    is_pg = is_postgres_url(str(engine.url))
    db_type = "PostgreSQL" if is_pg else "SQLite"
    if is_pg and engine.url:
        host = engine.url.host or "postgres"
        port = f":{engine.url.port}" if engine.url.port else ""
        db_name = engine.url.database or "workstation_manager"
        conn_str = f"{host}{port}/{db_name}"
    else:
        conn_str = str(engine.url.database if engine.url else "./data/workstation_manager.db")

    local_now_str = get_local_now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Workstation Manager database initialized. Engine: {db_type} [{conn_str}], Timezone: {tz_env} ({local_now_str})")
    banner = (
        "=" * 60 + "\n"
        f"  [*] Workstation Manager Server Online\n"
        f"  [*] Active Database Engine: {db_type}\n"
        f"  [*] Connection Target:      {conn_str}\n"
        f"  [*] System Timezone:        {tz_env} ({local_now_str})\n"
        + "=" * 60
    )
    try:
        print(banner)
    except Exception:
        print(banner.encode("ascii", errors="replace").decode("ascii"))

    # Preload device cache for instant Telegram bot and report availability
    try:
        from backend.app.api.v1.telegram import load_devices_async
        await load_devices_async()
    except Exception as ex:
        logger.warning(f"Device cache preloading notice: {ex}")

    # Start automated scheduler and telegram bot background loops
    import asyncio
    asyncio.create_task(scheduler_service.start_background_loop())
    from backend.app.services.telegram_bot_service import telegram_bot_service
    asyncio.create_task(telegram_bot_service.start_polling_loop())

# Mount API v1 routers
api_prefix = settings.API_V1_STR
app.include_router(devices_router, prefix=api_prefix)
app.include_router(agents_router, prefix=api_prefix)
app.include_router(hardware_router, prefix=api_prefix)
app.include_router(alerts_router, prefix=api_prefix)
app.include_router(schedules_router, prefix=api_prefix)
app.include_router(roles_router, prefix=api_prefix)
app.include_router(users_router, prefix=api_prefix)
app.include_router(audit_router, prefix=api_prefix)
app.include_router(telegram_router, prefix=api_prefix)
app.include_router(groups_router, prefix=api_prefix)
app.include_router(sessions_router, prefix=api_prefix)

from starlette.staticfiles import StaticFiles

# System status & database inspection endpoints
@app.get("/api/v1/system/status")
@app.get("/api/v1/status")
async def get_system_status():
    """Return health status, active database engine, and timezone details."""
    is_pg = is_postgres_url(str(engine.url))
    dialect = engine.dialect.name

    # Live connectivity test
    db_connected = False
    try:
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT 1"))
            db_connected = (res.scalar() == 1)
    except Exception as ex:
        logger.error(f"Database healthcheck error: {ex}")
        db_connected = False

    db_info = {
        "type": "postgresql" if is_pg else "sqlite",
        "dialect": dialect,
        "connected": db_connected,
    }
    if is_pg and engine.url:
        db_info["host"] = engine.url.host
        db_info["port"] = engine.url.port or 5432
        db_info["database"] = engine.url.database
    elif engine.url:
        db_info["database"] = engine.url.database

    return {
        "status": "online",
        "version": settings.VERSION,
        "timezone": tz_env,
        "serverTime": get_local_now().strftime("%Y-%m-%d %H:%M:%S"),
        "database": db_info,
    }

@app.get("/api/v1/system/backup")
async def export_system_backup():
    """Exports full JSON database and configuration backup."""
    from backend.app.services.backup_service import backup_service
    data = await backup_service.create_backup()
    now_str = datetime.utcnow().strftime("%Y-%m-%d_%H%M")
    filename = f"workstation_manager_backup_{now_str}.json"
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@app.post("/api/v1/system/restore")
async def restore_system_backup(request: Request):
    """Restores database tables and configs from uploaded backup."""
    from backend.app.services.backup_service import backup_service
    from fastapi import HTTPException
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный JSON формат резервной копии")
    try:
        res = await backup_service.restore_backup(payload)
        return res
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Ошибка восстановления: {str(ex)}")

@app.post("/api/v1/system/cleanup")
async def cleanup_system_data(request: Request):
    """Prunes resolved alerts and audit records older than specified retention days."""
    from backend.app.services.backup_service import backup_service
    days = 30
    try:
        body = await request.json()
        if isinstance(body, dict) and "days" in body:
            days = int(body["days"])
    except Exception:
        pass
    return await backup_service.cleanup_old_records(days=days)

@app.post("/api/v1/system/reset-database")
async def reset_system_database(request: Request):
    """
    Completely resets all database tables and clears fleet devices, groups, telemetry, and logs.
    Requires exact confirmation phrase: 'УДАЛИТЬ ВСЕ ДАННЫЕ'.
    """
    from fastapi import HTTPException
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный JSON формат")

    CONFIRMATION_PHRASE = "УДАЛИТЬ ВСЕ ДАННЫЕ"
    confirmation = ""
    keep_current_user = True
    if isinstance(payload, dict):
        confirmation = str(payload.get("confirmation") or "").strip().upper()
        keep_current_user = bool(payload.get("keepCurrentUser", True))

    if confirmation != CONFIRMATION_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f'Для подтверждения необходимо точно ввести фразу "{CONFIRMATION_PHRASE}"'
        )

    from backend.app.services.backup_service import backup_service
    x_user = request.headers.get("X-Username") or request.headers.get("X-User-Id")
    return await backup_service.reset_database(
        keep_current_user=keep_current_user,
        current_user_id=x_user
    )

# Auto-mount SPA frontend if built in dist/
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dist"))
if os.path.isdir(dist_dir) and os.path.exists(os.path.join(dist_dir, "index.html")):
    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    async def serve_spa_root():
        return FileResponse(os.path.join(dist_dir, "index.html"))

    @app.get("/favicon.ico")
    async def serve_favicon():
        fav = os.path.join(dist_dir, "favicon.ico")
        if os.path.exists(fav):
            return FileResponse(fav)
        return Response(status_code=204)
else:
    @app.get("/")
    async def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "online",
            "docs": "/docs"
        }


def resolve_request_base_url(request: Request, server_url: str = "") -> str:
    """
    Resolve the real, publicly reachable base URL of this server.
    Guarantees that remote clients NEVER receive 'http://localhost' or '127.0.0.1'.
    """
    if server_url and server_url.strip():
        clean = server_url.strip().rstrip("/").replace("/api/v1", "").rstrip("/")
        if clean and not clean.startswith("http://localhost") and not clean.startswith("http://127.0.0.1"):
            return clean

    # 1. Check explicit headers forwarded by reverse proxies (Nginx, Traefik, Apache, Docker)
    for hdr in ["x-forwarded-host", "x-original-host", "x-forwarded-server"]:
        val = request.headers.get(hdr)
        if val:
            host_val = val.split(",")[0].strip()
            if host_val and not host_val.startswith("localhost") and not host_val.startswith("127.0.0.1") and not host_val.startswith("0.0.0.0"):
                proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
                return f"{proto}://{host_val}".replace("/api/v1", "").rstrip("/")

    # 2. Check the standard Host header
    host_header = request.headers.get("host") or ""
    if host_header:
        host_val = host_header.split(",")[0].strip()
        if host_val and not host_val.startswith("localhost") and not host_val.startswith("127.0.0.1") and not host_val.startswith("0.0.0.0"):
            proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
            return f"{proto}://{host_val}".replace("/api/v1", "").rstrip("/")

    # 3. Check Referer or Origin headers (e.g. from browser UI)
    for hdr in ["referer", "origin"]:
        val = request.headers.get(hdr)
        if val:
            import urllib.parse
            parsed = urllib.parse.urlparse(val)
            if parsed.netloc and not parsed.netloc.startswith("localhost") and not parsed.netloc.startswith("127.0.0.1"):
                return f"{parsed.scheme}://{parsed.netloc}".replace("/api/v1", "").rstrip("/")

    # 4. Check tokens_store for any saved token with a real remote serverUrl
    try:
        from backend.app.api.v1.agents import tokens_store
        for t in tokens_store:
            s_url = t.get("serverUrl", "")
            if s_url and not s_url.startswith("http://localhost") and not s_url.startswith("http://127.0.0.1"):
                return s_url.strip().rstrip("/").replace("/api/v1", "").rstrip("/")
    except Exception:
        pass

    # 5. Check environment variable (SERVER_URL / WM_SERVER / APP_URL)
    env_server = os.getenv("SERVER_URL") or os.getenv("WM_SERVER") or os.getenv("APP_URL") or ""
    if env_server and "localhost" not in env_server and "127.0.0.1" not in env_server:
        return env_server.strip().rstrip("/").replace("/api/v1", "").rstrip("/")

    # 6. Fallback: Detect the server's local LAN IP communicating with the client
    client_ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host

    port = getattr(settings, "PORT", 2301) or 2301

    if client_ip and not client_ip.startswith("127."):
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((client_ip, 80))
            real_ip = s.getsockname()[0]
            s.close()
            if real_ip and real_ip not in ["127.0.0.1", "0.0.0.0"] and not real_ip.startswith("172.17.") and not real_ip.startswith("172.18."):
                return f"http://{real_ip}:{port}"
        except Exception:
            pass

    # 7. Auto-detect primary non-loopback LAN IP for local requests so installers point to real network address
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
        if lan_ip and lan_ip not in ["127.0.0.1", "0.0.0.0"] and not lan_ip.startswith("172.17.") and not lan_ip.startswith("172.18."):
            return f"http://{lan_ip}:{port}"
    except Exception:
        pass

    # 8. Multi-interface enumeration fallback (offline / air-gapped / isolated corporate networks)
    try:
        import psutil
        candidates = []
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127.") and not addr.address.startswith("169.254."):
                    ip = addr.address
                    if not ip.startswith("172.17.") and not ip.startswith("172.18."):
                        candidates.append(ip)
        if candidates:
            # Filter out virtual / host-only adapters (VMware 192.168.174.x, 192.168.236.x, VirtualBox 192.168.56.x)
            real_lan = [c for c in candidates if c.startswith("192.168.") and not c.startswith("192.168.174.") and not c.startswith("192.168.236.") and not c.startswith("192.168.56.")]
            if not real_lan:
                real_lan = [c for c in candidates if c.startswith("10.") or (c.startswith("172.") and 16 <= int(c.split(".")[1]) <= 31)]
            best = real_lan[0] if real_lan else candidates[0]
            return f"http://{best}:{port}"
    except Exception:
        pass

    try:
        addrs = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        ips = [a[4][0] for a in addrs if not a[4][0].startswith("127.") and not a[4][0].startswith("169.254.")]
        if ips:
            return f"http://{ips[0]}:{port}"
    except Exception:
        pass

    # 9. Final fallback (strictly guarantee NEVER returning localhost or 127.0.0.1)
    raw_base = str(request.base_url).rstrip("/")
    res = raw_base.replace("/api/v1", "").rstrip("/")
    if "localhost" in res or "127.0.0.1" in res or "0.0.0.0" in res:
        return f"http://192.168.1.109:{port}"
    return res

def get_windows_installer_ps1(base_url: str, token: str) -> str:
    template_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "standalone_installer.ps1")
    if not os.path.exists(template_path):
        template_path = os.path.join("agent", "standalone_installer.ps1")
    with open(template_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    return content.replace("__SERVER_URL__", base_url).replace("__TOKEN__", token)

def get_windows_uninstaller_ps1(base_url: str = "") -> str:
    template_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "standalone_uninstaller.ps1")
    if not os.path.exists(template_path):
        template_path = os.path.join("agent", "standalone_uninstaller.ps1")
    with open(template_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    return content.replace("__SERVER_URL__", base_url)

def make_safe_attachment_header(filename: str, fallback_ascii: str = "installer") -> str:
    """
    Format Content-Disposition safely conforming to RFC 6266 / RFC 5987.
    Uses pure ASCII for the fallback 'filename=' (so Starlette's latin-1 header encoding never fails)
    and RFC 5987 UTF-8 percent-encoded 'filename*=UTF-8\'\'...' for modern browsers to display Unicode/Cyrillic names.
    """
    import urllib.parse
    ascii_clean = "".join(c if c.isascii() and (c.isalnum() or c in ".-_") else "_" for c in filename).strip("._")
    if not ascii_clean:
        ascii_clean = fallback_ascii
    encoded_utf8 = urllib.parse.quote(filename, safe=".-_")
    return f'attachment; filename="{ascii_clean}"; filename*=UTF-8\'\'{encoded_utf8}'

@app.get("/install.bat", response_class=PlainTextResponse)
@app.get("/install-agent.bat", response_class=PlainTextResponse)
@app.get("/api/v1/install.bat", response_class=PlainTextResponse)
@app.get("/api/v1/agents/install.bat", response_class=PlainTextResponse)
async def get_windows_batch_installer(request: Request, token: str = "", server_url: str = "", group: str = ""):
    """
    Serve a robust 1-Click Windows Batch Installer (.bat).
    Double-clicking this file executes the PowerShell collector in-place with guaranteed output and pause.
    """
    import urllib.parse
    base_url = resolve_request_base_url(request, server_url)
    
    effective_token = token or "wm_tok_live_7f8a92b3c4d5e6f7"

    # Auto-detect group from tokens_store if not supplied
    if not group and token:
        try:
            from backend.app.api.v1.agents import tokens_store
            tok_obj = next((t for t in tokens_store if t.get("token") == token), None)
            if tok_obj and tok_obj.get("targetGroup"):
                group = tok_obj.get("targetGroup")
        except Exception:
            pass

    safe_group = "".join(c for c in group if c.isalnum() or c in ("-", "_", " ")).strip()
    group_suffix = f"-{safe_group}" if safe_group else ""
    filename = f"Install-WorkstationAgent{group_suffix}.bat"

    bat_content = f"""@echo off
setlocal
chcp 65001 >nul
title Workstation Manager Agent Setup

:: Auto-elevate to Administrator with UAC prompt
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Requesting Administrator permissions...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cls
echo ==============================================================================
echo        WORKSTATION MANAGER - AGENT INSTALLER (ADMINISTRATOR)
echo ==============================================================================
echo.
echo [*] Target Server: {base_url}
echo [*] Launching PowerShell Agent Setup...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $dst = [IO.Path]::Combine($env:TEMP, 'Install-WorkstationAgent.ps1'); $wc = New-Object Net.WebClient; $wc.Proxy = $null; try {{ $wc.DownloadFile('{base_url}/install.ps1?token={effective_token}&download=1', $dst) }} catch {{ Write-Host '[!] Error: Cannot download installer from {base_url}' -ForegroundColor Red; Write-Host ('[!] ' + $_.Exception.Message) -ForegroundColor Yellow; exit 1 }}; $bytes = [IO.File]::ReadAllBytes($dst); if ($bytes.Length -ge 3 -and ($bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF)) {{ [IO.File]::WriteAllBytes($dst, ([byte[]](0xEF, 0xBB, 0xBF) + $bytes)) }}; & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $dst -ServerUrl '{base_url}' -Token '{effective_token}'; Remove-Item $dst -Force -ErrorAction SilentlyContinue"

echo.
echo ==============================================================================
echo  Execution finished. Press any key to close this window...
echo ==============================================================================
pause
exit /b
""".replace("\n", "\r\n")

    headers = {
        "Content-Disposition": make_safe_attachment_header(filename, fallback_ascii="Install-WorkstationAgent.bat")
    }
    return PlainTextResponse(bat_content, media_type="application/x-bat", headers=headers)

@app.get("/install_full.ps1")
@app.get("/install-full.ps1")
async def get_windows_installer_full_ps1_endpoint(request: Request, token: str = "", server_url: str = "", download: bool = False):
    """
    Serve raw, complete Windows installer script for direct execution.
    """
    base_url = resolve_request_base_url(request, server_url)
    clean_token = token.split("_0123")[0] if token else "wm_tok_live_7f8a92b3c4d5e6f7"
    content = get_windows_installer_ps1(base_url, clean_token)
    if download:
        return Response(content=content.encode("utf-8-sig"), media_type="text/plain; charset=utf-8")
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")

@app.get("/install.ps1")
@app.get("/installer.ps1")
@app.get("/api/v1/install.ps1")
@app.get("/api/v1/installer.ps1")
@app.get("/api/v1/agents/install.ps1")
@app.get("/api/v1/agents/installer.ps1")
async def get_windows_installer_ps1_endpoint(request: Request, token: str = "", server_url: str = "", group: str = "", download: bool = False):
    """
    Serve dynamic Windows installer script with embedded server URL & token.
    Allows one-liner: irm "http://<server>:2301/install.ps1?token=XYZ" | iex
    """
    import urllib.parse
    base_url = resolve_request_base_url(request, server_url)
    
    effective_token = token or "wm_tok_live_7f8a92b3c4d5e6f7"
    content = get_windows_installer_ps1(base_url, effective_token)

    headers = {}
    if download:
        safe_group = "".join(c for c in group if c.isalnum() or c in ("-", "_", " ")).strip()
        group_suffix = f"-{safe_group}" if safe_group else ""
        filename = f"Install-Agent{group_suffix}.ps1"
        headers["Content-Disposition"] = make_safe_attachment_header(filename, fallback_ascii="Install-Agent.ps1")
        return Response(content=content.encode("utf-8-sig"), media_type="text/plain; charset=utf-8", headers=headers)

    # In-memory execution (irm ... | iex) requires pure UTF-8 WITHOUT BOM so PowerShell 5.1 doesn't treat \uFEFF as command name
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers=headers)

def get_windows_agent_service_ps1(base_url: str, device_id: str = "", mac: str = "") -> str:
    template_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "standalone_installer.ps1")
    if not os.path.exists(template_path):
        template_path = os.path.join("agent", "standalone_installer.ps1")
    with open(template_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    
    start_marker = '$serviceScriptCode = @"'
    end_marker = '"@'
    if start_marker in content:
        code_part = content.split(start_marker, 1)[1].split(end_marker, 1)[0].strip()
        if device_id:
            code_part = code_part.replace("`$DeviceId = '$deviceId'", f"`$DeviceId = '{device_id}'")
        else:
            code_part = code_part.replace("`$DeviceId = '$deviceId'", "`$DeviceId = ''")
        if mac:
            code_part = code_part.replace("`$DeviceMac = '$mac'", f"`$DeviceMac = '{mac}'")
        else:
            code_part = code_part.replace("`$DeviceMac = '$mac'", "`$DeviceMac = ''")
        if base_url:
            code_part = code_part.replace("`$ServerUrl = '$ServerUrl'", f"`$ServerUrl = '{base_url}'")
        else:
            code_part = code_part.replace("`$ServerUrl = '$ServerUrl'", "`$ServerUrl = ''")
        
        # Clean any literal single-quoted placeholders
        code_part = code_part.replace("'$InstallDir'", "$InstallDir")
        code_part = code_part.replace("'$Token'", "''")
        code_part = code_part.replace("'$osCaption'", "''")
        code_part = code_part.replace("`$", "$")
        code_part = code_part.replace("'$deviceId'", f"'{device_id}'" if device_id else "''")
        code_part = code_part.replace("'$mac'", f"'{mac}'" if mac else "''")
        code_part = code_part.replace("'$ServerUrl'", f"'{base_url}'" if base_url else "''")
        return code_part
    return content

@app.get("/agent.ps1")
@app.get("/api/v1/agents/service-script")
async def get_windows_service_script_endpoint(request: Request, server_url: str = "", deviceId: str = "", mac: str = ""):
    """
    Serve pure, lightweight Windows Agent Service runtime script for instant OTA update.
    """
    base_url = resolve_request_base_url(request, server_url)
    content = get_windows_agent_service_ps1(base_url, deviceId, mac)
    return Response(content=content.encode("utf-8-sig"), media_type="text/plain; charset=utf-8")

@app.get("/agent.py")
@app.get("/api/v1/agents/agent.py")
async def get_python_agent_script_endpoint():
    """
    Serve Python standalone agent script.
    """
    path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "agent_standalone.py")
    if not os.path.exists(path):
        path = os.path.join("agent", "agent_standalone.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return PlainTextResponse(content, media_type="text/x-python; charset=utf-8")

@app.get("/uninstall.ps1")
async def get_windows_uninstaller_ps1_endpoint(request: Request, server_url: str = "", download: bool = False):
    """
    Serve pure Windows uninstaller script.
    Allows one-liner: irm "http://<server>:2301/uninstall.ps1" | iex
    """
    base_url = resolve_request_base_url(request, server_url)
    content = get_windows_uninstaller_ps1(base_url)
    headers = {}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="Uninstall-Agent.ps1"'
        return Response(content=content.encode("utf-8-sig"), media_type="text/plain; charset=utf-8", headers=headers)
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers=headers)

@app.get("/uninstall.bat", response_class=PlainTextResponse)
@app.get("/uninstall-agent.bat", response_class=PlainTextResponse)
async def get_windows_uninstaller_batch(request: Request, server_url: str = ""):
    """
    Serve a single standalone 1-Click Windows Uninstaller (.bat).
    Double-clicking this file cleanly stops the agent process, removes scheduled tasks, and wipes agent files.
    """
    base_url = resolve_request_base_url(request, server_url)

    uninstaller_bat = f"""@echo off
setlocal
chcp 65001 >nul
title Workstation Manager Agent Uninstaller

:: Auto-elevate to Administrator with UAC prompt
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Requesting Administrator permissions...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cls
echo ==============================================================================
echo        WORKSTATION MANAGER - AGENT UNINSTALLER (ADMINISTRATOR)
echo ==============================================================================
echo.
echo [*] Target Server: {base_url}
echo [*] Launching PowerShell Agent Uninstaller...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $dst = [IO.Path]::Combine($env:TEMP, 'Uninstall-WorkstationAgent.ps1'); $wc = New-Object Net.WebClient; $wc.Proxy = $null; try {{ $wc.DownloadFile('{base_url}/uninstall.ps1?server_url={base_url}&download=1', $dst) }} catch {{ Write-Host '[!] Error: Cannot download uninstaller from {base_url}' -ForegroundColor Red; exit 1 }}; $bytes = [IO.File]::ReadAllBytes($dst); if ($bytes.Length -ge 3 -and ($bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF)) {{ [IO.File]::WriteAllBytes($dst, ([byte[]](0xEF, 0xBB, 0xBF) + $bytes)) }}; & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $dst; Remove-Item $dst -Force -ErrorAction SilentlyContinue"

echo.
echo ==============================================================================
echo  Uninstallation finished. Press any key to close this window...
echo ==============================================================================
pause
exit /b
""".replace("\n", "\r\n")

    headers = {
        "Content-Disposition": 'attachment; filename="Uninstall-WorkstationAgent.bat"'
    }
    return PlainTextResponse(uninstaller_bat, media_type="application/x-bat", headers=headers)

@app.get("/install.sh", response_class=PlainTextResponse)
async def get_linux_installer(request: Request, token: str = "", server_url: str = "", group: str = "", download: bool = False):
    """
    Serve dynamic Linux installer script with embedded server URL & token.
    Allows one-liner: curl -fsSL "http://<server>:2301/install.sh?token=XYZ" | sudo bash
    """
    import urllib.parse
    base_url = resolve_request_base_url(request, server_url)

    # Auto-detect group from tokens_store if not supplied
    if not group and token:
        try:
            from backend.app.api.v1.agents import tokens_store
            tok_obj = next((t for t in tokens_store if t.get("token") == token), None)
            if tok_obj and tok_obj.get("targetGroup"):
                group = tok_obj.get("targetGroup")
        except Exception:
            pass

    script_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "install_linux.sh")
    if not os.path.exists(script_path):
        script_path = os.path.join("agent", "install_linux.sh")

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace('__SERVER_URL__', base_url)
    content = content.replace('__SERVER_URL_PLACEHOLDER__', base_url)
    content = content.replace('__TOKEN__', token or "wm_tok_live_7f8a92b3c4d5e6f7")
    content = content.replace('__TOKEN_PLACEHOLDER__', token or "wm_tok_live_7f8a92b3c4d5e6f7")
    content = content.replace('__GROUP__', group or "Office")

    headers = {}
    if download:
        safe_group = "".join(c for c in group if c.isalnum() or c in ("-", "_", " ")).strip()
        group_suffix = f"_{safe_group}" if safe_group else ""
        filename = f"install_agent{group_suffix}.sh"
        headers["Content-Disposition"] = make_safe_attachment_header(filename, fallback_ascii="install_agent.sh")

    return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers=headers)

@app.get("/uninstall.sh", response_class=PlainTextResponse)
@app.get("/uninstall_linux.sh", response_class=PlainTextResponse)
async def get_linux_uninstaller_endpoint(request: Request, server_url: str = "", download: bool = False):
    """
    Serve pure Linux uninstaller script with dynamic SERVER_URL.
    Allows one-liner: curl -fsSL "http://<server>:2301/uninstall.sh" | sudo bash
    """
    base_url = resolve_request_base_url(request, server_url)

    script_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "uninstall_linux.sh")
    if not os.path.exists(script_path):
        script_path = os.path.join("agent", "uninstall_linux.sh")

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace('DEFAULT_SERVER_URL="__SERVER_URL_VALUE__"', f'DEFAULT_SERVER_URL="{base_url}"')
    content = content.replace('__SERVER_URL_PLACEHOLDER__', base_url)

    headers = {}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="uninstall_agent.sh"'

    return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers=headers)

@app.get("/agent.py", response_class=PlainTextResponse)
@app.get("/agent_standalone.py", response_class=PlainTextResponse)
async def get_agent_payload(download: bool = False):
    """
    Serve standalone background agent script for automated deployment.
    """
    agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "agent_standalone.py")
    if not os.path.exists(agent_path):
        agent_path = os.path.join("agent", "agent_standalone.py")

    with open(agent_path, "r", encoding="utf-8") as f:
        content = f.read()

    headers = {}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="agent.py"'

    return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers=headers)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect_client(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"ACK: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect_client(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
