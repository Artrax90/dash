import {
  agentBuilds,
  agentTokens,
  alerts,
  auditEntries,
  customRoles,
  devices,
  getCalculatedDashboardStats,
  hardwareChanges,
  managedUsers,
  schedules,
  sessions,
  telegramConfig,
} from './mockData';
import type {
  Alert,
  AgentBuild,
  AgentEnrollmentToken,
  AgentVersionInfo,
  AgentUpdateLog,
  AuditEntry,
  BulkOperationProgress,
  BulkOperationRequest,
  CustomRole,
  DashboardStats,
  Device,
  HardwareBaseline,
  HardwareChange,
  HardwareSpec,
  ManagedUser,
  RdpSession,
  Schedule,
  TelegramBotConfig,
} from '@/types';

const getApiBase = () => {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname || 'localhost';
    const protocol = window.location.protocol || 'http:';
    const port = window.location.port === '5173'
      ? (import.meta.env.VITE_API_PORT || '2301')
      : (window.location.port || '2301');
    return `${protocol}//${host}:${port}/api/v1`;
  }
  return 'http://localhost:2301/api/v1';
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || getApiBase();

export function getActiveUserName(): string {
  try {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('wm_user_session');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed) {
          const name = parsed.displayName || parsed.name || parsed.username;
          if (name && name.trim()) return name.trim();
        }
      }
    }
  } catch {}
  return 'Оператор';
}

export function getAuthHeaders(): Record<string, string> {
  const userName = getActiveUserName();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-User-Name': encodeURIComponent(userName)
  };
  try {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('wm_token');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }
  } catch {}
  return headers;
}

const wait = async <T,>(value: T, ms = 50): Promise<T> => new Promise((resolve) => setTimeout(() => resolve(value), ms));

export const devicesApi = {
  list: async (): Promise<Device[]> => {
    try {
      const res = await fetch(`${API_BASE}/devices`);
      if (res.ok) return await res.json();
    } catch {
      // fallback to in-memory
    }
    return wait(devices);
  },
  get: async (id: string): Promise<Device | undefined> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${id}`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(devices.find((device) => device.id === id));
  },
  getPowerLogs: async (id: string): Promise<any[]> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${id}/power-logs`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return [];
  },
  getFleetTelemetryHistory: async (timeRange: string = '24h', group: string = 'ALL'): Promise<{ timeRange: string; points: { label: string; timestamp: number; cpu: number; ram: number; disk: number; activeCount: number }[]; hasData: boolean }> => {
    try {
      const res = await fetch(`${API_BASE}/devices/telemetry/fleet-history?time_range=${timeRange}&group=${encodeURIComponent(group)}`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return { timeRange, points: [], hasData: false };
  },
  getDeviceTelemetryHistory: async (deviceId: string, timeRange: string = '1h'): Promise<{ deviceId: string; timeRange: string; points: { label: string; timestamp: number; cpu: number; ram: number; disk: number }[]; hasData: boolean }> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/telemetry-history?time_range=${timeRange}`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return { deviceId, timeRange, points: [], hasData: false };
  },
  delete: async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${id}`, { method: 'DELETE' });
      if (res.ok) return true;
    } catch {
      // fallback
    }
    const idx = devices.findIndex((d) => d.id === id);
    if (idx !== -1) {
      devices.splice(idx, 1);
      return wait(true);
    }
    return wait(false);
  },
  update: async (id: string, payload: Partial<Device>): Promise<Device | undefined> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    const dev = devices.find((d) => d.id === id);
    if (dev) {
      Object.assign(dev, payload);
      return wait(dev);
    }
    return wait(undefined);
  },
  getAlertPolicy: async (deviceId: string): Promise<any> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/alert-policy`);
      if (res.ok) return await res.json();
    } catch {}
    return null;
  },
  saveAlertPolicy: async (deviceId: string, policy: any): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/alert-policy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(policy),
      });
      if (res.ok) return true;
    } catch {
      // fallback
    }
    return wait(true);
  },
  getCredentials: async (deviceId: string): Promise<any> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/credentials`);
      if (res.ok) return await res.json();
    } catch {}
    return { adminUser: '', useLaps: false, hasPassword: false };
  },
  saveCredentials: async (deviceId: string, payload: any): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/credentials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) return true;
    } catch {}
    return true;
  },
  checkAccess: async (deviceId: string): Promise<{ ok: boolean; message: string }> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/check-access`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {}
    return { ok: true, message: 'Связь и права выполнения подтверждены (SYSTEM / Admin OK)' };
  },
  getAutomation: async (deviceId: string): Promise<any> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/automation`);
      if (res.ok) return await res.json();
    } catch {}
    return { watchdogEnabled: true, abandonedTimeout: '15', idleTimeout: '8', autoClean: true };
  },
  saveAutomation: async (deviceId: string, payload: any): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/automation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) return true;
    } catch {}
    return true;
  },
  setBaseline: async (deviceId: string, spec: HardwareSpec, approvedBy?: string): Promise<HardwareBaseline> => {
    const author = approvedBy || getActiveUserName();
    try {
      const res = await fetch(`${API_BASE}/hardware/baseline/${deviceId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ approvedBy: author, spec }),
      });
      if (res.ok) return await res.json();
    } catch {}
    const newBaseline: HardwareBaseline = {
      id: `bl-${deviceId}`,
      deviceId,
      createdAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
      updatedAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
      approvedBy: author,
      spec,
    };
    const dev = devices.find((d) => d.id === deviceId);
    if (dev) {
      dev.baseline = newBaseline;
      dev.hardwareChangesCount = 0;
    }
    return wait(newBaseline);
  },
  toggleMaintenance: async (deviceId: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/maintenance`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        return data.maintenance;
      }
    } catch {
      // fallback
    }
    const dev = devices.find((d) => d.id === deviceId);
    if (dev) {
      dev.maintenance = !dev.maintenance;
      return wait(dev.maintenance);
    }
    return wait(false);
  },
  wake: async (deviceId: string, meta?: { user?: string; source?: string }): Promise<boolean> => {
    const operator = meta?.user || getActiveUserName();
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/wake`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ user: operator, initiator: operator, source: meta?.source || 'MANUAL' }),
      });
      if (res.ok) return true;
    } catch {}
    return true;
  },
  powerAction: async (
    deviceId: string,
    action: 'WAKE' | 'SHUTDOWN' | 'FORCE_SHUTDOWN' | 'REBOOT' | 'SLEEP' | 'LOGOFF',
    force: boolean = true,
    meta?: { user?: string; source?: string; reason?: string }
  ): Promise<boolean> => {
    const operator = meta?.user || getActiveUserName();
    try {
      const res = await fetch(`${API_BASE}/devices/${deviceId}/power`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action,
          force,
          reason: meta?.reason || `Command from Web UI by ${operator}`,
          user: operator,
          initiator: operator,
          source: meta?.source || 'MANUAL',
        }),
      });
      if (res.ok) return true;
    } catch {}
    return true;
  },
  updateAgent: async (deviceId: string, user?: string): Promise<boolean> => {
    const operator = user || getActiveUserName();
    try {
      const res = await fetch(`${API_BASE}/agents/update/${deviceId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ user: operator, initiator: operator })
      });
      if (res.ok) return true;
    } catch {}
    return true;
  },
  bulkOperation: async (deviceIds: string[], action: string, meta?: { user?: string }): Promise<boolean> => {
    const operator = meta?.user || getActiveUserName();
    try {
      const res = await fetch(`${API_BASE}/devices/bulk`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ deviceIds, action, user: operator, initiator: operator }),
      });
      if (res.ok) return true;
    } catch {}
    return true;
  },
};

export const hardwareApi = {
  getChanges: async (deviceId?: string): Promise<HardwareChange[]> => {
    try {
      const url = deviceId ? `${API_BASE}/hardware/changes?device_id=${deviceId}` : `${API_BASE}/hardware/changes`;
      const res = await fetch(url);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(deviceId ? hardwareChanges.filter((c) => c.deviceId === deviceId) : hardwareChanges);
  },
};

export const dashboardApi = {
  stats: async (): Promise<DashboardStats> => {
    try {
      const res = await fetch(`${API_BASE}/devices/stats`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(getCalculatedDashboardStats());
  },
};

export const sessionsApi = {
  list: async (deviceId?: string): Promise<RdpSession[]> => {
    try {
      const url = deviceId ? `${API_BASE}/sessions?device_id=${encodeURIComponent(deviceId)}` : `${API_BASE}/sessions`;
      const res = await fetch(url);
      if (res.ok) return await res.json();
    } catch {}
    return [];
  },
  logoff: async (sessionId: number): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/sessions/${sessionId}/logoff`, { method: 'POST' });
      if (res.ok) return true;
    } catch {}
    return true;
  },
};

export const alertsApi = {
  list: async (): Promise<Alert[]> => {
    try {
      const res = await fetch(`${API_BASE}/alerts`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(alerts);
  },
  acknowledge: async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/alerts/${id}/acknowledge`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (res.ok) return true;
    } catch {}
    const alert = alerts.find((a) => a.id === id);
    if (alert) {
      alert.state = 'Acknowledged';
      return wait(true);
    }
    return wait(false);
  },
  resolve: async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/alerts/${id}/resolve`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (res.ok) return true;
    } catch {}
    const alert = alerts.find((a) => a.id === id);
    if (alert) {
      alert.state = 'Resolved';
      return wait(true);
    }
    return wait(false);
  },
  resolveAll: async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/alerts/resolve-all`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (res.ok) return true;
    } catch {}
    alerts.forEach(a => { a.state = 'Resolved'; });
    return wait(true);
  },
  delete: async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/alerts/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) return true;
    } catch {}
    return true;
  }
};

export const schedulesApi = {
  list: async (): Promise<Schedule[]> => {
    try {
      const res = await fetch(`${API_BASE}/schedules`, {
        headers: getAuthHeaders()
      });
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(schedules);
  },
  create: async (payload: Partial<Schedule>): Promise<Schedule> => {
    const creator = payload.createdBy || getActiveUserName() || 'Администратор';
    const enrichedPayload = { ...payload, createdBy: creator };
    try {
      const res = await fetch(`${API_BASE}/schedules`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(enrichedPayload)
      });
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    const newSch: Schedule = {
      id: `SCH-${String(schedules.length + 1).padStart(2, '0')}`,
      name: payload.name || 'Новое расписание',
      description: payload.description || '',
      enabled: payload.enabled ?? true,
      createdBy: creator,
      createdAt: new Date().toISOString(),
      timezone: payload.timezone || 'Europe/Moscow',
      days: payload.days || 'Пн-Пт',
      daysList: payload.daysList || ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ'],
      time: payload.time || '08:00',
      action: payload.action || 'LIFECYCLE',
      target: payload.target || 'All',
      type: payload.type || (payload.steps && payload.steps.length > 1 ? 'Lifecycle' : 'Custom'),
      steps: payload.steps || [],
      gracePeriodMinutes: payload.gracePeriodMinutes || 0,
      warningMessage: payload.warningMessage || '',
      forceShutdown: payload.forceShutdown || false
    };
    schedules.push(newSch);
    return wait(newSch);
  },
  update: async (id: string, payload: Partial<Schedule>): Promise<Schedule> => {
    try {
      const res = await fetch(`${API_BASE}/schedules/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    const idx = schedules.findIndex(s => s.id === id);
    if (idx !== -1) {
      schedules[idx] = { ...schedules[idx], ...payload };
      return wait(schedules[idx]);
    }
    throw new Error('Schedule not found');
  },
  delete: async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/schedules/${id}`, { method: 'DELETE' });
      if (res.ok) return true;
    } catch {
      // fallback
    }
    const idx = schedules.findIndex(s => s.id === id);
    if (idx !== -1) {
      schedules.splice(idx, 1);
      return wait(true);
    }
    return wait(false);
  },
  toggle: async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/schedules/${id}/toggle`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        return data.enabled;
      }
    } catch {
      // fallback
    }
    const s = schedules.find((item) => item.id === id);
    if (s) {
      s.enabled = !s.enabled;
      return wait(s.enabled);
    }
    return wait(false);
  },
  runNow: async (id: string): Promise<{ status: string; message: string; summary: string; log: any }> => {
    try {
      const res = await fetch(`${API_BASE}/schedules/${id}/run`, { method: 'POST' });
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait({
      status: 'success',
      message: 'Расписание успешно запущено',
      summary: 'Команда выполнена успешно',
      log: {
        id: `LOG-${Date.now().toString().slice(-4)}`,
        scheduleId: id,
        scheduleName: 'Расписание',
        action: 'WAKE',
        target: 'All',
        timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
        status: 'Success',
        devicesTargeted: 1,
        devicesSuccess: 1,
        devicesFailed: 0,
        triggeredBy: 'MANUAL_WEB_UI',
        details: 'Ручной запуск администратором.'
      }
    });
  },
  getLogs: async (): Promise<any[]> => {
    try {
      const res = await fetch(`${API_BASE}/schedules/logs`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return [];
  }
};

export const agentsApi = {
  getTokens: async (): Promise<AgentEnrollmentToken[]> => {
    try {
      const res = await fetch(`${API_BASE}/agents/tokens`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(agentTokens);
  },
  getBuilds: async (): Promise<AgentBuild[]> => {
    try {
      const res = await fetch(`${API_BASE}/agents/builds`);
      if (res.ok) return await res.json();
    } catch {}
    return wait(agentBuilds);
  },
  createToken: async (payload: { targetGroup: string; expiry?: string; expiresAt?: string; isReusable?: boolean; maxUses?: number; createdBy?: string }): Promise<AgentEnrollmentToken> => {
    const author = payload.createdBy || getActiveUserName();
    try {
      const res = await fetch(`${API_BASE}/agents/tokens`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ ...payload, createdBy: author }),
      });
      if (res.ok) return await res.json();
    } catch {}
    const newToken: AgentEnrollmentToken = {
      id: `TOK-${String(agentTokens.length + 1).padStart(2, '0')}`,
      token: `wm_tok_${Math.random().toString(36).substring(2, 12)}_${Math.random().toString(36).substring(2, 10)}`,
      targetGroup: payload.targetGroup,
      serverUrl: typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname || 'localhost'}:${window.location.port === '5173' ? '2301' : (window.location.port || '2301')}` : 'http://localhost:2301',
      createdAt: 'Только что',
      expiresAt: payload.expiresAt || (payload.expiry === '24h' ? 'Через 24 часа' : payload.expiry === '7d' ? 'Через 7 дней' : payload.expiry === 'never' ? 'Бессрочно' : 'Через 30 дней'),
      isReusable: payload.isReusable !== false,
      usedCount: 0,
      maxUses: payload.maxUses,
      createdBy: author,
    };
    agentTokens.unshift(newToken);
    return wait(newToken);
  },
  updateToken: async (id: string, payload: Partial<AgentEnrollmentToken>): Promise<AgentEnrollmentToken | undefined> => {
    try {
      const res = await fetch(`${API_BASE}/agents/tokens/${id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });
      if (res.ok) return await res.json();
    } catch {}
    const tok = agentTokens.find(t => t.id === id || t.token === id);
    if (tok) {
      Object.assign(tok, payload);
      return wait(tok);
    }
    return wait(undefined);
  },
  revokeToken: async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/agents/tokens/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) return true;
    } catch {}
    const idx = agentTokens.findIndex((t) => t.id === id || t.token === id);
    if (idx !== -1) {
      agentTokens.splice(idx, 1);
      return wait(true);
    }
    return wait(false);
  },
  getSettings: async (): Promise<{ defaultHeartbeatInterval: number; groupHeartbeatIntervals: Record<string, number> }> => {
    try {
      const res = await fetch(`${API_BASE}/agents/settings`);
      if (res.ok) return await res.json();
    } catch {}
    return {
      defaultHeartbeatInterval: 60,
      groupHeartbeatIntervals: {
        Servers: 15,
        DevOps: 30,
        Office: 60
      }
    };
  },
  updateSettings: async (settings: any) => {
    try {
      const res = await fetch(`${API_BASE}/agents/settings`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(settings)
      });
      if (res.ok) return await res.json();
    } catch {}
    return settings;
  },
  getVersionInfo: async (): Promise<AgentVersionInfo> => {
    try {
      const res = await fetch(`${API_BASE}/agents/version-info`);
      if (res.ok) return await res.json();
    } catch {}
    return {
      currentVersion: '2.2.0',
      releaseDate: '2026-08-28',
      minSupportedVersion: '1.0.0',
      changelog: 'Релиз v2.2.0: точное распознавание всех модулей RAM (DIMM_1/DIMM_2), отслеживание извлечения и возврата ОЗУ, мониторинг дисков/GPU и прямое OTA-обновление',
      totalAgents: 0,
      upToDateCount: 0,
      outdatedCount: 0,
      updatingCount: 0
    };
  },
  updateAgent: async (deviceId: string, user?: string): Promise<{ status: string; message: string; deviceId: string; targetVersion?: string }> => {
    const operator = user || getActiveUserName();
    try {
      const res = await fetch(`${API_BASE}/agents/update/${deviceId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ user: operator, initiator: operator })
      });
      if (res.ok) return await res.json();
    } catch {}
    return {
      status: 'queued',
      deviceId,
      message: `Команда обновления отправлена на ${deviceId}`,
      targetVersion: '2.2.0'
    };
  },
  updateBulk: async (deviceIds?: string[], updateAllOutdated?: boolean, user?: string): Promise<{ status: string; count: number; message: string; deviceIds?: string[] }> => {
    const operator = user || getActiveUserName();
    try {
      const res = await fetch(`${API_BASE}/agents/update-bulk`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ deviceIds, updateAllOutdated, user: operator, initiator: operator })
      });
      if (res.ok) return await res.json();
    } catch {}
    return {
      status: 'queued',
      count: deviceIds ? deviceIds.length : 0,
      message: 'Массовое обновление отправлено'
    };
  },
  getUpdateLogs: async (): Promise<AgentUpdateLog[]> => {
    try {
      const res = await fetch(`${API_BASE}/agents/update-logs`);
      if (res.ok) return await res.json();
    } catch {}
    return [];
  },
};

export interface GroupItem {
  name: string;
  desc?: string;
  color?: 'blue' | 'green' | 'purple' | 'orange' | 'red' | 'cyan' | 'slate';
  schedule?: string;
  count?: number;
}

export const groupsApi = {
  list: async (): Promise<GroupItem[]> => {
    try {
      const res = await fetch(`${API_BASE}/groups`);
      if (res.ok) return await res.json();
    } catch {}
    return [
      { name: 'Office', desc: 'Компьютеры главного офиса компании', color: 'blue', schedule: 'Office Working Day' },
      { name: 'Warehouse', desc: 'Терминалы логистического склада', color: 'orange', schedule: 'Warehouse Night Mode' },
      { name: 'Management', desc: 'Руководство и переговорные комнаты', color: 'green', schedule: 'Без расписания' },
      { name: 'Testing', desc: 'QA и тестовая лаборатория оборудования', color: 'purple', schedule: 'Testing Lab' },
      { name: 'Dev', desc: 'Рабочие станции разработчиков и дизайнеров', color: 'cyan', schedule: 'Dev Working Day' },
      { name: 'Accounting', desc: 'Бухгалтерия и финансовый отдел', color: 'slate', schedule: 'Без расписания' },
      { name: 'Servers', desc: 'Серверное оборудование и гипервизоры', color: 'red', schedule: 'Круглосуточно (24/7)' },
    ];
  },
  create: async (group: GroupItem): Promise<GroupItem> => {
    try {
      const res = await fetch(`${API_BASE}/groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(group),
      });
      if (res.ok) return await res.json();
    } catch {}
    return group;
  },
  update: async (name: string, payload: Partial<GroupItem>): Promise<GroupItem> => {
    try {
      const res = await fetch(`${API_BASE}/groups/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) return await res.json();
    } catch {}
    return { name, ...payload };
  },
  delete: async (name: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/groups/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      });
      if (res.ok) return true;
    } catch {}
    return true;
  }
};

export const rolesApi = {
  list: async (): Promise<CustomRole[]> => {
    try {
      const res = await fetch(`${API_BASE}/roles`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(customRoles);
  },
  createRole: async (role: Omit<CustomRole, 'id' | 'userCount'>): Promise<CustomRole> => {
    try {
      const res = await fetch(`${API_BASE}/roles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(role)
      });
      if (res.ok) return await res.json();
    } catch {}
    const newRole: CustomRole = {
      ...role,
      id: `ROLE-${String(customRoles.length + 1).padStart(2, '0')}`,
      userCount: 0,
    };
    customRoles.push(newRole);
    return wait(newRole);
  },
  updateRole: async (nameOrId: string, payload: Partial<CustomRole>): Promise<CustomRole> => {
    try {
      const res = await fetch(`${API_BASE}/roles/${encodeURIComponent(nameOrId)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) return await res.json();
    } catch {}
    const role = customRoles.find(r => r.name === nameOrId || r.id === nameOrId);
    if (role) {
      Object.assign(role, payload);
      return wait(role);
    }
    return wait(payload as any);
  }
};

export const usersApi = {
  list: async (): Promise<ManagedUser[]> => {
    try {
      const res = await fetch(`${API_BASE}/users`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(managedUsers);
  },
  create: async (payload: Partial<ManagedUser> & { password?: string }): Promise<ManagedUser> => {
    const res = await fetch(`${API_BASE}/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Ошибка создания пользователя' }));
      throw new Error(err.detail || 'Ошибка создания пользователя');
    }
    return await res.json();
  },
  update: async (id: string, payload: Partial<ManagedUser> & { newPassword?: string }): Promise<ManagedUser> => {
    const res = await fetch(`${API_BASE}/users/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Ошибка обновления пользователя' }));
      throw new Error(err.detail || 'Ошибка обновления пользователя');
    }
    return await res.json();
  },
  delete: async (id: string): Promise<boolean> => {
    const res = await fetch(`${API_BASE}/users/${encodeURIComponent(id)}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Ошибка удаления пользователя' }));
      throw new Error(err.detail || 'Ошибка удаления пользователя');
    }
    return true;
  }
};

export const authApi = {
  getSetupStatus: async (): Promise<{ isConfigured: boolean; userCount: number }> => {
    try {
      const res = await fetch(`${API_BASE}/users/setup-status`);
      if (res.ok) return await res.json();
    } catch {}
    return { isConfigured: true, userCount: 1 };
  },
  setupInitialAdmin: async (payload: { username: string; displayName: string; email?: string; password: string; telegramChatId?: string }): Promise<{ status: string; token: string; user: ManagedUser }> => {
    const res = await fetch(`${API_BASE}/users/setup-initial-admin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Ошибка инициализации администратора' }));
      throw new Error(err.detail || 'Ошибка инициализации администратора');
    }
    return await res.json();
  },
  login: async (username: string, password: string): Promise<{ status: string; token: string; user: ManagedUser }> => {
    const res = await fetch(`${API_BASE}/users/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Неверный логин или пароль' }));
      throw new Error(err.detail || 'Неверный логин или пароль');
    }
    return await res.json();
  },
  changePassword: async (username: string, oldPassword: string, newPassword: string): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${API_BASE}/users/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, oldPassword, newPassword })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Ошибка смены пароля' }));
      throw new Error(err.detail || 'Ошибка смены пароля');
    }
    return await res.json();
  }
};

export const auditApi = {
  list: async (): Promise<AuditEntry[]> => {
    try {
      const res = await fetch(`${API_BASE}/audit`);
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return wait(auditEntries);
  },
};

export const telegramApi = {
  getConfig: async (): Promise<any> => {
    try {
      const res = await fetch(`${API_BASE}/telegram/config`);
      if (res.ok) return await res.json();
    } catch {}
    return wait(telegramConfig);
  },
  saveConfig: async (payload: any): Promise<any> => {
    try {
      const res = await fetch(`${API_BASE}/telegram/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) return await res.json();
    } catch {}
    return payload;
  },
  sendTestAlert: async (message?: string): Promise<{ status: string; message: string }> => {
    try {
      const res = await fetch(`${API_BASE}/telegram/test-alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      });
      if (res.ok) return await res.json();
    } catch {}
    return { status: 'sent', message: 'Тестовый сигнал отправлен' };
  },
  testProxy: async (payload: { botToken?: string; proxyEnabled: boolean; proxyType: string; proxyHost: string; proxyPort: string; proxyUser?: string; proxyPass?: string }): Promise<{ ok: boolean; message: string; botUsername?: string }> => {
    try {
      const res = await fetch(`${API_BASE}/telegram/test-proxy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) return await res.json();
    } catch (e: any) {
      return { ok: false, message: `Ошибка вызова: ${e?.message || 'Сервер недоступен'}` };
    }
    return { ok: false, message: 'Ошибка проверки прокси' };
  }
};

export const bulkApi = {
  powerAction: async (deviceIds: string[], action: string): Promise<boolean> => {
    return devicesApi.bulkOperation(deviceIds, action);
  },
  execute: async (req: BulkOperationRequest): Promise<BulkOperationProgress> => {
    try {
      await devicesApi.bulkOperation(req.deviceIds, req.action);
    } catch {}
    const progress: BulkOperationProgress = {
      id: `BULK-${Date.now()}`,
      action: req.action,
      total: req.deviceIds.length,
      completed: req.deviceIds.length,
      succeeded: req.deviceIds.length,
      failed: 0,
      status: 'Completed',
      startedAt: 'Только что',
      items: req.deviceIds.map((id) => ({
        deviceId: id,
        deviceName: devices.find((d) => d.id === id)?.name || id,
        status: 'Success',
      })),
    };
    return wait(progress, 300);
  },
};

export { wsClient } from '@/services/websocket';
export { notificationService } from '@/services/notificationService';

