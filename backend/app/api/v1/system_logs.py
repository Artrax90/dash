import os
import re
import json
import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from backend.app.api.v1.users import require_superadmin, is_superadmin_role, load_users, get_current_user_from_request

router = APIRouter(prefix="/system", tags=["system-logs"])

# Silence httpx internal client logging so queries to docker.sock don't flood the server log
logging.getLogger("httpx").setLevel(logging.WARNING)

# In-memory circular buffer of recent logs (fallback when Docker socket is not mounted / during local dev & tests)
IN_MEMORY_LOGS_MAX = 3000
in_memory_log_buffer: deque = deque(maxlen=IN_MEMORY_LOGS_MAX)

class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            now_iso = datetime.now(timezone.utc).isoformat()
            in_memory_log_buffer.append({
                "timestamp": now_iso,
                "level": record.levelname.upper(),
                "stream": "stderr" if record.levelno >= logging.WARNING else "stdout",
                "message": msg,
                "raw": f"{now_iso} [{record.levelname.upper()}] {msg}"
            })
        except Exception:
            pass

# Attach memory log handler to root and app loggers
_mem_handler = MemoryLogHandler()
_mem_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger("workstation_manager").addHandler(_mem_handler)
logging.getLogger("uvicorn").addHandler(_mem_handler)

# Pre-populate buffer with initial startup log
if not in_memory_log_buffer:
    _init_ts = datetime.now(timezone.utc).isoformat()
    in_memory_log_buffer.append({
        "timestamp": _init_ts,
        "level": "INFO",
        "stream": "stdout",
        "message": "Workstation Manager system logger initialized",
        "raw": f"{_init_ts} [INFO] Workstation Manager system logger initialized"
    })

DEFAULT_CONTAINERS = [
    {
        "id": "workstation-manager",
        "name": "workstation-manager",
        "role": "Основной сервер (FastAPI, Планировщик, React UI)",
        "isDefault": True
    },
    {
        "id": "workstation-manager-postgres",
        "name": "workstation-manager-postgres",
        "role": "База данных PostgreSQL",
        "isDefault": False
    }
]

DOCKER_SOCKET_PATH = "/var/run/docker.sock"

def detect_log_level(text: str, stream: str = "stdout") -> str:
    """
    Detect log level based on content keywords.
    Priority is given to explicit bracketed levels [INFO], [WARN], [ERROR], [DEBUG].
    """
    upper = text.upper()

    # 1. Exact bracketed tags or colon patterns
    if "[ERROR]" in upper or "[CRITICAL]" in upper or "ERROR:" in upper or "CRITICAL:" in upper:
        return "ERROR"
    if "[WARN]" in upper or "[WARNING]" in upper or "WARNING:" in upper or "WARN:" in upper:
        return "WARN"
    if "[DEBUG]" in upper or "DEBUG:" in upper:
        return "DEBUG"
    if "[INFO]" in upper or "INFO:" in upper:
        return "INFO"

    # 2. General keywords only if not explicitly marked [INFO]/[DEBUG]
    if re.search(r"\b(TRACEBACK|EXCEPTION|FATAL)\b", upper):
        return "ERROR"

    # 3. Stream check: only flag ERROR if stream is stderr AND contains whole-word error tokens
    # Never match substrings like 'err' inside 'stderr' or URL query params
    if stream == "stderr":
        if re.search(r"\b(ERROR|FAIL|FAILED|FATAL|DENIED|CRITICAL)\b", upper):
            return "ERROR"
        if re.search(r"\b(WARNING|WARN)\b", upper):
            return "WARN"

    return "INFO"

def is_internal_logs_request(msg: str) -> bool:
    """Detects internal log queries to prevent infinite self-logging loops."""
    m_lower = msg.lower()
    return (
        "containers/workstation-manager/logs" in m_lower
        or "containers/workstation-manager-postgres/logs" in m_lower
        or "/api/v1/system/logs" in m_lower
        or "http request: get http://localhost/containers/" in m_lower
    )

def parse_docker_frame_stream(data: bytes) -> List[Dict[str, Any]]:
    """
    Parses Docker container logs stream. Handles both multiplexed 8-byte frame header
    format and plain-text fallback.
    """
    entries = []
    if not data:
        return entries

    offset = 0
    length = len(data)

    # Check if multiplexed stream (Docker multiplexes stdout/stderr into 8-byte frames)
    # Header format: [STREAM_TYPE (1 byte)][0 0 0 (3 bytes)][FRAME_SIZE (4 bytes big-endian)]
    is_multiplexed = False
    if length >= 8 and data[1:4] == b'\x00\x00\x00':
        frame_len = int.from_bytes(data[4:8], byteorder='big')
        if frame_len <= length - 8:
            is_multiplexed = True

    if is_multiplexed:
        while offset + 8 <= length:
            stream_type = data[offset]
            stream_name = "stderr" if stream_type == 2 else "stdout"
            frame_len = int.from_bytes(data[offset + 4:offset + 8], byteorder='big')
            offset += 8
            if offset + frame_len > length:
                chunk = data[offset:]
                offset = length
            else:
                chunk = data[offset:offset + frame_len]
                offset += frame_len

            lines = chunk.decode("utf-8", errors="replace").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                ts, msg = _split_timestamp_and_message(line)
                lvl = detect_log_level(msg, stream_name)
                # If explicit [INFO] or [DEBUG], don't flag stream as stderr to avoid scary red badges
                actual_stream = "stdout" if lvl in ["INFO", "DEBUG"] else stream_name
                entries.append({
                    "timestamp": ts,
                    "level": lvl,
                    "stream": actual_stream,
                    "message": msg,
                    "raw": line
                })
    else:
        # Plain text lines
        text = data.decode("utf-8", errors="replace")
        for line in text.splitlines():
            if not line.strip():
                continue
            ts, msg = _split_timestamp_and_message(line)
            lvl = detect_log_level(msg, "stdout")
            entries.append({
                "timestamp": ts,
                "level": lvl,
                "stream": "stdout",
                "message": msg,
                "raw": line
            })

    return entries

def _split_timestamp_and_message(line: str) -> (str, str):
    """Splits ISO timestamp prefix if present in docker logs --timestamps output."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))\s+(.*)$", line)
    if match:
        return match.group(1), match.group(2)
    return datetime.now(timezone.utc).isoformat(), line

async def fetch_docker_logs_via_socket(container_name: str, tail: int = 500) -> Optional[List[Dict[str, Any]]]:
    """Fetches logs directly from Docker Engine via Unix domain socket."""
    if not os.path.exists(DOCKER_SOCKET_PATH):
        return None

    url = f"http://localhost/containers/{container_name}/logs?stdout=1&stderr=1&tail={tail}&timestamps=1"
    try:
        transport = httpx.AsyncHTTPTransport(uds=DOCKER_SOCKET_PATH)
        async with httpx.AsyncClient(transport=transport, timeout=6.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return parse_docker_frame_stream(resp.content)
            elif resp.status_code == 404:
                return [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "WARN",
                    "stream": "stderr",
                    "message": f"Контейнер '{container_name}' не найден в Docker Engine",
                    "raw": f"Container {container_name} not found"
                }]
    except Exception as e:
        print(f"[Docker Logs UDS Error] {e}")
        return None
    return None

async def fetch_docker_logs_via_cli(container_name: str, tail: int = 500) -> Optional[List[Dict[str, Any]]]:
    """Fallback: fetches logs via docker CLI if available and daemon is running."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "logs", "--tail", str(tail), "-t", container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        # If docker daemon is not running or command failed, return None so we fallback to in-memory logs
        if proc.returncode != 0:
            return None
        combined = (stdout or b"") + (stderr or b"")
        if combined:
            return parse_docker_frame_stream(combined)
    except Exception:
        pass
    return None

@router.get("/containers")
async def list_system_containers(request: Request):
    """
    Returns list of monitored system Docker containers.
    Restricted strictly to Superadministrator role.
    """
    require_superadmin(request)

    containers = list(DEFAULT_CONTAINERS)

    # If Docker socket is present, check dynamic status
    if os.path.exists(DOCKER_SOCKET_PATH):
        try:
            transport = httpx.AsyncHTTPTransport(uds=DOCKER_SOCKET_PATH)
            async with httpx.AsyncClient(transport=transport, timeout=3.0) as client:
                r = await client.get("http://localhost/containers/json?all=1")
                if r.status_code == 200:
                    raw_list = r.json()
                    existing_names = set()
                    dynamic_containers = []
                    for c in raw_list:
                        c_names = [n.lstrip("/") for n in c.get("Names", [])]
                        for c_name in c_names:
                            if "workstation" in c_name or "postgres" in c_name:
                                existing_names.add(c_name)
                                dynamic_containers.append({
                                    "id": c_name,
                                    "name": c_name,
                                    "status": c.get("State", "running"),
                                    "role": "Основной сервер" if c_name == "workstation-manager" else "Сервисный контейнер",
                                    "isDefault": c_name == "workstation-manager"
                                })
                    if dynamic_containers:
                        containers = dynamic_containers
        except Exception:
            pass

    return {"containers": containers}

@router.get("/logs")
async def get_system_logs(
    request: Request,
    container: str = Query("workstation-manager", description="Target container name"),
    tail: int = Query(500, ge=1, le=5000, description="Number of tail lines"),
    level: Optional[str] = Query(None, description="Log level filter: ERROR, WARN, INFO, DEBUG"),
    search: Optional[str] = Query(None, description="Text or regex search"),
    since: Optional[str] = Query(None, description="Filter logs since ISO datetime"),
    until: Optional[str] = Query(None, description="Filter logs until ISO datetime"),
    show_internal: bool = Query(False, description="Include internal log polling lines")
):
    """
    Fetches container logs with filtering by level, search string, and datetime.
    Restricted strictly to Superadministrator role.
    """
    require_superadmin(request)

    # 1. Try Docker socket
    logs = await fetch_docker_logs_via_socket(container, tail=tail)

    # 2. Try Docker CLI
    if logs is None:
        logs = await fetch_docker_logs_via_cli(container, tail=tail)

    # 3. Fallback to in-memory application log buffer
    if logs is None or len(logs) == 0:
        logs = list(in_memory_log_buffer)[-tail:]

    # Apply filters
    filtered = []
    level_filter = level.strip().upper() if level and level.strip().upper() != "ALL" else None
    search_filter = search.strip().lower() if search and search.strip() else None

    # Normalization helper for ISO / datetime-local strings (e.g. '2026-09-16T12:00')
    clean_since = since.strip().replace(" ", "T") if since and since.strip() else None
    clean_until = until.strip().replace(" ", "T") if until and until.strip() else None

    for entry in logs:
        msg = entry.get("message", "")
        raw = entry.get("raw", "")

        # Omit internal log polling queries so the viewer shows real system events
        if not show_internal and is_internal_logs_request(msg):
            continue

        # Filter by level
        if level_filter:
            entry_level = entry.get("level", "INFO").upper()
            if level_filter == "ERROR" and entry_level != "ERROR":
                continue
            elif level_filter == "WARN" and entry_level not in ["WARN", "ERROR"]:
                continue
            elif level_filter not in ["ERROR", "WARN"] and entry_level != level_filter:
                continue

        # Filter by search keyword
        if search_filter:
            msg_lower = msg.lower()
            raw_lower = raw.lower()
            if search_filter not in msg_lower and search_filter not in raw_lower:
                continue

        # Filter by datetime range (since / until)
        entry_ts = (entry.get("timestamp") or "").replace(" ", "T")
        if clean_since:
            try:
                # Compare prefixes or full ISO
                if entry_ts[:len(clean_since)] < clean_since:
                    continue
            except Exception:
                pass

        if clean_until:
            try:
                if entry_ts[:len(clean_until)] > clean_until:
                    continue
            except Exception:
                pass

        filtered.append(entry)

    return {
        "container": container,
        "total": len(filtered),
        "source": "docker_socket" if os.path.exists(DOCKER_SOCKET_PATH) else "in_memory",
        "logs": filtered
    }

@router.websocket("/logs/ws")
async def stream_system_logs_websocket(websocket: WebSocket):
    """
    Real-time WebSocket streaming of container logs.
    Authenticated and restricted to Superadmin.
    """
    await websocket.accept()

    # Query params check for auth
    role = websocket.query_params.get("role")
    token = websocket.query_params.get("token")
    container = websocket.query_params.get("container", "workstation-manager")

    is_authorized = False
    if role and is_superadmin_role(role):
        is_authorized = True
    elif not load_users():
        # Dev mode with no users registered
        is_authorized = True

    if not is_authorized:
        await websocket.send_json({"type": "error", "message": "Отказ в доступе: требуется роль Суперадминистратор"})
        await websocket.close(code=4003)
        return

    # Stream initial batch of logs
    init_logs = await fetch_docker_logs_via_socket(container, tail=150)
    if not init_logs:
        init_logs = list(in_memory_log_buffer)[-150:]

    clean_init = [l for l in init_logs if not is_internal_logs_request(l.get("message", ""))]

    await websocket.send_json({
        "type": "init",
        "container": container,
        "logs": clean_init
    })

    last_seen_raw = clean_init[-1]["raw"] if clean_init else ""

    # Streaming loop
    try:
        while True:
            await asyncio.sleep(1.5)
            # Poll latest logs
            latest_logs = await fetch_docker_logs_via_socket(container, tail=50)
            if not latest_logs:
                latest_logs = list(in_memory_log_buffer)[-50:]

            clean_latest = [l for l in latest_logs if not is_internal_logs_request(l.get("message", ""))]

            if clean_latest:
                # Find new lines after last_seen_raw
                new_lines = []
                if last_seen_raw:
                    found = False
                    for entry in clean_latest:
                        if found:
                            new_lines.append(entry)
                        elif entry["raw"] == last_seen_raw:
                            found = True
                    if not found:
                        new_lines = clean_latest[-5:]
                else:
                    new_lines = clean_latest[-5:]

                if new_lines:
                    last_seen_raw = new_lines[-1]["raw"]
                    for new_entry in new_lines:
                        await websocket.send_json({
                            "type": "log",
                            "entry": new_entry
                        })
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        print(f"[WebSocket Logs Stream Error] {e}")
