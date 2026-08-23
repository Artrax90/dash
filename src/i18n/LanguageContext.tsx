import React, { createContext, useContext, useEffect, useState } from 'react';

export type Language = 'ru' | 'en';

export const translations = {
  ru: {
    common: {
      workspace: 'BMSTU',
      workspaceLabel: 'РАБОЧЕЕ ПРОСТРАНСТВО',
      backendConnected: 'Бэкенд подключен',
      live: 'LIVE',
      userName: 'Администратор',
      userRole: 'Суперадминистратор',
      alreadySignedIn: 'Вы вошли в систему',
      signOut: 'Выйти',
      allSystemsOperational: 'Все системы работают штатно',
      cancel: 'Отмена',
      saveChanges: 'Сохранить изменения',
      filter: 'Фильтр',
      refresh: 'Обновить',
      export: 'Экспорт',
      showing: 'Показано',
      ofTotal: 'из',
      devices: 'устройств',
      previous: 'Назад',
      next: 'Вперед',
      status: 'Статус',
      device: 'Устройство',
      group: 'Группа',
      ipAddress: 'IP-адрес',
      currentUser: 'Текущий пользователь',
      rdp: 'RDP',
      uptime: 'Время работы',
      lastSeen: 'Был в сети',
      close: 'Закрыть',
      copied: 'Скопировано в буфер обмена',
    },
    nav: {
      dashboard: 'Панель управления',
      devices: 'Устройства',
      groups: 'Группы',
      schedules: 'Расписания',
      monitoring: 'Мониторинг',
      alerts: 'Оповещения',
      users: 'Пользователи',
      roles: 'Роли и права',
      agents: 'Агенты и загрузки',
      telegram: 'Telegram-бот',
      audit: 'Журнал аудита',
      settings: 'Настройки',
      operations: 'Операции',
      administration: 'Администрирование',
    },
    dashboard: {
      eyebrow: 'ОБЗОР СИСТЕМЫ',
      greeting: 'Добро пожаловать в панель управления',
      subtitle: 'Оперативная сводка состояния парка рабочих станций',
      exportReport: 'Экспорт отчета',
      quickActions: 'Быстрые действия',
      totalDevices: 'Всего станций',
      acrossGroups: 'В 4 рабочих группах',
      online: 'В сети (Онлайн)',
      ofFleet: '80% парка',
      offline: 'Выключены (Оффлайн)',
      needAttention: '3 требуют внимания',
      problems: 'Проблемы / Аварии',
      criticalAlert: '1 критический инцидент',
      activeRdp: 'Активные RDP',
      idleSessions: '2 сессии простаивают',
      disconnectedRdp: 'Брошенные RDP',
      oldestSession: 'Старшая: 2 ч назад',
      needsAttention: 'Требуют внимания',
      needsAttentionSubtitle: 'Нерешенные инциденты и предупреждения оборудования',
      openCount: 'открыто',
      fleetHealth: 'Здоровье парка',
      fleetHealthSubtitle: 'Распределение статусов компьютеров',
      updatedJustNow: 'Обновлено только что',
      liveStatus: 'Текущее состояние парка',
      liveStatusSubtitle: 'Мониторинг рабочих станций в реальном времени',
      searchDevices: 'Поиск по имени, IP или группе...',
    },
    devices: {
      overview: 'Обзор',
      hardware: 'Оборудование',
      baseline: 'Эталон',
      rdpSessionsTab: 'RDP Сессии',
      powerTab: 'Питание и Расписание',
      alertPolicyTab: 'Политика алертинга',
      credentialsTab: 'Учетные данные',
      automationTab: 'Автоматизация',
      historyTab: 'История',
      title: 'Устройства',
      subtitle: 'Централизованное управление, мониторинг и питание рабочих станций.',
      addDevice: 'Добавить ПК',
      devicesSelected: 'выбрано устройств',
      allDevices: 'Все устройства',
      inFleet: 'рабочих станций в парке',
      backToDevices: 'Назад к списку устройств',
      editDevice: 'Редактировать ПК',
      powerActions: 'Управление питанием',
      power: 'Питание',
      agent: 'Агент',
      health: 'Здоровье',
      maintenanceMode: 'Режим обслуживания включен',
      systemInfo: 'Информация о системе',
      reportedByAgent: 'Передано фоновым агентом станции',
      hostname: 'Имя хоста',
      macAddress: 'MAC-адрес',
      os: 'Операционная система',
      agentVersion: 'Версия агента',
      lastHeartbeat: 'Последний сигнал',
      resourceUsage: 'Использование ресурсов',
      currentReadings: 'Текущие показатели утилизации',
      cpuUsage: 'Загрузка ЦП',
      ramUsage: 'Использование ОЗУ',
      diskUsage: 'Занято на диске',
      heartbeatHealthy: 'Связь с агентом стабильна',
      rdpSessions: 'RDP-сессии',
      activeConnections: 'Подключения пользователей к этой машине',
      tagsMetadata: 'Теги и метаданные',
      organizeWorkstation: 'Категоризация и пометки',
      addTag: 'Добавить тег',
      auditNote: 'Все изменения метаданных и конфигураций фиксируются в аудите.',
      ramSlots: 'Слоты оперативной памяти',
      storageDrives: 'Физические накопители',
      baselineApprovedBy: 'Эталон утвержден:',
      noBaseline: 'Эталон еще не зафиксирован',
      acceptAsBaseline: 'Принять текущее состояние как эталон',
      matchStatus: 'Статус соответствия эталону',
      matched: 'Полное соответствие эталону',
      mismatch: 'Обнаружено расхождение с эталоном!',
      history: 'История изменений комплектующих',
      powerControls: 'Управление питанием',
      powerControlsSubtitle: 'Отправка аппаратных команд на станцию',
      recentOperations: 'Последние операции',
      wake: 'Включить (WoL)',
      reboot: 'Перезагрузить',
      shutdown: 'Выключить',
      forceShutdown: 'Принудительно выключить',
      shutdownWarning: 'Рабочая станция завершит приложения и выключится.',
      forceShutdownWarning: 'Внимание! Несохраненные данные пользователей могут быть потеряны.',
    }
  },
  en: {
    common: {
      workspace: 'BMSTU',
      workspaceLabel: 'WORKSPACE',
      backendConnected: 'Backend connected',
      live: 'LIVE',
      userName: 'Administrator',
      userRole: 'Super Admin',
      alreadySignedIn: 'You are signed in',
      signOut: 'Sign out',
      allSystemsOperational: 'All systems operational',
      cancel: 'Cancel',
      saveChanges: 'Save changes',
      filter: 'Filter',
      refresh: 'Refresh',
      export: 'Export',
      showing: 'Showing',
      ofTotal: 'of',
      devices: 'devices',
      previous: 'Previous',
      next: 'Next',
      status: 'Status',
      device: 'Device',
      group: 'Group',
      ipAddress: 'IP address',
      currentUser: 'Current user',
      rdp: 'RDP',
      uptime: 'Uptime',
      lastSeen: 'Last seen',
      close: 'Close',
      copied: 'Copied to clipboard',
    },
    nav: {
      dashboard: 'Dashboard',
      devices: 'Devices',
      groups: 'Groups',
      schedules: 'Schedules',
      monitoring: 'Monitoring',
      alerts: 'Alerts',
      users: 'Users',
      roles: 'Roles & permissions',
      agents: 'Agents & downloads',
      telegram: 'Telegram Bot',
      audit: 'Audit Log',
      settings: 'Settings',
      operations: 'Operations',
      administration: 'Administration',
    },
    dashboard: {
      eyebrow: 'OVERVIEW',
      greeting: 'Welcome to Workstation Manager',
      subtitle: 'Here’s what’s happening across your workstation fleet.',
      exportReport: 'Export report',
      quickActions: 'Quick actions',
      totalDevices: 'Total devices',
      acrossGroups: 'Across 4 groups',
      online: 'Online',
      ofFleet: '80% of fleet',
      offline: 'Offline',
      needAttention: '3 need attention',
      problems: 'Problems',
      criticalAlert: '1 critical',
      activeRdp: 'Active RDP',
      idleSessions: '2 idle sessions',
      disconnectedRdp: 'Disconnected RDP',
      oldestSession: 'Oldest: 2h ago',
      needsAttention: 'Needs attention',
      needsAttentionSubtitle: 'Open items that may need your review',
      openCount: 'open',
      fleetHealth: 'Fleet health',
      fleetHealthSubtitle: 'Current status by device',
      updatedJustNow: 'Updated just now',
      liveStatus: 'Live device status',
      liveStatusSubtitle: 'Real-time view of your workstation fleet',
      searchDevices: 'Search devices...',
    },
    devices: {
      overview: 'Overview',
      hardware: 'Hardware',
      baseline: 'Baseline',
      rdpSessionsTab: 'RDP Sessions',
      powerTab: 'Power & Schedule',
      alertPolicyTab: 'Alert Policy',
      credentialsTab: 'Credentials',
      automationTab: 'Automation',
      historyTab: 'History',
      title: 'Devices',
      subtitle: 'Manage, monitor, and control every workstation in your network.',
      addDevice: 'Add device',
      devicesSelected: 'devices selected',
      allDevices: 'All devices',
      inFleet: 'workstations in your fleet',
      backToDevices: 'Back to devices',
      editDevice: 'Edit device',
      powerActions: 'Power actions',
      power: 'Power',
      agent: 'Agent',
      health: 'Health',
      maintenanceMode: 'Maintenance mode enabled',
      systemInfo: 'System information',
      reportedByAgent: 'Reported by the workstation agent',
      hostname: 'Hostname',
      macAddress: 'MAC address',
      os: 'Operating system',
      agentVersion: 'Agent version',
      lastHeartbeat: 'Last heartbeat',
      resourceUsage: 'Resource usage',
      currentReadings: 'Current readings',
      cpuUsage: 'CPU usage',
      ramUsage: 'Memory usage',
      diskUsage: 'Disk usage',
      heartbeatHealthy: 'Agent heartbeat healthy',
      rdpSessions: 'RDP sessions',
      activeConnections: 'Active connections on this device',
      tagsMetadata: 'Tags & metadata',
      organizeWorkstation: 'Organize this workstation',
      addTag: 'Add tag',
      auditNote: 'Changes to metadata are recorded in the audit log.',
      ramSlots: 'RAM Slots',
      storageDrives: 'Storage Drives',
      baselineApprovedBy: 'Baseline approved by:',
      noBaseline: 'No baseline configured yet',
      acceptAsBaseline: 'Accept current state as baseline',
      matchStatus: 'Baseline compliance status',
      matched: 'Baseline matches perfectly',
      mismatch: 'Hardware discrepancy detected!',
      history: 'Hardware change history',
      powerControls: 'Power controls',
      powerControlsSubtitle: 'Send hardware commands to workstation',
      recentOperations: 'Recent operations',
      wake: 'Wake (WoL)',
      reboot: 'Reboot',
      shutdown: 'Shutdown',
      forceShutdown: 'Force shutdown',
      shutdownWarning: 'The workstation will close active applications and power down.',
      forceShutdownWarning: 'Warning! Any unsaved data may be lost. This cannot be undone.',
    }
  }
};

type TranslationTree = typeof translations.ru;

interface LanguageContextType {
  lang: Language;
  setLang: (lang: Language) => void;
  tr: TranslationTree;
  t: (key: string, fallback?: string) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  lang: 'ru',
  setLang: () => {},
  tr: translations.ru,
  t: (k) => k,
});

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Language>(() => {
    const saved = localStorage.getItem('wm_lang');
    return saved === 'en' || saved === 'ru' ? saved : 'ru';
  });

  const setLang = (newLang: Language) => {
    setLangState(newLang);
    localStorage.setItem('wm_lang', newLang);
    document.documentElement.lang = newLang;
  };

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const currentTranslations = translations[lang] || translations.ru;

  const t = (path: string, fallback?: string): string => {
    const parts = path.split('.');
    let current: any = currentTranslations;
    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = current[part];
      } else {
        return fallback || path;
      }
    }
    return typeof current === 'string' ? current : (fallback || path);
  };

  const value = {
    lang,
    setLang,
    tr: currentTranslations,
    t,
  };

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
};

export const useLanguage = () => useContext(LanguageContext);
