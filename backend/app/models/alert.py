from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.db.session import Base

class AlertModel(Base):
    __tablename__ = "alerts"

    id = Column(String(32), primary_key=True) # e.g. "ALT-101"
    device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=True, index=True)
    alert_type = Column(String(50), nullable=False) # HARDWARE_MISMATCH, POWER_FAILED, etc.
    category = Column(String(30), default="General") # Hardware, Power, Security, Resource
    severity = Column(String(20), default="Warning") # Critical, Warning, Info
    state = Column(String(20), default="Open") # Open, Acknowledged, Resolved
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(String(500), nullable=False)

class AlertPolicyModel(Base):
    __tablename__ = "alert_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, unique=True)
    mode = Column(String(20), default="Full") # Full, Hardware Only, Custom, Muted
    
    events_config = Column(JSON, default=lambda: {
        "hardwareChanges": True,
        "powerStateFailed": True,
        "morningWakeFailed": True,
        "eveningShutdownFailed": True,
        "rdpSessionTimeout": True,
        "agentDisconnect": True,
        "highCpuUsage": True,
        "highRamUsage": True,
        "highDiskUsage": True,
    })
    
    thresholds = Column(JSON, default=lambda: {
        "cpuPercent": 90,
        "ramPercent": 85,
        "diskPercent": 90,
        "rdpIdleMinutes": 30,
    })
    
    notify_channels = Column(JSON, default=lambda: {
        "webUi": True,
        "telegram": True,
        "email": False,
    })

    device = relationship("Device", back_populates="alert_policy")

class RdpSessionModel(Base):
    __tablename__ = "rdp_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(100), nullable=False)
    state = Column(String(20), default="Active") # Active, Disconnected, Idle
    idle_time = Column(String(20), default="00:00")
    logon_time = Column(DateTime, default=datetime.utcnow)
    disconnected_since = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="sessions")

# Backward compatibility aliases
Alert = AlertModel
AlertPolicy = AlertPolicyModel
