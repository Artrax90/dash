import type {
  Alert,
  AgentBuild,
  AgentEnrollmentToken,
  AuditEntry,
  CustomRole,
  DashboardStats,
  Device,
  HardwareChange,
  ManagedUser,
  RdpSession,
  Schedule,
  TelegramBotConfig,
} from '@/types';

// Empty live datasets - devices will appear dynamically when agents enroll
export const devices: Device[] = [];
export const hardwareChanges: HardwareChange[] = [];
export const sessions: RdpSession[] = [];
export const alerts: Alert[] = [];
export const auditEntries: AuditEntry[] = [];
export const agentTokens: AgentEnrollmentToken[] = [];

export const managedUsers: ManagedUser[] = [
  {
    id: 'USR-01',
    username: 'admin',
    displayName: 'Administrator',
    email: 'admin@northstar.local',
    role: 'Super Admin',
    scope: 'Все устройства',
    enabled: true,
    lastLogin: 'Только что',
  }
];

export const customRoles: CustomRole[] = [
  {
    id: 'ROLE-01',
    name: 'Super Admin',
    description: 'Полный доступ ко всей функциональности системы',
    isBuiltIn: true,
    permissions: [
      'devices.view', 'devices.create', 'devices.edit', 'devices.delete',
      'devices.wake', 'devices.reboot', 'devices.shutdown', 'devices.force_shutdown',
      'sessions.view', 'sessions.logoff', 'monitoring.view', 'alerts.view',
      'audit.view', 'settings.edit', 'hardware.baseline_edit', 'agents.tokens_manage'
    ],
    scopeType: 'ALL',
    scopeValues: [],
    userCount: 1,
  },
  {
    id: 'ROLE-02',
    name: 'Administrator',
    description: 'Управление парком ПК, расписаниями и сессиями',
    isBuiltIn: true,
    permissions: [
      'devices.view', 'devices.edit', 'devices.wake', 'devices.reboot',
      'devices.shutdown', 'sessions.view', 'sessions.logoff', 'monitoring.view',
      'alerts.view', 'hardware.baseline_edit'
    ],
    scopeType: 'ALL',
    scopeValues: [],
    userCount: 0,
  },
  {
    id: 'ROLE-03',
    name: 'Operator',
    description: 'Оперативный мониторинг и управление питанием',
    isBuiltIn: true,
    permissions: ['devices.view', 'devices.wake', 'devices.reboot', 'sessions.view', 'monitoring.view', 'alerts.view'],
    scopeType: 'GROUPS',
    scopeValues: ['Office'],
    userCount: 0,
  },
  {
    id: 'ROLE-04',
    name: 'Viewer',
    description: 'Только просмотр статусов и телеметрии',
    isBuiltIn: true,
    permissions: ['devices.view', 'monitoring.view', 'alerts.view'],
    scopeType: 'ALL',
    scopeValues: [],
    userCount: 0,
  }
];

export const schedules: Schedule[] = [
  {
    id: 'SCH-01',
    name: 'Утреннее включение (WoL)',
    description: 'Включение рабочих станций перед началом смены',
    enabled: true,
    timezone: 'Europe/Moscow',
    days: 'ПН, ВТ, СР, ЧТ, ПТ',
    time: '07:50',
    action: 'WAKE',
    target: 'Все группы',
    type: 'Morning Wake',
  },
  {
    id: 'SCH-02',
    name: 'Вечернее завершение работы',
    description: 'Автоматическое выключение станций в конце рабочего дня',
    enabled: true,
    timezone: 'Europe/Moscow',
    days: 'ПН, ВТ, СР, ЧТ, ПТ',
    time: '22:00',
    action: 'SHUTDOWN',
    target: 'Все группы',
    type: 'Evening Shutdown',
  }
];

export const agentBuilds: AgentBuild[] = [
  {
    os: 'Windows 10 / 11 / Server',
    architecture: 'x64 / ARM64',
    packageType: '1-Click Installer (.bat)',
    version: '1.4.2',
    sizeMb: 0.1,
    sha256: '9b83b33ad56e8729f21394c8bfa4910248c894819d44c80381029c8e9f8e4729',
    downloadUrl: '/install.bat',
  },
  {
    os: 'Linux (Ubuntu / Debian / RHEL)',
    architecture: 'x64 / aarch64',
    packageType: 'Shell Script (.sh)',
    version: '1.4.2',
    sizeMb: 0.1,
    sha256: 'e83910c283948572019483829104857201928475839201948572019485720194',
    downloadUrl: '/install.sh',
  },
  {
    os: 'Windows PowerShell',
    architecture: 'Любая',
    packageType: 'PowerShell (.ps1)',
    version: '1.4.2',
    sizeMb: 0.1,
    sha256: 'a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0',
    downloadUrl: '/install.ps1',
  },
];

export const telegramConfig: TelegramBotConfig = {
  enabled: false,
  botUsername: '',
  status: 'Не настроен',
  subscribersCount: 0,
  eventsConfig: {
    criticalAlerts: true,
    morningWakeSummary: true,
    eveningShutdownSummary: true,
    hardwareChanges: true,
  },
};

export const monitoringSeries = [
  { label: '00:00', cpu: 0, ram: 0, network: 0 },
  { label: '02:00', cpu: 0, ram: 0, network: 0 },
  { label: '04:00', cpu: 0, ram: 0, network: 0 },
  { label: '06:00', cpu: 0, ram: 0, network: 0 },
  { label: '08:00', cpu: 0, ram: 0, network: 0 },
  { label: '10:00', cpu: 0, ram: 0, network: 0 },
  { label: '12:00', cpu: 0, ram: 0, network: 0 },
  { label: '14:00', cpu: 0, ram: 0, network: 0 },
];

export const getCalculatedDashboardStats = (): DashboardStats => {
  const total = devices.length;
  const online = devices.filter(d => d.powerStatus === 'On').length;
  const offline = devices.filter(d => d.powerStatus === 'Off').length;
  const problems = alerts.filter(a => a.state !== 'Resolved').length;
  const activeSessions = sessions.filter(s => s.state === 'Active').length;
  const disconnectedSessions = sessions.filter(s => s.state === 'Disconnected').length;
  const hardwareAlertsCount = alerts.filter(a => a.category === 'Hardware' && a.state !== 'Resolved').length;

  return {
    total,
    online,
    offline,
    problems,
    activeSessions,
    disconnectedSessions,
    hardwareAlertsCount,
  };
};
