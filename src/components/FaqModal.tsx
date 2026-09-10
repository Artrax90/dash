import React, { useState, useMemo } from 'react';
import {
  CircleHelp, Search, X, ChevronDown, ChevronRight, Copy, Check, Terminal,
  Key, Power, ShieldAlert, Users, Bot, Calendar, Cpu, Layers, AlertTriangle,
  CheckCircle2, Info, Laptop, Zap, RefreshCw, LogOut, Wrench, ShieldCheck,
  Radio, HardDrive, Usb, ArrowRight, ExternalLink
} from 'lucide-react';

interface FaqModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface FaqArticle {
  id: string;
  category: string;
  title: string;
  summary: string;
  badge?: string;
  badgeColor?: 'blue' | 'green' | 'amber' | 'red' | 'purple';
  content: React.ReactNode;
}

export const FaqModal: React.FC<FaqModalProps> = ({ isOpen, onClose }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [expandedArticleId, setExpandedArticleId] = useState<string | null>('quickstart_ps');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => {
      setCopiedKey(null);
    }, 2000);
  };

  const categories = [
    { id: 'all', label: 'Все темы', icon: CircleHelp },
    { id: 'quickstart', label: 'Быстрый старт и Агенты', icon: Laptop },
    { id: 'tokens', label: 'Токены безопасности', icon: Key },
    { id: 'power', label: 'Питание и Wake-on-LAN', icon: Power },
    { id: 'processes', label: 'Процессы и Сессии', icon: Zap },
    { id: 'hardware', label: 'Антикража и Железо', icon: Cpu },
    { id: 'monitoring', label: 'Политики мониторинга', icon: ShieldCheck },
    { id: 'telegram', label: 'Telegram-уведомления', icon: Bot },
    { id: 'users_roles', label: 'Роли и Зоны (Scopes)', icon: Users },
    { id: 'groups', label: 'Группы и Аудитории', icon: Layers },
    { id: 'schedules', label: 'Расписания и Cron', icon: Calendar },
    { id: 'troubleshooting', label: 'Решение проблем', icon: Wrench },
  ];

  const articles: FaqArticle[] = [
    // -------------------------------------------------------------
    // БЫСТРЫЙ СТАРТ И АГЕНТЫ
    // -------------------------------------------------------------
    {
      id: 'quickstart_agent_intro',
      category: 'quickstart',
      title: 'Что такое Агент (DashAgent) и как он устроен?',
      summary: 'Легковесная скрытая фоновая служба (менее 15 МБ), которая связывает компьютер с сервером управления.',
      badge: 'Базовые понятия',
      badgeColor: 'blue',
      content: (
        <div>
          <p>
            <strong>Агент (DashAgent)</strong> — это программа-помощник, которая устанавливается на целевой компьютер (Windows или Linux).
            Она работает в фоновом режиме как системная служба, не мешает пользователю и практически не потребляет ресурсы:
          </p>
          <div className="faq-grid-badges">
            <div className="faq-mini-card">
              <strong>💻 0.01% CPU</strong>
              <span>Работает в фоне незаметно для игр и программ</span>
            </div>
            <div className="faq-mini-card">
              <strong>🧠 ~15 МБ ОЗУ</strong>
              <span>Не замедляет загрузку и работу компьютера</span>
            </div>
            <div className="faq-mini-card">
              <strong>⚡ Порт 48123 UDP</strong>
              <span>Слушает прямые локальные команды для мгновенного отклика</span>
            </div>
          </div>
          <div className="faq-callout info">
            <Info size={18} />
            <div>
              <strong>Что умеет агент?</strong>
              <p>Агент сообщает серверу, включен ли ПК, загрузку процессора, температуру, состояние памяти, список запущенных программ, а также выполняет команды на выключение, перезагрузку, закрытие зависших процессов и отслеживает кражу комплектующих.</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'quickstart_ps',
      category: 'quickstart',
      title: 'Способ 1: Установка одной строкой в PowerShell (Рекомендуется)',
      summary: 'Самый быстрый способ подключить любой компьютер Windows за 10 секунд без ручной возни.',
      badge: 'Windows 10 / 11 / Server',
      badgeColor: 'green',
      content: (
        <div>
          <p>Чтобы мгновенно подключить компьютер Windows к вашей панели управления, выполните 3 простых шага:</p>
          <ol className="faq-steps-list">
            <li>
              <strong>Откройте PowerShell от имени Администратора:</strong>
              <p>Нажмите клавиши <code>Win + X</code> на клавиатуре или откройте меню «Пуск», введите <em>PowerShell</em>, нажмите правой кнопкой мыши и выберите <strong>«Запуск от имени администратора»</strong>.</p>
            </li>
            <li>
              <strong>Вставьте команду развёртывания:</strong>
              <div className="faq-code-block">
                <div className="faq-code-header">
                  <span>PowerShell (Admin)</span>
                  <button
                    className="faq-copy-btn"
                    onClick={() => copyToClipboard(`irm "http://${window.location.hostname || '192.168.1.109'}:2301/api/v1/agents/bootstrap/ps1?token=default_enroll_token" | iex`, 'ps_quick')}
                  >
                    {copiedKey === 'ps_quick' ? <Check size={14} className="text-green" /> : <Copy size={14} />}
                    <span>{copiedKey === 'ps_quick' ? 'Скопировано!' : 'Копировать'}</span>
                  </button>
                </div>
                <code>{`irm "http://${window.location.hostname || '192.168.1.109'}:2301/api/v1/agents/bootstrap/ps1?token=default_enroll_token" | iex`}</code>
              </div>
            </li>
            <li>
              <strong>Нажмите Enter:</strong>
              <p>Скрипт автоматически скачает исполняемый файл агента, зарегистрирует службу <code>DashAgent</code>, создаст правило в Брандмауэре Windows для порта <code>48123 UDP</code> и передаст на сервер отпечаток оборудования. Компьютер сразу появится в списке!</p>
            </li>
          </ol>
          <div className="faq-callout tip">
            <CheckCircle2 size={18} />
            <div>
              <strong>Где взять команду с актуальным токеном?</strong>
              <p>Перейдите в боковом меню в раздел <strong>«Агенты»</strong> — там вверху страницы всегда отображается готовая персональная команда для вашего сервера с вашим действующим токеном.</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'quickstart_bat',
      category: 'quickstart',
      title: 'Способ 2: Установка с флешки через .bat файл (Для учебных классов)',
      summary: 'Идеально, когда нужно обойти 20–30 компьютеров с флешкой без ввода команд вручную.',
      badge: 'Офлайн / Флешка',
      badgeColor: 'blue',
      content: (
        <div>
          <p>Если вам нужно подключить целый компьютерный класс или аудиторию:</p>
          <ol className="faq-steps-list">
            <li>Откройте раздел <strong>«Агенты»</strong> в панели управления.</li>
            <li>Нажмите синюю кнопку <strong>«Скачать .bat установщик»</strong>. Браузер сохранит файл <code>install_agent.bat</code>.</li>
            <li>Скопируйте этот <code>.bat</code> файл на обычную флешку.</li>
            <li>Вставьте флешку в целевой компьютер, нажмите правой кнопкой на <code>install_agent.bat</code> и выберите <strong>«Запуск от имени администратора»</strong>.</li>
            <li>Появится черное окно командной строки, пробегут зеленые строчки установки, и через 3 секунды окно закроется. Компьютер подключен!</li>
          </ol>
        </div>
      )
    },
    {
      id: 'quickstart_linux',
      category: 'quickstart',
      title: 'Способ 3: Подключение компьютеров на Linux (Ubuntu, Debian, Astra Linux, РЕД ОС)',
      summary: 'Развёртывание агента в качестве systemd демона одной командой через bash.',
      badge: 'Linux / Astra / РЕД ОС',
      badgeColor: 'purple',
      content: (
        <div>
          <p>Для компьютеров и серверов под управлением Linux установка выполняется через стандартный терминал:</p>
          <div className="faq-code-block">
            <div className="faq-code-header">
              <span>Bash (root / sudo)</span>
              <button
                className="faq-copy-btn"
                onClick={() => copyToClipboard(`curl -fsSL "http://${window.location.hostname || '192.168.1.109'}:2301/api/v1/agents/bootstrap/sh?token=default_enroll_token" | sudo bash`, 'linux_quick')}
              >
                {copiedKey === 'linux_quick' ? <Check size={14} className="text-green" /> : <Copy size={14} />}
                <span>{copiedKey === 'linux_quick' ? 'Скопировано!' : 'Копировать'}</span>
              </button>
            </div>
            <code>{`curl -fsSL "http://${window.location.hostname || '192.168.1.109'}:2301/api/v1/agents/bootstrap/sh?token=default_enroll_token" | sudo bash`}</code>
          </div>
          <p>
            Скрипт создаст системный сервис <code>dash-agent.service</code>, настроит автозапуск и активирует мониторинг системных метрик.
          </p>
        </div>
      )
    },
    {
      id: 'quickstart_agentless',
      category: 'quickstart',
      title: 'Способ 4: Тонкие клиенты и компьютеры БЕЗ агента (Agentless)',
      summary: 'Мониторинг оборудования, где нельзя установить программу: сетевые принтеры, коммутаторы, закрытые тонкие клиенты.',
      badge: 'Agentless / ICMP',
      badgeColor: 'amber',
      content: (
        <div>
          <p>
            Если на устройство нельзя установить агент (например, это сетевой принтер, маршрутизатор или тонкий клиент с заблокированной ОС):
          </p>
          <ol className="faq-steps-list">
            <li>В боковом меню перейдите в <strong>«Устройства»</strong> и нажмите кнопку <strong>«+ Добавить устройство»</strong>.</li>
            <li>Введите имя, сетевое имя (Hostname), IP-адрес и обязательно MAC-адрес устройства.</li>
            <li>Отметьте переключатель <strong>«Режим без агента (Agentless)»</strong>.</li>
            <li>Укажите сетевые порты для проверки (например, <code>3389</code> для RDP, <code>80/443</code> для веб-интерфейса или <code>9100</code> для принтеров).</li>
          </ol>
          <div className="faq-callout tip">
            <CheckCircle2 size={18} />
            <div>
              <strong>Умная миграция IP-адресов по MAC / ARP:</strong>
              <p>Если роутер выдаст тонкому клиенту новый динамический IP-адрес по DHCP, наш сервер автоматически обнаружит смену через периодический опрос ARP-таблицы по сохраненному MAC-адресу и сам обновит IP в карточке устройства!</p>
            </div>
          </div>
        </div>
      )
    },

    // -------------------------------------------------------------
    // ТОКЕНЫ БЕЗОПАСНОСТИ
    // -------------------------------------------------------------
    {
      id: 'token_purpose',
      category: 'tokens',
      title: 'Зачем нужен Токен подключения (FLEET_JOIN_TOKEN)?',
      summary: 'Цифровой пароль-ключ, который защищает ваш сервер от несанкционированного подключения чужих устройств.',
      badge: 'Безопасность',
      badgeColor: 'amber',
      content: (
        <div>
          <p>
            <strong>Токен регистрации</strong> — это секретный цифровой ключ вашей организации (например: <code>sec_tok_9f8e7d6c...</code>).
          </p>
          <div className="faq-callout warning">
            <ShieldAlert size={18} />
            <div>
              <strong>Зачем нужна эта защита?</strong>
              <p>Без токена любой посторонний человек в вашей локальной сети (например, озорной студент с ноутбука) мог бы отправить фиктивный запрос на сервер и засорить панель фальшивыми компьютерами или перехватить команды управления.</p>
            </div>
          </div>
          <h4>Как работает проверка токена:</h4>
          <ul>
            <li>Когда агент впервые связывается с сервером, он отправляет токен в заголовке <code>X-Enrollment-Token</code>.</li>
            <li>Сервер сверяет ключ со списком разрешенных токенов в базе данных.</li>
            <li>Если токен верный — компьютер регистрируется и получает уникальный зашифрованный сессионный ключ.</li>
            <li>Если токена нет или он просрочен — сервер возвращает ошибку <code>401 Unauthorized</code> и отклоняет устройство.</li>
          </ul>
          <h4>Где настроить токены?</h4>
          <p>
            Перейдите в раздел <strong>«Агенты»</strong> ➔ вкладка <strong>«Токены регистрации»</strong>. Здесь суперадминистратор может создавать новые токены с ограничением по времени (например, выдать технику временный токен на 24 часа для настройки нового кабинета) или лимитом подключений.
          </p>
        </div>
      )
    },

    // -------------------------------------------------------------
    // ПИТАНИЕ И WAKE-ON-LAN
    // -------------------------------------------------------------
    {
      id: 'power_wol',
      category: 'power',
      title: 'Как включить выключенный компьютер (Wake-on-LAN)?',
      summary: 'Отправка Magic Packet по сети для удаленного пробуждения компьютера.',
      badge: 'Wake-on-LAN (WoL)',
      badgeColor: 'blue',
      content: (
        <div>
          <p>
            Кнопка с иконкой молнии <strong>«Включить (WoL)»</strong> посылает специальный сетевой сигнал (Magic Packet) на сетевую карту компьютера по его MAC-адресу.
          </p>
          <h4>Что нужно настроить один раз, чтобы компьютер включался по сети:</h4>
          <ol className="faq-steps-list">
            <li>
              <strong>Включить WoL в BIOS/UEFI материнской платы:</strong>
              <p>При включении компьютера нажимайте клавишу <code>Del</code> или <code>F2</code>. Найдите раздел <em>Power Management</em> или <em>Advanced</em> и включите параметры <strong>«Wake on LAN»</strong>, <strong>«Power On By PCI-E Device»</strong> или <strong>«Resume by Onboard LAN»</strong>. Сохраните настройки (клавиша F10).</p>
            </li>
            <li>
              <strong>В свойствах сетевой карты Windows:</strong>
              <p>Откройте «Диспетчер устройств» ➔ «Сетевые адаптеры» ➔ свойства вашей сетевой карты ➔ вкладка <em>«Управление электропитанием»</em> ➔ поставьте галочку <strong>«Разрешить этому устройству выводить компьютер из ждущего режима»</strong> и <strong>«Разрешать только магическому пакету...»</strong>.</p>
            </li>
            <li>
              <strong>Отключить «Быстрый запуск» Windows (Fast Startup):</strong>
              <p>Панель управления ➔ Электропитание ➔ «Действие кнопок питания» ➔ «Изменение параметров, которые сейчас недоступны» ➔ <strong>снимите галочку с «Включить быстрый запуск»</strong>. При быстром запуске Windows полностью обесточивает сетевой адаптер, и он не сможет услышать сигнал включения.</p>
            </li>
          </ol>
          <div className="faq-callout tip">
            <Info size={18} />
            <div>
              <strong>Важное правило сетевого включения:</strong>
              <p>Компьютер должен быть подключен к сети обычным витым сетевым кабелем (Ethernet RJ-45). По беспроводному Wi-Fi стандартный Wake-on-LAN не работает, так как Wi-Fi модуль отключается при выключении ПК.</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'power_shutdown_reboot',
      category: 'power',
      title: 'Выключение и перезагрузка: Мягкое, Принудительное и UDP-каскад',
      summary: 'Разница между корректным завершением программ и экстренным сбросом зависшего ПК.',
      badge: 'Питание',
      badgeColor: 'green',
      content: (
        <div>
          <h4>В системе предусмотрено 3 вида управления питанием:</h4>
          <div className="faq-types-list">
            <div className="faq-type-row">
              <div className="faq-type-icon text-blue"><Power size={20} /></div>
              <div>
                <strong>Мягкое выключение (Soft Shutdown)</strong>
                <p>Кнопка «Выключить». Отправляет операционной системе стандартную команду на завершение работы. Программы закрываются штатно, несохраненные документы запрашивают сохранение. Идеально для конца учебного или рабочего дня.</p>
              </div>
            </div>
            <div className="faq-type-row">
              <div className="faq-type-icon text-red"><AlertTriangle size={20} /></div>
              <div>
                <strong>Принудительное выключение (Force Shutdown)</strong>
                <p>Кнопка «Выключить принудительно». Используется, если компьютер намертво завис или приложение блокирует выход. Агент моментально отдает приказ ядру ОС на отключение питания без ожидания подтверждений от зависших программ.</p>
              </div>
            </div>
            <div className="faq-type-row">
              <div className="faq-type-icon text-green"><RefreshCw size={20} /></div>
              <div>
                <strong>Мгновенная перезагрузка (UDP Каскад + Очередь)</strong>
                <p>Кнопка «Перезагрузить». Сервер отправляет прямой UDP-триггер на порт 48123 компьютера для отклика за доли секунды. Компьютер перезагружается сразу же, а в журнале аудита фиксируется имя оператора, нажавшего кнопку.</p>
              </div>
            </div>
          </div>
        </div>
      )
    },

    // -------------------------------------------------------------
    // ПРОЦЕССЫ И СЕССИИ
    // -------------------------------------------------------------
    {
      id: 'processes_kill',
      category: 'processes',
      title: 'Как закрыть зависшую программу или вирусный процесс?',
      summary: 'Принудительное снятие дерева процессов через taskkill /F /T в карточке компьютера.',
      badge: 'Диспетчер процессов',
      badgeColor: 'red',
      content: (
        <div>
          <p>Если у пользователя в аудитории зависла тяжелая 3D-программа, игра или ресурсоемкий скрипт:</p>
          <ol className="faq-steps-list">
            <li>Кликните на нужный компьютер в таблице устройств, чтобы открыть его карточку.</li>
            <li>Перейдите во вкладку <strong>«Процессы»</strong>.</li>
            <li>Вы увидите список всех запущенных программ с потреблением процессора и оперативной памяти в реальном времени.</li>
            <li>Воспользуйтесь поиском или сортировкой по <em>% CPU / RAM</em>, чтобы найти виновника.</li>
            <li>Нажмите красную кнопку с крестиком <strong>«Снять задачу»</strong> напротив процесса.</li>
          </ol>
          <div className="faq-callout info">
            <CheckCircle2 size={18} />
            <div>
              <strong>Как агент снимает зависшие процессы?</strong>
              <p>Агент выполняет системную команду <code>taskkill /F /T /PID &lt;id&gt;</code> с правами <code>SYSTEM</code>. Флаг <code>/T</code> гарантирует, что закроется не только главный процесс, но и все его дочерние подпроцессы, освободив 100% оперативной памяти. Интерфейс моментально зачеркивает процесс, не заставляя вас ждать обновления страницы!</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'sessions_logoff',
      category: 'processes',
      title: 'Как разлогинить пользователя (Завершение сеанса)?',
      summary: 'Безопасное закрытие сессии пользователя без отключения самого компьютера.',
      badge: 'Сессии',
      badgeColor: 'purple',
      content: (
        <div>
          <p>
            Если студент или сотрудник закончил работу, но забыл выйти из своей учетной записи Windows (оставил открытым личный профиль, почту или соцсети):
          </p>
          <ul>
            <li>В карточке компьютера перейдите во вкладку <strong>«Сессии»</strong> (RDP / Консоль).</li>
            <li>Найдите имя залогиненного пользователя (например, <code>STUDENT-05</code>).</li>
            <li>Нажмите кнопку <strong>«Завершить сеанс» (Logoff)</strong>.</li>
          </ul>
          <p>
            Сессия пользователя немедленно завершится, все его личные программы закроются, а компьютер вернется на синий экран входа в Windows, готовый к работе следующего человека. Компьютер при этом не выключается!
          </p>
        </div>
      )
    },

    // -------------------------------------------------------------
    // АНТИКРАЖА И ЖЕЛЕЗО
    // -------------------------------------------------------------
    {
      id: 'hardware_baseline',
      category: 'hardware',
      title: 'Антикража: Как работает охрана комплектующих (RAM, GPU, CPU, SSD)?',
      summary: 'Автоматическая фиксация эталонного профиля железа и мгновенная тревога при подмене или хищении деталей.',
      badge: 'Антикража',
      badgeColor: 'red',
      content: (
        <div>
          <h4>Что такое «Аппаратный профиль» (Hardware Baseline)?</h4>
          <p>
            При первом подключении компьютера агент сканирует материнскую плату, точную модель процессора, серийные номера планок оперативной памяти, видеокарты и всех SSD/HDD накопителей. Эти данные сохраняются в системе как <strong>эталонный снимок (Baseline)</strong>.
          </p>
          <div className="faq-callout alert">
            <AlertTriangle size={18} />
            <div>
              <strong>Что произойдет, если кто-то снимет крышку системного блока и украдет деталь?</strong>
              <p>Например, из компьютера вытащили одну планку памяти 8 ГБ или подменили видеокарту RTX 4060 на старую GT 710:</p>
              <ul style={{ marginTop: '8px', paddingLeft: '18px' }}>
                <li>Компьютер в дашборде немедленно помечается красным статусом тревоги.</li>
                <li>В разделе <strong>«Оповещения»</strong> генерируется инцидент <em>«Hardware Tampering Alert: RAM Missing / GPU Changed»</em> с указанием точной модели пропавшей детали.</li>
                <li>В Telegram-чат службы безопасности моментально прилетает уведомление с указанием номера кабинета и имени ПК!</li>
              </ul>
            </div>
          </div>
          <h4>Мониторинг флешек и USB-устройств:</h4>
          <p>
            В разделе <strong>«Оборудование» ➔ «USB события»</strong> фиксируются все факты подключения и извлечения съемных накопителей: дата, точное время, производитель и емкость флешки.
          </p>
        </div>
      )
    },

    // -------------------------------------------------------------
    // ПОЛИТИКИ МОНИТОРИНГА
    // -------------------------------------------------------------
    {
      id: 'monitoring_policies',
      category: 'monitoring',
      title: 'Политики мониторинга: Какую выбрать для компьютера?',
      summary: 'Настройка частоты опроса метрик и правил генерации тревог под разные задачи.',
      badge: 'Политики',
      badgeColor: 'blue',
      content: (
        <div>
          <p>Для каждого устройства или целой группы можно назначить политику мониторинга:</p>
          <div className="faq-types-list">
            <div className="faq-type-row">
              <span className="faq-badge-chip blue">Полный мониторинг (Full)</span>
              <div>
                <strong>Опрос каждые 5–10 секунд</strong>
                <p>Собирает подробнейшие графики загрузки CPU, RAM, дисков, температуры, сети и топ процессов. Идеально для ключевых серверов, рабочих станций преподавателей и игровых ПК.</p>
              </div>
            </div>
            <div className="faq-type-row">
              <span className="faq-badge-chip amber">Только критические сбои (Critical Only)</span>
              <div>
                <strong>Экономичный режим (опрос раз в 60 сек)</strong>
                <p>Тревоги генерируются только при критическом перегреве, заполнении диска C: более 95% или зависании операционной системы. Экономит трафик в удаленных филиалах.</p>
              </div>
            </div>
            <div className="faq-type-row">
              <span className="faq-badge-chip green">Только оборудование (Hardware Only)</span>
              <div>
                <strong>Слежение за сохранностью железа</strong>
                <p>Следит только за комплектующими и антикражей (планки ОЗУ, диски, видеокарты). Графики процессов отключены.</p>
              </div>
            </div>
            <div className="faq-type-row">
              <span className="faq-badge-chip muted">Режим без звука (Muted)</span>
              <div>
                <strong>Временная тишина</strong>
                <p>Используется, когда компьютер находится на ремонте, переустановке Windows или плановом обслуживании. Уведомления не будут спамить в чат.</p>
              </div>
            </div>
          </div>
        </div>
      )
    },

    // -------------------------------------------------------------
    // TELEGRAM-БОТ
    // -------------------------------------------------------------
    {
      id: 'telegram_integration',
      category: 'telegram',
      title: 'Как подключить Telegram-бота и управлять парком со смартфона?',
      summary: 'Получение мгновенных алертов и управление питанием прямо из мессенджера через интерактивные кнопки.',
      badge: 'Telegram Bot',
      badgeColor: 'blue',
      content: (
        <div>
          <p>Интеграция с Telegram позволяет системному администратору реагировать на аварии за считанные секунды прямо с телефона.</p>
          <h4>Пошаговая настройка за 2 минуты:</h4>
          <ol className="faq-steps-list">
            <li>
              <strong>Создайте бота в Telegram:</strong>
              <p>Откройте в Telegram официального бота <strong>@BotFather</strong>, отправьте команду <code>/newbot</code>, задайте имя (например, <em>FleetMonitorBot</em>) и скопируйте полученный <strong>HTTP API Token</strong> вида <code>123456789:AAH...</code>.</p>
            </li>
            <li>
              <strong>Вставьте токен в панели управления:</strong>
              <p>В левом меню перейдите в <strong>«Telegram»</strong>, вставьте токен в поле «Bot Token» и нажмите «Сохранить токен».</p>
            </li>
            <li>
              <strong>Получите Chat ID:</strong>
              <p>Запустите вашего созданного бота, отправив ему сообщение <code>/start</code>. Если хотите получать тревоги в групповой чат IT-отдела — добавьте бота в группу и напишите любое сообщение. Нажмите в панели кнопку «Проверить соединение» — бот сам определит ваш Chat ID!</p>
            </li>
          </ol>
          <div className="faq-callout tip">
            <Zap size={18} />
            <div>
              <strong>Кнопки действий прямо под сообщениями в Telegram:</strong>
              <p>Когда бот присылает алерт (например: «⚠️ ПК-204 перегрелся до 92°C»), под сообщением появляются интерактивные кнопки: <strong>[🔄 Перезагрузить]</strong>, <strong>[🛑 Выключить]</strong> и <strong>[✅ Принять]</strong>. Нажмите кнопку прямо в мессенджере — сервер выполнит действие мгновенно!</p>
            </div>
          </div>
        </div>
      )
    },

    // -------------------------------------------------------------
    // РОЛИ И ЗОНЫ (SCOPES)
    // -------------------------------------------------------------
    {
      id: 'users_roles_scopes',
      category: 'users_roles',
      title: 'Роли пользователей и Зоны ответственности (Scopes)',
      summary: 'Разграничение прав: кто может только смотреть, а кто — выключать и настраивать компьютеры.',
      badge: 'Безопасность доступа',
      badgeColor: 'purple',
      content: (
        <div>
          <h4>В системе настроены 4 базовые роли:</h4>
          <div className="faq-roles-grid">
            <div className="faq-role-card">
              <div className="faq-role-head">
                <span className="badge blue">Суперадминистратор</span>
              </div>
              <p>Абсолютный доступ ко всем возможностям: добавление администраторов, изменение системных токенов, аудит действий, настройки Telegram, удаление устройств.</p>
            </div>
            <div className="faq-role-card">
              <div className="faq-role-head">
                <span className="badge green">Администратор парка</span>
              </div>
              <p>Управление компьютерами, группами, питанием, расписаниями и политиками. Не может удалять главных админов и менять глобальные ключи шифрования.</p>
            </div>
            <div className="faq-role-card">
              <div className="faq-role-head">
                <span className="badge amber">Оператор</span>
              </div>
              <p>Дежурный специалист: может включать компьютеры перед уроками, перезагружать зависшие ПК и закрывать процессы в разрешенных аудиториях.</p>
            </div>
            <div className="faq-role-card">
              <div className="faq-role-head">
                <span className="badge muted">Наблюдатель (Viewer)</span>
              </div>
              <p>Только чтение: просмотр статусов устройств, графиков нагрузки и температуры без права нажимать кнопки питания.</p>
            </div>
          </div>
          <h4>Что такое «Зоны ответственности» (Scopes)?</h4>
          <p>
            Если у вас огромный университет или завод из нескольких корпусов, вы можете ограничить видимость компьютеров для конкретного сотрудника. Например:
          </p>
          <div className="faq-code-block">
            <code>Корпус 2 / Этаж 3 / Кабинет 305</code>
          </div>
          <p>
            Оператор с такой зоной увидит в своем интерфейсе только компьютеры из кабинета 305 и физически не сможет случайно выключить сервер в лаборатории другого здания!
          </p>
        </div>
      )
    },

    // -------------------------------------------------------------
    // ГРУППЫ И АУДИТОРИИ
    // -------------------------------------------------------------
    {
      id: 'groups_management',
      category: 'groups',
      title: 'Группировка: Здания, Этажи, Кабинеты и Пакетные действия',
      summary: 'Как организовать сотни компьютеров в понятное дерево и управлять аудиториями в один клик.',
      badge: 'Организация',
      badgeColor: 'blue',
      content: (
        <div>
          <p>
            В разделе <strong>«Группы»</strong> компьютеры раскладываются по удобной иерархической структуре:
          </p>
          <div className="faq-tree-preview">
            <div>🏢 <strong>Главный корпус</strong></div>
            <div style={{ paddingLeft: '20px' }}>📁 Этаж 1</div>
            <div style={{ paddingLeft: '40px' }}>🖥️ Кабинет 101 (Информатика — 25 ПК)</div>
            <div style={{ paddingLeft: '40px' }}>🖥️ Кабинет 102 (Физика — 15 ПК)</div>
            <div style={{ paddingLeft: '20px' }}>📁 Этаж 2</div>
            <div style={{ paddingLeft: '40px' }}>🖥️ Кабинет 204 (Мультимедиа — 30 ПК)</div>
          </div>
          <h4>Пакетные операции (Массовое управление):</h4>
          <p>
            Вам не нужно нажимать кнопку на каждом из 30 компьютеров по очереди! Откройте нужный кабинет и воспользуйтесь кнопкой <strong>«Действия над группой»</strong>:
          </p>
          <ul>
            <li><strong>Включить все (WoL)</strong> — пошлет команду пробуждения на все 30 компьютеров за 1 клик перед началом занятий.</li>
            <li><strong>Выключить все</strong> — аккуратно завершит работу всех ПК кабинета после уроков.</li>
            <li><strong>Перезагрузить все</strong> — обновит конфигурацию машин в классе.</li>
          </ul>
        </div>
      )
    },

    // -------------------------------------------------------------
    // РАСПИСАНИЯ И CRON
    // -------------------------------------------------------------
    {
      id: 'schedules_cron',
      category: 'schedules',
      title: 'Автоматизация: Расписания включения/выключения по таймеру',
      summary: 'Экономия электроэнергии и продление ресурса компьютеров с помощью автоматических расписаний.',
      badge: 'Энергосбережение',
      badgeColor: 'green',
      content: (
        <div>
          <p>
            Забытые на ночь включенные компьютеры тратят сотни киловатт электроэнергии и изнашивают вентиляторы. С помощью раздела <strong>«Расписания»</strong> система сделает всё сама:
          </p>
          <h4>Как настроить авто-выключение на каждый день:</h4>
          <ol className="faq-steps-list">
            <li>Перейдите в раздел <strong>«Расписания»</strong> и нажмите <strong>«+ Создать расписание»</strong>.</li>
            <li>Укажите понятное название, например: <em>«Вечернее отключение аудиторий»</em>.</li>
            <li>Выберите действие: <strong>«Выключить (Shutdown)»</strong>.</li>
            <li>Выберите целевую группу (например, <em>«Все учебные классы»</em>).</li>
            <li>Задайте время выполнения (например, каждый будний день в <code>20:30</code>) или используйте cron-маску <code>30 20 * * 1-5</code>.</li>
            <li>Нажмите <strong>«Сохранить»</strong>.</li>
          </ol>
          <div className="faq-callout tip">
            <CheckCircle2 size={18} />
            <div>
              <strong>Утренний авто-прогрев:</strong>
              <p>Точно так же можно настроить автоматическое включение через Wake-on-LAN в <code>08:15</code> утра с понедельника по субботу, чтобы к приходу преподавателей и студентов все компьютеры уже были загружены и готовы к работе!</p>
            </div>
          </div>
        </div>
      )
    },

    // -------------------------------------------------------------
    // РЕШЕНИЕ ПРОБЛЕМ (TROUBLESHOOTING)
    // -------------------------------------------------------------
    {
      id: 'troubleshoot_offline',
      category: 'troubleshooting',
      title: 'Компьютер включен, но в системе горит серым (Офлайн)',
      summary: 'Быстрая диагностика потери связи между агентом и сервером управления.',
      badge: 'Диагностика',
      badgeColor: 'red',
      content: (
        <div>
          <h4>Чек-лист решения проблемы:</h4>
          <ol className="faq-steps-list">
            <li>
              <strong>Проверьте статус службы на компьютере:</strong>
              <p>Нажмите <code>Win + R</code>, введите <code>services.msc</code> и нажмите Enter. Найдите службу <strong>DashAgent</strong>. Убедитесь, что её состояние — <em>«Выполняется»</em> (Running). Если она остановлена — нажмите «Запустить».</p>
            </li>
            <li>
              <strong>Проверьте доступность сервера в браузере:</strong>
              <p>На проблемном компьютере откройте браузер и перейдите по адресу: <code>http://&lt;IP_ВАШЕГО_СЕРВЕРА&gt;:2301/api/v1/health</code>. Должно появиться сообщение <code>{`{"status":"ok"}`}</code>. Если страница не открывается — проверьте сетевой кабель или маршрутизатор.</p>
            </li>
            <li>
              <strong>Проверьте Брандмауэр / Антивирус (Kaspersky, Dr.Web, Windows Defender):</strong>
              <p>Убедитесь, что фаервол на сервере не блокирует входящие подключения по порту <strong>TCP 2301</strong> (веб-интерфейс и API) и <strong>UDP 48123</strong> (быстрые команды агента).</p>
            </li>
          </ol>
        </div>
      )
    },
    {
      id: 'troubleshoot_wol_fail',
      category: 'troubleshooting',
      title: 'Компьютер не включается по кнопке Wake-on-LAN',
      summary: 'Почему выключенный компьютер может игнорировать сетевой магический пакет.',
      badge: 'Wake-on-LAN',
      badgeColor: 'amber',
      content: (
        <div>
          <h4>Самые частые причины:</h4>
          <ul>
            <li><strong>Компьютер подключен по Wi-Fi:</strong> Wake-on-LAN работает исключительно через проводной сетевой кабель Ethernet RJ-45.</li>
            <li><strong>Компьютер был полностью обесточен из розетки:</strong> После отключения сетевого фильтра или кабеля 220В сетевая карта теряет дежурное питание (+5VSB). Включите компьютер кнопкой на корпусе один раз — после штатного выключения WoL снова заработает.</li>
            <li><strong>Включен «Быстрый запуск Windows»:</strong> Windows 10/11 по умолчанию при выключении переводит компьютер в гибридный сон с обесточиванием адаптера. Отключите его в настройках электропитания Windows.</li>
            <li><strong>Неправильно указан MAC-адрес:</strong> Проверьте MAC-адрес в карточке устройства (он должен совпадать со значением команды <code>getmac /v</code> на самом компьютере).</li>
          </ul>
        </div>
      )
    },
    {
      id: 'troubleshoot_server_ip_change',
      category: 'troubleshooting',
      title: 'Сервер переехал на другой IP-адрес — что делать с агентами?',
      summary: 'Как переключить установленные агенты на новый адрес сервера без переустановки.',
      badge: 'Миграция сервера',
      badgeColor: 'blue',
      content: (
        <div>
          <p>Если у вашего центрального сервера изменился локальный IP-адрес (например, был <code>192.168.1.109</code>, а стал <code>192.168.0.200</code>):</p>
          <div className="faq-callout info">
            <Info size={18} />
            <div>
              <strong>Встроенный авто-поиск:</strong>
              <p>Агенты оснащены механизмом резервного вещания в подсеть: если сервер недоступен более 5 минут, агент пытается обнаружить новый адрес сервера по широковещательному маяку.</p>
            </div>
          </div>
          <p>Также вы можете моментально обновить адрес сервера на клиентах короткой командой в PowerShell:</p>
          <div className="faq-code-block">
            <code>Set-ItemProperty -Path "HKLM:\Software\DashAgent" -Name "ServerUrl" -Value "http://НОВЫЙ_IP:2301"; Restart-Service DashAgent</code>
          </div>
        </div>
      )
    }
  ];

  // Filtered articles
  const filteredArticles = useMemo(() => {
    return articles.filter(article => {
      const matchesCategory = activeCategory === 'all' || article.category === activeCategory;
      if (!matchesCategory) return false;

      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        article.title.toLowerCase().includes(q) ||
        article.summary.toLowerCase().includes(q) ||
        article.category.toLowerCase().includes(q)
      );
    });
  }, [articles, activeCategory, searchQuery]);

  if (!isOpen) return null;

  return (
    <div className="faq-modal-backdrop" onClick={onClose}>
      <div className="faq-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="faq-modal-header">
          <div className="faq-header-title-box">
            <div className="faq-header-icon">
              <CircleHelp size={24} />
            </div>
            <div>
              <h2>База знаний и руководство пользователя</h2>
              <p>Полноценная интерактивная инструкция по всем действиям, кнопкам и функциям системы</p>
            </div>
          </div>
          <button className="faq-close-btn" onClick={onClose} title="Закрыть справку (Esc)">
            <X size={20} />
          </button>
        </div>

        {/* Search Bar */}
        <div className="faq-search-wrapper">
          <div className="faq-search-box">
            <Search size={18} className="faq-search-icon" />
            <input
              type="text"
              placeholder="Поиск по инструкции (например: подключить ПК, токен, Wake-on-LAN, снять процесс, антикража, telegram)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
            />
            {searchQuery && (
              <button className="faq-search-clear" onClick={() => setSearchQuery('')}>
                <X size={15} />
              </button>
            )}
          </div>
        </div>

        {/* Main layout: Category sidebar + Content */}
        <div className="faq-body-layout">
          {/* Categories bar */}
          <div className="faq-categories-bar">
            {categories.map((cat) => {
              const Icon = cat.icon;
              const isActive = activeCategory === cat.id;
              const count = cat.id === 'all'
                ? articles.length
                : articles.filter(a => a.category === cat.id).length;
              return (
                <button
                  key={cat.id}
                  className={`faq-category-btn ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    setActiveCategory(cat.id);
                  }}
                >
                  <Icon size={16} />
                  <span className="faq-category-name">{cat.label}</span>
                  <span className="faq-category-count">{count}</span>
                </button>
              );
            })}
          </div>

          {/* Articles list */}
          <div className="faq-articles-scroll">
            {filteredArticles.length === 0 ? (
              <div className="faq-empty-results">
                <CircleHelp size={48} className="text-muted" />
                <h3>Ничего не найдено</h3>
                <p>По запросу «{searchQuery}» статей не найдено. Попробуйте сформулировать запрос иначе или выберите тему из списка слева.</p>
                <button className="faq-reset-btn" onClick={() => { setSearchQuery(''); setActiveCategory('all'); }}>
                  Сбросить фильтры
                </button>
              </div>
            ) : (
              <div className="faq-articles-list">
                {filteredArticles.map((article) => {
                  const isExpanded = expandedArticleId === article.id;
                  return (
                    <div
                      key={article.id}
                      className={`faq-article-card ${isExpanded ? 'expanded' : ''}`}
                    >
                      <div
                        className="faq-article-header"
                        onClick={() => setExpandedArticleId(isExpanded ? null : article.id)}
                      >
                        <div className="faq-article-header-left">
                          <div className="faq-expand-chevron">
                            {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                          </div>
                          <div>
                            <div className="faq-article-meta">
                              {article.badge && (
                                <span className={`faq-article-badge ${article.badgeColor || 'blue'}`}>
                                  {article.badge}
                                </span>
                              )}
                            </div>
                            <h3 className="faq-article-title">{article.title}</h3>
                            <p className="faq-article-summary">{article.summary}</p>
                          </div>
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="faq-article-content">
                          {article.content}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="faq-modal-footer">
          <div className="faq-footer-tip">
            <span className="pulse-dot" />
            <span>Инструкция обновлена и синхронизирована с текущей версией системы управления парком ПК.</span>
          </div>
          <button className="faq-close-action-btn" onClick={onClose}>
            Понятно, закрыть справку
          </button>
        </div>
      </div>
    </div>
  );
};
