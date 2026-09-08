import json
import os
import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
from backend.app.core.config import settings

router = APIRouter(prefix="/users", tags=["users"])

USERS_FILE = os.path.join(settings.DATA_DIR, "users.json")

SESSIONS_FILE = os.path.join(settings.DATA_DIR, "active_sessions.json")

def _load_sessions() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_sessions():
    try:
        os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(user_active_sessions, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# Persistent single active session per username: username_lower -> {"token": token, "loginTime": ...}
user_active_sessions: Dict[str, Dict[str, Any]] = _load_sessions()

def register_user_session(username: str, token: Optional[str] = None) -> str:
    """
    Registers a single active session for the given username.
    If an existing session exists, it is invalidated.
    Returns the new valid session token.
    """
    clean_username = (username or "").strip().lower()
    if not clean_username:
        clean_username = "admin"
    new_token = token or f"wm_sess_{secrets.token_hex(24)}"
    user_active_sessions[clean_username] = {
        "token": new_token,
        "loginTime": datetime.now(timezone.utc).isoformat()
    }
    _save_sessions()
    return new_token

def validate_user_session(username: str, token: str) -> bool:
    """
    Validates if the provided token matches the single active session for the user.
    """
    clean_username = (username or "").strip().lower()
    if not clean_username or not token:
        return False
    sess = user_active_sessions.get(clean_username)
    if not sess:
        # If no active session tracked yet, return False
        return False
    return sess.get("token") == token

def revoke_user_sessions(username: str):
    """
    Revokes any active session for the given user.
    """
    clean_username = (username or "").strip().lower()
    if clean_username in user_active_sessions:
        del user_active_sessions[clean_username]
        _save_sessions()


def is_superadmin_role(role: Optional[str]) -> bool:
    if not role:
        return False
    r = role.strip().lower().replace("-", " ").replace("_", " ")
    return r in {
        "суперадминистратор",
        "superadmin",
        "super admin",
        "главный администратор",
        "главный суперадминистратор",
        "root",
    }

def is_fleetadmin_role(role: Optional[str]) -> bool:
    if not role:
        return False
    r = role.strip().lower().replace("-", " ").replace("_", " ")
    return r in {
        "администратор парка",
        "fleet admin",
        "fleetadmin",
        "администратор",
        "administrator",
        "admin"
    }

def can_manage_fleet_groups(role: Optional[str]) -> bool:
    return is_superadmin_role(role) or is_fleetadmin_role(role)

def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    x_username = request.headers.get("X-Username")
    x_user_id = request.headers.get("X-User-Id")
    users = load_users()
    if not users:
        return {"role": "Суперадминистратор", "username": x_username or "admin", "enabled": True}
    if x_username:
        u = next((usr for usr in users if usr.get("username", "").strip().lower() == x_username.strip().lower()), None)
        if u and u.get("enabled", True):
            return u
    if x_user_id:
        u = next((usr for usr in users if usr.get("id") == x_user_id), None)
        if u and u.get("enabled", True):
            return u
    raw_role = request.headers.get("X-User-Role")
    if raw_role:
        import urllib.parse
        role_dec = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
        u = next((usr for usr in users if usr.get("role", "").strip().lower() == role_dec.lower() and usr.get("enabled", True)), None)
        if u:
            return u
        if is_superadmin_role(role_dec):
            admin_u = next((usr for usr in users if is_superadmin_role(usr.get("role")) and usr.get("enabled", True)), None)
            if admin_u:
                return admin_u
            return {"role": "Суперадминистратор", "username": x_username or "admin", "enabled": True}

    if len(users) == 1 and users[0].get("enabled", True):
        return users[0]

    return None

def get_request_user_scope(request: Request) -> Tuple[str, List[str]]:
    u = get_current_user_from_request(request)
    if not u:
        return "Суперадминистратор", []
    role = u.get("role", "Суперадминистратор")
    if is_superadmin_role(role) or u.get("scope") == "Все устройства":
        return role, []
    return role, u.get("allowedGroups", []) or []

def require_superadmin(request: Request) -> Dict[str, Any]:
    users = load_users()
    if not users:
        return {"role": "Суперадминистратор", "username": "system"}
    user = get_current_user_from_request(request)
    if user and is_superadmin_role(user.get("role")):
        return user
    raw_role = request.headers.get("X-User-Role")
    if raw_role:
        import urllib.parse
        role_dec = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
        if is_superadmin_role(role_dec):
            return {"role": "Суперадминистратор", "username": "admin"}
    raise HTTPException(
        status_code=403,
        detail="Отказ в доступе: управление учетными записями и ролями разрешено только администраторам системы."
    )

def require_superadmin_or_fleetadmin(request: Request) -> Dict[str, Any]:
    users = load_users()
    if not users:
        return {"role": "Суперадминистратор", "username": "system"}
    user = get_current_user_from_request(request)
    if user and can_manage_fleet_groups(user.get("role")):
        return user
    raw_role = request.headers.get("X-User-Role")
    if raw_role:
        import urllib.parse
        role_dec = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
        if can_manage_fleet_groups(role_dec):
            return {"role": role_dec, "username": "admin"}
    raise HTTPException(
        status_code=403,
        detail="Отказ в доступе: управление разрешено только Суперадминистратору и Администратору парка."
    )


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt

def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    if not password or not salt or not expected_hash:
        return False
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return secrets.compare_digest(key.hex(), expected_hash)

def sanitize_user(u: Dict[str, Any]) -> Dict[str, Any]:
    safe = dict(u)
    safe.pop("passwordHash", None)
    safe.pop("salt", None)
    return safe

BACKUP_USERS_FILE = os.path.join(settings.DATA_DIR, "users.backup.json")

def load_users() -> List[Dict[str, Any]]:
    # 1. Try loading from main users.json
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    # Upgrade any legacy users missing hashes or groups
                    updated = False
                    for u in data:
                        if "passwordHash" not in u:
                            h, s = hash_password("admin123")
                            u["passwordHash"] = h
                            u["salt"] = s
                            updated = True
                        if "allowedGroups" not in u:
                            u["allowedGroups"] = []
                            updated = True
                        if "telegramChatId" not in u:
                            u["telegramChatId"] = ""
                            updated = True
                    if updated:
                        save_users(data)
                    else:
                        # Auto-update backup
                        try:
                            with open(BACKUP_USERS_FILE, "w", encoding="utf-8") as bf:
                                json.dump(data, bf, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                    return data
        except Exception:
            pass

    # 2. Resilient fallback: If users.json was wiped or reset by git, restore from backup!
    if os.path.exists(BACKUP_USERS_FILE):
        try:
            with open(BACKUP_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    save_users(data)
                    return data
        except Exception:
            pass

    return []

def save_users(users: List[Dict[str, Any]]):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    if users:
        try:
            with open(BACKUP_USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

class InitialAdminSetupPayload(BaseModel):
    username: str
    displayName: str
    email: str = ""
    password: str
    telegramChatId: str = ""

class UserCreatePayload(BaseModel):
    username: str
    displayName: str
    email: str = ""
    password: str = "P@ssw0rd2026!"
    role: str = "Дежурный оператор"
    scope: str = "Все устройства"
    allowedGroups: List[str] = []
    telegramChatId: str = ""
    telegramReports: Optional[Dict[str, Any]] = None
    enabled: bool = True

class UserUpdatePayload(BaseModel):
    username: Optional[str] = None
    displayName: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    scope: Optional[str] = None
    allowedGroups: Optional[List[str]] = None
    telegramChatId: Optional[str] = None
    telegramReports: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    newPassword: Optional[str] = None


class LoginPayload(BaseModel):
    username: str
    password: str

class ChangePasswordPayload(BaseModel):
    username: str
    oldPassword: str
    newPassword: str

@router.get("/setup-status")
async def get_setup_status():
    users = load_users()
    is_configured = len(users) > 0
    return {
        "isConfigured": is_configured,
        "userCount": len(users)
    }

@router.post("/setup-initial-admin")
async def setup_initial_admin(payload: InitialAdminSetupPayload):
    users = load_users()
    if len(users) > 0:
        raise HTTPException(status_code=400, detail="Система уже инициализирована. Первичная регистрация недоступна.")
    
    clean_username = payload.username.strip().lower()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Укажите логин администратора")
    
    if not payload.password or len(payload.password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Пароль должен содержать не менее 4 символов")

    pwd_hash, salt = hash_password(payload.password.strip())
    
    new_admin = {
        "id": "USR-01",
        "username": clean_username,
        "displayName": payload.displayName.strip() or "Главный администратор",
        "email": payload.email.strip() or f"{clean_username}@bmstu.local",
        "role": "Суперадминистратор",
        "scope": "Все устройства",
        "allowedGroups": [],
        "telegramChatId": payload.telegramChatId.strip(),
        "enabled": True,
        "lastLogin": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M"),
        "passwordHash": pwd_hash,
        "salt": salt,
    }
    
    save_users([new_admin])
    
    return {
        "status": "success",
        "token": f"wm_sess_{secrets.token_hex(24)}",
        "user": sanitize_user(new_admin)
    }

@router.get("")
async def list_users(request: Request):
    require_superadmin_or_fleetadmin(request)
    users = load_users()
    return [sanitize_user(u) for u in users]

@router.post("")
async def create_user(payload: UserCreatePayload, request: Request):
    require_superadmin_or_fleetadmin(request)
    users = load_users()

    
    # Check if username already exists
    clean_username = payload.username.strip().lower()
    if any(u.get("username", "").lower() == clean_username for u in users):
        raise HTTPException(status_code=400, detail=f"Пользователь с логином '{clean_username}' уже существует")

    pwd = payload.password.strip() if payload.password else "P@ssw0rd2026!"
    pwd_hash, salt = hash_password(pwd)
    
    new_id_num = 1
    existing_ids = [int(u["id"].replace("USR-", "")) for u in users if u.get("id", "").startswith("USR-") and u["id"].replace("USR-", "").isdigit()]
    if existing_ids:
        new_id_num = max(existing_ids) + 1

    new_user = {
        "id": f"USR-{new_id_num:02d}",
        "username": clean_username,
        "displayName": payload.displayName.strip(),
        "email": payload.email.strip() or f"{clean_username}@bmstu.local",
        "role": payload.role,
        "scope": payload.scope,
        "allowedGroups": payload.allowedGroups or [],
        "telegramChatId": payload.telegramChatId.strip(),
        "telegramReports": payload.telegramReports or {
            "enabled": False,
            "morningReport": {"enabled": True, "time": "08:00"},
            "eveningReport": {"enabled": True, "time": "20:00"},
            "days": [0, 1, 2, 3, 4]
        },
        "enabled": payload.enabled,
        "lastLogin": "Никогда",
        "passwordHash": pwd_hash,
        "salt": salt,
    }
    users.insert(0, new_user)
    save_users(users)
    return sanitize_user(new_user)

@router.put("/{user_id}")
async def update_user(user_id: str, payload: UserUpdatePayload, request: Request):
    require_superadmin_or_fleetadmin(request)
    users = load_users()
    for u in users:
        if u["id"] == user_id or u.get("username") == user_id:
            # Prevent demoting or disabling the only Superadmin
            if u.get("role") == "Суперадминистратор":
                if (payload.role is not None and payload.role != "Суперадминистратор") or (payload.enabled is False):
                    other_superadmins = [other for other in users if other.get("role") == "Суперадминистратор" and other["id"] != u["id"] and other.get("enabled", True)]
                    if not other_superadmins:
                        raise HTTPException(status_code=400, detail="Нельзя заблокировать или понизить роль единственного активного Суперадминистратора")

            if payload.username is not None:
                clean_username = payload.username.strip().lower()
                # Ensure no other user has this username
                if any(other.get("username", "").lower() == clean_username and other["id"] != u["id"] for other in users):
                    raise HTTPException(status_code=400, detail=f"Логин '{clean_username}' уже занят другим пользователем")
                u["username"] = clean_username
            if payload.displayName is not None:
                u["displayName"] = payload.displayName.strip()
            if payload.email is not None:
                u["email"] = payload.email.strip()
            if payload.role is not None:
                u["role"] = payload.role
            if payload.scope is not None:
                u["scope"] = payload.scope
            if payload.allowedGroups is not None:
                u["allowedGroups"] = payload.allowedGroups
            if payload.telegramChatId is not None:
                u["telegramChatId"] = payload.telegramChatId.strip()
            if payload.telegramReports is not None:
                u["telegramReports"] = payload.telegramReports
            if payload.enabled is not None:
                u["enabled"] = payload.enabled
            if payload.newPassword and payload.newPassword.strip():
                h, s = hash_password(payload.newPassword.strip())
                u["passwordHash"] = h
                u["salt"] = s
            save_users(users)
            return sanitize_user(u)
    raise HTTPException(status_code=404, detail="User not found")


@router.delete("/{user_id}")
async def delete_user(user_id: str, request: Request):
    require_superadmin(request)
    users = load_users()
    target = next((u for u in users if u["id"] == user_id or u.get("username") == user_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Do not allow deleting the last Superadmin
    if target.get("role") == "Суперадминистратор":
        superadmins = [u for u in users if u.get("role") == "Суперадминистратор" and u["id"] != target["id"]]
        if not superadmins:
            raise HTTPException(status_code=400, detail="Нельзя удалить единственного Суперадминистратора системы")
            
    users = [u for u in users if u["id"] != target["id"]]
    save_users(users)
    return {"status": "deleted", "id": target["id"], "username": target.get("username")}

@router.post("/login")
async def login(payload: LoginPayload):
    users = load_users()
    clean_username = payload.username.strip().lower()
    user = next((u for u in users if u.get("username", "").lower() == clean_username), None)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    if not user.get("enabled", True):
        raise HTTPException(status_code=403, detail="Учетная запись заблокирована администратором")

    if not verify_password(payload.password, user.get("salt", ""), user.get("passwordHash", "")):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    # Update lastLogin timestamp
    user["lastLogin"] = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    save_users(users)

    # Check if there is an existing active session for this user
    old_session = user_active_sessions.get(clean_username)
    old_token = old_session.get("token") if old_session else None
    session_token = register_user_session(clean_username)

    # Notify WebSocket clients so any previously open sessions on other computers are kicked out immediately
    try:
        from backend.app.ws.manager import ws_manager
        await ws_manager.broadcast_event("session.invalidated", {
            "username": clean_username,
            "previousToken": old_token,
            "newToken": session_token,
            "reason": "Вход выполнен с другого устройства под этой же учетной записью"
        })
    except Exception:
        pass

    return {
        "status": "success",
        "token": session_token,
        "user": sanitize_user(user)
    }


@router.post("/change-password")
async def change_password(payload: ChangePasswordPayload):
    users = load_users()
    clean_username = payload.username.strip().lower() if payload.username else ""
    
    user = None
    if clean_username:
        user = next((u for u in users if u.get("username", "").lower() == clean_username or u.get("id", "").lower() == clean_username or u.get("email", "").lower() == clean_username or u.get("displayName", "").lower() == clean_username), None)
    
    # If not matched by exact name, fallback to first user if only 1 exists or first admin
    if not user:
        if len(users) == 1:
            user = users[0]
        elif clean_username in ["admin", "superadmin", "administrator", "root", ""]:
            user = next((u for u in users if u.get("role") in ["Суперадминистратор", "Главный администратор", "Администратор"]), users[0] if users else None)
        elif users:
            user = users[0]

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден в системе")
    
    if not verify_password(payload.oldPassword, user.get("salt", ""), user.get("passwordHash", "")):
        raise HTTPException(status_code=400, detail="Текущий пароль указан неверно")

    if not payload.newPassword or len(payload.newPassword.strip()) < 4:
        raise HTTPException(status_code=400, detail="Новый пароль должен содержать минимум 4 символа")

    h, s = hash_password(payload.newPassword.strip())
    user["passwordHash"] = h
    user["salt"] = s
    save_users(users)
    return {"status": "success", "message": f"Пароль учетной записи {user.get('username', 'admin')} успешно обновлен"}


@router.get("/validate-session")
async def validate_session_endpoint(request: Request):
    """
    Check whether the caller's session token is still the single active session.
    If another session logged in, this returns valid=False so client logs out immediately.
    """
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    x_username = request.headers.get("X-Username", "").strip().lower()

    if not x_username or not token:
        # If no active user is set yet, session is neutral
        return {"valid": True, "active": False}

    active_sess = user_active_sessions.get(x_username)
    if not active_sess:
        # If no session registered yet in memory (e.g. server restart), register current token
        register_user_session(x_username, token)
        return {"valid": True, "active": True}

    if active_sess.get("token") != token:
        return {
            "valid": False,
            "active": False,
            "reason": "Вход выполнен с другого устройства или сессия завершена"
        }

    return {"valid": True, "active": True}


@router.post("/logout")
async def logout_endpoint(request: Request):
    """
    Revoke active session for user.
    """
    x_username = request.headers.get("X-Username", "").strip().lower()
    if x_username:
        revoke_user_sessions(x_username)
    return {"status": "success"}

