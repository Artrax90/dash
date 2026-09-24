import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  CircleHelp, Search, X, ChevronRight, Copy, Check, Terminal,
  Key, Power, ShieldAlert, Users, Bot, Calendar, Cpu, Layers, AlertTriangle,
  CheckCircle2, Info, Laptop, Zap, RefreshCw, LogOut, Wrench, ShieldCheck,
  Radio, HardDrive, Usb, ArrowRight, ExternalLink, Archive, RotateCcw,
  FileSpreadsheet, FileText, Shield, Bell
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
  const [expandedArticleIds, setExpandedArticleIds] = useState<Set<string>>(() => new Set(['engineer_master_guide']));
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const articleRefs = useRef<{ [id: string]: HTMLDivElement | null }>({});

  const toggleArticle = (id: string) => {
    setExpandedArticleIds((prev) => {
      const next = new Set(prev);
      const isExpanding = !next.has(id);
      if (isExpanding) {
        next.add(id);
        // Smoothly scroll the container so the article header is aligned near the top
        requestAnimationFrame(() => {
          setTimeout(() => {
            const container = scrollContainerRef.current;
            const card = articleRefs.current[id];
            if (container && card) {
              const containerRect = container.getBoundingClientRect();
              const cardRect = card.getBoundingClientRect();
              const targetScroll = container.scrollTop + (cardRect.top - containerRect.top) - 12;
              container.scrollTo({
                top: Math.max(0, targetScroll),
                behavior: 'smooth'
              });
            }
          }, 40);
        });
      } else {
        next.delete(id);
      }
      return next;
    });
  };

  // Reset scroll position on category or search changes
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
  }, [activeCategory, searchQuery]);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => {
      setCopiedKey(null);
    }, 2000);
  };

  const categories = [
    { id: 'all', label: 'Все темы', icon: CircleHelp },
    { id: 'engineer_guide', label: 'Инструкция инженера (Раскатка)', icon: Wrench },
    { id: 'quickstart', label: 'Быстрый старт и Агенты', icon: Laptop },
    { id: 'tokens', label: 'Токены безопасности', icon: Key },
    { id: 'power', label: 'Питание и Wake-on-LAN', icon: Power },
    { id: 'processes', label: 'Процессы и Сессии', icon: Zap },
    { id: 'hardware', label: 'Антикража и Железо', icon: Cpu },
    { id: 'archive_itilium', label: 'Архив и 1С:Итилиум', icon: Archive },
    { id: 'monitoring', label: 'Политики и Отчёты', icon: ShieldCheck },
    { id: 'telegram', label: 'Telegram-уведомления', icon: Bot },
    { id: 'users_roles', label: 'Роли и Зоны (Scopes)', icon: Users },
    { id: 'groups', label: 'Группы и Аудитории', icon: Layers },
    { id: 'schedules', label: 'Расписания и Cron', icon: Calendar },
    { id: 'troubleshooting', label: 'Решение проблем', icon: Wrench },
  ];

  const articles: FaqArticle[] = [
    // -------------------------------------------------------------
    // ПОШАГОВАЯ ИНСТРУКЦИЯ ДЛЯ ИНЖЕНЕРА (РАСКАТКА ПО АУДИТОРИЯМ)
    // -------------------------------------------------------------
    {
      id: 'engineer_master_guide',
      category: 'engineer_guide',
      title: 'Пошаговая шпаргалка инженера: Как раскатать агенты в кабинете (Инструкция на пальцах)',
      summary: 'Сначала создаём кабинет и токен в панели, скачиваем .bat на флешку, и только потом идём раскатывать по 20 сек на ПК.',
      badge: 'Золотой стандарт раскатки',
      badgeColor: 'green',
      content: (
        <div>
          <p>
            Главное правило быстрой и безошибочной раскатки парка: <br />
            <strong>Сначала за 2 минуты подготовьте Кабинет и Токен в веб-панели за рабочим столом, и только потом идите в аудиторию с флешкой!</strong>
          </p>
          <div className="faq-grid-badges">
            <div className="faq-mini-card">
              <strong>🏢 1. Кабинет в панели</strong>
              <span>Создайте структуру: Здание → Этаж → Кабинет</span>
            </div>
            <div className="faq-mini-card">
              <strong>🔑 2. Токен под кабинет</strong>
              <span>Сервер свяжет токен с этой конкретной аудиторией</span>
            </div>
            <div className="faq-mini-card">
              <strong>💾 3. Скачать .bat на флешку</strong>
              <span>IP сервера, токен и аудитория уже зашиты внутри</span>
            </div>
            <div className="faq-mini-card">
              <strong>⚡ 4. По 20 сек на ПК</strong>
              <span>ПКМ → Запуск от имени администратора → Готово</span>
            </div>
          </div>

          <h4 style={{ marginTop: '16px', marginBottom: '8px', color: 'var(--text)' }}>Фаза 1: Подготовка за своим столом (2 минуты ДО выхода в аудиторию):</h4>
          <ol className="faq-steps-list">
            <li>
              <strong>Создайте кабинет в структуре организации (раздел «Группы»):</strong>
              <p>
                Зайдите в раздел <strong>«Группы»</strong>. Если вашей аудитории еще нет в списке, нажмите <strong>«+ Создать группу»</strong> и заполните путь:
                <br /><code>Здание: Главный корпус</code> → <code>Этаж: 4 этаж</code> → <code>Кабинет: Кабинет 401</code>.
              </p>
            </li>
            <li>
              <strong>Сгенерируйте Токен с привязкой к этому кабинету (раздел «Агенты»):</strong>
              <p>
                Перейдите в раздел <strong>«Агенты»</strong> → нажмите кнопку <strong>«Сгенерировать токен»</strong> (или вкладку «Токены регистрации»).
                В поле «Целевая группа/кабинет» выберите созданную аудиторию: <code>Главный корпус / 4 этаж / Кабинет 401</code>.
              </p>
              <div className="faq-callout tip" style={{ margin: '8px 0' }}>
                <Key size={18} />
                <div>
                  <strong>Зачем нужен токен и почему это важно?</strong>
                  <p>
                    Токен — это электронный пропуск безопасности сервера. Привязка токена к кабинету избавляет вас от ручной рутины:
                    каждый компьютер, настроенный с этой флешки, <strong>автоматически встанет в Кабинет 401</strong>, получит расписание звонков и правила алертов без ручной сортировки!
                  </p>
                </div>
              </div>
            </li>
            <li>
              <strong>Скачайте готовый .bat файл прямо на флешку:</strong>
              <p>
                В строке созданного токена нажмите кнопку <strong>«Скачать .bat установщик»</strong> (или верхнюю синюю кнопку «Скачать установщик Windows»).
                Сохраните файл <code>Install-WorkstationAgent.bat</code> прямо в корень обычной флешки.
              </p>
            </li>
          </ol>

          <h4 style={{ marginTop: '20px', marginBottom: '8px', color: 'var(--text)' }}>Фаза 2: Действия в аудитории (20 секунд у каждого компьютера):</h4>
          <ol className="faq-steps-list">
            <li>
              <strong>Включите ПК и войдите под учетной записью администратора:</strong>
              <p>Дождитесь загрузки рабочего стола Windows.</p>
            </li>
            <li>
              <strong>Вставьте флешку и откройте её в Проводнике:</strong>
              <p>Найдите файл <code>Install-WorkstationAgent.bat</code>.</p>
            </li>
            <li>
              <strong style={{ color: 'var(--amber, #f59e0b)' }}>ВНИМАНИЕ! САМЫЙ ВАЖНЫЙ ШАГ (Главная ошибка новичков):</strong>
              <p>
                <strong>НЕ нажимайте два раза левой кнопкой мыши!</strong> Обычный запуск ЛКМ блокируется системой контроля учетных записей Windows, и служба не сможет прописаться в автозагрузку.
              </p>
              <div className="faq-callout alert" style={{ margin: '8px 0' }}>
                <AlertTriangle size={18} />
                <div>
                  <strong>Как запускать правильно:</strong>
                  <p>
                    Нажмите по файлу <code>Install-WorkstationAgent.bat</code> <strong>ПРАВОЙ кнопкой мыши</strong> и выберите пункт меню: <br />
                    👉 <strong>«Запуск от имени администратора»</strong> (со значком сине-желтого щита 🛡️).
                  </p>
                </div>
              </div>
            </li>
            <li>
              <strong>Подтвердите запуск в окне контроля UAC:</strong>
              <p>Нажмите кнопку <strong>«Да»</strong>.</p>
            </li>
            <li>
              <strong>Подождите ровно 5 секунд:</strong>
              <p>
                Откроется черное окно консоли. В нем пробегут строчки:
                <br /><code>[1/4] Проверка прав администратора... ОК</code>
                <br /><code>[2/4] Регистрация системной задачи WorkstationManagerAgent... ОК</code>
                <br /><code>[3/4] Открытие порта 48123 UDP в Брандмауэре Windows... ОК</code>
                <br /><code>[4/4] Сбор характеристик железа и отправка на сервер... ОК</code>
                <br /><strong>После этого окно САМО закроется. Ничего нажимать не нужно!</strong>
              </p>
            </li>
            <li>
              <strong>Вытащите флешку и переходите к следующему компьютеру:</strong>
              <p>
                Машина уже зарегистрирована, отправляет телеметрию в фоне и отображается в созданном кабинете.
              </p>
            </li>
          </ol>
        </div>
      )
    },
    {
      id: 'engineer_tokens_and_groups',
      category: 'engineer_guide',
      title: 'Зачем нужен токен и почему кабинет нужно создавать ДО похода с флешкой (Секрет автопривязки)',
      summary: 'Что такое токен регистрации, зачем он нужен и как связка «Кабинет → Токен → Флешка» исключает ручную сортировку компьютеров.',
      badge: 'Секрет быстрой раскатки',
      badgeColor: 'amber',
      content: (
        <div>
          <p>
            Очень часто начинающие инженеры сначала скачивают дефолтный скрипт, обходят 30 компьютеров, а потом тратят час на то,
            чтобы вручную перетаскивать каждый компьютер из кучи «Нераспределенные» в нужный класс.
          </p>
          <p>
            Система умеет делать это <strong>автоматически</strong> благодаря механизму токенов привязки.
          </p>

          <h4 style={{ marginTop: '16px', marginBottom: '8px', color: 'var(--text)' }}>Что такое Токен (FLEET_JOIN_TOKEN)?</h4>
          <p>
            Токен (например: <code>wm_tok_7f8a92b3c4d5e6f7</code>) — это зашифрованный электронный ключ-пароль сервера управления.
          </p>
          <div className="faq-grid-badges">
            <div className="faq-mini-card">
              <strong>🛡️ 1. Защита от чужих устройств</strong>
              <span>Посторонний ноутбук или студент из сети Wi-Fi не сможет слать фейковые данные на сервер без токена.</span>
            </div>
            <div className="faq-mini-card">
              <strong>🎯 2. Автоматическая привязка к классу</strong>
              <span>Сервер связывает токен с кабинетом. Все ПК с этой флешки сразу попадают в свою аудиторию!</span>
            </div>
          </div>

          <h4 style={{ marginTop: '20px', marginBottom: '8px', color: 'var(--text)' }}>Правильный порядок подготовки (ДО выхода в аудиторию):</h4>
          <ol className="faq-steps-list">
            <li>
              <strong>Шаг 1: Зайдите в раздел «Группы»:</strong>
              <p>Убедитесь, что кабинет есть в иерархии (Здание → Этаж → Кабинет). Если нет — создайте его за 15 секунд.</p>
            </li>
            <li>
              <strong>Шаг 2: Зайдите в раздел «Агенты» → «Токены регистрации»:</strong>
              <p>Нажмите <strong>«+ Сгенерировать токен»</strong>. В выпадающем списке «Целевой кабинет/группа» выберите ваш созданный класс.</p>
            </li>
            <li>
              <strong>Шаг 3: Скачайте файл установщика:</strong>
              <p>
                Нажмите кнопку <strong>«Скачать .bat установщик»</strong>. Имя файла будет содержать название кабинета (например, <code>Install-WorkstationAgent-Кабинет401.bat</code>).
              </p>
            </li>
            <li>
              <strong>Шаг 4: Запишите файл на флешку:</strong>
              <p>
                Теперь установщик несёт в себе и секретный ключ, и команду серверу: <em>«Помести этот компьютер сразу в Кабинет 401»</em>.
                При раскатке вам останется только запускать его от администратора!
              </p>
            </li>
          </ol>
        </div>
      )
    },
    {
      id: 'engineer_flashdrive_prep',
      category: 'engineer_guide',
      title: 'Подготовка флешки перед выходом в аудитории (1 минута на подготовку)',
      summary: 'Где взять правильный файл установщика и как скинуть его на флешку перед походом по этажам.',
      badge: 'Подготовка к выезду',
      badgeColor: 'blue',
      content: (
        <div>
          <p>Перед тем как идти по кабинетам, подготовьте флешку на своем рабочем компьютере или ноутбуке:</p>
          <ol className="faq-steps-list">
            <li>
              <strong>Возьмите любую флешку:</strong>
              <p>Подойдет совершенно любая флешка любого размера (хоть на 1 ГБ, хоть на 64 ГБ), файл установщика весит всего несколько килобайт.</p>
            </li>
            <li>
              <strong>Откройте панель управления в браузере:</strong>
              <p>Зайдите в панель Workstation Manager под своей учетной записью.</p>
            </li>
            <li>
              <strong>Скачайте файл установщика:</strong>
              <p>В левом меню перейдите в раздел <strong>«Агенты»</strong>. В верхней части страницы нажмите большую синюю кнопку <strong>«Скачать пакетный .bat установщик»</strong> (или скачайте из строки нужного токена).</p>
            </li>
            <li>
              <strong>Скопируйте файл на флешку:</strong>
              <p>
                В папке «Загрузки» появится файл <code>Install-WorkstationAgent.bat</code>. Скопируйте его прямо в корень вашей флешки (чтобы потом не искать его по вложенным папкам).
              </p>
            </li>
          </ol>
          <div className="faq-callout info">
            <Info size={18} />
            <div>
              <strong>В чём секрет этого файла?</strong>
              <p>
                Когда вы нажимаете кнопку скачивания в панели, сервер автоматически вшивает внутрь файла текущий IP-адрес вашего сервера, действующий токен безопасности и привязанную группу. Вам <strong>не нужно ничего редактировать внутри файла</strong> — он полностью готов к работе сразу «из коробки».
              </p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'engineer_bios_faststartup',
      category: 'engineer_guide',
      title: 'Настройка BIOS и отключение «Быстрого запуска» (Чтобы ПК включались по сети и расписанию)',
      summary: 'Две обязательные настройки, без которых компьютеры не смогут просыпаться по расписанию и кнопке WoL.',
      badge: 'Обязательно для Wake-on-LAN',
      badgeColor: 'amber',
      content: (
        <div>
          <p>
            Если вы хотите, чтобы компьютеры в кабинетах включались сами по утреннему расписанию или по кнопке «Включить (WoL)» со смартфона,
            на каждом компьютере нужно выполнить две простые настройки. Без них сетевая карта при выключении ПК полностью обесточивается.
          </p>

          <h4 style={{ marginTop: '16px', marginBottom: '8px', color: 'var(--text)' }}>Настройка 1: Отключение «Быстрого запуска» в Windows (15 секунд):</h4>
          <ol className="faq-steps-list">
            <li>Нажмите на клавиатуре комбинацию клавиш <code>Win + R</code> (откроется окно «Выполнить»).</li>
            <li>Введите <code>powercfg.cpl</code> и нажмите <strong>Enter</strong> (откроется стандартное окно «Электропитание»).</li>
            <li>В левой колонке нажмите ссылку <strong>«Действие кнопок питания»</strong>.</li>
            <li>В верхней части окна нажмите синюю ссылку со щитом: <strong>«Изменение параметров, которые сейчас недоступны»</strong>.</li>
            <li>
              Внизу окна найдите блок «Параметры завершения работы» и <strong style={{ color: 'var(--red, #ef4444)' }}>СНИМИТЕ ГАЛОЧКУ</strong> с пункта:
              <br /><code>[ ] Включить быстрый запуск (рекомендуется)</code>
            </li>
            <li>Нажмите кнопку <strong>«Сохранить изменения»</strong> внизу окна.</li>
          </ol>
          <div className="faq-callout alert">
            <AlertTriangle size={18} />
            <div>
              <strong>Почему это критично?</strong>
              <p>
                «Быстрый запуск» Windows вместо настоящего выключения уводит ядро в гибернацию и <em>наглухо обесточивает сетевой адаптер</em>.
                После снятия этой галочки сетевая карта всегда остаётся на дежурном питании (на ней горит маленький зеленый/оранжевый светодиод) и ждет магический пакет включения.
              </p>
            </div>
          </div>

          <h4 style={{ marginTop: '20px', marginBottom: '8px', color: 'var(--text)' }}>Настройка 2: Включение Wake-on-LAN в BIOS/UEFI материнской платы:</h4>
          <ol className="faq-steps-list">
            <li>При включении или перезагрузке компьютера непрерывно нажимайте клавишу <code>Del</code> или <code>F2</code>, пока не откроется BIOS.</li>
            <li>
              Перейдите в раздел управления питанием. В зависимости от производителя материнской платы он называется:
              <br />• ASUS: <em>Advanced → APM Configuration → Power On By PCI-E/PCI</em> → выставить <strong>Enabled</strong>.
              <br />• Gigabyte: <em>Power → ErP</em> → выставить <strong>Disabled</strong>, а <em>Wake on LAN</em> → <strong>Enabled</strong>.
              <br />• MSI: <em>Settings → Advanced → Wake Up Event Setup → Resume By PCI-E Device</em> → <strong>Enabled</strong>.
              <br />• HP / Dell / Lenovo: <em>Power Management → Wake on LAN</em> → <strong>LAN Only</strong> или <strong>LAN with Boot Support</strong>.
            </li>
            <li>Если в BIOS есть пункт <strong>ErP / EuP Ready</strong> (глубокое энергосбережение) — <strong>обязательно выключите его (Disabled)</strong>! Иначе плата не подает дежурные 3.3V на сетевую карту.</li>
            <li>Нажмите клавишу <strong>F10</strong> на клавиатуре и подтвердите сохранение настроек (<strong>Yes / Enter</strong>).</li>
          </ol>
        </div>
      )
    },
    {
      id: 'engineer_checklist_verify',
      category: 'engineer_guide',
      title: 'Чек-лист проверки: 3 простых способа убедиться за 5 секунд, что компьютер подключился',
      summary: 'Работающие команды PowerShell, проверка Планировщика задач, просмотр лога и индикация в веб-панели.',
      badge: 'Контроль качества',
      badgeColor: 'purple',
      content: (
        <div>
          <p>После того как вы запустили установщик и черное окно закрылось, проверьте результат любым удобным способом:</p>
          
          <div className="faq-callout warning" style={{ marginBottom: '16px' }}>
            <AlertTriangle size={18} />
            <div>
              <strong>Почему команда «Get-Service» не работает?</strong>
              <p>
                В Windows агент регистрируется <strong>НЕ как классическая служба Windows Service (services.msc)</strong>, а как <strong>системная задача в Планировщике Windows (Task Scheduler) под учетной записью SYSTEM</strong> с именем <code>WorkstationManagerAgent</code>. <br />
                Это сделано намеренно: благодаря этому агент работает абсолютно бесшумно в скрытом фоне, не показывает всплывающих окон пользователям, стартует вместе с компьютером и автоматически перезапускается системным сторожем. Поэтому команда <code>Get-Service</code> его не находит — используйте правильные команды ниже!
              </p>
            </div>
          </div>

          <div className="faq-steps-list">
            <div style={{ marginBottom: '16px' }}>
              <strong>Способ 1: Прямо на экране настраиваемого ПК в PowerShell (100% работающие команды)</strong>
              <p>Нажмите <code>Win + X</code> → выберите <strong>«Терминал (Администратор)»</strong> или <strong>«PowerShell»</strong>:</p>
              
              <p style={{ marginTop: '8px', marginBottom: '4px', fontWeight: 600 }}>1. Проверка системной задачи в Планировщике:</p>
              <div className="faq-code-block">
                <code>Get-ScheduledTask WorkstationManagerAgent</code>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>
                Статус <strong>Ready</strong> или <strong>Running</strong> означает, что задача успешно создана и служба активна.
              </p>

              <p style={{ marginTop: '8px', marginBottom: '4px', fontWeight: 600 }}>2. Просмотр последних строк журнала работы агента:</p>
              <div className="faq-code-block">
                <code>Get-Content "C:\Program Files\WorkstationManagerAgent\agent_service.log" -Tail 5</code>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>
                В журнале будут свежие строчки: <code>[OK] Service started... Heartbeat sent... 200 OK</code>.
              </p>

              <p style={{ marginTop: '8px', marginBottom: '4px', fontWeight: 600 }}>3. Проверка активного фонового процесса:</p>
              <div className="faq-code-block">
                <code>Get-CimInstance Win32_Process | Where-Object {`{ $_.CommandLine -like "*run_service.ps1*" }`}</code>
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <strong>Способ 2: В веб-интерфейсе со смартфона или рабочего ноутбука</strong>
              <p>Откройте панель управления во вкладке <strong>«Компьютеры»</strong> (или перейдите в созданный кабинет в «Группах»):</p>
              <ul style={{ paddingLeft: '20px', margin: '6px 0', fontSize: '13px', color: 'var(--muted)' }}>
                <li>Компьютер отображается с зеленым кружком 🟢 <strong>«В сети»</strong>.</li>
                <li>В его карточке сразу заполнены процессор, модель материнской платы, объем ОЗУ и диски.</li>
                <li>Если вы скачивали установщик с токеном кабинета — компьютер уже находится внутри своего кабинета!</li>
              </ul>
            </div>

            <div>
              <strong>Способ 3: В рабочем Telegram-боте</strong>
              <p>Если к вашей системе привязан Telegram-бот, при первом запуске агента вам в чат мгновенно прилетит уведомление:</p>
              <div className="faq-callout tip" style={{ margin: '8px 0' }}>
                <Bot size={18} />
                <div>
                  <strong>🟢 СВЯЗЬ ВОССТАНОВЛЕНА / ПК ВКЛЮЧЕН</strong>
                  <p>Устройство: <code>AUD401-PC05</code> • Компьютер включен и вышел на связь</p>
                </div>
              </div>
              <p>Прилетело уведомление — значит связь идеальная, можно вынимать флешку и переходить к следующему ПК!</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'engineer_group_binding',
      category: 'engineer_guide',
      title: 'Что делать, если раскатали без токена кабинета? (Ручная группировка)',
      summary: 'Если флешка была со стандартным токеном — как в 2 клика массово распределить 20 компьютеров в нужный кабинет.',
      badge: 'Резервный вариант',
      badgeColor: 'blue',
      content: (
        <div>
          <p>
            Если вы по ошибке раскатали аудиторию общим установщиком и компьютеры попали в группу по умолчанию «Нераспределенные»,
            не переживайте — распределить весь класс можно буквально в 2 клика:
          </p>
          <ol className="faq-steps-list">
            <li>Откройте панель управления, раздел <strong>«Компьютеры»</strong>.</li>
            <li>Отметьте галочками все новые компьютеры из этой аудитории (или используйте быстрый фильтр по IP-подсети).</li>
            <li>В верхней синей панели массовых действий нажмите кнопку <strong>«Назначить группу»</strong>.</li>
            <li>
              В появившемся окне выберите нужный кабинет: <br />
              <code>Главный корпус / 4 этаж / Кабинет 401</code>
            </li>
            <li>Нажмите синюю кнопку <strong>«Сохранить»</strong>.</li>
          </ol>
          <div className="faq-callout tip">
            <CheckCircle2 size={18} />
            <div>
              <strong>Что это даёт?</strong>
              <p>
                Теперь в разделе «Группы» эта аудитория выделится в отдельную плитку с кнопками:
                <br />⚡ <strong>«Включить весь класс»</strong> — разбудит все 20 компьютеров разом.
                <br />🛑 <strong>«Выключить весь класс»</strong> — завершит сеансы и выключит питание после занятий.
              </p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'quickstart_agent_intro',
      category: 'quickstart',
      title: 'Что такое Агент рабочей станции и как он устроен?',
      summary: 'Легковесная скрытая фоновая служба (менее 15 МБ), которая связывает компьютер с сервером управления.',
      badge: 'Базовые понятия',
      badgeColor: 'blue',
      content: (
        <div>
          <p>
            <strong>Агент рабочей станции (Workstation Agent)</strong> — это программа-помощник, которая устанавливается на целевой компьютер (Windows или Linux).
            Она работает в фоновом режиме (в Windows — как системная задача в Планировщике под учетной записью SYSTEM, в Linux — как демон systemd), не мешает пользователю и практически не потребляет ресурсы:
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
              <p>Скрипт автоматически скачает исполняемый файл агента, зарегистрирует скрытую системную задачу <code>WorkstationManagerAgent</code> в Планировщике Windows, создаст правило в Брандмауэре Windows для порта <code>48123 UDP</code> и передаст на сервер отпечаток оборудования. Компьютер сразу появится в списке!</p>
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
    {
      id: 'quickstart_ota_update',
      category: 'quickstart',
      title: 'Удалённое обновление агентов по сети (OTA)',
      summary: 'Как обновлять службу агента на компьютерах парка в один клик без физического доступа.',
      badge: 'Обновление OTA',
      badgeColor: 'blue',
      content: (
        <div>
          <p>
            Когда на сервере выходит новая версия агента (например, улучшенный сбор телеметрии или новые команды), вам не нужно заново ходить по кабинетам с флешкой или рассылать скрипты!
          </p>
          <h4>Как обновить агент на рабочей станции:</h4>
          <ol className="faq-steps-list">
            <li>
              <strong>Индикация доступного обновления:</strong>
              <p>В реестре устройств и карточке ПК компьютеры с устаревшей версией агента помечаются жёлтым значком (например: <em>«Доступно v2.9.21»</em>).</p>
            </li>
            <li>
              <strong>Запуск обновления в 1 клик:</strong>
              <p>В карточке компьютера нажмите кнопку <strong>«Обновить агент»</strong> (или выберите этот пункт в меню действий <code>...</code> строки таблицы).</p>
            </li>
            <li>
              <strong>Автоматический процесс:</strong>
              <p>Сервер передает агенту защищенную команду обновления. Агент в фоновом режиме скачивает актуальные модули с сервера, плавно перезапускает свою службу и сразу сообщает о готовности с новой версией. Компьютер при этом не перезагружается и пользователь не отвлекается!</p>
            </li>
          </ol>
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
    // АРХИВ И 1С:ИТИЛИУМ
    // -------------------------------------------------------------
    {
      id: 'archive_decommission',
      category: 'archive_itilium',
      title: 'Списание рабочих станций и системная группа «Архив»',
      summary: 'Правильный вывод компьютеров из эксплуатации с фиксацией причин для бухгалтерии и инвентаризаций.',
      badge: 'Списание в Архив',
      badgeColor: 'amber',
      content: (
        <div>
          <h4>Зачем нужна архивация вместо простого удаления?</h4>
          <p>
            При обычном удалении компьютера из базы стираются все его серийные номера, история железа и акты привязки. Если в конце года придёт инвентаризационная комиссия, в системе возникнет недостача!
          </p>
          <div className="faq-callout info">
            <Archive size={18} />
            <div>
              <strong>Принцип архивации в системе:</strong>
              <p>
                Компьютер переносится в специальную защищённую группу <strong>«Архив»</strong>. Для него отключаются постоянные пинги и сторожевые тревоги об офлайне, но <strong>полная конфигурация оборудования, серийные номера и дата вывода из строя сохраняются</strong>.
              </p>
            </div>
          </div>
          <h4>Как списать компьютер (пошагово):</h4>
          <ol className="faq-steps-list">
            <li>В карточке ПК или в меню действий <code>...</code> таблицы устройств нажмите <strong>«Списать / Удалить»</strong>.</li>
            <li>
              Выберите официальную причину списания:
              <ul style={{ marginTop: '6px', paddingLeft: '18px' }}>
                <li><strong>Неисправность / Выход из строя</strong> — сгорела материнская плата, процессор или блок питания.</li>
                <li><strong>Плановая замена / Моральное устаревание</strong> — закупка нового парка ПК взамен старого.</li>
                <li><strong>Разобран на комплектующие (ЗИП / Донор)</strong> — детали пошли на ремонт других компьютеров.</li>
                <li><strong>Передан в другой отдел / филиал</strong> — перемещение оборудования между подразделениями.</li>
                <li><strong>Утрата / Хищение</strong> — фиксация факта кражи или утери.</li>
                <li><strong>Ошибочно добавленный / Тестовый ПК (полное удаление)</strong> — <em>внимание: единственный пункт, который безвозвратно удаляет запись из базы данных</em>.</li>
              </ul>
            </li>
            <li>В поле «Примечание / Номер акта» введите номер приказа, акта списания или причину (например: <em>«Акт №48 от 10.09.2026, сгорел чипсет»</em>).</li>
            <li>Нажмите <strong>«Списать в Архив»</strong>.</li>
          </ol>
          <div className="faq-callout warning">
            <ShieldAlert size={18} />
            <div>
              <strong>Защита группы «Архив»:</strong>
              <p>Системная группа «Архив» защищена от случайного переименования или удаления. Это гарантирует, что архивные машины не потеряются в структуре отделов.</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'archive_restore',
      category: 'archive_itilium',
      title: 'Как вернуть компьютер из архива обратно в эксплуатацию?',
      summary: '4 простых способа восстановить рабочую станцию после ремонта или возврата из филиала.',
      badge: 'Восстановление',
      badgeColor: 'green',
      content: (
        <div>
          <p>
            Если компьютер отремонтировали (заменили блок питания/материнскую плату), вернули из временного отдела или вы случайно отправили его в архив — вернуть его в строй можно за секунду!
          </p>
          <h4>4 удобных способа возврата:</h4>
          <ol className="faq-steps-list">
            <li>
              <strong>В 1 клик в карточке станции (самый быстрый):</strong>
              <p>Откройте карточку архивного ПК. В самом верху в жёлтой плашке списания нажмите кнопку <strong>«Вернуть из архива»</strong> (с иконкой ↺). Станция моментально вернётся в строй!</p>
            </li>
            <li>
              <strong>Через контекстное меню в таблице:</strong>
              <p>В разделе <strong>«Устройства»</strong> отфильтруйте группу «Архив», нажмите три точки <code>...</code> в строке компьютера и выберите пункт <strong>«Вернуть из архива»</strong>.</p>
            </li>
            <li>
              <strong>В режиме плиток (Grid View):</strong>
              <p>В отображении плитками у архивных компьютеров доступна прямая кнопка <strong>«Из архива»</strong>.</p>
            </li>
            <li>
              <strong>Через окно «Настройки и группы»:</strong>
              <p>Нажмите «Настройки и группы» (шестерёнка) и вместо группы «Архив» выберите любую рабочую группу (например, <em>Office</em> или <em>Кабинет 101</em>). Система автоматически поймет смену группы и снимет с ПК статус списания.</p>
            </li>
          </ol>
          <div className="faq-callout tip">
            <CheckCircle2 size={18} />
            <div>
              <strong>Что происходит при возврате:</strong>
              <p>Сервер очищает поля причины и даты списания, возобновляет проверку доступности и алертинг, а в выгрузках для 1С:Итилиум статус автоматически возвращается в <strong>«В эксплуатации»</strong>.</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'itilium_integration_export',
      category: 'archive_itilium',
      title: 'Выгрузка спецификации оборудования для 1С:Итилиум (.xlsx)',
      summary: 'Формирование точной описи компьютеров со штрихкодами КЕ, статусами и серийными номерами для CMDB.',
      badge: '1С:Итилиум',
      badgeColor: 'blue',
      content: (
        <div>
          <p>
            Интеграция с конфигурацией <strong>1С:Итилиум (Service Desk / ITIL CMDB)</strong> позволяет автоматически выгружать детальную аппаратную опись компьютеров для мгновенного импорта в базу данных 1С.
          </p>
          <h4>Где сформировать выгрузку:</h4>
          <p>
            Кнопка <strong>«Выгрузка в Итилиум»</strong> с иконкой таблицы доступна в разделах <strong>«Мониторинг»</strong> (рядом с экспортом отчетов) и <strong>«Устройства»</strong>. Вы можете выгрузить как весь парк целиком, так и конкретную аудиторию или корпус, применив фильтр.
          </p>
          <h4>Особенности структуры отчёта для 1С:</h4>
          <ul>
            <li><strong>Прямой импорт без сбоев:</strong> таблица сформирована строго со строки 1 (заголовки колонок) и строки 2 (данные), без лишних декоративных шапок и объединенных ячеек, которые обычно ломают типовой парсер Excel в 1С.</li>
            <li><strong>Колонка «Штрих-код КЕ»:</strong> содержит уникальный инвентарный номер компьютера для быстрой идентификации конфигурационной единицы сканером штрихкодов.</li>
            <li><strong>Колонка «Статус КЕ»:</strong> для активных станций указывается <code>В эксплуатации</code>, а для архивных — <code>Выведен из эксплуатации (Причина: ..., ДД.ММ.ГГГГ)</code>. Списанные компьютеры не исчезают из отчета, обеспечивая полную прозрачность бухгалтерии!</li>
          </ul>
          <h4>14 детализированных колонок оборудования:</h4>
          <div className="faq-grid-badges">
            <div className="faq-mini-card">
              <strong>Матплата & BIOS</strong>
              <span>Производитель, модель, ревизия, версия BIOS</span>
            </div>
            <div className="faq-mini-card">
              <strong>Процессор (CPU)</strong>
              <span>Точная модель, ядра/потоки, частота</span>
            </div>
            <div className="faq-mini-card">
              <strong>Память (RAM)</strong>
              <span>Объем, слоты, серийные номера планок</span>
            </div>
            <div className="faq-mini-card">
              <strong>Диски (HDD/SSD)</strong>
              <span>Модели, объемы, серийники накопителей</span>
            </div>
            <div className="faq-mini-card">
              <strong>Видеокарта (GPU)</strong>
              <span>Модель и видеопамять</span>
            </div>
            <div className="faq-mini-card">
              <strong>Сеть (MAC / IP)</strong>
              <span>Сетевой адаптер, MAC и IP адреса</span>
            </div>
          </div>
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
    {
      id: 'excel_monitoring_reports',
      category: 'monitoring',
      title: 'Углублённые отчёты Excel по мониторингу и инцидентам (5 листов)',
      summary: 'Экспорт динамики нагрузки, событий питания, истории алертов и реестра парка в формате .xlsx.',
      badge: 'Excel (.xlsx)',
      badgeColor: 'green',
      content: (
        <div>
          <p>
            В разделе <strong>«Мониторинг»</strong> кнопка <strong>«Экспорт в Excel»</strong> формирует комплексную аналитическую книгу из 5 специализированных листов:
          </p>
          <ol className="faq-steps-list">
            <li>
              <strong>Лист 1: Сводка и Графики:</strong>
              <p>Общие показатели парка (онлайн/офлайн, средняя загрузка) и 12-точечный график динамики загрузки процессора, оперативной памяти и дисков во времени за выбранный период (24 часа, 7 дней, 30 дней).</p>
            </li>
            <li>
              <strong>Лист 2: Телеметрия:</strong>
              <p>Построчные замеры состояния компьютеров с раздельными столбцами «ID ПК» и «Имя ПК» для удобной фильтрации в Excel.</p>
            </li>
            <li>
              <strong>Лист 3: События питания:</strong>
              <p>Хронологический журнал всех включений, выключений и перезагрузок с фиксацией точного времени и инициатора.</p>
            </li>
            <li>
              <strong>Лист 4: Алерты и Инциденты:</strong>
              <p>Журнал всех аварий: факты перегрева, дефицит памяти, тревоги антикражи комплектующих и сбои служб.</p>
            </li>
            <li>
              <strong>Лист 5: Список ПК:</strong>
              <p>Полный паспорт компьютеров с инвентарными номерами (колонка <em>«Инвентарный №»</em>), расположением, IP/MAC и операционными системами.</p>
            </li>
          </ol>
          <div className="faq-callout info">
            <Info size={18} />
            <div>
              <strong>Локальное время без смещения:</strong>
              <p>Все временные метки в отчётах автоматически конвертируются в локальный часовой пояс вашей организации (UTC+3), исключая путаницу со временем формирования и событиями в логах.</p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'device_alert_policy_inheritance',
      category: 'monitoring',
      title: 'Наследование политик алертов в карточке компьютера (Device Detail)',
      summary: 'Отображение источника наследования политики, индивидуальные переопределения и возврат к группе в 1 клик.',
      badge: 'Карточка ПК',
      badgeColor: 'purple',
      content: (
        <div>
          <p>
            В карточке каждого компьютера во вкладке <strong>«Политика алертов»</strong> отображается прозрачная информация о том, откуда поступают правила мониторинга:
          </p>

          <div className="faq-grid-badges">
            <div className="faq-mini-card">
              <strong style={{ color: 'var(--blue)' }}>🔵 Наследуется от группы</strong>
              <span>Синий баннер указывает точный источник (например, <em>«Главный корпус / 2 этаж»</em>).</span>
            </div>
            <div className="faq-mini-card">
              <strong style={{ color: 'var(--purple)' }}>🟣 Индивидуальная политика</strong>
              <span>Фиолетовый баннер означает, что на данном ПК заданы персональные правила.</span>
            </div>
            <div className="faq-mini-card">
              <strong style={{ color: 'var(--green)' }}>⚡ Сброс в 1 клик</strong>
              <span>Кнопка <em>«Сбросить к наследованию группы»</em> моментально удаляет персональные настройки.</span>
            </div>
          </div>

          <h4>Как переопределить политику для отдельной станции?</h4>
          <p>
            Если конкретному компьютеру (например, критически важному серверу бэкапов или тестовой машине разработчика) нужны индивидуальные пороги срабатывания:
          </p>
          <ol className="faq-steps-list">
            <li>
              <strong>Откройте вкладку «Политика алертов»</strong> в карточке нужного ПК.
            </li>
            <li>
              <strong>Измените профиль или нужные параметры:</strong> настройте пороги загрузки CPU, памяти, дисков, флаги антикражи комплектующих, события питания или каналы оповещения (Web / Telegram).
            </li>
            <li>
              <strong>Нажмите «Сохранить политику»:</strong> сервер зафиксирует персональное переопределение. Статус-баннер сменится на <em>«Индивидуальная политика ПК (переопределяет политику группы)»</em>, а изменения в группе больше не затронут этот компьютер.
            </li>
          </ol>

          <h4>Как вернуть компьютер обратно к правилам группы?</h4>
          <p>
            Просто нажмите кнопку <strong>«Сбросить к наследованию группы»</strong> в шапке вкладки или выберите режим <em>«Наследовать от группы»</em>. Компьютер моментально начнёт динамически подчиняться политике своего кабинета, этажа или корпуса.
          </p>
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
    {
      id: 'groups_archive_protection',
      category: 'groups',
      title: 'Системная группа «Архив» и защита от случайного удаления',
      summary: 'Как устроена специальная защищённая группа для выведенных из эксплуатации станций.',
      badge: 'Защита данных',
      badgeColor: 'amber',
      content: (
        <div>
          <p>
            В дереве групп всегда присутствует системная группа <strong>«Архив»</strong>, отмеченная специальным значком.
          </p>
          <ul>
            <li><strong>Автоматическое наполнение:</strong> компьютеры попадают в неё автоматически при списании и удаляются из неё при возврате в строй.</li>
            <li><strong>Защита от удаления и переименования:</strong> попытка удалить или переименовать группу «Архив» блокируется сервером, чтобы исключить потерю связей архивных компьютеров.</li>
            <li><strong>Изоляция мониторинга:</strong> архивные компьютеры не портят статистику доступности активных рабочих аудиторий и не вызывают ложных ночных алертов.</li>
          </ul>
        </div>
      )
    },
    {
      id: 'groups_alert_policies_inheritance',
      category: 'groups',
      title: 'Групповые политики оповещений и каскадное наследование (GPO-Style)',
      summary: 'Единая настройка алертов для групп, корпусов, этажей и кабинетов с автоматическим каскадом и выборочным тиражированием.',
      badge: 'Наследование (GPO)',
      badgeColor: 'purple',
      content: (
        <div>
          <p>
            В системе реализовано <strong>иерархическое каскадное наследование политик оповещений</strong> по аналогии с групповыми политиками (GPO в Active Directory). Вам больше не нужно настраивать каждый компьютер отдельно!
          </p>

          <h4>1. Принцип каскадной цепочки наследования:</h4>
          <div className="faq-tree-preview">
            <div>🏢 <strong>Корпус / Базовая группа</strong> <span style={{ color: 'var(--blue)' }}>(Политика верхнего уровня)</span></div>
            <div style={{ paddingLeft: '20px' }}>↳ 📁 <strong>Этаж</strong> <span style={{ color: 'var(--purple)' }}>(Наследует от корпуса, если не переопределен)</span></div>
            <div style={{ paddingLeft: '40px' }}>↳ 🚪 <strong>Кабинет</strong> <span style={{ color: 'var(--green)' }}>(Наследует от этажа, если не переопределен)</span></div>
            <div style={{ paddingLeft: '60px' }}>↳ 🖥️ <strong>Компьютер</strong> (Автоматически применяет эффективную политику своего кабинета)</div>
          </div>

          <h4>2. Где находятся кнопки настройки политик?</h4>
          <p>Значок колокольчика <span style={{ display: 'inline-flex', verticalAlign: '-3px' }}><Bell size={14} /></span> доступен на всех уровнях структуры:</p>
          <ul>
            <li><strong>В шапке группы:</strong> кнопка <em>«Политика алертов»</em> в панели действий открытой группы.</li>
            <li><strong>На плитках корпусов (Level 1):</strong> кнопка с колокольчиком в верхнем правом углу карточки корпуса.</li>
            <li><strong>На плитках этажей (Level 2):</strong> кнопка с колокольчиком для этажа.</li>
            <li><strong>На плитках кабинетов (Level 3):</strong> кнопка с колокольчиком для конкретного кабинета.</li>
            <li><strong>В результатах быстрого поиска:</strong> кнопка <em>«Алерты»</em> у найденной группы или кабинета.</li>
          </ul>

          <h4>3. Режимы распространения политики:</h4>
          <p>При сохранении политики для Корпуса или Группы предлагается три варианта тиражирования:</p>
          <div className="faq-types-list">
            <div className="faq-type-row">
              <span className="faq-badge-chip blue">Применить ко всей группе</span>
              <div>
                <strong>Динамическое наследование (Рекомендуется)</strong>
                <p>Все существующие и новые дочерние этажи, кабинеты и компьютеры автоматически наследуют эту политику без ручного копирования.</p>
              </div>
            </div>
            <div className="faq-type-row">
              <span className="faq-badge-chip purple">Расшарить на конкретные этажи</span>
              <div>
                <strong>Выборочное тиражирование по этажам</strong>
                <p>Интерактивный список с чекбоксами позволяет скопировать политику только на выбранные этажи корпуса.</p>
              </div>
            </div>
            <div className="faq-type-row">
              <span className="faq-badge-chip green">Расшарить на конкретные кабинеты</span>
              <div>
                <strong>Точечное назначение по аудиториям</strong>
                <p>Возможность выбрать чекбоксами конкретные кабинеты (например, только компьютерные классы или серверные комнаты).</p>
              </div>
            </div>
          </div>

          <div className="faq-callout info">
            <Info size={18} />
            <div>
              <strong>Возврат к наследованию в 1 клик:</strong>
              <p>Если для этажа или кабинета была настроена собственная политика, в окне настройки появится кнопка <em>«Сбросить к наследованию родителя»</em>. Нажатие удаляет локальное переопределение и мгновенно возвращает элемент к наследованию от родительского уровня.</p>
            </div>
          </div>
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
              <strong>Проверьте статус службы на компьютере в PowerShell:</strong>
              <p>Нажмите <code>Win + X</code> → выберите <strong>«PowerShell»</strong> (или «Терминал») и выполните команду <code>Get-ScheduledTask WorkstationManagerAgent</code>. Статус должен быть <em>«Ready»</em> или <em>«Running»</em>. Также можно посмотреть последние строки лога: <code>Get-Content "C:\Program Files\WorkstationManagerAgent\agent_service.log" -Tail 10</code>.</p>
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
          <p>Также вы можете моментально обновить адрес сервера в файле конфигурации <code>config.json</code> через PowerShell (от Администратора):</p>
          <div className="faq-code-block">
            <code>$cfg = "C:\Program Files\WorkstationManagerAgent\config.json"; (Get-Content $cfg) -replace 'http://[^:]+:2301', 'http://НОВЫЙ_IP:2301' | Set-Content $cfg; Start-ScheduledTask -TaskName WorkstationManagerAgent</code>
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

  const expandAll = () => {
    setExpandedArticleIds(new Set(filteredArticles.map((a) => a.id)));
  };

  const collapseAll = () => {
    setExpandedArticleIds(new Set());
  };

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
              placeholder="Поиск по инструкции (например: раскатка, инженер, флешка, bat, WoL, BIOS, архив, итилиум, GPO)..."
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
          <div className="faq-articles-scroll" ref={scrollContainerRef}>
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
              <>
                <div className="faq-list-header">
                  <div className="faq-list-count">
                    Статей в разделе: <strong>{filteredArticles.length}</strong>
                  </div>
                  <div className="faq-list-actions">
                    <button
                      type="button"
                      className="faq-action-link"
                      onClick={expandAll}
                    >
                      Развернуть все
                    </button>
                    <span className="faq-action-divider">•</span>
                    <button
                      type="button"
                      className="faq-action-link"
                      onClick={collapseAll}
                    >
                      Свернуть все
                    </button>
                  </div>
                </div>

                <div className="faq-articles-list">
                  {filteredArticles.map((article) => {
                    const isExpanded = expandedArticleIds.has(article.id);
                    return (
                      <div
                        key={article.id}
                        ref={(el) => {
                          articleRefs.current[article.id] = el;
                        }}
                        className={`faq-article-card ${isExpanded ? 'expanded' : ''}`}
                      >
                        <div
                          className="faq-article-header"
                          onClick={() => toggleArticle(article.id)}
                        >
                          <div className="faq-article-header-left">
                            <div className="faq-expand-chevron">
                              <ChevronRight size={18} />
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

                        <div className="faq-article-collapse">
                          <div className="faq-article-collapse-inner">
                            <div className="faq-article-content">
                              {article.content}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
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
