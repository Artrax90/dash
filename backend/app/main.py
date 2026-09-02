import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.db.session import engine, Base
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

@app.on_event("startup")
async def startup_event():
    # Initialize DB schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        def migrate_columns(connection):
            from sqlalchemy import text
            for col_sql in [
                "ALTER TABLE devices ADD COLUMN boot_time DATETIME",
                "ALTER TABLE devices ADD COLUMN uptime_seconds INTEGER DEFAULT 0",
            ]:
                try:
                    connection.execute(text(col_sql))
                except Exception:
                    pass
        await conn.run_sync(migrate_columns)
    print("Workstation Manager database initialized.")
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
    base_url = server_url or str(request.base_url).rstrip("/")
    base_url = base_url.replace("/api/v1", "").rstrip("/")
    
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
    encoded_fn = urllib.parse.quote(filename)

    bat_content = f"""@echo off
setlocal
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
echo [*] Launching PowerShell Agent Setup...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $wc = New-Object System.Net.WebClient; $wc.Encoding = [System.Text.Encoding]::UTF8; iex $wc.DownloadString('{base_url}/install.ps1?token={effective_token}')"

echo.
echo ==============================================================================
echo  Execution finished. Press any key to close this window...
echo ==============================================================================
pause
exit /b
""".replace("\n", "\r\n")

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_fn}'
    }
    return PlainTextResponse(bat_content, media_type="application/x-bat", headers=headers)

@app.get("/install_full.ps1")
@app.get("/install-full.ps1")
async def get_windows_installer_full_ps1_endpoint(request: Request, token: str = "", server_url: str = ""):
    """
    Serve raw, complete Windows installer script for direct execution.
    """
    base_url = server_url or str(request.base_url).rstrip("/")
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    clean_token = token.split("_0123")[0] if token else "wm_tok_live_7f8a92b3c4d5e6f7"
    content = get_windows_installer_ps1(base_url, clean_token)
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
    base_url = server_url or str(request.base_url).rstrip("/")
    base_url = base_url.replace("/api/v1", "").rstrip("/")
    
    effective_token = token or "wm_tok_live_7f8a92b3c4d5e6f7"
    content = get_windows_installer_ps1(base_url, effective_token)

    headers = {}
    if download:
        safe_group = "".join(c for c in group if c.isalnum() or c in ("-", "_", " ")).strip()
        group_suffix = f"-{safe_group}" if safe_group else ""
        filename = f"Install-Agent{group_suffix}.ps1"
        encoded_fn = urllib.parse.quote(filename)
        headers["Content-Disposition"] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_fn}'
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
        if mac:
            code_part = code_part.replace("`$DeviceMac = '$mac'", f"`$DeviceMac = '{mac}'")
        if base_url:
            code_part = code_part.replace("`$ServerUrl = '$ServerUrl'", f"`$ServerUrl = '{base_url}'")
        code_part = code_part.replace("`$", "$")
        return code_part
    return content

@app.get("/agent.ps1")
@app.get("/api/v1/agents/service-script")
async def get_windows_service_script_endpoint(request: Request, server_url: str = "", deviceId: str = "", mac: str = ""):
    """
    Serve pure, lightweight Windows Agent Service runtime script for instant OTA update.
    """
    base_url = server_url or str(request.base_url).rstrip("/")
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    content = get_windows_agent_service_ps1(base_url, deviceId, mac)
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")

@app.get("/uninstall.ps1")
async def get_windows_uninstaller_ps1_endpoint(request: Request, server_url: str = "", download: bool = False):
    """
    Serve pure Windows uninstaller script.
    Allows one-liner: irm "http://<server>:2301/uninstall.ps1" | iex
    """
    base_url = server_url or str(request.base_url).rstrip("/")
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    content = get_windows_uninstaller_ps1(base_url)
    headers = {}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="Uninstall-Agent.ps1"'
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers=headers)

@app.get("/uninstall.bat", response_class=PlainTextResponse)
@app.get("/uninstall-agent.bat", response_class=PlainTextResponse)
async def get_windows_uninstaller_batch(request: Request, server_url: str = ""):
    """
    Serve a single standalone 1-Click Windows Uninstaller (.bat).
    Double-clicking this file cleanly stops the agent process, removes scheduled tasks, and wipes agent files.
    """
    base_url = server_url or str(request.base_url).rstrip("/")
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    uninstaller_bat = f"""@echo off
setlocal
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
echo [*] Launching PowerShell Agent Uninstaller...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $wc = New-Object System.Net.WebClient; $wc.Encoding = [System.Text.Encoding]::UTF8; iex $wc.DownloadString('{base_url}/uninstall.ps1?server_url={base_url}')"

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
    base_url = server_url or str(request.base_url).rstrip("/")
    if base_url.endswith("/"):
        base_url = base_url[:-1]

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
        encoded_fn = urllib.parse.quote(filename)
        headers["Content-Disposition"] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_fn}'

    return PlainTextResponse(content, media_type="text/plain; charset=utf-8", headers=headers)

@app.get("/uninstall.sh", response_class=PlainTextResponse)
@app.get("/uninstall_linux.sh", response_class=PlainTextResponse)
async def get_linux_uninstaller_endpoint(request: Request, server_url: str = "", download: bool = False):
    """
    Serve pure Linux uninstaller script with dynamic SERVER_URL.
    Allows one-liner: curl -fsSL "http://<server>:2301/uninstall.sh" | sudo bash
    """
    base_url = server_url or str(request.base_url).rstrip("/")
    if base_url.endswith("/"):
        base_url = base_url[:-1]

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
