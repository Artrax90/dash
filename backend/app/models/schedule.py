from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Boolean
from datetime import datetime
from backend.app.db.session import Base

class ScheduleModel(Base):
    __tablename__ = "schedules"

    id = Column(String(32), primary_key=True) # e.g. "SCH-01"
    name = Column(String(100), nullable=False)
    schedule_type = Column(String(50), default="Custom") # Morning Wake, Evening Shutdown, Custom
    description = Column(String(255), default="")
    enabled = Column(Boolean, default=True)
    cron_expr = Column(String(50), nullable=True) # e.g. "0 45 7 * * 1-5"
    timezone = Column(String(50), default="Europe/Moscow")
    days = Column(String(50), default="Пн-Пт")
    time_str = Column(String(20), default="07:45")
    action = Column(String(50), nullable=False) # WAKE, SHUTDOWN, REBOOT, RDP_CLEANUP
    target = Column(String(100), default="All") # Group name or "All"

class OperationModel(Base):
    __tablename__ = "operations"

    id = Column(String(32), primary_key=True) # e.g. "OP-2026-001"
    action = Column(String(50), nullable=False) # WAKE, SHUTDOWN, FORCE_SHUTDOWN, REBOOT, LOGOFF
    initiated_by = Column(String(100), default="SYSTEM")
    target_type = Column(String(20), default="Device") # Device, Group, Fleet
    target_id = Column(String(100), nullable=False)
    status = Column(String(20), default="Pending") # Pending, In Progress, Success, Failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    error_message = Column(String(500), nullable=True)

class AgentEnrollmentTokenModel(Base):
    __tablename__ = "agent_enrollment_tokens"

    id = Column(String(32), primary_key=True) # e.g. "TOK-01"
    token = Column(String(100), nullable=False, unique=True, index=True)
    target_group = Column(String(100), default="Default")
    server_url = Column(String(255), default="https://localhost:8443")
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_reusable = Column(Boolean, default=False)
    used_count = Column(Integer, default=0)
    max_uses = Column(Integer, default=1)
    created_by = Column(String(100), default="Administrator")

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    email = Column(String(100), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(String(50), default="Operator") # Super Admin, Administrator, Operator, Viewer, Custom
    scope_type = Column(String(20), default="ALL") # ALL, GROUPS, DEVICES
    scope_values = Column(JSON, default=list)
    enabled = Column(Boolean, default=True)
    telegram_chat_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

class CustomRoleModel(Base):
    __tablename__ = "custom_roles"

    id = Column(String(32), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), default="")
    is_builtin = Column(Boolean, default=False)
    permissions = Column(JSON, default=list) # e.g. ["power.all", "rdp.all"]
    scope_type = Column(String(20), default="ALL")
    scope_values = Column(JSON, default=list)

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String(32), primary_key=True) # e.g. "AUD-001"
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    target = Column(String(100), nullable=False)
    target_type = Column(String(50), default="Device")
    result = Column(String(20), default="Success") # Success, Failed, Pending
    ip_address = Column(String(45), default="127.0.0.1")
    details = Column(String(1000), default="")

class TelegramSubscriberModel(Base):
    __tablename__ = "telegram_subscribers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(50), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=True)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    subscribed_events = Column(JSON, default=lambda: ["CRITICAL_ALERTS", "HARDWARE_CHANGES", "MORNING_WAKE"])
    created_at = Column(DateTime, default=datetime.utcnow)
