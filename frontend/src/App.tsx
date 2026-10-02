import { useEffect, useMemo, useState } from "react";

import "./app.css";

type Page = "overview" | "inbox" | "donors" | "channels" | "connections" | "planner" | "accounts" | "settings";
type ApiState = "idle" | "loading" | "error" | "ready";

type InboxItem = {
  id: string;
  source: string;
  title: string;
  original: string;
  rewrite: string;
  state: "Новый" | "На проверке" | "Готово" | "Отклонён";
  time: string;
  destinations: string[];
};

const navigation: { id: Page; icon: string; label: string }[] = [
  { id: "overview", icon: "⌁", label: "Обзор" },
  { id: "inbox", icon: "▣", label: "Входящие" },
  { id: "donors", icon: "♧", label: "Доноры" },
  { id: "channels", icon: "➤", label: "Мои каналы" },
  { id: "connections", icon: "⌘", label: "Связи" },
  { id: "planner", icon: "□", label: "Планировщик" },
  { id: "accounts", icon: "♙", label: "Аккаунты" },
  { id: "settings", icon: "⚙", label: "Настройки" },
];

const demoInbox: InboxItem[] = [
  {
    id: "mars",
    source: "Наука сегодня",
    title: "На Марсе обнаружены следы древних рек",
    original:
      "Группа учёных опубликовала новые снимки высохших долин Марса. Исследователи считают, что вода могла сохраняться там значительно дольше, чем предполагалось ранее.",
    rewrite:
      "Новые снимки Марса показали древние русла рек. Учёные уточняют, как долго на планете могла сохраняться вода.",
    state: "Новый",
    time: "12:24",
    destinations: ["Технологии сегодня", "Научные факты"],
  },
  {
    id: "model",
    source: "Технологии и люди",
    title: "OpenAI представила обновление модели",
    original: "Компания рассказала о новом обновлении модели и расширении инструментов для разработчиков.",
    rewrite: "",
    state: "На проверке",
    time: "11:47",
    destinations: ["Технологии сегодня"],
  },
  {
    id: "forest",
    source: "Зелёная планета",
    title: "В Европе запустили проект по восстановлению лесов",
    original: "Несколько регионов объединили усилия для восстановления лесных массивов и защиты редких видов.",
    rewrite: "",
    state: "Новый",
    time: "09:18",
    destinations: ["Мир вокруг нас"],
  },
  {
    id: "cats",
    source: "Котики и наука",
    title: "Почему кошки мурлыкают",
    original: "Исследование рассматривает разные причины мурлыканья домашних кошек.",
    rewrite: "",
    state: "Готово",
    time: "Вчера",
    destinations: ["Это интересно"],
  },
];

const donors = [
  ["Наука сегодня", "@science_today", "Активен", "Наука"],
  ["Технологии и люди", "@tech_today", "Активен", "Технологии"],
  ["Зелёная планета", "@green_world", "На проверке", "Природа"],
  ["Космос ближе", "@cosmos_near", "На паузе", "Космос"],
];
const channels = [
  ["Технологии сегодня", "124 320", "12/день", "23:00 — 08:00", "Ручной"],
  ["Это интересно", "89 441", "8/день", "00:00 — 07:00", "Ручной"],
  ["Научные факты", "56 213", "6/день", "22:00 — 08:00", "Ручной"],
  ["Мир вокруг нас", "28 441", "5/день", "22:00 — 08:00", "Ручной"],
];
const channelDetails = [
  { glyph: "⌁", art: "ice", category: "Технологии", today: "8 / 12", description: "Новости технологий и исследования простым языком.", link: "t.me/tech_today" },
  { glyph: "✦", art: "sun", category: "Образование", today: "4 / 8", description: "Объясняем интересные идеи, факты и открытия.", link: "t.me/curious_today" },
  { glyph: "◌", art: "atom", category: "Наука", today: "3 / 6", description: "Короткие проверенные материалы о науке.", link: "t.me/science_facts" },
  { glyph: "◒", art: "leaf", category: "Природа", today: "2 / 5", description: "Материалы об экологии, климате и окружающем мире.", link: "t.me/world_around" },
];

const pageMeta: Record<Page, { title: string; description: string }> = {
  overview: { title: "Обзор", description: "Поток материалов и состояние Telegram-каналов" },
  inbox: { title: "Входящие", description: "Новые материалы из источников для проверки и публикации" },
  donors: { title: "Доноры", description: "Управление источниками контента из Telegram" },
  channels: { title: "Мои каналы", description: "Настройки публикаций и правил ваших Telegram-каналов" },
  connections: { title: "Связи", description: "Маршрутизация контента от доноров к выходным каналам" },
  planner: { title: "Планировщик", description: "Расписание публикаций и материалы без назначенного времени" },
  accounts: { title: "Аккаунты", description: "Состояние подключённых Telegram-сессий" },
  settings: { title: "Настройки", description: "Параметры рабочего пространства, модерации и публикации" },
};

const statusClass = (status: string) =>
  status === "Активен" || status === "Готово" ? "success" : status === "На паузе" ? "muted" : status === "Новый" ? "violet" : "warning";

const demoFromUrl = () => new URLSearchParams(window.location.search).get("demo") === "1";

export function App({ initialDemo = demoFromUrl() }: { initialDemo?: boolean }) {
  const [page, setPage] = useState<Page>("overview");
  const [demo, setDemo] = useState(initialDemo);
  const [apiState, setApiState] = useState<ApiState>("idle");
  const [apiItems, setApiItems] = useState<InboxItem[]>([]);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (demo) {
      setApiState("idle");
      return;
    }
    let active = true;
    setApiState("loading");
    const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
    fetch(`${baseUrl}/api/telegram/incoming-posts`)
      .then(async (response) => {
        if (!response.ok) throw new Error("inbox request failed");
        return response.json() as Promise<{ items: Array<Record<string, unknown>> }>;
      })
      .then((payload) => {
        if (!active) return;
        setApiItems(
          payload.items.map((item, index) => ({
            id: String(item.source_key ?? index),
            source: "Telegram",
            title: String(item.source_text ?? "Материал без текста"),
            original: String(item.source_text ?? ""),
            rewrite: "",
            state: String(item.editorial_status) === "REJECT" ? "Отклонён" : "На проверке",
            time: "сейчас",
            destinations: [],
          })),
        );
        setApiState("ready");
      })
      .catch(() => active && setApiState("error"));
    return () => {
      active = false;
    };
  }, [demo, reload]);

  const common = { demo, apiState, apiItems, retry: () => setReload((value) => value + 1) };
  return (
    <div className="studio-shell">
      <Sidebar page={page} onNavigate={setPage} />
      <div className="studio-main">
        <Topbar demo={demo} onDemoChange={setDemo} />
        <main className="content" id="main-content">
          <PageHeading {...pageMeta[page]} page={page} />
          {page === "overview" && <Overview demo={demo} onNavigate={setPage} />}
          {page === "inbox" && <Inbox {...common} />}
          {page === "donors" && <Donors demo={demo} />}
          {page === "channels" && <Channels demo={demo} />}
          {page === "connections" && <Connections demo={demo} />}
          {page === "planner" && <Planner demo={demo} />}
          {page === "accounts" && <Accounts demo={demo} />}
          {page === "settings" && <Settings demo={demo} />}
        </main>
      </div>
    </div>
  );
}

function Sidebar({ page, onNavigate }: { page: Page; onNavigate: (page: Page) => void }) {
  return (
    <aside className="sidebar" aria-label="Разделы Content Studio">
      <a className="brand" href="#main-content" aria-label="К содержимому">
        <span className="brand-mark">➤</span><span><b>Content Studio</b><small>для Telegram</small></span>
      </a>
      <nav aria-label="Основная навигация">
        {navigation.map((item) => (
          <button key={item.id} className={page === item.id ? "nav-item active" : "nav-item"} onClick={() => onNavigate(item.id)}>
            <span aria-hidden="true">{item.icon}</span>{item.label}{item.id === "inbox" && <em>4</em>}
          </button>
        ))}
      </nav>
      <div className="sidebar-footer"><span>◌</span> Ручная модерация</div>
    </aside>
  );
}

function Topbar({ demo, onDemoChange }: { demo: boolean; onDemoChange: (value: boolean) => void }) {
  return (
    <header className="topbar">
      <label className="global-search"><span>⌕</span><input placeholder="Поиск по материалам и каналам" aria-label="Глобальный поиск" /></label>
      <div className={demo ? "mode-badge demo" : "mode-badge"}>{demo ? "Демо-данные — без публикации" : "Рабочий режим"}</div>
      <label className="demo-switch"><span>DEMO</span><input type="checkbox" role="switch" aria-label="Включить демо-режим" checked={demo} onChange={(event) => onDemoChange(event.target.checked)} /><i /></label>
      <button className="icon-button" aria-label="Уведомления">♢</button>
    </header>
  );
}

function PageHeading({ title, description, page }: { title: string; description: string; page: Page }) {
  const action = page === "channels" ? <button className="primary-button heading-action" disabled title="Добавление канала требует API">＋ Добавить канал <small>требуется API</small></button> : <button className="period-button">◫ Эта неделя</button>;
  return <section className="page-heading"><div><h1>{title}</h1><p>{description}</p></div>{action}</section>;
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>;
}

function EmptyOrDisabled({ demo, label }: { demo: boolean; label: string }) {
  if (demo) return null;
  return <div className="empty-state"><b>{label}</b><span>В рабочем режиме эта возможность ожидает поддерживаемый API. Включите DEMO для безопасного просмотра интерфейса.</span></div>;
}

function Overview({ demo, onNavigate }: { demo: boolean; onNavigate: (page: Page) => void }) {
  const stats = [["⌄", "Получено", "124", "blue"], ["◷", "На проверке", "18", "orange"], ["✓", "Готово", "36", "green"], ["➤", "Запланировано", "9", "violet"]];
  return <><EmptyOrDisabled demo={demo} label="Метрики недоступны" />{demo && <div className="overview-grid">
    <div className="metric-row">{stats.map(([icon, title, value, tone]) => <Card key={title} className="metric"><span className={`metric-icon ${tone}`}>{icon}</span><div><small>{title}</small><b>{value}</b><em>за неделю</em></div></Card>)}</div>
    <Card className="wide"><PanelTitle title="Поток контента" action="По дням" /><FlowChart /></Card>
    <Card><PanelTitle title="Источники контента" /><div className="donut"><b>124</b><span>материала</span></div><ul className="legend"><li>Наука <b>38%</b></li><li>Технологии <b>31%</b></li><li>Природа <b>19%</b></li><li>Другое <b>12%</b></li></ul></Card>
    <Card className="wide"><PanelTitle title="Очередь модерации" action="Открыть" onAction={() => onNavigate("inbox")} />{demoInbox.slice(0, 4).map((item) => <div className="compact-row" key={item.id}><span className="avatar">{item.source[0]}</span><div><b>{item.title}</b><small>{item.source}</small></div><span className={`status ${statusClass(item.state)}`}>{item.state}</span></div>)}</Card>
    <Card><PanelTitle title="Мои каналы" action="Управлять" onAction={() => onNavigate("channels")} />{channels.slice(0, 3).map(([name, followers]) => <div className="compact-row" key={name}><span className="avatar cyan">➤</span><div><b>{name}</b><small>{followers} подписчиков</small></div><strong className="positive">●</strong></div>)}</Card>
  </div>}</>;
}

function PanelTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return <div className="panel-title"><h2>{title}</h2>{action && <button className="link-button" onClick={onAction}>{action} →</button>}</div>;
}

function FlowChart() {
  return <div className="flow-chart" aria-label="График потока контента"><div className="grid-lines" />{["blue-line", "cyan-line", "violet-line", "orange-line"].map((line) => <svg key={line} className={line} viewBox="0 0 600 180" preserveAspectRatio="none"><polyline points="0,130 100,80 200,58 300,92 400,84 500,50 600,25" /></svg>)}<div className="axis"><span>Пн</span><span>Вт</span><span>Ср</span><span>Чт</span><span>Пт</span><span>Сб</span><span>Вс</span></div></div>;
}

function Inbox({ demo, apiState, apiItems, retry }: { demo: boolean; apiState: ApiState; apiItems: InboxItem[]; retry: () => void }) {
  const [selectedId, setSelectedId] = useState("mars");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("Все");
  const [notice, setNotice] = useState("");
  const [draft, setDraft] = useState("");
  const items = demo ? demoInbox : apiItems;
  const selected = items.find((item) => item.id === selectedId) ?? items[0];
  const visible = items.filter((item) => (filter === "Все" || item.state === filter) && `${item.title} ${item.source}`.toLowerCase().includes(query.toLowerCase()));

  if (!demo && apiState === "loading") return <Card><div className="loading">Загрузка входящих…</div></Card>;
  if (!demo && apiState === "error") return <Card><div className="error-state"><b>Не удалось загрузить входящие</b><span>Проверьте URL API и доступность сервиса.</span><button onClick={retry}>Повторить</button></div></Card>;
  return <div className="inbox-layout">
    <Card className="inbox-list"><label className="field search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по входящим" /></label><div className="filter-row">{["Все", "Новый", "На проверке", "Готово"].map((name) => <button key={name} className={filter === name ? "filter active" : "filter"} onClick={() => setFilter(name)}>{name}</button>)}</div>{visible.length ? visible.map((item) => <button className={selected?.id === item.id ? "inbox-card selected" : "inbox-card"} key={item.id} onClick={() => { setSelectedId(item.id); setDraft(item.rewrite); setNotice(""); }}><span className="avatar">{item.source[0]}</span><span><b>{item.source}</b><strong>{item.title}</strong><small>{item.time}</small></span><em className={`status ${statusClass(item.state)}`}>{item.state}</em></button>) : <div className="empty-state">Материалы не найдены</div>}</Card>
    <Card className="article-panel">{selected ? <><div className="article-meta"><span className="avatar">{selected.source[0]}</span><div><b>{selected.source}</b><small>Оригинал из Telegram · неизменяемый</small></div></div><h2>{selected.title}</h2><section className="source-copy"><h3>Оригинал</h3><p>{selected.original}</p></section><section className="rewrite-box"><div className="panel-title"><h3>Вариант для редактора</h3><span>Только ручное применение</span></div><textarea aria-label="Черновик варианта" value={draft || selected.rewrite} onChange={(event) => setDraft(event.target.value)} placeholder="AI-вариант будет доступен после подключения провайдера" disabled={!demo} /><button className="secondary-button" disabled={!demo || !(draft || selected.rewrite)} onClick={() => setNotice("Черновик применён только в DEMO. Оригинал сохранён без изменений.")}>Применить вариант</button></section>{notice && <p className="inline-notice" role="status">{notice}</p>}</> : <div className="empty-state">Выберите материал из списка</div>}</Card>
    <Card className="actions-panel"><PanelTitle title="Куда публиковать" />{selected?.destinations.map((destination) => <label className="destination" key={destination}><input type="checkbox" defaultChecked disabled={!demo} /> <span>{destination}</span></label>)}<hr /><h3>Следующее действие</h3><p className="muted-copy">Одобрение не публикует материал. Запланировать и опубликовать — независимые операции.</p><button className="primary-button" aria-label="Одобрить материал" disabled={!demo || selected?.state === "Отклонён"} onClick={() => setNotice("Материал одобрен. Публикация не выполнена.")}>✓ Одобрить</button><button className="secondary-button" aria-label="Запланировать" disabled={!demo} onClick={() => setNotice("В DEMO открыт сценарий планирования; публикация не выполнялась.")}>□ Запланировать</button><button className="danger-button" aria-label="Отклонить материал" disabled={!demo} onClick={() => setNotice("Материал отклонён только в DEMO.")}>× Отклонить</button><button className="secondary-button" aria-label="Опубликовать" disabled><span>➤</span> Опубликовать <small>требуется API</small></button></Card>
  </div>;
}

function Donors({ demo }: { demo: boolean }) {
  const [selected, setSelected] = useState(0); const [importOpen, setImportOpen] = useState(false); const [raw, setRaw] = useState(""); const [validated, setValidated] = useState(false);
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean); const invalid = lines.filter((line) => !/^@?[A-Za-z0-9_]{4,}$/.test(line)); const duplicate = lines.filter((line, index) => lines.indexOf(line) !== index);
  return <><EmptyOrDisabled demo={demo} label="Источники недоступны" />{demo && <div className="two-column"><Card><div className="toolbar"><label className="field search-field"><span>⌕</span><input placeholder="Поиск по источникам" /></label><button className="primary-button" onClick={() => { setValidated(false); setImportOpen(true); }}>↑ Импорт</button></div><div className="table-list">{donors.map((donor, index) => <button className={index === selected ? "table-row selected" : "table-row"} key={donor[1]} onClick={() => setSelected(index)}><span className="avatar">{donor[0][0]}</span><span><b>{donor[0]}</b><small>{donor[1]}</small></span><span className={`status ${statusClass(donor[2])}`}>{donor[2]}</span><span className="chip">{donor[3]}</span></button>)}</div></Card><Card><PanelTitle title="Настройки источника" /><div className="profile-title"><span className="avatar large">{donors[selected][0][0]}</span><div><h2>{donors[selected][0]}</h2><p>{donors[selected][1]}</p></div></div><label className="toggle-row">Включён для сбора<input type="checkbox" role="switch" defaultChecked /><i /></label><label className="field">Допустимые типы<select defaultValue="text-photo"><option value="text-photo">Текст и фото</option><option value="text">Только текст</option></select></label><label className="field">Стоп-слова<input defaultValue="Реклама, криптовалюта" /></label><p className="help-copy">Проверка URL, дублей и технических фильтров выполняется до EditorialGate.</p></Card></div>}{importOpen && <Modal title="Импорт доноров" onClose={() => setImportOpen(false)}><p>По одному @username в строке. В DEMO доступна только проверка: импорт не выполняется.</p><textarea value={raw} onChange={(event) => { setRaw(event.target.value); setValidated(false); }} placeholder="@science_today\n@tech_today" aria-label="Список доноров для импорта" />{raw && <div className="validation"><span>Строк: {lines.length}</span><span className={invalid.length ? "negative" : "positive"}>Ошибок формата: {invalid.length}</span><span className={duplicate.length ? "negative" : "positive"}>Дублей: {duplicate.length}</span></div>}{validated && <p className="inline-notice">Проверка DEMO завершена: строки не были импортированы.</p>}<button className="primary-button" disabled={!lines.length || invalid.length > 0 || duplicate.length > 0} onClick={() => setValidated(true)}>Проверить строки</button></Modal>}</>;
}

function Channels({ demo }: { demo: boolean }) {
  const [selected, setSelected] = useState(0); const [mode, setMode] = useState("Ручной"); const [saved, setSaved] = useState(false);
  const detail = channelDetails[selected];
  return <><EmptyOrDisabled demo={demo} label="Каналы недоступны" />{demo && <div className="channels-layout"><Card className="channel-directory"><div className="channel-toolbar"><label className="field search-field"><span>⌕</span><input placeholder="Поиск по каналам…" /></label><button className="filter active">Все статусы</button><button className="filter">Ручной режим</button><button className="icon-button" aria-label="Вид списка">☷</button></div><div className="directory-caption"><span>{channels.length} канала</span><small>Выберите канал, чтобы настроить правила</small></div>{channels.map((channel, index) => { const item = channelDetails[index]; return <button className={selected === index ? "channel-card rich selected" : "channel-card rich"} key={channel[0]} onClick={() => { setSelected(index); setMode(channel[4]); setSaved(false); }}><span className={`channel-art ${item.art}`}>{item.glyph}</span><span className="channel-identity"><b>{channel[0]}</b><small>{channel[1]} подписчиков</small><em>{item.category}</em></span><span><small>Лимит</small><b>{channel[2]}</b></span><span><small>Тихие часы</small><b>{channel[3]}</b></span><span><small>Сегодня</small><b>{item.today}</b><i className="progress"><i style={{ width: `${Math.round((Number(item.today.split(" /")[0]) / Number(item.today.split("/")[1].trim())) * 100)}%` }} /></i></span><span className="more">⋮</span></button>; })}</Card><Card className="channel-detail"><div className="channel-profile"><span className={`channel-art large ${detail.art}`}>{detail.glyph}</span><div><div className="detail-title"><h2>{channels[selected][0]}</h2><span className="verified">✓</span></div><p>{channels[selected][1]} подписчиков</p></div><button className="icon-button" aria-label="Дополнительные действия канала">⋮</button></div><p className="channel-description">{detail.description}</p><div className="channel-link"><span>⌁</span><span>{detail.link}</span><button disabled>Открыть ↗</button></div><div className="detail-tabs" aria-label="Разделы настроек канала"><button className="active">Публикации</button><button disabled>AI-профиль</button><button disabled>Правила</button><button disabled>Статистика</button></div><section className="detail-section"><div className="section-heading"><span className="section-symbol">◷</span><div><h3>Окна публикаций</h3><p>Когда материалы могут быть запланированы</p></div></div><div className="publish-window"><span>09:00</span><b>—</b><span>12:00</span><div className="weekday-row"><em>Пн</em><em>Вт</em><em>Ср</em><em>Чт</em><em>Пт</em></div></div><div className="publish-window"><span>15:00</span><b>—</b><span>20:00</span><div className="weekday-row"><em>Пн</em><em>Вт</em><em>Ср</em><em>Чт</em><em>Пт</em></div></div></section><section className="detail-section compact-section"><div className="section-heading"><span className="section-symbol violet">☾</span><div><h3>Тихие часы</h3><p>Публикации не будут выходить в этот период</p></div></div><span className="quiet-time">23:00 — 08:00</span></section><section className="detail-section compact-section"><div className="section-heading"><span className="section-symbol cyan">➤</span><div><h3>Режим публикации</h3><p>Редактор всегда подтверждает публикацию отдельно.</p></div></div><label className="mode-select">Режим<select value={mode} onChange={(event) => { setMode(event.target.value); setSaved(false); }}><option>Ручной</option><option>С проверкой</option><option>Автоматически</option></select></label></section>{mode === "Автоматически" && <p className="warning-note">Автоматический режим в DEMO не публикует материалы и требует серверной политики.</p>}<button className="primary-button channel-save" onClick={() => setSaved(true)}>Сохранить настройки DEMO</button>{saved && <p className="inline-notice">Настройки канала сохранены только в DEMO.</p>}</Card></div>}</>;
}

function Connections({ demo }: { demo: boolean }) {
  const [selected, setSelected] = useState(0); const [intake, setIntake] = useState(68); const [mix, setMix] = useState(42); const [saved, setSaved] = useState(false);
  const routes = [["Наука сегодня", "Научные факты"], ["Технологии и люди", "Технологии сегодня"], ["Зелёная планета", "Мир вокруг нас"]];
  return <><EmptyOrDisabled demo={demo} label="Связи недоступны" />{demo && <div className="connection-layout"><Card><PanelTitle title="Маршруты" />{routes.map((route, index) => <button key={route.join()} className={selected === index ? "route-card selected" : "route-card"} onClick={() => { setSelected(index); setSaved(false); }}><span className="avatar">{route[0][0]}</span><b>{route[0]} → {route[1]}</b><small>Ручная модерация · активна</small></button>)}</Card><Card><PanelTitle title="Настройки маршрута" /><div className="route-pair"><span>{routes[selected][0]}</span><b>→</b><span>{routes[selected][1]}</span></div><RangeField label="Доля входящих материалов" description="intake_percent: сколько материалов донора направлять на рассмотрение" value={intake} onChange={setIntake} /><RangeField label="Целевая доля в канале" description="target_mix_percent: желаемая доля донора среди публикаций канала" value={mix} onChange={setMix} /><fieldset><legend>Политика модерации</legend><label><input type="radio" name="moderation" defaultChecked /> Сначала редакторская проверка</label><label><input type="radio" name="moderation" /> Только вручную</label></fieldset><div className="action-row"><button className="secondary-button" onClick={() => { setIntake(68); setMix(42); }}>Отмена</button><button className="primary-button" onClick={() => setSaved(true)}>Сохранить изменения</button></div>{saved && <p className="inline-notice">Настройки сохранены только в DEMO.</p>}</Card></div>}</>;
}

function RangeField({ label, description, value, onChange }: { label: string; description: string; value: number; onChange: (value: number) => void }) { return <label className="range-field"><b>{label}</b><small>{description}</small><div><input type="range" min="0" max="100" value={value} onChange={(event) => onChange(Number(event.target.value))} /><output>{value}%</output></div></label>; }

function Planner({ demo }: { demo: boolean }) {
  const [selected, setSelected] = useState("mars"); const [scheduled, setScheduled] = useState<string[]>(["model", "forest"]); const days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
  return <><EmptyOrDisabled demo={demo} label="Планировщик недоступен" />{demo && <div className="planner-layout"><Card className="calendar"><div className="toolbar"><button className="period-button">◫ Неделя</button><button className="filter active">Сегодня</button><span className="timezone">Europe/Minsk (UTC+3)</span></div><div className="week-grid">{days.map((day, index) => <section key={day}><header><b>{day}</b><small>{index + 1}</small></header>{["09:00", "12:00", "15:00", "18:00"].map((time, slot) => <button className="calendar-slot" key={time} onClick={() => selected && setScheduled((items) => items.includes(selected) ? items : [...items, selected])}>{scheduled[(index + slot) % scheduled.length] && <span>{demoInbox.find((item) => item.id === scheduled[(index + slot) % scheduled.length])?.title.slice(0, 30)}<small>{time}</small></span>}</button>)}</section>)}</div></Card><Card><PanelTitle title="Без расписания" />{demoInbox.filter((item) => !scheduled.includes(item.id)).map((item) => <button className={selected === item.id ? "unscheduled selected" : "unscheduled"} onClick={() => setSelected(item.id)} key={item.id}><b>{item.title}</b><small>{item.source}</small></button>)}<button className="primary-button" disabled={!selected} onClick={() => setScheduled((items) => items.includes(selected) ? items : [...items, selected])}>Запланировать выбранный</button><p className="help-copy">Перенос в рабочем режиме требует серверной проверки окна и сохранения расписания.</p></Card></div>}</>;
}

function Accounts({ demo }: { demo: boolean }) {
  const [wizard, setWizard] = useState(false); const [step, setStep] = useState(1); const accounts = [["Рабочий", "+7 9•• ••• •• 42", "Активен"], ["Редакция", "+7 9•• ••• •• 18", "Активен"], ["Архив", "+7 9•• ••• •• 26", "Ошибка"]];
  return <><EmptyOrDisabled demo={demo} label="Аккаунты недоступны" />{demo && <div className="two-column"><Card><PanelTitle title="Подключённые аккаунты" />{accounts.map((account) => <div className="account-row" key={account[0]}><span className="avatar">{account[0][0]}</span><div><b>{account[0]}</b><small>{account[1]}</small></div><span className={`status ${statusClass(account[2])}`}>{account[2]}</span><button className="icon-button" aria-label={`Действия: ${account[0]}`}>⋮</button></div>)}</Card><Card><PanelTitle title="Подключение аккаунта" /><p>Мастер открывается только по действию. Для реального Telegram-входа нужен live provider; сессии и коды не хранятся в браузере.</p><button className="primary-button" onClick={() => { setWizard(true); setStep(1); }}>Подключить аккаунт DEMO</button></Card></div>}{wizard && <Modal title="Подключение Telegram в DEMO" onClose={() => setWizard(false)}><ol className="stepper">{["Номер телефона", "Код Telegram", "2FA при необходимости", "Результат"].map((name, index) => <li className={index + 1 === step ? "current" : index + 1 < step ? "done" : ""} key={name}><b>{index + 1}</b><span>{name}</span></li>)}</ol>{step < 4 ? <><label className="field">{step === 1 ? "Телефон" : step === 2 ? "Код" : "Пароль 2FA"}<input placeholder={step === 1 ? "+7 900 000-00-00" : "Не вводите реальный секрет"} /></label><button className="primary-button" onClick={() => setStep((value) => value + 1)}>Продолжить</button></> : <><p className="inline-notice">DEMO-сеанс создан только в памяти. Реальная авторизация не выполнялась.</p><button className="primary-button" onClick={() => setWizard(false)}>Закрыть</button></>}</Modal>}</>;
}

function Settings({ demo }: { demo: boolean }) {
  const [section, setSection] = useState("Общие");
  const [savedLanguage, setSavedLanguage] = useState("ru");
  const [language, setLanguage] = useState("ru");
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const sections = ["Общие", "Модерация", "Публикация", "Уведомления", "AI и перефразирование", "Безопасность"];
  const cancel = () => { setLanguage(savedLanguage); setDirty(false); };
  const save = () => { setSavedLanguage(language); setDirty(false); setSaved(true); };

  return <><EmptyOrDisabled demo={demo} label="Настройки недоступны" />{demo && <div className="settings-layout"><Card className="settings-nav">{sections.map((name) => <button className={section === name ? "settings-tab active" : "settings-tab"} onClick={() => { setSection(name); cancel(); }} key={name}>{name}<small>{name === "Модерация" ? "Правила и фильтры" : "Параметры"}</small></button>)}</Card><Card className="settings-form"><PanelTitle title={`${section}: настройки`} /><label className="field">Язык интерфейса<select value={language} onChange={(event) => { setLanguage(event.target.value); setDirty(event.target.value !== savedLanguage); }}><option value="ru">Русский</option><option value="en">English</option></select></label><label className="field">Часовой пояс<select defaultValue="minsk" onChange={() => setDirty(true)}><option value="minsk">Europe/Minsk (UTC+3)</option></select></label>{section === "Модерация" && <><label className="field">Строгость проверки<select onChange={() => setDirty(true)}><option>Стандартная</option><option>Строгая</option></select></label><label className="toggle-row">Проверять точные дубли<input type="checkbox" role="switch" defaultChecked onChange={() => setDirty(true)} /><i /></label></>}{section === "Публикация" && <><label className="field">Режим по умолчанию<select onChange={() => setDirty(true)}><option>Ручной</option><option>С проверкой</option></select></label><p className="warning-note">Автоматическая публикация не включается интерфейсом.</p></>}{dirty && <div className="unsaved"><span>Есть несохранённые изменения</span><button className="secondary-button" onClick={cancel}>Отмена</button><button className="primary-button" onClick={save}>Сохранить</button></div>}{saved && <p className="inline-notice">Изменения сохранены только в DEMO.</p>}</Card></div>}</>;
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) { return <div className="modal-backdrop" role="presentation"><section className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="panel-title"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Закрыть">×</button></div>{children}</section></div>; }
