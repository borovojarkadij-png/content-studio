import {
  useCallback,
  useEffect,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { loadInbox } from "./api";
import { LivePlanner } from "./LivePlanner";
import { Accounts, Connections, Planner, Settings } from "./workspaces";
import {
  Artwork,
  Icon,
  Metric,
  Modal,
  Notice,
  Panel,
  PanelTitle,
  Search,
  Status,
  Toggle,
  Unavailable,
} from "./ui";
import {
  canProcess,
  channelSettingsError,
  createDemo,
  navigation,
  scheduleError,
  validateDonors,
  type Channel,
  type Donor,
  type Page,
  type Post,
  type StudioData,
} from "./studio";
import "./app.css";

export type WorkspaceProps = {
  data: StudioData;
  setData: Dispatch<SetStateAction<StudioData>>;
  markDirty: (page: Page, dirty: boolean) => void;
};
const emptyData: StudioData = {
  posts: [],
  donors: [],
  channels: [],
  routes: [],
  accounts: [],
  scheduled: [],
};

export function App({
  initialDemo = new URLSearchParams(window.location.search).get("demo") === "1",
}: {
  initialDemo?: boolean;
}) {
  const [demo, setDemo] = useState(initialDemo);
  const [data, setData] = useState(() =>
    initialDemo ? createDemo() : emptyData,
  );
  const [page, setPage] = useState<Page>("overview");
  const [visited, setVisited] = useState<Page[]>(["overview"]);
  const [globalQuery, setGlobalQuery] = useState("");
  const [dirtyPages, setDirtyPages] = useState<Set<Page>>(new Set());
  const [pendingMode, setPendingMode] = useState<boolean | null>(null);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirtyPages.size) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirtyPages]);
  const markDirty = useCallback(
    (key: Page, dirty: boolean) =>
      setDirtyPages((prior) => {
        if (prior.has(key) === dirty) return prior;
        const next = new Set(prior);
        dirty ? next.add(key) : next.delete(key);
        return next;
      }),
    [],
  );
  const navigate = (next: Page) => {
    setPage(next);
    setVisited((prior) => (prior.includes(next) ? prior : [...prior, next]));
  };
  const applyMode = (next: boolean) => {
    setDemo(next);
    setData(next ? createDemo() : emptyData);
    setVisited([page]);
    setDirtyPages(new Set());
    setPendingMode(null);
  };
  const changeMode = (next: boolean) => {
    if (dirtyPages.size) setPendingMode(next);
    else applyMode(next);
  };
  const meta = navigation.find((item) => item.id === page)!;
  const workspace = { data, setData, markDirty };
  return (
    <div className="studio-shell">
      <a className="skip-link" href="#main-content">
        К содержимому
      </a>
      <aside className="sidebar" aria-label="Разделы Content Studio">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="channels" size={41} />
          </span>
          <span>
            <b>Content Studio</b>
            <small>для Telegram</small>
          </span>
        </div>
        <nav aria-label="Основная навигация">
          {navigation.map((item) => (
            <button
              key={item.id}
              aria-label={item.label}
              aria-current={page === item.id ? "page" : undefined}
              title={item.label}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              onClick={() => navigate(item.id)}
            >
              <Icon name={item.id} />
              <span>{item.label}</span>
              {item.id === "inbox" && demo && <em>{data.posts.length}</em>}
              {dirtyPages.has(item.id) && (
                <i className="dirty-dot" title="Несохранённые изменения" />
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <Icon name="shield" size={18} />
          <div>
            Ручная модерация<small>EditorialGate обязателен</small>
          </div>
        </div>
      </aside>
      <div className="studio-main">
        <header className="topbar">
          <form
            className="global-search"
            onSubmit={(event) => {
              event.preventDefault();
              navigate("inbox");
            }}
          >
            <Search
              value={globalQuery}
              onChange={setGlobalQuery}
              placeholder="Поиск по материалам…"
            />
          </form>
          <span className={`mode-badge ${demo ? "demo" : ""}`}>
            <Icon name="channels" size={19} />
            {demo ? "Демо-данные — без публикации" : "Рабочий режим"}
          </span>
          <Toggle label="DEMO" checked={demo} onChange={changeMode} />
          <span className="header-divider" />
          <span className="workspace-avatar">
            <Icon name="accounts" size={20} />
          </span>
          <span className="workspace-name">Рабочее пространство</span>
        </header>
        <main className="content" id="main-content">
          <div className="page-heading">
            <div>
              <h1>{page === "overview" ? "Обзор системы" : meta.label}</h1>
              <p>{meta.description}</p>
            </div>
            <span className="period-label">
              <Icon name="planner" size={18} />
              {demo ? "28 сен — 4 окт 2026 · DEMO" : "Текущее состояние"}
            </span>
          </div>
          {visited.map((section) => (
            <div
              hidden={section !== page}
              key={`${section}-${demo}`}
              className="workspace-view"
              data-page={section}
            >
              {section === "overview" && (
                <Overview {...workspace} demo={demo} onNavigate={navigate} />
              )}
              {section === "inbox" && (
                <Inbox {...workspace} demo={demo} globalQuery={globalQuery} />
              )}
              {section !== "overview" &&
                section !== "inbox" &&
                section !== "settings" &&
                section !== "planner" &&
                !demo && (
                  <Unavailable
                    title={`${navigation.find((item) => item.id === section)!.label}: подключение ожидается`}
                  />
                )}
              {demo && section === "donors" && <Donors {...workspace} />}
              {demo && section === "channels" && <Channels {...workspace} />}
              {demo && section === "connections" && (
                <Connections {...workspace} />
              )}
              {demo && section === "planner" && <Planner {...workspace} />}
              {!demo && section === "planner" && (
                <LivePlanner markDirty={markDirty} />
              )}
              {demo && section === "accounts" && <Accounts {...workspace} />}
              {section === "settings" && (
                <Settings {...workspace} demo={demo} />
              )}
            </div>
          ))}
        </main>
      </div>
      {pendingMode !== null && (
        <Modal title="Переключить режим?" onClose={() => setPendingMode(null)}>
          <p>
            Несохранённые правки будут потеряны. DEMO хранит изменения только в
            памяти этого окна.
          </p>
          <div className="action-row">
            <button onClick={() => setPendingMode(null)}>Остаться</button>
            <button
              className="danger-button"
              onClick={() => applyMode(pendingMode)}
            >
              Переключить и сбросить
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Overview({
  data,
  demo,
  onNavigate,
}: WorkspaceProps & { demo: boolean; onNavigate: (page: Page) => void }) {
  if (!demo) return <Unavailable title="Метрики пока недоступны" />;
  const pending = data.posts.filter((item) =>
    ["Новый", "На проверке"].includes(item.state),
  );
  const colors = ["#168bff", "#27d2cd", "#a28bfa", "#6d89ae"];
  const labels = ["Наука", "Технологии", "Природа", "Другое"];
  const groups = data.posts.map((post) =>
    ["mars", "space", "atom"].includes(post.art)
      ? 0
      : post.art === "tech"
        ? 1
        : post.art === "forest"
          ? 2
          : 3,
  );
  const counts = labels.map(
    (_, index) => groups.filter((group) => group === index).length,
  );
  let edge = 0;
  const gradient = counts
    .map((count, index) => {
      const start = edge;
      edge += (count / Math.max(data.posts.length, 1)) * 100;
      return `${colors[index]} ${start}% ${edge}%`;
    })
    .join(", ");
  return (
    <>
      <div className="metric-row">
        <Metric
          icon="download"
          title="Получено"
          value={data.posts.length}
          tone="blue"
        />
        <Metric
          icon="clock"
          title="На проверке"
          value={pending.length}
          tone="orange"
        />
        <Metric
          icon="check"
          title="Готово"
          value={data.posts.filter((item) => item.state === "Готово").length}
          tone="green"
        />
        <Metric
          icon="planner"
          title="Запланировано"
          value={data.scheduled.length}
          tone="violet"
        />
      </div>
      <div className="overview-grid">
        <Panel>
          <PanelTitle title="Поток контента" icon="chart">
            <span className="small-muted">Текущие статусы · DEMO</span>
          </PanelTitle>
          <div className="chart-legend">
            <span>
              <i className="blue" />
              Получено
            </span>
            <span>
              <i className="orange" />
              На проверке
            </span>
            <span>
              <i className="green" />
              Готово
            </span>
          </div>
          <FlowChart posts={data.posts} />
        </Panel>
        <Panel>
          <PanelTitle title="Источники контента" icon="donors">
            <button
              className="link-button"
              onClick={() => onNavigate("donors")}
            >
              Все доноры <Icon name="arrow" size={17} />
            </button>
          </PanelTitle>
          <div className="source-distribution">
            <div
              className="donut"
              style={{
                background: `radial-gradient(#0c2037 0 52%, transparent 53%), conic-gradient(${gradient})`,
              }}
            >
              <b>{data.posts.length}</b>
              <small>материалов</small>
            </div>
            <div className="distribution-legend">
              {labels.map((label, index) => (
                <div key={label}>
                  <i
                    style={{
                      background: colors[index],
                    }}
                  />
                  <span>{label}</span>
                  <b>
                    {Math.round(
                      (counts[index] / Math.max(data.posts.length, 1)) * 100,
                    )}
                    %
                  </b>
                </div>
              ))}
            </div>
          </div>
        </Panel>
        <Panel>
          <PanelTitle title="Очередь модерации" icon="clock">
            <button className="link-button" onClick={() => onNavigate("inbox")}>
              Все ({pending.length}) <Icon name="arrow" size={17} />
            </button>
          </PanelTitle>
          {pending.map((item) => (
            <div className="compact-row" key={item.id}>
              <Artwork kind={item.art} />
              <div>
                <b>{item.title}</b>
                <small>{item.source}</small>
              </div>
              <span className="small-muted">{item.time}</span>
              <Status value={item.state} />
            </div>
          ))}
        </Panel>
        <Panel>
          <PanelTitle title="Мои каналы" icon="channels">
            <button
              className="link-button"
              onClick={() => onNavigate("channels")}
            >
              Все каналы <Icon name="arrow" size={17} />
            </button>
          </PanelTitle>
          <div className="channel-mini-header">
            <span>Канал</span>
            <span>Подписчики</span>
            <span>Сегодня</span>
          </div>
          {data.channels.map((item) => (
            <div className="compact-row mini-channel" key={item.id}>
              <Artwork kind={item.art} />
              <div>
                <b>{item.name}</b>
                <small>{item.category}</small>
              </div>
              <span>{item.subscribers}</span>
              <span className="positive">
                {item.today} / {item.daily}
              </span>
            </div>
          ))}
          <div className="activity-note">
            <Icon name="shield" size={22} />
            <div>
              <b>Публикации под контролем редактора</b>
              <p>DEMO не обращается к Telegram и AI-провайдерам.</p>
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}
function FlowChart({ posts }: { posts: Post[] }) {
  // Fixture reception timestamps are explicitly Today / Yesterday within the labelled week.
  // This chart is a current-state breakdown, not a fabricated historical event log.
  const daily = Array.from({ length: 7 }, (_, day) =>
    posts.filter((post) => (post.time === "Вчера" ? 3 : 4) === day),
  );
  const series = [
    daily.map((items) => items.length),
    daily.map(
      (items) =>
        items.filter((post) => ["Новый", "На проверке"].includes(post.state))
          .length,
    ),
    daily.map(
      (items) => items.filter((post) => post.state === "Готово").length,
    ),
  ];
  const maximum = Math.max(3, ...series.flat());
  const line = (values: number[]) =>
    values
      .map(
        (value, index) =>
          `${index === 0 ? "M" : "L"}${index * 100} ${178 - (value / maximum) * 168}`,
      )
      .join(" ");
  return (
    <div className="flow-chart">
      <div className="y-axis">
        <span>{maximum}</span>
        <span>{Math.round((maximum * 2) / 3)}</span>
        <span>{Math.round(maximum / 3)}</span>
        <span>0</span>
      </div>
      <div className="plot">
        <div className="grid-lines" />
        <svg
          viewBox="0 0 600 180"
          preserveAspectRatio="none"
          role="img"
          aria-label="Демонстрационный поток материалов за выбранную неделю"
        >
          <path d={line(series[0])} stroke="#279cff" />
          <path d={line(series[1])} stroke="#f6ac59" />
          <path d={line(series[2])} stroke="#28d6c7" />
        </svg>
        <div className="x-axis">
          {[
            "28 сен",
            "29 сен",
            "30 сен",
            "1 окт",
            "2 окт",
            "3 окт",
            "4 окт",
          ].map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function Inbox({
  data,
  setData,
  markDirty,
  demo,
  globalQuery,
}: WorkspaceProps & { demo: boolean; globalQuery: string }) {
  const [live, setLive] = useState<Post[]>([]);
  const [apiState, setApiState] = useState("idle");
  const [apiError, setApiError] = useState("");
  const [reload, setReload] = useState(0);
  const [selectedId, setSelectedId] = useState("mars");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("Все");
  const [notice, setNotice] = useState("");
  const [schedule, setSchedule] = useState(false);
  const [pendingApplyId, setPendingApplyId] = useState<string | null>(null);
  useEffect(() => {
    setQuery(globalQuery);
  }, [globalQuery]);
  useEffect(() => {
    if (demo) return;
    const controller = new AbortController();
    setApiState("loading");
    setApiError("");
    loadInbox(controller.signal)
      .then((items) => {
        setLive(items);
        setApiState("ready");
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setApiState("error");
          setApiError(
            error instanceof Error ? error.message : "Ошибка загрузки",
          );
        }
      });
    return () => controller.abort();
  }, [demo, reload]);
  const items = demo ? data.posts : live;
  const visible = items.filter(
    (item) =>
      (filter === "Все" || item.state === filter) &&
      `${item.title} ${item.source}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const selected = visible.find((item) => item.id === selectedId);
  const dirty = data.posts.some((item) => Boolean(item.draft));
  useEffect(() => markDirty("inbox", dirty), [dirty, markDirty]);
  const update = (post: Post, patch: Partial<Post>) =>
    setData((prior) => ({
      ...prior,
      posts: prior.posts.map((item) =>
        item.id === post.id ? { ...item, ...patch } : item,
      ),
    }));
  const applySuggestion = (postId: string) => {
    if (!demo) return;
    setData((prior) => ({
      ...prior,
      posts: prior.posts.map((post) =>
        post.id === postId && canProcess(post)
          ? { ...post, draft: post.suggestion }
          : post,
      ),
    }));
    setPendingApplyId(null);
    setNotice(
      "Черновик применён только в DEMO. Оригинал сохранён без изменений.",
    );
  };
  const apply = () => {
    if (!demo || !selected || !canProcess(selected)) return;
    if (selected.draft && selected.draft !== selected.suggestion) {
      setPendingApplyId(selected.id);
      return;
    }
    applySuggestion(selected.id);
  };
  const approve = () => {
    if (!demo || !selected || !canProcess(selected)) return;
    update(selected, { state: "Готово" });
    setNotice("Материал одобрен в DEMO. Публикация не выполнена.");
  };
  if (!demo && apiState === "loading")
    return (
      <Panel>
        <div className="empty-state" role="status">
          Загрузка входящих…
        </div>
      </Panel>
    );
  if (!demo && apiState === "error")
    return (
      <Panel>
        <div className="empty-state">
          <Icon name="close" />
          <h2>Не удалось загрузить входящие</h2>
          <p role="alert">{apiError}</p>
          <button onClick={() => setReload((prior) => prior + 1)}>
            Повторить
          </button>
        </div>
      </Panel>
    );
  return (
    <div className="inbox-layout">
      <Panel className="inbox-list">
        <Search
          value={query}
          onChange={setQuery}
          placeholder="Поиск по входящим"
        />
        <div className="filter-row">
          {["Все", "Новый", "На проверке", "Готово", "Отклонён"].map(
            (value) => (
              <button
                key={value}
                className={`filter ${filter === value ? "active" : ""}`}
                onClick={() => setFilter(value)}
              >
                {value}
                <em>
                  {value === "Все"
                    ? items.length
                    : items.filter((item) => item.state === value).length}
                </em>
              </button>
            ),
          )}
        </div>
        <div className="inbox-queue">
          {visible.map((item) => (
            <button
              className={`inbox-card ${selected?.id === item.id ? "selected" : ""}`}
              key={item.id}
              onClick={() => {
                setSelectedId(item.id);
                setNotice("");
              }}
            >
              <Artwork kind={item.art || "tech"} />
              <span className="post-summary">
                <span className="post-byline">
                  <Icon name="channels" size={16} />
                  <b>{item.source}</b>
                  <small>{item.time}</small>
                </span>
                <strong>{item.title}</strong>
                <Status value={item.state} />
              </span>
            </button>
          ))}
          {!visible.length && (
            <div className="empty-state">
              <h3>Материалы не найдены</h3>
              <p>
                {query
                  ? "Измените поисковый запрос или фильтр."
                  : "Очередь входящих пуста."}
              </p>
            </div>
          )}
        </div>
      </Panel>
      <Panel className="article-panel">
        {selected ? (
          <>
            <div className="article-meta">
              <Artwork kind={selected.art || "tech"} />
              <div>
                <b>{selected.source}</b>
                <small>Telegram · ревизия {selected.revision}</small>
              </div>
              <Status value={selected.state} />
            </div>
            <div className="article-tags">
              <span>
                <Icon name="clock" size={15} />
                {selected.time}
              </span>
              <span>Оригинал из Telegram · неизменяемый</span>
            </div>
            <h2>{selected.title}</h2>
            <div className="original-copy" aria-label="Оригинал материала">
              {selected.original.split("\n\n").map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </div>
            {demo && (
              <div className="article-media">
                <Artwork kind={selected.art} />
                <span>Иллюстрация DEMO</span>
              </div>
            )}
            <section className="rewrite-box">
              <PanelTitle title="Предложение AI" icon="spark">
                <button
                  className="small-button"
                  disabled={
                    !demo || !canProcess(selected) || !selected.suggestion
                  }
                  onClick={apply}
                  title={
                    !canProcess(selected)
                      ? "EditorialGate не разрешил рерайт"
                      : "Применить к черновику"
                  }
                >
                  Применить вариант
                </button>
              </PanelTitle>
              <p>
                {selected.suggestion ||
                  (canProcess(selected)
                    ? "AI-вариант пока отсутствует. Провайдер не вызывается в DEMO."
                    : "EditorialGate не разрешил рерайт. AI-вызовы недоступны.")}
              </p>
            </section>
            <label className="field">
              Черновик редактора
              <textarea
                aria-label="Черновик варианта"
                value={selected.draft}
                disabled={!demo || !canProcess(selected)}
                placeholder="Примените предложение или введите ручной вариант"
                onChange={(event) =>
                  update(selected, { draft: event.target.value })
                }
              />
            </label>
            {selected.draft && (
              <button
                className="small-button"
                onClick={() => update(selected, { draft: "" })}
              >
                Отменить черновик
              </button>
            )}
            {selected.editorial === "REJECT" && (
              <Notice error>
                EDITORIAL REJECT: рерайт и планирование запрещены.
              </Notice>
            )}
            {notice && <Notice>{notice}</Notice>}
          </>
        ) : (
          <div className="empty-state">
            <Icon name="inbox" size={36} />
            <h2>Выберите материал</h2>
            <p>Оригинал и действия появятся после выбора строки.</p>
          </div>
        )}
      </Panel>
      <div className="inbox-actions">
        <Panel>
          <PanelTitle title="Куда публиковать" icon="channels" />
          {demo && selected ? (
            data.channels.map((channel) => (
              <label className="destination" key={channel.id}>
                <input
                  type="checkbox"
                  checked={selected.destinations.includes(channel.id)}
                  onChange={(event) =>
                    update(selected, {
                      destinations: event.target.checked
                        ? [...selected.destinations, channel.id]
                        : selected.destinations.filter(
                            (id) => id !== channel.id,
                          ),
                    })
                  }
                  disabled={!canProcess(selected)}
                />
                <Artwork kind={channel.art} />
                <span>
                  <b>{channel.name}</b>
                  <small>{channel.subscribers} подписчиков</small>
                </span>
              </label>
            ))
          ) : (
            <p className="help-copy">
              Получатели появятся после подключения рабочего API маршрутов.
            </p>
          )}
        </Panel>
        <Panel>
          <PanelTitle title="Публикация" icon="clock" />
          <p className="help-copy">
            Одобрение сохраняет решение редактора. Время публикации задаётся
            отдельно в планировщике.
          </p>
          <div className="policy-note">
            <Icon name="shield" size={20} />
            <span>
              Ручное подтверждение
              <br />
              <small>EditorialGate проверяется до действий</small>
            </span>
          </div>
        </Panel>
        <button
          className="primary-button full"
          disabled={!demo || !selected || !canProcess(selected)}
          aria-label="Одобрить материал"
          onClick={approve}
        >
          <Icon name="check" />
          Одобрить
        </button>
        <button
          className="danger-button full"
          disabled={!demo || !selected}
          aria-label="Отклонить материал"
          onClick={() => {
            if (selected) {
              update(selected, {
                state: "Отклонён",
                editorial: "REJECT",
                rewriteAllowed: false,
                suggestion: "",
              });
              setData((prior) => ({
                ...prior,
                scheduled: prior.scheduled.filter(
                  (job) => job.postId !== selected.id,
                ),
              }));
              setNotice(
                "Материал отклонён только в DEMO. Незавершённые планы удалены.",
              );
            }
          }}
        >
          <Icon name="close" />
          Отклонить
        </button>
        <button
          className="full"
          aria-label="Запланировать"
          disabled={!demo || !selected || !canProcess(selected)}
          onClick={() => setSchedule(true)}
        >
          <Icon name="planner" />
          Запланировать
        </button>
        <button
          className="full"
          aria-label="Опубликовать"
          disabled
          title="API публикации пока не реализован"
        >
          <Icon name="channels" />
          Опубликовать <small>требуется API</small>
        </button>
      </div>
      {schedule && selected && (
        <ScheduleDialog
          data={data}
          setData={setData}
          postId={selected.id}
          onClose={() => setSchedule(false)}
        />
      )}
      {pendingApplyId && (
        <Modal
          title="Заменить ручной черновик?"
          onClose={() => setPendingApplyId(null)}
        >
          <p>
            AI-вариант заменит текущие ручные правки. Оригинал Telegram
            останется неизменным.
          </p>
          <div className="action-row">
            <button onClick={() => setPendingApplyId(null)}>
              Сохранить ручной текст
            </button>
            <button
              className="primary-button"
              onClick={() => applySuggestion(pendingApplyId)}
            >
              Заменить вариантом AI
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export function ScheduleDialog({
  data,
  setData,
  postId,
  existingJobId,
  onClose,
}: Pick<WorkspaceProps, "data" | "setData"> & {
  postId: string;
  existingJobId?: string;
  onClose: () => void;
}) {
  const existing = data.scheduled.find(
    (job) =>
      job.postId === postId &&
      (existingJobId
        ? job.id === existingJobId
        : job.channelId ===
          data.posts.find((post) => post.id === postId)?.destinations[0]),
  );
  const [date, setDate] = useState(existing?.date ?? "2026-10-02");
  const [time, setTime] = useState(existing?.time ?? "15:00");
  const [channelId, setChannelId] = useState(
    existing?.channelId ??
      data.posts.find((item) => item.id === postId)?.destinations[0] ??
      "",
  );
  const [error, setError] = useState("");
  const [targetDrafts, setTargetDrafts] = useState<
    Record<string, { date: string; time: string }>
  >({});
  const chooseTarget = (nextId: string) => {
    if (!existingJobId) {
      const saved =
        targetDrafts[nextId] ??
        data.scheduled.find(
          (job) => job.postId === postId && job.channelId === nextId,
        );
      setTargetDrafts((prior) => ({ ...prior, [channelId]: { date, time } }));
      if (saved) {
        setDate(saved.date);
        setTime(saved.time);
      }
    }
    setChannelId(nextId);
  };
  const save = () => {
    const problem = scheduleError(
      data.posts.find((item) => item.id === postId),
      data.channels.find((item) => item.id === channelId),
      date,
      time,
    );
    if (problem) {
      setError(problem);
      return;
    }
    setData((prior) => {
      if (
        scheduleError(
          prior.posts.find((item) => item.id === postId),
          prior.channels.find((item) => item.id === channelId),
          date,
          time,
        )
      )
        return prior;
      const id = `${postId}-${channelId}`;
      return {
        ...prior,
        scheduled: [
          ...prior.scheduled.filter(
            (job) => job.id !== id && job.id !== existingJobId,
          ),
          { id, postId, channelId, date, time },
        ],
      };
    });
    onClose();
  };
  return (
    <Modal title="Планирование в DEMO" onClose={onClose}>
      <p>
        Расписание сохраняется в памяти рабочего пространства.
        Telegram-публикация не выполняется.
      </p>
      <label className="field">
        Канал
        <select
          aria-label="Канал"
          value={channelId}
          onChange={(event) => chooseTarget(event.target.value)}
        >
          <option value="">Выберите канал</option>
          {data.channels.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      {data.scheduled.some(
        (job) => job.postId === postId && job.channelId === channelId,
      ) && (
        <p className="help-copy">
          Для этого материала и канала уже есть запись. Сохранение явно обновит
          её дату и время, не создавая дубликат.
        </p>
      )}
      <div className="form-grid">
        <label className="field">
          Дата
          <input
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
        <label className="field">
          Время
          <input
            type="time"
            value={time}
            onChange={(event) => setTime(event.target.value)}
          />
        </label>
      </div>
      <p className="help-copy">
        Europe/Minsk · UTC+3. Проверяются окно публикации и тихие часы.
      </p>
      {error && <Notice error>{error}</Notice>}
      <div className="action-row">
        <button onClick={onClose}>Отмена</button>
        <button className="primary-button" onClick={save}>
          Сохранить расписание DEMO
        </button>
      </div>
    </Modal>
  );
}

function Donors({ data, setData, markDirty }: WorkspaceProps) {
  const [selectedId, setSelectedId] = useState(data.donors[0].id);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("Все");
  const selected = data.donors.find((item) => item.id === selectedId)!;
  const [draft, setDraft] = useState<Donor>(selected);
  const [notice, setNotice] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [raw, setRaw] = useState("");
  const [report, setReport] = useState("");
  const dirty = JSON.stringify(selected) !== JSON.stringify(draft);
  useEffect(() => markDirty("donors", dirty), [dirty, markDirty]);
  const choose = (donor: Donor) => {
    if (dirty) {
      setNotice("Сохраните или отмените правки перед выбором другого донора.");
      return;
    }
    setSelectedId(donor.id);
    setDraft(donor);
    setNotice("");
  };
  const parsed = validateDonors(
    raw,
    data.donors.map((item) => item.id),
  );
  const importDemo = () => {
    const valid = parsed.filter((row) => !row.error);
    if (!valid.length) return;
    setData((prior) => ({
      ...prior,
      donors: [
        ...prior.donors,
        ...valid.map((row) => ({
          id: row.id,
          name: row.id.slice(1),
          category: "Без категории",
          art: "tech",
          state: "На проверке",
          enabled: false,
          daily: 0,
          synced: "Не синхронизирован",
          words: "",
          media: "Только текст",
        })),
      ],
    }));
    setReport(
      `Добавлено в память DEMO: ${valid.length}. Подключение к Telegram не выполнялось.`,
    );
    setRaw("");
  };
  return (
    <>
      <div className="metric-row">
        <Metric
          title="Активные источники"
          value={data.donors.filter((item) => item.state === "Активен").length}
          icon="check"
          tone="green"
        />
        <Metric
          title="Требуют проверки"
          value={
            data.donors.filter((item) => item.state === "На проверке").length
          }
          icon="clock"
          tone="orange"
        />
        <Metric
          title="На паузе"
          value={data.donors.filter((item) => !item.enabled).length}
          icon="pause"
          tone="muted"
        />
        <Metric
          title="Всего источников"
          value={data.donors.length}
          icon="donors"
          tone="blue"
        />
      </div>
      <div className="donors-layout">
        <Panel>
          <div className="toolbar">
            <Search
              value={query}
              onChange={setQuery}
              placeholder="Поиск по источникам"
            />
            <button
              onClick={() => {
                setImportOpen(true);
                setReport("");
              }}
            >
              <Icon name="upload" size={18} />
              Импорт
            </button>
          </div>
          <div className="filter-row">
            {["Все", "Активен", "На проверке", "На паузе"].map((value) => (
              <button
                className={`filter ${filter === value ? "active" : ""}`}
                key={value}
                onClick={() => setFilter(value)}
              >
                {value}
              </button>
            ))}
          </div>
          <div className="table-scroller">
            <table className="directory-table">
              <thead>
                <tr>
                  <th>Источник</th>
                  <th>Категория</th>
                  <th>Частота</th>
                  <th>Статус</th>
                  <th>Последняя синхр.</th>
                </tr>
              </thead>
              <tbody>
                {data.donors
                  .filter(
                    (item) =>
                      (filter === "Все" || item.state === filter) &&
                      `${item.name} ${item.id}`
                        .toLowerCase()
                        .includes(query.toLowerCase()),
                  )
                  .map((item) => (
                    <tr
                      key={item.id}
                      className={selectedId === item.id ? "selected" : ""}
                    >
                      <td>
                        <button
                          className="table-identity"
                          onClick={() => choose(item)}
                        >
                          <Artwork kind={item.art} />
                          <span>
                            <b>{item.name}</b>
                            <small>{item.id}</small>
                          </span>
                        </button>
                      </td>
                      <td>
                        <span className="chip">{item.category}</span>
                      </td>
                      <td>{item.daily} / день</td>
                      <td>
                        <Status value={item.state} />
                      </td>
                      <td className="small-muted">{item.synced}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <div className="table-footer">
            Всего источников: {data.donors.length}
            <span>Только Telegram</span>
          </div>
        </Panel>
        <Panel>
          <div className="profile-title">
            <Artwork kind={selected.art} large />
            <div>
              <h2>{selected.name}</h2>
              <p>{selected.id}</p>
            </div>
            <Status value={selected.state} />
          </div>
          <p className="description">
            Материалы источника проходят технические фильтры, проверку дублей и
            EditorialGate.
          </p>
          <div className="chip-row">
            <span className="chip">{selected.category}</span>
            <span className="chip">Telegram</span>
          </div>
          <div className="section-divider" />
          <PanelTitle title="Настройки источника" icon="settings" />
          <Toggle
            label="Включён для сбора"
            checked={draft.enabled}
            onChange={(enabled) => setDraft({ ...draft, enabled })}
          />
          <label className="field">
            Допустимые типы
            <select
              value={draft.media}
              onChange={(event) =>
                setDraft({ ...draft, media: event.target.value })
              }
            >
              <option>Текст и фото</option>
              <option>Только текст</option>
            </select>
          </label>
          <label className="field">
            Стоп-слова
            <input
              value={draft.words}
              onChange={(event) =>
                setDraft({ ...draft, words: event.target.value })
              }
              placeholder="Через запятую"
            />
          </label>
          <p className="help-copy">
            Видео и запрещённые материалы исключаются до AI-классификации.
          </p>
          <DraftActions
            dirty={dirty}
            onCancel={() => {
              setDraft(selected);
              setNotice("");
            }}
            onSave={() => {
              setData((prior) => ({
                ...prior,
                donors: prior.donors.map((item) =>
                  item.id === draft.id
                    ? {
                        ...draft,
                        state: draft.enabled ? "Активен" : "На паузе",
                      }
                    : item,
                ),
              }));
              setDraft({
                ...draft,
                state: draft.enabled ? "Активен" : "На паузе",
              });
              setNotice("Настройки сохранены в памяти DEMO.");
            }}
          />
          {notice && <Notice>{notice}</Notice>}
          <div className="section-divider" />
          <PanelTitle title="Сбор материалов" icon="chart" />
          <div className="detail-metrics">
            <div>
              <b>{selected.daily}</b>
              <small>в день · DEMO</small>
            </div>
            <div>
              <b>{selected.synced}</b>
              <small>последняя синхронизация</small>
            </div>
          </div>
        </Panel>
      </div>
      {importOpen && (
        <Modal title="Импорт доноров" onClose={() => setImportOpen(false)}>
          <p>
            По одному @username или https://t.me/username в строке. Источники
            добавляются только в память DEMO.
          </p>
          <label className="field">
            Список доноров
            <textarea
              aria-label="Список доноров для импорта"
              value={raw}
              onChange={(event) => setRaw(event.target.value)}
              placeholder="@new_science\nhttps://t.me/another_source"
            />
          </label>
          <div className="validation-list">
            {parsed.map((row, index) => (
              <div key={index}>
                <span>{row.input}</span>
                <span className={row.error ? "negative" : "positive"}>
                  {row.error || "Корректно"}
                </span>
              </div>
            ))}
          </div>
          {report && <Notice>{report}</Notice>}
          <div className="action-row">
            <button onClick={() => setImportOpen(false)}>Закрыть</button>
            <button
              className="primary-button"
              disabled={!parsed.some((row) => !row.error)}
              onClick={importDemo}
            >
              Добавить корректные в DEMO
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

export function DraftActions({
  dirty,
  onSave,
  onCancel,
  saveLabel = "Сохранить",
}: {
  dirty: boolean;
  onSave: () => void;
  onCancel: () => void;
  saveLabel?: string;
}) {
  return (
    <div className="draft-actions">
      <span className={dirty ? "dirty-label" : "small-muted"}>
        {dirty
          ? "Есть несохранённые изменения"
          : "DEMO · изменения в памяти окна"}
      </span>
      <div className="action-row">
        <button disabled={!dirty} onClick={onCancel}>
          Отмена
        </button>
        <button className="primary-button" disabled={!dirty} onClick={onSave}>
          {saveLabel}
        </button>
      </div>
    </div>
  );
}

function Channels({ data, setData, markDirty }: WorkspaceProps) {
  const [selectedId, setSelectedId] = useState("tech");
  const [query, setQuery] = useState("");
  const [modeFilter, setModeFilter] = useState("Все режимы");
  const [tab, setTab] = useState("Публикации");
  const selected = data.channels.find((item) => item.id === selectedId)!;
  const [draft, setDraft] = useState<Channel>(selected);
  const [notice, setNotice] = useState("");
  const dirty = JSON.stringify(selected) !== JSON.stringify(draft);
  useEffect(() => markDirty("channels", dirty), [dirty, markDirty]);
  const choose = (item: Channel) => {
    if (dirty) {
      setNotice("Сохраните или отмените правки перед выбором другого канала.");
      return;
    }
    setSelectedId(item.id);
    setDraft(item);
    setNotice("");
  };
  const save = () => {
    const problem = channelSettingsError(draft);
    if (problem) {
      setNotice(problem);
      return;
    }
    setData((prior) => ({
      ...prior,
      channels: prior.channels.map((item) =>
        item.id === draft.id ? draft : item,
      ),
    }));
    setNotice("Настройки канала сохранены только в DEMO.");
  };
  return (
    <div className="channels-layout">
      <div className="channel-directory">
        <div className="toolbar">
          <Search
            value={query}
            onChange={setQuery}
            placeholder="Поиск по каналам"
          />
          <select
            aria-label="Фильтр режима канала"
            value={modeFilter}
            onChange={(event) => setModeFilter(event.target.value)}
          >
            <option>Все режимы</option>
            <option>Ручной</option>
            <option>С проверкой</option>
          </select>
          <button disabled title="Создание канала требует API">
            <Icon name="plus" size={18} />
            Добавить канал
          </button>
        </div>
        {data.channels
          .filter(
            (item) =>
              item.name.toLowerCase().includes(query.toLowerCase()) &&
              (modeFilter === "Все режимы" || item.mode === modeFilter),
          )
          .map((item) => (
            <button
              className={`channel-card ${item.id === selectedId ? "selected" : ""}`}
              key={item.id}
              onClick={() => choose(item)}
            >
              <Artwork kind={item.art} large />
              <span className="channel-identity">
                <b>{item.name}</b>
                <small>{item.subscribers} подписчиков</small>
                <em className="chip">{item.category}</em>
              </span>
              <span className="channel-stat">
                <small>Лимит</small>
                <b>{item.daily}/день</b>
              </span>
              <span className="channel-stat">
                <small>Тихие часы</small>
                <b>
                  {item.quietStart} — {item.quietEnd}
                </b>
              </span>
              <span className="channel-stat">
                <small>Режим</small>
                <b className="cyan-text">{item.mode}</b>
              </span>
              <span className="channel-stat">
                <small>Сегодня</small>
                <b>
                  {item.today} / {item.daily}
                </b>
                <span className="progress">
                  <i
                    style={{
                      width: `${Math.min(100, (item.today / item.daily) * 100)}%`,
                    }}
                  />
                </span>
              </span>
            </button>
          ))}
      </div>
      <Panel className="channel-detail">
        <div className="profile-title">
          <Artwork kind={selected.art} large />
          <div>
            <h2>{selected.name}</h2>
            <p>{selected.subscribers} подписчиков</p>
          </div>
        </div>
        <p className="description">
          {selected.category}: материалы проходят проверку редактора перед
          публикацией.
        </p>
        <div className="channel-link">
          <Icon name="connections" size={20} />
          <span>Telegram · DEMO-канал</span>
        </div>
        <div className="detail-tabs">
          {["Публикации", "AI-профиль", "Правила", "Статистика"].map(
            (value) => (
              <button
                key={value}
                className={tab === value ? "active" : ""}
                onClick={() => setTab(value)}
              >
                {value}
              </button>
            ),
          )}
        </div>
        {tab === "Публикации" && (
          <>
            <section className="detail-section">
              <PanelTitle title="Окно публикаций" icon="clock" />
              <p className="help-copy">
                В какое время можно планировать материалы
              </p>
              <div className="form-grid">
                <label className="field">
                  С
                  <input
                    type="time"
                    value={draft.windowStart}
                    onChange={(event) =>
                      setDraft({ ...draft, windowStart: event.target.value })
                    }
                  />
                </label>
                <label className="field">
                  До
                  <input
                    type="time"
                    value={draft.windowEnd}
                    onChange={(event) =>
                      setDraft({ ...draft, windowEnd: event.target.value })
                    }
                  />
                </label>
              </div>
              <div className="weekday-row">
                {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => (
                  <span key={day}>{day}</span>
                ))}
              </div>
            </section>
            <section className="detail-section">
              <PanelTitle title="Тихие часы" icon="moon" />
              <div className="form-grid">
                <label className="field">
                  Начало тихих часов
                  <input
                    type="time"
                    value={draft.quietStart}
                    onChange={(event) =>
                      setDraft({ ...draft, quietStart: event.target.value })
                    }
                  />
                </label>
                <label className="field">
                  Конец тихих часов
                  <input
                    type="time"
                    value={draft.quietEnd}
                    onChange={(event) =>
                      setDraft({ ...draft, quietEnd: event.target.value })
                    }
                  />
                </label>
              </div>
            </section>
            <section className="detail-section">
              <PanelTitle title="Режим публикации" icon="channels" />
              <label className="field">
                Режим
                <select
                  value={draft.mode}
                  onChange={(event) =>
                    setDraft({ ...draft, mode: event.target.value })
                  }
                >
                  <option>Ручной</option>
                  <option>С проверкой</option>
                </select>
              </label>
              <p className="help-copy">
                Автопубликация требует серверной политики и пока недоступна.
              </p>
            </section>
            <section className="detail-section">
              <PanelTitle title="Недельное окно" icon="planner" />
              <div className="hour-map">
                {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => (
                  <div key={day}>
                    <small>{day}</small>
                    {Array.from({ length: 24 }, (_, hour) => (
                      <i
                        className={
                          hour >= Number(draft.windowStart.slice(0, 2)) &&
                          hour < Number(draft.windowEnd.slice(0, 2))
                            ? "on"
                            : ""
                        }
                        key={hour}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
        {tab === "AI-профиль" && (
          <section className="detail-section">
            <PanelTitle title="AI-профиль канала" icon="spark" />
            <label className="field">
              Стиль
              <select
                value={draft.profile}
                onChange={(event) =>
                  setDraft({ ...draft, profile: event.target.value })
                }
              >
                <option>Нейтральный, без домыслов</option>
                <option>Краткий</option>
              </select>
            </label>
            <p className="help-copy">
              Смена профиля не вызывает AI. Факты и редакторские ограничения
              обязательны.
            </p>
          </section>
        )}
        {tab === "Правила" && (
          <section className="detail-section">
            <label className="field">
              Дневной лимит
              <input
                type="number"
                min="1"
                max="100"
                value={draft.daily}
                onChange={(event) =>
                  setDraft({ ...draft, daily: Number(event.target.value) })
                }
              />
            </label>
            <p className="policy-note">
              <Icon name="shield" />
              EditorialGate проверяется повторно перед публикацией.
            </p>
          </section>
        )}
        {tab === "Статистика" && (
          <section className="detail-section">
            <div className="detail-metrics">
              <div>
                <b>
                  {selected.today} / {selected.daily}
                </b>
                <small>сегодня · DEMO</small>
              </div>
              <div>
                <b>{selected.subscribers}</b>
                <small>подписчиков · DEMO</small>
              </div>
            </div>
            <p className="help-copy">
              История и аналитика ожидают рабочий API.
            </p>
          </section>
        )}
        <DraftActions
          dirty={dirty}
          onCancel={() => {
            setDraft(selected);
            setNotice("");
          }}
          onSave={save}
          saveLabel="Сохранить настройки DEMO"
        />
        {notice && <Notice>{notice}</Notice>}
      </Panel>
    </div>
  );
}
