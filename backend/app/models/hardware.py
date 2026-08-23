from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.db.session import Base

class HardwareSpecModel(Base):
    __tablename__ = "hardware_specs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # JSON payloads representing Motherboard, BIOS, CPU, RAM Slots, Storage, GPU, Network
    raw_spec = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    device = relationship("Device", back_populates="hardware_spec")

class HardwareBaselineModel(Base):
    __tablename__ = "hardware_baselines"

    id = Column(String(32), primary_key=True) # e.g. "BL-001"
    device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, unique=True)
    approved_by = Column(String(100), default="System")
    spec = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    device = relationship("Device", back_populates="baseline")

class HardwareChangeModel(Base):
    __tablename__ = "hardware_changes"

    id = Column(String(32), primary_key=True) # e.g. "HWC-001"
    device_id = Column(String(32), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    component = Column(String(50), nullable=False) # RAM, Storage, GPU, CPU, etc.
    change_type = Column(String(20), nullable=False) # REMOVED, ADDED, MODIFIED
    severity = Column(String(20), default="Warning") # Critical, Warning, Info
    previous_value = Column(String(255), nullable=False)
    current_value = Column(String(255), nullable=False)
    acknowledged = Column(Boolean, default=False)
    diff_status = Column(String(30), default="MISMATCH") # MISMATCH, ACCEPTED_AS_BASELINE, RESOLVED

    device = relationship("Device", back_populates="changes")
