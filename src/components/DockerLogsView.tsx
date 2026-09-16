import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Terminal, Play, Pause, RefreshCw, Download, Copy, Trash2, Search,
  Filter, Check, AlertCircle, AlertTriangle, Info, Clock, Server, ArrowDown,
  Layers, ArrowDownToLine, Cpu, Calendar, X
} from 'lucide-react';
import { systemApi } from '@/api';

interface LogEntry {
  id?: string | number;
  timestamp: string;
  level: string;
  stream: string;
  message: string;
  raw: string;
}

interface ContainerInfo {
  id: string;
  name: string;
  role: string;
  isDefault: boolean;
  status?: string;
}

interface DockerLogsViewProps {
  currentUser: any;
  notify: (message: string, type?: 'success' | 'error' | 'warning' | 'info') => void;
}

export const DockerLogsView: React.FC<DockerLogsViewProps> = ({ currentUser, notify }) => {
  const [containers, setContainers] = useState<ContainerInfo[]>([
    { id: 'workstation-manager', name: 'workstation-manager', role: 'Основной контейнер приложения (FastAPI, Планировщик, UI)', isDefault: true },
    { id: 'workstation-manager-postgres', name: 'workstation-manager-postgres', role: 'База данных PostgreSQL', isDefault: false }
  ]);
  const [selectedContainer, setSelectedContainer] = useState<string>('workstation-manager');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [levelFilter, setLevelFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [tailCount, setTailCount] = useState<number>(500);
  const [datePreset, setDatePreset] = useState<'ALL' | '15M' | '1H' | 'TODAY' | 'CUSTOM'>('ALL');
  const [customSince, setCustomSince] = useState<string>('');
  const [customUntil, setCustomUntil] = useState<string>('');
  const [showCustomRange, setShowCustomRange] = useState<boolean>(false);
  const [isLive, setIsLive] = useState<boolean>(true);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const terminalContainerRef = useRef<HTMLDivElement>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Load container list
  useEffect(() => {
    systemApi.getContainers()
      .then(res => {
        if (res && res.containers && res.containers.length > 0) {
          setContainers(res.containers);
        }
      })
      .catch(() => {});
  }, []);

  // Compute 'since' datetime based on datePreset
  const getSinceIso = useCallback((): string | undefined => {
    const now = new Date();
    if (datePreset === '15M') {
      return new Date(now.getTime() - 15 * 60 * 1000).toISOString();
    } else if (datePreset === '1H') {
      return new Date(now.getTime() - 60 * 60 * 1000).toISOString();
    } else if (datePreset === 'TODAY') {
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      return today.toISOString();
    } else if (datePreset === 'CUSTOM' && customSince) {
      try {
        return new Date(customSince).toISOString();
      } catch {
        return customSince;
      }
    }
    return undefined;
  }, [datePreset, customSince]);

  // Compute 'until' datetime based on custom range
  const getUntilIso = useCallback((): string | undefined => {
    if (datePreset === 'CUSTOM' && customUntil) {
      try {
        return new Date(customUntil).toISOString();
      } catch {
        return customUntil;
      }
    }
    return undefined;
  }, [datePreset, customUntil]);

  // Fetch logs
  const fetchLogs = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    try {
      const since = getSinceIso();
      const until = getUntilIso();
      const res = await systemApi.getLogs({
        container: selectedContainer,
        tail: tailCount,
        level: levelFilter !== 'ALL' ? levelFilter : undefined,
        search: searchQuery.trim() || undefined,
        since,
        until
      });
      if (res && Array.isArray(res.logs)) {
        setLogs(res.logs);
      }
    } catch (err: any) {
      if (showLoading) {
        notify(err.message || 'Ошибка загрузки логов', 'error');
      }
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [selectedContainer, tailCount, levelFilter, searchQuery, getSinceIso, getUntilIso, notify]);

  // Initial fetch and reload on parameter changes
  useEffect(() => {
    fetchLogs(true);
  }, [fetchLogs]);

  // Live polling (every 2.5 seconds when isLive is true and not in historical custom range)
  useEffect(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);

    if (isLive && datePreset !== 'CUSTOM') {
      pollingRef.current = setInterval(() => {
        fetchLogs(false);
      }, 2500);
    }

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [isLive, datePreset, fetchLogs]);

  // Auto-scroll to bottom when logs update
  useEffect(() => {
    if (autoScroll && terminalContainerRef.current) {
      terminalContainerRef.current.scrollTop = terminalContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Handle manual scroll to toggle auto-scroll
  const handleScroll = () => {
    if (!terminalContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = terminalContainerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 40;
    if (!atBottom && autoScroll) {
      setAutoScroll(false);
    } else if (atBottom && !autoScroll) {
      setAutoScroll(true);
    }
  };

  // Filter logs locally for instant feedback
  const filteredLogs = useMemo(() => {
    const since = getSinceIso();
    const until = getUntilIso();

    return logs.filter(entry => {
      // Level filter
      if (levelFilter !== 'ALL') {
        const lvl = entry.level.toUpperCase();
        if (levelFilter === 'ERROR' && lvl !== 'ERROR') return false;
        if (levelFilter === 'WARN' && !['WARN', 'WARNING', 'ERROR'].includes(lvl)) return false;
        if (levelFilter === 'INFO' && lvl !== 'INFO') return false;
        if (levelFilter === 'DEBUG' && lvl !== 'DEBUG') return false;
      }
      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchMsg = entry.message.toLowerCase().includes(q);
        const matchRaw = entry.raw.toLowerCase().includes(q);
        if (!matchMsg && !matchRaw) return false;
      }
      // Custom date range filter
      if (since && entry.timestamp < since) return false;
      if (until && entry.timestamp > until) return false;

      return true;
    });
  }, [logs, levelFilter, searchQuery, getSinceIso, getUntilIso]);

  // KPI counters
  const counts = useMemo(() => {
    let err = 0;
    let warn = 0;
    let info = 0;
    logs.forEach(l => {
      const lvl = l.level.toUpperCase();
      if (lvl === 'ERROR') err++;
      else if (lvl === 'WARN' || lvl === 'WARNING') warn++;
      else info++;
    });
    return { total: logs.length, err, warn, info };
  }, [logs]);

  // Download logs as .txt file
  const handleDownload = () => {
    const text = filteredLogs.map(l => l.raw || `${l.timestamp} [${l.level}] ${l.message}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${selectedContainer}-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    notify(`Лог (${filteredLogs.length} строк) успешно сохранен в файл`, 'success');
  };

  // Copy all visible logs to clipboard
  const handleCopyAll = () => {
    const text = filteredLogs.map(l => l.raw || `${l.timestamp} [${l.level}] ${l.message}`).join('\n');
    navigator.clipboard.writeText(text).then(() => {
      notify('Все отображаемые строки скопированы в буфер обмена', 'success');
    }).catch(() => {
      notify('Ошибка копирования в буфер обмена', 'error');
    });
  };

  // Copy single line
  const handleCopyLine = (text: string, index: number) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 1600);
    });
  };

  // Clear current view
  const handleClear = () => {
    setLogs([]);
    notify('Экран консоли очищен', 'info');
  };

  // Format log timestamp
  const formatTimestamp = (iso: string): string => {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso.split(' ')[0] || iso;
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
        '.' + String(d.getMilliseconds()).padStart(3, '0');
    } catch {
      return iso;
    }
  };

  return (
    <div className="docker-logs-page" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <span className="eyebrow" style={{ fontSize: '11px', letterSpacing: '1.2px', textTransform: 'uppercase', color: 'var(--blue)', fontWeight: 700 }}>
            DOCKER CONTAINER TELEMETRY & SYSTEM LOGS
          </span>
          <h1 style={{ fontSize: '24px', fontWeight: 800, margin: '4px 0 6px 0', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Terminal size={24} style={{ color: 'var(--blue)' }} /> Логи
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: '13px', color: 'var(--muted)' }}>
            Живой журнал работы контейнеров и сервисов в реальном времени с выборкой за период, фильтрацией и поиском.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Live stream toggle button */}
          <button
            className={`btn ${isLive ? 'primary' : ''}`}
            onClick={() => setIsLive(!isLive)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 14px',
              fontSize: '12px',
              background: isLive ? 'rgba(34, 197, 94, 0.15)' : 'var(--panel)',
              color: isLive ? '#22c55e' : 'var(--muted)',
              border: isLive ? '1px solid rgba(34, 197, 94, 0.4)' : '1px solid var(--line)',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: 600
            }}
            title={isLive ? 'Приостановить живой поток' : 'Возобновить прямой эфир'}
          >
            {isLive ? (
              <>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e', display: 'inline-block', boxShadow: '0 0 8px #22c55e' }} />
                Прямой эфир (Live)
              </>
            ) : (
              <>
                <Pause size={13} />
                На паузе
              </>
            )}
          </button>

          {/* Refresh button */}
          <button
            className="btn"
            onClick={() => fetchLogs(true)}
            disabled={loading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '7px 12px', fontSize: '12px', borderRadius: '8px', cursor: 'pointer', background: 'var(--panel)', border: '1px solid var(--line)' }}
            title="Обновить журнал"
          >
            <RefreshCw size={13} className={loading ? 'spinning' : ''} />
            Обновить
          </button>

          {/* Copy all button */}
          <button
            className="btn"
            onClick={handleCopyAll}
            disabled={filteredLogs.length === 0}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '7px 12px', fontSize: '12px', borderRadius: '8px', cursor: 'pointer', background: 'var(--panel)', border: '1px solid var(--line)' }}
            title="Скопировать отображаемый лог"
          >
            <Copy size={13} />
            Копировать
          </button>

          {/* Download button */}
          <button
            className="btn"
            onClick={handleDownload}
            disabled={filteredLogs.length === 0}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '7px 12px', fontSize: '12px', borderRadius: '8px', cursor: 'pointer', background: 'var(--panel)', border: '1px solid var(--line)' }}
            title="Скачать лог файлом .txt"
          >
            <Download size={13} />
            Скачать (.txt)
          </button>

          {/* Clear screen button */}
          <button
            className="btn danger"
            onClick={handleClear}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '7px 12px', fontSize: '12px', borderRadius: '8px', cursor: 'pointer', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)' }}
            title="Очистить экран"
          >
            <Trash2 size={13} />
            Очистить
          </button>
        </div>
      </div>

      {/* KPI Bento summary */}
      <div className="bento-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        <div className="bento-card" style={{ padding: '14px', background: 'var(--panel)', borderRadius: '10px', border: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: 600 }}>Всего строк лога</span>
            <Terminal size={16} style={{ color: 'var(--blue)' }} />
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800 }}>{counts.total}</div>
          <small style={{ color: 'var(--muted)', fontSize: '11px' }}>в текущем буфере выборки</small>
        </div>

        <div className="bento-card" style={{ padding: '14px', background: 'var(--panel)', borderRadius: '10px', border: counts.err > 0 ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid var(--line)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '12px', color: counts.err > 0 ? '#ef4444' : 'var(--muted)', fontWeight: 600 }}>Ошибки (ERROR)</span>
            <AlertCircle size={16} style={{ color: counts.err > 0 ? '#ef4444' : 'var(--muted)' }} />
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: counts.err > 0 ? '#ef4444' : 'inherit' }}>{counts.err}</div>
          <small style={{ color: counts.err > 0 ? '#ef4444' : 'var(--muted)', fontSize: '11px' }}>
            {counts.err > 0 ? 'требуют проверки' : 'критических сбоев нет'}
          </small>
        </div>

        <div className="bento-card" style={{ padding: '14px', background: 'var(--panel)', borderRadius: '10px', border: counts.warn > 0 ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid var(--line)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '12px', color: counts.warn > 0 ? '#f59e0b' : 'var(--muted)', fontWeight: 600 }}>Предупреждения (WARN)</span>
            <AlertTriangle size={16} style={{ color: counts.warn > 0 ? '#f59e0b' : 'var(--muted)' }} />
          </div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: counts.warn > 0 ? '#f59e0b' : 'inherit' }}>{counts.warn}</div>
          <small style={{ color: counts.warn > 0 ? '#f59e0b' : 'var(--muted)', fontSize: '11px' }}>
            {counts.warn > 0 ? 'предупреждений зафиксировано' : 'предупреждений нет'}
          </small>
        </div>

        <div className="bento-card" style={{ padding: '14px', background: 'var(--panel)', borderRadius: '10px', border: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: 600 }}>Контейнер</span>
            <Server size={16} style={{ color: 'var(--green)' }} />
          </div>
          <div style={{ fontSize: '16px', fontWeight: 800, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {selectedContainer}
          </div>
          <small style={{ color: '#22c55e', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} /> В работе
          </small>
        </div>
      </div>

      {/* Control / Filter Bar */}
      <div className="filter-bar" style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '12px 14px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '10px' }}>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Container Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Server size={14} style={{ color: 'var(--blue)' }} />
            <select
              value={selectedContainer}
              onChange={(e) => setSelectedContainer(e.target.value)}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                background: 'var(--bg)',
                color: 'var(--text)',
                border: '1px solid var(--line)',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: 700
              }}
            >
              {containers.map(c => (
                <option key={c.id} value={c.name}>
                  {c.name} {c.isDefault ? '(Главный)' : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Level Badges */}
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            {[
              { key: 'ALL', label: `Все (${counts.total})` },
              { key: 'ERROR', label: `ERROR (${counts.err})`, color: '#ef4444' },
              { key: 'WARN', label: `WARN (${counts.warn})`, color: '#f59e0b' },
              { key: 'INFO', label: `INFO (${counts.info})`, color: 'var(--blue)' },
            ].map(lvl => (
              <button
                key={lvl.key}
                onClick={() => setLevelFilter(lvl.key)}
                style={{
                  padding: '4px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  borderRadius: '6px',
                  border: levelFilter === lvl.key ? `1px solid ${lvl.color || 'var(--blue)'}` : '1px solid var(--line)',
                  background: levelFilter === lvl.key ? (lvl.color ? `${lvl.color}22` : 'rgba(59, 130, 246, 0.15)') : 'transparent',
                  color: levelFilter === lvl.key ? (lvl.color || 'var(--blue)') : 'var(--muted)'
                }}
              >
                {lvl.label}
              </button>
            ))}
          </div>

          {/* Search input */}
          <div style={{ flex: 1, minWidth: '180px', position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
            <input
              type="text"
              placeholder="Поиск по тексту лога (grep / фильтр)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 12px 6px 30px',
                fontSize: '12px',
                background: 'var(--bg)',
                color: 'var(--text)',
                border: '1px solid var(--line)',
                borderRadius: '6px'
              }}
            />
          </div>

          {/* Tail count selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--muted)' }}>
            <span>Строк:</span>
            <select
              value={tailCount}
              onChange={(e) => setTailCount(Number(e.target.value))}
              style={{
                padding: '5px 8px',
                fontSize: '11px',
                background: 'var(--bg)',
                color: 'var(--text)',
                border: '1px solid var(--line)',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              <option value={100}>100</option>
              <option value={300}>300</option>
              <option value={500}>500</option>
              <option value={1000}>1 000</option>
              <option value={2000}>2 000</option>
            </select>
          </div>

          {/* Date preset selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--muted)' }}>
            <Clock size={13} />
            <select
              value={datePreset}
              onChange={(e) => {
                const val = e.target.value as any;
                setDatePreset(val);
                if (val === 'CUSTOM') {
                  setShowCustomRange(true);
                  setIsLive(false);
                } else {
                  setShowCustomRange(false);
                }
              }}
              style={{
                padding: '5px 8px',
                fontSize: '11px',
                background: 'var(--bg)',
                color: 'var(--text)',
                border: '1px solid var(--line)',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: 600
              }}
            >
              <option value="ALL">За всё время</option>
              <option value="15M">Последние 15 мин</option>
              <option value="1H">Последний 1 час</option>
              <option value="TODAY">Сегодня</option>
              <option value="CUSTOM">📅 Указать период (С ... По ...)</option>
            </select>
          </div>
        </div>

        {/* Custom Date-Time Range Row */}
        {(showCustomRange || datePreset === 'CUSTOM') && (
          <div
            style={{
              display: 'flex',
              gap: '12px',
              alignItems: 'center',
              flexWrap: 'wrap',
              padding: '10px 12px',
              background: 'var(--bg)',
              border: '1px solid var(--blue)',
              borderRadius: '8px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <Calendar size={14} style={{ color: 'var(--blue)' }} />
              <span style={{ fontWeight: 600, color: 'var(--text)' }}>Период выборки:</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <span style={{ color: 'var(--muted)' }}>С (Начало):</span>
              <input
                type="datetime-local"
                value={customSince}
                onChange={(e) => setCustomSince(e.target.value)}
                style={{
                  padding: '5px 8px',
                  fontSize: '12px',
                  background: 'var(--panel)',
                  color: 'var(--text)',
                  border: '1px solid var(--line)',
                  borderRadius: '6px'
                }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              <span style={{ color: 'var(--muted)' }}>По (Конец):</span>
              <input
                type="datetime-local"
                value={customUntil}
                onChange={(e) => setCustomUntil(e.target.value)}
                style={{
                  padding: '5px 8px',
                  fontSize: '12px',
                  background: 'var(--panel)',
                  color: 'var(--text)',
                  border: '1px solid var(--line)',
                  borderRadius: '6px'
                }}
              />
            </div>

            <button
              className="btn primary"
              onClick={() => {
                fetchLogs(true);
                setIsLive(false);
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '5px 12px',
                fontSize: '12px',
                borderRadius: '6px',
                cursor: 'pointer',
                background: 'var(--blue)',
                color: '#fff',
                border: 'none',
                fontWeight: 600
              }}
            >
              Применить период
            </button>

            <button
              className="btn"
              onClick={() => {
                setCustomSince('');
                setCustomUntil('');
                setDatePreset('ALL');
                setShowCustomRange(false);
                setIsLive(true);
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '5px 10px',
                fontSize: '12px',
                borderRadius: '6px',
                cursor: 'pointer',
                background: 'var(--panel)',
                border: '1px solid var(--line)'
              }}
            >
              <X size={12} /> Сбросить
            </button>
          </div>
        )}
      </div>

      {/* Terminal Log Console */}
      <div
        className="terminal-window"
        style={{
          background: '#090d16',
          border: '1px solid #1e293b',
          borderRadius: '10px',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 8px 30px rgba(0, 0, 0, 0.5)'
        }}
      >
        {/* Terminal Header Bar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 14px',
            background: '#0f172a',
            borderBottom: '1px solid #1e293b',
            fontSize: '12px',
            color: '#94a3b8'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444' }} />
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f59e0b' }} />
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#22c55e' }} />
            </div>
            <strong style={{ color: '#e2e8f0', marginLeft: '6px', fontFamily: 'monospace' }}>
              docker logs -f {selectedContainer}
            </strong>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              Отображено: <strong style={{ color: '#cbd5e1' }}>{filteredLogs.length}</strong> строк
            </span>

            {/* Auto-scroll indicator & toggle */}
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 8px',
                fontSize: '11px',
                borderRadius: '4px',
                border: autoScroll ? '1px solid rgba(59, 130, 246, 0.5)' : '1px solid #334155',
                background: autoScroll ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                color: autoScroll ? '#60a5fa' : '#64748b',
                cursor: 'pointer'
              }}
              title={autoScroll ? 'Автопрокрутка включена' : 'Кликните, чтобы включить автопрокрутку вниз'}
            >
              <ArrowDown size={12} />
              {autoScroll ? 'Автоскролл вкл' : 'Автоскролл пауза'}
            </button>
          </div>
        </div>

        {/* Terminal Body */}
        <div
          ref={terminalContainerRef}
          onScroll={handleScroll}
          style={{
            height: '620px',
            overflowY: 'auto',
            padding: '12px 14px',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            fontSize: '12px',
            lineHeight: '1.6',
            color: '#cbd5e1',
            background: '#090d16'
          }}
        >
          {loading && logs.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', gap: '8px' }}>
              <RefreshCw size={16} className="spinning" />
              Подключение к потоку логов контейнера {selectedContainer}...
            </div>
          ) : filteredLogs.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', gap: '8px' }}>
              <Terminal size={32} style={{ color: '#334155' }} />
              <span>Записей лога по выбранным фильтрам не найдено</span>
              <small style={{ color: '#475569' }}>Попробуйте сбросить фильтр по уровню, изменить период или очистить поисковую строку</small>
            </div>
          ) : (
            filteredLogs.map((entry, index) => {
              const lvl = entry.level.toUpperCase();
              let badgeColor = '#38bdf8';
              let badgeBg = 'rgba(56, 189, 248, 0.12)';
              let rowBg = 'transparent';

              if (lvl === 'ERROR') {
                badgeColor = '#ef4444';
                badgeBg = 'rgba(239, 68, 68, 0.2)';
                rowBg = 'rgba(239, 68, 68, 0.05)';
              } else if (lvl === 'WARN' || lvl === 'WARNING') {
                badgeColor = '#f59e0b';
                badgeBg = 'rgba(245, 158, 11, 0.15)';
                rowBg = 'rgba(245, 158, 11, 0.03)';
              } else if (lvl === 'DEBUG') {
                badgeColor = '#a855f7';
                badgeBg = 'rgba(168, 85, 247, 0.15)';
              }

              return (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: rowBg,
                    transition: 'background 0.1s'
                  }}
                  className="terminal-row"
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = rowBg)}
                >
                  {/* Line number */}
                  <span style={{ color: '#475569', minWidth: '38px', textAlign: 'right', userSelect: 'none', fontSize: '11px' }}>
                    {index + 1}
                  </span>

                  {/* Timestamp */}
                  <span style={{ color: '#64748b', whiteSpace: 'nowrap', userSelect: 'none', fontSize: '11px' }}>
                    {formatTimestamp(entry.timestamp)}
                  </span>

                  {/* Level Pill */}
                  <span
                    style={{
                      padding: '1px 6px',
                      fontSize: '10px',
                      fontWeight: 700,
                      borderRadius: '3px',
                      background: badgeBg,
                      color: badgeColor,
                      minWidth: '46px',
                      textAlign: 'center',
                      userSelect: 'none'
                    }}
                  >
                    {lvl}
                  </span>

                  {/* Stream Indicator: Only show if stderr AND level is ERROR/WARN */}
                  {entry.stream === 'stderr' && (lvl === 'ERROR' || lvl === 'WARN') && (
                    <span style={{ color: '#f87171', fontSize: '10px', opacity: 0.7, userSelect: 'none' }}>
                      [stderr]
                    </span>
                  )}

                  {/* Message */}
                  <span
                    style={{
                      flex: 1,
                      wordBreak: 'break-word',
                      whiteSpace: 'pre-wrap',
                      color: lvl === 'ERROR' ? '#fca5a5' : lvl === 'WARN' ? '#fde68a' : '#cbd5e1'
                    }}
                  >
                    {entry.message}
                  </span>

                  {/* Copy button on hover */}
                  <button
                    onClick={() => handleCopyLine(entry.raw || entry.message, index)}
                    style={{
                      opacity: 0.3,
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#94a3b8',
                      padding: '0 4px'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.3')}
                    title="Скопировать эту строку"
                  >
                    {copiedIndex === index ? <Check size={12} style={{ color: '#22c55e' }} /> : <Copy size={12} />}
                  </button>
                </div>
              );
            })
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
};
