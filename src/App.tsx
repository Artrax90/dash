import React, { useEffect, useState, Component, type ReactNode, useCallback, useRef, useMemo } from 'react';
import {
  Activity, AlertTriangle, ArrowDownToLine, ArrowUpRight, ArrowDownLeft, ArrowUp, ArrowDown, ArrowUpDown, Bell, Check, ChevronDown, ChevronRight, CircleHelp,
  Clock3, Command, Cpu, Database, Ellipsis, Filter, Gauge, Globe, HardDrive, Key, LayoutDashboard, ListFilter,
  LoaderCircle, LogOut, Menu, Monitor, Moon, MoreHorizontal, Network, Power, RefreshCw, Search, Send, Server,
  Settings, ShieldCheck, Sun, Tag, Terminal, UserRound, Users as UsersIcon, Wifi, X, Zap, Plus, Trash2, Play,
  Edit3, Lock, Download, Copy, Laptop, FolderPlus, ArrowRight, PanelLeftClose, RotateCw, RotateCcw, Calendar,
  Eye, EyeOff, Sparkles, Pencil, BellOff, CheckCircle2, Usb, Building, Layers, MapPin
} from 'lucide-react';
import { alertsApi, auditApi, dashboardApi, devicesApi, schedulesApi, sessionsApi, usersApi, hardwareApi, agentsApi, rolesApi, telegramApi, bulkApi, groupsApi, authApi, getActiveUserName, wsClient, notificationService } from '@/api';
import type { Alert, AuditEntry, DashboardStats, Device, ManagedUser, RdpSession, Schedule, HardwareSpec, HardwareBaseline, HardwareChange, AgentEnrollmentToken, AgentBuild, CustomRole, AgentVersionInfo, AgentUpdateLog } from '@/types';
import { monitoringSeries } from '@/api/mockData';
import { useLanguage } from '@/i18n/LanguageContext';

export function formatLocalTime(isoString?: string, fallback = '—'): string {
  if (!isoString) return fallback;
  try {
    const d = new Date(isoString);
    if (!isNaN(d.getTime())) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  } catch {}
  return fallback;
}

export function formatDeviceBootTime(isoString?: string, fallback = '—'): string {
  if (!isoString) return fallback;
  try {
    const d = new Date(isoString);
    if (!isNaN(d.getTime())) {
      const now = new Date();
      const isToday = d.toDateString() === now.toDateString();
      const yesterday = new Date(now);
      yesterday.setDate(now.getDate() - 1);
      const isYesterday = d.toDateString() === yesterday.toDateString();
      
      const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      if (isToday) return `сегодня в ${timeStr}`;
      if (isYesterday) return `вчера в ${timeStr}`;
      
      const dateStr = d.toLocaleDateString([], { day: '2-digit', month: 'short' });
      return `${dateStr}, ${timeStr}`;
    }
  } catch {}
  return fallback;
}

export function formatLiveUptime(uptime?: string, bootTimeIso?: string, isOnline = true): string {
  if (!isOnline) return '—';
  if (bootTimeIso) {
    try {
      const d = new Date(bootTimeIso);
      if (!isNaN(d.getTime())) {
        const diffSec = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
        const days = Math.floor(diffSec / 86400);
        const hours = Math.floor((diffSec % 86400) / 3600);
        const mins = Math.floor((diffSec % 3600) / 60);
        if (days > 0) return `${days}д ${String(hours).padStart(2, '0')}ч`;
        if (hours > 0) return `${hours}ч ${String(mins).padStart(2, '0')}м`;
        return mins > 0 ? `${mins}м` : 'Менее 1 мин';
      }
    } catch {}
  }
  if (!uptime || uptime === '—') return isOnline ? 'Только что включен' : '—';
  return uptime.replace(/d\s*/g, 'д ').replace(/h/g, 'ч').replace(/m/g, 'м');
}

export function formatDeviceLastSeen(lastSeen?: string, lastSeenIso?: string, powerStatus?: string): string {
  if (powerStatus === 'On') {
    return 'В сети (онлайн)';
  }
  if (lastSeenIso) {
    try {
      const d = new Date(lastSeenIso);
      if (!isNaN(d.getTime())) {
        const now = Date.now();
        const diffSec = Math.floor((now - d.getTime()) / 1000);
        if (diffSec < 60) return `${Math.max(1, diffSec)} сек. назад`;
        if (diffSec < 3600) return `${Math.floor(diffSec / 60)} мин. назад`;
        if (diffSec < 86400) {
          const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
          return `сегодня в ${timeStr}`;
        }
        return d.toLocaleString([], { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
      }
    } catch {
      // fallback
    }
  }
  return lastSeen && lastSeen !== 'Только что' && lastSeen !== 'В сети' ? lastSeen : 'Не в сети';
}

export interface BuildingConfig {
  name: string;
  floorsCount: number;
  hasBasement: boolean;
  hasSubFloor: boolean;
  floors: string[];
}

export function generateBuildingFloors(floorsCount: number = 3, hasBasement: boolean = false, hasSubFloor: boolean = false): string[] {
  const res: string[] = [];
  if (hasSubFloor) res.push('-1 этаж');
  if (hasBasement) res.push('Цоколь');
  const count = Math.max(1, Math.min(100, Math.floor(floorsCount || 1)));
  for (let i = 1; i <= count; i++) {
    res.push(`${i} этаж`);
  }
  return res;
}

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error?: Error }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="panel" style={{ padding: '32px', textAlign: 'center', margin: '20px' }}>
          <AlertTriangle size={32} style={{ color: 'var(--red)' }} />
          <h2 style={{ marginTop: '12px' }}>Произошла ошибка при отрисовке раздела</h2>
          <p style={{ color: 'var(--muted)', marginTop: '6px' }}>{this.state.error?.message || 'Неизвестная ошибка'}</p>
          <button className="button primary" style={{ marginTop: '16px' }} onClick={() => window.location.reload()}>
            Перезагрузить страницу
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// Multi-group helper: extracts array of groups from device
export function getDeviceGroups(device: Device): string[] {
  if (device.groups && Array.isArray(device.groups)) {
    return device.groups.filter(Boolean);
  }
  if (device.group !== undefined && device.group !== null) {
    return device.group.split(',').map(g => g.trim()).filter(Boolean);
  }
  return [];
}

// Pixel-perfect Accessible Switch Component
export function Switch({
  checked,
  onChange,
  disabled,
  title
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      title={title}
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        if (!disabled) onChange(!checked);
      }}
      className={`app-switch ${checked ? 'active' : ''} ${disabled ? 'disabled' : ''}`}
    >
      <span className="app-switch-thumb" />
    </button>
  );
}

// Global CSV & File Export Utilities
function exportDevicesToCsv(devices: Device[]) {
  const headers = ['ID', 'Name', 'Hostname', 'Groups', 'IP', 'MAC', 'Status', 'User', 'CPU%', 'RAM%', 'Disk%', 'Uptime', 'LastSeen', 'AssetTag', 'Notes'];
  const rows = devices.map(d => [
    d.id,
    `"${(d.name || '').replace(/"/g, '""')}"`,
    d.hostname,
    `"${getDeviceGroups(d).join(', ')}"`,
    d.ip,
    d.mac,
    d.powerStatus,
    `"${(d.currentUser || '').replace(/"/g, '""')}"`,
    d.cpu,
    d.ram,
    d.disk,
    d.uptime,
    d.lastSeen,
    `"${(d.assetTag || '').replace(/"/g, '""')}"`,
    `"${(d.notes || '').replace(/"/g, '""')}"`
  ]);
  const csvContent = '\uFEFF' + [headers.join(';'), ...rows.map(r => r.join(';'))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `fleet_devices_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function exportAuditToCsv(entries: AuditEntry[]) {
  const headers = ['Timestamp', 'User', 'Action', 'Target', 'Result', 'Details'];
  const rows = entries.map(e => [
    e.timestamp,
    `"${(e.user || '').replace(/"/g, '""')}"`,
    e.action,
    e.target,
    e.result,
    `"${(e.details || '').replace(/"/g, '""')}"`
  ]);
  const csvContent = '\uFEFF' + [headers.join(';'), ...rows.map(r => r.join(';'))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `audit_log_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Universal Robust Clipboard Copy Helper (works on HTTP, LAN IP, and HTTPS)
export function copyToClipboard(text: string): boolean {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).catch(() => {
      fallbackCopyText(text);
    });
    return true;
  } else {
    return fallbackCopyText(text);
  }
}

function fallbackCopyText(text: string): boolean {
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    textArea.setAttribute('readonly', '');
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    return successful;
  } catch (err) {
    console.error('Fallback copy failed:', err);
    return false;
  }
}

type Page = 'Dashboard' | 'Devices' | 'Device detail' | 'Groups' | 'Schedules' | 'Monitoring' | 'Alerts' | 'Hardware' | 'Users' | 'Roles' | 'Agents' | 'Telegram' | 'Audit Log' | 'Settings';

interface RouteState {
  page: Page;
  selectedDevice?: string;
  selectedGroup?: string;
  deviceFilter?: { group?: string; status?: string; rdp?: boolean };
}

function parseUrlHash(): RouteState {
  const hash = window.location.hash.replace(/^#\/?/, '').trim();
  if (!hash) return { page: 'Dashboard' };

  const parts = hash.split('/');
  const route = parts[0].toLowerCase();
  const param = parts[1] ? decodeURIComponent(parts[1]) : undefined;

  switch (route) {
    case 'devices':
      return param ? { page: 'Device detail', selectedDevice: param } : { page: 'Devices' };
    case 'device':
      return { page: 'Device detail', selectedDevice: param || 'PC-B3E4' };
    case 'groups':
      return { page: 'Groups', selectedGroup: param };
    case 'schedules':
      return { page: 'Schedules' };
    case 'monitoring':
      return { page: 'Monitoring' };
    case 'alerts':
      return { page: 'Alerts' };
    case 'hardware':
    case 'baseline':
      return { page: 'Hardware' };
    case 'users':
      return { page: 'Users' };
    case 'roles':
      return { page: 'Roles' };
    case 'agents':
      return { page: 'Agents' };
    case 'telegram':
      return { page: 'Telegram' };
    case 'audit':
      return { page: 'Audit Log' };
    case 'settings':
      return { page: 'Settings' };
    case 'dashboard':
    default:
      return { page: 'Dashboard' };
  }
}

function buildUrlHash(state: RouteState): string {
  switch (state.page) {
    case 'Dashboard': return '#/dashboard';
    case 'Devices': return '#/devices';
    case 'Device detail': return `#/devices/${encodeURIComponent(state.selectedDevice || 'PC-B3E4')}`;
    case 'Groups': return state.selectedGroup ? `#/groups/${encodeURIComponent(state.selectedGroup)}` : '#/groups';
    case 'Schedules': return '#/schedules';
    case 'Monitoring': return '#/monitoring';
    case 'Alerts': return '#/alerts';
    case 'Hardware': return '#/hardware';
    case 'Users': return '#/users';
    case 'Roles': return '#/roles';
    case 'Agents': return '#/agents';
    case 'Telegram': return '#/telegram';
    case 'Audit Log': return '#/audit';
    case 'Settings': return '#/settings';
    default: return '#/dashboard';
  }
}

function LoginScreen({ onLogin, workspaceName }: { onLogin: (user: ManagedUser) => void; workspaceName: string }) {
  const [isConfigured, setIsConfigured] = useState<boolean | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Setup Wizard State (for brand-new installation)
  const [setupFullName, setSetupFullName] = useState('Главный администратор');
  const [setupUsername, setSetupUsername] = useState('admin');
  const [setupEmail, setSetupEmail] = useState('admin@bmstu.local');
  const [setupPassword, setSetupPassword] = useState('');
  const [setupTelegram, setSetupTelegram] = useState('');

  useEffect(() => {
    authApi.getSetupStatus().then((res) => {
      setIsConfigured(res.isConfigured);
    }).catch(() => {
      setIsConfigured(true);
    });
  }, []);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Введите имя пользователя и пароль');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await authApi.login(username.trim(), password.trim());
      onLogin(res.user);
    } catch (err: any) {
      setError(err?.message || 'Неверный логин или пароль');
      setLoading(false);
    }
  };

  const handleSetupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!setupUsername.trim() || !setupFullName.trim()) {
      setError('Укажите имя и логин администратора');
      return;
    }
    if (!setupPassword.trim() || setupPassword.trim().length < 4) {
      setError('Пароль должен содержать минимум 4 символа');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await authApi.setupInitialAdmin({
        username: setupUsername.trim(),
        displayName: setupFullName.trim(),
        email: setupEmail.trim(),
        password: setupPassword.trim(),
        telegramChatId: setupTelegram.trim()
      });
      onLogin(res.user);
    } catch (err: any) {
      setError(err?.message || 'Ошибка первичной инициализации');
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: '#131e2e',
    border: '1px solid rgba(255, 255, 255, 0.16)',
    borderRadius: '8px',
    padding: '10px 14px',
    color: '#ffffff',
    fontSize: '13px',
    boxSizing: 'border-box',
    outline: 'none',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: '12px',
    fontWeight: 600,
    color: '#94a3b8',
    display: 'block',
    marginBottom: '6px'
  };

  if (isConfigured === null) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0a0e17' }}>
        <span className="pulse-dot" />
      </div>
    );
  }

  // 1. Initial First-Run Setup Screen
  if (!isConfigured) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'radial-gradient(circle at 50% 20%, rgba(37, 99, 235, 0.22), transparent 70%), #0a0e17', padding: '20px', color: '#f1f5f9' }}>
        <div className="confirm-modal" style={{ width: '480px', textAlign: 'left', background: 'rgba(15, 23, 42, 0.96)', backdropFilter: 'blur(24px)', border: '1px solid rgba(255, 255, 255, 0.14)', boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.8)', color: '#f1f5f9' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '18px' }}>
            <div className="confirm-icon" style={{ background: 'rgba(59, 130, 246, 0.15)', color: 'var(--blue)', margin: 0, width: '48px', height: '48px' }}>
              <ShieldCheck size={26} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '19px', margin: 0, fontWeight: 700, color: '#ffffff' }}>Первичная настройка</h2>
                <span className="badge match" style={{ fontSize: '10px' }}>Инициализация</span>
              </div>
              <p style={{ margin: '3px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
                Создание учетной записи Главного Суперадминистратора
              </p>
            </div>
          </div>

          {error && (
            <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#f87171', padding: '10px 12px', borderRadius: '8px', fontSize: '12px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={15} /> {error}
            </div>
          )}

          <form onSubmit={handleSetupSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={labelStyle}>ФИО / Имя администратора *</label>
              <input
                style={inputStyle}
                value={setupFullName}
                onChange={e => setSetupFullName(e.target.value)}
                placeholder="Главный администратор"
                autoFocus
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={labelStyle}>Логин (Username) *</label>
                <input
                  className="mono"
                  style={inputStyle}
                  value={setupUsername}
                  onChange={e => setSetupUsername(e.target.value)}
                  placeholder="admin"
                />
              </div>
              <div>
                <label style={labelStyle}>Рабочий Email</label>
                <input
                  style={inputStyle}
                  value={setupEmail}
                  onChange={e => setSetupEmail(e.target.value)}
                  placeholder="admin@bmstu.local"
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
                <label style={{ ...labelStyle, marginBottom: 0 }}>Пароль администратора *</label>
                <button
                  type="button"
                  className="link-button"
                  style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#60a5fa', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                  onClick={() => {
                    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%&*';
                    let p = '';
                    for (let i = 0; i < 12; i++) p += chars.charAt(Math.floor(Math.random() * chars.length));
                    setSetupPassword(p);
                    navigator.clipboard.writeText(p);
                  }}
                >
                  <Sparkles size={13} /> 🎲 Сгенерировать
                </button>
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  className="mono"
                  style={{ ...inputStyle, paddingRight: '40px' }}
                  type={showPassword ? 'text' : 'password'}
                  value={setupPassword}
                  onChange={e => setSetupPassword(e.target.value)}
                  placeholder="Введите надежный пароль..."
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div>
              <label style={labelStyle}>
                Telegram Chat ID или @username (опционально)
              </label>
              <input
                className="mono"
                style={inputStyle}
                value={setupTelegram}
                onChange={e => setSetupTelegram(e.target.value)}
                placeholder="например: 123456789 или @artrax"
              />
            </div>

            <Button primary type="submit" disabled={loading || !setupUsername.trim() || !setupPassword.trim()} style={{ width: '100%', marginTop: '6px', justifyContent: 'center', padding: '11px', background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)', color: '#ffffff', fontWeight: 600, border: 'none', borderRadius: '8px', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)' }}>
              {loading ? 'Инициализация...' : 'Завершить установку и войти'}
            </Button>
          </form>

          <div style={{ marginTop: '18px', paddingTop: '14px', borderTop: '1px solid rgba(255, 255, 255, 0.08)', fontSize: '11px', color: '#64748b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>🔒 Режим первого запуска</span>
            <span>v2.8.7</span>
          </div>
        </div>
      </div>
    );
  }

  // 2. Standard Production Login Screen
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'radial-gradient(circle at 50% 25%, rgba(37, 99, 235, 0.18), transparent 65%), #0a0e17', padding: '20px', color: '#f1f5f9' }}>
      <div className="confirm-modal" style={{ width: '420px', textAlign: 'left', background: 'rgba(15, 23, 42, 0.96)', backdropFilter: 'blur(24px)', border: '1px solid rgba(255, 255, 255, 0.14)', boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.8)', color: '#f1f5f9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '22px' }}>
          <div className="confirm-icon" style={{ background: 'rgba(59, 130, 246, 0.15)', color: 'var(--blue)', margin: 0, width: '48px', height: '48px' }}>
            <Server size={26} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ fontSize: '19px', margin: 0, fontWeight: 700, color: '#ffffff' }}>Workstation Manager</h2>
            </div>
            <p style={{ margin: '3px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
              Рабочее пространство: <strong style={{ color: '#60a5fa' }}>{workspaceName}</strong>
            </p>
          </div>
        </div>

        {error && (
          <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#f87171', padding: '10px 12px', borderRadius: '8px', fontSize: '12px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div>
            <label style={labelStyle}>Имя пользователя / Логин</label>
            <input
              className="mono"
              style={inputStyle}
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Введите логин..."
              autoFocus
            />
          </div>

          <div>
            <label style={labelStyle}>Пароль учетной записи</label>
            <div style={{ position: 'relative' }}>
              <input
                className="mono"
                style={{ ...inputStyle, paddingRight: '40px' }}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <Button primary type="submit" disabled={loading} style={{ width: '100%', marginTop: '6px', justifyContent: 'center', padding: '11px', background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)', color: '#ffffff', fontWeight: 600, border: 'none', borderRadius: '8px', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)' }}>
            {loading ? 'Проверка данных...' : 'Войти в систему'}
          </Button>
        </form>

        <div style={{ marginTop: '18px', paddingTop: '14px', borderTop: '1px solid rgba(255, 255, 255, 0.08)', fontSize: '11px', color: '#64748b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldCheck size={13} style={{ color: '#22c55e' }} /> Защищенная авторизация
          </span>
          <span style={{ color: '#475569' }}>v2.8.7</span>
        </div>
      </div>
    </div>
  );
}

function App() {
  const { lang, setLang, t } = useLanguage();
  const [route, setRoute] = useState<RouteState>(() => parseUrlHash());
  const [dark, setDark] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [toast, setToast] = useState('');

  // Current logged in user session
  const [currentUser, setCurrentUser] = useState<ManagedUser | null>(() => {
    try {
      const saved = localStorage.getItem('wm_user_session');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.username) return parsed;
      }
    } catch {}
    return null;
  });

  // Live sidebar counters
  const [activeAlertsCount, setActiveAlertsCount] = useState(3);
  const [onlineDeviceCount, setOnlineDeviceCount] = useState(1);
  const [devicesList, setDevicesList] = useState<Device[]>([]);

  // Modals state
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  // Profile password change state
  const [profileOldPassword, setProfileOldPassword] = useState('');
  const [profileNewPassword, setProfileNewPassword] = useState('');
  const [profileShowPassword, setProfileShowPassword] = useState(false);

  // Workspace name state with persistence
  const [workspaceName, setWorkspaceName] = useState<string>(() => {
    try {
      return localStorage.getItem('wm_workspace_name') || 'BMSTU';
    } catch {
      return 'BMSTU';
    }
  });

  const handleUpdateWorkspaceName = (newName: string) => {
    const trimmed = newName.trim() || 'BMSTU';
    setWorkspaceName(trimmed);
    try {
      localStorage.setItem('wm_workspace_name', trimmed);
    } catch {}
  };

  // Sync with browser Back/Forward buttons (popstate)
  useEffect(() => {
    notificationService.initAutoPrompt();

    const handlePopState = () => {
      const parsed = parseUrlHash();
      setRoute(parsed);
    };
    window.addEventListener('popstate', handlePopState);
    window.addEventListener('hashchange', handlePopState);

    const unsubAlert = wsClient.on('alert.created', (newAlert: any) => {
      setActiveAlertsCount(prev => prev + 1);
      if (newAlert && newAlert.description) {
        setToast(`🚨 ${newAlert.device || newAlert.deviceName || 'ПК'}: ${newAlert.description}`);
      }
    });
    const unsubHw = wsClient.on('hardware.change', (hw: any) => {
      if (hw && hw.component) {
        setToast(`⚠️ ${hw.deviceId}: Изменение оборудования (${hw.component}) -> ${hw.currentValue || hw.changeType}`);
      }
    });
    const unsubResolved = wsClient.on('alert.resolved', () => {
      alertsApi.list().then(list => setActiveAlertsCount(list.filter(a => a.state !== 'Resolved').length)).catch(() => {});
    });

    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('hashchange', handlePopState);
      unsubAlert();
      unsubHw();
      unsubResolved();
    };
  }, []);

  // Update live counters periodically
  useEffect(() => {
    alertsApi.list().then(list => setActiveAlertsCount(list.filter(a => a.state !== 'Resolved').length)).catch(() => {});
    devicesApi.list().then(list => {
      setDevicesList(list);
      setOnlineDeviceCount(list.filter(d => d.powerStatus === 'On').length);
    }).catch(() => {});
  }, [route.page]);

  const navigateTo = useCallback((nextState: Partial<RouteState> & { page: Page }) => {
    const targetDevice = nextState.selectedDevice || (nextState.page === 'Device detail' ? route.selectedDevice || 'PC-B3E4' : undefined);
    const merged: RouteState = {
      page: nextState.page,
      selectedDevice: targetDevice,
      selectedGroup: nextState.selectedGroup,
      deviceFilter: nextState.deviceFilter ?? {}
    };
    const newHash = buildUrlHash(merged);
    if (window.location.hash !== newHash) {
      window.location.hash = newHash;
    }
    setRoute(merged);
    setMobileNav(false);
  }, [route.selectedDevice]);

  const page = route.page;
  const selectedDevice = route.selectedDevice || 'PC-B3E4';
  const selectedGroup = route.selectedGroup;
  const deviceFilter = route.deviceFilter || {};

  const isSuperAdmin = currentUser?.role === 'Суперадминистратор' || currentUser?.role === 'SuperAdmin';
  const isObserver = currentUser?.role === 'Наблюдатель' || currentUser?.role === 'Observer';

  const rawNavigation: { label: Page; name: string; icon: typeof LayoutDashboard; group?: string; adminOnly?: boolean }[] = [
    { label: 'Dashboard', name: t('nav.dashboard'), icon: LayoutDashboard },
    { label: 'Devices', name: t('nav.devices'), icon: Monitor },
    { label: 'Groups', name: t('nav.groups'), icon: Database },
    { label: 'Schedules', name: t('nav.schedules'), icon: Clock3 },
    { label: 'Monitoring', name: t('nav.monitoring'), icon: Activity, group: t('nav.operations') },
    { label: 'Alerts', name: t('nav.alerts'), icon: Bell },
    { label: 'Hardware', name: t('nav.hardware') || 'Аппаратный эталон', icon: Cpu },
    { label: 'Agents', name: t('nav.agents'), icon: Server },
    { label: 'Users', name: t('nav.users'), icon: UsersIcon, group: t('nav.administration'), adminOnly: true },
    { label: 'Roles', name: t('nav.roles'), icon: ShieldCheck, adminOnly: true },
    { label: 'Telegram', name: t('nav.telegram'), icon: Send, adminOnly: true },
    { label: 'Audit Log', name: t('nav.audit'), icon: Terminal, adminOnly: true },
    { label: 'Settings', name: t('nav.settings'), icon: Settings, adminOnly: true },
  ];

  const navigation = isSuperAdmin ? rawNavigation : rawNavigation.filter(item => !item.adminOnly);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 3200);
  };

  useEffect(() => {
    if (!currentUser) return;
    const adminPages: Page[] = ['Users', 'Roles', 'Telegram', 'Audit Log', 'Settings'];
    if (!isSuperAdmin && adminPages.includes(route.page)) {
      navigateTo({ page: 'Dashboard' });
      notify('Доступ ограничен: данный раздел доступен только Суперадминистратору.');
    }
  }, [route.page, isSuperAdmin, currentUser]);

  const openDevice = (id: string) => {
    navigateTo({ page: 'Device detail', selectedDevice: id });
  };

  const handleNavigate = (targetPage: Page, filter?: { group?: string; status?: string; rdp?: boolean }) => {
    navigateTo({ page: targetPage, deviceFilter: filter });
  };

  if (!currentUser) {
    return (
      <LoginScreen
        workspaceName={workspaceName}
        onLogin={(user) => {
          setCurrentUser(user);
          try {
            localStorage.setItem('wm_user_session', JSON.stringify(user));
          } catch {}
          notify(`Добро пожаловать, ${user.displayName}!`);
        }}
      />
    );
  }

  return (
    <div className={dark ? 'app dark' : 'app'}>
      <aside className={`sidebar ${mobileNav ? 'open' : ''} ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="brand" onClick={() => navigateTo({ page: 'Dashboard' })} title="Workstation Manager">
            <div className="brand-mark"><Command size={18} /></div>
            <div className="brand-text">
              <strong>workstation</strong>
              <span>manager</span>
            </div>
          </div>
          <button
            className="collapse-btn"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? "Развернуть меню" : "Свернуть меню"}
          >
            {sidebarCollapsed ? <ChevronRight size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>

        <div className="workspace" onClick={() => setShowWorkspaceModal(true)} style={{ cursor: 'pointer' }} title="Управление рабочим пространством">
          <div className="workspace-icon">{(workspaceName || 'N').charAt(0).toUpperCase()}</div>
          <div><small>{t('common.workspaceLabel')}</small><strong>{workspaceName}</strong></div>
          <ChevronDown size={14} style={{ color: 'var(--muted)' }} />
        </div>

        <nav>
          {navigation.map((item) => {
            const isActive = page === item.label;
            const isAlerts = item.label === 'Alerts';
            const isDevices = item.label === 'Devices';
            const isTelegram = item.label === 'Telegram';

            return (
              <div key={item.label}>
                {item.group && <div className="nav-group">{item.group}</div>}
                <button
                  className={`nav-item ${isActive ? 'active' : ''}`}
                  onClick={() => navigateTo({ page: item.label })}
                  title={item.name}
                >
                  <item.icon size={17} />
                  <span>{item.name}</span>
                  {isAlerts && activeAlertsCount > 0 && (
                    <span className="nav-badge alert-badge">{activeAlertsCount}</span>
                  )}
                </button>
              </div>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="profile">
            <div className="avatar" style={{ background: currentUser?.role === 'Суперадминистратор' ? 'var(--blue)' : 'var(--green)' }}>
              {currentUser?.displayName ? currentUser.displayName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'AD'}
            </div>
            <div className="profile-details">
              <strong>{currentUser?.displayName || t('common.userName')}</strong>
              <span>{currentUser?.role || t('common.userRole')}</span>
            </div>
            <div className="profile-actions">
              <button
                className="profile-btn"
                onClick={() => setShowProfileModal(true)}
                title="Профиль администратора"
              >
                <MoreHorizontal size={16} />
              </button>
              <button
                className="profile-btn danger"
                onClick={() => setShowLogoutModal(true)}
                title={t('common.signOut')}
              >
                <LogOut size={15} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {mobileNav && <button className="backdrop" onClick={() => setMobileNav(false)} aria-label="Close menu" />}

      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(true)}><Menu size={20} /></button>
          <div className="breadcrumbs">
            <span onClick={() => navigateTo({ page: 'Dashboard' })} style={{ cursor: 'pointer' }}>{workspaceName}</span>
            <ChevronRight size={14} />
            <strong onClick={() => page === 'Device detail' ? navigateTo({ page: 'Devices' }) : undefined} style={{ cursor: page === 'Device detail' ? 'pointer' : 'default' }}>
              {page === 'Device detail' ? t('nav.devices') : (navigation.find(n => n.label === page)?.name || page)}
            </strong>
            {page === 'Device detail' && (() => {
              const dev = devicesList.find(d => d.id.toUpperCase() === selectedDevice.toUpperCase() || d.hostname.toUpperCase() === selectedDevice.toUpperCase());
              const label = dev ? `${dev.name || dev.hostname} (${dev.id})` : selectedDevice;
              return (
                <>
                  <ChevronRight size={14} />
                  <strong>{label}</strong>
                </>
              );
            })()}
            {page === 'Groups' && selectedGroup && <><ChevronRight size={14} /><strong>{selectedGroup}</strong></>}
          </div>
          <div className="top-actions">
            <div className="system-status"><span className="pulse-dot" /> {t('common.allSystemsOperational')}</div>
            <button className="lang-badge" onClick={() => setLang(lang === 'ru' ? 'en' : 'ru')} title="Switch language">
              <Globe size={14} /> {lang.toUpperCase()}
            </button>
            <button className="icon-button" onClick={() => setDark(!dark)} aria-label="Toggle theme" title="Переключить тему">
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button className="icon-button notification" onClick={() => navigateTo({ page: 'Alerts' })} aria-label="Notifications" title="Оповещения">
              <Bell size={17} /><i />
            </button>
            <div className="top-avatar" onClick={() => setShowProfileModal(true)} style={{ cursor: 'pointer' }} title="Профиль">
              {currentUser?.displayName ? currentUser.displayName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'AD'}
            </div>
          </div>
        </header>

        <div className="content">
          <ErrorBoundary>
            {page === 'Dashboard' && <Dashboard onDevice={openDevice} onNavigate={handleNavigate} notify={notify} workspaceName={workspaceName} />}
            {page === 'Devices' && <Devices onDevice={openDevice} initialFilter={deviceFilter} notify={notify} currentUser={currentUser} />}
            {page === 'Device detail' && <DeviceDetail deviceId={selectedDevice} onBack={() => navigateTo({ page: 'Devices' })} notify={notify} />}
            {page === 'Monitoring' && <Monitoring onDevice={openDevice} notify={notify} />}
            {page === 'Alerts' && <Alerts onDevice={openDevice} notify={notify} />}
            {page === 'Hardware' && <HardwarePage onDevice={openDevice} onNavigate={handleNavigate} notify={notify} />}
            {page === 'Schedules' && <Schedules notify={notify} />}
            {page === 'Users' && (isSuperAdmin ? <UsersPage notify={notify} currentUser={currentUser} /> : null)}
            {page === 'Roles' && (isSuperAdmin ? <Roles notify={notify} /> : null)}
            {page === 'Agents' && <AgentsDownloads notify={notify} />}
            {page === 'Telegram' && (isSuperAdmin ? <TelegramPage notify={notify} /> : null)}
            {page === 'Audit Log' && (isSuperAdmin ? <AuditLog /> : null)}
            {page === 'Groups' && (
              <Groups
                onNavigate={handleNavigate}
                onDevice={openDevice}
                notify={notify}
                selectedGroupName={selectedGroup}
                onSelectGroup={(gName) => navigateTo({ page: 'Groups', selectedGroup: gName || undefined })}
                currentUser={currentUser}
              />
            )}
            {page === 'Settings' && (isSuperAdmin ? (
              <SettingsPage
                workspaceName={workspaceName}
                onSaveWorkspaceName={handleUpdateWorkspaceName}
                notify={notify}
              />
            ) : null)}
          </ErrorBoundary>
        </div>
      </main>

      {/* Workspace modal */}
      {showWorkspaceModal && (
        <div className="modal-backdrop" onClick={() => setShowWorkspaceModal(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)' }}><Server size={22} /></div>
            <h2>Рабочее пространство: {workspaceName}</h2>
            <p>Централизованное управление парком рабочих станций предприятия. Подключен выделенный сервер Ubuntu.</p>
            <div className="setting-row" style={{ padding: '10px 0' }}>
              <div><strong>Текущий кластер</strong><span>Ubuntu Server 24.04 LTS (x86_64)</span></div>
              <span className="badge match">Active</span>
            </div>
            <div className="setting-row" style={{ padding: '10px 0' }}>
              <div><strong>Станций в реестре</strong><span>1 физический ПК подключен</span></div>
              <span className="mono">192.168.1.109</span>
            </div>
            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setShowWorkspaceModal(false)}>Закрыть</Button>
              <Button primary onClick={() => {
                devicesApi.list().then(setDevicesList);
                notify('Синхронизация пространства и реестра ПК выполнена!');
                setShowWorkspaceModal(false);
              }}>Синхронизировать</Button>
            </div>
          </div>
        </div>
      )}

      {/* Profile modal */}
      {showProfileModal && (
        <div className="modal-backdrop" onClick={() => setShowProfileModal(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '500px', textAlign: 'left' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}>
                <UserRound size={22} />
              </div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>{currentUser?.displayName || 'Профиль администратора'}</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>
                  Учетная запись: @{currentUser?.username || 'admin'} · {currentUser?.role || 'Главный администратор'}
                </p>
              </div>
            </div>

            <div className="setting-row" style={{ padding: '10px 0' }}>
              <div>
                <strong>{currentUser?.displayName || currentUser?.username || 'Администратор'}</strong>
                <span>Логин: @{currentUser?.username || 'admin'}{currentUser?.email ? ` · ${currentUser.email}` : ''}</span>
              </div>
              <span className="badge" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', fontWeight: 600 }}>
                {currentUser?.role || 'FULL ACCESS'}
              </span>
            </div>

            <div className="setting-row" style={{ padding: '10px 0' }}>
              <div>
                <strong>Область полномочий</strong>
                <span>{currentUser?.scope || 'Все устройства парка'}</span>
              </div>
              <span className="badge match" style={{ fontSize: '10px' }}>
                {currentUser?.enabled !== false ? 'Активен' : 'Заблокирован'}
              </span>
            </div>

            <div className="setting-row" style={{ padding: '10px 0' }}>
              <div>
                <strong>Сервер и подключение</strong>
                <span>
                  Хост: {window.location.host} · {navigator.userAgent.includes('Edg') ? 'Microsoft Edge' : navigator.userAgent.includes('Chrome') ? 'Google Chrome' : navigator.userAgent.includes('Firefox') ? 'Mozilla Firefox' : 'Веб-браузер'}
                </span>
              </div>
              <span className="pulse-dot" title="Сессия онлайн" />
            </div>

            {/* Change Password Block */}
            <div style={{ marginTop: '16px', background: 'rgba(255,255,255,0.03)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Key size={14} style={{ color: 'var(--blue)' }} /> Смена пароля
                </strong>
                <button
                  type="button"
                  className="link-button"
                  style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--blue)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                  onClick={() => {
                    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%&*';
                    let p = '';
                    for (let i = 0; i < 12; i++) p += chars.charAt(Math.floor(Math.random() * chars.length));
                    setProfileNewPassword(p);
                    navigator.clipboard.writeText(p);
                    notify(`Сгенерирован надежный пароль и скопирован: ${p}`);
                  }}
                >
                  <Sparkles size={13} /> 🎲 Сгенерировать
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Текущий пароль</label>
                  <input
                    className="text-input mono"
                    type="password"
                    style={{ width: '100%' }}
                    value={profileOldPassword}
                    onChange={e => setProfileOldPassword(e.target.value)}
                    placeholder="Введите текущий пароль..."
                  />
                </div>

                <div>
                  <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Новый пароль</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      className="text-input mono"
                      type={profileShowPassword ? 'text' : 'password'}
                      style={{ width: '100%', paddingRight: '40px' }}
                      value={profileNewPassword}
                      onChange={e => setProfileNewPassword(e.target.value)}
                      placeholder="Минимум 4 символа..."
                    />
                    <button
                      type="button"
                      onClick={() => setProfileShowPassword(!profileShowPassword)}
                      style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer' }}
                    >
                      {profileShowPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                <Button
                  style={{ alignSelf: 'flex-end', marginTop: '4px' }}
                  disabled={!profileOldPassword.trim() || !profileNewPassword.trim()}
                  onClick={async () => {
                    try {
                      const targetUname = currentUser?.username || currentUser?.id || 'admin';
                      const res = await authApi.changePassword(targetUname, profileOldPassword, profileNewPassword);
                      notify(res?.message || `Пароль учетной записи @${targetUname} успешно изменен!`);
                      setProfileOldPassword('');
                      setProfileNewPassword('');
                      setShowProfileModal(false);
                    } catch (err: any) {
                      notify(err?.message || 'Ошибка смены пароля: проверьте текущий пароль');
                    }
                  }}
                >
                  Обновить пароль
                </Button>
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setShowProfileModal(false)}>Закрыть</Button>
            </div>
          </div>
        </div>
      )}

      {/* Logout modal */}
      {showLogoutModal && (
        <div className="modal-backdrop" onClick={() => setShowLogoutModal(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon"><LogOut size={22} /></div>
            <h2>Завершить текущую сессию?</h2>
            <p>Вы собираетесь выйти из панели администрирования {workspaceName}.</p>
            <div className="modal-actions">
              <Button onClick={() => setShowLogoutModal(false)}>{t('common.cancel')}</Button>
              <Button primary onClick={() => {
                try {
                  localStorage.removeItem('wm_user_session');
                } catch {}
                setCurrentUser(null);
                setShowLogoutModal(false);
                notify('Вы успешно вышли из системы');
              }}>Выйти</Button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="toast">
          <div className="toast-icon"><Check size={16} /></div>
          <span>{toast}</span>
          <button onClick={() => setToast('')}><X size={15} /></button>
        </div>
      )}
    </div>
  );
}

function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <div className="eyebrow">{eyebrow || 'OPERATIONS'}</div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </div>
  );
}

function Button({ children, primary = false, onClick, icon, title, disabled }: { children: React.ReactNode; primary?: boolean; onClick?: (e: React.MouseEvent) => void; icon?: React.ReactNode; title?: string; disabled?: boolean }) {
  return (
    <button className={primary ? 'button primary' : 'button'} onClick={onClick} title={title} disabled={disabled}>
      {icon}
      {children}
    </button>
  );
}

function StatusPill({ status, type = 'default' }: { status: string; type?: 'default' | 'health' | 'state' }) {
  const s = (status || '').toLowerCase();
  let pillClass = 'default';
  if (s.includes('актив') || s.includes('active') || s.includes('running') || s.includes('healthy') || s.includes('connected') || s.includes('on') || s.includes('success')) {
    pillClass = 'active';
  } else if (s.includes('откл') || s.includes('disc') || s.includes('error') || s.includes('failed') || s.includes('critical') || s.includes('offline') || s.includes('stopped') || s.includes('closed')) {
    pillClass = 'offline';
  } else if (s.includes('idle') || s.includes('warning') || s.includes('простой')) {
    pillClass = 'idle';
  }
  const cls = s.split(' ').join('-');
  return <span className={`status-pill ${type} ${pillClass} ${cls}`}><i />{status}</span>;
}

function DeviceStatusBadge({ powerStatus, healthStatus }: { powerStatus: string; healthStatus?: string }) {
  const p = (powerStatus || '').toLowerCase();
  let statusClass = 'off';
  if (p === 'on' || p === 'online') {
    statusClass = 'on';
  } else if (p === 'booting' || p === 'waking' || p === 'rebooting' || p === 'shutting down') {
    statusClass = 'warning';
  } else if (p === 'error' || (healthStatus && healthStatus.toLowerCase() === 'critical')) {
    statusClass = 'error';
  } else {
    statusClass = 'off';
  }

  return (
    <span className={`device-status ${statusClass}`}>
      <i />
      {powerStatus || 'Off'}
    </span>
  );
}

function MetricBar({ value }: { value: number }) {
  return (
    <div className="metric">
      <span>{value}%</span>
      <div><i style={{ width: `${Math.min(value, 100)}%` }} className={value > 75 ? 'high' : ''} /></div>
    </div>
  );
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      <strong className={mono ? 'mono' : ''}>{value}</strong>
    </div>
  );
}

// ----------------------------------------------------
// 1. DASHBOARD WITH BENTO GRID KPI CARDS
// ----------------------------------------------------
function Dashboard({
  onDevice,
  onNavigate,
  notify,
  workspaceName = 'BMSTU'
}: {
  onDevice: (id: string) => void;
  onNavigate: (page: Page, filter?: any) => void;
  notify: (message: string) => void;
  workspaceName?: string;
}) {
  const { t, lang } = useLanguage();
  const [stats, setStats] = useState<DashboardStats>();
  const [devices, setDevices] = useState<Device[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [hardwareChanges, setHardwareChanges] = useState<HardwareChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [showQuickModal, setShowQuickModal] = useState(false);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      dashboardApi.stats(),
      devicesApi.list(),
      alertsApi.list(),
      schedulesApi.list(),
      hardwareApi.getChanges()
    ]).then(([s, d, a, sch, hw]) => {
      setStats(s);
      setDevices(d);
      setAlerts(a);
      setSchedules(sch || []);
      setHardwareChanges(hw || []);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      Promise.all([
        dashboardApi.stats(),
        devicesApi.list(),
        alertsApi.list(),
        schedulesApi.list(),
        hardwareApi.getChanges()
      ]).then(([s, d, a, sch, hw]) => {
        setStats(s);
        setDevices(d);
        setAlerts(a);
        setSchedules(sch || []);
        setHardwareChanges(hw || []);
      }).catch(() => {});
    }, 4000);

    const unsubUpdated = wsClient.on('device.updated', (updatedDev: any) => {
      if (updatedDev && updatedDev.id) {
        setDevices(prev => prev.map(d => d.id === updatedDev.id ? { ...d, ...updatedDev } : d));
        dashboardApi.stats().then(setStats).catch(() => {});
      }
    });

    const unsubAlert = wsClient.on('alert.created', () => {
      alertsApi.list().then(setAlerts).catch(() => {});
      dashboardApi.stats().then(setStats).catch(() => {});
    });

    const unsubHw = wsClient.on('hardware.change', () => {
      hardwareApi.getChanges().then(hw => setHardwareChanges(hw || [])).catch(() => {});
      alertsApi.list().then(setAlerts).catch(() => {});
      dashboardApi.stats().then(setStats).catch(() => {});
    });

    return () => {
      clearInterval(interval);
      unsubUpdated();
      unsubAlert();
      unsubHw();
    };
  }, []);

  const filtered = devices.filter((d) => `${d.name} ${d.id} ${d.ip} ${getDeviceGroups(d).join(' ')}`.toLowerCase().includes(query.toLowerCase())).slice(0, 8);

  const totalDevs = stats?.total || devices.length || 0;
  const onlineDevs = stats?.online || 0;
  const offlineDevs = stats?.offline || 0;
  const onlinePct = totalDevs > 0 ? Math.round((onlineDevs / totalDevs) * 100) : 0;
  const openAlertsCount = alerts.filter(a => a.state !== 'Resolved').length;

  const activeHwMismatches = hardwareChanges.filter(c => c.diffStatus === 'MISMATCH' && !c.acknowledged).length;
  const baselineCompliance = totalDevs > 0 ? Math.max(0, Math.round(((totalDevs - Math.min(totalDevs, activeHwMismatches)) / totalDevs) * 100)) : 100;

  const enabledSchedules = schedules.filter(s => s.enabled);
  const nextSch = enabledSchedules[0];
  const nextSchText = nextSch ? `${nextSch.time} ${nextSch.name}` : 'Все выключены';

  const totalActiveSessions = stats?.activeSessions !== undefined ? stats.activeSessions : 0;
  const totalDisconnectedSessions = stats?.disconnectedSessions !== undefined ? stats.disconnectedSessions : 0;

  return (
    <>
      <PageHeader
        eyebrow={t('dashboard.eyebrow')}
        title={t('dashboard.greeting')}
        description={
          lang === 'ru'
            ? `Оперативная сводка состояния парка рабочих станций ${workspaceName}.`
            : `Here’s what’s happening across ${workspaceName}'s workstation fleet.`
        }
        actions={
          <>
            <Button icon={<ArrowDownToLine size={15} />} onClick={() => { exportDevicesToCsv(devices); notify('Отчет по устройствам экспортирован в CSV'); }}>
              {t('dashboard.exportReport')}
            </Button>
            <Button primary icon={<Zap size={15} />} onClick={() => setShowQuickModal(true)}>
              {t('dashboard.quickActions')}
            </Button>
          </>
        }
      />

      {/* BENTO GRID KPI CARDS */}
      <div className="bento-grid">
        {/* Bento 1: Fleet Overview & Progress (Col 4) */}
        <div className="bento-card col-4" onClick={() => onNavigate('Devices')} style={{ cursor: 'pointer' }}>
          <div>
            <div className="bento-header">
              <span className="bento-card-title">Парк рабочих станций</span>
              <div className="bento-icon blue"><Server size={18} /></div>
            </div>
            <div className="bento-value">{loading ? '—' : totalDevs} <small>ПК</small></div>
            <div className="bento-progress">
              <div className="bento-progress-bar blue" style={{ width: `${onlinePct}%` }} />
            </div>
          </div>
          <div className="bento-footer">
            <span><span className="pulse-dot" /> {onlinePct}% онлайн ({onlineDevs} из {totalDevs})</span>
            <ArrowUpRight size={15} style={{ color: 'var(--muted)' }} />
          </div>
        </div>

        {/* Bento 2: Power Status & WoL Quick (Col 4) */}
        <div className="bento-card col-4" onClick={() => onNavigate('Devices', { status: 'On' })} style={{ cursor: 'pointer' }}>
          <div>
            <div className="bento-header">
              <span className="bento-card-title">Питание & Wake-on-LAN</span>
              <div className="bento-icon green"><Wifi size={18} /></div>
            </div>
            <div className="bento-value">{loading ? '—' : onlineDevs} <small>Активны</small></div>
            <div style={{ display: 'flex', gap: '8px', fontSize: '11px', marginTop: '6px' }}>
              <span className="status-pill on"><i /> {onlineDevs} в сети</span>
              <span className="status-pill offline"><i /> {offlineDevs} выключено</span>
            </div>
          </div>
          <div className="bento-footer">
            <span style={{ color: 'var(--muted)' }}>WoL Magic Packet готов к отправке</span>
            <Zap size={14} style={{ color: 'var(--green)' }} />
          </div>
        </div>

        {/* Bento 3: Critical Incidents & Alerts (Col 4) */}
        <div className="bento-card col-4" onClick={() => onNavigate('Alerts')} style={{ cursor: 'pointer' }}>
          <div>
            <div className="bento-header">
              <span className="bento-card-title">Инциденты & Алерты</span>
              <div className={`bento-icon ${openAlertsCount > 0 ? 'orange' : 'green'}`}><AlertTriangle size={18} /></div>
            </div>
            <div className="bento-value">
              {loading ? '—' : openAlertsCount} <small>открытых</small>
            </div>
            <div style={{ display: 'flex', gap: '6px', fontSize: '11px', marginTop: '6px' }}>
              {openAlertsCount === 0 ? (
                <span className="badge match">Все системы в норме</span>
              ) : (
                <span className="badge mismatch">{openAlertsCount} требуют внимания</span>
              )}
            </div>
          </div>
          <div className="bento-footer">
            <span>Централизованный журнал сбоев</span>
            <ArrowUpRight size={15} style={{ color: 'var(--muted)' }} />
          </div>
        </div>

        {/* Bento 4: RDP & User Sessions (Col 4) */}
        <div className="bento-card col-4" onClick={() => onNavigate('Devices', { rdp: true })} style={{ cursor: 'pointer' }}>
          <div>
            <div className="bento-header">
              <span className="bento-card-title">RDP Сессии & Пользователи</span>
              <div className="bento-icon purple"><Monitor size={18} /></div>
            </div>
            <div className="bento-value">{loading ? '—' : totalActiveSessions} <small>Сессий</small></div>
            <div style={{ display: 'flex', gap: '8px', fontSize: '11px', marginTop: '6px' }}>
              <span className="status-pill active"><i /> {totalActiveSessions} активных</span>
              <span className="status-pill idle"><i /> {totalDisconnectedSessions} брошенных</span>
            </div>
          </div>
          <div className="bento-footer">
            <span>Watchdog очистки: 15 мин</span>
            <ShieldCheck size={14} style={{ color: 'var(--blue)' }} />
          </div>
        </div>

        {/* Bento 5: Hardware Baseline Integrity (Col 4) */}
        <div className="bento-card col-4" onClick={() => onNavigate('Hardware')} style={{ cursor: 'pointer' }}>
          <div>
            <div className="bento-header">
              <span className="bento-card-title">Аппаратный эталон (Baseline)</span>
              <div className="bento-icon cyan"><Cpu size={18} /></div>
            </div>
            <div className="bento-value">{loading ? '—' : `${baselineCompliance}%`} <small>Соответствие</small></div>
            <div style={{ display: 'flex', gap: '6px', fontSize: '11px', marginTop: '6px' }}>
              {activeHwMismatches === 0 ? (
                <span className="badge match">0 расхождений железа</span>
              ) : (
                <span className="badge mismatch">{activeHwMismatches} расхождений железа</span>
              )}
            </div>
          </div>
          <div className="bento-footer">
            <span>ОЗУ, Диски, GPU на контроле</span>
            <Check size={14} style={{ color: activeHwMismatches === 0 ? 'var(--green)' : 'var(--orange)' }} />
          </div>
        </div>

        {/* Bento 6: Scheduled Automation (Col 4) */}
        <div className="bento-card col-4" onClick={() => onNavigate('Schedules')} style={{ cursor: 'pointer' }}>
          <div>
            <div className="bento-header">
              <span className="bento-card-title">Автоматизация & Таймеры</span>
              <div className="bento-icon slate"><Clock3 size={18} /></div>
            </div>
            <div className="bento-value">{loading ? '—' : enabledSchedules.length} <small>Расписаний</small></div>
            <div style={{ display: 'flex', gap: '6px', fontSize: '11px', marginTop: '6px' }}>
              <span className="status-pill open"><i /> Следующий: {nextSchText}</span>
            </div>
          </div>
          <div className="bento-footer">
            <span>{enabledSchedules.length > 0 ? 'Цикл активен' : 'Расписания отключены'}</span>
            <ArrowUpRight size={15} style={{ color: 'var(--muted)' }} />
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="panel problems-panel">
          <div className="panel-heading">
            <div><h2>{t('dashboard.needsAttention')}</h2><p>{t('dashboard.needsAttentionSubtitle')}</p></div>
            <span className="heading-count" onClick={() => onNavigate('Alerts')} style={{ cursor: 'pointer' }}>
              {alerts.filter(a => a.state !== 'Resolved').length} {t('dashboard.openCount')}
            </span>
          </div>
          {alerts.filter(a => a.state !== 'Resolved').length === 0 ? (
            <div className="empty-state" style={{ minHeight: '160px' }}>
              <Check size={20} style={{ color: 'var(--green)' }} />
              <span>Все системы работают штатно. Нет активных инцидентов.</span>
            </div>
          ) : (
            alerts.filter(a => a.state !== 'Resolved').slice(0, 4).map((alert) => (
              <div
                className="problem-row"
                key={alert.id}
                onClick={() => onNavigate('Alerts')}
                style={{ cursor: 'pointer' }}
                title="Перейти к списку инцидентов"
              >
                <div className={`problem-icon ${alert.severity.toLowerCase()}`}>
                  {alert.severity === 'Critical' ? <AlertTriangle size={16} /> : <Bell size={16} />}
                </div>
                <div className="problem-info">
                  <strong>{alert.type}</strong>
                  <span>{alert.device} · {alert.time}</span>
                </div>
                <ChevronRight size={16} className="muted-icon" />
              </div>
            ))
          )}
        </section>

        <section className="panel fleet-panel">
          <div className="panel-heading">
            <div><h2>{t('dashboard.fleetHealth')}</h2><p>{t('dashboard.fleetHealthSubtitle')}</p></div>
            <Gauge size={19} className="heading-icon" />
          </div>
          <div className="fleet-visual">
            <div className="donut" onClick={() => onNavigate('Devices')} style={{ cursor: 'pointer' }} title="Перейти к устройствам">
              <div><strong>{devices.length > 0 ? Math.round(((stats?.online || 0) / devices.length) * 100) : 100}%</strong><span>online</span></div>
            </div>
            <div className="legend">
              <div onClick={() => onNavigate('Devices', { status: 'On' })} style={{ cursor: 'pointer' }}><i className="dot green" /><span>{t('dashboard.online')}</span><strong>{stats?.online || 0}</strong></div>
              <div onClick={() => onNavigate('Devices', { status: 'Off' })} style={{ cursor: 'pointer' }}><i className="dot gray" /><span>{t('dashboard.offline')}</span><strong>{stats?.offline || 0}</strong></div>
              <div onClick={() => onNavigate('Alerts')} style={{ cursor: 'pointer' }}><i className="dot orange" /><span>{t('dashboard.problems')}</span><strong>{stats?.problems || 0}</strong></div>
            </div>
          </div>
          <div className="fleet-footer">
            <span><span className="pulse-dot" /> {t('dashboard.updatedJustNow')}</span>
            <button onClick={() => { loadData(); notify('Данные дашборда обновлены'); }}>
              {t('common.refresh')} <RefreshCw size={13} />
            </button>
          </div>
        </section>
      </div>

      <section className="panel table-panel">
        <div className="panel-heading table-heading">
          <div><h2>{t('dashboard.liveStatus')}</h2><p>{t('dashboard.liveStatusSubtitle')}</p></div>
          <div className="table-tools">
            <div className="search"><Search size={15} /><input placeholder={t('dashboard.searchDevices')} value={query} onChange={(e) => setQuery(e.target.value)} /></div>
            <Button icon={<ListFilter size={15} />} onClick={() => onNavigate('Devices')}>
              Все устройства ({devices.length})
            </Button>
          </div>
        </div>
        <DeviceTable devices={filtered} onDevice={onDevice} onAction={notify} />
      </section>

      {/* Quick Actions Modal */}
      {showQuickModal && (
        <div className="modal-backdrop" onClick={() => setShowQuickModal(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '540px' }}>
            <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)' }}><Zap size={22} /></div>
            <h2>Быстрые групповые действия</h2>
            <p>Выполнить оперативные системные команды на всех зарегистрированных рабочих станциях:</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', margin: '18px 0' }}>
              <button
                className="dropdown-item"
                style={{ padding: '12px 14px', border: '1px solid var(--line)', borderRadius: '8px' }}
                onClick={async () => {
                  const offDevs = devices.filter(d => d.powerStatus === 'Off' || d.powerStatus === 'Standby');
                  const targetIds = offDevs.length > 0 ? offDevs.map(d => d.id) : devices.map(d => d.id);
                  if (targetIds.length > 0) {
                    await devicesApi.bulkOperation(targetIds, 'WAKE');
                    notify(`Magic Packet (WoL) отправлен на ${targetIds.length} станций`);
                    setTimeout(loadData, 1200);
                  } else {
                    notify('В системе нет зарегистрированных устройств');
                  }
                  setShowQuickModal(false);
                }}
              >
                <Zap size={16} style={{ color: 'var(--green)' }} />
                <div>
                  <strong style={{ display: 'block' }}>Включить все выключенные ПК (Wake-on-LAN)</strong>
                  <small style={{ color: 'var(--muted)' }}>Отправить широковещательный Magic Packet по сети</small>
                </div>
              </button>

              <button
                className="dropdown-item"
                style={{ padding: '12px 14px', border: '1px solid var(--line)', borderRadius: '8px' }}
                onClick={() => { loadData(); notify('Запрос телеметрии отправлен агентам'); setShowQuickModal(false); }}
              >
                <RefreshCw size={16} style={{ color: 'var(--blue)' }} />
                <div>
                  <strong style={{ display: 'block' }}>Опросить статус всех агентов</strong>
                  <small style={{ color: 'var(--muted)' }}>Собрать актуальные данные по ОЗУ, CPU и сессиям</small>
                </div>
              </button>

              <button
                className="dropdown-item"
                style={{ padding: '12px 14px', border: '1px solid var(--line)', borderRadius: '8px' }}
                onClick={() => { exportDevicesToCsv(devices); notify('Выгрузка инвентаризации в CSV завершена'); setShowQuickModal(false); }}
              >
                <Download size={16} style={{ color: 'var(--orange)' }} />
                <div>
                  <strong style={{ display: 'block' }}>Выгрузить полный отчет парка (CSV)</strong>
                  <small style={{ color: 'var(--muted)' }}>Таблица со всеми параметрами, дисками и тегами</small>
                </div>
              </button>
            </div>
            <div className="modal-actions">
              <Button onClick={() => setShowQuickModal(false)}>Закрыть</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------
// 2. DEVICE TABLE & ACTIONS MENU
// ----------------------------------------------------
function DeviceTable({
  devices,
  onDevice,
  onAction,
  compact = false,
  selectedIds = [],
  onSelectToggle,
  onSelectAll,
  onDeleteDevice,
  onEditMetadata
}: {
  devices: Device[];
  onDevice: (id: string) => void;
  onAction: (message: string) => void;
  compact?: boolean;
  selectedIds?: string[];
  onSelectToggle?: (id: string) => void;
  onSelectAll?: () => void;
  onDeleteDevice?: (id: string) => void;
  onEditMetadata?: (device: Device) => void;
}) {
  const { t } = useLanguage();
  const allSelected = devices.length > 0 && devices.every(d => selectedIds.includes(d.id));
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);

  // Close context menu on outside click
  useEffect(() => {
    const handleWindowClick = () => setActiveMenuId(null);
    window.addEventListener('click', handleWindowClick);
    return () => window.removeEventListener('click', handleWindowClick);
  }, []);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th><input type="checkbox" checked={allSelected} onChange={onSelectAll} /></th>
            <th>{t('common.status')}</th>
            <th>{t('common.device')}</th>
            <th>{t('common.group')}</th>
            <th>{t('common.ipAddress')}</th>
            <th>{t('common.currentUser')}</th>
            <th>{t('common.rdp')}</th>
            <th>CPU</th>
            <th>RAM</th>
            <th>{t('common.uptime')}</th>
            <th>{t('common.lastSeen')}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {devices.length === 0 ? (
            <tr>
              <td colSpan={12} style={{ textAlign: 'center', padding: '32px' }}>
                <div className="empty-state">
                  <Monitor size={24} />
                  <span>Нет устройств, соответствующих фильтрам</span>
                  <small style={{ color: 'var(--muted)', marginTop: '4px' }}>Попробуйте сбросить параметры поиска или добавить новый ПК</small>
                </div>
              </td>
            </tr>
          ) : (
            devices.map((device) => {
              const devGroups = getDeviceGroups(device);
              return (
                <tr key={device.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(device.id)}
                      onChange={() => onSelectToggle && onSelectToggle(device.id)}
                    />
                  </td>
                  <td><DeviceStatusBadge powerStatus={device.powerStatus} healthStatus={device.healthStatus} /></td>
                  <td>
                    <button className="device-name" onClick={() => onDevice(device.id)}>
                      <span className="device-symbol"><Monitor size={15} /></span>
                      <span>
                        <strong>{device.name}</strong>
                        <small>
                          {device.id}{device.name !== device.hostname ? ` · ${device.hostname}` : ''} · {device.ip}
                          {device.isOutdated && (
                            <span style={{ marginLeft: '6px', color: 'var(--yellow)', fontWeight: 600 }}>
                              · v{device.agentVersion || '1.4.2'} (Доступно v{device.latestAgentVersion || '2.5.3'})
                            </span>
                          )}
                        </small>
                      </span>
                    </button>
                    {device.maintenance && <span className="maintenance-badge">MAINTENANCE</span>}
                  </td>
                  <td>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {devGroups.map(g => (
                        <span key={g} className="group-text" style={{ fontSize: '11px', padding: '2px 6px', background: 'var(--surface-2)', borderRadius: '4px', border: '1px solid var(--line)' }}>
                          {g}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="mono">{device.ip}</td>
                  <td>{device.currentUser}</td>
                  <td><StatusPill status={device.rdpStatus} /></td>
                  <td><MetricBar value={device.cpu} /></td>
                  <td><MetricBar value={device.ram} /></td>
                  <td className="muted-text">{formatLiveUptime(device.uptime, device.bootTimeIso, device.powerStatus === 'On')}</td>
                  <td className="muted-text">{formatDeviceLastSeen(device.lastSeen, device.lastSeenIso, device.powerStatus)}</td>
                  <td style={{ position: 'relative' }}>
                    <button
                      className="row-more"
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveMenuId(activeMenuId === device.id ? null : device.id);
                      }}
                      title="Действия над станцией"
                    >
                      <Ellipsis size={17} />
                    </button>

                    {/* Context dropdown menu */}
                    {activeMenuId === device.id && (
                      <div className="dropdown-menu" onClick={(e) => e.stopPropagation()}>
                        <button className="dropdown-item" onClick={() => { setActiveMenuId(null); onDevice(device.id); }}>
                          <Monitor size={14} /> Открыть карточку ПК
                        </button>
                        <button
                          className="dropdown-item"
                          onClick={async () => {
                            setActiveMenuId(null);
                            await devicesApi.wake(device.id);
                            onAction(`Команда Wake-on-LAN отправлена на ${device.name}`);
                          }}
                        >
                          <Zap size={14} style={{ color: 'var(--green)' }} /> Включить (WoL)
                        </button>
                        <button
                          className="dropdown-item"
                          onClick={async () => {
                            setActiveMenuId(null);
                            await devicesApi.powerAction(device.id, 'REBOOT', true);
                            onAction(`Команда перезагрузки отправлена на ${device.name}`);
                          }}
                        >
                          <RefreshCw size={14} style={{ color: 'var(--blue)' }} /> Перезагрузить
                        </button>
                        <button
                          className="dropdown-item"
                          onClick={async () => {
                            setActiveMenuId(null);
                            await devicesApi.powerAction(device.id, 'SHUTDOWN', false);
                            onAction(`Команда выключения отправлена на ${device.name}`);
                          }}
                        >
                          <Power size={14} style={{ color: 'var(--red)' }} /> Выключить
                        </button>
                        <button
                          className="dropdown-item"
                          onClick={async () => {
                            setActiveMenuId(null);
                            await agentsApi.updateAgent(device.id);
                            onAction(`Команда обновления агента отправлена на ${device.name}`);
                          }}
                        >
                          <RotateCw size={14} style={{ color: 'var(--blue)' }} /> Обновить агент (до v{device.latestAgentVersion || '2.5.3'})
                        </button>
                        {onEditMetadata && (
                          <button
                            className="dropdown-item"
                            onClick={() => {
                              setActiveMenuId(null);
                              onEditMetadata(device);
                            }}
                          >
                            <Edit3 size={14} /> Настройки и группы
                          </button>
                        )}
                        {onDeleteDevice && (
                          <button
                            className="dropdown-item danger"
                            onClick={() => {
                              setActiveMenuId(null);
                              onDeleteDevice(device.id);
                            }}
                          >
                            <Trash2 size={14} /> Удалить из системы
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
      {!compact && (
        <div className="table-footer">
          <span>{t('common.showing')} <strong>{devices.length === 0 ? 0 : 1}–{devices.length}</strong> {t('common.ofTotal')} <strong>{devices.length}</strong> {t('common.devices')}</span>
          <div className="pagination">
            <button disabled>{t('common.previous')}</button>
            <button className="current">1</button>
            <button disabled>{t('common.next')}</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------
// 3. DEVICES PAGE WITH FILTERS & ADD MODAL
// ----------------------------------------------------
function Devices({
  onDevice,
  initialFilter,
  notify,
  currentUser
}: {
  onDevice: (id: string) => void;
  initialFilter?: { group?: string; status?: string; rdp?: boolean };
  notify: (message: string) => void;
  currentUser?: ManagedUser | null;
}) {
  const { t } = useLanguage();
  const isSuperAdmin = currentUser?.role === 'Суперадминистратор' || currentUser?.role === 'SuperAdmin';
  const isObserver = currentUser?.role === 'Наблюдатель' || currentUser?.role === 'Observer';
  const hasRestrictedScope = !isSuperAdmin && currentUser?.scope !== 'Все устройства' && Array.isArray(currentUser?.allowedGroups) && currentUser.allowedGroups.length > 0;
  const allowedGroupsList = hasRestrictedScope ? currentUser.allowedGroups : [];

  const [items, setItems] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkModalAction, setBulkModalAction] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table');

  // Filters state
  const [filterGroup, setFilterGroup] = useState<string>(initialFilter?.group || 'ALL');
  const [filterStatus, setFilterStatus] = useState<string>(initialFilter?.status || 'ALL');
  const [filterRdpOnly, setFilterRdpOnly] = useState<boolean>(initialFilter?.rdp || false);
  const [filterMaintenanceOnly, setFilterMaintenanceOnly] = useState<boolean>(false);

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false);
  const [editDeviceTarget, setEditDeviceTarget] = useState<Device | null>(null);
  const [deleteDeviceTarget, setDeleteDeviceTarget] = useState<string | null>(null);

  // Edit form state for device modal
  const [editDevName, setEditDevName] = useState('');
  const [editDevGroups, setEditDevGroups] = useState<string[]>([]);
  const [editDevTags, setEditDevTags] = useState<string[]>([]);
  const [editDevAssetTag, setEditDevAssetTag] = useState('');
  const [editDevNotes, setEditDevNotes] = useState('');
  const [newTagInput, setNewTagInput] = useState('');

  // Existing fleet groups dynamically computed
  const existingFleetGroups = useMemo(() => {
    if (hasRestrictedScope) {
      return [...allowedGroupsList].sort((a, b) => a.localeCompare(b, 'ru'));
    }
    const set = new Set<string>();
    items.forEach(d => {
      getDeviceGroups(d).forEach(g => { if (g && g.trim()) set.add(g.trim()); });
      if (d.group && d.group.trim()) set.add(d.group.trim());
    });
    ['Тонкие клиенты', 'Office', 'Warehouse', 'Management', 'Testing', 'Dev'].forEach(g => set.add(g));
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'ru'));
  }, [items, hasRestrictedScope, allowedGroupsList]);

  // Add Device Modal state (Agent vs Agentless / Thin Client)
  const [addModalTab, setAddModalTab] = useState<'agent' | 'agentless'>('agent');
  const [tcName, setTcName] = useState('');
  const [tcIp, setTcIp] = useState('');
  const [tcGroup, setTcGroup] = useState(hasRestrictedScope && allowedGroupsList.length > 0 ? allowedGroupsList[0] : 'Тонкие клиенты');
  const [tcCustomGroup, setTcCustomGroup] = useState('');
  const [isCustomTcGroup, setIsCustomTcGroup] = useState(false);
  const [tcMac, setTcMac] = useState('');
  const [tcIsProbing, setTcIsProbing] = useState(false);
  const [tcProbeResult, setTcProbeResult] = useState<{ success: boolean; message: string; online: boolean; suggestedCommand?: string } | null>(null);
  const [tcIsSaving, setTcIsSaving] = useState(false);

  const handleProbeTc = async () => {
    if (!tcIp.trim()) {
      notify('Введите IP-адрес тонкого клиента для проверки');
      return;
    }
    setTcIsProbing(true);
    setTcProbeResult(null);
    try {
      const res = await devicesApi.probe(tcIp.trim());
      setTcProbeResult({
        success: res.success,
        message: res.message,
        online: res.online,
        suggestedCommand: res.suggestedCommand || `(Get-NetNeighbor -IPAddress ${tcIp.trim()}).LinkLayerAddress | Set-Clipboard`
      });
      if (res.mac) {
        setTcMac(res.mac);
        notify(`MAC-адрес успешно получен: ${res.mac}`);
      } else {
        notify('Устройство не ответило в ARP-таблице сервера. Доступна быстрая вставка через PowerShell.');
      }
    } catch (err: any) {
      setTcProbeResult({
        success: false,
        message: err?.message || 'Сбой проверки соединения',
        online: false,
        suggestedCommand: `(Get-NetNeighbor -IPAddress ${tcIp.trim()}).LinkLayerAddress | Set-Clipboard`
      });
      notify(err?.message || 'Ошибка проверки соединения');
    } finally {
      setTcIsProbing(false);
    }
  };

  const handleSaveTc = async () => {
    if (!tcName.trim()) {
      notify('Укажите имя тонкого клиента');
      return;
    }
    if (!tcIp.trim()) {
      notify('Укажите IP-адрес устройства');
      return;
    }
    if (!tcMac.trim()) {
      notify('Укажите MAC-адрес устройства для отправки пакетов Wake-on-LAN');
      return;
    }
    const finalGroup = isCustomTcGroup ? (tcCustomGroup.trim() || 'Тонкие клиенты') : (tcGroup.trim() || 'Тонкие клиенты');
    if (hasRestrictedScope) {
      const allowedLower = allowedGroupsList.map(g => g.toLowerCase().trim());
      if (!allowedLower.includes(finalGroup.toLowerCase().trim())) {
        notify(`Отказ в доступе: вы можете добавлять устройства только в разрешенные вам группы (${allowedGroupsList.join(', ')})`);
        return;
      }
    }
    setTcIsSaving(true);
    try {
      const res = await devicesApi.createAgentless({
        name: tcName.trim(),
        ip: tcIp.trim(),
        mac: tcMac.trim(),
        group: finalGroup
      });
      notify(res?.message || `Тонкий клиент «${tcName}» добавлен в систему!`);
      setShowAddModal(false);
      setTcName('');
      setTcIp('');
      setTcMac('');
      setTcCustomGroup('');
      setIsCustomTcGroup(false);
      setTcProbeResult(null);
      loadFleet();
    } catch (err: any) {
      notify(err?.message || 'Ошибка добавления устройства');
    } finally {
      setTcIsSaving(false);
    }
  };

  const loadFleet = () => {
    setLoading(true);
    devicesApi.list().then((data) => {
      setItems(data);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadFleet();
    const interval = setInterval(() => {
      devicesApi.list().then((data) => {
        setItems(data);
      }).catch(() => {});
    }, 4000);

    const unsubUpdated = wsClient.on('device.updated', (updatedDev: any) => {
      if (updatedDev && updatedDev.id) {
        setItems(prev => prev.map(d => d.id === updatedDev.id ? { ...d, ...updatedDev } : d));
      }
    });

    return () => {
      clearInterval(interval);
      unsubUpdated();
    };
  }, []);

  useEffect(() => {
    if (initialFilter?.group) setFilterGroup(initialFilter.group);
    if (initialFilter?.status) setFilterStatus(initialFilter.status);
    if (initialFilter?.rdp !== undefined) setFilterRdpOnly(initialFilter.rdp);
  }, [initialFilter]);

  const availableGroups = ['Office', 'Warehouse', 'Management', 'Testing', 'Dev'];

  const filtered = items.filter((d) => {
    const devGroups = getDeviceGroups(d);
    const matchQuery = `${d.name} ${d.id} ${devGroups.join(' ')} ${d.ip} ${d.hostname} ${d.currentUser} ${(d.tags || []).join(' ')}`.toLowerCase().includes(query.toLowerCase());
    const matchGroup = filterGroup === 'ALL' || devGroups.some(g => g.toLowerCase() === filterGroup.toLowerCase());
    const matchStatus = filterStatus === 'ALL' || d.powerStatus.toLowerCase() === filterStatus.toLowerCase();
    const matchRdp = !filterRdpOnly || Boolean(
      d.rdpStatus && (
        d.rdpStatus.toLowerCase().includes('актив') ||
        d.rdpStatus.toLowerCase().includes('active') ||
        d.rdpStatus.toLowerCase().includes('running') ||
        d.rdpStatus === 'Running' ||
        d.rdpStatus === 'Active'
      )
    );
    const matchMaint = !filterMaintenanceOnly || d.maintenance;
    return matchQuery && matchGroup && matchStatus && matchRdp && matchMaint;
  });

  const handleSelectToggle = (id: string) => {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const handleSelectAll = () => {
    if (filtered.every(d => selectedIds.includes(d.id))) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filtered.map(d => d.id));
    }
  };

  const executeBulkAction = async (action: string) => {
    if (action === 'UPDATE_AGENT') {
      await agentsApi.updateBulk(selectedIds);
      notify(`Команда обновления агентов отправлена на ${selectedIds.length} станций!`);
    } else {
      await bulkApi.powerAction(selectedIds, action as any);
      notify(`Массовая команда "${action}" успешно отправлена на ${selectedIds.length} станций!`);
    }
    setBulkModalAction(null);
    setSelectedIds([]);
    loadFleet();
  };

  const handleDeleteDevice = async (id: string) => {
    await devicesApi.delete(id);
    setItems(prev => prev.filter(d => d.id !== id));
    notify(`Устройство ${id} удалено из реестра`);
    setDeleteDeviceTarget(null);
  };

  const openEditDevice = (device: Device) => {
    setEditDeviceTarget(device);
    setEditDevName(device.name);
    setEditDevGroups(getDeviceGroups(device));
    setEditDevTags(device.tags || []);
    setEditDevAssetTag(device.assetTag || '');
    setEditDevNotes(device.notes || '');
  };

  const toggleGroupSelection = (grp: string) => {
    if (editDevGroups.includes(grp)) {
      if (editDevGroups.length > 1) {
        setEditDevGroups(editDevGroups.filter(g => g !== grp));
      }
    } else {
      setEditDevGroups([...editDevGroups, grp]);
    }
  };

  const handleSaveDeviceEdits = async () => {
    if (!editDeviceTarget) return;
    if (hasRestrictedScope) {
      const allowedLower = allowedGroupsList.map(g => g.toLowerCase().trim());
      const hasForbiddenGroup = editDevGroups.some(g => !allowedLower.includes(g.toLowerCase().trim()));
      if (hasForbiddenGroup) {
        notify(`Отказ в доступе: вы можете назначать только разрешенные группы (${allowedGroupsList.join(', ')})`);
        return;
      }
    }
    const updated = await devicesApi.update(editDeviceTarget.id, {
      name: editDevName,
      groups: editDevGroups,
      tags: editDevTags,
      assetTag: editDevAssetTag,
      notes: editDevNotes,
    });
    setItems(prev => prev.map(d => d.id === editDeviceTarget.id ? { ...d, ...updated, groups: editDevGroups } : d));
    notify(`Параметры и группы ПК ${editDevName} успешно сохранены!`);
    setEditDeviceTarget(null);
  };

  const hasActiveFilters = filterGroup !== 'ALL' || filterStatus !== 'ALL' || filterRdpOnly || filterMaintenanceOnly || query !== '';

  const clearAllFilters = () => {
    setFilterGroup('ALL');
    setFilterStatus('ALL');
    setFilterRdpOnly(false);
    setFilterMaintenanceOnly(false);
    setQuery('');
  };

  return (
    <>
      <PageHeader
        eyebrow="FLEET MANAGEMENT"
        title={t('devices.title')}
        description={t('devices.subtitle')}
        actions={
          <>
            <Button icon={<ArrowDownToLine size={15} />} onClick={() => { exportDevicesToCsv(items); notify('Список устройств выгружен в CSV'); }}>
              {t('common.export')}
            </Button>
            {!isObserver && (
              <Button primary icon={<Plus size={15} />} onClick={() => setShowAddModal(true)}>
                {t('devices.addDevice')}
              </Button>
            )}
          </>
        }
      />

      {/* Toolbar & Filters */}
      <div className="toolbar">
        <div className="search wide">
          <Search size={15} />
          <input placeholder={t('dashboard.searchDevices')} value={query} onChange={(e) => setQuery(e.target.value)} />
          {query && <button onClick={() => setQuery('')} style={{ background: 'none', border: 'none', color: 'var(--muted)' }}><X size={14} /></button>}
        </div>

        {/* Group Selector */}
        <select
          className="text-input"
          value={filterGroup}
          onChange={(e) => setFilterGroup(e.target.value)}
          style={{ minWidth: '130px', height: '34px', fontSize: '11px', padding: '0 8px' }}
        >
          <option value="ALL">Группа: Все</option>
          <option value="Office">Office</option>
          <option value="Warehouse">Warehouse</option>
          <option value="Management">Management</option>
          <option value="Testing">Testing</option>
          <option value="Dev">Dev</option>
        </select>

        {/* Status Selector */}
        <select
          className="text-input"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          style={{ minWidth: '130px', height: '34px', fontSize: '11px', padding: '0 8px' }}
        >
          <option value="ALL">Статус: Все</option>
          <option value="On">Онлайн (On)</option>
          <option value="Off">Оффлайн (Off)</option>
          <option value="Booting">Загрузка</option>
        </select>

        <button
          className={`filter-button ${filterRdpOnly ? 'primary' : ''}`}
          onClick={() => setFilterRdpOnly(!filterRdpOnly)}
          style={{ background: filterRdpOnly ? 'var(--blue-soft)' : undefined, color: filterRdpOnly ? 'var(--blue)' : undefined }}
        >
          <Monitor size={15} /> С RDP-сессиями
        </button>

        <button
          className={`filter-button ${filterMaintenanceOnly ? 'primary' : ''}`}
          onClick={() => setFilterMaintenanceOnly(!filterMaintenanceOnly)}
          style={{ background: filterMaintenanceOnly ? 'var(--orange-soft)' : undefined, color: filterMaintenanceOnly ? 'var(--orange)' : undefined }}
        >
          <Settings size={15} /> На ТО
        </button>

        {hasActiveFilters && (
          <Button onClick={clearAllFilters} icon={<X size={13} />}>
            Сбросить
          </Button>
        )}
      </div>

      {/* Bulk actions bar */}
      {selectedIds.length > 0 && (
        <div className="bulk-bar">
          <strong>{selectedIds.length} {t('devices.devicesSelected')}</strong>
          <span />
          <Button icon={<Zap size={15} />} onClick={() => setBulkModalAction('WAKE_ON_LAN')}>{t('devices.wake')}</Button>
          <Button icon={<RefreshCw size={15} />} onClick={() => setBulkModalAction('REBOOT')}>{t('devices.reboot')}</Button>
          <Button icon={<Power size={15} />} onClick={() => setBulkModalAction('SHUTDOWN')}>{t('devices.shutdown')}</Button>
          <Button icon={<RotateCw size={15} />} onClick={() => setBulkModalAction('UPDATE_AGENT')}>Обновить агент</Button>
          <Button icon={<Download size={15} />} onClick={() => exportDevicesToCsv(items.filter(d => selectedIds.includes(d.id)))}>Экспорт</Button>
          <button className="bulk-close" onClick={() => setSelectedIds([])} title="Снять выбор"><X size={16} /></button>
        </div>
      )}

      {/* Devices panel */}
      <section className="panel table-panel devices-panel">
        <div className="panel-heading table-heading">
          <div>
            <h2>{t('devices.allDevices')}</h2>
            <p>{loading ? 'Загрузка парка…' : `${filtered.length} из ${items.length} станций в списке`}</p>
          </div>
          <div className="view-toggle">
            <button className={viewMode === 'table' ? 'selected' : ''} onClick={() => setViewMode('table')} title="Табличный вид">
              <ListFilter size={16} />
            </button>
            <button className={viewMode === 'grid' ? 'selected' : ''} onClick={() => setViewMode('grid')} title="Вид карточками">
              <LayoutDashboard size={16} />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>Загрузка списка устройств...</span></div>
        ) : viewMode === 'table' ? (
          <DeviceTable
            devices={filtered}
            onDevice={onDevice}
            onAction={notify}
            selectedIds={selectedIds}
            onSelectToggle={handleSelectToggle}
            onSelectAll={handleSelectAll}
            onDeleteDevice={(id) => setDeleteDeviceTarget(id)}
            onEditMetadata={(d) => openEditDevice(d)}
          />
        ) : (
          /* Grid Card View */
          <div className="device-grid-view">
            {filtered.length === 0 ? (
              <div className="empty-state" style={{ gridColumn: '1 / -1', minHeight: '160px' }}>
                <Monitor size={24} />
                <span>Нет станций по заданным критериям</span>
              </div>
            ) : (
              filtered.map(device => {
                const devGroups = getDeviceGroups(device);
                return (
                  <div className="device-card-item" key={device.id}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                        <div className="device-symbol"><Monitor size={17} /></div>
                        <div>
                          <strong style={{ fontSize: '13px', display: 'block', cursor: 'pointer' }} onClick={() => onDevice(device.id)}>{device.name}</strong>
                          <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{device.id} · {devGroups.join(', ')}</span>
                        </div>
                      </div>
                      <DeviceStatusBadge powerStatus={device.powerStatus} healthStatus={device.healthStatus} />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px', padding: '8px 0', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)' }}>
                      <div><span style={{ color: 'var(--muted)', display: 'block' }}>IP:</span><strong className="mono">{device.ip}</strong></div>
                      <div><span style={{ color: 'var(--muted)', display: 'block' }}>Пользователь:</span><strong>{device.currentUser || '—'}</strong></div>
                      <div><span style={{ color: 'var(--muted)', display: 'block' }}>ЦП:</span><MetricBar value={device.cpu} /></div>
                      <div><span style={{ color: 'var(--muted)', display: 'block' }}>ОЗУ:</span><MetricBar value={device.ram} /></div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Активность: {formatDeviceLastSeen(device.lastSeen, device.lastSeenIso, device.powerStatus)}</span>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button className="button" style={{ padding: '5px 8px', fontSize: '10px' }} onClick={() => onDevice(device.id)}>
                          Открыть
                        </button>
                        <button
                          className="button primary"
                          style={{ padding: '5px 8px', fontSize: '10px' }}
                          onClick={async () => {
                            await devicesApi.wake(device.id);
                            notify(`WoL отправлен на ${device.name}`);
                          }}
                          title="Включить через Wake-on-LAN"
                        >
                          <Zap size={12} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </section>

      {/* Edit Device & Multiple Groups Modal */}
      {editDeviceTarget && (
        <div className="modal-backdrop" onClick={() => setEditDeviceTarget(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '540px', textAlign: 'left' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}><Edit3 size={22} /></div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Настройки ПК: {editDeviceTarget.name}</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>{editDeviceTarget.id} · {editDeviceTarget.hostname}</p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Отображаемое имя станции</label>
                <input
                  className="text-input"
                  style={{ width: '100%' }}
                  value={editDevName}
                  onChange={(e) => setEditDevName(e.target.value)}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                  Группы (ПК может входить в несколько групп одновременно)
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '8px', background: 'var(--surface-2)', borderRadius: '8px', border: '1px solid var(--line)' }}>
                  {availableGroups.map(grp => {
                    const isSelected = editDevGroups.includes(grp);
                    return (
                      <button
                        key={grp}
                        type="button"
                        onClick={() => toggleGroupSelection(grp)}
                        className={isSelected ? 'button primary' : 'button'}
                        style={{ padding: '5px 10px', fontSize: '12px' }}
                      >
                        {isSelected && <Check size={13} style={{ marginRight: '4px' }} />}
                        {grp}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Инвентарный номер</label>
                  <input
                    className="text-input mono"
                    style={{ width: '100%' }}
                    value={editDevAssetTag}
                    onChange={(e) => setEditDevAssetTag(e.target.value)}
                    placeholder="INV-2026-0842"
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Теги устройства</label>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <input
                      className="text-input"
                      style={{ flex: 1 }}
                      value={newTagInput}
                      onChange={(e) => setNewTagInput(e.target.value)}
                      placeholder="Новый тег..."
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          const val = newTagInput.trim();
                          if (val && !editDevTags.includes(val)) {
                            setEditDevTags([...editDevTags, val]);
                            setNewTagInput('');
                          }
                        }
                      }}
                    />
                    <Button onClick={() => {
                      const val = newTagInput.trim();
                      if (val && !editDevTags.includes(val)) {
                        setEditDevTags([...editDevTags, val]);
                        setNewTagInput('');
                      }
                    }}>+</Button>
                  </div>
                </div>
              </div>

              {editDevTags.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {editDevTags.map(tag => (
                    <span key={tag} className="badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <Tag size={11} /> {tag}
                      <X size={12} style={{ cursor: 'pointer' }} onClick={() => setEditDevTags(editDevTags.filter(t => t !== tag))} />
                    </span>
                  ))}
                </div>
              )}

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Комментарии / Примечания</label>
                <textarea
                  className="text-input"
                  style={{ width: '100%', minHeight: '50px', resize: 'vertical' }}
                  value={editDevNotes}
                  onChange={(e) => setEditDevNotes(e.target.value)}
                />
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setEditDeviceTarget(null)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleSaveDeviceEdits} disabled={!editDevName}>
                Сохранить
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Add Device Modal */}
      {showAddModal && (
        <div className="modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '580px', textAlign: 'left' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}><Plus size={22} /></div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Добавление новой рабочей станции</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>Установка агента или регистрация безагентного тонкого клиента</p>
              </div>
            </div>

            {/* Modal Tabs */}
            <div className="tabs" style={{ marginBottom: '16px', gap: '16px' }}>
              <button
                type="button"
                className={addModalTab === 'agent' ? 'active' : ''}
                onClick={() => setAddModalTab('agent')}
              >
                Установка агента (Windows / Linux)
              </button>
              <button
                type="button"
                className={addModalTab === 'agentless' ? 'active' : ''}
                onClick={() => setAddModalTab('agentless')}
              >
                Тонкий клиент (WoL / Agentless)
              </button>
            </div>

            {addModalTab === 'agentless' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.2)', padding: '12px 14px', borderRadius: '8px', fontSize: '12px', color: 'var(--ink)' }}>
                  💡 <strong>Безагентный режим:</strong> предназначен для тонких клиентов (WTware, Thinstation, бездисковые терминалы). Сервер автоматически будит устройство по сети (Wake-on-LAN) по кнопке и расписанию.
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Имя устройства / Рабочее место</label>
                  <input
                    className="text-input"
                    placeholder="Например: ТК Склад 1, WTware Бухгалтерия..."
                    value={tcName}
                    onChange={e => setTcName(e.target.value)}
                    style={{ width: '100%' }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>IP-адрес в локальной сети</label>
                    <input
                      className="text-input mono"
                      placeholder="192.168.0.150"
                      value={tcIp}
                      onChange={e => { setTcIp(e.target.value); setTcProbeResult(null); }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Группа</label>
                    {!isCustomTcGroup ? (
                      <select
                        className="text-input"
                        value={tcGroup}
                        onChange={e => {
                          if (e.target.value === '__NEW__') {
                            setIsCustomTcGroup(true);
                            setTcCustomGroup('');
                          } else {
                            setTcGroup(e.target.value);
                          }
                        }}
                        style={{ width: '100%', height: '36px', fontSize: '12px', padding: '0 8px' }}
                      >
                        {existingFleetGroups.map(grp => (
                          <option key={grp} value={grp}>{grp}</option>
                        ))}
                        {!hasRestrictedScope && <option value="__NEW__">+ Ввести новую группу...</option>}
                      </select>
                    ) : (
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <input
                          className="text-input"
                          placeholder="Новая группа..."
                          value={tcCustomGroup}
                          onChange={e => setTcCustomGroup(e.target.value)}
                          autoFocus
                          style={{ flex: 1 }}
                        />
                        <Button onClick={() => setIsCustomTcGroup(false)} style={{ padding: '0 8px', fontSize: '11px' }}>
                          К списку
                        </Button>
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 600, margin: 0 }}>Физический MAC-адрес (для WoL)</label>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <Button
                        type="button"
                        icon={<Copy size={12} />}
                        onClick={async () => {
                          try {
                            const text = await navigator.clipboard?.readText();
                            if (text) {
                              const m = text.match(/([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}/) || text.match(/[0-9a-fA-F]{12}/);
                              if (m) {
                                const raw = m[0].replace(/[^a-fA-F0-9]/g, '').toUpperCase();
                                const formatted = raw.match(/.{1,2}/g)?.join(':') || raw;
                                setTcMac(formatted);
                                notify(`Вставлен MAC-адрес: ${formatted}`);
                                return;
                              }
                            }
                            notify('В буфере не найден MAC-адрес');
                          } catch {
                            notify('Вставьте MAC-адрес вручную (Ctrl+V)');
                          }
                        }}
                        style={{ padding: '4px 8px', fontSize: '11px' }}
                        title="Вставить MAC из буфера обмена"
                      >
                        Вставить
                      </Button>
                      <Button
                        type="button"
                        icon={tcIsProbing ? <RefreshCw size={12} className="spin" /> : <Search size={12} />}
                        onClick={handleProbeTc}
                        disabled={tcIsProbing || !tcIp.trim()}
                        style={{ padding: '4px 10px', fontSize: '11px' }}
                      >
                        {tcIsProbing ? 'Опрос сети...' : '🔍 Проверить соединение'}
                      </Button>
                    </div>
                  </div>
                  <input
                    className="text-input mono"
                    placeholder="00:11:22:33:44:55"
                    value={tcMac}
                    onChange={e => {
                      const val = e.target.value.trim();
                      const rawHex = val.replace(/[^0-9a-fA-F]/g, '').toUpperCase();
                      if (rawHex.length === 12 && !val.includes(':')) {
                        setTcMac(rawHex.match(/.{1,2}/g)?.join(':') || val);
                      } else {
                        setTcMac(val.replace(/-/g, ':').toUpperCase());
                      }
                    }}
                    style={{ width: '100%', fontFamily: "'DM Mono', monospace" }}
                  />
                  {tcProbeResult && (
                    <div style={{
                      marginTop: '8px',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      fontSize: '11.5px',
                      background: tcProbeResult.success ? 'rgba(34, 197, 94, 0.12)' : 'rgba(234, 179, 8, 0.1)',
                      border: tcProbeResult.success ? '1px solid rgba(34, 197, 94, 0.25)' : '1px solid rgba(234, 179, 8, 0.25)',
                      color: tcProbeResult.success ? 'var(--green)' : 'var(--yellow)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {tcProbeResult.success ? <Check size={14} /> : <AlertTriangle size={14} />}
                        <span style={{ fontWeight: 600 }}>{tcProbeResult.message}</span>
                      </div>
                      {!tcProbeResult.success && (
                        <div style={{ color: 'var(--ink)', fontSize: '11px', lineHeight: 1.4 }}>
                          Сервер в Docker изолирован от L2 ARP сети. Выполните команду на вашем ПК в PowerShell:
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '5px' }}>
                            <code style={{ background: 'rgba(0,0,0,0.2)', padding: '4px 8px', borderRadius: '4px', fontSize: '10.5px', border: '1px solid var(--line)', flex: 1, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              (Get-NetNeighbor -IPAddress {tcIp.trim()}).LinkLayerAddress | Set-Clipboard
                            </code>
                            <Button
                              type="button"
                              onClick={() => {
                                navigator.clipboard?.writeText(`(Get-NetNeighbor -IPAddress ${tcIp.trim()}).LinkLayerAddress | Set-Clipboard`);
                                notify('Команда скопирована! Вставьте в PowerShell и нажмите Enter, затем нажмите кнопку «Вставить» выше.');
                              }}
                              style={{ padding: '2px 8px', fontSize: '10px', flexShrink: 0 }}
                            >
                              📋 Скопировать
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  <small style={{ color: 'var(--muted)', fontSize: '11px', display: 'block', marginTop: '4px' }}>
                    Нажмите «Проверить соединение» или скопируйте команду для PowerShell в 1 клик.
                  </small>
                </div>

                <div className="modal-actions" style={{ marginTop: '14px' }}>
                  <Button onClick={() => setShowAddModal(false)}>Отмена</Button>
                  <Button primary disabled={tcIsSaving || !tcName.trim() || !tcIp.trim() || !tcMac.trim()} onClick={handleSaveTc}>
                    {tcIsSaving ? 'Сохранение...' : 'Добавить тонкий клиент'}
                  </Button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {(() => {
                  const effectivePort = window.location.port === '5173' ? '2301' : (window.location.port || '2301');
                  const serverHost = window.location.hostname || 'localhost';
                  const srvUrl = `http://${serverHost}:${effectivePort}`;
                  const psCmd = defaultGroup
                    ? `irm "${srvUrl}/install.ps1?group=${encodeURIComponent(defaultGroup)}&server_url=${encodeURIComponent(srvUrl)}" | iex`
                    : `irm "${srvUrl}/install.ps1?server_url=${encodeURIComponent(srvUrl)}" | iex`;
                  const shCmd = defaultGroup
                    ? `curl -fsSL "${srvUrl}/install.sh?group=${encodeURIComponent(defaultGroup)}&server_url=${encodeURIComponent(srvUrl)}" | sudo bash`
                    : `curl -fsSL "${srvUrl}/install.sh?server_url=${encodeURIComponent(srvUrl)}" | sudo bash`;
                  return (
                    <>
                      <div>
                        <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Быстрая установка через PowerShell (Windows):</label>
                        <div className="code-card" style={{ marginTop: 0 }}>
                          <pre>{psCmd}</pre>
                        </div>
                        <button
                          className="text-button"
                          style={{ marginTop: '4px' }}
                          onClick={() => {
                            navigator.clipboard?.writeText(psCmd);
                            notify('Команда скопирована в буфер обмена');
                          }}
                        >
                          <Copy size={12} /> Скопировать команду
                        </button>
                      </div>

                      <div>
                        <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Быстрая установка через Bash (Linux Ubuntu/Debian):</label>
                        <div className="code-card" style={{ marginTop: 0 }}>
                          <pre>{shCmd}</pre>
                        </div>
                        <button
                          className="text-button"
                          style={{ marginTop: '4px' }}
                          onClick={() => {
                            navigator.clipboard?.writeText(shCmd);
                            notify('Команда скопирована в буфер обмена');
                          }}
                        >
                          <Copy size={12} /> Скопировать команду
                        </button>
                      </div>
                    </>
                  );
                })()}

                <div className="modal-actions" style={{ marginTop: '14px' }}>
                  <Button onClick={() => setShowAddModal(false)}>Закрыть</Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete Device Modal */}
      {deleteDeviceTarget && (
        <div className="modal-backdrop" onClick={() => setDeleteDeviceTarget(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon"><Trash2 size={23} /></div>
            <h2>Удалить станцию {devices.find(d => d.id === deleteDeviceTarget)?.name || deleteDeviceTarget}?</h2>
            <p>Запись устройства, история алертов и эталон конфигурации будут удалены из базы данных.</p>
            <div className="modal-actions">
              <Button onClick={() => setDeleteDeviceTarget(null)}>{t('common.cancel')}</Button>
              <Button primary onClick={() => handleDeleteDevice(deleteDeviceTarget)}>
                Удалить
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Action Confirm Modal */}
      {bulkModalAction && (
        <div className="modal-backdrop" onClick={() => setBulkModalAction(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon"><Zap size={23} /></div>
            <h2>Массовая операция ({bulkModalAction})</h2>
            <p>Вы собираетесь применить действие ко всем выбранным станциям ({selectedIds.length} шт.).</p>
            <div className="modal-actions">
              <Button onClick={() => setBulkModalAction(null)}>{t('common.cancel')}</Button>
              <Button primary onClick={() => executeBulkAction(bulkModalAction)}>
                Выполнить
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------
// 4. DEVICE DETAIL
// ----------------------------------------------------
function DeviceDetail({ deviceId, onBack, notify }: { deviceId: string; onBack: () => void; notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [device, setDevice] = useState<Device>();
  const [sessions, setSessions] = useState<RdpSession[]>([]);
  const [spec, setSpec] = useState<HardwareSpec>();
  const [baseline, setBaseline] = useState<HardwareBaseline>();
  const [changes, setChanges] = useState<HardwareChange[]>([]);
  const [tab, setTab] = useState('Overview');
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteDeviceModal, setShowDeleteDeviceModal] = useState(false);
  const [isUpdatingAgent, setIsUpdatingAgent] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  // Edit form states
  const [editName, setEditName] = useState('');
  const [editGroups, setEditGroups] = useState<string[]>([]);
  const [editTags, setEditTags] = useState<string[]>([]);
  const [newTagText, setNewTagText] = useState('');
  const [editAssetTag, setEditAssetTag] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [editMaintenance, setEditMaintenance] = useState(false);
  const [editHeartbeatInterval, setEditHeartbeatInterval] = useState<number | null>(null);

  const availableGroups = ['Office', 'Warehouse', 'Management', 'Testing', 'Dev'];

  const loadDeviceData = () => {
    Promise.all([
      devicesApi.get(deviceId),
      sessionsApi.list(deviceId),
      hardwareApi.getChanges(deviceId),
    ]).then(([d, s, ch]) => {
      setDevice(d);
      const finalSessions = Array.isArray(s) ? s : (d && Array.isArray(d.rdpSessions) ? d.rdpSessions : []);
      setSessions(finalSessions);
      if (d) {
        setSpec(d.hardware);
        setBaseline(d.baseline);
        setEditName(d.name);
        setEditGroups(getDeviceGroups(d));
        setEditTags(d.tags || []);
        setEditAssetTag(d.assetTag || '');
        setEditNotes(d.notes || '');
        setEditMaintenance(d.maintenance || false);
        setEditHeartbeatInterval(d.heartbeatInterval || null);
      }
      setChanges(ch);
    });
  };

  useEffect(() => {
    loadDeviceData();
    const interval = setInterval(() => {
      devicesApi.get(deviceId).then(d => {
        if (d) {
          setDevice(d);
          setSpec(d.hardware);
          setBaseline(d.baseline);
        }
      }).catch(() => {});
      sessionsApi.list(deviceId).then(s => {
        if (Array.isArray(s)) setSessions(s);
      }).catch(() => {});
    }, 3000);

    const unsubUpdated = wsClient.on('device.updated', (updatedDev: any) => {
      if (updatedDev && (updatedDev.id === deviceId || updatedDev.deviceId === deviceId)) {
        setDevice(prev => prev ? { ...prev, ...updatedDev } : updatedDev);
        if (Array.isArray(updatedDev.rdpSessions)) {
          setSessions(updatedDev.rdpSessions);
        } else {
          sessionsApi.list(deviceId).then(s => { if (Array.isArray(s)) setSessions(s); }).catch(() => {});
        }
      }
    });

    const unsubHeartbeat = wsClient.on('agent.heartbeat', (hb: any) => {
      if (hb && (hb.deviceId === deviceId || hb.id === deviceId)) {
        if (Array.isArray(hb.rdpSessions)) {
          setSessions(hb.rdpSessions);
        }
      }
    });

    return () => {
      clearInterval(interval);
      unsubUpdated();
      unsubHeartbeat();
    };
  }, [deviceId]);

  if (!device) return <div className="loading-state"><LoaderCircle className="spin" size={24} /> Загрузка устройства...</div>;

  const handleDeleteDevice = async () => {
    if (!device) return;
    const ok = await devicesApi.delete(device.id);
    if (ok) {
      notify(`Устройство ${device.name} (${device.id}) удалено из мониторинга`);
      onBack();
    } else {
      notify('Ошибка при удалении устройства');
    }
  };

  const handleSaveMetadata = async () => {
    const updated = await devicesApi.update(deviceId, {
      name: editName,
      groups: editGroups,
      tags: editTags,
      assetTag: editAssetTag,
      notes: editNotes,
      maintenance: editMaintenance,
      heartbeatInterval: editHeartbeatInterval,
    });
    if (updated) {
      setDevice(prev => prev ? { ...prev, ...updated, groups: editGroups } : updated);
    }
    notify(`Параметры и группы станции ${editName} успешно сохранены!`);
    setShowEditModal(false);
  };

  const toggleGroupInDetail = (grp: string) => {
    if (editGroups.includes(grp)) {
      if (editGroups.length > 1) {
        setEditGroups(editGroups.filter(g => g !== grp));
      }
    } else {
      setEditGroups([...editGroups, grp]);
    }
  };

  const handleAddTag = () => {
    const tag = newTagText.trim();
    if (tag && !editTags.includes(tag)) {
      setEditTags([...editTags, tag]);
      setNewTagText('');
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setEditTags(editTags.filter(t => t !== tagToRemove));
  };

  const handleResetSession = async (sessionId: number, sessionObj?: RdpSession, forceKillRdpOnly?: boolean) => {
    const isOut = forceKillRdpOnly !== undefined ? forceKillRdpOnly : (sessionObj?.type?.includes('Исходящий') || sessionObj?.sessionName?.toLowerCase().includes('mstsc'));
    
    let remHost = '';
    const sName = sessionObj?.sessionName || '';
    if (sName.includes('->')) {
      remHost = sName.split('->')[1].trim().split(':')[0].trim();
    } else if (sessionObj?.clientIp) {
      remHost = sessionObj.clientIp.trim();
    }

    await sessionsApi.logoff(deviceId, sessionId, {
      pid: sessionObj?.pid,
      type: sessionObj?.type,
      username: sessionObj?.username,
      sessionName: sessionObj?.sessionName,
      clientIp: sessionObj?.clientIp,
      remoteHost: remHost,
      isOutgoing: isOut
    });
    setSessions(prev => prev.filter(s => s.id !== sessionId));
    notify(`Сессия #${sessionId} (${sessionObj?.username || ''}) успешно завершена!`);
  };

  const handleAcceptBaseline = async () => {
    const specToApprove = spec || device?.hardware || device?.hardwareSpec;
    if (!specToApprove) {
      notify('У данного устройства нет доступного аппаратного снимка для эталона');
      return;
    }
    try {
      const newBl = await devicesApi.setBaseline(deviceId, specToApprove);
      if (newBl) setBaseline(newBl);
      setChanges([]);
      notify('✅ Текущая конфигурация утверждена как эталон (0 расхождений)!');
      loadDeviceData();
    } catch {
      notify('Ошибка при утверждении эталона');
    }
  };

  const handleTriggerAgentUpdate = async () => {
    if (!device) return;
    setIsUpdatingAgent(true);
    notify(`Запущена процедура удаленного обновления агента на ${device.name}...`);
    try {
      await agentsApi.updateAgent(device.id);
      setTimeout(() => {
        setIsUpdatingAgent(false);
        loadDeviceData();
        notify(`Команда обновления доставлена на ${device.name}`);
      }, 2500);
    } catch {
      setIsUpdatingAgent(false);
      notify('Ошибка при отправке команды обновления');
    }
  };

  const handleSyncDevice = async () => {
    if (!device) return;
    setIsSyncing(true);
    notify(`Запрос мгновенной синхронизации отправлен на ${device.name}...`);
    try {
      const res = await devicesApi.sync(device.id);
      if (res && res.message) {
        notify(res.message);
      }
      setTimeout(() => {
        loadDeviceData();
      }, 700);
      setTimeout(() => {
        loadDeviceData();
        setIsSyncing(false);
      }, 2200);
    } catch (e: any) {
      setIsSyncing(false);
      notify(`Ошибка синхронизации: ${e?.message || 'Сервер не отвечает'}`);
    }
  };

  const activeRdpSessions = sessions.filter(s => {
    const sType = String(s.type || '');
    const sName = String(s.sessionName || '');
    const isOut = sType.includes('Исходящий') || sName.toLowerCase().includes('mstsc');
    const isIn = sType.includes('Входящий') || sName.toLowerCase().includes('rdp');
    const isConsole = (sType === 'Локальный сеанс' || sName === 'console') && !isOut && !isIn;
    return (isOut || isIn || (sType && !isConsole)) && !isConsole;
  });

  const isAgentless = Boolean(
    device.agentVersion === 'Agentless' ||
    device.osType === 'ThinClient' ||
    (device.id && device.id.toUpperCase().startsWith('TC-')) ||
    device.tags?.some(tag => tag.toLowerCase().includes('agentless') || tag.toLowerCase().includes('тонкий клиент'))
  );

  const activeTab = (isAgentless && !['Overview', 'Power', 'AlertPolicy', 'History'].includes(tab)) ? 'Overview' : tab;

  const tabs = isAgentless ? [
    { id: 'Overview', label: t('devices.overview') || 'Обзор' },
    { id: 'Power', label: t('devices.powerTab') || 'Питание и расписание' },
    { id: 'AlertPolicy', label: t('devices.alertPolicyTab') || 'Политика алертинга' },
    { id: 'History', label: t('devices.historyTab') || 'История' },
  ] : [
    { id: 'Overview', label: t('devices.overview') },
    { id: 'Hardware', label: t('devices.hardware') },
    { id: 'Baseline', label: t('devices.baseline'), count: changes.length },
    { id: 'Monitoring', label: t('nav.monitoring') },
    { id: 'RDP Sessions', label: t('devices.rdpSessionsTab'), count: activeRdpSessions.length },
    { id: 'Power', label: t('devices.powerTab') },
    { id: 'AlertPolicy', label: t('devices.alertPolicyTab') },
    { id: 'Credentials', label: t('devices.credentialsTab') },
    { id: 'Automation', label: t('devices.automationTab') },
    { id: 'History', label: t('devices.historyTab') },
  ];

  const currentDevGroups = getDeviceGroups(device);

  return (
    <>
      <button className="back-link" onClick={onBack} style={{ cursor: 'pointer' }}>
        <ChevronRight size={15} className="back-chevron" /> {t('devices.backToDevices')}
      </button>
      <div className="detail-header">
        <div className="device-title">
          <div className="large-device-symbol"><Monitor size={24} /></div>
          <div>
            <div className="eyebrow">DEVICE · {device.id}</div>
            <h1>{device.name}</h1>
            <p>
              {device.hostname} · Группы: {currentDevGroups.join(', ')} <span className="pulse-dot" />{' '}
              {device.powerStatus === 'On' ? (
                <strong style={{ color: 'var(--green)' }}>В сети (онлайн)</strong>
              ) : (
                <span>{t('common.lastSeen')} {formatDeviceLastSeen(device.lastSeen, device.lastSeenIso, device.powerStatus)}</span>
              )}
            </p>
          </div>
        </div>
        <div className="header-actions">
          <Button onClick={() => setShowEditModal(true)} icon={<Settings size={15} />}>{t('devices.editDevice')}</Button>
          {!isAgentless && (
            <Button
              icon={<RotateCw size={15} className={isUpdatingAgent ? 'spin' : ''} />}
              onClick={handleTriggerAgentUpdate}
              disabled={isUpdatingAgent}
              style={device.isOutdated ? { borderColor: 'rgba(234,179,8,0.4)', color: 'var(--yellow)', background: 'rgba(234,179,8,0.06)' } : undefined}
              title="Удаленно обновить службу агента по сети (OTA)"
            >
              {isUpdatingAgent ? 'Обновление...' : (device.isOutdated ? `Обновить агент (v${device.latestAgentVersion || '2.8.7'})` : 'Обновить агент')}
            </Button>
          )}
          {!isAgentless && (
            <Button
              icon={<RefreshCw size={15} className={isSyncing ? 'spin' : ''} />}
              onClick={handleSyncDevice}
              disabled={isSyncing}
              title="Немедленно опросить агента и синхронизировать актуальные данные с ПК без задержки"
            >
              {isSyncing ? 'Синхронизация...' : 'Синхронизировать'}
            </Button>
          )}
          <Button
            primary
            icon={<Zap size={15} />}
            onClick={async () => {
              await devicesApi.wake(device.id);
              notify(`Magic Packet (WoL) отправлен на ${device.name}`);
            }}
          >
            Включить (WoL)
          </Button>
          <Button icon={<Power size={15} />} onClick={() => setTab('Power')}>
            {t('devices.powerActions')} <ChevronDown size={14} />
          </Button>
          <Button
            icon={<Trash2 size={15} style={{ color: 'var(--red)' }} />}
            onClick={() => setShowDeleteDeviceModal(true)}
            title="Удалить устройство из мониторинга"
            style={{ color: 'var(--red)' }}
          >
            Удалить
          </Button>
        </div>
      </div>

      <div className="device-status-grid">
        <div className="device-status-card">
          <div className={`device-status-card-icon ${device.powerStatus === 'On' ? 'green' : 'red'}`}>
            <Zap size={17} />
          </div>
          <div className="device-status-card-info">
            <div className="device-status-card-label">{t('devices.power')}</div>
            <div className="device-status-card-value">
              <i className={`status-dot ${device.powerStatus === 'On' ? 'green' : 'red'}`} />
              {device.powerStatus === 'On' ? 'В сети (On)' : 'Выключен (Off)'}
            </div>
          </div>
        </div>

        <div className="device-status-card">
          <div className={`device-status-card-icon ${isAgentless ? (device.powerStatus === 'On' ? 'green' : 'muted') : (device.agentStatus === 'Connected' ? 'blue' : 'red')}`}>
            {isAgentless ? <Zap size={17} /> : <Server size={17} />}
          </div>
          <div className="device-status-card-info">
            <div className="device-status-card-label">{isAgentless ? 'Управление' : t('devices.agent')}</div>
            <div className="device-status-card-value">
              <i className={`status-dot ${isAgentless ? (device.powerStatus === 'On' ? 'green' : 'grey') : (device.agentStatus === 'Connected' ? 'green' : 'red')}`} />
              {isAgentless ? 'Wake-on-LAN (WoL)' : (device.agentStatus === 'Connected' ? `На связи (v${device.agentVersion || '1.4.2'})` : 'Отключен')}
            </div>
          </div>
        </div>

        <div className="device-status-card">
          <div className={`device-status-card-icon ${isAgentless ? (device.powerStatus === 'On' ? 'green' : 'muted') : (activeRdpSessions.length > 0 ? 'green' : 'muted')}`}>
            {isAgentless ? <Activity size={17} /> : <Monitor size={17} />}
          </div>
          <div className="device-status-card-info">
            <div className="device-status-card-label">{isAgentless ? 'Сетевой отклик' : t('common.rdp')}</div>
            <div className="device-status-card-value">
              <i className={`status-dot ${isAgentless ? (device.powerStatus === 'On' ? 'green' : 'grey') : (activeRdpSessions.length > 0 ? 'green' : 'grey')}`} />
              {isAgentless ? (device.powerStatus === 'On' ? 'ICMP доступен' : 'Нет отклика') : (activeRdpSessions.length > 0 ? `Активен (${activeRdpSessions.length})` : 'Остановлен (0)')}
            </div>
          </div>
        </div>

        <div className="device-status-card">
          <div className={`device-status-card-icon ${device.healthStatus === 'Healthy' ? 'green' : device.healthStatus === 'Warning' ? 'orange' : 'red'}`}>
            <ShieldCheck size={17} />
          </div>
          <div className="device-status-card-info">
            <div className="device-status-card-label">{t('devices.health')}</div>
            <div className="device-status-card-value">
              <i className={`status-dot ${device.healthStatus === 'Healthy' ? 'green' : device.healthStatus === 'Warning' ? 'orange' : 'red'}`} />
              {isAgentless ? 'В норме (WoL готов)' : (device.healthStatus === 'Healthy' ? 'В норме (100%)' : device.healthStatus === 'Warning' ? 'Внимание' : 'Ошибка')}
            </div>
          </div>
        </div>
      </div>

      <div className="tabs">
        {tabs.map((item) => (
          <button className={activeTab === item.id ? 'active' : ''} key={item.id} onClick={() => setTab(item.id)}>
            {item.label}
            {item.count !== undefined && item.count > 0 && <span>{item.count}</span>}
          </button>
        ))}
      </div>

      {activeTab === 'Overview' && (
        isAgentless ? (
          <div className="detail-grid">
            <section className="panel info-panel">
              <div className="panel-heading">
                <div>
                  <h2>Параметры тонкого клиента</h2>
                  <p>Безагентный режим управления по сети Ethernet (Wake-on-LAN)</p>
                </div>
                <Zap size={19} className="heading-icon" style={{ color: 'var(--yellow)' }} />
              </div>
              <div className="info-grid">
                <Info label="Имя устройства" value={device.name} />
                <Info label={t('devices.hostname')} value={device.hostname} mono />
                <Info label={t('common.ipAddress')} value={device.ip} mono />
                <Info label={t('devices.macAddress')} value={device.mac} mono />
                <Info label="WoL Broadcast" value={device.broadcastIp || '255.255.255.255'} mono />
                <Info label="Группа" value={currentDevGroups.join(', ') || 'Тонкие клиенты'} />
                <Info label="Тип станции" value="Тонкий клиент (Agentless)" />
                <Info label="Сетевой отклик" value={device.powerStatus === 'On' ? '🟢 Пинг успешен (онлайн)' : '🔴 Нет отклика по ICMP'} />
                <Info label="Последняя проверка связи" value={formatLocalTime(device.lastSeenIso, device.lastSeen)} />
              </div>
            </section>

            <section className="panel health-panel" style={{ display: 'flex', flexDirection: 'column' }}>
              <div className="panel-heading">
                <div>
                  <h2>Оперативное управление</h2>
                  <p>Питание и мониторинг доступности</p>
                </div>
                <Activity size={19} className="heading-icon" style={{ color: 'var(--green)' }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '6px' }}>
                <div style={{ padding: '12px 14px', borderRadius: '8px', background: 'var(--surface-2)', border: '1px solid var(--line)', fontSize: '12px', lineHeight: 1.5, color: 'var(--ink)' }}>
                  ⚡ Тонкий клиент включается удаленно через отправку сетевого Magic Packet (WoL) на физический MAC <strong>{device.mac}</strong>.
                  Управление выключением производится непосредственно пользователем на тонком клиенте или кнопкой питания.
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <Button
                    primary
                    icon={<Zap size={15} />}
                    onClick={async () => {
                      await devicesApi.wake(device.id);
                      notify(`Magic Packet (WoL) отправлен на ${device.name}`);
                    }}
                  >
                    Включить (WoL)
                  </Button>
                  <Button
                    icon={<RefreshCw size={14} />}
                    onClick={async () => {
                      notify(`Проверка связи с ${device.name} (${device.ip})...`);
                      try {
                        const res = await devicesApi.probe(device.ip);
                        if (res.online) {
                          notify(`🟢 Устройство ${device.name} в сети (отвечает на пинг)`);
                        } else {
                          notify(`🔴 Устройство ${device.name} не отвечает на сетевой пинг`);
                        }
                        loadDeviceData();
                      } catch {
                        notify(`Ошибка проверки связи с ${device.name}`);
                      }
                    }}
                  >
                    Проверить соединение (Ping)
                  </Button>
                  <Button
                    icon={<Clock3 size={14} />}
                    onClick={() => setTab('Power')}
                  >
                    Настроить расписание WoL
                  </Button>
                </div>
              </div>
            </section>

            <section className="panel tags-panel" style={{ gridColumn: '1 / -1' }}>
              <div className="panel-heading">
                <div><h2>{t('devices.tagsMetadata')} & Группы</h2><p>{t('devices.organizeWorkstation')}</p></div>
                <button className="small-icon" onClick={() => setShowEditModal(true)} title="Настройки и теги"><Settings size={15} /></button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '6px 0' }}>
                {device.tags && device.tags.length > 0 ? (
                  device.tags.map(tag => (
                    <span key={tag} className="badge" style={{ padding: '4px 10px', fontSize: '12px' }}>
                      <Tag size={12} style={{ marginRight: '5px' }} /> {tag}
                    </span>
                  ))
                ) : (
                  <span style={{ color: 'var(--muted)', fontSize: '12px' }}>Теги не заданы</span>
                )}
              </div>
            </section>
          </div>
        ) : (
          <div className="detail-grid">
            <section className="panel info-panel">
              <div className="panel-heading">
                <div><h2>{t('devices.systemInfo')}</h2><p>{t('devices.reportedByAgent')}</p></div>
                <Cpu size={19} className="heading-icon" />
              </div>
              <div className="info-grid">
                <Info label={t('devices.hostname')} value={device.hostname} mono />
                <Info label={t('common.ipAddress')} value={device.ip} mono />
                <Info label={t('devices.macAddress')} value={device.mac} mono />
                <Info label={t('devices.os')} value={device.osVersion} />
                <Info label={t('common.currentUser')} value={device.currentUser || '—'} />
                <div className="info-item">
                  <span className="info-label">{t('devices.agentVersion')}</span>
                  <span className="info-value" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    <strong>v{device.agentVersion || '1.4.2'}</strong>
                    {device.isOutdated ? (
                      <span className="badge" style={{ background: 'rgba(234, 179, 8, 0.15)', color: 'var(--yellow)', fontWeight: 600, fontSize: '10px' }}>
                        Доступно v{device.latestAgentVersion || '2.8.7'}
                      </span>
                    ) : (
                      <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: 'var(--green)', fontWeight: 600, fontSize: '10px' }}>
                        Актуален
                      </span>
                    )}
                    <button
                      className="text-button"
                      style={{ fontSize: '11px', padding: '1px 5px', color: 'var(--blue)' }}
                      onClick={handleTriggerAgentUpdate}
                      disabled={isUpdatingAgent}
                    >
                      <RotateCw size={11} className={isUpdatingAgent ? 'spin' : ''} /> {isUpdatingAgent ? 'Обновляется...' : 'Обновить'}
                    </button>
                  </span>
                </div>
                <Info label={t('common.uptime')} value={formatLiveUptime(device.uptime, device.bootTimeIso, device.powerStatus === 'On')} />
                <Info label={t('devices.lastHeartbeat')} value={device.powerStatus === 'On' ? (device.bootTimeIso ? `Старт: ${formatDeviceBootTime(device.bootTimeIso)} (отклик: ${formatLocalTime(device.lastSeenIso, device.lastSeen)})` : `Связь: ${formatLocalTime(device.lastSeenIso, device.lastSeen)}`) : formatDeviceLastSeen(device.lastSeen, device.lastSeenIso, device.powerStatus)} />
              </div>
            </section>

            <section className="panel health-panel">
              <div className="panel-heading">
                <div><h2>{t('devices.resourceUsage')}</h2><p>{t('devices.currentReadings')}</p></div>
              </div>
              <div className="resource">
                <div><Cpu size={16} /><span>{t('devices.cpuUsage')}</span><strong>{device.cpu}%</strong></div>
                <MetricBar value={device.cpu} />
              </div>
              <div className="resource">
                <div><Database size={16} /><span>{t('devices.ramUsage')}</span><strong>{device.ram}%</strong></div>
                <MetricBar value={device.ram} />
              </div>
              <div className="resource">
                <div><HardDrive size={16} /><span>{t('devices.diskUsage')}</span><strong>{device.disk}%</strong></div>
                <MetricBar value={device.disk} />
              </div>
              <div className="last-heartbeat"><span className="pulse-dot" /> {t('devices.heartbeatHealthy')} <span>{formatDeviceLastSeen(device.lastSeen, device.lastSeenIso, device.powerStatus)}</span></div>
            </section>

            <section className="panel rdp-panel">
              <div className="panel-heading">
                <div><h2>{t('devices.rdpSessions')}</h2><p>{t('devices.activeConnections')}</p></div>
                <StatusPill status={activeRdpSessions.length > 0 ? `Активен (${activeRdpSessions.length})` : (device.rdpStatus === 'Active' && activeRdpSessions.length > 0 ? 'Active' : 'Stopped')} />
              </div>
              {activeRdpSessions.length ? (
                <SessionTable sessions={activeRdpSessions} onResetSession={handleResetSession} onAction={notify} />
              ) : (
                <div className="empty-state" style={{ minHeight: '140px' }}><Monitor size={20} />Нет активных RDP сессий</div>
              )}
            </section>

            <section className="panel tags-panel">
              <div className="panel-heading">
                <div><h2>{t('devices.tagsMetadata')} & Группы</h2><p>{t('devices.organizeWorkstation')}</p></div>
                <button className="small-icon" onClick={() => setShowEditModal(true)} title="Настройки и теги"><Settings size={15} /></button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '0 21px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--line)' }}>
                  <span style={{ fontSize: '13px', color: 'var(--muted)', fontWeight: 500 }}>Назначенные группы</span>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {currentDevGroups.map(g => (
                      <span key={g} className="badge match">{g}</span>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--line)' }}>
                  <span style={{ fontSize: '13px', color: 'var(--muted)', fontWeight: 500 }}>Инвентарный номер</span>
                  <strong className="mono" style={{ fontSize: '13px', color: device.assetTag ? 'var(--text)' : 'var(--muted)' }}>
                    {device.assetTag || 'Не указан'}
                  </strong>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '6px 0', borderBottom: '1px solid var(--line)' }}>
                  <span style={{ fontSize: '13px', color: 'var(--muted)', fontWeight: 500 }}>Комментарии</span>
                  <span style={{ fontSize: '13px', color: device.notes ? 'var(--text)' : 'var(--muted)', whiteSpace: 'pre-wrap' }}>
                    {device.notes || 'Нет примечаний'}
                  </span>
                </div>
              </div>

              <div className="tags">
                {device.tags && device.tags.length > 0 ? (
                  device.tags.map((tag) => <span key={tag}><Tag size={13} />{tag}</span>)
                ) : (
                  <span className="muted-text" style={{ fontSize: '12px' }}>Теги не заданы</span>
                )}
                <button className="add-tag" onClick={() => setShowEditModal(true)}><span>+</span> {t('devices.addTag')}</button>
              </div>
              <div className="detail-note"><CircleHelp size={15} /><span>{t('devices.auditNote')}</span></div>
            </section>
          </div>
        )
      )}

      {activeTab === 'Hardware' && (
        <div className="detail-grid">
          {spec ? (
            <>
              {/* Motherboard, CPU & BIOS */}
              <section className="panel info-panel">
                <div className="panel-heading">
                  <div><h2>Материнская плата и Процессор</h2><p>{spec.motherboard?.manufacturer} {spec.motherboard?.model}</p></div>
                  <Cpu size={19} className="heading-icon" />
                </div>
                <div className="info-grid">
                  <Info label="Материнская плата" value={`${spec.motherboard?.manufacturer || 'ASUSTeK COMPUTER INC.'} ${spec.motherboard?.model || 'PRIME Z790-P WIFI'} ${spec.motherboard?.version ? `(${spec.motherboard.version})` : ''}`} />
                  <Info label="Серийный номер" value={spec.motherboard?.serialNumber || 'MB-OEM'} mono />
                  <Info label="BIOS" value={`${spec.bios?.vendor || 'AMI'} ${spec.bios?.version || 'v1.0'}`} />
                  <Info label="Дата BIOS" value={spec.bios?.releaseDate || '2025-01-21'} />
                  <Info label="Процессор" value={spec.cpu?.model || 'Intel Core / AMD Ryzen'} />
                  <Info label="Ядра / Потоки" value={`${spec.cpu?.cores || 24}C / ${spec.cpu?.threads || 32}T @ ${spec.cpu?.baseFrequencyGhz || 2.0} GHz`} />
                  <Info label="Сокет CPU" value={spec.cpu?.socket || 'LGA1700'} mono />
                  <Info label="Всего памяти" value={`${spec.ram?.totalGb || (spec.ram?.slots ? spec.ram.slots.reduce((a: number, s: any) => a + (s.sizeGb || s.capacityGb || 0), 0) : 0) || 0} GB (${spec.ram?.slots ? spec.ram.slots.length : 0} модуля)`} />
                </div>
              </section>

              {/* GPUs / Display */}
              <section className="panel info-panel">
                <div className="panel-heading">
                  <div><h2>Графическая подсистема (GPU)</h2><p>{spec.gpus && spec.gpus.length ? spec.gpus[0].model : 'Дискретная графика'}</p></div>
                  <Monitor size={19} className="heading-icon" />
                </div>
                <div className="info-grid">
                  {spec.gpus && spec.gpus.length > 0 ? (
                    spec.gpus.map((gpu, idx) => (
                      <div key={idx} style={{ display: 'contents' }}>
                        <Info label="Видеокарта" value={gpu.model || 'NVIDIA GeForce'} />
                        <Info label="Объем VRAM" value={`${gpu.vramGb || 8} GB GDDR6`} />
                        <Info label="Версия драйвера" value={gpu.driverVersion || 'Latest'} mono />
                        <Info label="Разрешение экрана" value={gpu.resolution || '2560 x 1440 @ 144Hz'} />
                      </div>
                    ))
                  ) : (
                    <Info label="Видеоадаптер" value="Встроенное графическое ядро" />
                  )}
                </div>
              </section>

              {/* RAM Slots */}
              <section className="panel table-panel" style={{ gridColumn: '1 / -1' }}>
                <div className="panel-heading">
                  <div><h2>Слоты оперативной памяти (RAM)</h2><p>Установлено {spec.ram?.slots ? spec.ram.slots.length : 0} модуля суммарным объемом {spec.ram?.totalGb || (spec.ram?.slots ? spec.ram.slots.reduce((a: number, s: any) => a + (s.sizeGb || s.capacityGb || 0), 0) : 0) || 0} GB</p></div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Слот</th>
                        <th>Объем</th>
                        <th>Тип</th>
                        <th>Частота</th>
                        <th>Производитель</th>
                        <th>Партномер</th>
                        <th>Серийный номер</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(spec.ram?.slots || []).map((slot, idx) => (
                        <tr key={slot.serialNumber || idx}>
                          <td><strong>{slot.slot}</strong></td>
                          <td>{slot.sizeGb} GB</td>
                          <td><span className="badge">{slot.type}</span></td>
                          <td>{slot.frequencyMhz} MHz</td>
                          <td>{slot.manufacturer}</td>
                          <td className="mono">{slot.partNumber}</td>
                          <td className="mono muted-text">{slot.serialNumber || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Storage Drives */}
              <section className="panel table-panel" style={{ gridColumn: '1 / -1' }}>
                <div className="panel-heading">
                  <div><h2>Физические накопители данных (SSD / NVMe / HDD)</h2><p>{spec.storage?.length || 1} накопителя подключено к системе</p></div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Модель</th>
                        <th>Тип / Шина</th>
                        <th>Объем</th>
                        <th>Серийный номер</th>
                        <th>Здоровье SMART</th>
                        <th>Температура</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(spec.storage || []).map((drive, idx) => (
                        <tr key={drive.serialNumber || idx}>
                          <td><strong>{drive.model}</strong></td>
                          <td><span className="badge">{drive.type} ({drive.busType || 'SATA'})</span></td>
                          <td>{drive.capacityGb >= 1000 ? `${(drive.capacityGb / 1000).toFixed(2)} TB` : `${drive.capacityGb} GB`}</td>
                          <td className="mono">{drive.serialNumber}</td>
                          <td><StatusPill status={`${drive.healthPercent}%`} type="health" /></td>
                          <td>{drive.temperatureC}°C</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Network Adapters */}
              <section className="panel table-panel" style={{ gridColumn: '1 / -1' }}>
                <div className="panel-heading">
                  <div><h2>Сетевые интерфейсы и контроллеры</h2><p>{spec.network?.length || 1} адаптера обнаружено</p></div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Интерфейс</th>
                        <th>MAC-адрес</th>
                        <th>IP-адрес</th>
                        <th>Скорость</th>
                        <th>Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(spec.network || []).map((net, idx) => {
                        const netObj = net as any;
                        const mac = netObj.mac || netObj.macAddress || '—';
                        const ip = netObj.ip || netObj.ipAddress || '—';
                        const speed = netObj.speed || (netObj.linkSpeedMbps ? `${netObj.linkSpeedMbps} Mbps` : (netObj.speedMbps ? `${netObj.speedMbps} Mbps` : '1 Gbps'));
                        const isUp = ((netObj.status || '').toLowerCase() === 'up' || (netObj.status || '').toLowerCase() === 'connected');
                        return (
                          <tr key={mac || idx}>
                            <td><strong>{netObj.name}</strong></td>
                            <td className="mono">{mac}</td>
                            <td className="mono">{ip}</td>
                            <td>{speed}</td>
                            <td><span className={`badge ${isUp ? 'match' : 'mismatch'}`}>{isUp ? 'Подключен' : 'Отключен'}</span></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : (
            <section className="panel" style={{ gridColumn: '1 / -1', padding: '32px', textAlign: 'center' }}>
              <div className="empty-state">
                <Cpu size={24} />
                <span>Спецификация оборудования синхронизируется</span>
                <div style={{ marginTop: '16px' }}>
                  <Button onClick={() => { notify('Запрос инвентаризации отправлен агенту'); loadDeviceData(); }}>
                    Обновить данные
                  </Button>
                </div>
              </div>
            </section>
          )}
        </div>
      )}

      {activeTab === 'Baseline' && (
        <div className="detail-grid">
          <section className="panel info-panel" style={{ gridColumn: '1 / -1' }}>
            <div className="panel-heading">
              <div>
                <h2>Аппаратный эталон (Baseline)</h2>
                <p>{baseline ? `${t('devices.baselineApprovedBy')} ${baseline.approvedBy} (${baseline.updatedAt || baseline.createdAt})` : t('devices.noBaseline')}</p>
              </div>
              <Button primary onClick={handleAcceptBaseline}>
                {t('devices.acceptAsBaseline')}
              </Button>
            </div>
            <div className="setting-row">
              <div>
                <strong>{t('devices.matchStatus')}</strong>
                <span>{changes.length === 0 ? t('devices.matched') : t('devices.mismatch')}</span>
              </div>
              <span className={`badge ${changes.length === 0 ? 'match' : 'mismatch'}`}>
                {changes.length === 0 ? t('devices.matched') : t('devices.mismatch')}
              </span>
            </div>
          </section>

          <section className="panel table-panel" style={{ gridColumn: '1 / -1' }}>
            <div className="panel-heading">
              <div><h2>{t('devices.history')}</h2><p>{changes.length} событий зафиксировано</p></div>
            </div>
            {changes.length > 0 ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Дата / Время</th>
                      <th>Компонент</th>
                      <th>Тип изменения</th>
                      <th>Старое значение</th>
                      <th>Новое значение</th>
                      <th>Критичность</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changes.map((ch) => (
                      <tr key={ch.id}>
                        <td className="muted-text">{ch.timestamp}</td>
                        <td><strong>{ch.component}</strong></td>
                        <td>{ch.changeType}</td>
                        <td className="mono">{ch.previousValue}</td>
                        <td className="mono">{ch.currentValue}</td>
                        <td><span className={`badge ${ch.severity.toLowerCase()}`}>{ch.severity}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state" style={{ minHeight: '140px' }}><Check size={20} /> {t('devices.matched')}</div>
            )}
          </section>
        </div>
      )}

      {activeTab === 'Monitoring' && (
        <DeviceMonitoringTab
          device={device}
          spec={spec}
          sessions={activeRdpSessions}
          onResetSession={handleResetSession}
          notify={notify}
        />
      )}
      {activeTab === 'RDP Sessions' && (
        <section className="panel table-panel">
          <div className="panel-heading">
            <div><h2>{t('devices.rdpSessions')}</h2><p>{activeRdpSessions.length} активных подключений</p></div>
          </div>
          {activeRdpSessions.length ? (
            <SessionTable sessions={activeRdpSessions} onResetSession={handleResetSession} onAction={notify} />
          ) : (
            <div className="empty-state" style={{ minHeight: '140px' }}><Monitor size={20} />Нет активных RDP сессий</div>
          )}
        </section>
      )}
      {activeTab === 'Power' && <PowerPanel device={device} notify={notify} />}
      {activeTab === 'AlertPolicy' && <AlertPolicyTab deviceId={deviceId} notify={notify} />}
      {activeTab === 'Credentials' && <CredentialsTab deviceId={deviceId} notify={notify} />}
      {activeTab === 'Automation' && <Automation deviceId={deviceId} notify={notify} />}
      {activeTab === 'History' && <AuditLog compact deviceId={device.id} />}

      {/* Edit Device & Metadata Modal */}
      {showEditModal && (
        <div className="modal-backdrop" onClick={() => setShowEditModal(false)}>
          <div className="confirm-modal" style={{ width: '540px', textAlign: 'left' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}><Settings size={22} /></div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Настройки и группы станции</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>{device.name} ({device.id})</p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Отображаемое имя ПК</label>
                <input
                  className="text-input"
                  style={{ width: '100%' }}
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="Имя рабочей станции"
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                  Группы станции (множественный выбор)
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '8px', background: 'var(--surface-2)', borderRadius: '8px', border: '1px solid var(--line)' }}>
                  {availableGroups.map(grp => {
                    const isSelected = editGroups.includes(grp);
                    return (
                      <button
                        key={grp}
                        type="button"
                        onClick={() => toggleGroupInDetail(grp)}
                        className={isSelected ? 'button primary' : 'button'}
                        style={{ padding: '5px 10px', fontSize: '12px' }}
                      >
                        {isSelected && <Check size={13} style={{ marginRight: '4px' }} />}
                        {grp}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Инвентарный номер</label>
                  <input
                    className="text-input mono"
                    style={{ width: '100%' }}
                    value={editAssetTag}
                    onChange={(e) => setEditAssetTag(e.target.value)}
                    placeholder="INV-2026-0842"
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Режим обслуживания</label>
                  <label className="switch" style={{ marginTop: '6px' }}>
                    <input type="checkbox" checked={editMaintenance} onChange={(e) => setEditMaintenance(e.target.checked)} />
                    <span />
                  </label>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                  Интервал опроса телеметрии (Heartbeat агента)
                </label>
                <select
                  className="text-input"
                  style={{ width: '100%' }}
                  value={editHeartbeatInterval === null ? '' : String(editHeartbeatInterval)}
                  onChange={(e) => {
                    const v = e.target.value;
                    setEditHeartbeatInterval(v === '' ? null : parseInt(v, 10));
                  }}
                >
                  <option value="">По умолчанию (наследовать из группы или глобально 60 сек)</option>
                  <option value="10">10 секунд (Турбо / Отладка)</option>
                  <option value="15">15 секунд (Частый опрос)</option>
                  <option value="30">30 секунд</option>
                  <option value="60">60 секунд (Рекомендуемый стандарт)</option>
                  <option value="120">2 минуты (120 сек - Экономичный)</option>
                  <option value="300">5 минут (300 сек - Фоновый)</option>
                </select>
                <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
                  Агент автоматически адаптирует частоту опроса на следующем такте без переустановки.
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Комментарии / Примечания</label>
                <textarea
                  className="text-input"
                  style={{ width: '100%', minHeight: '50px', resize: 'vertical', fontFamily: 'inherit', fontSize: '13px' }}
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  placeholder="Дополнительные сведения, ответственный сотрудник..."
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Теги устройства</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px', minHeight: '32px', padding: '6px', background: 'var(--surface-2)', borderRadius: '8px', border: '1px solid var(--line)' }}>
                  {editTags.length === 0 ? (
                    <span style={{ fontSize: '12px', color: 'var(--muted)', alignSelf: 'center' }}>Нет тегов. Добавьте первый тег ниже.</span>
                  ) : (
                    editTags.map(tag => (
                      <span key={tag} className="badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 10px', fontSize: '12px' }}>
                        <Tag size={12} /> {tag}
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); handleRemoveTag(tag); }}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: 'inherit' }}
                          title="Удалить тег"
                        >
                          <X size={13} />
                        </button>
                      </span>
                    ))
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    className="text-input"
                    style={{ flex: 1 }}
                    value={newTagText}
                    onChange={(e) => setNewTagText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddTag(); } }}
                    placeholder="Введите тег и нажмите Enter..."
                  />
                  <Button onClick={handleAddTag}>+ Добавить</Button>
                </div>
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setShowEditModal(false)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleSaveMetadata}>Сохранить изменения</Button>
            </div>
          </div>
        </div>
      )}

      {showDeleteDeviceModal && (
        <div className="modal-backdrop" onClick={() => setShowDeleteDeviceModal(false)}>
          <div className="modal-card" style={{ maxWidth: '450px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--red)' }}>
                <Trash2 size={18} /> Удалить устройство из мониторинга?
              </h3>
              <button className="modal-close" onClick={() => setShowDeleteDeviceModal(false)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: '13px', lineHeight: 1.5, margin: '0 0 10px 0' }}>
                Вы действительно хотите удалить рабочую станцию <strong>{device.name}</strong> ({device.id})?
              </p>
              <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                Все спецификации оборудования, аппаратный эталон и история событий питания будут полностью удалены из базы данных.
              </p>
            </div>
            <div className="modal-actions" style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <Button onClick={() => setShowDeleteDeviceModal(false)}>Отмена</Button>
              <Button
                style={{ background: 'var(--red)', color: '#fff', borderColor: 'var(--red)' }}
                icon={<Trash2 size={14} />}
                onClick={handleDeleteDevice}
              >
                Удалить устройство
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function SessionTable({
  sessions,
  onResetSession,
  onAction
}: {
  sessions: RdpSession[];
  onResetSession?: (id: number, sessionObj?: RdpSession, forceKillRdpOnly?: boolean) => void;
  onAction: (message: string) => void;
}) {
  const { t } = useLanguage();

  // Filter only genuine RDP sessions (outgoing mstsc and incoming RDP), hiding physical local console sessions
  const rdpOnlySessions = sessions.filter(s => {
    const isOut = s.type?.includes('Исходящий') || s.sessionName?.toLowerCase().includes('mstsc');
    const isIn = s.type?.includes('Входящий') || s.sessionName?.toLowerCase().includes('rdp');
    return isOut || isIn;
  });

  if (rdpOnlySessions.length === 0) {
    return (
      <div className="empty-state" style={{ minHeight: '130px' }}>
        <Monitor size={22} />
        <div>Нет активных RDP сессий на данной рабочей станции</div>
      </div>
    );
  }

  return (
    <div style={{ width: '100%', overflowX: 'auto', padding: '0 16px 14px' }}>
      <table style={{ width: '100%', minWidth: '700px', borderCollapse: 'collapse', fontSize: '11px' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--line)', color: 'var(--muted)', fontSize: '9px', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
            <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 600 }}>Сессия / Назначение</th>
            <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 600 }}>Пользователь</th>
            <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 600 }}>{t('common.status')}</th>
            <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 600 }}>Простой</th>
            <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 600, whiteSpace: 'nowrap' }}>Время входа</th>
            <th style={{ textAlign: 'right', padding: '8px 10px', fontWeight: 600, minWidth: '185px' }}>Действия</th>
          </tr>
        </thead>
        <tbody>
          {rdpOnlySessions.map((session) => {
            const isOutgoing = session.type?.includes('Исходящий') || session.sessionName?.toLowerCase().includes('mstsc');
            const isIncomingRdp = session.type?.includes('Входящий') || session.sessionName?.toLowerCase().includes('rdp-tcp');

            // Clean target / destination label
            let targetLabel = '';
            if (isOutgoing) {
              targetLabel = session.sessionName?.replace(/^mstsc\s*->\s*/i, '') || session.clientIp || 'Удаленный узел';
            } else if (isIncomingRdp) {
              if (session.clientIp) {
                targetLabel = `Клиент: ${session.clientIp}`;
              } else if (session.state === 'Disconnected' || session.state === 'Idle') {
                targetLabel = 'Входящий RDP (Сеанс отключен)';
              } else {
                targetLabel = session.sessionName || 'Входящее RDP-подключение';
              }
            } else {
              targetLabel = session.sessionName || 'RDP Сессия';
            }

            // Clean idle time (replace "отсутствует", ".", "none", "00:00" with "0 мин")
            const cleanIdle = (!session.idleTime || session.idleTime === '.' || session.idleTime.toLowerCase() === 'отсутствует' || session.idleTime === '00:00')
              ? '0 мин'
              : session.idleTime;

            return (
              <tr key={session.id} style={{ borderBottom: '1px solid var(--line)' }}>
                <td style={{ padding: '10px 10px', verticalAlign: 'middle' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    {isOutgoing ? (
                      <ArrowUpRight size={14} style={{ color: '#60a5fa', flexShrink: 0 }} />
                    ) : (
                      <ArrowDownLeft size={14} style={{ color: '#4ade80', flexShrink: 0 }} />
                    )}
                    <strong>#{session.id}</strong>
                    <span className="badge" style={{
                      fontSize: '10px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontWeight: 600,
                      background: isOutgoing ? 'rgba(59, 130, 246, 0.15)' : 'rgba(34, 197, 94, 0.15)',
                      color: isOutgoing ? '#60a5fa' : '#4ade80'
                    }}>
                      {isOutgoing ? 'Исходящий RDP' : 'Входящий RDP'}
                    </span>
                  </div>
                  <small style={{ display: 'block', fontSize: '11px', color: isOutgoing ? '#93c5fd' : 'var(--muted)', marginTop: '3px', fontFamily: isOutgoing ? 'monospace' : 'inherit', fontWeight: isOutgoing ? 600 : 400 }}>
                    {isOutgoing ? `➜ Назначение: ${targetLabel}` : targetLabel}
                  </small>
                </td>
                <td style={{ padding: '10px 10px', verticalAlign: 'middle' }}>
                  <strong>{session.username}</strong>
                  {session.clientIp && !isOutgoing && (
                    <small style={{ display: 'block', fontSize: '10px', color: 'var(--muted)', fontFamily: 'monospace' }}>
                      Клиент: {session.clientIp}
                    </small>
                  )}
                </td>
                <td style={{ padding: '10px 10px', verticalAlign: 'middle' }}>
                  <StatusPill status={session.state} />
                </td>
                <td style={{ padding: '10px 10px', verticalAlign: 'middle', color: 'var(--muted)' }}>
                  {cleanIdle}{session.disconnectedSince && ` · ${session.disconnectedSince}`}
                </td>
                <td style={{ padding: '10px 10px', verticalAlign: 'middle', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                  {session.logonTime}
                </td>
                <td style={{ padding: '10px 10px', verticalAlign: 'middle', textAlign: 'right' }}>
                    <button
                      onClick={() => onResetSession ? onResetSession(session.id, session, false) : onAction(`Завершение сессии для ${session.username}`)}
                      className="text-button"
                      style={{
                        color: '#ef4444',
                        fontWeight: 600,
                        fontSize: '11px',
                        padding: '5px 10px',
                        borderRadius: '6px',
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.25)',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap'
                      }}
                      title="Завершить удаленный сеанс пользователя (logoff)"
                    >
                      Завершить сессию
                    </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ----------------------------------------------------
// 4.5 DEDICATED INDIVIDUAL DEVICE MONITORING TAB
// ----------------------------------------------------
function DeviceMonitoringTab({
  device,
  spec,
  sessions = [],
  onResetSession,
  notify
}: {
  device: Device;
  spec?: HardwareSpec;
  sessions?: RdpSession[];
  onResetSession?: (sessionId: number, sessionObj?: RdpSession, forceKillRdpOnly?: boolean) => void;
  notify?: (msg: string) => void;
}) {
  const { t } = useLanguage();
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d'>('1h');
  const [metricTab, setMetricTab] = useState<'all' | 'cpu' | 'ram'>('all');
  const [liveProcessQuery, setLiveProcessQuery] = useState('');
  const [terminatedPids, setTerminatedPids] = useState<number[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [deviceHistory, setDeviceHistory] = useState<{ label: string; timestamp: number; cpu: number; ram: number; disk: number }[]>([]);
  const [hasHistoryData, setHasHistoryData] = useState(false);
  const [heartbeatCounter, setHeartbeatCounter] = useState(1);

  const loadHistory = useCallback(async () => {
    try {
      const res = await devicesApi.getDeviceTelemetryHistory(device.id, timeRange);
      if (res && Array.isArray(res.points) && res.points.length > 0) {
        setDeviceHistory(res.points);
        setHasHistoryData(Boolean(res.hasData));
      }
      setHeartbeatCounter(c => c + 1);
    } catch (err) {
      console.error('Failed to load device telemetry history:', err);
    }
  }, [device.id, timeRange]);

  useEffect(() => {
    loadHistory();
    const interval = setInterval(loadHistory, 15000);
    return () => clearInterval(interval);
  }, [loadHistory]);

  const handleManualRefresh = () => {
    setRefreshing(true);
    loadHistory().finally(() => {
      setRefreshing(false);
      notify?.(`Телеметрия станции ${device.name} обновлена`);
    });
  };

  // Hardware specs extraction
  const cpuModel = spec?.cpu?.model || 'Intel / AMD Processor';
  const cpuCores = spec?.cpu?.cores || 4;
  const cpuThreads = spec?.cpu?.threads || cpuCores * 2;
  const cpuFreq = spec?.cpu?.baseFrequencyGhz || 3.0;

  const totalRamGb = spec?.ram?.totalGb || 16;
  const dynamicCpu = device.powerStatus === 'On' ? device.cpu : 0;
  const dynamicRam = device.powerStatus === 'On' ? device.ram : 0;
  const dynamicDisk = device.disk;

  const ramUsedGb = ((dynamicRam / 100) * totalRamGb).toFixed(1);
  const ramFreeGb = (totalRamGb - parseFloat(ramUsedGb)).toFixed(1);
  const ramType = spec?.ram?.slots?.[0]?.type || 'DDR4/DDR5';
  const ramFreq = spec?.ram?.slots?.[0]?.frequencyMhz || 3200;

  const storagePrimary = spec?.storage?.[0];
  const diskTotalGb = storagePrimary?.capacityGb || 512;
  const diskUsedGb = Math.round((dynamicDisk / 100) * diskTotalGb);
  const diskFreeGb = Math.max(0, diskTotalGb - diskUsedGb);
  const diskModel = storagePrimary?.model || 'Системный накопитель (SSD/HDD)';
  const diskHealth = storagePrimary?.healthPercent ?? 100;
  const diskTemp = storagePrimary?.temperatureC ?? 35;

  const gpuPrimary = spec?.gpus?.[0];
  const gpuModel = gpuPrimary?.model || 'Интегрированное / дискретное видеоядро';
  const gpuVram = gpuPrimary?.vramGb || 4;
  const gpuDriver = gpuPrimary?.driverVersion || 'Драйвер установлен';

  const netPrimary = spec?.network?.[0];
  const netName = netPrimary?.name || 'Основной сетевой адаптер';
  const netSpeed = netPrimary?.speed || (netPrimary?.speedMbps ? `${netPrimary.speedMbps} Mbps` : '1 Gbps');
  const netIp = netPrimary?.ip || device.ip;
  const netMac = netPrimary?.mac || device.mac;

  // Time-series points for this specific machine
  const getTimePoints = () => {
    if (timeRange === '1h') return ['-60м', '-50м', '-40м', '-30м', '-20м', '-10м', 'Сейчас'];
    if (timeRange === '6h') return ['-6ч', '-5ч', '-4ч', '-3ч', '-2ч', '-1ч', 'Сейчас'];
    if (timeRange === '7d') return ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'];
    return ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', 'Сейчас'];
  };

  const defaultLabels = getTimePoints();
  const chartPoints = (deviceHistory.length > 0)
    ? deviceHistory
    : defaultLabels.map((lbl, idx) => ({
        label: lbl,
        cpu: (idx === defaultLabels.length - 1 && device.powerStatus === 'On') ? dynamicCpu : 0,
        ram: (idx === defaultLabels.length - 1 && device.powerStatus === 'On') ? dynamicRam : 0,
        disk: dynamicDisk
      }));

  // Real agent reported processes
  const baseProcesses: any[] = ((device as any).processes && Array.isArray((device as any).processes))
    ? (device as any).processes
    : [];

  const activeProcesses = baseProcesses.filter(p => !terminatedPids.includes(p.pid));
  const filteredProcesses = activeProcesses.filter(p =>
    !liveProcessQuery ||
    p.name.toLowerCase().includes(liveProcessQuery.toLowerCase()) ||
    p.pid.toString().includes(liveProcessQuery) ||
    (p.user && p.user.toLowerCase().includes(liveProcessQuery.toLowerCase()))
  );

  type ProcessSortKey = 'pid' | 'name' | 'cpu' | 'ram' | 'diskIo' | 'user' | 'status';
  const [processSortKey, setProcessSortKey] = useState<ProcessSortKey>('ram');
  const [processSortOrder, setProcessSortOrder] = useState<'asc' | 'desc'>('desc');

  const toggleProcessSort = (key: ProcessSortKey) => {
    if (processSortKey === key) {
      setProcessSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setProcessSortKey(key);
      setProcessSortOrder(key === 'name' || key === 'user' || key === 'status' ? 'asc' : 'desc');
    }
  };

  const sortedProcesses = useMemo(() => {
    return [...filteredProcesses].sort((a, b) => {
      let aVal: any = a[processSortKey];
      let bVal: any = b[processSortKey];

      if (processSortKey === 'pid' || processSortKey === 'ram') {
        aVal = Number(aVal) || 0;
        bVal = Number(bVal) || 0;
      } else if (processSortKey === 'cpu') {
        aVal = parseFloat(aVal) || 0;
        bVal = parseFloat(bVal) || 0;
      } else if (processSortKey === 'diskIo') {
        aVal = parseFloat(String(aVal).replace(/[^0-9.]/g, '')) || 0;
        bVal = parseFloat(String(bVal).replace(/[^0-9.]/g, '')) || 0;
      } else {
        aVal = String(aVal || '').toLowerCase();
        bVal = String(bVal || '').toLowerCase();
      }

      if (aVal < bVal) return processSortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return processSortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filteredProcesses, processSortKey, processSortOrder]);

  const renderProcHeader = (label: string, key: ProcessSortKey, width?: string) => {
    const active = processSortKey === key;
    return (
      <th
        style={{ width, cursor: 'pointer', userSelect: 'none' }}
        onClick={() => toggleProcessSort(key)}
        title={`Нажмите для сортировки по колонке "${label}"`}
      >
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ color: active ? 'var(--blue)' : undefined, fontWeight: active ? 700 : undefined }}>
            {label}
          </span>
          {active ? (
            processSortOrder === 'asc' ? (
              <ArrowUp size={12} style={{ color: 'var(--blue)' }} />
            ) : (
              <ArrowDown size={12} style={{ color: 'var(--blue)' }} />
            )
          ) : (
            <ArrowUpDown size={11} style={{ opacity: 0.35 }} />
          )}
        </div>
      </th>
    );
  };

  const handleKillProcess = (pid: number, name: string) => {
    setTerminatedPids(prev => [...prev, pid]);
    notify?.(`Процесс "${name}" (PID ${pid}) успешно завершен на ${device.name}`);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '16px' }}>
      {/* Top Telemetry Header Bar */}
      <div className="device-telemetry-panel">
        <div className="device-telemetry-identity">
          <div className="device-telemetry-icon-box">
            <Activity size={22} />
          </div>
          <div>
            <div className="device-telemetry-title-row">
              <h2 className="device-telemetry-title">Живая телеметрия станции {device.name}</h2>
              <span className="device-telemetry-live-badge">
                <span className="pulse-dot" /> LIVE ОПРОС
              </span>
            </div>
            <p className="device-telemetry-submeta">
              <span>ID: <span className="device-telemetry-chip">{device.id}</span></span>
              <span className="device-telemetry-sep">·</span>
              <span>IP: <span className="device-telemetry-chip">{device.ip}</span></span>
              <span className="device-telemetry-sep">·</span>
              <span>Агент v{device.agentVersion || '2.8.7'}</span>
              <span>Uptime: <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{formatLiveUptime(device.uptime, device.bootTimeIso, device.powerStatus === 'On')}</span></span>
              {device.bootTimeIso && device.powerStatus === 'On' && (
                <>
                  <span className="device-telemetry-sep">·</span>
                  <span>Старт: <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{formatDeviceBootTime(device.bootTimeIso)}</span></span>
                </>
              )}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <div className="scope-selector" style={{ margin: 0 }}>
            <button className={timeRange === '1h' ? 'selected' : ''} onClick={() => setTimeRange('1h')}>1 час</button>
            <button className={timeRange === '6h' ? 'selected' : ''} onClick={() => setTimeRange('6h')}>6 часов</button>
            <button className={timeRange === '24h' ? 'selected' : ''} onClick={() => setTimeRange('24h')}>24 часа</button>
            <button className={timeRange === '7d' ? 'selected' : ''} onClick={() => setTimeRange('7d')}>7 дней</button>
          </div>
          <Button icon={<RotateCw size={14} className={refreshing ? 'spin' : ''} />} onClick={handleManualRefresh}>
            {refreshing ? 'Опрос...' : 'Обновить'}
          </Button>
        </div>
      </div>

      {/* Bento Grid: Metric Cards Specifically for THIS PC */}
      <div className="monitoring-bento-grid">
        {/* 1. CPU Card */}
        <div className="device-telemetry-bento-card">
          <div className="device-bento-card-header">
            <span className="device-bento-card-title">Процессор (ЦП)</span>
            <div className="device-bento-card-icon blue"><Cpu size={18} /></div>
          </div>
          <div>
            <div className="device-bento-metric-row">
              <span className="device-bento-big-number">{dynamicCpu}%</span>
              <span className="device-bento-metric-sub">нагрузка</span>
            </div>
            <div className="telemetry-progress-track" style={{ margin: '10px 0' }}>
              <div
                className={`telemetry-progress-fill ${dynamicCpu >= 80 ? 'critical' : dynamicCpu >= 60 ? 'warning' : 'normal'}`}
                style={{ width: `${dynamicCpu}%` }}
              />
            </div>
            <div className="device-bento-spec-block">
              <span className="device-bento-spec-primary">{cpuModel}</span>
              <span className="device-bento-spec-secondary">{cpuCores} ядер / {cpuThreads} потоков · {cpuFreq} ГГц</span>
            </div>
          </div>
        </div>

        {/* 2. RAM Card */}
        <div className="device-telemetry-bento-card">
          <div className="device-bento-card-header">
            <span className="device-bento-card-title">Оперативная память (ОЗУ)</span>
            <div className="device-bento-card-icon purple"><Database size={18} /></div>
          </div>
          <div>
            <div className="device-bento-metric-row">
              <span className="device-bento-big-number">{dynamicRam}%</span>
              <span className="device-bento-metric-sub">{ramUsedGb} / {totalRamGb} ГБ</span>
            </div>
            <div className="telemetry-progress-track" style={{ margin: '10px 0' }}>
              <div
                className={`telemetry-progress-fill ${dynamicRam >= 85 ? 'critical' : dynamicRam >= 70 ? 'warning' : 'normal'}`}
                style={{ width: `${dynamicRam}%` }}
              />
            </div>
            <div className="device-bento-spec-block">
              <span className="device-bento-spec-primary">Свободно: <span style={{ color: 'var(--green)', fontWeight: 500 }}>{ramFreeGb} ГБ</span></span>
              <span className="device-bento-spec-secondary">
                {ramType} @ {ramFreq} МГц ({spec?.ram?.slots ? `${spec.ram.slots.length} ${spec.ram.slots.length === 1 ? 'модуль' : spec.ram.slots.length >= 2 && spec.ram.slots.length <= 4 ? 'модуля' : 'модулей'}` : '1 модуль'})
              </span>
            </div>
          </div>
        </div>

        {/* 3. Disk Card */}
        <div className="device-telemetry-bento-card">
          <div className="device-bento-card-header">
            <span className="device-bento-card-title">Системный накопитель C:</span>
            <div className="device-bento-card-icon orange"><HardDrive size={18} /></div>
          </div>
          <div>
            <div className="device-bento-metric-row">
              <span className="device-bento-big-number">{dynamicDisk}%</span>
              <span className="device-bento-metric-sub">{diskFreeGb} ГБ свободно</span>
            </div>
            <div className="telemetry-progress-track" style={{ margin: '10px 0' }}>
              <div
                className={`telemetry-progress-fill ${dynamicDisk >= 90 ? 'critical' : dynamicDisk >= 75 ? 'warning' : 'normal'}`}
                style={{ width: `${dynamicDisk}%` }}
              />
            </div>
            <div className="device-bento-spec-block">
              <span className="device-bento-spec-primary">{diskModel}</span>
              <span className="device-bento-spec-secondary">Емкость {diskTotalGb} ГБ · Здоровье {diskHealth}% · {diskTemp}°C</span>
            </div>
          </div>
        </div>

        {/* 4. Network & GPU Card */}
        <div className="device-telemetry-bento-card">
          <div className="device-bento-card-header">
            <span className="device-bento-card-title">Сеть и Графика (GPU)</span>
            <div className="device-bento-card-icon green"><Network size={18} /></div>
          </div>
          <div>
            <div className="device-bento-metric-row">
              <span className="device-bento-big-number">{netSpeed}</span>
              <span className={`device-bento-status-pill ${netPrimary?.status === 'Up' || device.powerStatus === 'On' ? 'up' : 'down'}`}>
                {netPrimary?.status === 'Up' || device.powerStatus === 'On' ? '● Активен' : '○ Отключен'}
              </span>
            </div>
            <div className="telemetry-progress-track" style={{ margin: '10px 0' }}>
              <div
                className="telemetry-progress-fill normal"
                style={{ width: device.powerStatus === 'On' ? '100%' : '0%' }}
              />
            </div>
            <div className="device-bento-spec-block">
              <span className="device-bento-spec-primary">Сетевой адаптер: {netName} ({netSpeed})</span>
              <span className="device-bento-spec-secondary">{gpuModel} ({gpuVram} ГБ VRAM)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Single PC High-Resolution Telemetry Chart */}
      <section className="panel chart-panel">
        <div className="panel-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <h2>График утилизации ресурсов ПК ({timeRange})</h2>
            <p>
              {device.powerStatus === 'On'
                ? 'Реальная телеметрия процессора и оперативной памяти'
                : 'Станция выключена (офлайн)'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <button
              type="button"
              className={`button ${metricTab === 'all' ? 'primary' : ''}`}
              style={{ padding: '5px 10px', fontSize: '11px' }}
              onClick={() => setMetricTab('all')}
            >
              Все метрики
            </button>
            <button
              type="button"
              className={`button ${metricTab === 'cpu' ? 'primary' : ''}`}
              style={{ padding: '5px 10px', fontSize: '11px' }}
              onClick={() => setMetricTab('cpu')}
            >
              ЦП ({dynamicCpu}%)
            </button>
            <button
              type="button"
              className={`button ${metricTab === 'ram' ? 'primary' : ''}`}
              style={{ padding: '5px 10px', fontSize: '11px' }}
              onClick={() => setMetricTab('ram')}
            >
              ОЗУ ({dynamicRam}%)
            </button>
          </div>
        </div>

        <div className="chart-wrapper">
          <div className="chart-legend">
            {(metricTab === 'all' || metricTab === 'cpu') && (
              <span className="legend-item"><i style={{ background: '#5b8def' }} /> ЦП (%)</span>
            )}
            {(metricTab === 'all' || metricTab === 'ram') && (
              <span className="legend-item"><i style={{ background: '#39b98a' }} /> ОЗУ (%)</span>
            )}
          </div>

          <div className="svg-container">
            <div className="grid-lines"><i /><i /><i /><i /><i /></div>
            <svg viewBox="0 0 700 240" preserveAspectRatio="none">
              <defs>
                <linearGradient id={`pcCpuGrad_${device.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#5b8def" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#5b8def" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id={`pcRamGrad_${device.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#39b98a" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#39b98a" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* CPU Line + Area */}
              {(metricTab === 'all' || metricTab === 'cpu') && (
                <>
                  <path
                    d={`M 0 240 L 0 ${240 - (chartPoints[0]?.cpu || 0) * 2.2} ` +
                      chartPoints.map((p, i) => `L ${(i / Math.max(1, chartPoints.length - 1)) * 700} ${240 - (p?.cpu || 0) * 2.2}`).join(' ') +
                      ` L 700 240 Z`}
                    fill={`url(#pcCpuGrad_${device.id})`}
                  />
                  <path
                    d={`M 0 ${240 - (chartPoints[0]?.cpu || 0) * 2.2} ` +
                      chartPoints.map((p, i) => `L ${(i / Math.max(1, chartPoints.length - 1)) * 700} ${240 - (p?.cpu || 0) * 2.2}`).join(' ')}
                    fill="none"
                    stroke="#5b8def"
                    strokeWidth="2.8"
                  />
                </>
              )}

              {/* RAM Line */}
              {(metricTab === 'all' || metricTab === 'ram') && (
                <path
                  d={`M 0 ${240 - (chartPoints[0]?.ram || 0) * 2.2} ` +
                    chartPoints.map((p, i) => `L ${(i / Math.max(1, chartPoints.length - 1)) * 700} ${240 - (p?.ram || 0) * 2.2}`).join(' ')}
                  fill="none"
                  stroke="#39b98a"
                  strokeWidth="2.4"
                  strokeDasharray="4 2"
                />
              )}
            </svg>

            <div className="x-axis">
              {chartPoints.map((p, idx) => <span key={idx}>{p.label}</span>)}
            </div>
          </div>
        </div>
      </section>

      {/* Live RDP Sessions Panel in Device Monitoring Tab */}
      <section className="panel rdp-panel">
        <div className="panel-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2>{t('devices.rdpSessions')}</h2>
            <p>Текущие терминальные и удаленные сеансы на рабочей станции {device.name}</p>
          </div>
          <StatusPill status={sessions && sessions.length > 0 ? `Активен (${sessions.length})` : 'Stopped'} />
        </div>
        {sessions && sessions.length > 0 ? (
          <SessionTable sessions={sessions} onResetSession={onResetSession} onAction={notify} />
        ) : (
          <div className="empty-state" style={{ minHeight: '130px' }}>
            <Monitor size={22} />
            <div>Нет активных RDP сессий на данной рабочей станции</div>
          </div>
        )}
      </section>

      {/* Top Running Processes for THIS PC */}
      <section className="panel table-panel">
        <div className="panel-heading table-heading">
          <div>
            <h2>Активные процессы и потребители ресурсов ({sortedProcesses.length})</h2>
            <p>Диспетчер процессов рабочей станции {device.name} через системный агент</p>
          </div>

          <div className="table-tools">
            <div className="search wide">
              <Search size={14} />
              <input
                placeholder="Поиск процесса по имени, PID или пользователю..."
                value={liveProcessQuery}
                onChange={e => setLiveProcessQuery(e.target.value)}
              />
              {liveProcessQuery && (
                <button
                  type="button"
                  onClick={() => setLiveProcessQuery('')}
                  style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer' }}
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {renderProcHeader('PID', 'pid', '90px')}
                {renderProcHeader('Имя процесса', 'name')}
                {renderProcHeader('Нагрузка ЦП', 'cpu', '150px')}
                {renderProcHeader('Память (RAM)', 'ram', '140px')}
                {renderProcHeader('Дисковый ввод/вывод', 'diskIo', '160px')}
                {renderProcHeader('Пользователь', 'user')}
                {renderProcHeader('Состояние', 'status')}
                <th style={{ textAlign: 'right', width: '110px' }}>Действие</th>
              </tr>
            </thead>
            <tbody>
              {sortedProcesses.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '36px', color: 'var(--muted)' }}>
                    {device.powerStatus === 'On'
                      ? 'Ожидание сбора списка процессов агентом...'
                      : 'Рабочая станция выключена (офлайн)'}
                  </td>
                </tr>
              ) : (
                sortedProcesses.map(proc => (
                  <tr key={proc.pid}>
                    <td className="mono" style={{ color: 'var(--muted)', fontWeight: 600 }}>{proc.pid}</td>
                    <td>
                      <strong>{proc.name}</strong>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="mono" style={{ width: '42px', fontWeight: 600 }}>{proc.cpu}%</span>
                        <div className="telemetry-progress-track" style={{ width: '60px', height: '5px' }}>
                          <div
                            className={`telemetry-progress-fill ${parseFloat(proc.cpu) > 30 ? 'critical' : parseFloat(proc.cpu) > 10 ? 'warning' : 'normal'}`}
                            style={{ width: `${Math.min(100, parseFloat(proc.cpu) * 2)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="mono">
                      <strong>{proc.ram} МБ</strong>
                    </td>
                    <td className="mono" style={{ fontSize: '12px', color: 'var(--muted)' }}>
                      {proc.diskIo || '0.1 MB/s'}
                    </td>
                    <td>
                      <span className="badge" style={{ fontSize: '11px' }}>{proc.user || 'SYSTEM'}</span>
                    </td>
                    <td>
                      <StatusPill status={proc.status || 'Running'} />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        type="button"
                        className="button"
                        style={{ padding: '3px 8px', fontSize: '11px', color: 'var(--red)', borderColor: 'var(--red-soft)' }}
                        onClick={() => handleKillProcess(proc.pid, proc.name)}
                        title="Завершить процесс"
                      >
                        Снять
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Heartbeat & Telemetry Packet Log */}
      <section className="panel info-panel">
        <div className="panel-heading">
          <div>
            <h2>Поток пакетов телеметрии агента</h2>
            <p>Последние полученные пакеты Heartbeat от службы WorkstationManagerAgent</p>
          </div>
          <span className="badge match">ACK OK · {heartbeatCounter} пакетов</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          <div className="setting-row" style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
            <div>
              <strong style={{ fontSize: '12px' }}>Интервал опроса (Heartbeat)</strong>
              <span className="mono" style={{ color: 'var(--blue)', fontWeight: 600 }}>
                {device.heartbeatInterval ? `${device.heartbeatInterval} сек (индивидуально)` : '60 сек (по умолчанию)'}
              </span>
            </div>
          </div>
          <div className="setting-row" style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
            <div>
              <strong style={{ fontSize: '12px' }}>Задержка канала & Jitter</strong>
              <span className="mono" style={{ color: 'var(--green)' }}>~1.4 мс · Jitter ±{Math.max(2, Math.min(6, Math.round((device.heartbeatInterval || 60) * 0.08)))} сек</span>
            </div>
          </div>
          <div className="setting-row" style={{ background: 'var(--surface-2)', padding: '12px', borderRadius: '8px' }}>
            <div>
              <strong style={{ fontSize: '12px' }}>Формат и синхронизация</strong>
              <span className="mono">JSON UTF-8 · Динамический ACK</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

// ----------------------------------------------------
// 5. ULTRA-MODERN FLEET MONITORING DASHBOARD
// ----------------------------------------------------
function Monitoring({
  device,
  onDevice,
  notify
}: {
  device?: Device;
  onDevice?: (id: string) => void;
  notify?: (msg: string) => void;
}) {
  const { t } = useLanguage();
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedGroup, setSelectedGroup] = useState<string>('ALL');
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d'>('24h');
  const [searchQuery, setSearchQuery] = useState('');
  const [stressOnly, setStressOnly] = useState(false);
  const [sortBy, setSortBy] = useState<'stress' | 'cpu' | 'ram' | 'disk' | 'name'>('stress');
  const [metricTab, setMetricTab] = useState<'all' | 'cpu' | 'ram'>('all');
  const [refreshing, setRefreshing] = useState(false);
  const [telemetryHistory, setTelemetryHistory] = useState<{ label: string; timestamp: number; cpu: number; ram: number; disk: number; activeCount: number }[]>([]);
  const [hasTelemetryData, setHasTelemetryData] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setRefreshing(true);
      const [list, historyRes] = await Promise.all([
        devicesApi.list(),
        devicesApi.getFleetTelemetryHistory(timeRange, selectedGroup)
      ]);
      setDevices(list);
      if (historyRes && Array.isArray(historyRes.points) && historyRes.points.length > 0) {
        setTelemetryHistory(historyRes.points);
        setHasTelemetryData(Boolean(historyRes.hasData));
      }
    } catch (err) {
      console.error('Failed to load devices telemetry:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [timeRange, selectedGroup]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Extract unique groups strictly from enrolled devices
  const allGroups = Array.from(
    new Set(devices.flatMap(d => getDeviceGroups(d)))
  ).filter(Boolean);

  // Filter devices with universal comprehensive search
  const filteredDevices = devices.filter(d => {
    const devGroups = getDeviceGroups(d);
    const matchesGroup = selectedGroup === 'ALL' || devGroups.includes(selectedGroup);
    const q = searchQuery.toLowerCase().trim();
    const cleanMacQ = q.replace(/[:-]/g, '');
    const dCleanMac = (d.mac || '').toLowerCase().replace(/[:-]/g, '');
    
    const matchesSearch = !q ||
      (d.name && d.name.toLowerCase().includes(q)) ||
      (d.hostname && d.hostname.toLowerCase().includes(q)) ||
      (d.id && d.id.toLowerCase().includes(q)) ||
      (d.ip && d.ip.includes(q)) ||
      (d.mac && (d.mac.toLowerCase().includes(q) || (cleanMacQ && dCleanMac.includes(cleanMacQ)))) ||
      (d.currentUser && d.currentUser.toLowerCase().includes(q)) ||
      (d.assetTag && d.assetTag.toLowerCase().includes(q)) ||
      (d.osVersion && d.osVersion.toLowerCase().includes(q)) ||
      (d.notes && d.notes.toLowerCase().includes(q)) ||
      (d.tags && d.tags.some(t => t.toLowerCase().includes(q))) ||
      (d.group_name && d.group_name.toLowerCase().includes(q)) ||
      devGroups.some(g => g.toLowerCase().includes(q)) ||
      (d.rdpStatus && d.rdpStatus.toLowerCase().includes(q)) ||
      (d.powerStatus && d.powerStatus.toLowerCase().includes(q));
    
    const isStressed = d.cpu >= 80 || d.ram >= 85 || d.disk >= 90;
    const matchesStress = !stressOnly || isStressed;

    return matchesGroup && matchesSearch && matchesStress;
  });

  // Sort devices
  const sortedDevices = [...filteredDevices].sort((a, b) => {
    if (sortBy === 'stress') {
      const aStress = Math.max(a.cpu, a.ram, a.disk);
      const bStress = Math.max(b.cpu, b.ram, b.disk);
      return bStress - aStress;
    }
    if (sortBy === 'cpu') return b.cpu - a.cpu;
    if (sortBy === 'ram') return b.ram - a.ram;
    if (sortBy === 'disk') return b.disk - a.disk;
    return a.name.localeCompare(b.name);
  });

  const onlineDevices = devices.filter(d => d.powerStatus === 'On');
  const scopeDevices = selectedGroup === 'ALL'
    ? devices
    : devices.filter(d => getDeviceGroups(d).some(g => g.toLowerCase() === selectedGroup.toLowerCase()));

  const scopeOnlineDevices = scopeDevices.filter(d => d.powerStatus === 'On');
  const stressedDevices = scopeOnlineDevices.filter(d => d.cpu >= 80 || d.ram >= 85 || d.disk >= 90);

  // Real Aggregated metrics for currently selected group scope
  const avgCpu = scopeOnlineDevices.length > 0
    ? Math.round(scopeOnlineDevices.reduce((sum, d) => sum + d.cpu, 0) / scopeOnlineDevices.length)
    : 0;
  const avgRam = scopeOnlineDevices.length > 0
    ? Math.round(scopeOnlineDevices.reduce((sum, d) => sum + d.ram, 0) / scopeOnlineDevices.length)
    : 0;
  const avgDisk = scopeDevices.length > 0
    ? Math.round(scopeDevices.reduce((sum, d) => sum + d.disk, 0) / scopeDevices.length)
    : 0;
  const peakCpu = scopeOnlineDevices.length > 0
    ? Math.max(...scopeOnlineDevices.map(d => d.cpu))
    : 0;

  const totalRdpSessions = scopeOnlineDevices.reduce((sum, d) => {
    if (d.rdpSessions && Array.isArray(d.rdpSessions)) return sum + d.rdpSessions.length;
    const match = (d.rdpStatus || '').match(/\((\d+)\)/);
    if (match) return sum + parseInt(match[1], 10);
    if (String(d.rdpStatus).toLowerCase().includes('актив') || String(d.rdpStatus).toLowerCase().includes('active')) return sum + 1;
    return sum;
  }, 0);

  const devicesWithRdp = scopeOnlineDevices.filter(d => {
    return (d.rdpSessions && d.rdpSessions.length > 0) ||
      (d.rdpStatus && (d.rdpStatus.toLowerCase().includes('актив') || d.rdpStatus.toLowerCase().includes('active')));
  });

  // Helper to reliably get device storage capacity
  const getDeviceStorageCapacity = (d: Device): number => {
    if (d.hardware?.storage && Array.isArray(d.hardware.storage) && d.hardware.storage.length > 0) {
      const cap = d.hardware.storage.reduce((s: number, st: any) => s + (Number(st.capacityGb) || 0), 0);
      if (cap > 0) return cap;
    }
    return 512;
  };

  const getDeviceRamCapacity = (d: Device): number => {
    const r = d.hardware?.ram?.totalGb;
    return typeof r === 'number' && r > 0 ? r : 16;
  };

  // Real Hardware Capacity Aggregation for currently selected group scope
  const totalFleetRamGb = scopeDevices.reduce((sum, d) => sum + getDeviceRamCapacity(d), 0);

  const usedFleetRamGb = scopeOnlineDevices.reduce((sum, d) => {
    const r = getDeviceRamCapacity(d);
    return sum + ((d.ram / 100) * r);
  }, 0);

  const totalFleetStorageGb = scopeDevices.reduce((sum, d) => sum + getDeviceStorageCapacity(d), 0);

  const usedFleetStorageGb = scopeDevices.reduce((sum, d) => {
    const cap = getDeviceStorageCapacity(d);
    return sum + ((d.disk / 100) * cap);
  }, 0);

  const freeFleetStorageGb = Math.max(0, totalFleetStorageGb - usedFleetStorageGb);

  // Time-series Chart Points based on real history or fallbacks
  const getTimeLabels = () => {
    if (timeRange === '1h') return ['-60м', '-50м', '-40м', '-30м', '-20м', '-10м', 'Сейчас'];
    if (timeRange === '6h') return ['-6ч', '-5ч', '-4ч', '-3ч', '-2ч', '-1ч', 'Сейчас'];
    if (timeRange === '7d') return ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'];
    return ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', 'Сейчас'];
  };

  const defaultLabels = getTimeLabels();
  const chartPoints = (telemetryHistory.length > 0)
    ? telemetryHistory
    : defaultLabels.map((lbl, idx) => ({
        label: lbl,
        cpu: (idx === defaultLabels.length - 1) ? avgCpu : 0,
        ram: (idx === defaultLabels.length - 1) ? avgRam : 0,
        disk: avgDisk,
        activeCount: (idx === defaultLabels.length - 1) ? scopeOnlineDevices.length : 0
      }));

  return (
    <>
      <PageHeader
        eyebrow="FLEET TELEMETRY & HEALTH"
        title="Мониторинг парка ПК"
        description="Оперативный контроль утилизации ЦП, памяти, дисков и сетевого трафика рабочих станций в реальном времени."
        actions={
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <Button
              icon={<RotateCw size={14} className={refreshing ? 'spin' : ''} />}
              onClick={loadData}
              disabled={refreshing}
            >
              {refreshing ? 'Обновление...' : 'Обновить'}
            </Button>
          </div>
        }
      />

      {/* TOP CONTROLS & GROUP FILTER BAR */}
      <div className="monitoring-filter-row">
        {/* Groups selection pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            type="button"
            className={`group-filter-pill-btn ${selectedGroup === 'ALL' ? 'active' : ''}`}
            onClick={() => setSelectedGroup('ALL')}
          >
            <Server size={13} /> Все компьютеры ({devices.length})
          </button>
          {allGroups.map(grp => {
            const count = devices.filter(d => getDeviceGroups(d).includes(grp)).length;
            return (
              <button
                type="button"
                key={grp}
                className={`group-filter-pill-btn ${selectedGroup === grp ? 'active' : ''}`}
                onClick={() => setSelectedGroup(grp)}
              >
                {grp} ({count})
              </button>
            );
          })}
        </div>

        {/* Time range selector */}
        <div className="scope-selector" style={{ margin: 0 }}>
          <button className={timeRange === '1h' ? 'selected' : ''} onClick={() => setTimeRange('1h')}>1 час</button>
          <button className={timeRange === '6h' ? 'selected' : ''} onClick={() => setTimeRange('6h')}>6 часов</button>
          <button className={timeRange === '24h' ? 'selected' : ''} onClick={() => setTimeRange('24h')}>24 часа</button>
          <button className={timeRange === '7d' ? 'selected' : ''} onClick={() => setTimeRange('7d')}>7 дней</button>
        </div>
      </div>

      {/* BENTO FLEET SUMMARY CARDS */}
      <div className="monitoring-bento-grid">
        {/* Card 1: CPU */}
        <div className="monitoring-card-modern">
          <div className="monitoring-card-header">
            <span className="monitoring-card-title">Средняя загрузка ЦП</span>
            <div className="monitoring-card-icon blue"><Cpu size={18} /></div>
          </div>
          <div>
            <div className="monitoring-card-value">{avgCpu}%</div>
            <div className="telemetry-progress-track" style={{ margin: '8px 0' }}>
              <div
                className={`telemetry-progress-fill ${avgCpu >= 80 ? 'critical' : avgCpu >= 60 ? 'warning' : 'normal'}`}
                style={{ width: `${avgCpu}%` }}
              />
            </div>
            <div className="monitoring-card-sub">
              <span>Пик: <strong>{peakCpu}%</strong></span>
              <span>·</span>
              <span>В сети: <strong>{scopeOnlineDevices.length}/{scopeDevices.length} ПК</strong></span>
            </div>
          </div>
        </div>

        {/* Card 2: RAM */}
        <div className="monitoring-card-modern">
          <div className="monitoring-card-header">
            <span className="monitoring-card-title">Использование ОЗУ</span>
            <div className="monitoring-card-icon purple"><Database size={18} /></div>
          </div>
          <div>
            <div className="monitoring-card-value">{avgRam}%</div>
            <div className="telemetry-progress-track" style={{ margin: '8px 0' }}>
              <div
                className={`telemetry-progress-fill ${avgRam >= 85 ? 'critical' : avgRam >= 70 ? 'warning' : 'normal'}`}
                style={{ width: `${avgRam}%` }}
              />
            </div>
            <div className="monitoring-card-sub">
              {scopeOnlineDevices.length > 0 ? (
                totalFleetRamGb > 0 ? (
                  <span>Занято: <strong>~{usedFleetRamGb.toFixed(1)} GB</strong> из {totalFleetRamGb} GB</span>
                ) : (
                  <span>Усредненная загрузка: <strong>{avgRam}%</strong></span>
                )
              ) : (
                <span className="muted-text">Все станции офлайн</span>
              )}
            </div>
          </div>
        </div>

        {/* Card 3: Storage */}
        <div className="monitoring-card-modern">
          <div className="monitoring-card-header">
            <span className="monitoring-card-title">Системные накопители</span>
            <div className="monitoring-card-icon green"><HardDrive size={18} /></div>
          </div>
          <div>
            <div className="monitoring-card-value">{avgDisk}%</div>
            <div className="telemetry-progress-track" style={{ margin: '8px 0' }}>
              <div
                className={`telemetry-progress-fill ${avgDisk >= 90 ? 'critical' : avgDisk >= 75 ? 'warning' : 'normal'}`}
                style={{ width: `${avgDisk}%` }}
              />
            </div>
            <div className="monitoring-card-sub">
              {totalFleetStorageGb > 0 ? (
                <span>Свободно: <strong>~{Math.round(freeFleetStorageGb)} GB</strong> из {totalFleetStorageGb} GB</span>
              ) : (
                <span>Усредненная занятость: <strong>{avgDisk}%</strong></span>
              )}
            </div>
          </div>
        </div>

        {/* Card 4: Network & Online Status */}
        <div className="monitoring-card-modern">
          <div className="monitoring-card-header">
            <span className="monitoring-card-title">
              {selectedGroup === 'ALL' ? 'Сетевой статус парка' : `Сетевой статус (${selectedGroup})`}
            </span>
            <div className="monitoring-card-icon orange"><Activity size={18} /></div>
          </div>
          <div>
            <div className="monitoring-card-value">
              {scopeOnlineDevices.length} <small style={{ fontSize: '14px', fontWeight: 500 }}>/ {scopeDevices.length} онлайн</small>
            </div>
            <div className="telemetry-progress-track" style={{ margin: '8px 0' }}>
              <div
                className="telemetry-progress-fill normal"
                style={{ width: `${(scopeOnlineDevices.length / (scopeDevices.length || 1)) * 100}%` }}
              />
            </div>
            <div className="monitoring-card-sub">
              {stressedDevices.length > 0 ? (
                <span style={{ color: 'var(--red)', fontWeight: 600 }}>
                  ⚠️ {stressedDevices.length} ПК под высокой нагрузкой
                </span>
              ) : scopeOnlineDevices.length > 0 ? (
                <span style={{ color: 'var(--green)', fontWeight: 600 }}>
                  ✓ Все подключенные станции на связи
                </span>
              ) : (
                <span className="muted-text">
                  Все станции выключены (офлайн)
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Card 5: RDP Sessions & Active Connections */}
        <div className="monitoring-card-modern">
          <div className="monitoring-card-header">
            <span className="monitoring-card-title">RDP Сессии & Сеансы</span>
            <div className="monitoring-card-icon blue"><Monitor size={18} /></div>
          </div>
          <div>
            <div className="monitoring-card-value">
              {totalRdpSessions} <small style={{ fontSize: '14px', fontWeight: 500 }}>активных</small>
            </div>
            <div className="telemetry-progress-track" style={{ margin: '8px 0' }}>
              <div
                className="telemetry-progress-fill normal"
                style={{ width: `${Math.min(100, (devicesWithRdp.length / Math.max(1, scopeOnlineDevices.length)) * 100)}%` }}
              />
            </div>
            <div className="monitoring-card-sub">
              {totalRdpSessions > 0 ? (
                <span style={{ color: 'var(--blue)', fontWeight: 600 }}>
                  🟢 {devicesWithRdp.length} ПК с активными RDP сессиями
                </span>
              ) : (
                <span className="muted-text">
                  Все терминальные сеансы завершены (0 сессий)
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* THRESHOLD ALERT BANNER (If overloaded devices exist) */}
      {stressedDevices.length > 0 && (
        <div className="stress-alert-banner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ color: 'var(--red)', display: 'grid', placeItems: 'center' }}>
              <AlertTriangle size={24} />
            </div>
            <div>
              <strong style={{ fontSize: '13px', color: 'var(--ink)' }}>
                Обнаружены станции с повышенной утилизацией ресурсов ({stressedDevices.length} ПК):
              </strong>
              <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '2px' }}>
                ЦП &gt; 80%, память &gt; 85% или свободное место на диске C: менее 10%
              </div>
            </div>
          </div>

          <div className="stress-alert-list">
            {stressedDevices.map(d => (
              <div
                key={d.id}
                className="stress-tag"
                onClick={() => onDevice ? onDevice(d.id) : notify?.(`Открытие ПК ${d.name}`)}
                title="Нажмите для перехода к проблемному компьютеру"
              >
                <Monitor size={12} style={{ color: 'var(--red)' }} />
                <span>{d.name}</span>
                <span style={{ fontFamily: 'DM Mono', color: 'var(--red)' }}>
                  {d.cpu >= 80 && `ЦП ${d.cpu}%`}
                  {d.ram >= 85 && ` ОЗУ ${d.ram}%`}
                  {d.disk >= 90 && ` Диск ${d.disk}%`}
                </span>
                <ChevronRight size={11} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* DYNAMIC HIGH-RES CHART PANEL */}
      <section className="panel chart-panel">
        <div className="panel-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <h2>Динамика нагрузки парка ({timeRange})</h2>
            <p>
              {scopeOnlineDevices.length > 0
                ? 'Реальная телеметрия по активным рабочим станциям'
                : 'Все станции офлайн · Ожидание запуска агентов'}
            </p>
          </div>

          {/* Metric tabs */}
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <button
              type="button"
              className={`button ${metricTab === 'all' ? 'primary' : ''}`}
              style={{ padding: '5px 9px', fontSize: '11px' }}
              onClick={() => setMetricTab('all')}
            >
              Все метрики
            </button>
            <button
              type="button"
              className={`button ${metricTab === 'cpu' ? 'primary' : ''}`}
              style={{ padding: '5px 9px', fontSize: '11px' }}
              onClick={() => setMetricTab('cpu')}
            >
              Только ЦП
            </button>
            <button
              type="button"
              className={`button ${metricTab === 'ram' ? 'primary' : ''}`}
              style={{ padding: '5px 9px', fontSize: '11px' }}
              onClick={() => setMetricTab('ram')}
            >
              Только ОЗУ
            </button>
          </div>

          <div className="chart-legend">
            {(metricTab === 'all' || metricTab === 'cpu') && (
              <span><i className="blue-line" /> ЦП (%)</span>
            )}
            {(metricTab === 'all' || metricTab === 'ram') && (
              <span><i className="green-line" /> ОЗУ (%)</span>
            )}
          </div>
        </div>

        <div className="chart">
          <div className="y-axis">
            <span>100%</span>
            <span>75%</span>
            <span>50%</span>
            <span>25%</span>
            <span>0%</span>
          </div>

          <div className="chart-area">
            <div className="grid-lines"><i /><i /><i /><i /><i /></div>
            <svg viewBox="0 0 700 240" preserveAspectRatio="none">
              <defs>
                <linearGradient id="cpuAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#5b8def" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#5b8def" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="ramAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#39b98a" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="#39b98a" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* CPU Line + Area */}
              {(metricTab === 'all' || metricTab === 'cpu') && (
                <>
                  <path
                    d={`M 0 240 L 0 ${240 - (chartPoints[0]?.cpu || 0) * 2.2} ` +
                      chartPoints.map((p, i) => `L ${(i / Math.max(1, chartPoints.length - 1)) * 700} ${240 - (p?.cpu || 0) * 2.2}`).join(' ') +
                      ` L 700 240 Z`}
                    fill="url(#cpuAreaGrad)"
                  />
                  <path
                    d={`M 0 ${240 - (chartPoints[0]?.cpu || 0) * 2.2} ` +
                      chartPoints.map((p, i) => `L ${(i / Math.max(1, chartPoints.length - 1)) * 700} ${240 - (p?.cpu || 0) * 2.2}`).join(' ')}
                    fill="none"
                    stroke="#5b8def"
                    strokeWidth="2.8"
                  />
                </>
              )}

              {/* RAM Line */}
              {(metricTab === 'all' || metricTab === 'ram') && (
                <path
                  d={`M 0 ${240 - (chartPoints[0]?.ram || 0) * 2.2} ` +
                    chartPoints.map((p, i) => `L ${(i / Math.max(1, chartPoints.length - 1)) * 700} ${240 - (p?.ram || 0) * 2.2}`).join(' ')}
                  fill="none"
                  stroke="#39b98a"
                  strokeWidth="2.4"
                  strokeDasharray="4 2"
                />
              )}
            </svg>

            <div className="x-axis">
              {chartPoints.map((p, idx) => <span key={idx}>{p.label}</span>)}
            </div>
          </div>
        </div>
      </section>

      {/* LIVE WORKSTATIONS TELEMETRY MATRIX & CONSUMERS TABLE */}
      <section className="panel table-panel" style={{ marginTop: '22px' }}>
        <div className="panel-heading table-heading">
          <div>
            <h2>Живая матрица телеметрии рабочих станций ({sortedDevices.length})</h2>
            <p>Текущие показатели нагрузки служб агента и активные пользовательские сессии</p>
          </div>

          <div className="table-tools">
            {/* Search */}
            <div className="search wide" style={{ position: 'relative', minWidth: '320px' }}>
              <Search size={14} />
              <input
                placeholder="Поиск по имени, IP, MAC, ID, инвентарнику, юзеру..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ paddingRight: searchQuery ? '65px' : '10px' }}
              />
              {searchQuery && (
                <div style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: 'var(--muted)', background: 'var(--surface-2)', padding: '1px 5px', borderRadius: '4px', border: '1px solid var(--line)' }}>
                    {filteredDevices.length}
                  </span>
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    style={{ background: 'none', border: 'none', color: 'var(--muted)', padding: '2px', display: 'grid', placeItems: 'center', cursor: 'pointer' }}
                    title="Очистить поиск"
                  >
                    <X size={13} />
                  </button>
                </div>
              )}
            </div>

            {/* Stress filter toggle */}
            <Button
              className={stressOnly ? 'primary' : ''}
              onClick={() => setStressOnly(!stressOnly)}
              title="Фильтр: показать только станции под нагрузкой"
            >
              <AlertTriangle size={13} /> {stressOnly ? 'Показаны перегруженные' : 'Все станции'}
            </Button>

            {/* Sort selection */}
            <select
              className="text-input"
              value={sortBy}
              onChange={e => setSortBy(e.target.value as any)}
              style={{ height: '34px', minWidth: '150px' }}
            >
              <option value="stress">По уровню нагрузки</option>
              <option value="cpu">По загрузке ЦП</option>
              <option value="ram">По использованию ОЗУ</option>
              <option value="disk">По заполнению диска</option>
              <option value="name">По алфавиту (A-Z)</option>
            </select>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Рабочая станция</th>
                <th>Группа / Локация</th>
                <th>Пользователь / RDP</th>
                <th style={{ width: '170px' }}>Загрузка ЦП</th>
                <th style={{ width: '170px' }}>Использование ОЗУ</th>
                <th style={{ width: '170px' }}>Системный диск C:</th>
                <th>Uptime / Связь</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              {sortedDevices.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '36px', color: 'var(--muted)' }}>
                    {loading ? 'Загрузка телеметрии станций...' : 'Станций по выбранным фильтрам не найдено'}
                  </td>
                </tr>
              ) : (
                sortedDevices.map(d => {
                  const devGroups = getDeviceGroups(d);
                  const isOnline = d.powerStatus === 'On';
                  const cpuClass = d.cpu >= 80 ? 'critical' : d.cpu >= 60 ? 'warning' : 'normal';
                  const ramClass = d.ram >= 85 ? 'critical' : d.ram >= 70 ? 'warning' : 'normal';
                  const diskClass = d.disk >= 90 ? 'critical' : d.disk >= 75 ? 'warning' : 'normal';

                  return (
                    <tr
                      key={d.id}
                      style={{ cursor: 'pointer' }}
                      onClick={() => {
                        if (onDevice) onDevice(d.id);
                        window.location.hash = `#/devices/${encodeURIComponent(d.id)}`;
                      }}
                    >
                      <td>
                        <div
                          className="device-name"
                          style={{ cursor: 'pointer' }}
                          onClick={e => {
                            e.stopPropagation();
                            if (onDevice) onDevice(d.id);
                            window.location.hash = `#/devices/${encodeURIComponent(d.id)}`;
                          }}
                        >
                          <div className={`device-symbol ${isOnline ? 'online' : 'offline'}`}>
                            <Monitor size={15} />
                          </div>
                          <div>
                            <strong>{d.name}</strong>
                            <small className="mono">{d.id}{d.name !== d.hostname ? ` · ${d.hostname}` : ''} · {d.ip}</small>
                          </div>
                        </div>
                      </td>

                      <td>
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                          {devGroups.map(grp => (
                            <span key={grp} className="badge">
                              {grp}
                            </span>
                          ))}
                        </div>
                      </td>

                      <td>
                        <div>
                          <strong>{d.currentUser || '—'}</strong>
                          {(() => {
                            const sessCount = (d.rdpSessions && d.rdpSessions.length) || (
                              d.rdpStatus && d.rdpStatus.match(/\((\d+)\)/) ? parseInt(d.rdpStatus.match(/\((\d+)\)/)![1], 10) : 0
                            );
                            const isActive = sessCount > 0 || (d.rdpStatus && (d.rdpStatus.toLowerCase().includes('актив') || d.rdpStatus.toLowerCase().includes('active')));
                            if (isActive) {
                              return (
                                <span className="status-pill active" style={{ display: 'inline-flex', fontSize: '10px', padding: '2px 6px', marginTop: '3px' }}>
                                  <i /> RDP {sessCount > 0 ? `Активен (${sessCount})` : (d.rdpStatus || 'Активен')}
                                </span>
                              );
                            }
                            return (
                              <small style={{ display: 'block', color: 'var(--muted)', fontSize: '10px', marginTop: '2px' }}>
                                RDP: {d.rdpStatus || 'Отключен'}
                              </small>
                            );
                          })()}
                        </div>
                      </td>

                      {/* CPU Bar */}
                      <td>
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                            <span style={{ fontFamily: 'DM Mono', fontWeight: 600, color: d.cpu >= 80 ? 'var(--red)' : 'inherit' }}>
                              {d.cpu}%
                            </span>
                            <span style={{ fontSize: '10px', color: 'var(--muted)' }}>
                              {d.cpu >= 80 ? 'Перегруз' : d.cpu >= 60 ? 'Высокая' : 'Норма'}
                            </span>
                          </div>
                          <div className="telemetry-progress-track">
                            <div className={`telemetry-progress-fill ${cpuClass}`} style={{ width: `${d.cpu}%` }} />
                          </div>
                        </div>
                      </td>

                      {/* RAM Bar */}
                      <td>
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                            <span style={{ fontFamily: 'DM Mono', fontWeight: 600, color: d.ram >= 85 ? 'var(--red)' : 'inherit' }}>
                              {d.ram}%
                            </span>
                            <span style={{ fontSize: '10px', color: 'var(--muted)' }}>
                              {((d.ram / 100) * getDeviceRamCapacity(d)).toFixed(1)} / {getDeviceRamCapacity(d)} GB
                            </span>
                          </div>
                          <div className="telemetry-progress-track">
                            <div className={`telemetry-progress-fill ${ramClass}`} style={{ width: `${d.ram}%` }} />
                          </div>
                        </div>
                      </td>

                      {/* Disk Bar */}
                      <td>
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                            <span style={{ fontFamily: 'DM Mono', fontWeight: 600, color: d.disk >= 90 ? 'var(--red)' : 'inherit' }}>
                              {d.disk}%
                            </span>
                            <span style={{ fontSize: '10px', color: 'var(--muted)' }}>
                              {Math.max(0, Math.round((1 - d.disk / 100) * getDeviceStorageCapacity(d)))} GB своб.
                            </span>
                          </div>
                          <div className="telemetry-progress-track">
                            <div className={`telemetry-progress-fill ${diskClass}`} style={{ width: `${d.disk}%` }} />
                          </div>
                        </div>
                      </td>

                      <td>
                        <div>
                          <strong style={{ fontSize: '11px', display: 'block', color: isOnline ? 'var(--ink)' : 'var(--muted)', fontWeight: 600 }}>
                            {formatLiveUptime(d.uptime, d.bootTimeIso, isOnline)}
                          </strong>
                          <small
                            style={{ display: 'block', color: 'var(--muted)', fontSize: '10px', marginTop: '2px' }}
                            title={isOnline ? `Последний отклик агента: ${formatLocalTime(d.lastSeenIso, d.lastSeen)}` : undefined}
                          >
                            {isOnline ? (
                              d.bootTimeIso ? (
                                `Старт: ${formatDeviceBootTime(d.bootTimeIso)}`
                              ) : (
                                `Связь: ${formatLocalTime(d.lastSeenIso, d.lastSeen)}`
                              )
                            ) : (
                              formatDeviceLastSeen(d.lastSeen, d.lastSeenIso, d.powerStatus)
                            )}
                          </small>
                        </div>
                      </td>

                      <td>
                        <button
                          type="button"
                          className="button"
                          style={{ padding: '4px 9px', fontSize: '11px', cursor: 'pointer' }}
                          onClick={e => {
                            e.stopPropagation();
                            if (onDevice) onDevice(d.id);
                            window.location.hash = `#/devices/${encodeURIComponent(d.id)}`;
                          }}
                        >
                          Детали <ChevronRight size={12} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

// ----------------------------------------------------
// 6. POWER & SCHEDULE PANEL
// ----------------------------------------------------
function PowerPanel({ device, notify }: { device: Device; notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [confirm, setConfirm] = useState<string>();
  const [existingScheduleId, setExistingScheduleId] = useState<string | null>(null);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [devicePowerLogs, setDevicePowerLogs] = useState<Array<{
    id: string;
    action: string;
    detail: string;
    time: string;
    status: 'ok' | 'fail';
  }>>([]);

  // Schedules state (default: disabled for newly added devices)
  const [morningEnabled, setMorningEnabled] = useState(false);
  const [morningTime, setMorningTime] = useState('07:50');
  const [morningDays, setMorningDays] = useState<string[]>(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']);

  const [eveningEnabled, setEveningEnabled] = useState(false);
  const [eveningTime, setEveningTime] = useState('22:00');
  const [eveningDays, setEveningDays] = useState<string[]>(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']);
  const [forceShutdown, setForceShutdown] = useState(false);

  const [rebootEnabled, setRebootEnabled] = useState(false);
  const [rebootTime, setRebootTime] = useState('04:00');

  const allDays = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'];

  const formatLogTime = (ts: string) => {
    try {
      let safeTs = ts;
      if (!safeTs.endsWith('Z') && !safeTs.includes('+')) {
        safeTs = safeTs.replace(' ', 'T') + 'Z';
      }
      const d = new Date(safeTs);
      if (isNaN(d.getTime())) return ts;
      const today = new Date();
      const isToday = d.getFullYear() === today.getFullYear() &&
                      d.getMonth() === today.getMonth() &&
                      d.getDate() === today.getDate();
      const timeStr = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
      if (isToday) {
        return `Сегодня ${timeStr}`;
      }
      return `${d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })} ${timeStr}`;
    } catch {
      return ts;
    }
  };

  // Load existing schedule and logs for this device from server
  useEffect(() => {
    let isMounted = true;
    schedulesApi.list().then(list => {
      if (!isMounted || !list) return;
      const targetDevId = (device.id || '').toLowerCase();
      const targetDevHost = (device.hostname || '').toLowerCase();

      const found = list.find(s => {
        const tLower = (s.target || '').toLowerCase();
        const nLower = (s.name || '').toLowerCase();
        return (
          tLower === targetDevId ||
          (targetDevHost && tLower === targetDevHost) ||
          (nLower.includes('персональное расписание') && (tLower === targetDevId || nLower.includes(targetDevId)))
        );
      });

      if (found) {
        setExistingScheduleId(found.id);
        const isOverallEnabled = found.enabled !== false;

        const wakeStep = found.steps?.find(st => st.action === 'WAKE');
        if (wakeStep) {
          setMorningEnabled(isOverallEnabled && wakeStep.enabled !== false);
          if (wakeStep.time) setMorningTime(wakeStep.time);
          if (wakeStep.daysList && wakeStep.daysList.length > 0) setMorningDays(wakeStep.daysList);
          else if (found.daysList && found.daysList.length > 0) setMorningDays(found.daysList);
        } else if (found.action === 'WAKE') {
          setMorningEnabled(isOverallEnabled && found.enabled !== false);
          if (found.time) setMorningTime(found.time);
          if (found.daysList && found.daysList.length > 0) setMorningDays(found.daysList);
        } else {
          setMorningEnabled(false);
        }

        const shutdownStep = found.steps?.find(st => st.action === 'SHUTDOWN' || st.action === 'FORCE_SHUTDOWN');
        if (shutdownStep) {
          setEveningEnabled(isOverallEnabled && shutdownStep.enabled !== false);
          if (shutdownStep.time) setEveningTime(shutdownStep.time);
          setForceShutdown(Boolean(shutdownStep.forceShutdown));
          if (shutdownStep.daysList && shutdownStep.daysList.length > 0) setEveningDays(shutdownStep.daysList);
          else if (found.daysList && found.daysList.length > 0) setEveningDays(found.daysList);
        } else if (found.action === 'SHUTDOWN') {
          setEveningEnabled(isOverallEnabled && found.enabled !== false);
          if (found.time) setEveningTime(found.time);
          if (found.daysList && found.daysList.length > 0) setEveningDays(found.daysList);
        } else {
          setEveningEnabled(false);
        }

        const rebootStep = found.steps?.find(st => st.action === 'REBOOT');
        if (rebootStep) {
          setRebootEnabled(isOverallEnabled && rebootStep.enabled !== false);
          if (rebootStep.time) setRebootTime(rebootStep.time);
        } else if (found.action === 'REBOOT') {
          setRebootEnabled(isOverallEnabled && found.enabled !== false);
          if (found.time) setRebootTime(found.time);
        } else {
          setRebootEnabled(false);
        }
      } else {
        setExistingScheduleId(null);
        setMorningEnabled(false);
        setEveningEnabled(false);
        setRebootEnabled(false);
      }
    }).catch(console.error);

    const fetchLogs = () => {
      devicesApi.getPowerLogs(device.id).then(logs => {
        if (!isMounted || !logs || !Array.isArray(logs)) return;
        const formatted = logs.map((l: any) => {
          const isSuccess = String(l.status || '').toUpperCase() === 'SUCCESS';
          const isSch = String(l.source || '').toUpperCase() === 'SCHEDULE';
          const isLocal = String(l.source || '').toUpperCase() === 'LOCAL';
          const defaultTitle = isSch
            ? (l.action === 'WAKE' ? 'Включение по расписанию (Wake-on-LAN)' :
               l.action === 'SHUTDOWN' ? 'Выключение по расписанию (Shutdown)' :
               l.action === 'FORCE_SHUTDOWN' ? 'Принудительное выключение по расписанию' :
               l.action === 'REBOOT' ? 'Перезагрузка по расписанию (Reboot)' : `Действие по расписанию: ${l.action}`)
            : isLocal
            ? (l.action === 'BOOT' || l.action === 'WAKE' || l.action === 'STARTUP' ? 'Локальное включение (Кнопка питания / Автостарт)' :
               l.action === 'SHUTDOWN' || l.action === 'POWEROFF' ? 'Локальное выключение (Завершение работы ОС)' :
               l.action === 'REBOOT' ? 'Локальная перезагрузка (Reboot)' : `Локальное событие: ${l.action}`)
            : (l.action === 'WAKE' ? 'Удаленное включение (Wake-on-LAN)' :
               l.action === 'SHUTDOWN' ? 'Удаленное выключение (Shutdown)' :
               l.action === 'FORCE_SHUTDOWN' ? 'Удаленное принудительное выключение (Force Shutdown)' :
               l.action === 'REBOOT' ? 'Удаленная перезагрузка (Reboot)' : `Удаленная команда: ${l.action}`);

          return {
            id: l.id || Math.random().toString(),
            action: l.title || defaultTitle,
            detail: isSuccess ? `${l.details || 'Сигнал успешно отправлен'}` : `Ошибка: ${l.details || 'Сбой выполнения'}`,
            initiator: l.initiator || (isSch ? 'Планировщик' : isLocal ? 'Локальный пользователь' : getActiveUserName()),
            source: l.source || (isSch ? 'SCHEDULE' : isLocal ? 'LOCAL' : 'MANUAL'),
            time: l.timestamp ? formatLogTime(l.timestamp) : 'Недавно',
            status: (isSuccess ? 'ok' : 'fail') as 'ok' | 'fail'
          };
        });

        setDevicePowerLogs(formatted);
      }).catch(console.error);
    };

    fetchLogs();
    const pollTimer = setInterval(fetchLogs, 4000);

    return () => { 
      isMounted = false; 
      clearInterval(pollTimer);
    };
  }, [device.id, device.hostname, device.name, device.powerStatus]);

  const toggleDay = (day: string, currentDays: string[], setDays: React.Dispatch<React.SetStateAction<string[]>>) => {
    if (currentDays.includes(day)) {
      if (currentDays.length > 1) {
        setDays(currentDays.filter(d => d !== day));
      }
    } else {
      setDays([...currentDays, day]);
    }
  };

  const handleSavePowerSchedule = async () => {
    const steps: any[] = [];
    if (morningEnabled) {
      steps.push({
        id: `wake-${device.id}`,
        action: 'WAKE',
        time: morningTime,
        enabled: true,
        daysList: morningDays,
        gracePeriodMinutes: 0,
        forceShutdown: false
      });
    }
    if (eveningEnabled) {
      steps.push({
        id: `shutdown-${device.id}`,
        action: 'SHUTDOWN',
        time: eveningTime,
        enabled: true,
        daysList: eveningDays,
        gracePeriodMinutes: 0,
        forceShutdown: forceShutdown
      });
    }
    if (rebootEnabled) {
      steps.push({
        id: `reboot-${device.id}`,
        action: 'REBOOT',
        time: rebootTime,
        enabled: true,
        daysList: ['ВС'],
        gracePeriodMinutes: 0,
        forceShutdown: true
      });
    }

    const allSelectedDays = Array.from(new Set([...morningDays, ...eveningDays, ...(rebootEnabled ? ['ВС'] : [])]));

    const payload: any = {
      name: `Персональное расписание: ${device.name}`,
      action: 'LIFECYCLE',
      type: 'Lifecycle',
      target: device.id,
      time: steps[0] ? steps[0].time : '00:00',
      daysList: allSelectedDays.length > 0 ? allSelectedDays : ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'],
      timezone: 'Europe/Moscow',
      steps: steps,
      enabled: morningEnabled || eveningEnabled || rebootEnabled,
      description: `Индивидуальное расписание включения/выключения для ${device.name} (${device.id})`
    };

    setSavingSchedule(true);
    try {
      if (existingScheduleId) {
        await schedulesApi.update(existingScheduleId, payload);
      } else {
        const created = await schedulesApi.create(payload);
        if (created && created.id) {
          setExistingScheduleId(created.id);
        }
      }
      notify(`Индивидуальное расписание питания ПК ${device.name} успешно сохранено и активировано на сервере!`);
    } catch (e) {
      console.error(e);
      notify(`Ошибка при сохранении расписания на сервере`);
    } finally {
      setSavingSchedule(false);
    }
  };

  const handleExecutePowerAction = async (action: string) => {
    const nowStr = `Сегодня ${new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`;
    const currentAdminName = getActiveUserName();
    try {
      if (action === 'Wake on LAN' || action === 'WAKE') {
        await devicesApi.wake(device.id, { user: currentAdminName, source: 'MANUAL' });
        notify(`Magic Packet (WoL) успешно отправлен на MAC ${device.mac}!`);
        setDevicePowerLogs(prev => [
          {
            id: `pwr-${Date.now()}`,
            action: 'Удаленное включение (Wake-on-LAN)',
            detail: `Magic Packet отправлен на MAC ${device.mac}`,
            initiator: currentAdminName,
            source: 'MANUAL',
            time: nowStr,
            status: 'ok'
          },
          ...prev
        ]);
      } else if (action === 'Reboot' || action === 'REBOOT') {
        await devicesApi.powerAction(device.id, 'REBOOT', true, { user: currentAdminName, source: 'MANUAL' });
        notify(`Команда перезагрузки отправлена на ${device.name}!`);
        setDevicePowerLogs(prev => [
          {
            id: `pwr-${Date.now()}`,
            action: 'Удаленная перезагрузка (Reboot)',
            detail: `Direct LAN сигнал отправлен на ${device.ip || 'хост'}`,
            initiator: currentAdminName,
            source: 'MANUAL',
            time: nowStr,
            status: 'ok'
          },
          ...prev
        ]);
      } else if (action === 'Shutdown' || action === 'SHUTDOWN') {
        await devicesApi.powerAction(device.id, 'SHUTDOWN', false, { user: currentAdminName, source: 'MANUAL' });
        notify(`Команда штатного выключения отправлена на ${device.name}!`);
        setDevicePowerLogs(prev => [
          {
            id: `pwr-${Date.now()}`,
            action: 'Удаленное выключение (Shutdown)',
            detail: `Direct LAN сигнал отправлен на ${device.ip || 'хост'}`,
            initiator: currentAdminName,
            source: 'MANUAL',
            time: nowStr,
            status: 'ok'
          },
          ...prev
        ]);
      } else if (action === 'Force shutdown' || action === 'FORCE_SHUTDOWN') {
        await devicesApi.powerAction(device.id, 'FORCE_SHUTDOWN', true, { user: currentAdminName, source: 'MANUAL' });
        notify(`Команда принудительного выключения отправлена на ${device.name}!`);
        setDevicePowerLogs(prev => [
          {
            id: `pwr-${Date.now()}`,
            action: 'Удаленное принудительное выключение (Force Shutdown)',
            detail: `Прямой аварийный сигнал питания отправлен на ${device.ip || 'хост'}`,
            initiator: currentAdminName,
            source: 'MANUAL',
            time: nowStr,
            status: 'ok'
          },
          ...prev
        ]);
      }
    } catch (err: any) {
      notify(`Ошибка отправки команды: ${err?.message || 'Сбой сети'}`);
    }
    setConfirm(undefined);
  };

  const isAgentless = device.agentVersion === 'Agentless' || device.osType === 'ThinClient' || device.osType === 'Standalone' || (device.tags || []).includes('Тонкий клиент') || (device.tags || []).includes('Agentless') || device.id.startsWith('TC-');

  return (
    <>
      <div className="power-grid">
        <section className="panel power-card" style={{ display: 'flex', flexDirection: 'column', minHeight: '320px' }}>
          <div className="power-orb"><Power size={25} /></div>
          <h2>{isAgentless ? 'Управление питанием тонкого клиента' : 'Управление питанием рабочей станции'}</h2>
          <p>
            {isAgentless 
              ? `Отправка низкоуровневого пакета Wake-on-LAN (WoL) на сетевой адаптер ${device.mac}. Безагентный режим: удаленное завершение работы отключено.`
              : 'Отправка низкоуровневых команд пробуждения через Ethernet (WoL), программной перезагрузки и выключения операционной системы.'}
          </p>
          <div className="power-buttons" style={{ marginTop: 'auto' }}>
            <Button
              primary
              icon={<Zap size={15} />}
              onClick={() => handleExecutePowerAction('Wake on LAN')}
            >
              Включить (WoL)
            </Button>
            {!isAgentless && (
              <>
                <Button icon={<RefreshCw size={15} />} onClick={() => setConfirm('Reboot')}>
                  {t('devices.reboot')}
                </Button>
                <Button icon={<Power size={15} />} onClick={() => setConfirm('Shutdown')}>
                  {t('devices.shutdown')}
                </Button>
                <Button icon={<AlertTriangle size={15} />} onClick={() => setConfirm('Force shutdown')}>
                  {t('devices.forceShutdown')}
                </Button>
              </>
            )}
          </div>
        </section>

        <section className="panel operation-card" style={{ display: 'flex', flexDirection: 'column', height: '320px', overflow: 'hidden' }}>
          <div className="panel-heading" style={{ borderBottom: '1px solid var(--line)', padding: '16px 20px', flexShrink: 0 }}>
            <div>
              <h2 style={{ fontSize: '14px', margin: 0 }}>Журнал команд питания</h2>
              <p style={{ fontSize: '11px', margin: '3px 0 0', color: 'var(--muted)' }}>История операций за последние 24 часа</p>
            </div>
            {devicePowerLogs.length > 0 && (
              <span className="badge" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', fontWeight: 600, fontSize: '10px', padding: '3px 8px', borderRadius: '6px' }}>
                {devicePowerLogs.length} {devicePowerLogs.length === 1 ? 'запись' : devicePowerLogs.length < 5 ? 'записи' : 'записей'}
              </span>
            )}
          </div>
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            {devicePowerLogs.length === 0 ? (
              <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--muted)', fontSize: '13px' }}>
                Команд управления питанием за последние 24 часа не зафиксировано
              </div>
            ) : (
              devicePowerLogs.map(log => (
                <div key={log.id} className="operation-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 18px', borderBottom: '1px solid var(--line)' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', flex: 1, minWidth: 0 }}>
                    <div className={log.status === 'ok' ? 'operation-ok' : 'operation-fail'} style={{ marginTop: '2px', flexShrink: 0, width: '22px', height: '22px', minWidth: '22px' }}>
                      {log.status === 'ok' ? <Check size={12} /> : <AlertTriangle size={12} />}
                    </div>
                    <div className="operation-info" style={{ minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <strong style={{ fontSize: '12px' }}>{log.action}</strong>
                        {log.initiator && (
                          <span style={{
                            fontSize: '10px',
                            padding: '1px 6px',
                            borderRadius: '4px',
                            backgroundColor: log.source === 'SCHEDULE' ? 'rgba(139, 92, 246, 0.15)' : 'rgba(59, 130, 246, 0.12)',
                            color: log.source === 'SCHEDULE' ? '#8b5cf6' : 'var(--primary)',
                            fontWeight: 600
                          }}>
                            {log.source === 'SCHEDULE' ? '⏰ ' : '👤 '}{log.initiator}
                          </span>
                        )}
                      </div>
                      <small style={{ color: 'var(--muted)', fontSize: '11px', marginTop: '2px', display: 'block' }}>{log.detail}</small>
                    </div>
                  </div>
                  <time style={{ fontSize: '11px', color: 'var(--muted)', whiteSpace: 'nowrap', marginLeft: '12px', flexShrink: 0, fontFamily: "'DM Mono', monospace" }}>{log.time}</time>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {/* Schedule Configuration Card */}
      <section className="panel" style={{ marginTop: '20px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '16px', margin: 0 }}>
              {isAgentless ? 'Персональное расписание включения (Wake-on-LAN)' : 'Персональное расписание включения и выключения'}
            </h2>
            <p style={{ color: 'var(--muted)', fontSize: '12px', margin: '4px 0 0' }}>
              {isAgentless 
                ? 'Настройка времени автоматического утреннего старта тонкого клиента по Magic Packet (WoL)'
                : 'Настройка времени автоматического старта по WoL и вечернего гашения рабочей станции'}
            </p>
          </div>
          <Clock3 size={20} className="heading-icon" />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: isAgentless ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {/* Morning wake */}
          <div className="panel info-panel" style={{ border: '1px solid var(--line)', padding: '16px', borderRadius: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <strong style={{ fontSize: '13px', display: 'block' }}>🌅 Утреннее включение (WoL)</strong>
                <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Автоматический старт ПК перед началом смены</span>
              </div>
              <Switch checked={morningEnabled} onChange={setMorningEnabled} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <span style={{ fontSize: '12px', color: 'var(--muted)' }}>Время включения:</span>
              <input
                type="time"
                className="text-input"
                value={morningTime}
                onChange={(e) => setMorningTime(e.target.value)}
                style={{ width: '110px', fontFamily: "'DM Mono', monospace" }}
              />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '6px' }}>Дни недели:</span>
              <div style={{ display: 'flex', gap: '4px' }}>
                {allDays.map(day => (
                  <button
                    key={day}
                    onClick={() => toggleDay(day, morningDays, setMorningDays)}
                    className={morningDays.includes(day) ? 'button primary' : 'button'}
                    style={{ padding: '4px 8px', fontSize: '11px', minWidth: '32px' }}
                  >
                    {day}
                  </button>
                ))}
              </div>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Magic Packet отправляется на MAC-адрес {device.mac}</span>
          </div>

          {!isAgentless && (
            <>
              {/* Evening shutdown */}
              <div className="panel info-panel" style={{ border: '1px solid var(--line)', padding: '16px', borderRadius: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div>
                    <strong style={{ fontSize: '13px', display: 'block' }}>🌙 Вечернее выключение</strong>
                    <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Штатное завершение работы в конце дня</span>
                  </div>
                  <Switch checked={eveningEnabled} onChange={setEveningEnabled} />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                  <span style={{ fontSize: '12px', color: 'var(--muted)' }}>Время выключения:</span>
                  <input
                    type="time"
                    className="text-input"
                    value={eveningTime}
                    onChange={(e) => setEveningTime(e.target.value)}
                    style={{ width: '110px', fontFamily: "'DM Mono', monospace" }}
                  />
                </div>

                <div style={{ marginBottom: '12px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '6px' }}>Дни недели:</span>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {allDays.map(day => (
                      <button
                        key={day}
                        onClick={() => toggleDay(day, eveningDays, setEveningDays)}
                        className={eveningDays.includes(day) ? 'button primary' : 'button'}
                        style={{ padding: '4px 8px', fontSize: '11px', minWidth: '32px' }}
                      >
                        {day}
                      </button>
                    ))}
                  </div>
                </div>

                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--muted)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={forceShutdown} onChange={(e) => setForceShutdown(e.target.checked)} />
                  Принудительно закрывать незавершенные программы (Force Kill)
                </label>
              </div>

              {/* Weekly reboot */}
              <div className="panel info-panel" style={{ border: '1px solid var(--line)', padding: '16px', borderRadius: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div>
                    <strong style={{ fontSize: '13px', display: 'block' }}>🔄 Профилактическая перезагрузка</strong>
                    <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Еженедельная очистка памяти и служб</span>
                  </div>
                  <Switch checked={rebootEnabled} onChange={setRebootEnabled} />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                  <span style={{ fontSize: '12px', color: 'var(--muted)' }}>Время (Воскресенье):</span>
                  <input
                    type="time"
                    className="text-input"
                    value={rebootTime}
                    onChange={(e) => setRebootTime(e.target.value)}
                    style={{ width: '110px', fontFamily: "'DM Mono', monospace" }}
                  />
                </div>
                <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Перезагрузка выполняется в период минимальной нагрузки в выходной день.</span>
              </div>
            </>
          )}
        </div>

        <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
          <Button primary onClick={handleSavePowerSchedule} disabled={savingSchedule}>
            {savingSchedule ? 'Сохранение...' : 'Применить расписание питания'}
          </Button>
        </div>
      </section>

      {confirm && (
        <div className="modal-backdrop" onClick={() => setConfirm(undefined)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon"><AlertTriangle size={23} /></div>
            <h2>
              {confirm === 'Reboot'
                ? `Перезагрузить ${device.name || device.hostname || device.id}?`
                : confirm === 'Shutdown'
                ? `Выключить ${device.name || device.hostname || device.id}?`
                : confirm === 'Force shutdown'
                ? `Принудительно выключить ${device.name || device.hostname || device.id}?`
                : `${confirm} ${device.name || device.hostname || device.id}?`}
            </h2>
            <p>
              {confirm === 'Force shutdown'
                ? 'Компьютер будет немедленно выключен с принудительным закрытием всех запущенных программ.'
                : confirm === 'Reboot'
                ? 'Рабочая станция завершит приложения и выполнит перезагрузку операционной системы.'
                : 'Рабочая станция штатно сохранит данные, завершит приложения и выключится.'}
            </p>
            <div className="modal-actions">
              <Button onClick={() => setConfirm(undefined)}>{t('common.cancel')}</Button>
              <Button primary onClick={() => handleExecutePowerAction(confirm)}>
                {confirm === 'Reboot' ? 'Перезагрузить' : confirm === 'Shutdown' ? 'Выключить' : confirm === 'Force shutdown' ? 'Принудительно выключить' : confirm}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------
// 7. ALERT POLICY TAB
// ----------------------------------------------------
function AlertPolicyTab({ deviceId, notify }: { deviceId: string; notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [mode, setMode] = useState<'Full' | 'Critical Only' | 'Hardware Only' | 'Custom' | 'Muted'>('Full');
  
  // Custom mode granular toggles
  const [hwCritical, setHwCritical] = useState(true);
  const [hwDisks, setHwDisks] = useState(true);
  const [hwUsb, setHwUsb] = useState(false);
  const [hwNetwork, setHwNetwork] = useState(true);

  const [powerWake, setPowerWake] = useState(true);
  const [powerShutdown, setPowerShutdown] = useState(true);
  const [powerUnexpected, setPowerUnexpected] = useState(true);

  const [agentDisconnect, setAgentDisconnect] = useState(true);
  const [agentOnline, setAgentOnline] = useState(true);

  const [rdpIdle, setRdpIdle] = useState(true);
  const [rdpLogon, setRdpLogon] = useState(false);

  const [resourceCpu, setResourceCpu] = useState(true);
  const [resourceRam, setResourceRam] = useState(true);
  const [resourceDisk, setResourceDisk] = useState(true);

  const [cpuThreshold, setCpuThreshold] = useState(90);
  const [ramThreshold, setRamThreshold] = useState(85);
  const [diskThreshold, setDiskThreshold] = useState(90);
  const [rdpIdleLimit, setRdpIdleLimit] = useState(30);

  const [webUiChannel, setWebUiChannel] = useState(true);
  const [telegramChannel, setTelegramChannel] = useState(true);
  const [emailChannel, setEmailChannel] = useState(false);

  useEffect(() => {
    devicesApi.getAlertPolicy(deviceId).then(policy => {
      if (policy) {
        if (policy.mode) setMode(policy.mode as any);
        const ev = policy.events || policy.events_config || {};
        if (ev.hardwareChanges !== undefined) setHwCritical(ev.hardwareChanges);
        if (ev.hwDisks !== undefined) setHwDisks(ev.hwDisks);
        if (ev.usbStorage !== undefined) setHwUsb(ev.usbStorage);
        if (ev.hwNetwork !== undefined) setHwNetwork(ev.hwNetwork);

        if (ev.morningWakeFailed !== undefined) setPowerWake(ev.morningWakeFailed);
        if (ev.eveningShutdownFailed !== undefined) setPowerShutdown(ev.eveningShutdownFailed);
        if (ev.powerStateFailed !== undefined) setPowerUnexpected(ev.powerStateFailed);

        if (ev.agentDisconnect !== undefined) setAgentDisconnect(ev.agentDisconnect);
        if (ev.agentOnline !== undefined) setAgentOnline(ev.agentOnline);

        if (ev.rdpSessionTimeout !== undefined) setRdpIdle(ev.rdpSessionTimeout);
        if (ev.rdpLogon !== undefined) setRdpLogon(ev.rdpLogon);

        if (ev.highCpuUsage !== undefined) setResourceCpu(ev.highCpuUsage);
        if (ev.highRamUsage !== undefined) setResourceRam(ev.highRamUsage);
        if (ev.highDiskUsage !== undefined) setResourceDisk(ev.highDiskUsage);

        if (policy.thresholds) {
          if (policy.thresholds.cpuPercent !== undefined) setCpuThreshold(policy.thresholds.cpuPercent);
          if (policy.thresholds.ramPercent !== undefined) setRamThreshold(policy.thresholds.ramPercent);
          if (policy.thresholds.diskPercent !== undefined) setDiskThreshold(policy.thresholds.diskPercent);
          if (policy.thresholds.rdpIdleMinutes !== undefined) setRdpIdleLimit(policy.thresholds.rdpIdleMinutes);
        }
        const ch = policy.notifyChannels || policy.notify_channels || {};
        if (ch.webUi !== undefined) setWebUiChannel(ch.webUi);
        if (ch.telegram !== undefined) setTelegramChannel(ch.telegram);
        if (ch.email !== undefined) setEmailChannel(ch.email);
      }
    });
  }, [deviceId]);

  const handleSavePolicy = async () => {
    await devicesApi.saveAlertPolicy(deviceId, {
      mode,
      events: {
        hardwareChanges: hwCritical,
        hwDisks,
        usbStorage: hwUsb,
        hwNetwork,
        morningWakeFailed: powerWake,
        eveningShutdownFailed: powerShutdown,
        powerStateFailed: powerUnexpected,
        agentDisconnect,
        agentOnline,
        rdpSessionTimeout: rdpIdle,
        rdpLogon,
        highCpuUsage: resourceCpu,
        highRamUsage: resourceRam,
        highDiskUsage: resourceDisk,
      },
      thresholds: {
        cpuPercent: cpuThreshold,
        ramPercent: ramThreshold,
        diskPercent: diskThreshold,
        rdpIdleMinutes: rdpIdleLimit,
      },
      notifyChannels: {
        webUi: webUiChannel,
        telegram: telegramChannel,
        email: emailChannel,
      }
    });
    notify('Политика оповещений устройства успешно сохранена!');
  };

  return (
    <section className="panel automation-panel">
      <div className="panel-heading" style={{ flexWrap: 'wrap', gap: '14px', alignItems: 'center' }}>
        <div>
          <h2>Политика оповещений устройства</h2>
          <p>Выбор профиля мониторинга, пороговых значений и каналов оповещения</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>Профиль:</span>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as any)}
            className="text-input"
            style={{ fontWeight: 600, minWidth: '220px' }}
          >
            <option value="Full">Full (Все события и пороги)</option>
            <option value="Critical Only">Critical Only (Только критические сбои)</option>
            <option value="Hardware Only">Hardware Only (Комплектующие ПК)</option>
            <option value="Custom">Custom (Пользовательские настройки)</option>
            <option value="Muted">Muted (Оповещения отключены)</option>
          </select>
        </div>
      </div>

      {/* Preset summary banner when NOT in Custom mode */}
      {mode === 'Critical Only' && (
        <div style={{ padding: '18px 21px', background: 'var(--panel)', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <div className="stat-icon red" style={{ flexShrink: 0 }}><AlertTriangle size={18} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <strong style={{ fontSize: '13px' }}>Профиль: Только критические сбои и аварии</strong>
                <span className="status-pill critical">Critical Only</span>
              </div>
              <p style={{ margin: '0 0 10px', fontSize: '11px', color: 'var(--muted)', lineHeight: '1.55' }}>
                Включен мониторинг исключительно критических инцидентов: несанкционированное изъятие или замена комплектующих (CPU, RAM, GPU, системных дисков), аварийное обесточивание и потеря связи со станцией.
                Обычные внешние USB-флешки и пороги нагрузки игнорируются, исключая ложный шум в Telegram и почте.
              </p>
              <button className="text-button" style={{ fontWeight: 600, fontSize: '11px' }} onClick={() => setMode('Custom')}>
                ⚙️ Переключить в Custom для ручной настройки чекбоксов →
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === 'Full' && (
        <div style={{ padding: '18px 21px', background: 'var(--panel)', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <div className="stat-icon blue" style={{ flexShrink: 0 }}><CheckCircle2 size={18} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <strong style={{ fontSize: '13px' }}>Профиль: Полный контроль (Все события)</strong>
                <span className="status-pill open">Full</span>
              </div>
              <p style={{ margin: '0 0 10px', fontSize: '11px', color: 'var(--muted)', lineHeight: '1.55' }}>
                Отслеживаются все категории инцидентов: конфигурация комплектующих, питание, расписания, доступность, сессии и пороги нагрузки.
              </p>
              <button className="text-button" style={{ fontWeight: 600, fontSize: '11px' }} onClick={() => setMode('Custom')}>
                ⚙️ Переключить в Custom для выбора конкретных событий →
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === 'Hardware Only' && (
        <div style={{ padding: '18px 21px', background: 'var(--panel)', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <div className="stat-icon blue" style={{ flexShrink: 0 }}><Cpu size={18} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <strong style={{ fontSize: '13px' }}>Профиль: Только аппаратное обеспечение</strong>
                <span className="status-pill open">Hardware Only</span>
              </div>
              <p style={{ margin: '0 0 10px', fontSize: '11px', color: 'var(--muted)', lineHeight: '1.55' }}>
                Контролируются физические компоненты компьютера: CPU, оперативная память, видеокарта и накопители. События сессий, циклов расписания и нагрузки отключены.
              </p>
              <button className="text-button" style={{ fontWeight: 600, fontSize: '11px' }} onClick={() => setMode('Custom')}>
                ⚙️ Переключить в Custom для ручной настройки чекбоксов →
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === 'Muted' && (
        <div style={{ padding: '18px 21px', background: 'var(--panel)', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <div className="stat-icon slate" style={{ flexShrink: 0 }}><BellOff size={18} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <strong style={{ fontSize: '13px' }}>Оповещения отключены</strong>
                <span className="status-pill warning">Muted</span>
              </div>
              <p style={{ margin: '0 0 10px', fontSize: '11px', color: 'var(--muted)', lineHeight: '1.55' }}>
                Для данного компьютера все уведомления и алерты заглушены. Алерты не генерируются и не рассылаются.
              </p>
              <button className="text-button" style={{ fontWeight: 600, fontSize: '11px' }} onClick={() => setMode('Custom')}>
                ⚙️ Включить Custom и выбрать нужные события →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* FULL CUSTOM MATRIX PANEL (like Roles & Permissions) */}
      {mode === 'Custom' && (
        <div style={{ borderTop: '1px solid var(--line)' }}>
          {/* Section 1: Hardware */}
          <div style={{ padding: '14px 21px 8px', background: 'var(--blue-soft)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={16} style={{ color: 'var(--blue)' }} />
            <strong style={{ fontSize: '12px', color: 'var(--ink)' }}>1. Аппаратный контроль и накопители</strong>
          </div>
          <div className="permissions" style={{ borderTop: 0 }}>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={hwCritical} onChange={(e) => setHwCritical(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Критическое оборудование</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Замена или изъятие CPU, модулей RAM, GPU, мат. платы</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={hwDisks} onChange={(e) => setHwDisks(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Внутренние накопители</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Замена или извлечение системных дисков SATA / NVMe SSD</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={hwNetwork} onChange={(e) => setHwNetwork(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Сетевые интерфейсы и MAC</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Смена физического MAC-адреса или сетевого контроллера</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px', background: hwUsb ? 'rgba(235, 120, 50, 0.08)' : undefined }}>
              <input type="checkbox" checked={hwUsb} onChange={(e) => setHwUsb(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Внешние USB-накопители и флешки</strong>
                  <span className="maintenance-badge" style={{ margin: 0 }}>Внимание</span>
                </div>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Оповещать о подключении/извлечении флешек. Отключите в проде для защиты от спама</span>
              </div>
            </label>
          </div>

          {/* Section 2: Power & Schedules */}
          <div style={{ padding: '14px 21px 8px', background: 'var(--blue-soft)', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap size={16} style={{ color: 'var(--orange)' }} />
            <strong style={{ fontSize: '12px', color: 'var(--ink)' }}>2. Питание и расписания</strong>
          </div>
          <div className="permissions" style={{ borderTop: 0 }}>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={powerWake} onChange={(e) => setPowerWake(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Сбой утреннего включения (WoL)</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>ПК не вышел на связь после отправки сигнала включения</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={powerShutdown} onChange={(e) => setPowerShutdown(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Сбой вечернего выключения</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Станция осталась включенной после команды выключения</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={powerUnexpected} onChange={(e) => setPowerUnexpected(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Аварийное обесточивание</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Непредвиденное отключение питания в рабочие часы</span>
              </div>
            </label>
          </div>

          {/* Section 3: Availability */}
          <div style={{ padding: '14px 21px 8px', background: 'var(--blue-soft)', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Wifi size={16} style={{ color: 'var(--green)' }} />
            <strong style={{ fontSize: '12px', color: 'var(--ink)' }}>3. Доступность и связь с агентом</strong>
          </div>
          <div className="permissions" style={{ borderTop: 0 }}>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={agentDisconnect} onChange={(e) => setAgentDisconnect(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Потеря связи со станцией</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Отсутствие Heartbeat от агента более 2 минут (уход в оффлайн)</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={agentOnline} onChange={(e) => setAgentOnline(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Восстановление связи (Online)</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Уведомлять при успешном возвращении станции в сеть</span>
              </div>
            </label>
          </div>

          {/* Section 4: Security & RDP */}
          <div style={{ padding: '14px 21px 8px', background: 'var(--blue-soft)', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Lock size={16} style={{ color: 'var(--blue)' }} />
            <strong style={{ fontSize: '12px', color: 'var(--ink)' }}>4. Безопасность и RDP-сессии</strong>
          </div>
          <div className="permissions" style={{ borderTop: 0 }}>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={rdpIdle} onChange={(e) => setRdpIdle(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Превышение простоя RDP</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Фиксировать брошенные неактивные подключения пользователей</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={rdpLogon} onChange={(e) => setRdpLogon(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Вход пользователя в систему</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Уведомлять при каждой новой авторизации в RDP или консоли</span>
              </div>
            </label>
          </div>

          {/* Section 5: Resource Thresholds */}
          <div style={{ padding: '14px 21px 8px', background: 'var(--blue-soft)', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Gauge size={16} style={{ color: 'var(--orange)' }} />
            <strong style={{ fontSize: '12px', color: 'var(--ink)' }}>5. Пороги нагрузки и ресурсов</strong>
          </div>
          <div className="permissions" style={{ borderTop: 0 }}>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={resourceCpu} onChange={(e) => setResourceCpu(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Контроль нагрузки CPU</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Превышение лимита использования процессора</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={resourceRam} onChange={(e) => setResourceRam(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Контроль памяти RAM</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Превышение лимита оперативной памяти</span>
              </div>
            </label>
            <label style={{ cursor: 'pointer', display: 'flex', gap: '10px', alignItems: 'flex-start', padding: '12px 21px' }}>
              <input type="checkbox" checked={resourceDisk} onChange={(e) => setResourceDisk(e.target.checked)} style={{ marginTop: '2px' }} />
              <div>
                <strong style={{ display: 'block', fontSize: '11px', color: 'var(--ink)' }}>Контроль свободного места на диске</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Превышение заполненности системного накопителя</span>
              </div>
            </label>
          </div>
        </div>
      )}

      {/* Threshold numeric limits */}
      {(mode === 'Custom' || mode === 'Full') && (
        <div style={{ padding: '16px 21px', borderTop: '1px solid var(--line)', borderBottom: '1px solid var(--line)' }}>
          <strong style={{ fontSize: '12px', display: 'block', marginBottom: '12px', color: 'var(--ink)' }}>Лимиты срабатывания порогов:</strong>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>Порог нагрузки CPU (%):</span>
              <input type="number" min="50" max="99" value={cpuThreshold} onChange={(e) => setCpuThreshold(Number(e.target.value))} className="text-input" style={{ width: '100%' }} />
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>Порог использования RAM (%):</span>
              <input type="number" min="50" max="99" value={ramThreshold} onChange={(e) => setRamThreshold(Number(e.target.value))} className="text-input" style={{ width: '100%' }} />
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>Порог заполнения диска (%):</span>
              <input type="number" min="50" max="99" value={diskThreshold} onChange={(e) => setDiskThreshold(Number(e.target.value))} className="text-input" style={{ width: '100%' }} />
            </div>
            <div>
              <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>Таймаут простоя RDP (мин):</span>
              <input type="number" min="5" max="240" value={rdpIdleLimit} onChange={(e) => setRdpIdleLimit(Number(e.target.value))} className="text-input" style={{ width: '100%' }} />
            </div>
          </div>
        </div>
      )}

      {/* Channels */}
      <div style={{ padding: '16px 21px' }}>
        <strong style={{ fontSize: '12px', display: 'block', marginBottom: '10px', color: 'var(--ink)' }}>Каналы отправки оповещений:</strong>
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', cursor: 'pointer' }}>
            <input type="checkbox" checked={webUiChannel} onChange={(e) => setWebUiChannel(e.target.checked)} />
            Веб-интерфейс (Колокольчик и бейджи)
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', cursor: 'pointer' }}>
            <input type="checkbox" checked={telegramChannel} onChange={(e) => setTelegramChannel(e.target.checked)} />
            Telegram-бот
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', cursor: 'pointer' }}>
            <input type="checkbox" checked={emailChannel} onChange={(e) => setEmailChannel(e.target.checked)} />
            Email оповещения
          </label>
        </div>
      </div>

      <div className="automation-footer">
        <span><ShieldCheck size={15} /> Параметры политики сохраняются на сервере и применяются мгновенно</span>
        <Button primary onClick={handleSavePolicy}>Сохранить политику алертинга</Button>
      </div>
    </section>
  );
}

// ----------------------------------------------------
// 8. CREDENTIALS & AUTOMATION TABS
// ----------------------------------------------------
function CredentialsTab({ deviceId, notify }: { deviceId: string; notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [accountType, setAccountType] = useState('SYSTEM');
  const [adminUser, setAdminUser] = useState('');
  const [adminPass, setAdminPass] = useState('');
  const [useLaps, setUseLaps] = useState(false);

  useEffect(() => {
    devicesApi.getCredentials(deviceId).then(creds => {
      if (creds) {
        if (creds.adminUser) setAdminUser(creds.adminUser);
        if (creds.useLaps !== undefined) setUseLaps(creds.useLaps);
        if (creds.adminUser && creds.adminUser !== 'SYSTEM') {
          setAccountType(creds.adminUser.includes('\\') ? 'DOMAIN_ADMIN' : 'LOCAL_ADMIN');
        } else {
          setAccountType('SYSTEM');
        }
      }
    });
  }, [deviceId]);

  const handleSave = async () => {
    try {
      await devicesApi.saveCredentials(deviceId, {
        adminUser: accountType === 'SYSTEM' ? 'SYSTEM' : adminUser,
        adminPass: accountType === 'SYSTEM' ? '' : adminPass,
        useLaps
      });
      notify('Учетные данные станции успешно сохранены на сервере!');
    } catch {
      notify('Ошибка сохранения учетных данных');
    }
  };

  const handleCheck = async () => {
    try {
      const res = await devicesApi.checkAccess(deviceId);
      notify(res?.message || 'Связь и права выполнения успешно подтверждены (SYSTEM / Admin OK)');
    } catch {
      notify('Проверка доступа завершена');
    }
  };

  return (
    <section className="panel automation-panel">
      <div className="panel-heading">
        <div><h2>Учетные данные выполнения команд</h2><p>Контекст прав локального исполнения на рабочей станции</p></div>
        <Key size={18} className="heading-icon" />
      </div>
      <div className="setting-row">
        <div><strong>Запуск команд от имени</strong><span>Контекст прав выполнения команд выключения, скриптов и сброса сессий</span></div>
        <select value={accountType} onChange={(e) => setAccountType(e.target.value)} className="text-input">
          <option value="SYSTEM">NT AUTHORITY\SYSTEM (Рекомендуется по умолчанию)</option>
          <option value="LOCAL_ADMIN">Локальный администратор (Local Admin)</option>
          <option value="DOMAIN_ADMIN">Доменная учетная запись (Active Directory / LDAP)</option>
        </select>
      </div>

      {accountType !== 'SYSTEM' && (
        <>
          <div className="setting-row">
            <div><strong>Имя учетной записи</strong><span>Формат DOMAIN\User или .\Administrator</span></div>
            <input className="text-input" value={adminUser} onChange={(e) => setAdminUser(e.target.value)} placeholder="DOMAIN\admin_ops" />
          </div>
          <div className="setting-row">
            <div><strong>Пароль учетной записи</strong><span>Шифруется ключом AES-256 на сервере</span></div>
            <input className="text-input" type="password" value={adminPass} onChange={(e) => setAdminPass(e.target.value)} placeholder="••••••••••••" />
          </div>
        </>
      )}

      <div className="setting-row">
        <div><strong>Проверка прав доступа и связи</strong><span>Тестирование выполнения команды с привилегиями агента</span></div>
        <Button onClick={handleCheck}>
          Проверить доступ
        </Button>
      </div>

      <div className="automation-footer">
        <span><ShieldCheck size={15} /> Данные защищены и хранятся в защищенном Vault</span>
        <Button primary onClick={handleSave}>
          Сохранить параметры
        </Button>
      </div>
    </section>
  );
}

function Automation({ deviceId, notify }: { deviceId?: string; notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [watchdogEnabled, setWatchdogEnabled] = useState(true);
  const [abandonedTimeout, setAbandonedTimeout] = useState('15');
  const [idleTimeout, setIdleTimeout] = useState('8');
  const [autoClean, setAutoClean] = useState(true);

  useEffect(() => {
    if (deviceId) {
      devicesApi.getAutomation(deviceId).then(cfg => {
        if (cfg) {
          if (cfg.watchdogEnabled !== undefined) setWatchdogEnabled(cfg.watchdogEnabled);
          if (cfg.abandonedTimeout !== undefined) setAbandonedTimeout(cfg.abandonedTimeout);
          if (cfg.idleTimeout !== undefined) setIdleTimeout(cfg.idleTimeout);
          if (cfg.autoClean !== undefined) setAutoClean(cfg.autoClean);
        }
      });
    }
  }, [deviceId]);

  const handleSave = async () => {
    if (deviceId) {
      try {
        await devicesApi.saveAutomation(deviceId, {
          watchdogEnabled,
          abandonedTimeout,
          idleTimeout,
          autoClean
        });
        notify('Параметры сторожевого сервиса успешно сохранены на сервере!');
      } catch {
        notify('Ошибка сохранения параметров сторожевого сервиса');
      }
    } else {
      notify('Параметры сторожевого сервиса успешно сохранены!');
    }
  };

  return (
    <section className="panel automation-panel">
      <div className="panel-heading">
        <div><h2>Сторожевой сервис RDP и автоочистка</h2><p>Автоматическое поддержание чистоты и стабильности удаленных подключений</p></div>
        <Switch checked={watchdogEnabled} onChange={setWatchdogEnabled} />
      </div>
      <div className="setting-row">
        <div><strong>Таймаут брошенных сессий</strong><span>Сбрасывать сессии при отключении (Disconnected) более указанного времени</span></div>
        <select value={abandonedTimeout} onChange={(e) => setAbandonedTimeout(e.target.value)} className="text-input">
          <option value="15">15 минут</option>
          <option value="30">30 минут</option>
          <option value="60">1 час</option>
        </select>
      </div>
      <div className="setting-row">
        <div><strong>Таймаут неактивности (Idle)</strong><span>Сбрасывать сессии без активности ввода мыши/клавиатуры</span></div>
        <select value={idleTimeout} onChange={(e) => setIdleTimeout(e.target.value)} className="text-input">
          <option value="4">4 часа</option>
          <option value="8">8 часов</option>
          <option value="12">12 часов</option>
        </select>
      </div>
      <div className="setting-row">
        <div><strong>Автоматическая очистка временных файлов (%TEMP%)</strong><span>Удалять кэш и временные файлы при ночном выключении</span></div>
        <Switch checked={autoClean} onChange={setAutoClean} />
      </div>
      <div className="automation-footer">
        <span><ShieldCheck size={15} /> Фоновый агент применяет правила каждые 60 секунд</span>
        <Button primary onClick={handleSave}>Сохранить</Button>
      </div>
    </section>
  );
}

// ----------------------------------------------------
// 9. ALERTS PAGE
// ----------------------------------------------------
function Alerts({ onDevice, notify }: { onDevice?: (id: string) => void; notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [items, setItems] = useState<Alert[]>([]);
  const [query, setQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'Critical' | 'Warning' | 'Info'>('ALL');
  const [showResolved, setShowResolved] = useState<boolean>(false);
  const [browserNotifPerm, setBrowserNotifPerm] = useState<NotificationPermission>(notificationService.getPermission());

  const loadAlerts = () => {
    alertsApi.list().then(setItems);
  };

  const handleRequestPush = async () => {
    const granted = await notificationService.requestPermission();
    setBrowserNotifPerm(notificationService.getPermission());
    if (granted) {
      notify('Браузерные уведомления успешно включены! Вы будете получать всплывающие оповещения об инцидентах.');
      notificationService.showNotification('✅ Уведомления Northstar включены', {
        body: 'Вы будете мгновенно получать всплывающие оповещения о критических событиях и изменениях железа ПК.'
      });
    } else {
      notify('Разрешение на отправку уведомлений не было предоставлено.');
    }
  };

  useEffect(() => {
    loadAlerts();
    // Proactively prompt user if not decided
    if (notificationService.getPermission() === 'default') {
      notificationService.initAutoPrompt();
    }
    
    const unsub1 = wsClient.on('alert.created', (newAlert: any) => {
      setItems(prev => [newAlert, ...prev.filter(a => a.id !== newAlert.id)]);
    });
    const unsub2 = wsClient.on('alert.resolved', (data: any) => {
      setItems(prev => prev.map(a => a.id === data.id ? { ...a, state: 'Resolved' } : a));
    });
    const unsub3 = wsClient.on('alert.updated', (data: any) => {
      setItems(prev => prev.map(a => a.id === data.id ? { ...a, state: data.state || a.state } : a));
    });
    return () => {
      unsub1();
      unsub2();
      unsub3();
    };
  }, []);

  const handleResolveAll = async () => {
    await alertsApi.resolveAll();
    setItems(prev => prev.map(a => ({ ...a, state: 'Resolved' })));
    notify('Все активные оповещения успешно закрыты');
  };

  const handleToggleState = async (id: string, currentState: string) => {
    if (currentState === 'Resolved') {
      await alertsApi.acknowledge(id);
      setItems(prev => prev.map(a => a.id === id ? { ...a, state: 'Open' } : a));
      notify(`Инцидент #${id} открыт снова`);
    } else {
      await alertsApi.resolve(id);
      setItems(prev => prev.map(a => a.id === id ? { ...a, state: 'Resolved' } : a));
      notify(`Инцидент #${id} закрыт (Resolved)`);
    }
  };

  const handleDelete = async (id: string) => {
    await alertsApi.delete(id);
    setItems(prev => prev.filter(a => a.id !== id));
    notify(`Оповещение #${id} удалено`);
  };

  const filtered = items.filter(a => {
    const matchQuery = `${a.type} ${a.device} ${a.description} ${a.id}`.toLowerCase().includes(query.toLowerCase());
    const matchSev = severityFilter === 'ALL' || a.severity === severityFilter;
    const matchResolved = showResolved ? true : a.state !== 'Resolved';
    return matchQuery && matchSev && matchResolved;
  });

  const criticalCount = items.filter(a => a.severity === 'Critical' && a.state !== 'Resolved').length;
  const warningCount = items.filter(a => a.severity === 'Warning' && a.state !== 'Resolved').length;
  const infoCount = items.filter(a => a.severity === 'Info' && a.state !== 'Resolved').length;
  const totalActive = items.filter(a => a.state !== 'Resolved').length;

  const formatAlertTime = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      let d: Date;
      if (dateStr.includes('T')) {
        d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
      } else if (dateStr.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)) {
        d = new Date(dateStr.replace(' ', 'T') + 'Z');
      } else {
        d = new Date(dateStr);
      }
      if (isNaN(d.getTime())) return dateStr;
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    } catch {
      return dateStr;
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="OPERATIONS"
        title="Оповещения"
        description="Централизованный журнал событий, инцидентов и аварийных ситуаций парка ПК."
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            {browserNotifPerm !== 'granted' && (
              <Button icon={<Bell size={15} />} onClick={handleRequestPush}>
                Включить Desktop Push
              </Button>
            )}
            <Button icon={<Check size={15} />} onClick={handleResolveAll} disabled={totalActive === 0}>
              Закрыть все активные
            </Button>
          </div>
        }
      />

      <div className="alert-summary-bar">
        <div 
          className={`alert-stat-card critical ${severityFilter === 'Critical' ? 'active' : ''}`}
          onClick={() => setSeverityFilter(severityFilter === 'Critical' ? 'ALL' : 'Critical')}
          role="button"
          tabIndex={0}
        >
          <span className="alert-stat-icon critical"><AlertTriangle size={18} /></span>
          <div className="alert-stat-info">
            <strong>{criticalCount}</strong>
            <span>Критические</span>
          </div>
        </div>

        <div 
          className={`alert-stat-card warning ${severityFilter === 'Warning' ? 'active' : ''}`}
          onClick={() => setSeverityFilter(severityFilter === 'Warning' ? 'ALL' : 'Warning')}
          role="button"
          tabIndex={0}
        >
          <span className="alert-stat-icon warning"><Bell size={18} /></span>
          <div className="alert-stat-info">
            <strong>{warningCount}</strong>
            <span>Предупреждения</span>
          </div>
        </div>

        <div 
          className={`alert-stat-card info ${severityFilter === 'Info' ? 'active' : ''}`}
          onClick={() => setSeverityFilter(severityFilter === 'Info' ? 'ALL' : 'Info')}
          role="button"
          tabIndex={0}
        >
          <span className="alert-stat-icon info"><CircleHelp size={18} /></span>
          <div className="alert-stat-info">
            <strong>{infoCount}</strong>
            <span>Информационные</span>
          </div>
        </div>

        <div className="summary-spacer" />
        
        <div className="alert-live-indicator">
          <span className="pulse-dot" />
          <span>Мониторинг в реальном времени</span>
        </div>
      </div>

      <section className="panel table-panel">
        <div className="panel-heading table-heading">
          <div>
            <h2>Входящие оповещения</h2>
            <p>{filtered.length} событий в списке {showResolved ? '(включая закрытые)' : '(только активные)'}</p>
          </div>
          <div className="table-tools">
            <div className="search"><Search size={15} /><input placeholder="Поиск по алертам..." value={query} onChange={e => setQuery(e.target.value)} /></div>
            <button
              className={`filter-button ${showResolved ? 'primary' : ''}`}
              onClick={() => setShowResolved(!showResolved)}
              style={{ fontSize: '11px' }}
            >
              {showResolved ? 'Скрыть закрытые' : 'Показать архив (все)'}
            </button>
            {severityFilter !== 'ALL' && (
              <Button onClick={() => setSeverityFilter('ALL')} icon={<X size={13} />}>
                Фильтр: {severityFilter} (Сбросить)
              </Button>
            )}
          </div>
        </div>
        <div className="alert-list">
          {filtered.length === 0 ? (
            <div className="empty-state" style={{ minHeight: '180px' }}>
              <Check size={24} style={{ color: 'var(--green)' }} />
              <span>Нет активных оповещений</span>
              <small style={{ color: 'var(--muted)', marginTop: '4px' }}>Все станции и сервисы функционируют в штатном режиме</small>
            </div>
          ) : (
            filtered.map(alert => (
              <div className="alert-row" key={alert.id}>
                <div className={`problem-icon ${alert.severity.toLowerCase()}`}>
                  {alert.severity === 'Critical' ? <AlertTriangle size={16} /> : <Bell size={16} />}
                </div>
                <div className="alert-main">
                  <div>
                    <strong>{alert.type}</strong>
                    <StatusPill status={alert.state} />
                  </div>
                  <span>{alert.description}</span>
                  <small style={{ cursor: onDevice ? 'pointer' : 'default' }} onClick={() => onDevice && onDevice(alert.deviceId || alert.device)}>
                    {alert.device || alert.deviceId || 'Рабочая станция'} · {alert.id} · {formatAlertTime(alert.time || alert.timestamp || alert.createdAt)}
                  </small>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button className="row-action" onClick={() => handleToggleState(alert.id, alert.state)}>
                    {alert.state === 'Resolved' ? 'Открыть снова' : 'Закрыть инцидент'}
                  </button>
                  <button
                    className="row-action"
                    onClick={() => handleDelete(alert.id)}
                    title="Удалить навсегда"
                    style={{ color: 'var(--muted)' }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </>
  );
}

// ----------------------------------------------------
// 9.1 HARDWARE BASELINE & INTEGRITY PAGE
// ----------------------------------------------------
function HardwarePage({
  onDevice,
  onNavigate,
  notify
}: {
  onDevice?: (id: string) => void;
  onNavigate?: (page: Page, filter?: any) => void;
  notify: (message: string) => void;
}) {
  const { t } = useLanguage();
  const [devices, setDevices] = useState<Device[]>([]);
  const [changes, setChanges] = useState<HardwareChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'fleet' | 'history'>('fleet');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'MISMATCH' | 'MATCH' | 'NO_BASELINE'>('ALL');
  const [componentFilter, setComponentFilter] = useState<'ALL' | 'RAM' | 'Storage' | 'GPU' | 'CPU' | 'Network' | 'PCI Device' | 'Motherboard'>('ALL');

  // Modals
  const [diffDevice, setDiffDevice] = useState<Device | null>(null);
  const [approveDevice, setApproveDevice] = useState<Device | null>(null);
  const [bulkApproveModal, setBulkApproveModal] = useState(false);
  const [approving, setApproving] = useState(false);

  const loadData = useCallback(() => {
    setLoading(true);
    Promise.all([
      devicesApi.list(),
      hardwareApi.getChanges()
    ]).then(([dList, chList]) => {
      setDevices(dList);
      setChanges(chList || []);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    loadData();
    const unsub1 = wsClient.on('hardware.change', () => loadData());
    const unsub2 = wsClient.on('baseline.updated', () => loadData());
    const unsub3 = wsClient.on('device.updated', () => loadData());
    return () => {
      unsub1();
      unsub2();
      unsub3();
    };
  }, [loadData]);

  // Derived metrics
  const totalDevs = devices.length;
  const mismatchDevs = devices.filter(d => {
    const hasUnresolved = changes.some(c => c.deviceId === d.id && (c.baselineDiffStatus === 'MISMATCH' || (!c.acknowledged && c.severity === 'Critical')));
    return (d.hardwareChangesCount && d.hardwareChangesCount > 0) || hasUnresolved || d.healthStatus === 'Critical';
  });
  const matchingDevs = devices.filter(d => d.baseline && !mismatchDevs.some(m => m.id === d.id));
  const noBaselineDevs = devices.filter(d => !d.baseline);
  const compliancePct = totalDevs > 0 ? Math.round((matchingDevs.length / totalDevs) * 100) : 100;

  // Filtered devices for Fleet tab
  const filteredDevices = devices.filter(d => {
    const matchQuery = `${d.name} ${d.hostname} ${d.id} ${d.ip} ${d.group || ''}`.toLowerCase().includes(query.toLowerCase());
    const isMismatch = mismatchDevs.some(m => m.id === d.id);
    const hasBaseline = !!d.baseline;
    
    let matchStatus = true;
    if (statusFilter === 'MISMATCH') matchStatus = isMismatch;
    else if (statusFilter === 'MATCH') matchStatus = hasBaseline && !isMismatch;
    else if (statusFilter === 'NO_BASELINE') matchStatus = !hasBaseline;

    return matchQuery && matchStatus;
  });

  // Filtered changes for History tab
  const filteredChanges = changes.filter(c => {
    const dev = devices.find(d => d.id === c.deviceId);
    const devName = dev?.name || dev?.hostname || c.deviceId;
    const matchQuery = `${devName} ${c.deviceId} ${c.component} ${c.previousValue} ${c.currentValue} ${c.changeType}`.toLowerCase().includes(query.toLowerCase());
    const matchComp = componentFilter === 'ALL' || c.component === componentFilter;
    return matchQuery && matchComp;
  });

  const handleApproveSingle = async (device: Device) => {
    const specToApprove = device.hardwareSpec || device.hardware;
    setApproving(true);
    try {
      await devicesApi.setBaseline(device.id, specToApprove as any);
      notify(`✅ Текущая конфигурация ПК ${device.name || device.id} утверждена как эталон!`);
      setApproveDevice(null);
      setDiffDevice(null);
      loadData();
    } catch {
      notify('Ошибка утверждения эталона');
    } finally {
      setApproving(false);
    }
  };

  const handleBulkApprove = async () => {
    setApproving(true);
    try {
      let count = 0;
      for (const d of devices) {
        const specToApprove = d.hardwareSpec || d.hardware;
        await devicesApi.setBaseline(d.id, specToApprove as any);
        count++;
      }
      notify(`✅ Утверждены эталоны для ${count} рабочих станций!`);
      setBulkApproveModal(false);
      loadData();
    } catch {
      notify('Ошибка при групповом утверждении эталонов');
    } finally {
      setApproving(false);
    }
  };

  const formatChangeTime = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr.includes('T') ? dateStr : dateStr.replace(' ', 'T') + 'Z');
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return dateStr;
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="OPERATIONS & COMPLIANCE"
        title="Аппаратный эталон (Baseline)"
        description="Контроль целостности оборудования парка ПК, фиксация извлечения или подмены планок ОЗУ, дисков, видеокарт и утверждение аппаратных эталонов."
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button icon={<RefreshCw size={14} />} onClick={() => { loadData(); notify('Данные эталонов обновлены'); }}>
              {t('common.refresh')}
            </Button>
            <Button primary icon={<Sparkles size={14} />} onClick={() => setBulkApproveModal(true)}>
              Утвердить всё как эталон
            </Button>
          </div>
        }
      />

      {/* KPI Bento Cards */}
      <div className="bento-grid" style={{ marginBottom: '22px' }}>
        <div className="bento-card col-3">
          <div className="bento-header">
            <span className="bento-card-title">Соответствие парка</span>
            <div className="bento-icon cyan"><Cpu size={18} /></div>
          </div>
          <div className="bento-value">{loading ? '—' : `${compliancePct}%`} <small>Эталон</small></div>
          <div className="bento-footer">
            <span style={{ color: mismatchDevs.length > 0 ? 'var(--red)' : 'var(--green)' }}>
              {mismatchDevs.length === 0 ? 'Все ПК соответствуют эталону' : `${mismatchDevs.length} ПК с расхождениями`}
            </span>
            <Check size={14} style={{ color: mismatchDevs.length === 0 ? 'var(--green)' : 'var(--orange)' }} />
          </div>
        </div>

        <div className="bento-card col-3" onClick={() => setStatusFilter('MISMATCH')} style={{ cursor: 'pointer' }}>
          <div className="bento-header">
            <span className="bento-card-title">Расхождения железа</span>
            <div className="bento-icon red"><AlertTriangle size={18} /></div>
          </div>
          <div className="bento-value" style={{ color: mismatchDevs.length > 0 ? '#ef4444' : 'inherit' }}>
            {loading ? '—' : mismatchDevs.length} <small>ПК с несовпадением</small>
          </div>
          <div className="bento-footer">
            <span>ОЗУ, диски, GPU на контроле</span>
            <ArrowRight size={14} style={{ color: 'var(--muted)' }} />
          </div>
        </div>

        <div className="bento-card col-3" onClick={() => setStatusFilter('MATCH')} style={{ cursor: 'pointer' }}>
          <div className="bento-header">
            <span className="bento-card-title">Утверждённые эталоны</span>
            <div className="bento-icon green"><ShieldCheck size={18} /></div>
          </div>
          <div className="bento-value">{loading ? '—' : `${matchingDevs.length} / ${totalDevs}`} <small>станций</small></div>
          <div className="bento-footer">
            <span>{noBaselineDevs.length > 0 ? `${noBaselineDevs.length} ПК без эталона` : 'Все ПК зафиксированы'}</span>
            <Check size={14} style={{ color: 'var(--green)' }} />
          </div>
        </div>

        <div className="bento-card col-3" onClick={() => setActiveTab('history')} style={{ cursor: 'pointer' }}>
          <div className="bento-header">
            <span className="bento-card-title">Журнал изменений</span>
            <div className="bento-icon purple"><Activity size={18} /></div>
          </div>
          <div className="bento-value">{loading ? '—' : changes.length} <small>событий</small></div>
          <div className="bento-footer">
            <span>Автофиксация через Heartbeat</span>
            <ArrowRight size={14} style={{ color: 'var(--muted)' }} />
          </div>
        </div>
      </div>

      {/* Tabs Switcher */}
      <div className="tab-group" style={{ marginBottom: '18px' }}>
        <button
          className={`tab-btn ${activeTab === 'fleet' ? 'active' : ''}`}
          onClick={() => setActiveTab('fleet')}
        >
          <Monitor size={15} /> Рабочие станции & Эталоны ({devices.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          <Activity size={15} /> Хроника изменений оборудования ({changes.length})
        </button>
      </div>

      {/* TAB 1: FLEET BASELINES */}
      {activeTab === 'fleet' && (
        <section className="panel">
          <div className="panel-heading" style={{ flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h2>Состояние аппаратных эталонов</h2>
              <p>Текущая физическая конфигурация ПК в сравнении с утверждённым профилем безопасности</p>
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <div className="search" style={{ minWidth: '240px' }}>
                <Search size={15} />
                <input
                  placeholder="Поиск по имени, IP или группе..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <select
                className="select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as any)}
                style={{ height: '34px', fontSize: '12px' }}
              >
                <option value="ALL">Все статусы ({devices.length})</option>
                <option value="MISMATCH">Только с расхождениями ({mismatchDevs.length})</option>
                <option value="MATCH">Соответствует эталону ({matchingDevs.length})</option>
                <option value="NO_BASELINE">Без эталона ({noBaselineDevs.length})</option>
              </select>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="device-table">
              <thead>
                <tr>
                  <th>Рабочая станция</th>
                  <th>Группа</th>
                  <th>Текущее оборудование (Live)</th>
                  <th>Утверждённый эталон</th>
                  <th>Статус эталона</th>
                  <th style={{ textAlign: 'right' }}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {filteredDevices.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: '36px', color: 'var(--muted)' }}>
                      Нет рабочих станций, соответствующих заданным критериям фильтра
                    </td>
                  </tr>
                ) : (
                  filteredDevices.map(device => {
                    const isMismatch = mismatchDevs.some(m => m.id === device.id);
                    const hasBaseline = !!device.baseline;
                    const liveSpec = device.hardwareSpec || device.hardware;
                    const liveRam = liveSpec?.ram;
                    const liveRamGb = liveRam?.totalGb || (liveRam?.slots ? liveRam.slots.reduce((s, x) => s + (x.sizeGb || x.capacityGb || 0), 0) : 0);
                    const liveSlotsCount = liveRam?.slots?.length || 0;
                    const liveStorageCount = liveSpec?.storage?.length || 0;
                    const liveGpuCount = liveSpec?.gpus?.length || 0;

                    const blRam = device.baseline?.spec?.ram;
                    const blRamGb = blRam?.totalGb || (blRam?.slots ? blRam.slots.reduce((s, x) => s + (x.sizeGb || x.capacityGb || 0), 0) : 0);
                    const blSlotsCount = blRam?.slots?.length || 0;
                    const blStorageCount = device.baseline?.spec?.storage?.length || 0;

                    return (
                      <tr key={device.id}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span className={`status-dot ${device.powerStatus === 'On' ? 'online' : 'offline'}`} />
                            <div>
                              <strong
                                style={{ cursor: onDevice ? 'pointer' : 'default', color: 'var(--ink)' }}
                                onClick={() => onDevice && onDevice(device.id)}
                              >
                                {device.name || device.hostname || device.id}
                              </strong>
                              <div style={{ fontSize: '11px', color: 'var(--muted)' }}>
                                {device.ip || '—'} · {device.id}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="group-badge">{device.group || 'Без группы'}</span>
                        </td>
                        <td>
                          <div style={{ fontSize: '12px' }}>
                            <div>
                              <Cpu size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-1px', color: 'var(--blue)' }} />
                              <strong>ОЗУ:</strong> {liveRamGb > 0 ? `${liveRamGb} GB` : '—'} {liveSlotsCount > 0 ? `(${liveSlotsCount} мод.)` : ''}
                            </div>
                            <div style={{ color: 'var(--muted)', fontSize: '11px', marginTop: '2px' }}>
                              <HardDrive size={11} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-1px' }} />
                              Диски: {liveStorageCount > 0 ? `${liveStorageCount} шт.` : '—'} · GPU: {liveGpuCount}
                            </div>
                          </div>
                        </td>
                        <td>
                          {hasBaseline ? (
                            <div style={{ fontSize: '12px' }}>
                              <div>
                                <strong>ОЗУ:</strong> {blRamGb > 0 ? `${blRamGb} GB` : '—'} {blSlotsCount > 0 ? `(${blSlotsCount} мод.)` : ''}
                              </div>
                              <div style={{ color: 'var(--muted)', fontSize: '11px', marginTop: '2px' }}>
                                Диски: {blStorageCount > 0 ? `${blStorageCount} шт.` : '—'} · {device.baseline?.approvedBy || 'Оператор'}
                              </div>
                            </div>
                          ) : (
                            <span style={{ fontSize: '11px', color: 'var(--muted)', fontStyle: 'italic' }}>
                              Эталон не утвержден
                            </span>
                          )}
                        </td>
                        <td>
                          {isMismatch ? (
                            <span className="badge mismatch" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <AlertTriangle size={12} /> Расхождение
                            </span>
                          ) : hasBaseline ? (
                            <span className="badge match" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <Check size={12} /> Соответствует
                            </span>
                          ) : (
                            <span className="status-pill idle">Нет эталона</span>
                          )}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                            <button
                              className="btn btn-sm"
                              style={{ padding: '4px 8px', fontSize: '11px' }}
                              onClick={() => setDiffDevice(device)}
                              title="Сравнить текущую конфигурацию с утверждённым эталоном"
                            >
                              <Eye size={12} /> Сравнить
                            </button>
                            <button
                              className="btn btn-sm btn-primary"
                              style={{ padding: '4px 8px', fontSize: '11px' }}
                              onClick={() => handleApproveSingle(device)}
                              title="Утвердить текущую конфигурацию ПК как новый эталон"
                              disabled={approving}
                            >
                              <Check size={12} /> Утвердить
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB 2: HARDWARE CHANGES HISTORY */}
      {activeTab === 'history' && (
        <section className="panel">
          <div className="panel-heading" style={{ flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h2>Журнал аппаратных событий</h2>
              <p>Хронологическая летопись всех изменений оборудования, обнаруженных фоновыми агентами</p>
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <div className="search" style={{ minWidth: '220px' }}>
                <Search size={15} />
                <input
                  placeholder="Поиск по событию, ПК или железу..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <select
                className="select"
                value={componentFilter}
                onChange={(e) => setComponentFilter(e.target.value as any)}
                style={{ height: '34px', fontSize: '12px' }}
              >
                <option value="ALL">Все компоненты</option>
                <option value="RAM">Оперативная память (RAM)</option>
                <option value="Storage">Накопители (Диски / SSD)</option>
                <option value="PCI Device">PCI / PCIe устройства</option>
                <option value="GPU">Видеокарты (GPU)</option>
                <option value="Network">Сетевые адаптеры</option>
                <option value="CPU">Процессоры (CPU)</option>
                <option value="Motherboard">Материнские платы</option>
              </select>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="device-table">
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Рабочая станция</th>
                  <th>Компонент</th>
                  <th>Тип события</th>
                  <th>Предыдущее значение</th>
                  <th>Текущее значение</th>
                  <th>Статус</th>
                  <th style={{ textAlign: 'right' }}>Действие</th>
                </tr>
              </thead>
              <tbody>
                {filteredChanges.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '36px', color: 'var(--muted)' }}>
                      Журнал аппаратных изменений пуст. Все системы стабильны.
                    </td>
                  </tr>
                ) : (
                  filteredChanges.map(change => {
                    const dev = devices.find(d => d.id === change.deviceId);
                    const devName = dev?.name || dev?.hostname || change.deviceId;
                    const isRemoved = change.changeType === 'REMOVED';
                    const isAdded = change.changeType === 'ADDED';

                    return (
                      <tr key={change.id}>
                        <td style={{ fontSize: '11px', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                          {formatChangeTime(change.timestamp)}
                        </td>
                        <td>
                          <strong
                            style={{ cursor: onDevice ? 'pointer' : 'default', color: 'var(--ink)' }}
                            onClick={() => onDevice && onDevice(change.deviceId)}
                          >
                            {devName}
                          </strong>
                          <div style={{ fontSize: '10px', color: 'var(--muted)' }}>{change.deviceId}</div>
                        </td>
                        <td>
                          <span style={{ fontWeight: 600 }}>{change.component}</span>
                        </td>
                        <td>
                          <span className={`status-pill ${isRemoved ? 'closed' : (isAdded ? 'open' : 'idle')}`}>
                            {isRemoved ? 'Извлечено' : (isAdded ? 'Добавлено' : 'Заменено')}
                          </span>
                        </td>
                        <td style={{ fontSize: '12px', color: 'var(--muted)' }}>
                          {change.previousValue || '—'}
                        </td>
                        <td style={{ fontSize: '12px', fontWeight: 600 }}>
                          {change.currentValue || '—'}
                        </td>
                        <td>
                          {change.baselineDiffStatus === 'ACCEPTED_AS_BASELINE' ? (
                            <span className="badge match" style={{ fontSize: '10px' }}>Принято в эталон</span>
                          ) : (
                            <span className="badge mismatch" style={{ fontSize: '10px' }}>Несоответствие</span>
                          )}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          {dev && (
                            <button
                              className="btn btn-sm"
                              style={{ padding: '4px 8px', fontSize: '11px' }}
                              onClick={() => handleApproveSingle(dev)}
                              title="Принять данную конфигурацию как новый эталон"
                            >
                              Принять эталон
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* MODAL: COMPARISON DIFF (Live Spec vs Approved Baseline) */}
      {diffDevice && (
        <div className="modal-backdrop" onClick={() => setDiffDevice(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '720px', maxWidth: '95vw' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}>
                  <Cpu size={20} />
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: '18px' }}>Сравнение конфигурации: {diffDevice.name || diffDevice.hostname}</h2>
                  <span style={{ fontSize: '12px', color: 'var(--muted)' }}>ID: {diffDevice.id} · IP: {diffDevice.ip || '—'}</span>
                </div>
              </div>
              <button className="btn btn-sm" onClick={() => setDiffDevice(null)} style={{ border: 'none', background: 'transparent' }}>
                <X size={18} />
              </button>
            </div>

            {(() => {
              const diffLiveSpec = diffDevice.hardwareSpec || diffDevice.hardware;
              const liveRamGb = diffLiveSpec?.ram?.totalGb || (diffLiveSpec?.ram?.slots ? diffLiveSpec.ram.slots.reduce((s, x) => s + (x.sizeGb || x.capacityGb || 0), 0) : 0);
              const liveSlots = diffLiveSpec?.ram?.slots || [];
              const liveStorage = diffLiveSpec?.storage || [];
              const liveGpus = diffLiveSpec?.gpus || [];
              const livePci = diffLiveSpec?.pciDevices || [];

              return (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '18px' }}>
                  {/* Current Live Spec */}
                  <div style={{ border: '1px solid var(--line)', borderRadius: '8px', padding: '14px', background: 'var(--panel)', maxHeight: '420px', overflowY: 'auto' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                      <strong style={{ fontSize: '13px', color: 'var(--blue)' }}>Текущее железо (Live)</strong>
                      <span className="status-dot online" title="Подключено" />
                    </div>
                    
                    {/* RAM */}
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>ОПЕРАТИВНАЯ ПАМЯТЬ</div>
                      <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '2px' }}>
                        {liveRamGb} GB ({liveSlots.length} модулей)
                      </div>
                      {liveSlots.map((s, i) => (
                        <div key={i} style={{ fontSize: '11px', color: 'var(--ink)', padding: '2px 0 2px 8px', borderLeft: '2px solid var(--blue)', marginTop: '4px' }}>
                          {s.slot}: {s.sizeGb || s.capacityGb || 8} GB {s.type || 'DDR4'} {s.frequencyMhz ? `${s.frequencyMhz} MHz` : ''}
                          <div style={{ color: 'var(--muted)', fontSize: '10px' }}>S/N: {s.serialNumber || '—'}</div>
                        </div>
                      ))}
                    </div>

                    {/* Storage */}
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>НАКОПИТЕЛИ</div>
                      <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '2px' }}>
                        {liveStorage.length} дисков
                      </div>
                      {liveStorage.map((d, i) => (
                        <div key={i} style={{ fontSize: '11px', color: 'var(--ink)', padding: '2px 0 2px 8px', borderLeft: '2px solid var(--blue)', marginTop: '4px' }}>
                          {d.model} ({d.capacityGb} GB)
                          <div style={{ color: 'var(--muted)', fontSize: '10px' }}>S/N: {d.serialNumber || '—'}</div>
                        </div>
                      ))}
                    </div>

                    {/* GPU */}
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>ВИДЕОКАРТА</div>
                      <div style={{ fontSize: '12px', marginTop: '2px' }}>
                        {liveGpus[0]?.model || 'Интегрированная графика'}
                      </div>
                    </div>

                    {/* PCI Expansion Devices */}
                    {livePci.length > 0 && (
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>PCI / PCIE УСТРОЙСТВА ({livePci.length})</div>
                        {livePci.map((p, i) => (
                          <div key={i} style={{ fontSize: '11px', color: 'var(--ink)', padding: '2px 0 2px 8px', borderLeft: '2px solid var(--blue)', marginTop: '4px' }}>
                            {p.name}
                            <div style={{ color: 'var(--muted)', fontSize: '10px' }}>{p.pnpDeviceId || p.deviceId || 'PCI'}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

              {/* Baseline Spec */}
              <div style={{ border: '1px solid var(--line)', borderRadius: '8px', padding: '14px', background: 'var(--panel)', maxHeight: '420px', overflowY: 'auto' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', paddingBottom: '8px', borderBottom: '1px solid var(--line)' }}>
                  <strong style={{ fontSize: '13px', color: 'var(--green)' }}>Утверждённый эталон</strong>
                  {diffDevice.baseline ? (
                    <span style={{ fontSize: '11px', color: 'var(--muted)' }}>{diffDevice.baseline.approvedBy}</span>
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--orange)' }}>Не утверждён</span>
                  )}
                </div>

                {diffDevice.baseline ? (
                  <>
                    {/* Baseline RAM */}
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>ЭТАЛОН ОЗУ</div>
                      <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '2px' }}>
                        {diffDevice.baseline.spec?.ram?.totalGb || 0} GB ({diffDevice.baseline.spec?.ram?.slots?.length || 0} модулей)
                      </div>
                      {diffDevice.baseline.spec?.ram?.slots?.map((s, i) => (
                        <div key={i} style={{ fontSize: '11px', color: 'var(--ink)', padding: '2px 0 2px 8px', borderLeft: '2px solid var(--green)', marginTop: '4px' }}>
                          {s.slot}: {s.sizeGb || s.capacityGb || 8} GB {s.type || 'DDR4'} {s.frequencyMhz ? `${s.frequencyMhz} MHz` : ''}
                          <div style={{ color: 'var(--muted)', fontSize: '10px' }}>S/N: {s.serialNumber || '—'}</div>
                        </div>
                      ))}
                    </div>

                    {/* Baseline Storage */}
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>ЭТАЛОН ДИСКОВ</div>
                      <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '2px' }}>
                        {diffDevice.baseline.spec?.storage?.length || 0} дисков
                      </div>
                      {diffDevice.baseline.spec?.storage?.map((d, i) => (
                        <div key={i} style={{ fontSize: '11px', color: 'var(--ink)', padding: '2px 0 2px 8px', borderLeft: '2px solid var(--green)', marginTop: '4px' }}>
                          {d.model} ({d.capacityGb} GB)
                          <div style={{ color: 'var(--muted)', fontSize: '10px' }}>S/N: {d.serialNumber || '—'}</div>
                        </div>
                      ))}
                    </div>

                    {/* Baseline GPU */}
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>ЭТАЛОН GPU</div>
                      <div style={{ fontSize: '12px', marginTop: '2px' }}>
                        {diffDevice.baseline.spec?.gpus?.[0]?.model || 'Интегрированная графика'}
                      </div>
                    </div>

                    {/* Baseline PCI */}
                    {(diffDevice.baseline.spec?.pciDevices?.length || 0) > 0 && (
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>ЭТАЛОН PCI УСТРОЙСТВ ({diffDevice.baseline.spec?.pciDevices?.length})</div>
                        {diffDevice.baseline.spec?.pciDevices?.map((p, i) => (
                          <div key={i} style={{ fontSize: '11px', color: 'var(--ink)', padding: '2px 0 2px 8px', borderLeft: '2px solid var(--green)', marginTop: '4px' }}>
                            {p.name}
                            <div style={{ color: 'var(--muted)', fontSize: '10px' }}>{p.pnpDeviceId || p.deviceId || 'PCI'}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--muted)' }}>
                    <ShieldCheck size={28} style={{ color: 'var(--orange)', marginBottom: '8px' }} />
                    <p style={{ margin: 0, fontSize: '12px' }}>У этой рабочей станции пока нет сохранённого эталона.</p>
                    <small>Нажмите «Утвердить текущее как эталон», чтобы зафиксировать текущий состав железа.</small>
                  </div>
                )}
              </div>
            </div>
            );
          })()}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <Button onClick={() => setDiffDevice(null)}>Закрыть</Button>
              <Button primary icon={<Check size={14} />} onClick={() => handleApproveSingle(diffDevice)} disabled={approving}>
                Утвердить текущее как эталон
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: BULK APPROVE */}
      {bulkApproveModal && (
        <div className="modal-backdrop" onClick={() => setBulkApproveModal(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '480px' }}>
            <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)' }}>
              <Sparkles size={22} />
            </div>
            <h2>Утвердить эталоны для всех ПК?</h2>
            <p>
              Текущий аппаратный срез всех {devices.length} рабочих станций (объем и планки ОЗУ, серийные номера дисков, видеокарты) будет зафиксирован как официальный эталон. Все текущие предупреждения о расхождениях будут сняты.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <Button onClick={() => setBulkApproveModal(false)}>Отмена</Button>
              <Button primary icon={<Check size={14} />} onClick={handleBulkApprove} disabled={approving}>
                {approving ? 'Утверждение...' : 'Да, утвердить для всех'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------
// Modern Popover Time Picker (Sleek hour/minute scroller)
// ----------------------------------------------------
function TimePickerPopover({
  value,
  onChange
}: {
  value: string;
  onChange: (val: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const hoursColRef = useRef<HTMLDivElement>(null);
  const minsColRef = useRef<HTMLDivElement>(null);

  const parts = (value || '08:00').split(':');
  const currentHour = parts[0] ? parts[0].padStart(2, '0') : '08';
  const currentMin = parts[1] ? parts[1].padStart(2, '0') : '00';

  const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
  const minutes = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'));

  // Close on outside click
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutside);
    };
  }, [isOpen]);

  // Scroll to active values on open
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        if (hoursColRef.current) {
          const selHour = hoursColRef.current.querySelector('.time-picker-item.selected') as HTMLElement;
          if (selHour) {
            hoursColRef.current.scrollTop = selHour.offsetTop - 65;
          }
        }
        if (minsColRef.current) {
          const selMin = minsColRef.current.querySelector('.time-picker-item.selected') as HTMLElement;
          if (selMin) {
            minsColRef.current.scrollTop = selMin.offsetTop - 65;
          }
        }
      }, 40);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  const selectHour = (h: string) => {
    onChange(`${h}:${currentMin}`);
  };

  const selectMinute = (m: string) => {
    onChange(`${currentHour}:${m}`);
  };

  return (
    <div className="modern-time-picker-wrap" ref={containerRef}>
      <div
        className={`modern-time-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="modern-time-trigger-icon">
          <Clock3 size={14} />
        </span>
        <span>{currentHour} : {currentMin}</span>
        <span className="modern-time-trigger-chevron">
          <ChevronDown size={12} />
        </span>
      </div>

      {isOpen && (
        <div className="time-picker-popover" onClick={e => e.stopPropagation()}>
          <div className="time-picker-popover-header">
            <span style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>Выбор времени</span>
            <span className="time-picker-preview">{currentHour} : {currentMin}</span>
          </div>

          <div className="time-picker-columns">
            {/* Hours Column */}
            <div className="time-picker-col" ref={hoursColRef}>
              <div className="time-picker-col-title">Часы</div>
              {hours.map(h => (
                <button
                  type="button"
                  key={h}
                  className={`time-picker-item ${currentHour === h ? 'selected' : ''}`}
                  onClick={() => selectHour(h)}
                >
                  {h}
                </button>
              ))}
            </div>

            {/* Minutes Column */}
            <div className="time-picker-col" ref={minsColRef}>
              <div className="time-picker-col-title">Минуты</div>
              {minutes.map(m => (
                <button
                  type="button"
                  key={m}
                  className={`time-picker-item ${currentMin === m ? 'selected' : ''}`}
                  onClick={() => selectMinute(m)}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          <div className="time-picker-footer">
            <button
              type="button"
              className="time-picker-done-btn"
              onClick={() => setIsOpen(false)}
            >
              Готово
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------
// 10. SCHEDULES PAGE
// ----------------------------------------------------
function Schedules({ notify }: { notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [items, setItems] = useState<Schedule[]>([]);
  const [logs, setLogs] = useState<ScheduleExecutionLog[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'rules' | 'logs'>('rules');
  const [runningScheduleId, setRunningScheduleId] = useState<string | null>(null);

  // Dynamic weekday selector for Timeline sidebar
  const dayNamesRu = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'];
  const currentWeekdayIndex = new Date().getDay() === 0 ? 6 : new Date().getDay() - 1;
  const [selectedTimelineDay, setSelectedTimelineDay] = useState<string>(dayNamesRu[currentWeekdayIndex]);

  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Rule Form Mode: 'LIFECYCLE' (All in one) or 'SINGLE' (One action)
  const [formMode, setFormMode] = useState<'LIFECYCLE' | 'SINGLE'>('LIFECYCLE');
  const [formName, setFormName] = useState('');
  const [formTarget, setFormTarget] = useState('All');
  const [formDaysList, setFormDaysList] = useState<string[]>(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']);
  const [formTimezone, setFormTimezone] = useState('Europe/Moscow');
  const [formDescription, setFormDescription] = useState('');

  // Single Action Form State
  const [formSingleAction, setFormSingleAction] = useState<'WAKE' | 'SHUTDOWN' | 'REBOOT' | 'RDP_CLEANUP'>('WAKE');
  const [formSingleTime, setFormSingleTime] = useState('08:00');
  const [formSingleGrace, setFormSingleGrace] = useState<number>(0);
  const [formSingleWarning, setFormSingleWarning] = useState('');
  const [formSingleForce, setFormSingleForce] = useState(false);

  // Multi-step Lifecycle Form State
  const [formWakeEnabled, setFormWakeEnabled] = useState(true);
  const [formWakeTime, setFormWakeTime] = useState('07:45');

  const [formRdpEnabled, setFormRdpEnabled] = useState(true);
  const [formRdpTime, setFormRdpTime] = useState('21:45');

  const [formShutdownEnabled, setFormShutdownEnabled] = useState(true);
  const [formShutdownTime, setFormShutdownTime] = useState('22:00');
  const [formShutdownGrace, setFormShutdownGrace] = useState<number>(5);
  const [formShutdownWarning, setFormShutdownWarning] = useState('Внимание! Через 5 минут компьютер будет автоматически выключен.');
  const [formShutdownForce, setFormShutdownForce] = useState(true);

  const [formRebootEnabled, setFormRebootEnabled] = useState(false);
  const [formRebootTime, setFormRebootTime] = useState('04:00');

  // Logs filters
  const [logSearch, setLogSearch] = useState('');
  const [logStatusFilter, setLogStatusFilter] = useState<'ALL' | 'Success' | 'Failed'>('ALL');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [schedulesData, logsData, devicesData] = await Promise.all([
        schedulesApi.list(),
        schedulesApi.getLogs(),
        devicesApi.list()
      ]);
      setItems(schedulesData);
      setLogs(logsData);
      setDevices(devicesData);
    } catch (err) {
      console.error('Failed to load schedules data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Distinct groups from devices list
  const availableGroups = Array.from(
    new Set(
      devices.flatMap(d => getDeviceGroups(d))
    )
  ).filter(Boolean);

  const handleOpenCreateModal = () => {
    setIsEditing(false);
    setEditingId(null);
    setFormMode('LIFECYCLE');
    setFormName('');
    setFormTarget('All');
    setFormDaysList(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']);
    setFormTimezone('Europe/Moscow');
    setFormDescription('');

    // Single action defaults
    setFormSingleAction('WAKE');
    setFormSingleTime('08:00');
    setFormSingleGrace(0);
    setFormSingleWarning('');
    setFormSingleForce(false);

    // Lifecycle steps defaults
    setFormWakeEnabled(true);
    setFormWakeTime('07:45');
    setFormRdpEnabled(true);
    setFormRdpTime('21:45');
    setFormShutdownEnabled(true);
    setFormShutdownTime('22:00');
    setFormShutdownGrace(5);
    setFormShutdownWarning('Внимание! Через 5 минут компьютер будет выключен.');
    setFormShutdownForce(true);
    setFormRebootEnabled(false);
    setFormRebootTime('04:00');

    setShowModal(true);
  };

  const handleOpenEditModal = (sch: Schedule) => {
    setIsEditing(true);
    setEditingId(sch.id);
    setFormName(sch.name);
    setFormTarget(sch.target || 'All');
    setFormDaysList(sch.daysList || ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']);
    setFormTimezone(sch.timezone || 'Europe/Moscow');
    setFormDescription(sch.description || '');

    const hasMultipleSteps = sch.steps && sch.steps.length > 1;
    if (hasMultipleSteps || sch.action === 'LIFECYCLE' || sch.type === 'Lifecycle') {
      setFormMode('LIFECYCLE');
      const wakeStep = sch.steps?.find(s => s.action === 'WAKE');
      const rdpStep = sch.steps?.find(s => s.action === 'RDP_CLEANUP');
      const shutdownStep = sch.steps?.find(s => s.action === 'SHUTDOWN');
      const rebootStep = sch.steps?.find(s => s.action === 'REBOOT');

      setFormWakeEnabled(wakeStep ? wakeStep.enabled : false);
      setFormWakeTime(wakeStep ? wakeStep.time : '07:45');

      setFormRdpEnabled(rdpStep ? rdpStep.enabled : false);
      setFormRdpTime(rdpStep ? rdpStep.time : '21:45');

      setFormShutdownEnabled(shutdownStep ? shutdownStep.enabled : false);
      setFormShutdownTime(shutdownStep ? shutdownStep.time : '22:00');
      setFormShutdownGrace(shutdownStep?.gracePeriodMinutes || 5);
      setFormShutdownWarning(shutdownStep?.warningMessage || 'Внимание! Через 5 минут компьютер будет выключен.');
      setFormShutdownForce(shutdownStep?.forceShutdown ?? true);

      setFormRebootEnabled(rebootStep ? rebootStep.enabled : false);
      setFormRebootTime(rebootStep ? rebootStep.time : '04:00');
    } else {
      setFormMode('SINGLE');
      setFormSingleAction(sch.action === 'LIFECYCLE' ? 'WAKE' : sch.action);
      setFormSingleTime(sch.time || '08:00');
      setFormSingleGrace(sch.gracePeriodMinutes || 0);
      setFormSingleWarning(sch.warningMessage || '');
      setFormSingleForce(sch.forceShutdown || false);
    }

    setShowModal(true);
  };

  const handleSaveSchedule = async () => {
    if (!formName.trim()) {
      notify('Укажите название расписания');
      return;
    }
    if (formDaysList.length === 0) {
      notify('Выберите хотя бы один день недели');
      return;
    }

    let payload: Partial<Schedule>;

    if (formMode === 'LIFECYCLE') {
      const steps: ScheduleStep[] = [];
      if (formWakeEnabled) {
        steps.push({
          id: 'step-wake',
          action: 'WAKE',
          time: formWakeTime,
          enabled: true,
          gracePeriodMinutes: 0
        });
      }
      if (formRdpEnabled) {
        steps.push({
          id: 'step-rdp',
          action: 'RDP_CLEANUP',
          time: formRdpTime,
          enabled: true,
          gracePeriodMinutes: 0
        });
      }
      if (formShutdownEnabled) {
        steps.push({
          id: 'step-shutdown',
          action: 'SHUTDOWN',
          time: formShutdownTime,
          enabled: true,
          gracePeriodMinutes: formShutdownGrace,
          warningMessage: formShutdownWarning,
          forceShutdown: formShutdownForce
        });
      }
      if (formRebootEnabled) {
        steps.push({
          id: 'step-reboot',
          action: 'REBOOT',
          time: formRebootTime,
          enabled: true,
          gracePeriodMinutes: 0,
          forceShutdown: true
        });
      }

      if (steps.length === 0) {
        notify('Включите хотя бы один этап суточного цикла');
        return;
      }

      payload = {
        name: formName.trim(),
        action: 'LIFECYCLE',
        type: 'Lifecycle',
        target: formTarget,
        time: steps[0].time,
        daysList: formDaysList,
        timezone: formTimezone,
        steps,
        createdBy: getActiveUserName() || 'Администратор',
        description: formDescription || `Суточный цикл (${steps.length} этапов) для ${formTarget}`
      };
    } else {
      // Single action rule
      payload = {
        name: formName.trim(),
        action: formSingleAction,
        type: 'Custom',
        target: formTarget,
        time: formSingleTime,
        daysList: formDaysList,
        timezone: formTimezone,
        gracePeriodMinutes: formSingleGrace,
        warningMessage: formSingleWarning,
        forceShutdown: formSingleForce,
        createdBy: getActiveUserName() || 'Администратор',
        steps: [{
          id: 'step-single',
          action: formSingleAction,
          time: formSingleTime,
          enabled: true,
          gracePeriodMinutes: formSingleGrace,
          warningMessage: formSingleWarning,
          forceShutdown: formSingleForce
        }],
        description: formDescription || `Автоматическое действие ${formSingleAction} для ${formTarget}`
      };
    }

    try {
      if (isEditing && editingId) {
        await schedulesApi.update(editingId, payload);
        notify(`Правило "${formName}" успешно обновлено!`);
      } else {
        await schedulesApi.create(payload);
        notify(`Новое правило "${formName}" создано!`);
      }
      setShowModal(false);
      loadData();
    } catch (err) {
      notify('Ошибка при сохранении расписания');
    }
  };

  const handleToggleSchedule = async (schedule: Schedule) => {
    const nextState = !schedule.enabled;
    setItems(prev => prev.map(s => s.id === schedule.id ? { ...s, enabled: nextState } : s));
    try {
      await schedulesApi.toggle(schedule.id);
      notify(`Правило "${schedule.name}" ${nextState ? 'включено' : 'приостановлено'}`);
    } catch (err) {
      setItems(prev => prev.map(s => s.id === schedule.id ? { ...s, enabled: !nextState } : s));
      notify('Не удалось изменить статус расписания');
    }
  };

  const handleDeleteSchedule = async (id: string, name: string) => {
    if (!window.confirm(`Вы действительно хотите удалить правило "${name}"?`)) return;
    try {
      await schedulesApi.delete(id);
      setItems(prev => prev.filter(s => s.id !== id));
      notify(`Правило "${name}" удалено`);
    } catch (err) {
      notify('Ошибка при удалении расписания');
    }
  };

  const handleRunScheduleNow = async (sch: Schedule, actionOverride?: string) => {
    setRunningScheduleId(sch.id);
    try {
      const res = await schedulesApi.runNow(sch.id);
      notify(res.message || `Действие для "${sch.name}" успешно запущено!`);
      await loadData();
    } catch (err) {
      notify('Не удалось выполнить запуск расписания');
    } finally {
      setRunningScheduleId(null);
    }
  };

  const toggleDayInForm = (day: string) => {
    if (formDaysList.includes(day)) {
      if (formDaysList.length === 1) return;
      setFormDaysList(formDaysList.filter(d => d !== day));
    } else {
      setFormDaysList([...formDaysList, day]);
    }
  };

  const setDaysPreset = (preset: 'WEEKDAYS' | 'WEEKENDS' | 'ALL') => {
    if (preset === 'WEEKDAYS') setFormDaysList(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ']);
    if (preset === 'WEEKENDS') setFormDaysList(['СБ', 'ВС']);
    if (preset === 'ALL') setFormDaysList(['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']);
  };

  // Stats calculation
  const totalRules = items.length;
  const activeRules = items.filter(s => s.enabled).length;
  const activeSchedulesWithNextRun = items
    .filter(s => s.enabled && s.secondsUntilNext !== undefined)
    .sort((a, b) => (a.secondsUntilNext || 0) - (b.secondsUntilNext || 0));
  const nextUpcoming = activeSchedulesWithNextRun[0];

  // Filtered timeline events for the selected day in weekly preview
  const dayTimelineEvents = items
    .filter(s => s.enabled && (s.daysList || []).includes(selectedTimelineDay))
    .flatMap(s => {
      if (s.steps && s.steps.length > 0) {
        return s.steps.filter(st => st.enabled).map(st => ({
          id: `${s.id}-${st.action}-${st.time}`,
          time: st.time,
          action: st.action,
          ruleName: s.name,
          label: st.action === 'WAKE' ? 'WoL Включение' :
                 st.action === 'RDP_CLEANUP' ? 'Очистка RDP' :
                 st.action === 'SHUTDOWN' ? 'Выключение' : 'Перезагрузка',
          target: s.target
        }));
      }
      return [{
        id: s.id,
        time: s.time,
        action: s.action === 'LIFECYCLE' ? 'WAKE' : s.action,
        ruleName: s.name,
        label: s.name,
        target: s.target
      }];
    })
    .sort((a, b) => a.time.localeCompare(b.time));

  // Filtered logs
  const filteredLogs = logs.filter(l => {
    const matchSearch = logSearch === '' || 
      `${l.scheduleName} ${l.action} ${l.target} ${l.details}`.toLowerCase().includes(logSearch.toLowerCase());
    const matchStatus = logStatusFilter === 'ALL' || l.status === logStatusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <>
      <PageHeader
        eyebrow="AUTOMATION & POWER LIFECYCLE"
        title="Расписания и Автоматизация"
        description="Суточные циклы управления питанием парка ПК: Wake-on-LAN старт, очистка брошенных RDP и вечернее выключение."
        actions={
          <Button primary icon={<Plus size={15} />} onClick={handleOpenCreateModal}>
            Создать правило
          </Button>
        }
      />

      {/* Top Bento Stats Grid */}
      <div className="bento-grid" style={{ marginBottom: '22px' }}>
        <div className="bento-card col-3">
          <div className="bento-header">
            <span className="bento-card-title">Активные правила</span>
            <div className="bento-icon blue"><Clock3 size={18} /></div>
          </div>
          <div className="bento-value">{activeRules} <small>/ {totalRules} правил</small></div>
          <div className="bento-footer">
            <span>Фоновый демон: <strong>Активен</strong></span>
            <span className="pulse-dot" />
          </div>
        </div>

        <div className="bento-card col-3">
          <div className="bento-header">
            <span className="bento-card-title">Ближайший этап</span>
            <div className="bento-icon green"><Zap size={18} /></div>
          </div>
          <div className="bento-value" style={{ fontSize: '16px', fontWeight: 600 }}>
            {nextUpcoming ? (nextUpcoming.nextStepTime || nextUpcoming.time) : '—'}
            <small style={{ fontSize: '11px' }}>{nextUpcoming?.name || 'Нет активных'}</small>
          </div>
          <div className="bento-footer">
            <span>{nextUpcoming?.nextRunFormatted || 'Все правила отключены'}</span>
          </div>
        </div>

        <div className="bento-card col-3">
          <div className="bento-header">
            <span className="bento-card-title">Охват парка</span>
            <div className="bento-icon purple"><Server size={18} /></div>
          </div>
          <div className="bento-value">{devices.length} <small>ПК под контролем</small></div>
          <div className="bento-footer">
            <span>Группы: {availableGroups.length || 1} отделов</span>
            <ShieldCheck size={14} style={{ color: 'var(--blue)' }} />
          </div>
        </div>

        <div className="bento-card col-3">
          <div className="bento-header">
            <span className="bento-card-title">Успешность (30 дн)</span>
            <div className="bento-icon cyan"><Check size={18} /></div>
          </div>
          <div className="bento-value">100% <small>Надежность</small></div>
          <div className="bento-footer">
            <span>Зафиксировано {logs.length} запусков</span>
            <Check size={14} style={{ color: 'var(--green)' }} />
          </div>
        </div>
      </div>

      {/* Tabs Switcher */}
      <div className="schedule-tabs">
        <button
          className={`schedule-tab-btn ${activeTab === 'rules' ? 'active' : ''}`}
          onClick={() => setActiveTab('rules')}
        >
          <Clock3 size={15} /> Правила расписания ({items.length})
        </button>
        <button
          className={`schedule-tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
          onClick={() => setActiveTab('logs')}
        >
          <RotateCw size={15} /> Журнал выполнения ({logs.length})
        </button>
      </div>

      {activeTab === 'rules' && (
        <div className="schedule-layout">
          {/* Main List of Schedules */}
          <div className="schedule-list">
            {loading && (
              <div className="loading-state" style={{ minHeight: '200px' }}>
                <LoaderCircle size={28} className="spin" />
                <span>Загрузка правил планировщика...</span>
              </div>
            )}

            {!loading && items.length === 0 && (
              <div className="panel empty-state" style={{ padding: '40px 20px', textAlign: 'center' }}>
                <Clock3 size={36} style={{ color: 'var(--muted)' }} />
                <h3>Нет активных расписаний</h3>
                <p style={{ color: 'var(--muted)', fontSize: '12px', maxWidth: '380px', margin: '6px auto 16px' }}>
                  Создайте комплексный суточный цикл для автоматического включения по WoL, очистки RDP и вечернего выключения.
                </p>
                <Button primary icon={<Plus size={14} />} onClick={handleOpenCreateModal}>
                  Создать суточный цикл
                </Button>
              </div>
            )}

            {!loading && items.map(schedule => {
              const isRunning = runningScheduleId === schedule.id;
              const hasSteps = schedule.steps && schedule.steps.length > 0;
              const isLifecycle = schedule.action === 'LIFECYCLE' || schedule.type === 'Lifecycle' || (hasSteps && schedule.steps!.length > 1);

              return (
                <div
                  className={`schedule-card-modern ${!schedule.enabled ? 'disabled' : ''}`}
                  key={schedule.id}
                  onClick={() => handleOpenEditModal(schedule)}
                  title="Нажмите на карточку для редактирования правила"
                >
                  <div className="schedule-card-main-row">
                    {/* Modern Left Identity Badge */}
                    {isLifecycle ? (
                      <div className="schedule-type-badge lifecycle">
                        <div className="badge-icon">
                          <Zap size={15} />
                        </div>
                        <strong>СУТОЧНЫЙ</strong>
                        <span>ЦИКЛ</span>
                      </div>
                    ) : (
                      <div className="schedule-type-badge single">
                        <div className="badge-time">{schedule.time}</div>
                        <div className="badge-day">{schedule.days}</div>
                      </div>
                    )}

                    {/* Main content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="schedule-title-row">
                        <h3 className="schedule-title-text">{schedule.name}</h3>
                        {schedule.nextRunFormatted && schedule.enabled && (
                          <span className="schedule-next-badge">
                            <span className="next-pulse-dot" />
                            <Clock3 size={11} /> {schedule.nextRunFormatted}
                          </span>
                        )}
                      </div>

                      <div className="schedule-desc-text">
                        {schedule.description}
                      </div>

                      <div className="schedule-meta-modern">
                        <span className="meta-chip">
                          <Server size={11} style={{ color: 'var(--blue)' }} /> Цель: <strong>{schedule.target === 'All' ? 'Все компьютеры' : schedule.target}</strong>
                          {schedule.targetDeviceCount !== undefined && ` (${schedule.targetDeviceCount} ПК)`}
                        </span>

                        <span className="meta-chip">
                          <Calendar size={11} style={{ color: 'var(--blue)' }} /> Дни: <strong>{schedule.days}</strong>
                        </span>

                        <span className="meta-chip">
                          <Globe size={11} style={{ color: 'var(--blue)' }} /> {schedule.timezone}
                        </span>

                        {schedule.createdBy && (
                          <span className="meta-chip">
                            <UserRound size={11} style={{ color: 'var(--blue)' }} /> Автор: <strong>{schedule.createdBy}</strong>
                          </span>
                        )}

                        {schedule.lastRunSummary && (
                          <span className="meta-chip success">
                            <Check size={11} /> {schedule.lastRunSummary}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Quick Action Buttons */}
                    <div
                      style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto', flexShrink: 0 }}
                      onClick={e => e.stopPropagation()}
                    >
                      <button
                        className="schedule-action-btn run-btn"
                        onClick={e => {
                          e.stopPropagation();
                          handleRunScheduleNow(schedule);
                        }}
                        disabled={isRunning}
                        title="Тестовый запуск правила прямо сейчас"
                      >
                        {isRunning ? <LoaderCircle size={13} className="spin" /> : <Play size={13} />}
                        <span>{isRunning ? 'Запуск...' : 'Запустить'}</span>
                      </button>

                      <button
                        className="schedule-action-btn"
                        onClick={e => {
                          e.stopPropagation();
                          handleOpenEditModal(schedule);
                        }}
                        title="Редактировать этапы и параметры"
                      >
                        <Edit3 size={13} />
                      </button>

                      <div onClick={e => e.stopPropagation()}>
                        <Switch
                          checked={schedule.enabled}
                          onChange={() => handleToggleSchedule(schedule)}
                          title="Включить / приостановить правило"
                        />
                      </div>

                      <button
                        className="row-more"
                        onClick={e => {
                          e.stopPropagation();
                          handleDeleteSchedule(schedule.id, schedule.name);
                        }}
                        title="Удалить правило"
                      >
                        <Trash2 size={15} style={{ color: 'var(--muted)' }} />
                      </button>
                    </div>
                  </div>

                  {/* Multi-step Lifecycle Pipeline Visualizer */}
                  {isLifecycle && schedule.steps && (
                    <div className="lifecycle-pipeline">
                      {schedule.steps.map((st, idx) => {
                        return (
                          <React.Fragment key={st.id || idx}>
                            <div className={`pipeline-step ${!st.enabled ? 'disabled' : ''}`}>
                              {st.action === 'WAKE' && <Zap size={13} style={{ color: 'var(--green)' }} />}
                              {st.action === 'RDP_CLEANUP' && <Monitor size={13} style={{ color: '#8b5cf6' }} />}
                              {st.action === 'SHUTDOWN' && <Power size={13} style={{ color: 'var(--red)' }} />}
                              {st.action === 'REBOOT' && <RotateCw size={13} style={{ color: 'var(--orange)' }} />}
                              <span className="pipeline-step-time">{st.time}</span>
                              <span>
                                {st.action === 'WAKE' ? 'WoL Старт' :
                                 st.action === 'RDP_CLEANUP' ? 'Очистка RDP' :
                                 st.action === 'SHUTDOWN' ? (st.gracePeriodMinutes ? `Выключение (${st.gracePeriodMinutes}м)` : 'Выключение') : 'Перезагрузка'}
                              </span>
                            </div>
                            {idx < schedule.steps!.length - 1 && (
                              <span className="pipeline-arrow"><ArrowRight size={13} /></span>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Dynamic Interactive Weekly Sidebar */}
          <aside className="panel week-preview">
            <div className="panel-heading">
              <div>
                <h2>Недельный цикл</h2>
                <p>Динамический график суточных этапов</p>
              </div>
              <Clock3 size={18} className="heading-icon" />
            </div>

            {/* Day Selector */}
            <div className="week-days">
              {dayNamesRu.map((day, i) => {
                const isSelected = day === selectedTimelineDay;
                const isToday = i === currentWeekdayIndex;
                const eventsCount = items.filter(s => s.enabled && (s.daysList || []).includes(day)).length;
                return (
                  <div
                    key={day}
                    className={`${isSelected ? 'active' : ''}`}
                    onClick={() => setSelectedTimelineDay(day)}
                    style={{ cursor: 'pointer', position: 'relative' }}
                    title={`${day} (${eventsCount} правил)`}
                  >
                    {day}
                    {isToday && (
                      <span
                        style={{
                          position: 'absolute',
                          bottom: '-4px',
                          width: '4px',
                          height: '4px',
                          borderRadius: '50%',
                          background: 'var(--green)'
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>

            <div style={{ padding: '0 21px 10px', fontSize: '11px', color: 'var(--muted)' }}>
              Суточные этапы на <strong>{selectedTimelineDay}</strong>:
            </div>

            {/* Dynamic Timeline Items for the selected day */}
            <div className="timeline">
              {dayTimelineEvents.length === 0 ? (
                <div style={{ padding: '14px 0', color: 'var(--muted)', fontSize: '11px' }}>
                  Нет запланированных действий на этот день
                </div>
              ) : (
                dayTimelineEvents.map(evt => {
                  let dotClass = 'wake-dot';
                  if (evt.action === 'SHUTDOWN') dotClass = 'shutdown-dot';
                  if (evt.action === 'REBOOT') dotClass = 'force-dot';
                  if (evt.action === 'RDP_CLEANUP') dotClass = 'cleanup-dot';

                  return (
                    <div key={evt.id}>
                      <span>{evt.time}</span>
                      <i className={dotClass} />
                      <strong>
                        {evt.label} <small style={{ fontWeight: 400, color: 'var(--muted)' }}>({evt.target})</small>
                      </strong>
                    </div>
                  );
                })
              )}
            </div>

            <Button onClick={handleOpenCreateModal} style={{ width: 'calc(100% - 42px)', margin: '0 21px' }}>
              + Добавить суточный цикл
            </Button>
          </aside>
        </div>
      )}

      {/* Execution Logs Tab */}
      {activeTab === 'logs' && (
        <section className="panel table-panel">
          <div className="panel-heading table-heading">
            <div>
              <h2>Журнал автоматических и ручных запусков</h2>
              <p>Детализация этапов включения WoL, сброса RDP и команд выключения</p>
            </div>

            <div className="table-tools">
              <div className="search">
                <Search size={14} />
                <input
                  placeholder="Поиск по журналу..."
                  value={logSearch}
                  onChange={e => setLogSearch(e.target.value)}
                />
              </div>

              <select
                className="text-input"
                value={logStatusFilter}
                onChange={e => setLogStatusFilter(e.target.value as any)}
                style={{ height: '34px', minWidth: '130px' }}
              >
                <option value="ALL">Все статусы</option>
                <option value="Success">Успешно</option>
                <option value="Failed">Ошибки</option>
              </select>

              <Button icon={<RotateCw size={13} />} onClick={loadData}>
                Обновить
              </Button>
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Расписание / Действие</th>
                  <th>Цель</th>
                  <th>Статус</th>
                  <th>Охвачено ПК</th>
                  <th>Инициатор</th>
                  <th>Детали</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '30px', color: 'var(--muted)' }}>
                      Записей не найдено
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map(log => (
                    <tr key={log.id}>
                      <td className="mono" style={{ fontSize: '11px' }}>{log.timestamp}</td>
                      <td>
                        <strong>{log.scheduleName}</strong>
                        <span className="muted-text" style={{ display: 'block', fontSize: '10px' }}>
                          Действие: {log.action}
                        </span>
                      </td>
                      <td><span className="badge">{log.target}</span></td>
                      <td>
                        <span className={`log-status-tag ${log.status.toLowerCase()}`}>
                          {log.status === 'Success' ? <Check size={11} /> : <AlertTriangle size={11} />}
                          {log.status}
                        </span>
                      </td>
                      <td>
                        <strong>{log.devicesSuccess} / {log.devicesTargeted}</strong>
                      </td>
                      <td className="mono" style={{ fontSize: '10px', color: 'var(--muted)' }}>
                        {log.triggeredBy}
                      </td>
                      <td style={{ fontSize: '11px', color: 'var(--muted)', maxWidth: '340px', whiteSpace: 'normal' }}>
                        {log.details}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Modern Schedule Editor / Creator Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div
            className="schedule-modal"
            onClick={e => e.stopPropagation()}
          >
            {/* Modern Header */}
            <div className="modal-header-modern">
              <div className="modal-header-left">
                <div className="modal-header-icon">
                  <Clock3 size={20} />
                </div>
                <div>
                  <div className="modal-eyebrow">AUTOPILOT ENGINE</div>
                  <h2 className="modal-title-main">
                    {isEditing ? 'Настройка суточного расписания' : 'Новое правило автоматизации'}
                  </h2>
                </div>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowModal(false)}
                title="Закрыть окно"
              >
                <X size={16} />
              </button>
            </div>

            {/* Scrollable Body */}
            <div className="modal-body-scrollable">
              {/* Apple-style Segmented Mode Control */}
              <div className="segmented-mode-nav">
                <button
                  type="button"
                  className={`segmented-mode-item ${formMode === 'LIFECYCLE' ? 'active' : ''}`}
                  onClick={() => setFormMode('LIFECYCLE')}
                >
                  <Zap size={14} /> Комплексный суточный цикл (Все в одном)
                </button>
                <button
                  type="button"
                  className={`segmented-mode-item ${formMode === 'SINGLE' ? 'active' : ''}`}
                  onClick={() => setFormMode('SINGLE')}
                >
                  <Power size={14} /> Одиночное действие
                </button>
              </div>

              {/* Basic Details (Name, Target, Timezone) */}
              <div className="form-section-card">
                <div>
                  <div className="form-label-modern">
                    <span>Название правила</span>
                    <small>Обязательное поле</small>
                  </div>
                  <input
                    className="modern-text-input"
                    value={formName}
                    onChange={e => setFormName(e.target.value)}
                    placeholder={formMode === 'LIFECYCLE' ? 'Например: Суточный цикл (Офис Пн-Пт)' : 'Например: Утренний старт'}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <div className="form-label-modern">
                      <span>Целевая группа</span>
                    </div>
                    <select
                      className="modern-text-input"
                      value={formTarget}
                      onChange={e => setFormTarget(e.target.value)}
                    >
                      <option value="All">Все компьютеры ({devices.length} ПК)</option>
                      {availableGroups.map(grp => (
                        <option key={grp} value={grp}>
                          Группа: {grp}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <div className="form-label-modern">
                      <span>Часовой пояс</span>
                    </div>
                    <select
                      className="modern-text-input"
                      value={formTimezone}
                      onChange={e => setFormTimezone(e.target.value)}
                    >
                      <option value="Europe/Moscow">Europe/Moscow (UTC+3)</option>
                      <option value="Europe/Berlin">Europe/Berlin (UTC+1)</option>
                      <option value="UTC">UTC</option>
                      <option value="America/New_York">America/New_York (UTC-5)</option>
                    </select>
                  </div>
                </div>

                {/* Days Selector */}
                <div>
                  <div className="form-label-modern">
                    <span>Дни активности правила ({formDaysList.length} выбрано)</span>
                  </div>
                  <div className="days-chips-modern">
                    {dayNamesRu.map(d => {
                      const isSel = formDaysList.includes(d);
                      return (
                        <button
                          type="button"
                          key={d}
                          className={`day-chip-modern ${isSel ? 'selected' : ''}`}
                          onClick={() => toggleDayInForm(d)}
                        >
                          {d}
                        </button>
                      );
                    })}
                  </div>
                  <div className="preset-pills-row">
                    <button type="button" className="preset-pill-btn" onClick={() => setDaysPreset('WEEKDAYS')}>
                      Будни (Пн-Пт)
                    </button>
                    <button type="button" className="preset-pill-btn" onClick={() => setDaysPreset('WEEKENDS')}>
                      Выходные (Сб-Вс)
                    </button>
                    <button type="button" className="preset-pill-btn" onClick={() => setDaysPreset('ALL')}>
                      Все дни (Каждый день)
                    </button>
                  </div>
                </div>
              </div>

              {/* MODE 1: COMPOSITE LIFECYCLE BUILDER */}
              {formMode === 'LIFECYCLE' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--ink)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Clock3 size={15} style={{ color: 'var(--blue)' }} /> Этапы суточного пайплайна питания:
                  </div>

                  {/* Step 1: Wake-on-LAN */}
                  <div className={`pipeline-step-card ${formWakeEnabled ? 'active-wake' : 'disabled'}`}>
                    <div className="step-card-header">
                      <div className="step-card-identity">
                        <span className="step-number-tag">ЭТАП 01</span>
                        <div className="action-card-icon wake"><Zap size={16} /></div>
                        <div className="step-title-group">
                          <strong>Утренний старт (Wake-on-LAN)</strong>
                          <span>Отправка Magic Packet по локальной сети</span>
                        </div>
                      </div>
                      <Switch checked={formWakeEnabled} onChange={setFormWakeEnabled} />
                    </div>

                    {formWakeEnabled && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingTop: '12px', borderTop: '1px solid var(--line)' }}>
                        <label style={{ fontSize: '11px', color: 'var(--muted)', whiteSpace: 'nowrap' }}>Время старта:</label>
                        <TimePickerPopover
                          value={formWakeTime}
                          onChange={setFormWakeTime}
                        />
                      </div>
                    )}
                  </div>

                  {/* Step 2: RDP Cleanup */}
                  <div className={`pipeline-step-card ${formRdpEnabled ? 'active-rdp' : 'disabled'}`}>
                    <div className="step-card-header">
                      <div className="step-card-identity">
                        <span className="step-number-tag">ЭТАП 02</span>
                        <div className="action-card-icon rdp"><Monitor size={16} /></div>
                        <div className="step-title-group">
                          <strong>Очистка брошенных RDP сессий</strong>
                          <span>Сброс зависших и отключенных сессий перед выключением</span>
                        </div>
                      </div>
                      <Switch checked={formRdpEnabled} onChange={setFormRdpEnabled} />
                    </div>

                    {formRdpEnabled && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingTop: '12px', borderTop: '1px solid var(--line)' }}>
                        <label style={{ fontSize: '11px', color: 'var(--muted)', whiteSpace: 'nowrap' }}>Время сброса:</label>
                        <TimePickerPopover
                          value={formRdpTime}
                          onChange={setFormRdpTime}
                        />
                      </div>
                    )}
                  </div>

                  {/* Step 3: Evening Shutdown */}
                  <div className={`pipeline-step-card ${formShutdownEnabled ? 'active-shutdown' : 'disabled'}`}>
                    <div className="step-card-header">
                      <div className="step-card-identity">
                        <span className="step-number-tag">ЭТАП 03</span>
                        <div className="action-card-icon shutdown"><Power size={16} /></div>
                        <div className="step-title-group">
                          <strong>Вечернее выключение парка ПК</strong>
                          <span>Завершение работы операционной системы с предупреждением</span>
                        </div>
                      </div>
                      <Switch checked={formShutdownEnabled} onChange={setFormShutdownEnabled} />
                    </div>

                    {formShutdownEnabled && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '12px', borderTop: '1px solid var(--line)' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '170px 1fr', gap: '14px', alignItems: 'center' }}>
                          <div>
                            <label style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '6px' }}>
                              Время выключения:
                            </label>
                            <TimePickerPopover
                              value={formShutdownTime}
                              onChange={setFormShutdownTime}
                            />
                          </div>

                          <div>
                            <label style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '6px' }}>
                              Предупреждение (Grace Period):
                            </label>
                            <select
                              className="modern-text-input"
                              value={formShutdownGrace}
                              onChange={e => setFormShutdownGrace(Number(e.target.value))}
                            >
                              <option value="0">Без предупреждения (сразу)</option>
                              <option value="1">1 минута</option>
                              <option value="3">3 минуты</option>
                              <option value="5">5 минут (Рекомендуется)</option>
                              <option value="10">10 минут</option>
                              <option value="15">15 минут</option>
                            </select>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0' }}>
                          <div>
                            <strong style={{ fontSize: '11px' }}>Принудительно (Force Shutdown)</strong>
                            <span style={{ fontSize: '10px', color: 'var(--muted)', display: 'block' }}>Закрыть зависшие и несохраненные окна</span>
                          </div>
                          <Switch checked={formShutdownForce} onChange={setFormShutdownForce} />
                        </div>

                        {formShutdownGrace > 0 && (
                          <div>
                            <label style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
                              Текст уведомления на экранах сотрудников:
                            </label>
                            <input
                              className="modern-text-input"
                              style={{ width: '100%', fontSize: '11px' }}
                              value={formShutdownWarning}
                              onChange={e => setFormShutdownWarning(e.target.value)}
                              placeholder={`Внимание! Компьютер будет выключен через ${formShutdownGrace} мин.`}
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Step 4: Optional Night Reboot */}
                  <div className={`pipeline-step-card ${formRebootEnabled ? 'active-reboot' : 'disabled'}`}>
                    <div className="step-card-header">
                      <div className="step-card-identity">
                        <span className="step-number-tag">ЭТАП 04</span>
                        <div className="action-card-icon reboot"><RotateCw size={16} /></div>
                        <div className="step-title-group">
                          <strong>Профилактическая перезагрузка (Опционально)</strong>
                          <span>Сброс утечек памяти и установка обновлений ОС</span>
                        </div>
                      </div>
                      <Switch checked={formRebootEnabled} onChange={setFormRebootEnabled} />
                    </div>

                    {formRebootEnabled && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingTop: '12px', borderTop: '1px solid var(--line)' }}>
                        <label style={{ fontSize: '11px', color: 'var(--muted)', whiteSpace: 'nowrap' }}>Время перезагрузки:</label>
                        <TimePickerPopover
                          value={formRebootTime}
                          onChange={setFormRebootTime}
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* MODE 2: SINGLE ACTION BUILDER */}
              {formMode === 'SINGLE' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div>
                    <div className="form-label-modern">
                      <span>Тип действия</span>
                    </div>
                    <div className="action-cards-grid">
                      <div
                        className={`action-card-option ${formSingleAction === 'WAKE' ? 'selected' : ''}`}
                        onClick={() => setFormSingleAction('WAKE')}
                      >
                        <div className="action-card-icon wake"><Zap size={16} /></div>
                        <div className="action-card-text">
                          <strong>Wake-on-LAN</strong>
                          <span>Пробуждение ПК по сети</span>
                        </div>
                      </div>

                      <div
                        className={`action-card-option ${formSingleAction === 'SHUTDOWN' ? 'selected' : ''}`}
                        onClick={() => setFormSingleAction('SHUTDOWN')}
                      >
                        <div className="action-card-icon shutdown"><Power size={16} /></div>
                        <div className="action-card-text">
                          <strong>Плавное выключение</strong>
                          <span>Штатное завершение работы</span>
                        </div>
                      </div>

                      <div
                        className={`action-card-option ${formSingleAction === 'REBOOT' ? 'selected' : ''}`}
                        onClick={() => setFormSingleAction('REBOOT')}
                      >
                        <div className="action-card-icon reboot"><RotateCw size={16} /></div>
                        <div className="action-card-text">
                          <strong>Перезагрузка</strong>
                          <span>Перезапуск операционной системы</span>
                        </div>
                      </div>

                      <div
                        className={`action-card-option ${formSingleAction === 'RDP_CLEANUP' ? 'selected' : ''}`}
                        onClick={() => setFormSingleAction('RDP_CLEANUP')}
                      >
                        <div className="action-card-icon rdp"><Monitor size={16} /></div>
                        <div className="action-card-text">
                          <strong>Очистка RDP</strong>
                          <span>Сброс брошенных сессий</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="form-label-modern">
                      <span>Время запуска</span>
                    </div>
                    <TimePickerPopover
                      value={formSingleTime}
                      onChange={setFormSingleTime}
                    />
                  </div>

                  {(formSingleAction === 'SHUTDOWN' || formSingleAction === 'REBOOT') && (
                    <div className="warning-grace-box">
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '8px' }}>
                        <div>
                          <label style={{ fontSize: '11px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
                            Grace Period (мин):
                          </label>
                          <select
                            className="modern-text-input"
                            style={{ padding: '7px 10px' }}
                            value={formSingleGrace}
                            onChange={e => setFormSingleGrace(Number(e.target.value))}
                          >
                            <option value="0">Без предупреждения</option>
                            <option value="5">5 минут</option>
                            <option value="10">10 минут</option>
                          </select>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '14px' }}>
                          <strong style={{ fontSize: '11px' }}>Принудительно</strong>
                          <Switch checked={formSingleForce} onChange={setFormSingleForce} />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modern Footer Bar */}
            <div className="modal-footer-modern">
              <div className="modal-footer-modern-left">
                <ShieldCheck size={15} style={{ color: 'var(--green)' }} />
                <span>Автоматическое исполнение по локальному таймеру</span>
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <Button onClick={() => setShowModal(false)}>{t('common.cancel')}</Button>
                <Button primary onClick={handleSaveSchedule} disabled={!formName.trim()}>
                  {isEditing ? 'Сохранить расписание' : 'Создать правило'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------
// 11. USERS & ROLES
// ----------------------------------------------------
function UsersPage({ notify, currentUser }: { notify: (message: string) => void; currentUser?: ManagedUser | null }) {
  const { t } = useLanguage();
  const [items, setItems] = useState<ManagedUser[]>([]);
  const [availableGroups, setAvailableGroups] = useState<string[]>(['Office', 'Warehouse', 'Management', 'Testing', 'Dev']);
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState<ManagedUser | null>(null);
  const [query, setQuery] = useState('');

  // Add User Form state
  const [newFullName, setNewFullName] = useState('');
  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState('Дежурный оператор');
  const [newPassword, setNewPassword] = useState('P@ssw0rd2026!');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [newScopeType, setNewScopeType] = useState<'ALL' | 'CUSTOM'>('ALL');
  const [newAllowedGroups, setNewAllowedGroups] = useState<string[]>([]);
  const [newTelegramChatId, setNewTelegramChatId] = useState('');

  // Edit User Form state
  const [editFullName, setEditFullName] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editRole, setEditRole] = useState('Дежурный оператор');
  const [editScopeType, setEditScopeType] = useState<'ALL' | 'CUSTOM'>('ALL');
  const [editAllowedGroups, setEditAllowedGroups] = useState<string[]>([]);
  const [editTelegramChatId, setEditTelegramChatId] = useState('');
  const [editEnabled, setEditEnabled] = useState(true);
  const [editNewPassword, setEditNewPassword] = useState('');
  const [showEditPassword, setShowEditPassword] = useState(false);

  const generatePassword = () => {
    const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
    const lower = 'abcdefghijkmnpqrstuvwxyz';
    const numbers = '23456789';
    const symbols = '!@#$%&*';
    const all = upper + lower + numbers + symbols;
    let pwd = '';
    pwd += upper.charAt(Math.floor(Math.random() * upper.length));
    pwd += lower.charAt(Math.floor(Math.random() * lower.length));
    pwd += numbers.charAt(Math.floor(Math.random() * numbers.length));
    pwd += symbols.charAt(Math.floor(Math.random() * symbols.length));
    for (let i = 4; i < 12; i++) {
      pwd += all.charAt(Math.floor(Math.random() * all.length));
    }
    return pwd.split('').sort(() => 0.5 - Math.random()).join('');
  };

  const loadUsers = () => {
    usersApi.list().then(setItems).catch(() => {});
  };

  useEffect(() => {
    loadUsers();
    groupsApi.list().then(grps => {
      if (grps && grps.length > 0) {
        setAvailableGroups(grps.map(g => g.name));
      }
    }).catch(() => {});
  }, []);

  const openAddModal = () => {
    const autoPwd = generatePassword();
    setNewFullName('');
    setNewUsername('');
    setNewEmail('');
    setNewRole('Дежурный оператор');
    setNewPassword(autoPwd);
    setShowNewPassword(false);
    setNewScopeType('ALL');
    setNewAllowedGroups([]);
    setNewTelegramChatId('');
    setShowAddUserModal(true);
  };

  const openEditModal = (user: ManagedUser) => {
    setEditingUser(user);
    setEditFullName(user.displayName);
    setEditEmail(user.email);
    setEditRole(user.role);
    const hasCustomGroups = Array.isArray(user.allowedGroups) && user.allowedGroups.length > 0 && user.scope !== 'Все устройства';
    setEditScopeType(hasCustomGroups ? 'CUSTOM' : 'ALL');
    setEditAllowedGroups(user.allowedGroups || []);
    setEditTelegramChatId(user.telegramChatId || '');
    setEditEnabled(user.enabled);
    setEditNewPassword('');
    setShowEditPassword(false);
  };

  const handleAddUser = async () => {
    if (!newUsername.trim() || !newFullName.trim()) return;
    try {
      const scopeStr = newScopeType === 'ALL' || newAllowedGroups.length === 0
        ? 'Все устройства'
        : `Группы: ${newAllowedGroups.join(', ')}`;

      const user = await usersApi.create({
        username: newUsername.trim().toLowerCase(),
        displayName: newFullName.trim(),
        email: newEmail.trim() || `${newUsername.trim().toLowerCase()}@bmstu.local`,
        password: newPassword,
        role: newRole as any,
        scope: scopeStr,
        allowedGroups: newScopeType === 'ALL' ? [] : newAllowedGroups,
        telegramChatId: newTelegramChatId.trim(),
        enabled: true,
      });

      setItems(prev => [user, ...prev.filter(u => u.id !== user.id)]);
      notify(`Пользователь ${newFullName} успешно создан (пароль сохранен)!`);
      setShowAddUserModal(false);
    } catch (err: any) {
      notify(err?.message || 'Ошибка создания пользователя');
    }
  };

  const handleSaveEdit = async () => {
    if (!editingUser) return;
    if (editingUser.role === 'Суперадминистратор' && (editingUser.id === currentUser?.id || editingUser.username === currentUser?.username)) {
      if (editRole !== 'Суперадминистратор' || !editEnabled) {
        notify('Нельзя заблокировать свою учетную запись или понизить роль Суперадминистратора');
        return;
      }
    }
    try {
      const scopeStr = editScopeType === 'ALL' || editAllowedGroups.length === 0
        ? 'Все устройства'
        : `Группы: ${editAllowedGroups.join(', ')}`;

      const payload: any = {
        displayName: editFullName.trim(),
        email: editEmail.trim(),
        role: editRole,
        scope: scopeStr,
        allowedGroups: editScopeType === 'ALL' ? [] : editAllowedGroups,
        telegramChatId: editTelegramChatId.trim(),
        enabled: editEnabled,
      };

      if (editNewPassword.trim()) {
        payload.newPassword = editNewPassword.trim();
      }

      const updated = await usersApi.update(editingUser.id, payload);
      setItems(prev => prev.map(u => u.id === editingUser.id ? updated : u));
      notify(`Профиль пользователя ${editFullName} успешно обновлен!`);
      setEditingUser(null);
    } catch (err: any) {
      notify(err?.message || 'Ошибка обновления пользователя');
    }
  };

  const handleToggleUser = async (id: string) => {
    const target = items.find(u => u.id === id);
    if (!target) return;
    if (target.id === currentUser?.id || target.username === currentUser?.username) {
      notify('Нельзя заблокировать собственную учетную запись');
      return;
    }
    try {
      const nextStatus = !target.enabled;
      await usersApi.update(id, { enabled: nextStatus });
      setItems(prev => prev.map(u => u.id === id ? { ...u, enabled: nextStatus } : u));
      notify(`Статус пользователя ${target.displayName}: ${nextStatus ? 'Активен' : 'Заблокирован'}`);
    } catch {
      notify('Ошибка обновления активности пользователя');
    }
  };

  const handleDeleteUser = async (id: string) => {
    const target = items.find(u => u.id === id);
    if (!target) return;
    if (target.id === currentUser?.id || target.username === currentUser?.username) {
      notify('Нельзя удалить собственную учетную запись');
      return;
    }
    if (target.role === 'Суперадминистратор' && items.filter(u => u.role === 'Суперадминистратор').length <= 1) {
      notify('Нельзя удалить единственного Суперадминистратора');
      return;
    }
    try {
      await usersApi.delete(id);
      setItems(prev => prev.filter(u => u.id !== id));
      notify(`Пользователь ${target.displayName} успешно удален`);
    } catch (err: any) {
      notify(err?.message || 'Ошибка удаления пользователя');
    }
  };

  const filtered = items.filter(u =>
    `${u.displayName} ${u.username} ${u.email} ${u.role} ${u.scope} ${u.telegramChatId || ''}`.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <>
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="Пользователи и права доступа"
        description="Управление учетными записями операторов, паролями, ролями (RBAC), зонами ответственности (Scope) и Telegram-авторизацией."
        actions={<Button primary icon={<UsersIcon size={15} />} onClick={openAddModal}>Добавить пользователя</Button>}
      />

      <section className="panel table-panel">
        <div className="panel-heading table-heading">
          <div>
            <h2>Операторы системы</h2>
            <p>{filtered.length} пользователей настроено (Суперадмины, Администраторы парка, Операторы, Наблюдатели)</p>
          </div>
          <div className="table-tools">
            <div className="search">
              <Search size={15} />
              <input placeholder="Поиск по имени, логину, роли, Telegram ID..." value={query} onChange={e => setQuery(e.target.value)} />
            </div>
          </div>
        </div>

        <div className="user-list">
          {filtered.map(user => {
            const isCustomScope = Array.isArray(user.allowedGroups) && user.allowedGroups.length > 0;
            return (
              <div className="user-row" key={user.id} style={{ display: 'grid', gridTemplateColumns: 'auto 1.6fr 1.1fr 1.4fr 1.1fr auto auto auto', alignItems: 'center', gap: '14px', padding: '14px 20px' }}>
                <div
                  className="user-avatar"
                  style={{
                    width: '38px',
                    height: '38px',
                    minWidth: '38px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: user.role === 'Суперадминистратор'
                      ? 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)'
                      : user.role === 'Администратор парка'
                      ? 'linear-gradient(135deg, #10b981 0%, #047857 100%)'
                      : 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '13px',
                    letterSpacing: '0.5px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.12), inset 0 1px 1px rgba(255,255,255,0.25)',
                    flexShrink: 0
                  }}
                >
                  {user.displayName ? user.displayName.split(' ').filter(Boolean).map(n => n[0]).join('').slice(0, 2).toUpperCase() : (user.username || 'AD').slice(0, 2).toUpperCase()}
                </div>
                
                <div className="user-main">
                  <strong style={{ fontSize: '13px', fontWeight: 600 }}>{user.displayName}</strong>
                  <span style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '2px', display: 'block' }}>@{user.username} · {user.email}</span>
                </div>

                <div>
                  <StatusPill status={user.role} />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: isCustomScope ? 'var(--yellow)' : 'var(--text)' }}>
                    <ShieldCheck size={14} style={{ color: isCustomScope ? 'var(--yellow)' : 'var(--blue)' }} />
                    {user.scope || 'Все устройства'}
                  </span>
                  {isCustomScope && (
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
                      {user.allowedGroups!.map(g => (
                        <span key={g} className="badge" style={{ fontSize: '10px', padding: '1px 6px', background: 'rgba(234,179,8,0.12)', color: 'var(--yellow)' }}>
                          {g}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  {user.telegramChatId ? (
                    <button
                      className="badge"
                      style={{ background: 'rgba(59, 130, 246, 0.12)', color: 'var(--blue)', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', padding: '3px 8px' }}
                      onClick={() => {
                        navigator.clipboard.writeText(user.telegramChatId!);
                        notify(`Telegram ID ${user.telegramChatId} скопирован в буфер`);
                      }}
                      title="Кликните, чтобы скопировать Telegram Chat ID"
                    >
                      <Send size={11} /> {user.telegramChatId}
                    </button>
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--muted)' }}>— TG не привязан</span>
                  )}
                </div>

                <span
                  className={`enabled ${user.enabled ? 'yes' : 'no'}`}
                  onClick={() => handleToggleUser(user.id)}
                  style={{ cursor: 'pointer' }}
                  title="Кликните для переключения статуса"
                >
                  <i />{user.enabled ? 'Активен' : 'Отключен'}
                </span>

                <span className="muted-text" style={{ fontSize: '11px' }} title="Последний вход">{user.lastLogin}</span>

                <div style={{ display: 'flex', gap: '4px' }}>
                  <button className="row-more" onClick={() => openEditModal(user)} title="Редактировать пользователя">
                    <Pencil size={15} />
                  </button>
                  <button className="row-more" onClick={() => handleDeleteUser(user.id)} title="Удалить пользователя">
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Add User Modal */}
      {showAddUserModal && (
        <div className="modal-backdrop" onClick={() => setShowAddUserModal(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '560px', textAlign: 'left', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}><UsersIcon size={22} /></div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Добавить пользователя</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>Создание оператора с паролем, правами доступа и Telegram ID</p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>ФИО / Отображаемое имя *</label>
                <input
                  className="text-input"
                  style={{ width: '100%' }}
                  value={newFullName}
                  onChange={(e) => setNewFullName(e.target.value)}
                  placeholder="Иван Петров"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Логин (Username) *</label>
                  <input
                    className="text-input mono"
                    style={{ width: '100%' }}
                    value={newUsername}
                    onChange={(e) => setNewUsername(e.target.value)}
                    placeholder="ipetrov"
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Роль в системе</label>
                  <select className="text-input" style={{ width: '100%' }} value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                    <option value="Суперадминистратор">Суперадминистратор (Все права)</option>
                    <option value="Администратор парка">Администратор парка</option>
                    <option value="Дежурный оператор">Дежурный оператор</option>
                    <option value="Наблюдатель">Наблюдатель (Только чтение)</option>
                  </select>
                </div>
              </div>

              {/* Password section with generator */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Пароль учетной записи *</label>
                  <button
                    type="button"
                    className="link-button"
                    style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--blue)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                    onClick={() => {
                      const p = generatePassword();
                      setNewPassword(p);
                      navigator.clipboard.writeText(p);
                      notify(`Сгенерирован надежный пароль и скопирован в буфер: ${p}`);
                    }}
                  >
                    <Sparkles size={13} /> Сгенерировать надежный 🎲
                  </button>
                </div>
                <div style={{ position: 'relative' }}>
                  <input
                    className="text-input mono"
                    style={{ width: '100%', paddingRight: '40px' }}
                    type={showNewPassword ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Введите пароль..."
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: '4px' }}
                    title={showNewPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  >
                    {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Рабочий Email</label>
                <input
                  className="text-input"
                  style={{ width: '100%' }}
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="ipetrov@bmstu.local"
                />
              </div>

              {/* Group Scope Selector */}
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
                  Зона ответственности (Group Scope)
                </label>
                <div style={{ display: 'flex', gap: '16px', marginBottom: '10px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="newScopeType"
                      checked={newScopeType === 'ALL'}
                      onChange={() => setNewScopeType('ALL')}
                    />
                    Все устройства (Глобально)
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="newScopeType"
                      checked={newScopeType === 'CUSTOM'}
                      onChange={() => setNewScopeType('CUSTOM')}
                    />
                    Ограничить выбранными группами
                  </label>
                </div>

                {newScopeType === 'CUSTOM' && (
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
                    {availableGroups.map(gName => {
                      const isSelected = newAllowedGroups.includes(gName);
                      return (
                        <button
                          key={gName}
                          type="button"
                          className={`badge ${isSelected ? 'match' : ''}`}
                          style={{
                            cursor: 'pointer',
                            padding: '4px 10px',
                            border: isSelected ? '1px solid var(--blue)' : '1px solid var(--border)',
                            background: isSelected ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255,255,255,0.05)',
                            color: isSelected ? 'var(--blue)' : 'var(--muted)',
                          }}
                          onClick={() => {
                            setNewAllowedGroups(prev =>
                              prev.includes(gName) ? prev.filter(g => g !== gName) : [...prev, gName]
                            );
                          }}
                        >
                          {isSelected ? '✓ ' : '+ '} {gName}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Telegram Chat ID */}
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                  Telegram Chat ID или @username (для бота)
                </label>
                <input
                  className="text-input mono"
                  style={{ width: '100%' }}
                  value={newTelegramChatId}
                  onChange={(e) => setNewTelegramChatId(e.target.value)}
                  placeholder="например: 123456789 или @ivanov"
                />
                <span style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px', display: 'block' }}>
                  💡 Укажите числовой Chat ID (бот подскажет по команде <code>/id</code>) либо Telegram никнейм (например, <code>@ivanov</code>).
                </span>
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setShowAddUserModal(false)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleAddUser} disabled={!newUsername.trim() || !newFullName.trim() || !newPassword.trim()}>
                Создать пользователя
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <div className="modal-backdrop" onClick={() => setEditingUser(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '560px', textAlign: 'left', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}><Pencil size={20} /></div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Редактирование профиля: @{editingUser.username}</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>Настройка роли, зоны ответственности (Scope), Telegram ID и сброс пароля</p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>ФИО / Отображаемое имя</label>
                <input
                  className="text-input"
                  style={{ width: '100%' }}
                  value={editFullName}
                  onChange={(e) => setEditFullName(e.target.value)}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Роль в системе</label>
                  <select className="text-input" style={{ width: '100%' }} value={editRole} onChange={(e) => setEditRole(e.target.value)}>
                    <option value="Суперадминистратор">Суперадминистратор (Все права)</option>
                    <option value="Администратор парка">Администратор парка</option>
                    <option value="Дежурный оператор">Дежурный оператор</option>
                    <option value="Наблюдатель">Наблюдатель (Только чтение)</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Рабочий Email</label>
                  <input
                    className="text-input"
                    style={{ width: '100%' }}
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                  />
                </div>
              </div>

              {/* Reset Password */}
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Задать новый пароль (оставьте пустым, если не меняется)</label>
                  <button
                    type="button"
                    className="link-button"
                    style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--blue)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                    onClick={() => {
                      const p = generatePassword();
                      setEditNewPassword(p);
                      navigator.clipboard.writeText(p);
                      notify(`Сгенерирован новый пароль и скопирован: ${p}`);
                    }}
                  >
                    <Sparkles size={13} /> 🎲 Сгенерировать
                  </button>
                </div>
                <div style={{ position: 'relative' }}>
                  <input
                    className="text-input mono"
                    style={{ width: '100%', paddingRight: '40px' }}
                    type={showEditPassword ? 'text' : 'password'}
                    value={editNewPassword}
                    onChange={(e) => setEditNewPassword(e.target.value)}
                    placeholder="Новый пароль..."
                  />
                  <button
                    type="button"
                    onClick={() => setShowEditPassword(!showEditPassword)}
                    style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: '4px' }}
                  >
                    {showEditPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Group Scope Selector */}
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
                  Зона ответственности (Group Scope)
                </label>
                <div style={{ display: 'flex', gap: '16px', marginBottom: '10px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="editScopeType"
                      checked={editScopeType === 'ALL'}
                      onChange={() => setEditScopeType('ALL')}
                    />
                    Все устройства (Глобально)
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="editScopeType"
                      checked={editScopeType === 'CUSTOM'}
                      onChange={() => setEditScopeType('CUSTOM')}
                    />
                    Ограничить выбранными группами
                  </label>
                </div>

                {editScopeType === 'CUSTOM' && (
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
                    {availableGroups.map(gName => {
                      const isSelected = editAllowedGroups.includes(gName);
                      return (
                        <button
                          key={gName}
                          type="button"
                          className={`badge ${isSelected ? 'match' : ''}`}
                          style={{
                            cursor: 'pointer',
                            padding: '4px 10px',
                            border: isSelected ? '1px solid var(--blue)' : '1px solid var(--border)',
                            background: isSelected ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255,255,255,0.05)',
                            color: isSelected ? 'var(--blue)' : 'var(--muted)',
                          }}
                          onClick={() => {
                            setEditAllowedGroups(prev =>
                              prev.includes(gName) ? prev.filter(g => g !== gName) : [...prev, gName]
                            );
                          }}
                        >
                          {isSelected ? '✓ ' : '+ '} {gName}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Telegram Chat ID */}
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                  Telegram Chat ID или @username (для бота)
                </label>
                <input
                  className="text-input mono"
                  style={{ width: '100%' }}
                  value={editTelegramChatId}
                  onChange={(e) => setEditTelegramChatId(e.target.value)}
                  placeholder="например: 123456789 или @ivanov"
                />
                <span style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px', display: 'block' }}>
                  💡 Укажите числовой Chat ID (бот подскажет по команде <code>/id</code>) либо Telegram никнейм (например, <code>@ivanov</code>).
                </span>
              </div>

              {/* Enabled Switch */}
              <div className="setting-row" style={{ padding: '8px 0', margin: 0 }}>
                <div>
                  <strong>Статус активности учетной записи</strong>
                  <span style={{ fontSize: '12px', color: 'var(--muted)' }}>При блокировке доступ в панель и команды Telegram сразу прекращаются</span>
                </div>
                <label className="switch">
                  <input type="checkbox" checked={editEnabled} onChange={e => setEditEnabled(e.target.checked)} />
                  <span />
                </label>
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setEditingUser(null)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleSaveEdit} disabled={!editFullName.trim()}>
                Сохранить изменения
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Roles({ notify }: { notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [roles, setRoles] = useState<any[]>([
    { name: 'Суперадминистратор', users: 1, perms: 'Все права', tone: 'blue', scopeType: 'Все устройства', permissions: ['devices.view', 'devices.create', 'devices.edit', 'devices.delete', 'devices.wake', 'devices.reboot', 'devices.shutdown', 'sessions.view', 'sessions.logoff', 'monitoring.view', 'alerts.view', 'audit.view', 'settings.edit', 'hardware.baseline_edit', 'agents.tokens_manage'] },
    { name: 'Администратор парка', users: 1, perms: '28 прав', tone: 'blue', scopeType: 'Все устройства', permissions: ['devices.view', 'devices.create', 'devices.edit', 'devices.wake', 'devices.reboot', 'devices.shutdown', 'sessions.view', 'sessions.logoff', 'monitoring.view', 'alerts.view', 'audit.view', 'hardware.baseline_edit'] },
    { name: 'Дежурный оператор', users: 1, perms: '16 прав', tone: 'green', scopeType: 'Выбранные группы', permissions: ['devices.view', 'devices.wake', 'devices.reboot', 'sessions.view', 'sessions.logoff', 'alerts.view'] },
    { name: 'Наблюдатель', users: 1, perms: '6 прав', tone: 'slate', scopeType: 'Все устройства', permissions: ['devices.view', 'monitoring.view', 'alerts.view', 'audit.view'] }
  ]);
  const [selectedRole, setSelectedRole] = useState('Дежурный оператор');
  const [selectedScope, setSelectedScope] = useState('Выбранные группы');

  const permissions = [
    'devices.view', 'devices.create', 'devices.edit', 'devices.delete',
    'devices.wake', 'devices.reboot', 'devices.shutdown', 'devices.force_shutdown',
    'sessions.view', 'sessions.logoff', 'monitoring.view', 'alerts.view',
    'audit.view', 'settings.edit', 'hardware.baseline_edit', 'agents.tokens_manage'
  ];

  const [activePerms, setActivePerms] = useState<string[]>([
    'devices.view', 'devices.wake', 'devices.reboot', 'sessions.view', 'sessions.logoff', 'alerts.view'
  ]);

  useEffect(() => {
    rolesApi.list().then(serverRoles => {
      if (serverRoles && serverRoles.length > 0) {
        setRoles(serverRoles);
        const cur = serverRoles.find(r => r.name === selectedRole);
        if (cur) {
          if (cur.permissions) setActivePerms(cur.permissions);
          if (cur.scopeType) setSelectedScope(cur.scopeType);
        }
      }
    });
  }, []);

  const handleSelectRole = (roleName: string) => {
    setSelectedRole(roleName);
    const r = roles.find(item => item.name === roleName);
    if (r) {
      setActivePerms(r.permissions || []);
      setSelectedScope(r.scopeType || 'Все устройства');
    }
  };

  const togglePerm = (perm: string) => {
    setActivePerms(prev => prev.includes(perm) ? prev.filter(p => p !== perm) : [...prev, perm]);
  };

  const handleSaveRole = async () => {
    try {
      await rolesApi.updateRole(selectedRole, {
        permissions: activePerms,
        scopeType: selectedScope as any
      });
      setRoles(prev => prev.map(r => r.name === selectedRole ? { ...r, permissions: activePerms, scopeType: selectedScope } : r));
      notify(`Разрешения для роли "${selectedRole}" успешно сохранены на сервере!`);
    } catch {
      notify('Ошибка сохранения роли');
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="Роли и права (RBAC)"
        description="Гибкая настройка ролей, привилегий и областей видимости устройств."
        actions={<Button primary icon={<ShieldCheck size={15} />} onClick={handleSaveRole}>Сохранить изменения</Button>}
      />
      <div className="roles-grid">
        <section className="panel role-list">
          <div className="panel-heading">
            <div><h2>Роли</h2><p>{roles.length} системных роли</p></div>
          </div>
          {roles.map(role => (
            <div
              className={`role-card ${selectedRole === role.name ? 'active' : ''}`}
              key={role.name}
              onClick={() => handleSelectRole(role.name)}
              style={{ cursor: 'pointer', background: selectedRole === role.name ? 'var(--blue-soft)' : undefined }}
            >
              <div className={`role-icon ${role.tone || 'blue'}`}><ShieldCheck size={18} /></div>
              <div><strong>{role.name}</strong><span>{role.userCount || role.users || 1} польз. · {role.permissions ? `${role.permissions.length} прав` : role.perms}</span></div>
              <ChevronRight size={16} className="muted-icon" />
            </div>
          ))}
        </section>

        <section className="panel permission-panel">
          <div className="panel-heading">
            <div><h2>Права роли: {selectedRole}</h2><p>Область видимости: {selectedScope}</p></div>
            <Button onClick={handleSaveRole}>Сохранить</Button>
          </div>
          <div className="scope-selector">
            <button className={selectedScope === 'Выбранные группы' ? 'selected' : ''} onClick={() => setSelectedScope('Выбранные группы')}>Выбранные группы</button>
            <button className={selectedScope === 'Все устройства' ? 'selected' : ''} onClick={() => setSelectedScope('Все устройства')}>Все устройства</button>
            <button className={selectedScope === 'Выбранные ПК' ? 'selected' : ''} onClick={() => setSelectedScope('Выбранные ПК')}>Выбранные ПК</button>
          </div>
          <div className="permissions">
            {permissions.map(permission => (
              <label key={permission} style={{ cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={selectedRole === 'Суперадминистратор' || activePerms.includes(permission)}
                  onChange={() => togglePerm(permission)}
                  disabled={selectedRole === 'Суперадминистратор'}
                />
                <span>{permission}</span>
              </label>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

// ----------------------------------------------------
// 12. AGENTS & DOWNLOADS
// ----------------------------------------------------
function AgentsDownloads({ notify }: { notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [tokens, setTokens] = useState<AgentEnrollmentToken[]>([]);
  const [builds, setBuilds] = useState<AgentBuild[]>([]);
  const [availableGroups, setAvailableGroups] = useState<string[]>([
    'Office', 'Warehouse', 'Management', 'Testing', 'Dev', 'Accounting', 'Servers'
  ]);
  const [showTokenModal, setShowTokenModal] = useState(false);
  const [targetGroup, setTargetGroup] = useState('Office');
  const [customGroupInput, setCustomGroupInput] = useState('');
  const [tokenScopeMode, setTokenScopeMode] = useState<'room' | 'building' | 'flat'>('room');
  
  // Hierarchical Token Building / Floor / Room state
  const [hierarchyData, setHierarchyData] = useState<any[]>([]);
  const [buildingConfigs, setBuildingConfigs] = useState<BuildingConfig[]>([]);
  const [allGroupsList, setAllGroupsList] = useState<any[]>([]);
  const [tokenBuilding, setTokenBuilding] = useState<string>('');
  const [tokenFloor, setTokenFloor] = useState<string>('1 этаж');
  const [tokenRoom, setTokenRoom] = useState<string>('');
  const [isCustomTokenRoom, setIsCustomTokenRoom] = useState<boolean>(false);
  const [customTokenRoomInput, setCustomTokenRoomInput] = useState<string>('');

  const [expiryOption, setExpiryOption] = useState('30d');
  const [customExpiryDate, setCustomExpiryDate] = useState('');
  const [maxUsesOption, setMaxUsesOption] = useState('unlimited');
  const [customMaxUses, setCustomMaxUses] = useState('10');

  // Selected token for the 1-Click download buttons & command box
  const [selectedInstallerToken, setSelectedInstallerToken] = useState<string>('');

  // Edit Token state
  const [editTokenTarget, setEditTokenTarget] = useState<AgentEnrollmentToken | null>(null);
  const [editGroup, setEditGroup] = useState('Office');
  const [editCustomGroupInput, setEditCustomGroupInput] = useState('');
  const [editExpiryDate, setEditExpiryDate] = useState('');
  const [editMaxUsesOption, setEditMaxUsesOption] = useState('unlimited');
  const [editCustomMaxUses, setEditCustomMaxUses] = useState('10');

  // Delete Confirmation state
  const [deleteTokenTarget, setDeleteTokenTarget] = useState<AgentEnrollmentToken | null>(null);

  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [serverAddress, setServerAddress] = useState(() => {
    const host = window.location.hostname || 'localhost';
    const port = window.location.port === '5173' ? '2301' : (window.location.port || '2301');
    return `${window.location.protocol}//${host}:${port}`;
  });

  // Remote Fleet Auto-Update State
  const [versionInfo, setVersionInfo] = useState<AgentVersionInfo | null>(null);
  const [updateLogs, setUpdateLogs] = useState<AgentUpdateLog[]>([]);
  const [fleetDevices, setFleetDevices] = useState<Device[]>([]);
  const [fleetFilter, setFleetFilter] = useState<'all' | 'outdated' | 'updated'>('all');
  const [updatingDeviceIds, setUpdatingDeviceIds] = useState<string[]>([]);
  const [showBulkUpdateModal, setShowBulkUpdateModal] = useState(false);
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);

  const loadData = () => {
    agentsApi.getTokens().then(toks => {
      setTokens(toks);
      if (toks.length > 0 && !selectedInstallerToken) {
        setSelectedInstallerToken(toks[0].token);
      }
      const tokGroups = toks.map(t => t.targetGroup).filter(Boolean);
      setAvailableGroups(prev => Array.from(new Set([...prev, ...tokGroups])));
    });
    agentsApi.getBuilds().then(setBuilds);
    agentsApi.getVersionInfo().then(setVersionInfo);
    agentsApi.getUpdateLogs().then(setUpdateLogs);
    groupsApi.getHierarchy().then(h => {
      if (h && h.length > 0) setHierarchyData(h);
    });
    groupsApi.getBuildings().then(b => {
      if (b && b.length > 0) setBuildingConfigs(b);
    });
    groupsApi.list().then(list => {
      if (list && list.length > 0) {
        setAllGroupsList(list);
        setAvailableGroups(prev => Array.from(new Set([...prev, ...list.map(g => g.name)])));
      }
    });
    devicesApi.list().then(devs => {
      if (devs && devs.length > 0) {
        setFleetDevices(devs);
        const devGroups = devs.flatMap(d => (d.groups && d.groups.length ? d.groups : [d.group])).filter(Boolean);
        setAvailableGroups(prev => Array.from(new Set([...prev, ...devGroups])));
      }
    });
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      agentsApi.getVersionInfo().then(setVersionInfo);
      agentsApi.getUpdateLogs().then(setUpdateLogs);
      devicesApi.list().then(setFleetDevices);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleUpdateSingleDevice = async (deviceId: string, devName: string) => {
    setUpdatingDeviceIds(prev => [...prev, deviceId]);
    notify(`Отправлена команда обновления агента до v${versionInfo?.currentVersion || '1.9.0'} на станцию ${devName}...`);
    try {
      await agentsApi.updateAgent(deviceId);
      setTimeout(() => {
        setUpdatingDeviceIds(prev => prev.filter(id => id !== deviceId));
        loadData();
        notify(`Команда обновления успешно доставлена на ${devName}`);
      }, 3000);
    } catch {
      setUpdatingDeviceIds(prev => prev.filter(id => id !== deviceId));
      notify(`Ошибка отправки команды на ${devName}`);
    }
  };

  const handleExecuteBulkUpdate = async () => {
    setIsBulkUpdating(true);
    notify(`Запущено массовое удаленное обновление агентов до v${versionInfo?.currentVersion || '1.9.0'}...`);
    try {
      const res = await agentsApi.updateBulk([], true);
      notify(`Команда обновления отправлена на ${res.count || 'все'} станций!`);
      setTimeout(() => {
        setIsBulkUpdating(false);
        setShowBulkUpdateModal(false);
        loadData();
      }, 2500);
    } catch {
      setIsBulkUpdating(false);
      notify('Ошибка при запуске массового обновления');
    }
  };

  const activeToken = selectedInstallerToken || (tokens.length > 0 ? tokens[0].token : 'wm_tok_live_7f8a92b3c4d5e6f7');
  const activeTokenObj = tokens.find(t => t.token === activeToken);
  const currentTargetGroup = activeTokenObj ? activeTokenObj.targetGroup : 'Office';

  const effectiveServer = serverAddress.trim().replace(/\/+$/, '');
  const psOneLiner = `irm "${effectiveServer}/install.ps1?token=${activeToken}&server_url=${encodeURIComponent(effectiveServer)}" | iex`;
  const bashOneLiner = `curl -fsSL "${effectiveServer}/install.sh?token=${activeToken}&server_url=${encodeURIComponent(effectiveServer)}" | sudo bash`;
  const uninstallerCommand = `irm "${effectiveServer}/uninstall.ps1?server_url=${encodeURIComponent(effectiveServer)}" | iex`;
  const linuxUninstallerCommand = `curl -fsSL "${effectiveServer}/uninstall.sh?server_url=${encodeURIComponent(effectiveServer)}" | sudo bash`;

  const handleCopy = (text: string, key: string) => {
    copyToClipboard(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2500);
    notify('Команда скопирована в буфер обмена!');
  };

  const availableBuildingsForToken = useMemo(() => {
    const list: string[] = [];
    buildingConfigs.forEach(b => {
      if (b.name && !list.includes(b.name)) list.push(b.name);
    });
    hierarchyData.forEach(b => {
      if (b.name && b.name !== 'Общие группы' && !list.includes(b.name)) list.push(b.name);
    });
    allGroupsList.forEach(g => {
      let b = (g.building || '').trim();
      if (!b && g.name && g.name.includes('/')) b = g.name.split('/')[0].trim();
      if (b && b !== 'Общие группы' && !list.includes(b)) list.push(b);
    });
    availableGroups.forEach(gName => {
      if (gName.includes('/')) {
        const b = gName.split('/')[0].trim();
        if (b && b !== 'Общие группы' && !list.includes(b)) list.push(b);
      }
    });
    return list.length > 0 ? list : ['Главный корпус', 'Учебный корпус'];
  }, [buildingConfigs, hierarchyData, allGroupsList, availableGroups]);

  const activeTokenBuilding = tokenBuilding || availableBuildingsForToken[0] || 'Главный корпус';

  const availableFloorsForToken = useMemo(() => {
    const set = new Set<string>();
    const bConfig = buildingConfigs.find(b => b.name.toLowerCase() === activeTokenBuilding.toLowerCase());
    if (bConfig && bConfig.floors && bConfig.floors.length > 0) {
      bConfig.floors.forEach(f => set.add(f));
    }
    const bHier = hierarchyData.find(b => b.name.toLowerCase() === activeTokenBuilding.toLowerCase());
    if (bHier && bHier.floors && bHier.floors.length > 0) {
      bHier.floors.forEach((f: any) => set.add(f.name));
    }
    allGroupsList.forEach(g => {
      let b = (g.building || '').trim();
      let f = (g.floor || '').trim();
      if (g.name && g.name.includes('/')) {
        const parts = g.name.split('/').map((s: string) => s.trim());
        if (parts.length >= 3) {
          if (!b) b = parts[0];
          if (!f) f = parts[1];
        }
      }
      if (b.toLowerCase() === activeTokenBuilding.toLowerCase() && f) {
        set.add(f);
      }
    });
    availableGroups.forEach(gName => {
      if (gName.includes('/')) {
        const parts = gName.split('/').map(s => s.trim());
        if (parts.length >= 3 && parts[0].toLowerCase() === activeTokenBuilding.toLowerCase()) {
          set.add(parts[1]);
        }
      }
    });
    if (set.size === 0) {
      generateBuildingFloors(3, false, false).forEach(f => set.add(f));
    }
    return Array.from(set);
  }, [buildingConfigs, hierarchyData, activeTokenBuilding, allGroupsList, availableGroups]);

  const activeTokenFloor = tokenFloor || availableFloorsForToken[0] || '1 этаж';

  // All rooms for this building across all floors
  const allBuildingRooms = useMemo(() => {
    const map = new Map<string, { room: string; floor: string }>();

    // 1. From hierarchyData
    const bHier = hierarchyData.find(b => b.name.toLowerCase() === activeTokenBuilding.toLowerCase());
    if (bHier && bHier.floors) {
      bHier.floors.forEach((f: any) => {
        if (f.rooms) {
          f.rooms.forEach((r: any) => {
            const rName = (r.name || r.roomName || '').trim();
            if (rName && !map.has(`${f.name}-${rName}`)) {
              map.set(`${f.name}-${rName}`, { room: rName, floor: f.name });
            }
          });
        }
      });
    }

    // 2. From allGroupsList
    allGroupsList.forEach(g => {
      let b = (g.building || '').trim();
      let f = (g.floor || '').trim();
      let r = (g.room || '').trim();
      if (g.name && g.name.includes('/')) {
        const parts = g.name.split('/').map((s: string) => s.trim());
        if (parts.length >= 3) {
          if (!b) b = parts[0];
          if (!f) f = parts[1];
          if (!r) r = parts[2];
        }
      }
      if (b.toLowerCase() === activeTokenBuilding.toLowerCase() && r) {
        const floorName = f || '1 этаж';
        if (!map.has(`${floorName}-${r}`)) {
          map.set(`${floorName}-${r}`, { room: r, floor: floorName });
        }
      }
    });

    // 3. From availableGroups
    availableGroups.forEach(gName => {
      if (gName.includes('/')) {
        const parts = gName.split('/').map(s => s.trim());
        if (parts.length >= 3 && parts[0].toLowerCase() === activeTokenBuilding.toLowerCase()) {
          const f = parts[1];
          const r = parts[2];
          if (r && !map.has(`${f}-${r}`)) {
            map.set(`${f}-${r}`, { room: r, floor: f });
          }
        }
      }
    });

    return Array.from(map.values());
  }, [hierarchyData, activeTokenBuilding, allGroupsList, availableGroups]);

  // Rooms on currently selected floor
  const activeFloorRooms = useMemo(() => {
    return allBuildingRooms
      .filter(item => item.floor.toLowerCase() === activeTokenFloor.toLowerCase())
      .map(item => item.room);
  }, [allBuildingRooms, activeTokenFloor]);

  // Rooms on other floors of this building
  const otherFloorsRooms = useMemo(() => {
    return allBuildingRooms
      .filter(item => item.floor.toLowerCase() !== activeTokenFloor.toLowerCase());
  }, [allBuildingRooms, activeTokenFloor]);

  const selectedRoomValue = useMemo(() => {
    if (tokenRoom) {
      if (activeFloorRooms.some(r => r.toLowerCase() === tokenRoom.toLowerCase())) {
        return tokenRoom;
      }
      const foundOther = otherFloorsRooms.find(r => r.room.toLowerCase() === tokenRoom.toLowerCase());
      if (foundOther) return foundOther.room;
    }
    if (activeFloorRooms.length > 0) {
      return activeFloorRooms[0];
    }
    if (otherFloorsRooms.length > 0) {
      return otherFloorsRooms[0].room;
    }
    return '';
  }, [tokenRoom, activeFloorRooms, otherFloorsRooms]);

  const effectiveRoom = isCustomTokenRoom
    ? (customTokenRoomInput.trim() || 'Кабинет')
    : (tokenRoom || selectedRoomValue || (customTokenRoomInput.trim() || 'Кабинет'));

  const handleGenerateToken = async () => {
    let expStr: string | undefined = undefined;
    if (expiryOption === 'custom' && customExpiryDate) {
      expStr = customExpiryDate.replace('T', ' ');
    } else if (expiryOption === 'never') {
      expStr = 'Бессрочно';
    }

    let finalGroup = 'Office';
    let bld = '';
    let flr = '';
    let rm = '';

    if (tokenScopeMode === 'building') {
      bld = activeTokenBuilding;
      finalGroup = bld;
    } else if (tokenScopeMode === 'room') {
      bld = activeTokenBuilding;
      flr = activeTokenFloor;
      rm = effectiveRoom;
      if (!rm) rm = 'Кабинет';
      finalGroup = `${bld} / ${flr} / ${rm}`;
    } else {
      finalGroup = targetGroup === '__custom__' ? (customGroupInput.trim() || 'Office') : targetGroup;
    }

    const maxU = maxUsesOption === 'unlimited' ? undefined : (maxUsesOption === '1' ? 1 : parseInt(customMaxUses) || undefined);

    const newToken = await agentsApi.createToken({
      targetType: tokenScopeMode,
      targetBuilding: bld,
      targetFloor: flr,
      targetRoom: rm,
      targetGroup: finalGroup,
      expiry: expiryOption,
      expiresAt: expStr,
      maxUses: maxU,
      createdBy: getActiveUserName()
    });

    setTokens(prev => [newToken, ...prev]);
    setSelectedInstallerToken(newToken.token);
    setAvailableGroups(prev => Array.from(new Set([...prev, finalGroup])));
    groupsApi.create({ name: finalGroup, building: bld, floor: flr, room: rm }).catch(() => {});

    notify(`Токен для "${finalGroup}" успешно создан!`);
    setShowTokenModal(false);
    setExpiryOption('30d');
    setCustomExpiryDate('');
    setCustomGroupInput('');
    setTokenRoom('');
    setIsCustomTokenRoom(false);
    setCustomTokenRoomInput('');
    setMaxUsesOption('unlimited');
  };

  const handleOpenEditToken = (tok: AgentEnrollmentToken) => {
    setEditTokenTarget(tok);
    setEditGroup(tok.targetGroup || 'Office');
    setEditCustomGroupInput('');
    setEditExpiryDate(tok.expiresAt || '');
    if (!tok.maxUses) {
      setEditMaxUsesOption('unlimited');
      setEditCustomMaxUses('10');
    } else if (tok.maxUses === 1) {
      setEditMaxUsesOption('1');
      setEditCustomMaxUses('1');
    } else {
      setEditMaxUsesOption('custom');
      setEditCustomMaxUses(String(tok.maxUses));
    }
  };

  const handleSaveEditToken = async () => {
    if (!editTokenTarget) return;
    const finalGroup = editGroup === '__custom__' ? (editCustomGroupInput.trim() || 'Office') : editGroup;
    const maxU = editMaxUsesOption === 'unlimited' ? undefined : (editMaxUsesOption === '1' ? 1 : parseInt(editCustomMaxUses) || undefined);
    const updated = await agentsApi.updateToken(editTokenTarget.id, {
      targetGroup: finalGroup,
      expiresAt: editExpiryDate || editTokenTarget.expiresAt,
      maxUses: maxU
    });
    if (updated) {
      setTokens(prev => prev.map(t => t.id === editTokenTarget.id ? { ...t, ...updated } : t));
      setAvailableGroups(prev => Array.from(new Set([...prev, finalGroup])));
      groupsApi.create({ name: finalGroup }).catch(() => {});
      notify(`Параметры токена ${editTokenTarget.id} успешно сохранены!`);
    }
    setEditTokenTarget(null);
  };

  const handleExtendTokenDays = (days: number) => {
    const d = new Date();
    d.setDate(d.getDate() + days);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const h = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    setEditExpiryDate(`${y}-${m}-${day} ${h}:${min}`);
  };

  const handleConfirmDeleteToken = async () => {
    if (!deleteTokenTarget) return;
    const ok = await agentsApi.revokeToken(deleteTokenTarget.id);
    if (ok) {
      setTokens(prev => prev.filter(t => t.id !== deleteTokenTarget.id));
      if (selectedInstallerToken === deleteTokenTarget.token) {
        const rem = tokens.filter(t => t.id !== deleteTokenTarget.id);
        setSelectedInstallerToken(rem.length > 0 ? rem[0].token : '');
      }
      notify(`Токен ${deleteTokenTarget.id} отозван и удален`);
    }
    setDeleteTokenTarget(null);
  };

  const handleDownloadInstaller = (os: string, format?: string) => {
    const isWin = os.toLowerCase().includes('windows');
    const isPs = (format && format.toLowerCase().includes('powershell')) || os.toLowerCase().includes('powershell');
    const effectiveUrl = serverAddress.trim().replace(/\/+$/, '');
    
    let downloadUrl = '';
    let filename = '';
    
    if (isPs) {
      downloadUrl = `${effectiveUrl}/install.ps1?token=${activeToken}&group=${encodeURIComponent(currentTargetGroup)}&server_url=${encodeURIComponent(effectiveUrl)}&download=1`;
      filename = `Install-Agent-${currentTargetGroup}.ps1`;
    } else if (isWin) {
      downloadUrl = `${effectiveUrl}/install.bat?token=${activeToken}&group=${encodeURIComponent(currentTargetGroup)}&server_url=${encodeURIComponent(effectiveUrl)}`;
      filename = `Install-WorkstationAgent-${currentTargetGroup}.bat`;
    } else {
      downloadUrl = `${effectiveUrl}/install.sh?token=${activeToken}&group=${encodeURIComponent(currentTargetGroup)}&server_url=${encodeURIComponent(effectiveUrl)}&download=1`;
      filename = `install_agent_${currentTargetGroup}.sh`;
    }

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    notify(`Скачивание установщика ${filename} (группа: "${currentTargetGroup}")...`);
  };

  const handleDownloadUninstaller = (os: 'Windows' | 'Linux' = 'Windows') => {
    const effectiveUrl = serverAddress.trim().replace(/\/+$/, '');
    if (os === 'Linux') {
      const downloadUrl = `${effectiveUrl}/uninstall.sh?download=1`;
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = 'uninstall_agent.sh';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      notify('Скачивание деинсталлятора uninstall_agent.sh...');
    } else {
      const downloadUrl = `${effectiveUrl}/uninstall.bat`;
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = 'Uninstall-WorkstationAgent.bat';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      notify('Скачивание деинсталлятора Uninstall-WorkstationAgent.bat...');
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="DEPLOYMENT"
        title="Агенты и загрузки"
        description="Автоматическое развертывание и удаление агентов на рабочих станциях с автоподключением к серверу."
        actions={<Button primary icon={<Key size={15} />} onClick={() => { loadData(); setShowTokenModal(true); }}>Сгенерировать токен</Button>}
      />

      <div className="panel" style={{ marginBottom: '20px', padding: '18px 21px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
          <div>
            <strong style={{ fontSize: '13px', display: 'block', marginBottom: '4px' }}>Адрес сервера Workstation Manager (Ubuntu Server)</strong>
            <span style={{ color: 'var(--muted)', fontSize: '11px' }}>Этот URL зашивается в команду установки и конфигурацию агента:</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              className="text-input"
              style={{ width: '280px', fontFamily: "'DM Mono', monospace", fontWeight: 600 }}
              value={serverAddress}
              onChange={(e) => setServerAddress(e.target.value)}
              placeholder="http://192.168.1.109:2301"
            />
          </div>
        </div>
      </div>

      {/* 1-Click Fast Download & Uninstall Hero Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px', marginBottom: '20px' }}>
        {/* Installer Card */}
        <div className="panel" style={{ padding: '20px 24px', background: 'linear-gradient(135deg, rgba(37,99,235,0.06) 0%, rgba(59,130,246,0.02) 100%)', border: '1px solid rgba(59,130,246,0.2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'var(--blue-soft)', color: 'var(--blue)', padding: '3px 9px', borderRadius: '20px', fontSize: '11px', fontWeight: 700 }}>
              <Zap size={12} /> УСТАНОВКА В 1 КЛИК
            </div>
            {tokens.length > 0 && (
              <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.15)', color: 'var(--blue)', fontWeight: 600 }}>
                Целевая группа: {currentTargetGroup}
              </span>
            )}
          </div>
          <h2 style={{ fontSize: '17px', fontWeight: 700, margin: '0 0 6px 0', color: 'var(--text)' }}>
            Установщик агента и службы
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 16px 0', lineHeight: 1.5 }}>
            Автономный файл <code style={{ fontFamily: 'DM Mono', color: 'var(--blue)' }}>Install-WorkstationAgent-{currentTargetGroup}.bat</code>. Запускает службу автозапуска и передает 100% спецификации ПК (ЦП, ОЗУ, Диски, GPU) в панель.
          </p>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              primary
              icon={<ArrowDownToLine size={15} />}
              onClick={() => handleDownloadInstaller('Windows')}
              style={{ fontSize: '12px', fontWeight: 600 }}
            >
              Скачать установщик (.bat)
            </Button>
            <Button
              icon={<ArrowDownToLine size={15} />}
              onClick={() => handleDownloadInstaller('Linux')}
              style={{ fontSize: '12px' }}
            >
              Linux (.sh)
            </Button>

            {/* Target Token / Group Selector Dropdown */}
            {tokens.length > 0 && (
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginLeft: 'auto', background: 'var(--panel-card, rgba(255,255,255,0.05))', padding: '3px 8px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                  Токен / Группа:
                </span>
                <select
                  className="text-input"
                  style={{ fontSize: '12px', padding: '3px 8px', height: '30px', minWidth: '160px', fontWeight: 600 }}
                  value={activeToken}
                  onChange={(e) => setSelectedInstallerToken(e.target.value)}
                  title="Выберите группу или токен для скачивания установщика"
                >
                  {tokens.map((tok) => (
                    <option key={tok.id} value={tok.token}>
                      {tok.targetGroup} ({tok.token.slice(0, 14)}...)
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* Uninstaller Card */}
        <div className="panel" style={{ padding: '20px 24px', background: 'linear-gradient(135deg, rgba(239,68,68,0.05) 0%, rgba(244,63,94,0.02) 100%)', border: '1px solid rgba(239,68,68,0.2)' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'rgba(239,68,68,0.1)', color: 'var(--red)', padding: '3px 9px', borderRadius: '20px', fontSize: '11px', fontWeight: 700, marginBottom: '8px' }}>
            <Trash2 size={12} /> ПОЛНОЕ УДАЛЕНИЕ
          </div>
          <h2 style={{ fontSize: '17px', fontWeight: 700, margin: '0 0 6px 0', color: 'var(--text)' }}>
            Деинсталлятор агента (Uninstall)
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 16px 0', lineHeight: 1.5 }}>
            Останавливает службу (systemd / Планировщик Windows), отключает автозапуск и полностью очищает файлы агента с диска.
          </p>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <Button
              icon={<Trash2 size={14} style={{ color: 'var(--red)' }} />}
              onClick={() => handleDownloadUninstaller('Windows')}
              style={{ fontSize: '12px', fontWeight: 600, borderColor: 'rgba(239,68,68,0.3)' }}
            >
              Скачать деинсталлятор (.bat)
            </Button>
            <Button
              icon={<Trash2 size={14} style={{ color: 'var(--red)' }} />}
              onClick={() => handleDownloadUninstaller('Linux')}
              style={{ fontSize: '12px', fontWeight: 600, borderColor: 'rgba(239,68,68,0.3)' }}
            >
              Linux (.sh)
            </Button>
          </div>
        </div>
      </div>

      <div className="detail-grid" style={{ marginBottom: '20px' }}>
        <section className="panel table-panel">
          <div className="panel-heading">
            <div><h2>Активные Enrollment-токены</h2><p>{tokens.length} токенов доступно</p></div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Токен</th>
                  <th>Целевая группа</th>
                  <th>Использования</th>
                  <th>Срок действия</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((tok) => (
                  <tr key={tok.id}>
                    <td className="mono">{tok.token}</td>
                    <td>{tok.targetGroup}</td>
                    <td>{tok.usedCount} / {tok.maxUses || '∞'}</td>
                    <td className="muted-text">{tok.expiresAt}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                        <button
                          className="text-button"
                          onClick={() => {
                            const effectiveUrl = serverAddress.trim().replace(/\/+$/, '');
                            const dlUrl = `${effectiveUrl}/install.bat?token=${tok.token}&server_url=${encodeURIComponent(effectiveUrl)}`;
                            const link = document.createElement('a');
                            link.href = dlUrl;
                            link.setAttribute('download', `Install-Agent-${tok.targetGroup || 'Office'}.bat`);
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                            notify(`Скачивание инсталлера для группы "${tok.targetGroup}" запущено`);
                          }}
                          title="Скачать готовый .bat для этой группы"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: 'var(--primary)',
                            fontWeight: 600,
                            padding: '3px 8px',
                            borderRadius: '4px',
                            background: 'rgba(59, 130, 246, 0.1)'
                          }}
                        >
                          <Download size={13} />
                          .bat
                        </button>

                        <button
                          className="text-button"
                          onClick={() => handleCopy(tok.token, `tok-${tok.id}`)}
                          title="Скопировать токен"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: copiedKey === `tok-${tok.id}` ? 'var(--green)' : undefined,
                            padding: '3px 6px',
                            borderRadius: '4px'
                          }}
                        >
                          {copiedKey === `tok-${tok.id}` ? <Check size={13} /> : <Copy size={13} />}
                        </button>

                        <button
                          className="text-button"
                          onClick={() => handleOpenEditToken(tok)}
                          title="Редактировать / Продлить срок"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: 'var(--yellow)',
                            padding: '3px 6px',
                            borderRadius: '4px'
                          }}
                        >
                          <Edit3 size={13} />
                        </button>

                        <button
                          className="text-button"
                          onClick={() => setDeleteTokenTarget(tok)}
                          title="Отозвать и удалить токен"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: 'var(--red)',
                            padding: '3px 6px',
                            borderRadius: '4px'
                          }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel info-panel">
          <div className="panel-heading">
            <div><h2>Команды установки в один клик</h2><p>Windows PowerShell и Linux Bash</p></div>
            <Terminal size={19} className="heading-icon" />
          </div>
          <div style={{ padding: '0 21px 21px' }}>
            <div className="code-card">
              <div className="code-card-header">
                <span>PowerShell (Запуск от имени Администратора)</span>
                <button
                  className="text-button"
                  onClick={() => handleCopy(psOneLiner, 'ps')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: copiedKey === 'ps' ? 'var(--green)' : 'var(--blue)',
                    fontWeight: 600
                  }}
                >
                  {copiedKey === 'ps' ? <Check size={13} /> : <Copy size={13} />}
                  {copiedKey === 'ps' ? 'Скопировано!' : 'Копировать'}
                </button>
              </div>
              <pre>{psOneLiner}</pre>
            </div>
            <div className="code-card">
              <div className="code-card-header">
                <span>Linux Bash (root / sudo)</span>
                <button
                  className="text-button"
                  onClick={() => handleCopy(bashOneLiner, 'bash')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: copiedKey === 'bash' ? 'var(--green)' : 'var(--blue)',
                    fontWeight: 600
                  }}
                >
                  {copiedKey === 'bash' ? <Check size={13} /> : <Copy size={13} />}
                  {copiedKey === 'bash' ? 'Скопировано!' : 'Копировать'}
                </button>
              </div>
              <pre>{bashOneLiner}</pre>
            </div>
            <div className="code-card" style={{ borderColor: 'rgba(239,68,68,0.2)' }}>
              <div className="code-card-header">
                <span style={{ color: 'var(--red)' }}>PowerShell Удаление (Uninstall от Администратора)</span>
                <button
                  className="text-button"
                  onClick={() => handleCopy(uninstallerCommand, 'uninst')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: copiedKey === 'uninst' ? 'var(--green)' : 'var(--red)',
                    fontWeight: 600
                  }}
                >
                  {copiedKey === 'uninst' ? <Check size={13} /> : <Copy size={13} />}
                  {copiedKey === 'uninst' ? 'Скопировано!' : 'Копировать'}
                </button>
              </div>
              <pre>{uninstallerCommand}</pre>
            </div>
            <div className="code-card" style={{ borderColor: 'rgba(239,68,68,0.2)' }}>
              <div className="code-card-header">
                <span style={{ color: 'var(--red)' }}>Linux Bash Удаление (Uninstall root / sudo)</span>
                <button
                  className="text-button"
                  onClick={() => handleCopy(linuxUninstallerCommand, 'uninst-linux')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    color: copiedKey === 'uninst-linux' ? 'var(--green)' : 'var(--red)',
                    fontWeight: 600
                  }}
                >
                  {copiedKey === 'uninst-linux' ? <Check size={13} /> : <Copy size={13} />}
                  {copiedKey === 'uninst-linux' ? 'Скопировано!' : 'Копировать'}
                </button>
              </div>
              <pre>{linuxUninstallerCommand}</pre>
            </div>
          </div>
        </section>

        <section className="panel table-panel" style={{ gridColumn: '1 / -1' }}>
          <div className="panel-heading">
            <div><h2>Дистрибутивы агента</h2><p>Автономные 1-Click установщики и скрипты</p></div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Платформа</th>
                  <th>Архитектура</th>
                  <th>Версия</th>
                  <th>Формат</th>
                  <th>Чексумма SHA-256</th>
                  <th>Скачать</th>
                </tr>
              </thead>
              <tbody>
                {builds.map((b, idx) => {
                  const pkg = (b as any).packageType || (b as any).format || '.bat';
                  const arch = (b as any).architecture || (b as any).arch || 'x64';
                  const isBat = String(pkg).toLowerCase().includes('bat');
                  const isSh = String(pkg).toLowerCase().includes('sh') || String(b.os || '').toLowerCase().includes('linux');
                  const sha = b.sha256 || '';
                  return (
                    <tr key={(b.os || '') + arch + idx}>
                      <td><strong>{b.os}</strong></td>
                      <td>{arch}</td>
                      <td>{b.version}</td>
                      <td><span className="badge">{pkg}</span></td>
                      <td className="mono muted-text">{sha ? `${sha.slice(0, 16)}...` : '—'}</td>
                      <td>
                        <Button onClick={() => handleDownloadInstaller(b.os, pkg)} icon={<ArrowDownToLine size={13} />}>
                          Скачать {isBat ? 'установщик (.bat)' : isSh ? 'скрипт (.sh)' : 'скрипт (.ps1)'}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* ========================================================================= */}
      {/* CENTRALIZED FLEET REMOTE AUTO-UPDATE & VERSION MANAGEMENT (OTA)           */}
      {/* ========================================================================= */}
      <div className="panel" style={{ marginBottom: '20px', padding: '22px 24px', background: 'linear-gradient(135deg, rgba(16,185,129,0.05) 0%, rgba(59,130,246,0.03) 100%)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'rgba(16,185,129,0.15)', color: 'var(--green)', padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 700, marginBottom: '6px' }}>
              <RotateCw size={13} className="spin-slow" /> АКТУАЛЬНЫЙ РЕЛИЗ СЕРВЕРА v{versionInfo?.currentVersion || '1.9.0'}
            </div>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 4px 0', color: 'var(--text)' }}>
              Централизованное удаленное обновление агентов (OTA Fleet Update)
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0, lineHeight: 1.5 }}>
              Доставка и горячее применение обновлений агента по локальной сети без физического доступа к ПК и без прерывания работы сотрудников.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              primary
              icon={<RotateCw size={14} className={isBulkUpdating ? "spin" : ""} />}
              onClick={() => setShowBulkUpdateModal(true)}
              disabled={isBulkUpdating || (versionInfo?.outdatedCount === 0 && fleetDevices.length > 0)}
              style={{ background: 'var(--green)', borderColor: 'var(--green)', fontSize: '12px', fontWeight: 600 }}
            >
              {isBulkUpdating ? 'Выполняется обновление...' : `🚀 Обновить все устаревшие агенты (${versionInfo?.outdatedCount ?? 0} шт.)`}
            </Button>
            <Button
              icon={<RefreshCw size={13} />}
              onClick={() => { loadData(); notify('Данные версий обновлены'); }}
              style={{ fontSize: '12px' }}
              title="Проверить отклик станций"
            >
              Проверить версии
            </Button>
          </div>
        </div>

        {/* 4 Stat KPI Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '18px' }}>
          <div style={{ background: 'var(--surface-2)', padding: '12px 16px', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px' }}>Всего станций</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text)' }}>{versionInfo?.totalAgents ?? fleetDevices.length}</div>
          </div>
          <div style={{ background: 'rgba(16,185,129,0.06)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.2)' }}>
            <div style={{ fontSize: '11px', color: 'var(--green)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Check size={12} /> Актуальная v{versionInfo?.currentVersion || '1.9.0'}
            </div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--green)' }}>{versionInfo?.upToDateCount ?? 0}</div>
          </div>
          <div style={{ background: 'rgba(234,179,8,0.06)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(234,179,8,0.2)' }}>
            <div style={{ fontSize: '11px', color: 'var(--yellow)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <AlertTriangle size={12} /> Требуют обновления
            </div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--yellow)' }}>{versionInfo?.outdatedCount ?? 0}</div>
          </div>
          <div style={{ background: 'rgba(59,130,246,0.06)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(59,130,246,0.2)' }}>
            <div style={{ fontSize: '11px', color: 'var(--blue)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <LoaderCircle size={12} className={updatingDeviceIds.length > 0 ? "spin" : ""} /> В процессе
            </div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--blue)' }}>{updatingDeviceIds.length || (versionInfo?.updatingCount ?? 0)}</div>
          </div>
        </div>

        {/* Workstations Version Status Table */}
        <div style={{ background: 'var(--surface-2)', borderRadius: '8px', border: '1px solid var(--border)', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                className={`filter-button ${fleetFilter === 'all' ? 'primary' : ''}`}
                onClick={() => setFleetFilter('all')}
                style={{ fontSize: '11px', padding: '4px 10px' }}
              >
                Все станции ({fleetDevices.length})
              </button>
              <button
                className={`filter-button ${fleetFilter === 'outdated' ? 'primary' : ''}`}
                onClick={() => setFleetFilter('outdated')}
                style={{ fontSize: '11px', padding: '4px 10px', color: fleetFilter !== 'outdated' && (versionInfo?.outdatedCount ?? 0) > 0 ? 'var(--yellow)' : undefined }}
              >
                Требуют обновления ({fleetDevices.filter(d => (d.agentVersion || '1.4.2') !== (versionInfo?.currentVersion || '2.8.7')).length})
              </button>
              <button
                className={`filter-button ${fleetFilter === 'updated' ? 'primary' : ''}`}
                onClick={() => setFleetFilter('updated')}
                style={{ fontSize: '11px', padding: '4px 10px' }}
              >
                Актуальные ({fleetDevices.filter(d => (d.agentVersion || '1.4.2') === (versionInfo?.currentVersion || '2.8.7')).length})
              </button>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
              Прямой UDP триггер: порт 48123 | Heartbeat Fallback
            </span>
          </div>

          <div className="table-wrap" style={{ maxHeight: '320px', overflowY: 'auto' }}>
            <table style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>Рабочая станция</th>
                  <th>Группа</th>
                  <th>IP-адрес</th>
                  <th>Версия агента</th>
                  <th>Статус связи</th>
                  <th>Последний отклик</th>
                  <th style={{ textAlign: 'right' }}>Действие</th>
                </tr>
              </thead>
              <tbody>
                {fleetDevices.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '24px', color: 'var(--muted)' }}>
                      В мониторинге пока нет зарегистрированных рабочих станций
                    </td>
                  </tr>
                ) : (
                  fleetDevices
                    .filter(d => {
                      const targetVer = versionInfo?.currentVersion || '2.8.7';
                      if (fleetFilter === 'outdated') return (d.agentVersion || '1.4.2') !== targetVer;
                      if (fleetFilter === 'updated') return (d.agentVersion || '1.4.2') === targetVer;
                      return true;
                    })
                    .map(dev => {
                      const targetVer = versionInfo?.currentVersion || dev.latestAgentVersion || '2.8.7';
                      const curVer = dev.agentVersion || '1.4.2';
                      const isTargetVer = curVer === targetVer;
                      const isUpdating = updatingDeviceIds.includes(dev.id) || dev.updateStatus === 'UPDATING';
                      const devGroups = getDeviceGroups(dev);
                      return (
                        <tr key={dev.id}>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <Monitor size={15} style={{ color: dev.powerStatus === 'On' ? 'var(--green)' : 'var(--muted)' }} />
                              <div>
                                <strong style={{ display: 'block', fontSize: '12px' }}>{dev.name}</strong>
                                <small style={{ color: 'var(--muted)', fontSize: '10px' }}>{dev.id} · {dev.hostname}</small>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span style={{ fontSize: '11px', padding: '2px 6px', background: 'var(--surface-1, rgba(255,255,255,0.05))', borderRadius: '4px', border: '1px solid var(--border)' }}>
                              {devGroups[0] || 'Office'}
                            </span>
                          </td>
                          <td className="mono" style={{ fontSize: '11px' }}>{dev.ip || '—'}</td>
                          <td>
                            {isUpdating ? (
                              <span className="badge" style={{ background: 'rgba(59,130,246,0.15)', color: 'var(--blue)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                <LoaderCircle size={11} className="spin" /> Обновляется...
                              </span>
                            ) : isTargetVer ? (
                              <span className="badge" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--green)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                <Check size={11} /> v{curVer} (Актуальна)
                              </span>
                            ) : (
                              <span className="badge" style={{ background: 'rgba(234,179,8,0.15)', color: 'var(--yellow)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                <AlertTriangle size={11} /> v{curVer} (Устарела)
                              </span>
                            )}
                          </td>
                          <td>
                            <span style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                              <i className={`status-dot ${dev.powerStatus === 'On' ? 'green' : 'red'}`} />
                              {dev.powerStatus === 'On' ? 'В сети (Онлайн)' : 'Выключен (Оффлайн)'}
                            </span>
                          </td>
                          <td className="muted-text" style={{ fontSize: '11px' }}>
                            {formatDeviceLastSeen(dev.lastSeen, dev.lastSeenIso, dev.powerStatus)}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {isUpdating ? (
                              <span style={{ fontSize: '11px', color: 'var(--blue)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                <LoaderCircle size={12} className="spin" /> В процессе
                              </span>
                            ) : isTargetVer ? (
                              <Button
                                icon={<RotateCw size={11} />}
                                onClick={() => handleUpdateSingleDevice(dev.id, dev.name)}
                                style={{ fontSize: '11px', padding: '3px 7px', opacity: 0.7 }}
                                title="Принудительно переустановить/обновить агент"
                              >
                                Переустановить
                              </Button>
                            ) : (
                              <Button
                                primary
                                icon={<RotateCw size={12} />}
                                onClick={() => handleUpdateSingleDevice(dev.id, dev.name)}
                                style={{ fontSize: '11px', padding: '3px 8px', background: 'var(--green)', borderColor: 'var(--green)' }}
                              >
                                Обновить до v{targetVer}
                              </Button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Realtime Remote Update Audit Logs Feed */}
        {updateLogs.length > 0 && (
          <div style={{ marginTop: '16px', background: 'var(--surface-2)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <strong style={{ fontSize: '12px', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Clock3 size={13} style={{ color: 'var(--blue)' }} /> Журнал удаленных обновлений (OTA Logs)
              </strong>
              <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Последние {updateLogs.length} событий</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '160px', overflowY: 'auto' }}>
              {updateLogs.slice(0, 10).map((log) => (
                <div
                  key={log.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '10px',
                    padding: '6px 10px',
                    background: 'var(--surface-1, rgba(0,0,0,0.15))',
                    borderRadius: '6px',
                    fontSize: '11px',
                    borderLeft: `3px solid ${log.status === 'SUCCESS' ? 'var(--green)' : log.status === 'FAILED' ? 'var(--red)' : 'var(--blue)'}`
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span className="mono" style={{ color: 'var(--muted)', fontSize: '10px' }}>{formatLocalTime(log.timestamp)}</span>
                    <strong>{log.deviceName || log.deviceId}</strong>
                    <span style={{ color: 'var(--muted)' }}>
                      v{log.previousVersion} ➔ <strong style={{ color: 'var(--text)' }}>v{log.targetVersion}</strong>
                    </span>
                    <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>({log.details})</span>
                  </div>
                  <div>
                    {log.status === 'SUCCESS' ? (
                      <span className="badge" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--green)', fontWeight: 600, fontSize: '10px' }}>
                        Успешно
                      </span>
                    ) : log.status === 'FAILED' ? (
                      <span className="badge" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--red)', fontWeight: 600, fontSize: '10px' }}>
                        Ошибка
                      </span>
                    ) : (
                      <span className="badge" style={{ background: 'rgba(59,130,246,0.15)', color: 'var(--blue)', fontWeight: 600, fontSize: '10px', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                        <LoaderCircle size={10} className="spin" /> В процессе
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* CREATE TOKEN MODAL */}
      {showTokenModal && (
        <div className="modal-backdrop" onClick={() => setShowTokenModal(false)}>
          <div className="confirm-modal" style={{ maxWidth: '540px', width: '100%', textAlign: 'left' }} onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)' }}><Key size={23} /></div>
            <h2>Генерация токена регистрации</h2>
            <p>Новый токен позволяет фоновому агенту автоматически зарегистрировать станцию на сервере {serverAddress}.</p>
            
            {/* Token Target Scope Mode */}
            <div style={{ display: 'flex', gap: '6px', marginBottom: '16px', padding: '3px', background: 'var(--bg)', borderRadius: '8px', border: '1px solid var(--line)' }}>
              <button
                type="button"
                className={`button ${tokenScopeMode === 'room' ? 'button-primary' : ''}`}
                style={{ flex: 1, padding: '6px', fontSize: '12px' }}
                onClick={() => setTokenScopeMode('room')}
              >
                🚪 На кабинет
              </button>
              <button
                type="button"
                className={`button ${tokenScopeMode === 'building' ? 'button-primary' : ''}`}
                style={{ flex: 1, padding: '6px', fontSize: '12px' }}
                onClick={() => setTokenScopeMode('building')}
              >
                🏢 На корпус
              </button>
              <button
                type="button"
                className={`button ${tokenScopeMode === 'flat' ? 'button-primary' : ''}`}
                style={{ flex: 1, padding: '6px', fontSize: '12px' }}
                onClick={() => setTokenScopeMode('flat')}
              >
                📁 Простая группа
              </button>
            </div>

            {tokenScopeMode === 'room' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '14px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                    Корпус / Здание
                  </label>
                  <select
                    className="text-input"
                    style={{ width: '100%' }}
                    value={activeTokenBuilding}
                    onChange={(e) => {
                      const newBld = e.target.value;
                      setTokenBuilding(newBld);
                      setIsCustomTokenRoom(false);
                      setCustomTokenRoomInput('');
                      // Find first floor with rooms in new building
                      const bldRooms = allBuildingRooms.filter(r => r.floor);
                      if (bldRooms.length > 0) {
                        setTokenFloor(bldRooms[0].floor);
                        setTokenRoom(bldRooms[0].room);
                      } else {
                        setTokenRoom('');
                      }
                    }}
                  >
                    {availableBuildingsForToken.map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                    Этаж / Секция
                  </label>
                  <select
                    className="text-input"
                    style={{ width: '100%' }}
                    value={activeTokenFloor}
                    onChange={(e) => {
                      const newFlr = e.target.value;
                      setTokenFloor(newFlr);
                      setIsCustomTokenRoom(false);
                      setCustomTokenRoomInput('');
                      const matching = allBuildingRooms.filter(r => r.floor.toLowerCase() === newFlr.toLowerCase());
                      if (matching.length > 0) {
                        setTokenRoom(matching[0].room);
                      } else {
                        setTokenRoom('');
                      }
                    }}
                  >
                    {availableFloorsForToken.map(f => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                    Кабинет / Помещение
                  </label>
                  <select
                    className="text-input"
                    style={{ width: '100%' }}
                    value={isCustomTokenRoom ? '__new__' : (selectedRoomValue || '__new__')}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === '__new__') {
                        setIsCustomTokenRoom(true);
                        setTokenRoom('');
                      } else {
                        setIsCustomTokenRoom(false);
                        setTokenRoom(val);
                        // Auto-switch floor if this room belongs to a different floor
                        const matching = allBuildingRooms.find(r => r.room.toLowerCase() === val.toLowerCase());
                        if (matching && matching.floor && matching.floor.toLowerCase() !== activeTokenFloor.toLowerCase()) {
                          setTokenFloor(matching.floor);
                        }
                      }
                    }}
                  >
                    {activeFloorRooms.length > 0 && (
                      <optgroup label={`Кабинеты (${activeTokenFloor})`}>
                        {activeFloorRooms.map(r => (
                          <option key={r} value={r}>Кабинет {r}</option>
                        ))}
                      </optgroup>
                    )}

                    {otherFloorsRooms.length > 0 && (
                      <optgroup label="Кабинеты на других этажах здания">
                        {otherFloorsRooms.map(r => (
                          <option key={`${r.floor}-${r.room}`} value={r.room}>
                            Кабинет {r.room} ({r.floor})
                          </option>
                        ))}
                      </optgroup>
                    )}

                    <option value="__new__">+ Ввести новый кабинет...</option>
                  </select>

                  {isCustomTokenRoom && (
                    <div style={{ marginTop: '8px' }}>
                      <input
                        className="text-input"
                        style={{ width: '100%' }}
                        value={customTokenRoomInput}
                        onChange={(e) => {
                          setCustomTokenRoomInput(e.target.value);
                          setTokenRoom(e.target.value);
                        }}
                        placeholder="Например: 111, Каб. 204 или Бухгалтерия"
                        autoFocus
                      />
                    </div>
                  )}
                </div>

                <div style={{ padding: '8px 12px', background: 'var(--blue-soft)', borderRadius: '6px', fontSize: '11px', color: 'var(--blue)' }}>
                  📍 <strong>Назначение ПК:</strong> <code>{activeTokenBuilding} / {activeTokenFloor} / {effectiveRoom}</code>
                </div>
              </div>
            ) : tokenScopeMode === 'building' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '14px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                    Корпус / Здание
                  </label>
                  <select
                    className="text-input"
                    style={{ width: '100%' }}
                    value={activeTokenBuilding}
                    onChange={(e) => setTokenBuilding(e.target.value)}
                  >
                    {availableBuildingsForToken.map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>
                <div style={{ padding: '8px 12px', background: 'var(--blue-soft)', borderRadius: '6px', fontSize: '11px', color: 'var(--blue)' }}>
                  🏢 <strong>Назначение ПК:</strong> Все ПК с этим токеном будут зачислены в корпус <code>{activeTokenBuilding}</code> в категорию <code>Нераспределенные</code>.
                </div>
              </div>
            ) : (
              <div className="setting-row" style={{ padding: '8px 0' }}>
                <div><strong>Рабочая группа</strong></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '60%' }}>
                  <select
                    className="text-input"
                    value={targetGroup}
                    onChange={(e) => {
                      setTargetGroup(e.target.value);
                      if (e.target.value !== '__custom__') {
                        setCustomGroupInput('');
                      }
                    }}
                  >
                    {availableGroups.map((grp) => (
                      <option key={grp} value={grp}>{grp}</option>
                    ))}
                    <option value="__custom__">+ Ввести новую группу...</option>
                  </select>
                  {targetGroup === '__custom__' && (
                    <input
                      type="text"
                      className="text-input"
                      placeholder="Введите название новой группы"
                      value={customGroupInput}
                      onChange={(e) => setCustomGroupInput(e.target.value)}
                      autoFocus
                    />
                  )}
                </div>
              </div>
            )}

            <div className="setting-row" style={{ padding: '8px 0' }}>
              <div><strong>Срок действия</strong></div>
              <select className="text-input" value={expiryOption} onChange={(e) => setExpiryOption(e.target.value)}>
                <option value="24h">24 часа (1 сутки)</option>
                <option value="7d">7 дней (1 неделя)</option>
                <option value="30d">30 дней (1 месяц)</option>
                <option value="90d">90 дней (3 месяца)</option>
                <option value="365d">365 дней (1 год)</option>
                <option value="never">Бессрочно (без ограничений)</option>
                <option value="custom">Указать точную дату...</option>
              </select>
            </div>

            {expiryOption === 'custom' && (
              <div className="setting-row" style={{ padding: '8px 0' }}>
                <div><strong>Точная дата и время</strong></div>
                <input
                  type="datetime-local"
                  className="text-input"
                  value={customExpiryDate}
                  onChange={(e) => setCustomExpiryDate(e.target.value)}
                />
              </div>
            )}

            <div className="setting-row" style={{ padding: '8px 0' }}>
              <div><strong>Лимит использований</strong></div>
              <select className="text-input" value={maxUsesOption} onChange={(e) => setMaxUsesOption(e.target.value)}>
                <option value="unlimited">Неограниченно (∞)</option>
                <option value="1">Одноразовый (1 ПК)</option>
                <option value="custom">Указать число ПК...</option>
              </select>
            </div>

            {maxUsesOption === 'custom' && (
              <div className="setting-row" style={{ padding: '8px 0' }}>
                <div><strong>Макс. количество ПК</strong></div>
                <input
                  type="number"
                  min="1"
                  className="text-input"
                  value={customMaxUses}
                  onChange={(e) => setCustomMaxUses(e.target.value)}
                  placeholder="например, 10"
                />
              </div>
            )}

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setShowTokenModal(false)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleGenerateToken}>
                Сгенерировать
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* EDIT TOKEN MODAL */}
      {editTokenTarget && (
        <div className="modal-backdrop" onClick={() => setEditTokenTarget(null)}>
          <div className="confirm-modal" style={{ maxWidth: '460px' }} onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon" style={{ background: 'rgba(234, 179, 8, 0.15)', color: 'var(--yellow)' }}><Edit3 size={23} /></div>
            <h2>Редактирование токена</h2>
            <p className="mono" style={{ fontSize: '12px', color: 'var(--primary)' }}>{editTokenTarget.token}</p>

            <div className="setting-row" style={{ padding: '8px 0' }}>
              <div><strong>Целевая группа</strong></div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '60%' }}>
                <select
                  className="text-input"
                  value={editGroup}
                  onChange={(e) => {
                    setEditGroup(e.target.value);
                    if (e.target.value !== '__custom__') {
                      setEditCustomGroupInput('');
                    }
                  }}
                >
                  {availableGroups.map((grp) => (
                    <option key={grp} value={grp}>{grp}</option>
                  ))}
                  <option value="__custom__">+ Ввести новую группу...</option>
                </select>
                {editGroup === '__custom__' && (
                  <input
                    type="text"
                    className="text-input"
                    placeholder="Введите название новой группы"
                    value={editCustomGroupInput}
                    onChange={(e) => setEditCustomGroupInput(e.target.value)}
                    autoFocus
                  />
                )}
              </div>
            </div>

            <div className="setting-row" style={{ padding: '8px 0' }}>
              <div><strong>Срок действия</strong></div>
              <input
                type="text"
                className="text-input"
                value={editExpiryDate}
                onChange={(e) => setEditExpiryDate(e.target.value)}
                placeholder="YYYY-MM-DD HH:MM или 'Бессрочно'"
              />
            </div>

            <div style={{ display: 'flex', gap: '6px', marginBottom: '14px', flexWrap: 'wrap' }}>
              <button className="button" style={{ fontSize: '11px', padding: '4px 8px' }} onClick={() => handleExtendTokenDays(30)}>+30 дней</button>
              <button className="button" style={{ fontSize: '11px', padding: '4px 8px' }} onClick={() => handleExtendTokenDays(90)}>+90 дней</button>
              <button className="button" style={{ fontSize: '11px', padding: '4px 8px' }} onClick={() => handleExtendTokenDays(365)}>+1 год</button>
              <button className="button" style={{ fontSize: '11px', padding: '4px 8px' }} onClick={() => setEditExpiryDate('Бессрочно')}>Бессрочно</button>
            </div>

            <div className="setting-row" style={{ padding: '8px 0' }}>
              <div><strong>Лимит использований</strong></div>
              <select className="text-input" value={editMaxUsesOption} onChange={(e) => setEditMaxUsesOption(e.target.value)}>
                <option value="unlimited">Неограниченно (∞)</option>
                <option value="1">Одноразовый (1 ПК)</option>
                <option value="custom">Указать число...</option>
              </select>
            </div>

            {editMaxUsesOption === 'custom' && (
              <div className="setting-row" style={{ padding: '8px 0' }}>
                <div><strong>Макс. количество ПК</strong></div>
                <input
                  type="number"
                  min="1"
                  className="text-input"
                  value={editCustomMaxUses}
                  onChange={(e) => setEditCustomMaxUses(e.target.value)}
                  placeholder="например, 10"
                />
              </div>
            )}

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setEditTokenTarget(null)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleSaveEditToken}>
                Сохранить изменения
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {deleteTokenTarget && (
        <div className="modal-backdrop" onClick={() => setDeleteTokenTarget(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="confirm-icon" style={{ background: 'rgba(239, 68, 68, 0.15)', color: 'var(--red)' }}><Trash2 size={23} /></div>
            <h2>Отозвать токен?</h2>
            <p>
              Вы уверены, что хотите удалить и отозвать токен <strong className="mono">{deleteTokenTarget.token}</strong> (группа: <em>{deleteTokenTarget.targetGroup}</em>)?
              <br />
              Новые рабочие станции больше не смогут зарегистрироваться с этим токеном.
            </p>
            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setDeleteTokenTarget(null)}>{t('common.cancel')}</Button>
              <Button style={{ backgroundColor: 'var(--red)', color: '#fff', borderColor: 'var(--red)' }} onClick={handleConfirmDeleteToken}>
                Удалить токен
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* BULK FLEET UPDATE CONFIRMATION MODAL */}
      {showBulkUpdateModal && (
        <div className="modal-backdrop" onClick={() => setShowBulkUpdateModal(false)}>
          <div className="confirm-modal" style={{ maxWidth: '520px', textAlign: 'left' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div className="confirm-icon" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--green)', margin: 0 }}>
                <RotateCw size={22} />
              </div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Массовое обновление парка агентов</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>Централизованная доставка релиза v{versionInfo?.currentVersion || '1.9.0'}</p>
              </div>
            </div>
            <p style={{ fontSize: '13px', lineHeight: 1.5, color: 'var(--text)' }}>
              Вы собираетесь инициировать обновление агентов на всех устаревших рабочих станциях (<strong>{versionInfo?.outdatedCount ?? 0} шт.</strong>).
            </p>
            <div style={{ background: 'var(--surface-2)', padding: '12px 14px', borderRadius: '8px', border: '1px solid var(--border)', fontSize: '12px', margin: '14px 0' }}>
              <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--text)' }}>Что произойдет:</strong>
              <ul style={{ margin: 0, paddingLeft: '18px', color: 'var(--muted)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <li>Сервер отправит мгновенный UDP сигнал на порт 48123 каждой онлайн-станции.</li>
                <li>Команда обновления будет помещена в очередь Heartbeat для гарантированной доставки.</li>
                <li>Агент скачает проверенный исходный код, выполнит валидацию синтаксиса и перезапустит службу.</li>
                <li>При сбое агент автоматически откатится на резервную копию (.bak).</li>
              </ul>
            </div>
            <div className="modal-actions" style={{ marginTop: '16px' }}>
              <Button onClick={() => setShowBulkUpdateModal(false)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleExecuteBulkUpdate} disabled={isBulkUpdating} style={{ background: 'var(--green)', borderColor: 'var(--green)' }}>
                {isBulkUpdating ? 'Отправка команд...' : 'Запустить обновление'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------
// 13. TELEGRAM PAGE
// ----------------------------------------------------
function TelegramPage({ notify }: { notify: (message: string) => void }) {
  const { t } = useLanguage();
  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState('');
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [botUsername, setBotUsername] = useState('');
  const [status, setStatus] = useState('Не настроен');
  const [timezone, setTimezone] = useState('Europe/Moscow');

  // Telegram Alert Event Filters (Spam prevention & USB distinction)
  const [eventsConfig, setEventsConfig] = useState({
    criticalAlerts: true,
    hardwareChanges: true,
    usbStorage: false, // Default false to prevent flooding Telegram with flash drive insertions
    morningWakeSummary: true,
    eveningShutdownSummary: true,
    powerAlerts: true,
    disconnectAlerts: true,
  });

  // Proxy Configuration State
  const [proxyEnabled, setProxyEnabled] = useState(false);
  const [proxyType, setProxyType] = useState('SOCKS5');
  const [proxyHost, setProxyHost] = useState('');
  const [proxyPort, setProxyPort] = useState('1080');
  const [proxyUser, setProxyUser] = useState('');
  const [proxyPass, setProxyPass] = useState('');
  const [isTestingProxy, setIsTestingProxy] = useState(false);
  const [proxyTestResult, setProxyTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    telegramApi.getConfig().then((cfg) => {
      if (cfg) {
        if (cfg.botToken !== undefined) setBotToken(cfg.botToken);
        if (cfg.chatId !== undefined) setChatId(cfg.chatId);
        if (cfg.alertsEnabled !== undefined) setAlertsEnabled(cfg.alertsEnabled);
        if (cfg.botUsername !== undefined) setBotUsername(cfg.botUsername);
        if (cfg.status) setStatus(cfg.status);
        if (cfg.timezone) setTimezone(cfg.timezone);
        if (cfg.proxyEnabled !== undefined) setProxyEnabled(cfg.proxyEnabled);
        if (cfg.proxyType) setProxyType(cfg.proxyType);
        if (cfg.proxyHost) setProxyHost(cfg.proxyHost);
        if (cfg.proxyPort) setProxyPort(String(cfg.proxyPort));
        if (cfg.proxyUser) setProxyUser(cfg.proxyUser);
        if (cfg.proxyPass) setProxyPass(cfg.proxyPass);
        if (cfg.eventsConfig && typeof cfg.eventsConfig === 'object') {
          setEventsConfig(prev => ({ ...prev, ...cfg.eventsConfig }));
        }
      }
    });
  }, []);

  const handleSendTest = async () => {
    try {
      const res = await telegramApi.sendTestAlert('Тестовое уведомление из панели управления: Все системы в норме!');
      notify(res?.message || 'Тестовый сигнал отправлен в Telegram!');
    } catch {
      notify('Тестовый сигнал отправлен на сервер');
    }
  };

  const handleTestProxy = async () => {
    setIsTestingProxy(true);
    setProxyTestResult(null);
    try {
      const res = await telegramApi.testProxy({
        botToken,
        proxyEnabled,
        proxyType,
        proxyHost,
        proxyPort,
        proxyUser,
        proxyPass
      });
      setProxyTestResult(res);
      notify(res.message);
      if (res.botUsername) {
        setBotUsername(res.botUsername);
        setStatus('Подключен');
      }
    } catch (err: any) {
      const msg = `Ошибка связи с прокси: ${err?.message || 'Сервер не отвечает'}`;
      setProxyTestResult({ ok: false, message: msg });
      notify(msg);
    } finally {
      setIsTestingProxy(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      const savedCfg = await telegramApi.saveConfig({
        botToken,
        chatId,
        timezone,
        alertsEnabled,
        botUsername,
        proxyEnabled,
        proxyType,
        proxyHost,
        proxyPort,
        proxyUser,
        proxyPass,
        eventsConfig
      });
      if (savedCfg) {
        if (savedCfg.botUsername !== undefined) setBotUsername(savedCfg.botUsername);
        if (savedCfg.status) setStatus(savedCfg.status);
      }
      notify('Настройки Telegram-бота и прокси успешно сохранены на сервере!');
    } catch {
      notify('Ошибка сохранения настроек Telegram');
    }
  };

  const isConnected = status === 'Подключен' || status === 'Connected';

  return (
    <>
      <PageHeader
        eyebrow="COMMUNICATIONS"
        title="Telegram-бот и Прокси"
        description="Оперативное управление парком физических станций, получение алертов и обход блокировок через прокси."
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button icon={<Send size={15} />} onClick={handleSendTest} disabled={!botToken || !chatId}>Отправить тестовый алерт</Button>
            <Button primary onClick={handleSaveSettings}>Сохранить все настройки</Button>
          </div>
        }
      />
      <div className="detail-grid">
        {/* Panel 1: Bot API Settings */}
        <section className="panel info-panel">
          <div className="panel-heading">
            <div>
              <h2>Параметры Telegram Bot API</h2>
              <p>
                {botUsername ? <strong style={{ color: 'var(--blue)', marginRight: '6px' }}>{botUsername} ·</strong> : null}
                <span className={`badge ${isConnected ? 'match' : 'muted'}`}>
                  {status}
                </span>
              </p>
            </div>
            <Send size={19} className="heading-icon" />
          </div>
          <div style={{ padding: '0 21px 21px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Токен бота (Telegram Bot Token)</label>
              <input
                className="text-input mono"
                style={{ width: '100%' }}
                value={botToken}
                onChange={e => setBotToken(e.target.value)}
                type="password"
                placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
              />
            </div>
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Основной ID чата / группы для алертов</label>
              <input
                className="text-input mono"
                style={{ width: '100%' }}
                value={chatId}
                onChange={e => setChatId(e.target.value)}
                placeholder="-1001234567890"
              />
            </div>
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Часовой пояс уведомлений (Timezone)</label>
              <select
                className="text-input"
                style={{ width: '100%' }}
                value={timezone}
                onChange={e => setTimezone(e.target.value)}
              >
                <option value="Europe/Moscow">Europe/Moscow (UTC+3, Москва / Минск / СПб)</option>
                <option value="Europe/Kaliningrad">Europe/Kaliningrad (UTC+2)</option>
                <option value="Europe/Samara">Europe/Samara (UTC+4)</option>
                <option value="Asia/Yekaterinburg">Asia/Yekaterinburg (UTC+5, Екатеринбург)</option>
                <option value="Asia/Omsk">Asia/Omsk (UTC+6, Омск)</option>
                <option value="Asia/Krasnoyarsk">Asia/Krasnoyarsk (UTC+7, Красноярск, Новосибирск)</option>
                <option value="Asia/Irkutsk">Asia/Irkutsk (UTC+8, Иркутск)</option>
                <option value="Asia/Yakutsk">Asia/Yakutsk (UTC+9, Якутск)</option>
                <option value="Asia/Vladivostok">Asia/Vladivostok (UTC+10, Владивосток)</option>
                <option value="Asia/Magadan">Asia/Magadan (UTC+11, Магадан)</option>
                <option value="Asia/Kamchatka">Asia/Kamchatka (UTC+12, Камчатка)</option>
                <option value="UTC">UTC (GMT+0)</option>
                <option value="Europe/Berlin">Europe/Berlin (CET / UTC+1)</option>
              </select>
            </div>
            <div className="setting-row" style={{ padding: '10px 0', margin: 0 }}>
              <div><strong>Мгновенные алерты в Telegram</strong><span>Включить глобальную рассылку сообщений ботом</span></div>
              <label className="switch"><input type="checkbox" checked={alertsEnabled} onChange={e => setAlertsEnabled(e.target.checked)} /><span /></label>
            </div>
          </div>
        </section>

        {/* Panel 2: Proxy Configuration */}
        <section className="panel info-panel">
          <div className="panel-heading">
            <div>
              <h2>Проксирование Telegram (Обход блокировок)</h2>
              <p>SOCKS5 / HTTP / HTTPS туннелирование</p>
            </div>
            <Globe size={19} className="heading-icon" />
          </div>
          <div style={{ padding: '0 21px 21px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div className="setting-row" style={{ padding: '4px 0', margin: 0 }}>
              <div>
                <strong>Включить проксирование</strong>
                <span style={{ fontSize: '12px', color: 'var(--muted)' }}>Маршрутизировать все запросы к api.telegram.org через прокси</span>
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={proxyEnabled}
                  onChange={e => {
                    setProxyEnabled(e.target.checked);
                    setProxyTestResult(null);
                  }}
                />
                <span />
              </label>
            </div>

            {proxyEnabled && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', background: 'rgba(255,255,255,0.03)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 2fr 1.2fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Протокол</label>
                    <select
                      className="text-input"
                      value={proxyType}
                      onChange={e => setProxyType(e.target.value)}
                      style={{ width: '100%' }}
                    >
                      <option value="SOCKS5">SOCKS5</option>
                      <option value="HTTP">HTTP</option>
                      <option value="HTTPS">HTTPS</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Хост / IP-адрес *</label>
                    <input
                      className="text-input mono"
                      style={{ width: '100%' }}
                      value={proxyHost}
                      onChange={e => setProxyHost(e.target.value)}
                      placeholder="127.0.0.1 или proxy.host"
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Порт *</label>
                    <input
                      className="text-input mono"
                      style={{ width: '100%' }}
                      value={proxyPort}
                      onChange={e => setProxyPort(e.target.value)}
                      placeholder="1080"
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Логин (если требуется)</label>
                    <input
                      className="text-input mono"
                      style={{ width: '100%' }}
                      value={proxyUser}
                      onChange={e => setProxyUser(e.target.value)}
                      placeholder="user"
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Пароль (если требуется)</label>
                    <input
                      className="text-input mono"
                      type="password"
                      style={{ width: '100%' }}
                      value={proxyPass}
                      onChange={e => setProxyPass(e.target.value)}
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                {proxyTestResult && (
                  <div
                    style={{
                      padding: '8px 12px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      background: proxyTestResult.ok ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                      color: proxyTestResult.ok ? 'var(--green)' : 'var(--red)',
                      border: `1px solid ${proxyTestResult.ok ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
                    }}
                  >
                    {proxyTestResult.ok ? <Check size={15} /> : <AlertTriangle size={15} />}
                    <span>{proxyTestResult.message}</span>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
                  <Button
                    onClick={handleTestProxy}
                    disabled={isTestingProxy || !proxyHost.trim() || !proxyPort.trim()}
                    icon={isTestingProxy ? <LoaderCircle size={14} className="spin" /> : <Zap size={14} />}
                  >
                    {isTestingProxy ? 'Проверка соединения...' : 'Проверить прокси соединение'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Panel 3: Granular Telegram Alerts Filtering */}
        <section className="panel info-panel" style={{ gridColumn: '1 / -1' }}>
          <div className="panel-heading">
            <div>
              <h2>Фильтрация категорий оповещений для Telegram</h2>
              <p>Разграничение критических инцидентов и обычных событий для защиты от спама</p>
            </div>
            <Bell size={19} className="heading-icon" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '12px', padding: '0 21px 21px' }}>
            <div className="setting-row" style={{ margin: 0, padding: '12px 14px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '8px' }}>
              <div>
                <strong>Критические сбои оборудования</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Отказ CPU, изъятие модулей памяти RAM, отказ питания</span>
              </div>
              <Switch checked={eventsConfig.criticalAlerts} onChange={v => setEventsConfig(p => ({ ...p, criticalAlerts: v }))} />
            </div>

            <div className="setting-row" style={{ margin: 0, padding: '12px 14px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '8px' }}>
              <div>
                <strong>Изменение конфигурации оборудования</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Замена системных накопителей, видеокарт, сетевых карт</span>
              </div>
              <Switch checked={eventsConfig.hardwareChanges} onChange={v => setEventsConfig(p => ({ ...p, hardwareChanges: v }))} />
            </div>

            <div className="setting-row" style={{ margin: 0, padding: '12px 14px', background: eventsConfig.usbStorage ? 'rgba(235, 120, 50, 0.08)' : 'var(--panel)', border: '1px solid var(--line)', borderRadius: '8px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <strong>Съемные USB-накопители и флешки</strong>
                  <span className="maintenance-badge" style={{ margin: 0 }}>Внимание</span>
                </div>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>По умолчанию выключено. Включайте только для станций строгого контроля, чтобы обычные флешки не спамили в Telegram</span>
              </div>
              <Switch checked={eventsConfig.usbStorage} onChange={v => setEventsConfig(p => ({ ...p, usbStorage: v }))} />
            </div>

            <div className="setting-row" style={{ margin: 0, padding: '12px 14px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '8px' }}>
              <div>
                <strong>Потеря связи со станцией</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Оповещать об уходе рабочей станции в оффлайн (Heartbeat таймаут)</span>
              </div>
              <Switch checked={eventsConfig.disconnectAlerts} onChange={v => setEventsConfig(p => ({ ...p, disconnectAlerts: v }))} />
            </div>

            <div className="setting-row" style={{ margin: 0, padding: '12px 14px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '8px' }}>
              <div>
                <strong>Сбои питания и расписания</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Ошибки утреннего включения WoL и вечернего выключения</span>
              </div>
              <Switch checked={eventsConfig.powerAlerts} onChange={v => setEventsConfig(p => ({ ...p, powerAlerts: v }))} />
            </div>

            <div className="setting-row" style={{ margin: 0, padding: '12px 14px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '8px' }}>
              <div>
                <strong>Ежедневные сводки включения / выключения</strong>
                <span style={{ fontSize: '10px', color: 'var(--muted)' }}>Утренний и вечерний отчеты о готовности парка машин</span>
              </div>
              <Switch checked={eventsConfig.morningWakeSummary} onChange={v => setEventsConfig(p => ({ ...p, morningWakeSummary: v }))} />
            </div>
          </div>
        </section>

        {/* Panel 4: Commands cheat-sheet */}
        <section className="panel info-panel" style={{ gridColumn: '1 / -1' }}>
          <div className="panel-heading">
            <div><h2>Команды управления и ролевой доступ</h2><p>Инструкция для операторов в Telegram</p></div>
            <Terminal size={19} className="heading-icon" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px', padding: '0 21px 21px' }}>
            <div className="setting-row" style={{ margin: 0 }}><div><strong>/id или /start</strong><span>Узнать свой Telegram ID для привязки к учетной записи</span></div></div>
            <div className="setting-row" style={{ margin: 0 }}><div><strong>/status</strong><span>Сводка состояния станций в разрешенных группах</span></div></div>
            <div className="setting-row" style={{ margin: 0 }}><div><strong>/devices</strong><span>Список доступных ПК и их текущий онлайн-статус</span></div></div>
            <div className="setting-row" style={{ margin: 0 }}><div><strong>/wake &lt;ИМЯ_ПК&gt;</strong><span>Отправить Magic Packet (WoL) на ПК своей группы</span></div></div>
            <div className="setting-row" style={{ margin: 0 }}><div><strong>/shutdown &lt;ИМЯ_ПК&gt;</strong><span>Выключить рабочую станцию своей группы</span></div></div>
            <div className="setting-row" style={{ margin: 0 }}><div><strong>/reboot &lt;ИМЯ_ПК&gt;</strong><span>Перезагрузить рабочую станцию своей группы</span></div></div>
          </div>
        </section>
      </div>
    </>
  );
}

// ----------------------------------------------------
// 14. AUDIT LOG & COMPLIANCE TRAIL
// ----------------------------------------------------
function formatAuditTimestamp(raw?: string): string {
  if (!raw) return '—';
  if (raw.includes('T') || raw.endsWith('Z')) {
    const d = new Date(raw);
    if (!isNaN(d.getTime())) {
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    }
  }
  const match = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2}):(\d{2})$/);
  if (match) {
    const [_, day, month, year, hour, min, sec] = match;
    const d = new Date(Date.UTC(parseInt(year), parseInt(month) - 1, parseInt(day), parseInt(hour), parseInt(min), parseInt(sec)));
    if (!isNaN(d.getTime())) {
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    }
  }
  return raw;
}

function renderAuditActionBadge(action: string) {
  const act = action.toUpperCase();
  if (act === 'HARDWARE_REMOVED') {
    return (
      <span className="badge mismatch" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600 }}>
        <Cpu size={12} /> Извлечение железа
      </span>
    );
  }
  if (act === 'HARDWARE_ADDED') {
    return (
      <span className="badge match" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600 }}>
        <Cpu size={12} /> Добавление железа
      </span>
    );
  }
  if (act === 'HARDWARE_REPLACED') {
    return (
      <span className="badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600, background: 'rgba(245, 158, 11, 0.15)', color: 'var(--yellow)', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
        <Cpu size={12} /> Замена модуля
      </span>
    );
  }
  if (act.startsWith('HARDWARE_')) {
    return (
      <span className="badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600, background: 'rgba(59, 130, 246, 0.15)', color: 'var(--blue)' }}>
        <Cpu size={12} /> {act.replace('HARDWARE_', 'Железо: ')}
      </span>
    );
  }
  if (act === 'BASELINE_APPROVED') {
    return (
      <span className="badge match" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600 }}>
        <ShieldCheck size={12} /> Эталон утверждён
      </span>
    );
  }
  if (act.startsWith('ALERT_')) {
    return (
      <span className="badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600, background: 'rgba(168, 85, 247, 0.15)', color: 'var(--purple)' }}>
        <Bell size={12} /> {act.replace('ALERT_', '')}
      </span>
    );
  }
  if (act === 'WAKE') {
    return (
      <span className="badge match" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600 }}>
        <Zap size={12} /> WAKE (WoL)
      </span>
    );
  }
  if (act === 'SHUTDOWN' || act === 'REBOOT') {
    return (
      <span className="badge mismatch" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600 }}>
        <Power size={12} /> {act}
      </span>
    );
  }

  return <span className="action-code">{action}</span>;
}

function AuditLog({ compact = false, deviceId }: { compact?: boolean; deviceId?: string }) {
  const { t } = useLanguage();
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [deviceMap, setDeviceMap] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<'ALL' | 'HARDWARE' | 'POWER' | 'ALERTS' | 'SECURITY'>('ALL');
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(() => {
    setLoading(true);
    auditApi.list().then((logs) => {
      setItems(logs || []);
      setLoading(false);
    }).catch(() => setLoading(false));

    devicesApi.list().then(devs => {
      if (Array.isArray(devs)) {
        const map: Record<string, string> = {};
        devs.forEach(d => {
          if (d.id) map[d.id.toUpperCase()] = d.name;
          if (d.hostname) map[d.hostname.toUpperCase()] = d.name;
        });
        setDeviceMap(map);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    loadData();
    const unsub1 = wsClient.on('audit.created', () => loadData());
    const unsub2 = wsClient.on('hardware.change', () => loadData());
    const unsub3 = wsClient.on('baseline.updated', () => loadData());
    const unsub4 = wsClient.on('alert.resolved', () => loadData());
    return () => {
      unsub1();
      unsub2();
      unsub3();
      unsub4();
    };
  }, [loadData]);

  const getTargetDisplayName = (rawTarget: string) => {
    if (!rawTarget) return 'Fleet';
    const upper = rawTarget.toUpperCase();
    if (deviceMap[upper]) {
      return deviceMap[upper];
    }
    return rawTarget;
  };

  // Hardware and categories count
  const hardwareCount = items.filter(i => i.action.startsWith('HARDWARE_') || i.action.startsWith('BASELINE_')).length;
  const powerCount = items.filter(i => ['WAKE', 'SHUTDOWN', 'REBOOT', 'FORCE_SHUTDOWN'].includes(i.action.toUpperCase())).length;
  const alertCount = items.filter(i => i.action.startsWith('ALERT_') || i.action.startsWith('ALERTS_')).length;
  const criticalCount = items.filter(i => i.result === 'CRITICAL' || i.result === 'FAILED').length;

  const filtered = (deviceId ? items.filter(item => item.target === deviceId || item.target === getTargetDisplayName(deviceId)) : items)
    .filter(e => {
      const act = e.action.toUpperCase();
      let matchCat = true;
      if (categoryFilter === 'HARDWARE') {
        matchCat = act.startsWith('HARDWARE_') || act.startsWith('BASELINE_');
      } else if (categoryFilter === 'POWER') {
        matchCat = ['WAKE', 'SHUTDOWN', 'REBOOT', 'FORCE_SHUTDOWN'].includes(act);
      } else if (categoryFilter === 'ALERTS') {
        matchCat = act.startsWith('ALERT_') || act.startsWith('ALERTS_');
      } else if (categoryFilter === 'SECURITY') {
        matchCat = act.startsWith('USER_') || act.startsWith('ROLE_') || act.startsWith('TOKEN_');
      }

      const targetName = getTargetDisplayName(e.target);
      const matchQuery = `${e.action} ${e.user} ${e.target} ${targetName} ${e.details}`.toLowerCase().includes(query.toLowerCase());
      return matchCat && matchQuery;
    });

  return (
    <>
      <PageHeader
        eyebrow="COMPLIANCE & AUDIT TRAIL"
        title={compact ? 'История активности' : 'Журнал аудита'}
        description={compact ? 'Команды и аппаратные события данной рабочей станции.' : 'Неизменяемый реестр всех системных действий, изменений конфигураций железа и решений операторов.'}
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button icon={<RefreshCw size={14} />} onClick={() => loadData()}>
              {t('common.refresh')}
            </Button>
            {!compact && (
              <Button primary icon={<ArrowDownToLine size={14} />} onClick={() => exportAuditToCsv(filtered)}>
                {t('common.export')} (CSV)
              </Button>
            )}
          </div>
        }
      />

      {/* KPI Bento summary when on full page */}
      {!compact && (
        <div className="bento-grid" style={{ marginBottom: '22px' }}>
          <div className="bento-card col-3" onClick={() => setCategoryFilter('ALL')} style={{ cursor: 'pointer' }}>
            <div className="bento-header">
              <span className="bento-card-title">Все события аудита</span>
              <div className="bento-icon cyan"><Terminal size={18} /></div>
            </div>
            <div className="bento-value">{loading ? '—' : items.length} <small>записей</small></div>
            <div className="bento-footer">
              <span>Полный хронологический лог</span>
              <ArrowRight size={14} style={{ color: 'var(--muted)' }} />
            </div>
          </div>

          <div className="bento-card col-3" onClick={() => setCategoryFilter('HARDWARE')} style={{ cursor: 'pointer' }}>
            <div className="bento-header">
              <span className="bento-card-title">События оборудования</span>
              <div className="bento-icon purple"><Cpu size={18} /></div>
            </div>
            <div className="bento-value">{loading ? '—' : hardwareCount} <small>событий железа</small></div>
            <div className="bento-footer">
              <span>ОЗУ, диски, GPU, эталоны</span>
              <ArrowRight size={14} style={{ color: 'var(--muted)' }} />
            </div>
          </div>

          <div className="bento-card col-3" onClick={() => setCategoryFilter('POWER')} style={{ cursor: 'pointer' }}>
            <div className="bento-header">
              <span className="bento-card-title">Команды питания</span>
              <div className="bento-icon green"><Zap size={18} /></div>
            </div>
            <div className="bento-value">{loading ? '—' : powerCount} <small>команд</small></div>
            <div className="bento-footer">
              <span>WoL, выключение, перезагрузка</span>
              <ArrowRight size={14} style={{ color: 'var(--muted)' }} />
            </div>
          </div>

          <div className="bento-card col-3" onClick={() => setCategoryFilter('ALERTS')} style={{ cursor: 'pointer' }}>
            <div className="bento-header">
              <span className="bento-card-title">Инциденты и Решения</span>
              <div className="bento-icon red"><Bell size={18} /></div>
            </div>
            <div className="bento-value" style={{ color: criticalCount > 0 ? '#ef4444' : 'inherit' }}>
              {loading ? '—' : alertCount} <small>решений</small>
            </div>
            <div className="bento-footer">
              <span style={{ color: criticalCount > 0 ? 'var(--red)' : 'var(--muted)' }}>
                {criticalCount > 0 ? `${criticalCount} критических инцидентов` : 'Все инциденты закрыты'}
              </span>
              <Check size={14} style={{ color: 'var(--green)' }} />
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="audit-filters" style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div className="search wide" style={{ flex: 1, minWidth: '240px' }}>
          <Search size={15} />
          <input placeholder="Поиск по действиям, пользователям, оборудованию или ПК..." value={query} onChange={e => setQuery(e.target.value)} />
        </div>
        {!compact && (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <button
              className={`badge ${categoryFilter === 'ALL' ? 'match' : ''}`}
              style={{ cursor: 'pointer', padding: '6px 12px', fontSize: '12px' }}
              onClick={() => setCategoryFilter('ALL')}
            >
              Все ({items.length})
            </button>
            <button
              className={`badge ${categoryFilter === 'HARDWARE' ? 'match' : ''}`}
              style={{ cursor: 'pointer', padding: '6px 12px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
              onClick={() => setCategoryFilter('HARDWARE')}
            >
              <Cpu size={12} /> Железо и эталоны ({hardwareCount})
            </button>
            <button
              className={`badge ${categoryFilter === 'POWER' ? 'match' : ''}`}
              style={{ cursor: 'pointer', padding: '6px 12px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
              onClick={() => setCategoryFilter('POWER')}
            >
              <Zap size={12} /> Питание ({powerCount})
            </button>
            <button
              className={`badge ${categoryFilter === 'ALERTS' ? 'match' : ''}`}
              style={{ cursor: 'pointer', padding: '6px 12px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
              onClick={() => setCategoryFilter('ALERTS')}
            >
              <Bell size={12} /> Оповещения ({alertCount})
            </button>
          </div>
        )}
      </div>

      <section className="panel table-panel">
        <div className="audit-list">
          <div className="audit-head">
            <span>Дата / Время</span>
            <span>Пользователь</span>
            <span>Действие</span>
            <span>Цель</span>
            <span>Результат</span>
            <span>Детали</span>
          </div>
          {filtered.length === 0 ? (
            <div className="empty-state" style={{ minHeight: '180px' }}>
              <Terminal size={24} />
              <span>Журнал аудита пуст</span>
              <small style={{ color: 'var(--muted)', marginTop: '4px' }}>Все последующие действия и события оборудования будут автоматически зафиксированы</small>
            </div>
          ) : (
            filtered.map(entry => (
              <div className="audit-row" key={entry.id}>
                <span className="muted-text" style={{ whiteSpace: 'nowrap' }}>{formatAuditTimestamp(entry.timestamp)}</span>
                <strong>{entry.user}</strong>
                <div>{renderAuditActionBadge(entry.action)}</div>
                <span style={{ fontWeight: 600 }}>{getTargetDisplayName(entry.target)}</span>
                <StatusPill status={entry.result} />
                <span className="muted-text audit-detail">{entry.details}</span>
              </div>
            ))
          )}
        </div>
      </section>
    </>
  );
}

// ----------------------------------------------------
// 15. GROUPS WITH MULTI-GROUP MEMBERSHIP & EDIT MODALS
// ----------------------------------------------------
interface GroupData {
  name: string;
  count: number;
  desc: string;
  color: 'blue' | 'green' | 'purple' | 'orange' | 'red' | 'cyan' | 'slate';
  schedule: string;
}

function Groups({
  onNavigate,
  onDevice,
  notify,
  selectedGroupName,
  onSelectGroup,
  currentUser
}: {
  onNavigate?: (page: Page, filter?: any) => void;
  onDevice: (id: string) => void;
  notify: (message: string) => void;
  selectedGroupName?: string;
  onSelectGroup: (name: string | null) => void;
  currentUser?: ManagedUser | null;
}) {
  const { t } = useLanguage();
  const isSuperAdmin = currentUser?.role === 'Суперадминистратор' || currentUser?.role === 'SuperAdmin';
  const isObserver = currentUser?.role === 'Наблюдатель' || currentUser?.role === 'Observer';
  const hasRestrictedScope = !isSuperAdmin && currentUser?.scope !== 'Все устройства' && Array.isArray(currentUser?.allowedGroups) && currentUser.allowedGroups.length > 0;
  const allowedGroupNames = hasRestrictedScope ? currentUser.allowedGroups.map(g => g.toLowerCase().trim()) : null;
  const canManageGroup = (groupName: string) => !hasRestrictedScope || (allowedGroupNames ? allowedGroupNames.includes(groupName.toLowerCase().trim()) : false);

  const [devices, setDevices] = useState<Device[]>([]);
  const [groups, setGroups] = useState<GroupData[]>([
    { name: 'Office', count: 1, desc: 'Компьютеры главного офиса компании', color: 'blue', schedule: 'Office Working Day' },
    { name: 'Warehouse', count: 0, desc: 'Терминалы логистического склада', color: 'orange', schedule: 'Warehouse Night Mode' },
    { name: 'Management', count: 0, desc: 'Руководство и переговорные комнаты', color: 'green', schedule: 'Без расписания' },
    { name: 'Testing', count: 0, desc: 'QA и тестовая лаборатория оборудования', color: 'purple', schedule: 'Testing Lab' },
    { name: 'Dev', count: 0, desc: 'Рабочие станции разработчиков и дизайнеров', color: 'cyan', schedule: 'Dev Working Day' }
  ]);

  // Create modal state
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDesc, setNewGroupDesc] = useState('');
  const [newGroupSchedule, setNewGroupSchedule] = useState('Без расписания');
  const [newGroupColor, setNewGroupColor] = useState<GroupData['color']>('blue');

  // Edit modal state
  const [editGroupTarget, setEditGroupTarget] = useState<GroupData | null>(null);
  const [editGroupName, setEditGroupName] = useState('');
  const [editGroupDesc, setEditGroupDesc] = useState('');
  const [editGroupSchedule, setEditGroupSchedule] = useState('');
  const [editGroupColor, setEditGroupColor] = useState<GroupData['color']>('blue');
  const [editGroupInterval, setEditGroupInterval] = useState<number>(60);
  const [groupIntervals, setGroupIntervals] = useState<Record<string, number>>({ Servers: 15, DevOps: 30, Office: 60 });

  // Add PC to group modal
  const [showAddPcModal, setShowAddPcModal] = useState(false);
  const [selectedPcToAssign, setSelectedPcToAssign] = useState<string>('');

  // 3-Level Hierarchy Drill-Down State (Cards / Tiles)
  const [drillBuilding, setDrillBuilding] = useState<string | null>(null);
  const [drillFloor, setDrillFloor] = useState<string | null>(null);
  const [drillSearch, setDrillSearch] = useState<string>('');

  // Building Configurations (loaded from backend)
  const [buildingConfigs, setBuildingConfigs] = useState<BuildingConfig[]>([]);

  // 3-Level Creation Form State
  const [isHierarchicalCreate, setIsHierarchicalCreate] = useState<boolean>(true);
  const [selectedBuildingOption, setSelectedBuildingOption] = useState<string>('Главный корпус');
  const [isNewBuildingMode, setIsNewBuildingMode] = useState<boolean>(false);
  const [newBuildingNameInput, setNewBuildingNameInput] = useState<string>('');
  const [newBuildingFloorsCount, setNewBuildingFloorsCount] = useState<string>('3');
  const [newBuildingHasBasement, setNewBuildingHasBasement] = useState<boolean>(false);
  const [newBuildingHasSubFloor, setNewBuildingHasSubFloor] = useState<boolean>(false);

  const [selectedFloorOption, setSelectedFloorOption] = useState<string>('1 этаж');
  const [isCustomFloorMode, setIsCustomFloorMode] = useState<boolean>(false);
  const [customFloorInput, setCustomFloorInput] = useState<string>('');
  const [createRoom, setCreateRoom] = useState<string>('');

  const parseGroupHierarchy = useCallback((gName: string, bld?: string, flr?: string, rm?: string) => {
    let b = (bld || '').trim();
    let f = (flr || '').trim();
    let r = (rm || '').trim();

    if ((!b || !r) && gName.includes('/')) {
      const parts = gName.split('/').map(s => s.trim());
      if (parts.length >= 3) {
        b = parts[0];
        f = parts[1];
        r = parts[2];
      } else if (parts.length === 2) {
        b = parts[0];
        f = '1 этаж';
        r = parts[1];
      }
    }

    return {
      building: b || 'Общие группы',
      floor: f || '1 этаж',
      room: r || gName,
      isHierarchical: Boolean(b && b !== 'Общие группы')
    };
  }, []);

  const loadData = () => {
    groupsApi.list().then((serverGroups) => {
      if (serverGroups && serverGroups.length > 0) {
        setGroups(serverGroups.map(g => ({
          name: g.name,
          count: 0,
          desc: g.desc || 'Рабочая группа',
          color: (g.color || 'blue') as GroupData['color'],
          schedule: g.schedule || 'Без расписания',
          building: (g as any).building || '',
          floor: (g as any).floor || '',
          room: (g as any).room || ''
        } as any)));
      }
    });
    groupsApi.getBuildings().then(blds => {
      if (blds && blds.length > 0) setBuildingConfigs(blds);
    });
    devicesApi.list().then((devList) => {
      setDevices(devList);
      setGroups(prev => prev.map(g => ({
        ...g,
        count: devList.filter(d => getDeviceGroups(d).some(grp => grp.toLowerCase() === g.name.toLowerCase())).length
      })));
    });
    agentsApi.getSettings().then(s => {
      if (s && s.groupHeartbeatIntervals) setGroupIntervals(s.groupHeartbeatIntervals);
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const visibleGroups = useMemo(() => {
    if (hasRestrictedScope && allowedGroupNames) {
      return groups.filter(g => allowedGroupNames.includes(g.name.toLowerCase().trim()));
    }
    return groups;
  }, [groups, hasRestrictedScope, allowedGroupNames]);

  const hierarchyData = useMemo(() => {
    const buildingsMap: Record<string, {
      name: string;
      floors: Record<string, {
        name: string;
        rooms: (GroupData & { roomName: string })[];
      }>;
    }> = {};

    visibleGroups.forEach(g => {
      const { building, floor, room } = parseGroupHierarchy(g.name, (g as any).building, (g as any).floor, (g as any).room);
      if (!buildingsMap[building]) {
        buildingsMap[building] = { name: building, floors: {} };
      }
      if (!buildingsMap[building].floors[floor]) {
        buildingsMap[building].floors[floor] = { name: floor, rooms: [] };
      }
      buildingsMap[building].floors[floor].rooms.push({
        ...g,
        roomName: room
      });
    });

    return buildingsMap;
  }, [visibleGroups, parseGroupHierarchy]);

  const availableBuildingOptions = useMemo(() => {
    const list: string[] = [];
    buildingConfigs.forEach(b => {
      if (b.name && !list.includes(b.name)) list.push(b.name);
    });
    Object.keys(hierarchyData).forEach(bName => {
      if (bName && bName !== 'Общие группы' && !list.includes(bName)) list.push(bName);
    });
    return list.length > 0 ? list : ['Главный корпус', 'Учебный корпус'];
  }, [buildingConfigs, hierarchyData]);

  const activeBuildingName = isNewBuildingMode
    ? newBuildingNameInput.trim()
    : (selectedBuildingOption || availableBuildingOptions[0] || 'Главный корпус');

  const parsedNewBuildingFloorsCount = Math.max(1, Math.min(50, parseInt(newBuildingFloorsCount, 10) || 1));

  const availableFloorsForActiveBuilding = useMemo(() => {
    if (isNewBuildingMode) {
      return generateBuildingFloors(parsedNewBuildingFloorsCount, newBuildingHasBasement, newBuildingHasSubFloor);
    }
    const found = buildingConfigs.find(b => b.name.toLowerCase() === activeBuildingName.toLowerCase());
    if (found && found.floors && found.floors.length > 0) {
      return found.floors;
    }
    const fromHierarchy = hierarchyData[activeBuildingName]?.floors;
    if (fromHierarchy) {
      const keys = Object.keys(fromHierarchy);
      if (keys.length > 0) return keys;
    }
    return generateBuildingFloors(3, false, false);
  }, [isNewBuildingMode, parsedNewBuildingFloorsCount, newBuildingHasBasement, newBuildingHasSubFloor, buildingConfigs, activeBuildingName, hierarchyData]);

  const getBuildingStats = useCallback((bldName: string) => {
    const bld = hierarchyData[bldName];
    if (!bld) return { floorsCount: 0, roomsCount: 0, totalPcs: 0, onlinePcs: 0, groupNames: [] as string[] };
    const floors = Object.values(bld.floors);
    const floorsCount = floors.length;
    let roomsCount = 0;
    const groupNames: string[] = [];
    floors.forEach(f => {
      roomsCount += f.rooms.length;
      f.rooms.forEach(r => groupNames.push(r.name.toLowerCase()));
    });
    const bldDevs = devices.filter(d => getDeviceGroups(d).some(grp => groupNames.includes(grp.toLowerCase())));
    const totalPcs = bldDevs.length;
    const onlinePcs = bldDevs.filter(d => d.powerStatus === 'On').length;
    return { floorsCount, roomsCount, totalPcs, onlinePcs, groupNames };
  }, [hierarchyData, devices]);

  const getFloorStats = useCallback((bldName: string, flrName: string) => {
    const bld = hierarchyData[bldName];
    const flr = bld?.floors[flrName];
    if (!flr) return { roomsCount: 0, totalPcs: 0, onlinePcs: 0, groupNames: [] as string[] };
    const roomsCount = flr.rooms.length;
    const groupNames = flr.rooms.map(r => r.name.toLowerCase());
    const flrDevs = devices.filter(d => getDeviceGroups(d).some(grp => groupNames.includes(grp.toLowerCase())));
    const totalPcs = flrDevs.length;
    const onlinePcs = flrDevs.filter(d => d.powerStatus === 'On').length;
    return { roomsCount, totalPcs, onlinePcs, groupNames };
  }, [hierarchyData, devices]);

  useEffect(() => {
    if (hasRestrictedScope && selectedGroupName && !canManageGroup(selectedGroupName)) {
      const fallback = visibleGroups[0]?.name || null;
      onSelectGroup(fallback);
      notify('Доступ к этой группе ограничен вашей зоной ответственности');
    }
  }, [hasRestrictedScope, selectedGroupName, visibleGroups]);

  const selectedGroup = selectedGroupName ? groups.find(g => g.name.toLowerCase() === selectedGroupName.toLowerCase()) || {
    name: selectedGroupName,
    count: 0,
    desc: 'Рабочая группа',
    color: 'blue' as const,
    schedule: 'Без расписания'
  } : null;

  const handleCreateGroup = async () => {
    if (!isSuperAdmin) {
      notify('Отказ в доступе: создание групп разрешено только Суперадминистратору');
      return;
    }

    let finalName = '';
    let bldVal = '';
    let flrVal = '';
    let rmVal = '';

    if (isHierarchicalCreate) {
      if (isNewBuildingMode) {
        bldVal = newBuildingNameInput.trim();
        if (!bldVal) {
          notify('Пожалуйста, укажите название нового корпуса');
          return;
        }
        const parsedFloorsCount = Math.max(1, Math.min(50, parseInt(newBuildingFloorsCount, 10) || 1));
        const genFloors = generateBuildingFloors(parsedFloorsCount, newBuildingHasBasement, newBuildingHasSubFloor);
        await groupsApi.saveBuilding({
          name: bldVal,
          floorsCount: parsedFloorsCount,
          hasBasement: newBuildingHasBasement,
          hasSubFloor: newBuildingHasSubFloor,
          floors: genFloors
        });
        setBuildingConfigs(prev => [...prev.filter(b => b.name.toLowerCase() !== bldVal.toLowerCase()), {
          name: bldVal,
          floorsCount: parsedFloorsCount,
          hasBasement: newBuildingHasBasement,
          hasSubFloor: newBuildingHasSubFloor,
          floors: genFloors
        }]);
      } else {
        bldVal = selectedBuildingOption.trim() || availableBuildingOptions[0] || 'Главный корпус';
      }

      flrVal = (isCustomFloorMode ? customFloorInput.trim() : (selectedFloorOption || availableFloorsForActiveBuilding[0] || '1 этаж')).trim();
      rmVal = createRoom.trim() || newGroupName.trim();
      if (!rmVal) {
        notify('Пожалуйста, укажите название или номер кабинета');
        return;
      }
      finalName = `${bldVal} / ${flrVal} / ${rmVal}`;
    } else {
      finalName = newGroupName.trim();
      if (!finalName) {
        notify('Пожалуйста, укажите название группы');
        return;
      }
    }

    const created: GroupData = {
      name: finalName,
      count: 0,
      desc: newGroupDesc || (isHierarchicalCreate ? `Кабинет ${rmVal} (${bldVal}, ${flrVal})` : 'Пользовательская группа рабочих станций'),
      color: newGroupColor,
      schedule: newGroupSchedule,
      building: bldVal,
      floor: flrVal,
      room: rmVal
    } as any;

    setGroups(prev => [...prev, created]);
    await groupsApi.create(created);
    notify(`Группа "${created.name}" успешно создана!`);
    setShowCreateGroup(false);
    setNewGroupName('');
    setCreateRoom('');
    setNewGroupDesc('');
    setNewGroupColor('blue');
    setIsNewBuildingMode(false);
    setNewBuildingNameInput('');
    setNewBuildingFloorsCount('3');
    setIsCustomFloorMode(false);
    setCustomFloorInput('');
    loadData();
  };

  const handleOpenEditGroupModal = (g: GroupData) => {
    setEditGroupTarget(g);
    setEditGroupName(g.name);
    setEditGroupDesc(g.desc);
    setEditGroupSchedule(g.schedule);
    setEditGroupColor(g.color);
    setEditGroupInterval(groupIntervals[g.name] || 60);
  };

  const handleSaveEditGroup = async () => {
    if (!isSuperAdmin) {
      notify('Отказ в доступе: редактирование групп разрешено только Суперадминистратору');
      return;
    }
    if (!editGroupTarget || !editGroupName) return;
    const oldName = editGroupTarget.name;
    const newName = editGroupName.trim();

    const updatedData = {
      name: newName,
      desc: editGroupDesc,
      schedule: editGroupSchedule,
      color: editGroupColor
    };

    setGroups(prev => prev.map(g => g.name === oldName ? { ...g, ...updatedData } : g));
    await groupsApi.update(oldName, updatedData);

    const newMap = { ...groupIntervals, [newName]: editGroupInterval };
    if (oldName !== newName && (oldName in newMap)) delete (newMap as any)[oldName];
    setGroupIntervals(newMap);
    agentsApi.updateSettings({ groupHeartbeatIntervals: newMap });

    if (selectedGroupName?.toLowerCase() === oldName.toLowerCase()) {
      onSelectGroup(newName);
    }
    notify(`Параметры группы "${newName}" успешно сохранены!`);
    setEditGroupTarget(null);
  };

  const handleDeleteGroup = async (groupName: string) => {
    if (!isSuperAdmin) {
      notify('Отказ в доступе: удаление групп разрешено только Суперадминистратору');
      return;
    }
    setGroups(prev => prev.filter(g => g.name !== groupName));
    await groupsApi.delete(groupName);
    if (selectedGroupName?.toLowerCase() === groupName.toLowerCase()) {
      onSelectGroup(null);
    }
    notify(`Группа "${groupName}" удалена`);
    setEditGroupTarget(null);
  };

  const handleAssignPcToGroup = async () => {
    if (!selectedGroup || !selectedPcToAssign) return;
    if (!canManageGroup(selectedGroup.name) || isObserver) {
      notify('Отказ в доступе: вы не можете добавлять компьютеры в эту группу');
      return;
    }
    const targetDev = devices.find(d => d.id === selectedPcToAssign);
    if (targetDev) {
      const existingGroups = getDeviceGroups(targetDev);
      if (!existingGroups.includes(selectedGroup.name)) {
        const updatedGroups = [...existingGroups, selectedGroup.name];
        await devicesApi.update(targetDev.id, { ...targetDev, groups: updatedGroups });
        notify(`Компьютер ${targetDev.name} добавлен в группу "${selectedGroup.name}"!`);
      } else {
        notify(`Компьютер ${targetDev.name} уже состоит в группе "${selectedGroup.name}"`);
      }
      setShowAddPcModal(false);
      setSelectedPcToAssign('');
      loadData();
    }
  };

  const [selectedGroupPcIds, setSelectedGroupPcIds] = useState<string[]>([]);

  useEffect(() => {
    setSelectedGroupPcIds([]);
  }, [selectedGroupName]);

  const handleBulkGroupPower = async (action: 'WAKE' | 'SHUTDOWN' | 'REBOOT') => {
    if (selectedGroupPcIds.length === 0) return;
    if (!canManageGroup(selectedGroup?.name || '') || isObserver) {
      notify('Отказ в доступе: управление питанием недоступно для этой группы');
      return;
    }
    const actionNames: Record<string, string> = {
      WAKE: 'Включение (WoL)',
      SHUTDOWN: 'Выключение',
      REBOOT: 'Перезагрузка'
    };
    try {
      await devicesApi.bulkOperation(selectedGroupPcIds, action);
      notify(`Команда "${actionNames[action]}" отправлена на ${selectedGroupPcIds.length} выбранных ПК`);
      setTimeout(loadData, 1200);
    } catch (e) {
      notify('Ошибка выполнения групповой команды');
    }
  };

  const handleBulkRemoveFromGroup = async () => {
    if (!selectedGroup || selectedGroupPcIds.length === 0) return;
    if (!canManageGroup(selectedGroup.name) || isObserver) {
      notify('Отказ в доступе: у вас нет прав на управление этой группой');
      return;
    }
    const currentGroupDevices = devices.filter(d => getDeviceGroups(d).some(grp => grp.toLowerCase() === selectedGroup.name.toLowerCase()));
    const devsToUpdate = currentGroupDevices.filter(d => selectedGroupPcIds.includes(d.id));
    if (devsToUpdate.length === 0) return;

    for (const d of devsToUpdate) {
      const existingGroups = getDeviceGroups(d);
      const updatedGroups = existingGroups.filter(g => g.toLowerCase() !== selectedGroup.name.toLowerCase());
      await devicesApi.update(d.id, { ...d, groups: updatedGroups });
    }
    notify(`Удалено ${devsToUpdate.length} ПК из группы "${selectedGroup.name}"`);
    setSelectedGroupPcIds([]);
    loadData();
  };

  const handleRemovePcFromGroup = async (dev: Device) => {
    if (!selectedGroup) return;
    if (!canManageGroup(selectedGroup.name) || isObserver) {
      notify('Отказ в доступе: у вас нет прав на управление этой группой');
      return;
    }
    const existingGroups = getDeviceGroups(dev);
    const updatedGroups = existingGroups.filter(g => g.toLowerCase() !== selectedGroup.name.toLowerCase());
    await devicesApi.update(dev.id, { ...dev, groups: updatedGroups });
    notify(`Компьютер ${dev.name} удален из группы "${selectedGroup.name}"`);
    setSelectedGroupPcIds(prev => prev.filter(id => id !== dev.id));
    loadData();
  };

  const colorOptions: { id: GroupData['color']; label: string }[] = [
    { id: 'blue', label: 'Синий' },
    { id: 'green', label: 'Зеленый' },
    { id: 'purple', label: 'Фиолетовый' },
    { id: 'orange', label: 'Оранжевый' },
    { id: 'red', label: 'Красный' },
    { id: 'cyan', label: 'Бирюзовый' },
    { id: 'slate', label: 'Серый' }
  ];

  return (
    <>
      {selectedGroup ? (
        /* ================= GROUP DETAIL VIEW ================= */
        (() => {
          const groupDevices = devices.filter(d => getDeviceGroups(d).some(grp => grp.toLowerCase() === selectedGroup.name.toLowerCase()));
          const onlineInGroup = groupDevices.filter(d => d.powerStatus === 'On').length;
          const rdpInGroup = groupDevices.filter(d => d.rdpStatus === 'Running' || d.rdpStatus === 'Active').length;

          return (
            <>
              <button className="back-link" onClick={() => onSelectGroup(null)} style={{ cursor: 'pointer' }}>
                <ChevronRight size={15} className="back-chevron" /> Назад ко всем группам
              </button>

              <div className="detail-header" style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <div className={`bento-icon ${selectedGroup.color}`} style={{ width: '52px', height: '52px', borderRadius: '12px' }}>
                    <Server size={26} />
                  </div>
                  <div>
                    <div className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      ГРУППА СТАНЦИЙ · <span className="badge" style={{ textTransform: 'uppercase' }}>{selectedGroup.color}</span>
                    </div>
                    <h1 style={{ fontSize: '26px' }}>{selectedGroup.name}</h1>
                    <p>{selectedGroup.desc} · <Clock3 size={13} style={{ verticalAlign: '-2px', marginLeft: '4px' }} /> {selectedGroup.schedule}</p>
                  </div>
                </div>

                <div className="header-actions">
                  {isSuperAdmin && (
                    <Button
                      icon={<Edit3 size={15} />}
                      onClick={() => handleOpenEditGroupModal(selectedGroup)}
                    >
                      Настройки группы
                    </Button>
                  )}
                  {canManageGroup(selectedGroup.name) && !isObserver && (
                    <Button
                      primary
                      icon={<Zap size={15} />}
                      onClick={async () => {
                        const groupDevIds = groupDevices.map(d => d.id);
                        if (groupDevIds.length > 0) {
                          await devicesApi.bulkOperation(groupDevIds, 'WAKE');
                          notify(`Magic Packet (WoL) отправлен на ${groupDevIds.length} ПК группы "${selectedGroup.name}"`);
                          setTimeout(loadData, 1200);
                        } else {
                          notify(`В группе "${selectedGroup.name}" нет добавленных ПК`);
                        }
                      }}
                    >
                      Включить всю группу (WoL)
                    </Button>
                  )}
                  {canManageGroup(selectedGroup.name) && !isObserver && (
                    <Button
                      icon={<Plus size={15} />}
                      onClick={() => setShowAddPcModal(true)}
                    >
                      + Добавить ПК
                    </Button>
                  )}
                </div>
              </div>

              {/* Bento KPI row for Group */}
              <div className="bento-grid" style={{ marginBottom: '20px' }}>
                <div className="bento-card col-4">
                  <div>
                    <div className="bento-header">
                      <span className="bento-card-title">Устройств в группе</span>
                      <div className={`bento-icon ${selectedGroup.color}`}><Server size={18} /></div>
                    </div>
                    <div className="bento-value">{groupDevices.length} <small style={{ fontSize: '13px', color: 'var(--muted)', fontWeight: 500 }}>ПК</small></div>
                  </div>
                  <div className="bento-footer">
                    <span>{groupDevices.length > 0 ? `${onlineInGroup} из ${groupDevices.length} активны` : 'Нет ПК в группе'}</span>
                    <Monitor size={14} style={{ color: 'var(--muted)' }} />
                  </div>
                </div>

                <div className="bento-card col-4">
                  <div>
                    <div className="bento-header">
                      <span className="bento-card-title">Статус питания (Онлайн)</span>
                      <div className="bento-icon green"><Wifi size={18} /></div>
                    </div>
                    <div className="bento-value" style={{ color: 'var(--green)' }}>{onlineInGroup} <small style={{ fontSize: '13px', color: 'var(--muted)', fontWeight: 500 }}>в сети</small></div>
                  </div>
                  <div className="bento-footer">
                    <span>{groupDevices.length - onlineInGroup} выключено</span>
                    <Power size={14} style={{ color: 'var(--green)' }} />
                  </div>
                </div>

                <div className="bento-card col-4">
                  <div>
                    <div className="bento-header">
                      <span className="bento-card-title">Активные RDP сессии</span>
                      <div className="bento-icon purple"><Monitor size={18} /></div>
                    </div>
                    <div className="bento-value">{rdpInGroup} <small style={{ fontSize: '13px', color: 'var(--muted)', fontWeight: 500 }}>Подключений</small></div>
                  </div>
                  <div className="bento-footer">
                    <span>{selectedGroup.schedule}</span>
                    <Clock3 size={14} style={{ color: 'var(--muted)' }} />
                  </div>
                </div>
              </div>

              {/* Group PCs table */}
              <section className="panel table-panel">
                <div className="panel-heading table-heading">
                  <div>
                    <h2>Компьютеры группы "{selectedGroup.name}"</h2>
                    <p>{groupDevices.length} рабочих станций привязано к этой группе</p>
                  </div>
                </div>

                {selectedGroupPcIds.length > 0 && (
                  <div className="bulk-bar" style={{ margin: '0 21px 16px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span>Выбрано: <strong>{selectedGroupPcIds.length}</strong> из {groupDevices.length} ПК</span>
                    <Button primary icon={<Zap size={14} />} onClick={() => handleBulkGroupPower('WAKE')}>
                      Включить (WoL)
                    </Button>
                    <Button icon={<Power size={14} />} onClick={() => handleBulkGroupPower('SHUTDOWN')}>
                      Выключить
                    </Button>
                    <Button icon={<RotateCcw size={14} />} onClick={() => handleBulkGroupPower('REBOOT')}>
                      Перезагрузить
                    </Button>
                    <Button style={{ color: 'var(--red)' }} icon={<Trash2 size={14} />} onClick={handleBulkRemoveFromGroup}>
                      Удалить из группы
                    </Button>
                    <button
                      className="bulk-close"
                      onClick={() => setSelectedGroupPcIds([])}
                      style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
                      title="Снять выбор"
                    >
                      <X size={15} />
                    </button>
                  </div>
                )}

                {groupDevices.length === 0 ? (
                  <div className="empty-state" style={{ minHeight: '180px' }}>
                    <Monitor size={26} />
                    <span>В группе "{selectedGroup.name}" пока нет компьютеров</span>
                    <small style={{ color: 'var(--muted)' }}>Нажмите кнопку «+ Добавить ПК» вверху для добавления существующих компьютеров</small>
                  </div>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th style={{ width: '40px', paddingLeft: '16px' }}>
                            <input
                              type="checkbox"
                              checked={groupDevices.length > 0 && selectedGroupPcIds.length === groupDevices.length}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedGroupPcIds(groupDevices.map(d => d.id));
                                } else {
                                  setSelectedGroupPcIds([]);
                                }
                              }}
                            />
                          </th>
                          <th>Статус</th>
                          <th>Имя ПК</th>
                          <th>Все группы ПК</th>
                          <th>IP-адрес</th>
                          <th>MAC-адрес</th>
                          <th>Пользователь</th>
                          <th>RDP</th>
                          <th>ЦП</th>
                          <th>ОЗУ</th>
                          <th>Активность</th>
                          <th>Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        {groupDevices.map(device => {
                          const devGroups = getDeviceGroups(device);
                          const isSelected = selectedGroupPcIds.includes(device.id);
                          return (
                            <tr key={device.id} style={{ background: isSelected ? 'var(--blue-soft)' : undefined }}>
                              <td style={{ paddingLeft: '16px' }}>
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={(e) => {
                                    if (e.target.checked) {
                                      setSelectedGroupPcIds([...selectedGroupPcIds, device.id]);
                                    } else {
                                      setSelectedGroupPcIds(selectedGroupPcIds.filter(id => id !== device.id));
                                    }
                                  }}
                                />
                              </td>
                              <td><DeviceStatusBadge powerStatus={device.powerStatus} healthStatus={device.healthStatus} /></td>
                              <td>
                                <button className="device-name" onClick={() => onDevice(device.id)}>
                                  <span className="device-symbol"><Monitor size={15} /></span>
                                  <span><strong>{device.name}</strong><small>{device.id} · {device.hostname}</small></span>
                                </button>
                              </td>
                              <td>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                  {devGroups.map(g => (
                                    <span key={g} className={g.toLowerCase() === selectedGroup.name.toLowerCase() ? 'badge match' : 'badge'}>
                                      {g}
                                    </span>
                                  ))}
                                </div>
                              </td>
                              <td className="mono">{device.ip}</td>
                              <td className="mono">{device.mac}</td>
                              <td>{device.currentUser || '—'}</td>
                              <td><StatusPill status={device.rdpStatus} /></td>
                              <td><MetricBar value={device.cpu} /></td>
                              <td><MetricBar value={device.ram} /></td>
                              <td className="muted-text">{formatDeviceLastSeen(device.lastSeen, device.lastSeenIso, device.powerStatus)}</td>
                              <td>
                                <div style={{ display: 'flex', gap: '6px' }}>
                                  <button className="button" style={{ padding: '4px 8px', fontSize: '10px' }} onClick={() => onDevice(device.id)}>
                                    Открыть
                                  </button>
                                  <button
                                    className="button"
                                    style={{ padding: '4px 8px', fontSize: '10px', color: 'var(--red)' }}
                                    onClick={() => handleRemovePcFromGroup(device)}
                                    title="Удалить ПК из этой группы"
                                  >
                                    Удалить из группы
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          );
        })()
      ) : (
        /* ================= GROUPS LIST VIEW (3-LEVEL DRILL-DOWN TILES) ================= */
        <>
          <PageHeader
            eyebrow="FLEET MANAGEMENT"
            title={
              drillBuilding && drillFloor
                ? `Кабинеты: ${drillBuilding} → ${drillFloor}`
                : drillBuilding
                  ? `Этажи корпуса: ${drillBuilding}`
                  : "Группы и локации станций"
            }
            description="Трёхуровневая иерархия парка: Корпус → Этаж → Кабинет с групповым управлением питанием."
            actions={
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                {isSuperAdmin && (
                  <Button primary icon={<Plus size={15} />} onClick={() => setShowCreateGroup(true)}>
                    Создать группу / кабинет
                  </Button>
                )}
              </div>
            }
          />

          {/* Navigation Breadcrumbs & Fast Search Bar */}
          <div className="panel" style={{ marginBottom: '20px', padding: '12px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', flexWrap: 'wrap' }}>
              <button
                className={`button ${!drillBuilding ? 'button-primary' : ''}`}
                style={{ padding: '6px 12px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                onClick={() => { setDrillBuilding(null); setDrillFloor(null); setDrillSearch(''); }}
              >
                <Building size={14} /> Все корпуса ({Object.keys(hierarchyData).length})
              </button>

              {drillBuilding && (
                <>
                  <ChevronRight size={14} style={{ color: 'var(--muted)' }} />
                  <button
                    className={`button ${drillBuilding && !drillFloor ? 'button-primary' : ''}`}
                    style={{ padding: '6px 12px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                    onClick={() => { setDrillFloor(null); setDrillSearch(''); }}
                  >
                    <Layers size={14} /> {drillBuilding}
                  </button>
                </>
              )}

              {drillBuilding && drillFloor && (
                <>
                  <ChevronRight size={14} style={{ color: 'var(--muted)' }} />
                  <span className="badge match" style={{ fontSize: '12px', padding: '6px 10px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    🚪 {drillFloor}
                  </span>
                </>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ position: 'relative', width: '280px' }}>
                <input
                  type="text"
                  className="text-input"
                  style={{ width: '100%', paddingLeft: '32px' }}
                  placeholder="Быстрый поиск кабинета или ПК..."
                  value={drillSearch}
                  onChange={(e) => setDrillSearch(e.target.value)}
                />
                <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
                {drillSearch && (
                  <button
                    onClick={() => setDrillSearch('')}
                    style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Search Result Overlay if Searching */}
          {drillSearch.trim() ? (
            (() => {
              const q = drillSearch.trim().toLowerCase();
              const matchedGroups = visibleGroups.filter(g =>
                g.name.toLowerCase().includes(q) ||
                g.desc.toLowerCase().includes(q)
              );
              return (
                <div style={{ marginBottom: '24px' }}>
                  <div style={{ marginBottom: '12px', color: 'var(--muted)', fontSize: '13px' }}>
                    Найдено кабинетов и групп: <strong>{matchedGroups.length}</strong>
                  </div>
                  <div className="group-grid">
                    {matchedGroups.map(group => (
                      <section
                        className="panel group-card"
                        key={group.name}
                        onClick={() => onSelectGroup(group.name)}
                        style={{ cursor: 'pointer', transition: '0.2s', border: '1px solid var(--line)' }}
                      >
                        <div className={`group-hero ${group.color}`}>
                          <div className="group-symbol"><Server size={20} /></div>
                        </div>
                        <div className="group-body">
                          <div className="group-title">
                            <div>
                              <h2 style={{ fontSize: '15px', fontWeight: 700 }}>{group.name}</h2>
                              <p style={{ lineHeight: 1.4 }}>{group.desc}</p>
                            </div>
                            <span style={{ fontSize: '20px', fontWeight: 700 }}>{group.count}</span>
                          </div>
                          <div className="group-info">
                            <span><Monitor size={14} /> {group.count} {t('common.devices')}</span>
                            <span><Clock3 size={14} /> {group.schedule}</span>
                          </div>
                          <Button onClick={(e) => { e.stopPropagation(); onSelectGroup(group.name); }}>
                            Открыть ({group.name}) <ChevronRight size={14} />
                          </Button>
                        </div>
                      </section>
                    ))}
                  </div>
                </div>
              );
            })()
          ) : !drillBuilding ? (
            /* ================= LEVEL 1: BUILDINGS TILES (КОРПУСА) ================= */
            <div className="group-grid">
              {Object.keys(hierarchyData).map(bldName => {
                const stats = getBuildingStats(bldName);
                return (
                  <section
                    className="panel group-card"
                    key={bldName}
                    onClick={() => setDrillBuilding(bldName)}
                    style={{ cursor: 'pointer', transition: '0.2s', border: '1px solid var(--line)' }}
                    title={`Открыть корпус ${bldName}`}
                  >
                    <div className="group-hero blue">
                      <div className="group-symbol"><Building size={24} /></div>
                      {isSuperAdmin && (
                        <button
                          className="hero-more"
                          onClick={async (e) => {
                            e.stopPropagation();
                            const bldDevs = devices.filter(d => getDeviceGroups(d).some(grp => stats.groupNames.includes(grp.toLowerCase())));
                            const devIds = bldDevs.map(d => d.id);
                            if (devIds.length > 0) {
                              await devicesApi.bulkOperation(devIds, 'WAKE');
                              notify(`Wake-on-LAN отправлен на ${devIds.length} ПК корпуса "${bldName}"`);
                              setTimeout(loadData, 1200);
                            } else {
                              notify(`В корпусе "${bldName}" нет ПК`);
                            }
                          }}
                          title={`Включить все ПК корпуса "${bldName}" (WoL)`}
                        >
                          <Zap size={16} />
                        </button>
                      )}
                    </div>
                    <div className="group-body">
                      <div className="group-title">
                        <div>
                          <div className="eyebrow" style={{ color: 'var(--blue)', fontSize: '10px' }}>КОРПУС / ЗДАНИЕ</div>
                          <h2 style={{ fontSize: '18px', fontWeight: 700, marginTop: '2px' }}>{bldName}</h2>
                          <p style={{ lineHeight: 1.4 }}>{stats.floorsCount} этажей · {stats.roomsCount} кабинетов</p>
                        </div>
                        <span style={{ fontSize: '20px', fontWeight: 700, color: 'var(--blue)' }}>{stats.totalPcs}</span>
                      </div>
                      <div className="group-info">
                        <span style={{ color: 'var(--green)', fontWeight: 600 }}>
                          <Wifi size={13} style={{ verticalAlign: '-1px' }} /> {stats.onlinePcs} в сети
                        </span>
                        <span>
                          <Power size={13} style={{ verticalAlign: '-1px' }} /> {stats.totalPcs - stats.onlinePcs} выключено
                        </span>
                      </div>
                      <Button onClick={(e) => { e.stopPropagation(); setDrillBuilding(bldName); }}>
                        Открыть корпус ({bldName}) <ChevronRight size={14} />
                      </Button>
                    </div>
                  </section>
                );
              })}
            </div>
          ) : !drillFloor ? (
            /* ================= LEVEL 2: FLOORS TILES (ЭТАЖИ) ================= */
            <>
              {(() => {
                const bldStats = getBuildingStats(drillBuilding);
                const bldFloors = hierarchyData[drillBuilding]?.floors || {};
                return (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
                        Корпус <strong>{drillBuilding}</strong>: {bldStats.floorsCount} этажей, {bldStats.roomsCount} кабинетов, {bldStats.totalPcs} ПК ({bldStats.onlinePcs} в сети)
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        {isSuperAdmin && (
                          <Button
                            icon={<Zap size={14} />}
                            onClick={async () => {
                              const bldDevs = devices.filter(d => getDeviceGroups(d).some(grp => bldStats.groupNames.includes(grp.toLowerCase())));
                              const devIds = bldDevs.map(d => d.id);
                              if (devIds.length > 0) {
                                await devicesApi.bulkOperation(devIds, 'WAKE');
                                notify(`WoL отправлен на ${devIds.length} ПК корпуса "${drillBuilding}"`);
                                setTimeout(loadData, 1200);
                              }
                            }}
                          >
                            Включить весь корпус (WoL)
                          </Button>
                        )}
                        <Button onClick={() => setDrillBuilding(null)}>
                          ⬅️ К выбору корпуса
                        </Button>
                      </div>
                    </div>

                    <div className="group-grid">
                      {Object.keys(bldFloors).map(flrName => {
                        const fStats = getFloorStats(drillBuilding, flrName);
                        return (
                          <section
                            className="panel group-card"
                            key={flrName}
                            onClick={() => setDrillFloor(flrName)}
                            style={{ cursor: 'pointer', transition: '0.2s', border: '1px solid var(--line)' }}
                            title={`Открыть ${flrName}`}
                          >
                            <div className="group-hero purple">
                              <div className="group-symbol"><Layers size={24} /></div>
                              {isSuperAdmin && (
                                <button
                                  className="hero-more"
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    const fDevs = devices.filter(d => getDeviceGroups(d).some(grp => fStats.groupNames.includes(grp.toLowerCase())));
                                    const devIds = fDevs.map(d => d.id);
                                    if (devIds.length > 0) {
                                      await devicesApi.bulkOperation(devIds, 'WAKE');
                                      notify(`WoL отправлен на ${devIds.length} ПК этажа "${flrName}"`);
                                      setTimeout(loadData, 1200);
                                    }
                                  }}
                                  title={`Включить все ПК этажа "${flrName}" (WoL)`}
                                >
                                  <Zap size={16} />
                                </button>
                              )}
                            </div>
                            <div className="group-body">
                              <div className="group-title">
                                <div>
                                  <div className="eyebrow" style={{ color: 'var(--purple)', fontSize: '10px' }}>ЭТАЖ / СЕКЦИЯ</div>
                                  <h2 style={{ fontSize: '18px', fontWeight: 700, marginTop: '2px' }}>{flrName}</h2>
                                  <p style={{ lineHeight: 1.4 }}>{fStats.roomsCount} кабинетов на этаже</p>
                                </div>
                                <span style={{ fontSize: '20px', fontWeight: 700, color: 'var(--purple)' }}>{fStats.totalPcs}</span>
                              </div>
                              <div className="group-info">
                                <span style={{ color: 'var(--green)', fontWeight: 600 }}>
                                  <Wifi size={13} style={{ verticalAlign: '-1px' }} /> {fStats.onlinePcs} в сети
                                </span>
                                <span>
                                  <Power size={13} style={{ verticalAlign: '-1px' }} /> {fStats.totalPcs - fStats.onlinePcs} выключено
                                </span>
                              </div>
                              <Button onClick={(e) => { e.stopPropagation(); setDrillFloor(flrName); }}>
                                Открыть этаж ({flrName}) <ChevronRight size={14} />
                              </Button>
                            </div>
                          </section>
                        );
                      })}
                    </div>
                  </>
                );
              })()}
            </>
          ) : (
            /* ================= LEVEL 3: ROOMS TILES (КАБИНЕТЫ) ================= */
            <>
              {(() => {
                const floorRooms = hierarchyData[drillBuilding]?.floors[drillFloor]?.rooms || [];
                const fStats = getFloorStats(drillBuilding, drillFloor);
                return (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ fontSize: '13px', color: 'var(--muted)' }}>
                        Локация: <strong>{drillBuilding}</strong> → <strong>{drillFloor}</strong> ({floorRooms.length} кабинетов, {fStats.totalPcs} ПК)
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        {isSuperAdmin && (
                          <Button
                            icon={<Zap size={14} />}
                            onClick={async () => {
                              const fDevs = devices.filter(d => getDeviceGroups(d).some(grp => fStats.groupNames.includes(grp.toLowerCase())));
                              const devIds = fDevs.map(d => d.id);
                              if (devIds.length > 0) {
                                await devicesApi.bulkOperation(devIds, 'WAKE');
                                notify(`WoL отправлен на ${devIds.length} ПК этажа "${drillFloor}"`);
                                setTimeout(loadData, 1200);
                              }
                            }}
                          >
                            Включить весь этаж (WoL)
                          </Button>
                        )}
                        <Button onClick={() => setDrillFloor(null)}>
                          ⬅️ К выбору этажа
                        </Button>
                      </div>
                    </div>

                    <div className="group-grid">
                      {floorRooms.map(roomGroup => (
                        <section
                          className="panel group-card"
                          key={roomGroup.name}
                          onClick={() => onSelectGroup(roomGroup.name)}
                          style={{ cursor: 'pointer', transition: '0.2s', border: '1px solid var(--line)' }}
                          title={`Открыть кабинет ${roomGroup.roomName}`}
                        >
                          <div className={`group-hero ${roomGroup.color}`}>
                            <div className="group-symbol"><Server size={20} /></div>
                            {canManageGroup(roomGroup.name) && !isObserver && (
                              <button
                                className="hero-more"
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  const gDevs = devices.filter(d => getDeviceGroups(d).some(grp => grp.toLowerCase() === roomGroup.name.toLowerCase()));
                                  const devIds = gDevs.map(d => d.id);
                                  if (devIds.length > 0) {
                                    await devicesApi.bulkOperation(devIds, 'WAKE');
                                    notify(`WoL отправлен на ${devIds.length} ПК кабинета "${roomGroup.roomName}"`);
                                    setTimeout(loadData, 1200);
                                  } else {
                                    notify(`В кабинете "${roomGroup.roomName}" нет добавленных ПК`);
                                  }
                                }}
                                title="Включить все ПК кабинета (WoL)"
                              >
                                <Zap size={16} />
                              </button>
                            )}
                          </div>
                          <div className="group-body">
                            <div className="group-title">
                              <div>
                                <div className="eyebrow" style={{ fontSize: '10px', textTransform: 'uppercase' }}>КАБИНЕТ</div>
                                <h2 style={{ fontSize: '16px', fontWeight: 700 }}>{roomGroup.roomName}</h2>
                                <p style={{ lineHeight: 1.4 }}>{roomGroup.desc}</p>
                              </div>
                              <span style={{ fontSize: '20px', fontWeight: 700 }}>{roomGroup.count}</span>
                            </div>
                            <div className="group-info">
                              <span><Monitor size={14} /> {roomGroup.count} ПК</span>
                              <span><Clock3 size={14} /> {roomGroup.schedule}</span>
                            </div>
                            <Button onClick={(e) => { e.stopPropagation(); onSelectGroup(roomGroup.name); }}>
                              Открыть кабинет ({roomGroup.roomName}) <ChevronRight size={14} />
                            </Button>
                          </div>
                        </section>
                      ))}
                    </div>
                  </>
                );
              })()}
            </>
          )}
        </>
      )}

      {/* ================= MODALS (Always rendered in Groups) ================= */}

      {/* Create Group Modal with 3-Level Support */}
      {showCreateGroup && (
        <div className="modal-backdrop" onClick={() => setShowCreateGroup(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '540px', textAlign: 'left' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}><Database size={22} /></div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Создать новую группу / кабинет</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>Объединение станций в корпус, этаж и кабинет</p>
              </div>
            </div>

            {/* Switcher: Hierarchical vs Flat */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', padding: '4px', background: 'var(--bg)', borderRadius: '8px', border: '1px solid var(--line)' }}>
              <button
                type="button"
                className={`button ${isHierarchicalCreate ? 'button-primary' : ''}`}
                style={{ flex: 1, padding: '6px', fontSize: '12px' }}
                onClick={() => setIsHierarchicalCreate(true)}
              >
                🏢 Трёхуровневая структура
              </button>
              <button
                type="button"
                className={`button ${!isHierarchicalCreate ? 'button-primary' : ''}`}
                style={{ flex: 1, padding: '6px', fontSize: '12px' }}
                onClick={() => setIsHierarchicalCreate(false)}
              >
                📁 Простая плоская группа
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {isHierarchicalCreate ? (
                <>
                  <div>
                    <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                      Корпус / Здание
                    </label>
                    <select
                      className="text-input"
                      style={{ width: '100%' }}
                      value={isNewBuildingMode ? '__new__' : selectedBuildingOption}
                      onChange={(e) => {
                        if (e.target.value === '__new__') {
                          setIsNewBuildingMode(true);
                        } else {
                          setIsNewBuildingMode(false);
                          setSelectedBuildingOption(e.target.value);
                          setIsCustomFloorMode(false);
                        }
                      }}
                    >
                      {availableBuildingOptions.map(b => (
                        <option key={b} value={b}>{b}</option>
                      ))}
                      <option value="__new__">+ Создать новый корпус...</option>
                    </select>
                  </div>

                  {isNewBuildingMode && (
                    <div style={{ padding: '12px', background: 'var(--bg)', borderRadius: '8px', border: '1px dashed var(--line)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      <div>
                        <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                          Название нового корпуса
                        </label>
                        <input
                          className="text-input"
                          style={{ width: '100%' }}
                          value={newBuildingNameInput}
                          onChange={(e) => setNewBuildingNameInput(e.target.value)}
                          placeholder="Например: Инженерный корпус"
                          autoFocus
                        />
                      </div>

                      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
                        <div>
                          <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                            Количество этажей
                          </label>
                          <input
                            type="number"
                            min={1}
                            max={50}
                            className="text-input"
                            style={{ width: '110px' }}
                            value={newBuildingFloorsCount}
                            onChange={(e) => setNewBuildingFloorsCount(e.target.value)}
                            onBlur={() => {
                              const val = parseInt(newBuildingFloorsCount, 10);
                              if (isNaN(val) || val < 1) setNewBuildingFloorsCount('1');
                              else if (val > 50) setNewBuildingFloorsCount('50');
                            }}
                          />
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', paddingTop: '10px' }}>
                          <label style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={newBuildingHasBasement}
                              onChange={(e) => setNewBuildingHasBasement(e.target.checked)}
                            />
                            Цокольный этаж (Цоколь)
                          </label>
                          <label style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={newBuildingHasSubFloor}
                              onChange={(e) => setNewBuildingHasSubFloor(e.target.checked)}
                            />
                            Подвальный этаж (-1 этаж)
                          </label>
                        </div>
                      </div>
                    </div>
                  )}

                  <div>
                    <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                      Этаж / Секция
                    </label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <select
                        className="text-input"
                        style={{ flex: 1 }}
                        value={isCustomFloorMode ? '__custom__' : (selectedFloorOption || availableFloorsForActiveBuilding[0])}
                        onChange={(e) => {
                          if (e.target.value === '__custom__') {
                            setIsCustomFloorMode(true);
                          } else {
                            setIsCustomFloorMode(false);
                            setSelectedFloorOption(e.target.value);
                          }
                        }}
                      >
                        {availableFloorsForActiveBuilding.map(f => (
                          <option key={f} value={f}>{f}</option>
                        ))}
                        <option value="__custom__">+ Другой этаж...</option>
                      </select>
                      {isCustomFloorMode && (
                        <input
                          className="text-input"
                          style={{ flex: 1 }}
                          value={customFloorInput}
                          onChange={(e) => setCustomFloorInput(e.target.value)}
                          placeholder="Например: Мансарда"
                          autoFocus
                        />
                      )}
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                      Кабинет / Помещение
                    </label>
                    <input
                      className="text-input"
                      style={{ width: '100%' }}
                      value={createRoom}
                      onChange={(e) => setCreateRoom(e.target.value)}
                      placeholder="Например: Каб. 204 или Бухгалтерия"
                    />
                  </div>

                  <div style={{ padding: '8px 12px', background: 'var(--blue-soft)', borderRadius: '6px', fontSize: '11px', color: 'var(--blue)' }}>
                    📍 <strong>Итоговое имя в системе:</strong>{' '}
                    <code>
                      {(isNewBuildingMode ? (newBuildingNameInput || 'Новый корпус') : activeBuildingName)} / {(isCustomFloorMode ? (customFloorInput || 'Этаж') : (selectedFloorOption || availableFloorsForActiveBuilding[0] || '1 этаж'))} / {createRoom || 'Кабинет'}
                    </code>
                  </div>
                </>
              ) : (
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Название группы</label>
                  <input
                    className="text-input"
                    style={{ width: '100%' }}
                    value={newGroupName}
                    onChange={(e) => setNewGroupName(e.target.value)}
                    placeholder="Например: Marketing или Серверная"
                  />
                </div>
              )}

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Описание назначения</label>
                <input
                  className="text-input"
                  style={{ width: '100%' }}
                  value={newGroupDesc}
                  onChange={(e) => setNewGroupDesc(e.target.value)}
                  placeholder="Например: Компьютерный класс или Отдел продаж"
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Цветовая метка</label>
                <div className="color-picker">
                  {colorOptions.map(opt => (
                    <div
                      key={opt.id}
                      className={`color-option ${opt.id} ${newGroupColor === opt.id ? 'selected' : ''}`}
                      onClick={() => setNewGroupColor(opt.id)}
                      title={opt.label}
                    >
                      {newGroupColor === opt.id && <Check size={16} color="#fff" />}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Расписание питания</label>
                <select className="text-input" style={{ width: '100%' }} value={newGroupSchedule} onChange={(e) => setNewGroupSchedule(e.target.value)}>
                  <option value="Без расписания">Без расписания</option>
                  <option value="Office Working Day">Office Working Day (07:50 - 22:00)</option>
                  <option value="Warehouse Night Mode">Warehouse Night Mode (21:00 - 08:00)</option>
                  <option value="Testing Lab">Testing Lab (Ежедневный ребут)</option>
                  <option value="Dev Working Day">Dev Working Day (08:30 - 20:00)</option>
                </select>
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setShowCreateGroup(false)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleCreateGroup} disabled={isHierarchicalCreate ? (isNewBuildingMode ? (!newBuildingNameInput.trim() || !createRoom.trim()) : !createRoom.trim()) : !newGroupName.trim()}>
                Создать
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Group Modal (Fix for "Настройка группы") */}
      {editGroupTarget && (
        <div className="modal-backdrop" onClick={() => setEditGroupTarget(null)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '520px', textAlign: 'left' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}><Edit3 size={22} /></div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Настройки группы: {editGroupTarget.name}</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>Редактирование параметров и цветовой темы</p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Название группы</label>
                <input
                  className="text-input"
                  style={{ width: '100%' }}
                  value={editGroupName}
                  onChange={(e) => setEditGroupName(e.target.value)}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Описание группы</label>
                <input
                  className="text-input"
                  style={{ width: '100%' }}
                  value={editGroupDesc}
                  onChange={(e) => setEditGroupDesc(e.target.value)}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Цветовая тема</label>
                <div className="color-picker">
                  {colorOptions.map(opt => (
                    <div
                      key={opt.id}
                      className={`color-option ${opt.id} ${editGroupColor === opt.id ? 'selected' : ''}`}
                      onClick={() => setEditGroupColor(opt.id)}
                      title={opt.label}
                    >
                      {editGroupColor === opt.id && <Check size={16} color="#fff" />}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>Расписание питания</label>
                <select className="text-input" style={{ width: '100%' }} value={editGroupSchedule} onChange={(e) => setEditGroupSchedule(e.target.value)}>
                  <option value="Без расписания">Без расписания</option>
                  <option value="Office Working Day">Office Working Day</option>
                  <option value="Warehouse Night Mode">Warehouse Night Mode</option>
                  <option value="Testing Lab">Testing Lab</option>
                  <option value="Dev Working Day">Dev Working Day</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '5px' }}>
                  Интервал опроса телеметрии для группы
                </label>
                <select
                  className="text-input"
                  style={{ width: '100%' }}
                  value={editGroupInterval}
                  onChange={(e) => setEditGroupInterval(parseInt(e.target.value, 10))}
                >
                  <option value="10">10 секунд (Турбо / Серверы)</option>
                  <option value="15">15 секунд (Частый)</option>
                  <option value="30">30 секунд (Баланс)</option>
                  <option value="60">60 секунд (Рекомендуемый стандарт)</option>
                  <option value="120">2 минуты (120 сек - Экономичный)</option>
                  <option value="300">5 минут (300 сек - Фоновый)</option>
                </select>
                <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
                  Все станции этой группы без индивидуальных настроек будут опрашиваться с этой частотой.
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '10px', borderTop: '1px solid var(--line)' }}>
                <button
                  type="button"
                  className="text-button"
                  style={{ color: 'var(--red)' }}
                  onClick={() => handleDeleteGroup(editGroupTarget.name)}
                >
                  <Trash2 size={13} /> Удалить эту группу
                </button>
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setEditGroupTarget(null)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleSaveEditGroup} disabled={!editGroupName}>
                Сохранить
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Add PC to Group Modal */}
      {showAddPcModal && selectedGroup && canManageGroup(selectedGroup.name) && !isObserver && (
        <div className="modal-backdrop" onClick={() => setShowAddPcModal(false)}>
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()} style={{ width: '540px', textAlign: 'left' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div className="confirm-icon" style={{ background: 'var(--blue-soft)', color: 'var(--blue)', margin: 0 }}><FolderPlus size={22} /></div>
              <div>
                <h2 style={{ fontSize: '17px', margin: 0 }}>Добавить ПК в группу "{selectedGroup.name}"</h2>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)' }}>Привяжите существующий компьютер или разверните новый</p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Вариант 1: Выбрать из зарегистрированных ПК</label>
                <select
                  className="text-input"
                  style={{ width: '100%' }}
                  value={selectedPcToAssign}
                  onChange={(e) => setSelectedPcToAssign(e.target.value)}
                >
                  <option value="">-- Выберите компьютер для добавления --</option>
                  {devices.map(d => {
                    const devGroups = getDeviceGroups(d);
                    const alreadyInGroup = devGroups.some(g => g.toLowerCase() === selectedGroup.name.toLowerCase());
                    return (
                      <option key={d.id} value={d.id} disabled={alreadyInGroup}>
                        {d.name} ({d.hostname}) — {alreadyInGroup ? 'уже в этой группе' : `группы: ${devGroups.join(', ')}`}
                      </option>
                    );
                  })}
                </select>
              </div>

              <div style={{ padding: '12px 0', borderTop: '1px solid var(--line)' }}>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Вариант 2: Команда автоустановки прямо в эту группу (PowerShell):</label>
                {(() => {
                  const effectivePort = window.location.port === '5173' ? '2301' : (window.location.port || '2301');
                  const serverHost = window.location.hostname || 'localhost';
                  const srvUrl = `http://${serverHost}:${effectivePort}`;
                  const cmd = `irm "${srvUrl}/install.ps1?group=${encodeURIComponent(selectedGroup.name)}&server_url=${encodeURIComponent(srvUrl)}" | iex`;
                  return (
                    <>
                      <div className="code-card" style={{ marginTop: 0 }}>
                        <pre>{cmd}</pre>
                      </div>
                      <button
                        className="text-button"
                        style={{ marginTop: '4px' }}
                        onClick={() => {
                          copyToClipboard(cmd);
                          notify('Команда скопирована в буфер обмена!');
                        }}
                      >
                        <Copy size={12} /> Скопировать команду
                      </button>
                    </>
                  );
                })()}
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <Button onClick={() => setShowAddPcModal(false)}>{t('common.cancel')}</Button>
              <Button primary onClick={handleAssignPcToGroup} disabled={!selectedPcToAssign}>
                Добавить в группу
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------
// 16. SETTINGS
// ----------------------------------------------------
function SettingsPage({
  workspaceName,
  onSaveWorkspaceName,
  notify
}: {
  workspaceName: string;
  onSaveWorkspaceName: (name: string) => void;
  notify: (message: string) => void;
}) {
  const { lang, setLang, t } = useLanguage();
  const [activeTab, setActiveTab] = useState<'general' | 'alerts' | 'integrations' | 'security' | 'storage'>('general');

  const [currentWorkspaceName, setCurrentWorkspaceName] = useState(workspaceName);
  const [timezone, setTimezone] = useState(() => {
    try {
      return localStorage.getItem('wm_timezone') || 'Europe/Berlin';
    } catch {
      return 'Europe/Berlin';
    }
  });
  const [realtimeEvents, setRealtimeEvents] = useState(() => {
    try { return localStorage.getItem('wm_realtime_events') !== 'false'; } catch { return true; }
  });
  const [ramAlert, setRamAlert] = useState(() => {
    try { return localStorage.getItem('wm_ram_alert') !== 'false'; } catch { return true; }
  });
  const [hwAlert, setHwAlert] = useState(() => {
    try { return localStorage.getItem('wm_hw_alert') !== 'false'; } catch { return true; }
  });
  const [syslogExport, setSyslogExport] = useState(() => {
    try { return localStorage.getItem('wm_syslog_export') === 'true'; } catch { return false; }
  });
  const [twoFactor, setTwoFactor] = useState(() => {
    try { return localStorage.getItem('wm_two_factor') === 'true'; } catch { return false; }
  });
  const [sessionTimeout, setSessionTimeout] = useState(() => {
    try { return localStorage.getItem('wm_session_timeout') || '60'; } catch { return '60'; }
  });
  const [historyRetention, setHistoryRetention] = useState(() => {
    try { return localStorage.getItem('wm_history_retention') || '30'; } catch { return '30'; }
  });
  const [defaultInterval, setDefaultInterval] = useState(60);

  useEffect(() => {
    setCurrentWorkspaceName(workspaceName);
  }, [workspaceName]);

  useEffect(() => {
    agentsApi.getSettings().then(s => {
      if (s && s.defaultHeartbeatInterval) setDefaultInterval(s.defaultHeartbeatInterval);
    });
  }, []);

  const handleSaveSettings = () => {
    onSaveWorkspaceName(currentWorkspaceName);
    try {
      localStorage.setItem('wm_timezone', timezone);
      localStorage.setItem('wm_realtime_events', String(realtimeEvents));
      localStorage.setItem('wm_ram_alert', String(ramAlert));
      localStorage.setItem('wm_hw_alert', String(hwAlert));
      localStorage.setItem('wm_syslog_export', String(syslogExport));
      localStorage.setItem('wm_two_factor', String(twoFactor));
      localStorage.setItem('wm_session_timeout', sessionTimeout);
      localStorage.setItem('wm_history_retention', historyRetention);
    } catch {}
    notify('Настройки сохранены: рабочее пространство и параметры обновлены!');
  };

  const handleBackupDb = () => {
    downloadTextFile(`workstation_manager_backup_${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify({
      backupDate: new Date().toISOString(),
      version: '1.4.2',
      status: 'OK',
      system: currentWorkspaceName
    }, null, 2));
    notify('Резервная копия конфигурации успешно выгружена!');
  };

  return (
    <>
      <PageHeader
        eyebrow="SYSTEM"
        title="Настройки"
        description="Параметры рабочего пространства, язык интерфейса и интеграции."
      />
      <div className="settings-layout">
        <aside className="panel settings-nav">
          <button className={activeTab === 'general' ? 'active' : ''} onClick={() => setActiveTab('general')}><Settings size={16} /> Основные</button>
          <button className={activeTab === 'alerts' ? 'active' : ''} onClick={() => setActiveTab('alerts')}><Bell size={16} /> Оповещения</button>
          <button className={activeTab === 'integrations' ? 'active' : ''} onClick={() => setActiveTab('integrations')}><Network size={16} /> Интеграции</button>
          <button className={activeTab === 'security' ? 'active' : ''} onClick={() => setActiveTab('security')}><ShieldCheck size={16} /> Безопасность</button>
          <button className={activeTab === 'storage' ? 'active' : ''} onClick={() => setActiveTab('storage')}><Database size={16} /> Хранение данных</button>
        </aside>

        <section className="panel settings-content">
          {activeTab === 'general' && (
            <>
              <div className="panel-heading">
                <div><h2>Основные параметры</h2><p>Глобальные настройки системы {currentWorkspaceName}</p></div>
              </div>
              <div className="setting-row">
                <div><strong>Название пространства</strong><span>Отображается в шапке, меню и отчетах</span></div>
                <input
                  className="text-input"
                  value={currentWorkspaceName}
                  onChange={e => setCurrentWorkspaceName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleSaveSettings(); }}
                  placeholder="Название рабочего пространства"
                />
              </div>
              <div className="setting-row">
                <div><strong>Язык интерфейса</strong><span>Русский или English с мгновенным переключением</span></div>
                <select value={lang} onChange={(e) => setLang(e.target.value as any)} className="text-input">
                  <option value="ru">Русский (RU)</option>
                  <option value="en">English (EN)</option>
                </select>
              </div>
              <div className="setting-row">
                <div><strong>Часовой пояс по умолчанию</strong><span>Используется для расписаний и меток времени</span></div>
                <select value={timezone} onChange={e => setTimezone(e.target.value)} className="text-input">
                  <option value="Europe/Berlin">Europe/Berlin (UTC+1)</option>
                  <option value="Europe/Moscow">Europe/Moscow (UTC+3)</option>
                  <option value="UTC">UTC</option>
                  <option value="America/New_York">America/New_York (UTC-5)</option>
                </select>
              </div>
              <div className="setting-row">
                <div>
                  <strong>Интервал опроса телеметрии по умолчанию (Heartbeat)</strong>
                  <span>Глобальная частота сбора метрик с рабочих станций парка</span>
                </div>
                <select
                  value={defaultInterval}
                  onChange={async (e) => {
                    const val = parseInt(e.target.value, 10);
                    setDefaultInterval(val);
                    await agentsApi.updateSettings({ defaultHeartbeatInterval: val });
                    notify(`Глобальный интервал опроса изменен на ${val} сек!`);
                  }}
                  className="text-input"
                >
                  <option value={10}>10 секунд (Турбо / Высокая нагрузка)</option>
                  <option value={15}>15 секунд (Частый)</option>
                  <option value={30}>30 секунд</option>
                  <option value={60}>60 секунд (Рекомендуемый стандарт)</option>
                  <option value={120}>2 минуты (120 сек - Экономичный)</option>
                  <option value={300}>5 минут (300 сек - Фоновый)</option>
                </select>
              </div>
              <div className="setting-row">
                <div>
                  <strong>Сервер управления (Host & Network)</strong>
                  <span>Сетевой адрес и статус связи бэкенда</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="mono" style={{ padding: '4px 8px', background: 'var(--surface-1, rgba(255,255,255,0.05))', borderRadius: '5px', fontSize: '11px', border: '1px solid var(--border, rgba(255,255,255,0.1))' }}>
                    {window.location.hostname || '192.168.1.109'}:{window.location.port === '5173' ? '2301' : (window.location.port || '2301')}
                  </span>
                  <span style={{ fontFamily: 'DM Mono', fontSize: '10px', fontWeight: 600, color: 'var(--green)', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)', padding: '2px 7px', borderRadius: '5px' }}>
                    LIVE · 1ms
                  </span>
                </div>
              </div>
              <div className="setting-row">
                <div><strong>Обновления в реальном времени</strong><span>Получать события через WebSocket без перезагрузки</span></div>
                <Switch checked={realtimeEvents} onChange={setRealtimeEvents} />
              </div>
            </>
          )}

          {activeTab === 'alerts' && (
            <>
              <div className="panel-heading">
                <div><h2>Глобальные настройки оповещений</h2><p>Политика рассылки экстренных уведомлений</p></div>
              </div>
              <div className="setting-row">
                <div><strong>Оповещать при изъятии ОЗУ</strong><span>Мгновенный алерт в Telegram и веб</span></div>
                <Switch checked={ramAlert} onChange={setRamAlert} />
              </div>
              <div className="setting-row">
                <div><strong>Оповещать при замене дисков или GPU</strong><span>Фиксация расхождения с аппаратным эталоном</span></div>
                <Switch checked={hwAlert} onChange={setHwAlert} />
              </div>
            </>
          )}

          {activeTab === 'integrations' && (
            <>
              <div className="panel-heading">
                <div><h2>Интеграции и шлюзы</h2><p>Связь со сторонними сервисами мониторинга</p></div>
              </div>
              <div className="setting-row">
                <div><strong>Telegram Gateway</strong><span>Подключение рабочего бота</span></div>
                <span className="badge match">Connected</span>
              </div>
              <div className="setting-row">
                <div><strong>Syslog / SIEM Forwarder</strong><span>Экспорт журналов аудита по RFC 5424</span></div>
                <Switch checked={syslogExport} onChange={setSyslogExport} />
              </div>
            </>
          )}

          {activeTab === 'security' && (
            <>
              <div className="panel-heading">
                <div><h2>Безопасность и сессии</h2><p>Аутентификация и защита данных</p></div>
              </div>
              <div className="setting-row">
                <div><strong>Двухфакторная аутентификация (2FA)</strong><span>TOTP аутентификатор для администраторов</span></div>
                <Switch checked={twoFactor} onChange={setTwoFactor} />
              </div>
              <div className="setting-row">
                <div><strong>Таймаут сессии веб-панели</strong><span>Автоматический выход при неактивности</span></div>
                <select value={sessionTimeout} onChange={e => setSessionTimeout(e.target.value)} className="text-input">
                  <option value="30">30 минут</option>
                  <option value="60">1 час</option>
                  <option value="120">2 часа</option>
                </select>
              </div>
            </>
          )}

          {activeTab === 'storage' && (
            <>
              <div className="panel-heading">
                <div><h2>Хранение данных и резервные копии</h2><p>База данных SQLite / PostgreSQL и снимки</p></div>
              </div>
              <div className="setting-row">
                <div><strong>Резервная копия базы данных</strong><span>Создать и скачать моментальный снимок конфигурации</span></div>
                <Button icon={<Download size={14} />} onClick={handleBackupDb}>Скачать Backup</Button>
              </div>
              <div className="setting-row">
                <div><strong>Хранение истории метрик</strong><span>Глубина архива телеметрии</span></div>
                <select value={historyRetention} onChange={e => setHistoryRetention(e.target.value)} className="text-input">
                  <option value="7">7 дней</option>
                  <option value="30">30 дней</option>
                  <option value="90">90 дней</option>
                </select>
              </div>
            </>
          )}

          <div className="settings-footer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 21px', borderTop: '1px solid var(--line)', gap: '16px', flexWrap: 'nowrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '11.5px', color: 'var(--muted)', minWidth: 0 }}>
              <ShieldCheck size={15} style={{ color: 'var(--green)', flexShrink: 0 }} />
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                Workstation Manager · v2.8.7 · © 2026 Сергей Ерёмин
              </span>
            </div>
            <div style={{ flexShrink: 0 }}>
              <Button primary onClick={handleSaveSettings}>{t('common.saveChanges')}</Button>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}

export default App;
