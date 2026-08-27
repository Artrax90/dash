export type UserRole = 'Super Admin' | 'Administrator' | 'Operator' | 'Viewer' | 'Custom';
export type PowerStatus = 'On' | 'Off' | 'Booting' | 'Shutting down' | 'Unknown' | 'Error';
export type AgentStatus = 'Connected' | 'Disconnected' | 'Outdated';
export type RdpStatus = 'Running' | 'Stopped' | 'Error';
export type HealthStatus = 'Healthy' | 'Warning' | 'Critical';
export type OsType = 'Windows' | 'Linux';

export interface RamSlot {
  slot: string;
  sizeGb: number;
  type: string;
  frequencyMhz: number;
  manufacturer: string;
  partNumber: string;
  serialNumber?: string;
}

export interface StorageDrive {
  id: string;
  model: string;
  serialNumber: string;
  type: 'NVMe SSD' | 'SATA SSD' | 'HDD' | string;
  busType?: string;
  capacityGb: number;
  healthPercent: number;
  temperatureC: number;
}

export interface GpuItem {
  model: string;
  vramGb: number;
  driverVersion: string;
  temperatureC?: number;
  resolution?: string;
}

export interface NetworkAdapter {
  name: string;
  mac: string;
  ip: string;
  speedMbps?: number;
  speed?: string;
  status?: string;
}

export interface HardwareSpec {
  motherboard: {
    manufacturer: string;
    model: string;
    serialNumber: string;
    version?: string;
  };
  bios: {
    vendor: string;
    version: string;
    releaseDate: string;
  };
  cpu: {
    model: string;
    cores: number;
    threads: number;
    baseFrequencyGhz: number;
    socket?: string;
  };
  ram: {
    totalGb: number;
    slots: RamSlot[];
  };
  storage: StorageDrive[];
  gpus: GpuItem[];
  network: NetworkAdapter[];
  sound?: { name: string; manufacturer: string; }[];
}

export interface HardwareBaseline {
  id: string;
  deviceId: string;
  createdAt: string;
  updatedAt: string;
  approvedBy: string;
  spec: HardwareSpec;
}

export interface HardwareChange {
  id: string;
  deviceId: string;
  timestamp: string;
  component: 'RAM' | 'Storage' | 'GPU' | 'Motherboard' | 'CPU' | 'Network';
  changeType: 'REMOVED' | 'ADDED' | 'MODIFIED';
  severity: 'Critical' | 'Warning' | 'Info';
  previousValue: string;
  currentValue: string;
  acknowledged: boolean;
  baselineDiffStatus: 'MISMATCH' | 'RESOLVED' | 'ACCEPTED_AS_BASELINE';
}

export type AlertPolicyMode = 'Full' | 'Hardware Only' | 'Custom' | 'Muted';

export interface AlertPolicy {
  deviceId: string;
  mode: AlertPolicyMode;
  events: {
    hardwareChanges: boolean;
    powerStateFailed: boolean;
    morningWakeFailed: boolean;
    eveningShutdownFailed: boolean;
    rdpSessionTimeout: boolean;
    agentDisconnect: boolean;
    highCpuUsage: boolean;
    highRamUsage: boolean;
    highDiskUsage: boolean;
  };
  thresholds: {
    cpuPercent: number;
    ramPercent: number;
    diskPercent: number;
    rdpIdleMinutes: number;
  };
  notifyChannels: {
    webUi: boolean;
    telegram: boolean;
    email: boolean;
  };
}

export interface ExecutionProfile {
  id: string;
  deviceId: string;
  defaultContext: 'SYSTEM' | 'LOCAL_ADMIN' | 'LOCAL_USER';
  adminUsername?: string;
  lastTested?: string;
  testStatus?: 'Success' | 'Failed' | 'Untested';
}

export interface Device {
  id: string;
  name: string;
  hostname: string;
  group: string;
  ip: string;
  mac: string;
  osType: OsType;
  currentUser: string;
  powerStatus: PowerStatus;
  agentStatus: AgentStatus;
  rdpStatus: RdpStatus;
  healthStatus: HealthStatus;
  cpu: number;
  ram: number;
  disk: number;
  uptime: string;
  uptimeSeconds?: number;
  bootTime?: string;
  bootTimeIso?: string;
  lastSeen: string;
  lastSeenIso?: string;
  osVersion: string;
  agentVersion: string;
  latestAgentVersion?: string;
  isOutdated?: boolean;
  updateStatus?: 'idle' | 'updating' | 'success' | 'failed' | string;
  maintenance: boolean;
  tags: string[];
  groups?: string[];
  assetTag?: string;
  notes?: string;
  heartbeatInterval?: number | null;
  hardware?: HardwareSpec;
  baseline?: HardwareBaseline;
  hardwareChangesCount?: number;
  alertPolicy?: AlertPolicy;
  executionProfile?: ExecutionProfile;
}

export interface RdpSession {
  id: number;
  deviceId: string;
  username: string;
  state: 'Active' | 'Disconnected' | 'Idle';
  idleTime: string;
  logonTime: string;
  disconnectedSince?: string;
}

export interface Alert {
  id: string;
  type: string;
  device: string;
  severity: 'Critical' | 'Warning' | 'Info';
  state: 'Open' | 'Acknowledged' | 'Resolved';
  time: string;
  description: string;
  category?: 'Hardware' | 'Power' | 'Security' | 'Resource';
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  target: string;
  targetType: string;
  result: 'Success' | 'Failed' | 'Pending';
  ip: string;
  details: string;
}

export interface ScheduleStep {
  id?: string;
  action: 'WAKE' | 'SHUTDOWN' | 'REBOOT' | 'RDP_CLEANUP';
  time: string; // e.g. "07:45", "21:45", "22:00"
  enabled: boolean;
  gracePeriodMinutes?: number;
  warningMessage?: string;
  forceShutdown?: boolean;
}

export interface Schedule {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  timezone: string;
  days: string;
  daysList?: string[];
  time: string;
  action: 'WAKE' | 'SHUTDOWN' | 'REBOOT' | 'RDP_CLEANUP' | 'LIFECYCLE';
  target: string;
  type?: 'Lifecycle' | 'Morning Wake' | 'Evening Shutdown' | 'RDP Cleanup' | 'Reboot' | 'Custom';
  steps?: ScheduleStep[];
  gracePeriodMinutes?: number;
  warningMessage?: string;
  forceShutdown?: boolean;
  lastRun?: string | null;
  lastRunResult?: 'Success' | 'Failed' | 'Warning' | null;
  lastRunSummary?: string;
  nextRunFormatted?: string;
  nextRunIso?: string;
  secondsUntilNext?: number;
  nextStepAction?: string;
  nextStepTime?: string;
  targetDeviceCount?: number;
  createdBy?: string;
  createdAt?: string;
}

export interface ScheduleExecutionLog {
  id: string;
  scheduleId: string;
  scheduleName: string;
  action: 'WAKE' | 'SHUTDOWN' | 'REBOOT' | 'RDP_CLEANUP';
  target: string;
  timestamp: string;
  status: 'Success' | 'Failed' | 'Partial';
  devicesTargeted: number;
  devicesSuccess: number;
  devicesFailed: number;
  triggeredBy: string;
  details: string;
}

export interface AgentEnrollmentToken {
  id: string;
  token: string;
  targetGroup: string;
  serverUrl: string;
  createdAt: string;
  expiresAt: string;
  isReusable: boolean;
  usedCount: number;
  maxUses?: number;
  createdBy: string;
}

export interface AgentBuild {
  os: 'Windows' | 'Linux';
  architecture: 'x64' | 'ARM64';
  packageType: '.exe' | '.deb' | '.rpm' | '.tar.gz';
  version: string;
  sizeMb: number;
  sha256: string;
  downloadUrl: string;
}

export interface AgentVersionInfo {
  currentVersion: string;
  releaseDate: string;
  minSupportedVersion: string;
  changelog: string;
  totalAgents: number;
  upToDateCount: number;
  outdatedCount: number;
  updatingCount: number;
}

export interface AgentUpdateLog {
  id: string;
  deviceId: string;
  deviceName?: string;
  previousVersion: string;
  targetVersion: string;
  newVersion?: string;
  status: 'UPDATING' | 'SUCCESS' | 'FAILED' | string;
  timestamp: string;
  time?: string;
  details?: string;
  error?: string;
  initiator?: string;
}

export interface CustomPermission {
  id: string;
  name: string;
  category: 'Power' | 'Hardware' | 'Sessions' | 'Automation' | 'Administration';
  description: string;
}

export interface CustomRole {
  id: string;
  name: string;
  description: string;
  isBuiltIn: boolean;
  permissions: string[];
  scopeType: 'ALL' | 'GROUPS' | 'DEVICES';
  scopeValues: string[];
  userCount: number;
}

export interface ManagedUser {
  id: string;
  username: string;
  displayName: string;
  email: string;
  role: UserRole;
  customRoleId?: string;
  scope: string;
  allowedGroups?: string[];
  enabled: boolean;
  lastLogin: string;
  telegramChatId?: string;
}

export interface BulkOperationRequest {
  action: 'WAKE' | 'SHUTDOWN' | 'REBOOT' | 'LOGOFF_SESSIONS' | 'UPDATE_AGENT' | 'SET_GROUP' | 'SET_ALERT_POLICY';
  deviceIds: string[];
  parameters?: Record<string, any>;
}

export interface BulkOperationProgress {
  id: string;
  action: string;
  total: number;
  completed: number;
  succeeded: number;
  failed: number;
  status: 'Running' | 'Completed' | 'Failed';
  startedAt: string;
  items: {
    deviceId: string;
    deviceName: string;
    status: 'Pending' | 'Success' | 'Failed';
    error?: string;
  }[];
}

export interface TelegramBotConfig {
  enabled: boolean;
  botUsername: string;
  status: 'Connected' | 'Disconnected' | 'Error';
  subscribersCount: number;
  eventsConfig: {
    criticalAlerts: boolean;
    morningWakeSummary: boolean;
    eveningShutdownSummary: boolean;
    hardwareChanges: boolean;
  };
}

export interface DashboardStats {
  total: number;
  online: number;
  offline: number;
  problems: number;
  activeSessions: number;
  disconnectedSessions: number;
  hardwareAlertsCount: number;
}
