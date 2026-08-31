from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime

class RamSlotSchema(BaseModel):
    slot: str
    sizeGb: int
    type: str
    frequencyMhz: int
    manufacturer: str
    partNumber: str

class StorageDriveSchema(BaseModel):
    id: str
    model: str
    serialNumber: str
    type: str
    capacityGb: int
    healthPercent: int
    temperatureC: int

class GpuItemSchema(BaseModel):
    model: str
    vramGb: int
    driverVersion: str

class NetworkAdapterSchema(BaseModel):
    name: str
    mac: str
    ip: str
    speedMbps: int

class MotherboardSchema(BaseModel):
    manufacturer: str
    model: str
    serialNumber: str

class BiosSchema(BaseModel):
    vendor: str
    version: str
    releaseDate: str

class CpuSchema(BaseModel):
    model: str
    cores: int
    threads: int
    baseFrequencyGhz: float

class RamSpecSchema(BaseModel):
    totalGb: int
    slots: List[RamSlotSchema]

class HardwareSpecSchema(BaseModel):
    motherboard: MotherboardSchema
    bios: BiosSchema
    cpu: CpuSchema
    ram: RamSpecSchema
    storage: List[StorageDriveSchema]
    gpus: List[GpuItemSchema]
    network: List[NetworkAdapterSchema]

class HardwareChangeSchema(BaseModel):
    id: str
    deviceId: str
    timestamp: str
    component: str
    changeType: str
    severity: str
    previousValue: str
    currentValue: str
    acknowledged: bool
    baselineDiffStatus: str

class AlertPolicyEventsSchema(BaseModel):
    hardwareChanges: bool = True
    powerStateFailed: bool = True
    morningWakeFailed: bool = True
    eveningShutdownFailed: bool = True
    rdpSessionTimeout: bool = True
    agentDisconnect: bool = True
    highCpuUsage: bool = True
    highRamUsage: bool = True
    highDiskUsage: bool = True

class AlertPolicyThresholdsSchema(BaseModel):
    cpuPercent: int = 90
    ramPercent: int = 85
    diskPercent: int = 90
    rdpIdleMinutes: int = 30

class AlertPolicyChannelsSchema(BaseModel):
    webUi: bool = True
    telegram: bool = True
    email: bool = False

class AlertPolicySchema(BaseModel):
    deviceId: str
    mode: str = "Full"
    events: AlertPolicyEventsSchema = Field(default_factory=AlertPolicyEventsSchema)
    thresholds: AlertPolicyThresholdsSchema = Field(default_factory=AlertPolicyThresholdsSchema)
    notifyChannels: AlertPolicyChannelsSchema = Field(default_factory=AlertPolicyChannelsSchema)

class DeviceBase(BaseModel):
    name: str
    hostname: str
    group: str = "Default"
    ip: str
    mac: str
    osType: str = "Windows"
    tags: List[str] = Field(default_factory=list)

class DeviceCreate(DeviceBase):
    pass

class DeviceOut(DeviceBase):
    id: str
    currentUser: str = "—"
    powerStatus: str = "Off"
    agentStatus: str = "Disconnected"
    rdpStatus: str = "Stopped"
    healthStatus: str = "Healthy"
    cpu: int = 0
    ram: int = 0
    disk: int = 0
    uptime: str = "—"
    uptimeSeconds: Optional[int] = 0
    bootTime: Optional[str] = None
    bootTimeIso: Optional[str] = None
    lastSeen: str
    lastSeenIso: Optional[str] = None
    osVersion: str
    agentVersion: str
    latestAgentVersion: Optional[str] = "2.4.5"
    isOutdated: Optional[bool] = False
    updateStatus: Optional[str] = "idle"
    maintenance: bool = False
    hardware: Optional[HardwareSpecSchema] = None
    hardwareChangesCount: int = 0
    alertPolicy: Optional[AlertPolicySchema] = None

    class Config:
        from_attributes = True

class BulkOperationRequestSchema(BaseModel):
    action: str # WAKE, SHUTDOWN, FORCE_SHUTDOWN, REBOOT, LOGOFF_SESSIONS, UPDATE_AGENT
    deviceIds: List[str]
    parameters: Optional[Dict[str, Any]] = None
    user: Optional[str] = None
    initiator: Optional[str] = None
