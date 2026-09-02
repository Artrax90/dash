import json
import os
import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from backend.app.core.config import settings

router = APIRouter(prefix="/users", tags=["users"])

USERS_FILE = os.path.join(settings.DATA_DIR, "users.json")

def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    x_username = request.headers.get("X-Username")
    x_user_id = request.headers.get("X-User-Id")
    users = load_users()
    if not users:
        return None
    if x_username:
        u = next((usr for usr in users if usr.get("username", "").lower() == x_username.strip().lower()), None)
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
        u = next((usr for usr in users if usr.get("role") == role_dec and usr.get("enabled", True)), None)
        if u:
            return u
    return None

def require_superadmin(request: Request) -> Dict[str, Any]:
    users = load_users()
    if not users:
        return {"role": "Суперадминистратор", "username": "system"}
    user = get_current_user_from_request(request)
    if not user or user.get("role") not in ["Суперадминистратор", "SuperAdmin"]:
        raise HTTPException(
            status_code=403,
            detail="Отказ в доступе: управление учетными записями разрешено только Суперадминистратору системы."
        )
    return user

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

def load_users() -> List[Dict[str, Any]]:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
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
                    return data
        except Exception:
            pass
    return []

def save_users(users: List[Dict[str, Any]]):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

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
    enabled: bool = True

class UserUpdatePayload(BaseModel):
    username: Optional[str] = None
    displayName: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    scope: Optional[str] = None
    allowedGroups: Optional[List[str]] = None
    telegramChatId: Optional[str] = None
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
    require_superadmin(request)
    users = load_users()
    return [sanitize_user(u) for u in users]

@router.post("")
async def create_user(payload: UserCreatePayload, request: Request):
    require_superadmin(request)
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
    require_superadmin(request)
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

    session_token = f"wm_sess_{secrets.token_hex(24)}"
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
