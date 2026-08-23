import enum
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.db.session import Base

class PowerStatus(str, enum.Enum):
    ON = "On"
    OFF = "Off"
    BOOTING = "Booting"
    SHUTTING_DOWN = "Shutting down"
    UNKNOWN = "Unknown"
    ERROR = "Error"

class AgentStatus(str, enum.Enum):
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    OUTDATED = "Outdated"

class RdpStatus(str, enum.Enum):
    RUNNING = "Running"
    STOPPED = "Stopped"
    ERROR = "Error"

class HealthStatus(str, enum.Enum):
    HEALTHY = "Healthy"
    WARNING = "Warning"
    CRITICAL = "Critical"

class Device(Base):
    __tablename__ = "devices"

    id = Column(String(32), primary_key=True, index=True) # e.g. "PC-001"
    name = Column(String(100), nullable=False)
    hostname = Column(String(100), nullable=False, unique=True, index=True)
    group_name = Column(String(100), nullable=False, index=True, default="Default")
    ip_address = Column(String(45), nullable=False, index=True)
    mac_address = Column(String(32), nullable=False, index=True)
    broadcast_ip = Column(String(45), nullable=True, default="255.255.255.255")
    os_type = Column(String(20), default="Windows") # Windows | Linux
    os_version = Column(String(100), default="Windows 11 Pro")
    agent_version = Column(String(20), default="1.4.2")
    current_user = Column(String(100), default="—")
    
    power_status = Column(Enum(PowerStatus), default=PowerStatus.OFF)
    agent_status = Column(Enum(AgentStatus), default=AgentStatus.DISCONNECTED)
    rdp_status = Column(Enum(RdpStatus), default=RdpStatus.STOPPED)
    health_status = Column(Enum(HealthStatus), default=HealthStatus.HEALTHY)
    
    cpu_usage = Column(Integer, default=0)
    ram_usage = Column(Integer, default=0)
    disk_usage = Column(Integer, default=0)
    uptime = Column(String(50), default="—")
    uptime_seconds = Column(Integer, default=0)
    boot_time = Column(DateTime, nullable=True, default=None)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    maintenance_mode = Column(Boolean, default=False)
    tags = Column(JSON, default=list) # e.g. ["Office", "WOL-Morning"]
    asset_tag = Column(String(128), nullable=True, default="")
    notes = Column(String(500), nullable=True, default="")
    heartbeat_interval = Column(Integer, nullable=True, default=None) # Custom seconds override (None = use group / global default)
    
    # Relationships
    hardware_spec = relationship("HardwareSpecModel", back_populates="device", uselist=False, cascade="all, delete-orphan")
    baseline = relationship("HardwareBaselineModel", back_populates="device", uselist=False, cascade="all, delete-orphan")
    changes = relationship("HardwareChangeModel", back_populates="device", cascade="all, delete-orphan")
    alert_policy = relationship("AlertPolicyModel", back_populates="device", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("RdpSessionModel", back_populates="device", cascade="all, delete-orphan")
