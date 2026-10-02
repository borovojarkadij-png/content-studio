import { useEffect, useState } from "react";
import { DraftActions, ScheduleDialog, type WorkspaceProps } from "./App";
import {
  calendarSlots,
  canProcess,
  datePlus,
  demoWeekStart,
  type Route,
  type ScheduledPost,
} from "./studio";
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
} from "./ui";

export function Connections({ data, setData, markDirty }: WorkspaceProps) {
  const [selectedId, setSelectedId] = useState(data.routes[0].id);
  const [sourceId, setSourceId] = useState("");
  const [query, setQuery] = useState("");
  const selected = data.routes.find((item) => item.id === selectedId)!;
  const [draft, setDraft] = useState<Route>(selected);
  const [notice, setNotice] = useState("");
  const dirty = JSON.stringify(selected) !== JSON.stringify(draft);
  useEffect(() => markDirty("connections", dirty), [dirty, markDirty]);
  const choose = (item: Route) => {
    if (dirty) {
      setNotice("Сохраните или отмените правки перед выбором другой связи.");
      return;
    }
    setSelectedId(item.id);
    setDraft(item);
    setNotice("");
  };
  const donor = data.donors.find((item) => item.id === selected.donorId)!;
  const channel = data.channels.find((item) => item.id === selected.channelId)!;
  return (
    <div className="connections-layout">
      <Panel className="connection-sources">
        <PanelTitle title="Источники (доноры)" icon="donors" />
        <p className="help-copy">Telegram-каналы, откуда берём материалы</p>
        <Search
          value={query}
          onChange={setQuery}
          placeholder="Поиск источников"
        />
        <button
          className={`source-row all-source ${!sourceId ? "selected" : ""}`}
          onClick={() => setSourceId("")}
        >
          Все источники <span>{data.donors.length}</span>
        </button>
        {data.donors
          .filter((item) =>
            item.name.toLowerCase().includes(query.toLowerCase()),
          )
          .map((item) => (
            <button
              className={`source-row ${sourceId === item.id ? "selected" : ""}`}
              key={item.id}
              onClick={() => setSourceId(item.id)}
            >
              <Artwork kind={item.art} />
              <span>
                <b>{item.name}</b>
                <small>Telegram-канал</small>
              </span>
              <small>
                {item.daily}
                <br />в день
              </small>
            </button>
          ))}
      </Panel>
      <Panel className="route-directory">
        <PanelTitle title="Маршруты" icon="connections" />
        <p className="help-copy">Куда и по каким правилам направлять</p>
        {data.routes
          .filter((item) => !sourceId || item.donorId === sourceId)
          .map((item) => {
            const source = data.donors.find(
              (entry) => entry.id === item.donorId,
            )!;
            const target = data.channels.find(
              (entry) => entry.id === item.channelId,
            )!;
            return (
              <button
                className={`route-card ${selectedId === item.id ? "selected" : ""}`}
                key={item.id}
                onClick={() => choose(item)}
              >
                <div className="route-card-header">
                  <Artwork kind={source.art} />
                  <span>
                    <b>{source.name}</b>
                    <small>→ {target.name}</small>
                  </span>
                  <span
                    className={`route-state ${item.enabled ? "positive" : "small-muted"}`}
                  >
                    <i />
                    {item.enabled ? "Активна" : "Пауза"}
                  </span>
                </div>
                <div className="route-summary">
                  <span>
                    <b>{item.intake}%</b>
                    <small>отбор входящих</small>
                  </span>
                  <span>
                    <b>{item.mix}%</b>
                    <small>доля в канале</small>
                  </span>
                  <span>
                    <b>{item.policy}</b>
                    <small>модерация</small>
                  </span>
                </div>
              </button>
            );
          })}
        {sourceId && !data.routes.some((item) => item.donorId === sourceId) && (
          <div className="empty-state">
            <p>Для источника нет маршрутов.</p>
            <button disabled title="Создание маршрута требует API">
              Добавить маршрут
            </button>
          </div>
        )}
      </Panel>
      <Panel className="route-editor">
        <PanelTitle title="Настройки маршрута" />
        <p className="help-copy">
          {donor.name} → {channel.name}
        </p>
        <div className="route-pair">
          <div>
            <Artwork kind={donor.art} />
            <span>
              <small>Источник</small>
              <b>{donor.name}</b>
            </span>
          </div>
          <div>
            <Artwork kind={channel.art} />
            <span>
              <small>Целевой канал</small>
              <b>{channel.name}</b>
            </span>
          </div>
        </div>
        <RangeField
          label="Доля входящих материалов"
          help="Сколько постов донора направлять на рассмотрение"
          value={draft.intake}
          onChange={(intake) => setDraft({ ...draft, intake })}
        />
        <RangeField
          label="Целевая доля в канале"
          help="Желаемая доля донора среди публикаций канала"
          value={draft.mix}
          onChange={(mix) => setDraft({ ...draft, mix })}
          violet
        />
        <fieldset className="policy-options">
          <legend>Политика модерации</legend>
          {["С проверкой", "Только вручную"].map((policy) => (
            <label key={policy}>
              <input
                type="radio"
                name="route-policy"
                checked={draft.policy === policy}
                onChange={() => setDraft({ ...draft, policy })}
              />
              <span>
                <b>{policy}</b>
                <small>
                  {policy === "С проверкой"
                    ? "Сначала во входящие для редактора"
                    : "Ручной отбор и отдельное подтверждение"}
                </small>
              </span>
            </label>
          ))}
        </fieldset>
        <section className="detail-section">
          <h3>Разрешённые типы контента</h3>
          <div className="checkbox-row">
            <label>
              <input
                type="checkbox"
                checked={draft.text}
                onChange={(event) =>
                  setDraft({ ...draft, text: event.target.checked })
                }
              />
              Текст
            </label>
            <label>
              <input
                type="checkbox"
                checked={draft.photo}
                onChange={(event) =>
                  setDraft({ ...draft, photo: event.target.checked })
                }
              />
              Фото
            </label>
            <span className="small-muted">Видео исключено фильтром</span>
          </div>
        </section>
        <Toggle
          label="Маршрут активен"
          checked={draft.enabled}
          onChange={(enabled) => setDraft({ ...draft, enabled })}
        />
        <details className="advanced-filters">
          <summary>Дополнительные фильтры</summary>
          <p className="help-copy">
            Exact dedup и EditorialGate обязательны. Управление защищёнными
            сущностями ожидает серверный API.
          </p>
        </details>
        <DraftActions
          dirty={dirty}
          saveLabel="Сохранить изменения"
          onCancel={() => {
            setDraft(selected);
            setNotice("");
          }}
          onSave={() => {
            if (!draft.text && !draft.photo) {
              setNotice("Разрешите хотя бы один тип контента.");
              return;
            }
            setData((prior) => ({
              ...prior,
              routes: prior.routes.map((item) =>
                item.id === draft.id ? draft : item,
              ),
            }));
            setNotice("Настройки сохранены только в DEMO.");
          }}
        />
        {notice && <Notice>{notice}</Notice>}
      </Panel>
    </div>
  );
}
function RangeField({
  label,
  help,
  value,
  onChange,
  violet = false,
}: {
  label: string;
  help: string;
  value: number;
  onChange: (value: number) => void;
  violet?: boolean;
}) {
  return (
    <label className={`range-field ${violet ? "violet-range" : ""}`}>
      <b>{label}</b>
      <small>{help}</small>
      <div>
        <input
          aria-label={label}
          type="range"
          min="0"
          max="100"
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <output>
          {value}
          <small>%</small>
        </output>
      </div>
    </label>
  );
}

export function Planner({ data, setData }: WorkspaceProps) {
  const [week, setWeek] = useState(demoWeekStart);
  const [channelFilter, setChannelFilter] = useState("");
  const [view, setView] = useState("Неделя");
  const [day, setDay] = useState("2026-10-02");
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [editingJobId, setEditingJobId] = useState<string | undefined>();
  const [slotJobs, setSlotJobs] = useState<ScheduledPost[] | null>(null);
  const days =
    view === "День"
      ? [day]
      : Array.from({ length: 7 }, (_, index) => datePlus(week, index));
  const unscheduled = data.posts.filter(
    (item) =>
      !data.scheduled.some((job) => job.postId === item.id) && canProcess(item),
  );
  const scheduled = data.scheduled.filter(
    (item) => !channelFilter || item.channelId === channelFilter,
  );
  const formatDate = (date: string) =>
    new Date(`${date}T12:00:00Z`).toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "short",
      timeZone: "UTC",
    });
  const visibleJobs = scheduled.filter((item) => days.includes(item.date));
  const startHour = Math.min(
    9,
    ...visibleJobs.map((job) => Number(job.time.slice(0, 2))),
  );
  const endHour = Math.min(
    23,
    Math.max(21, ...visibleJobs.map((job) => Number(job.time.slice(0, 2)) + 3)),
  );
  const timelineHeight = Math.max(
    (endHour - startHour + 1) * 48,
    ...visibleJobs.map(
      (job) =>
        (Number(job.time.slice(0, 2)) * 60 +
          Number(job.time.slice(3)) -
          startHour * 60) *
          0.8 +
        128,
    ),
  );
  const busiest = days.map((date) => ({
    date,
    count: scheduled.filter((job) => job.date === date).length,
  }));
  return (
    <div className="planner-layout">
      <div className="calendar-column">
        <div className="calendar-toolbar">
          <button
            aria-label="Предыдущая неделя"
            onClick={() => {
              setWeek(datePlus(week, -7));
              setDay(datePlus(day, -7));
            }}
          >
            ‹
          </button>
          <span>
            {formatDate(days[0])} {days[0].slice(0, 4)} —{" "}
            {formatDate(days[days.length - 1])}{" "}
            {days[days.length - 1].slice(0, 4)}
          </span>
          <button
            aria-label="Следующая неделя"
            onClick={() => {
              setWeek(datePlus(week, 7));
              setDay(datePlus(day, 7));
            }}
          >
            ›
          </button>
          <button
            onClick={() => {
              setWeek(demoWeekStart);
              setDay("2026-10-02");
            }}
          >
            Сегодня DEMO
          </button>
          <div className="segmented">
            {["День", "Неделя"].map((value) => (
              <button
                className={view === value ? "active" : ""}
                key={value}
                onClick={() => setView(value)}
              >
                {value}
              </button>
            ))}
          </div>
          <select
            aria-label="Канал календаря"
            value={channelFilter}
            onChange={(event) => setChannelFilter(event.target.value)}
          >
            <option value="">Все каналы</option>
            {data.channels.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div className="calendar-zone">
          <Icon name="clock" size={15} />
          Europe/Minsk · UTC+3{" "}
          <span>{visibleJobs.length} публикации в DEMO-расписании</span>
        </div>
        <Panel className="calendar">
          <div className="calendar-scroller">
            <div
              className={`week-grid ${view === "День" ? "day-grid" : ""}`}
              style={{
                gridTemplateColumns: `48px repeat(${days.length}, minmax(${view === "День" ? "240px" : "86px"}, 1fr))`,
              }}
            >
              <div className="time-column">
                <header />
                <div
                  className="time-scale"
                  style={{
                    height: timelineHeight,
                    gridTemplateRows: `repeat(${endHour - startHour + 1}, 48px)`,
                  }}
                >
                  {Array.from(
                    { length: endHour - startHour + 1 },
                    (_, index) => (
                      <span key={index}>{index + startHour}:00</span>
                    ),
                  )}
                </div>
              </div>
              {days.map((date) => (
                <section className={date === day ? "today" : ""} key={date}>
                  <header>
                    <button onClick={() => setDay(date)}>
                      <b>
                        {new Date(`${date}T12:00:00Z`).toLocaleDateString(
                          "ru-RU",
                          { weekday: "short", timeZone: "UTC" },
                        )}
                      </b>
                      <small>{formatDate(date)}</small>
                    </button>
                  </header>
                  <div
                    className="day-timeline"
                    style={{ height: timelineHeight }}
                  >
                    {calendarSlots(
                      scheduled.filter((item) => item.date === date),
                    ).map((slot) => {
                      const job = slot.jobs[0];
                      const post = data.posts.find(
                        (item) => item.id === job.postId,
                      );
                      const channel = data.channels.find(
                        (item) => item.id === job.channelId,
                      );
                      if (!post || !channel) return null;
                      const top = Math.max(
                        0,
                        ((slot.minute - startHour * 60) / 60) * 48,
                      );
                      if (slot.jobs.length > 1)
                        return (
                          <button
                            className="calendar-event grouped-event"
                            key={job.id}
                            style={{ top }}
                            aria-label={`Открыть ${slot.jobs.length} публикации · ${date} · ${job.time}`}
                            onClick={() => setSlotJobs(slot.jobs)}
                          >
                            <span>
                              <Icon name="planner" />
                              {slot.jobs.length} публикации
                            </span>
                            <small>
                              {slot.jobs.map((entry) => entry.time).join(" · ")}
                            </small>
                            <b>Пересекающиеся карточки</b>
                            <span>Открыть список →</span>
                          </button>
                        );
                      return (
                        <button
                          className={`calendar-event tone-${channel.id}`}
                          key={job.id}
                          data-job={job.id}
                          style={{ top }}
                          onClick={() => {
                            setEditingJobId(job.id);
                            setScheduleId(post.id);
                          }}
                          title={`${post.title} · ${job.time} — изменить дату и время`}
                        >
                          <span>
                            <Icon name="channels" size={15} />
                            {channel.name}
                          </span>
                          <small>{job.time}</small>
                          <Artwork kind={post.art} />
                          <b>{post.title}</b>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          </div>
        </Panel>
      </div>
      <div className="planner-aside">
        <Panel>
          <PanelTitle title="Без расписания" icon="planner">
            <span className="count-badge">{unscheduled.length}</span>
          </PanelTitle>
          {unscheduled.map((item) => (
            <button
              className="unscheduled"
              key={item.id}
              onClick={() => {
                setEditingJobId(undefined);
                setScheduleId(item.id);
              }}
            >
              <Artwork kind={item.art} />
              <span>
                <b>{item.title}</b>
                <small>{item.source}</small>
                <em className="chip">Запланировать</em>
              </span>
            </button>
          ))}
          {!unscheduled.length && (
            <p className="help-copy">Все подходящие материалы запланированы.</p>
          )}
        </Panel>
        <Panel>
          <PanelTitle title="Загрузка недели" icon="chart" />
          <p className="help-copy">Количество записей в DEMO-расписании</p>
          <div className="week-bars">
            {busiest.map((item) => (
              <div key={item.date}>
                <b>{item.count}</b>
                <i style={{ height: `${item.count * 28}px` }} />
                <small>
                  {new Date(`${item.date}T12:00:00Z`).toLocaleDateString(
                    "ru-RU",
                    { weekday: "short", timeZone: "UTC" },
                  )}
                </small>
              </div>
            ))}
          </div>
          <div className="policy-note">
            <Icon name="clock" />
            <span>Окна и тихие часы проверяются при сохранении.</span>
          </div>
        </Panel>
      </div>
      {scheduleId && (
        <ScheduleDialog
          data={data}
          setData={setData}
          postId={scheduleId}
          existingJobId={editingJobId}
          onClose={() => setScheduleId(null)}
        />
      )}
      {slotJobs && (
        <Modal
          title="Публикации выбранного слота"
          onClose={() => setSlotJobs(null)}
        >
          <p>
            Все пересекающиеся записи доступны по отдельности. Часовой пояс:
            Europe/Minsk.
          </p>
          {slotJobs.map((job) => (
            <button
              className="slot-job full"
              key={job.id}
              onClick={() => {
                setEditingJobId(job.id);
                setScheduleId(job.postId);
                setSlotJobs(null);
              }}
            >
              <span>
                <b>
                  {data.posts.find((post) => post.id === job.postId)?.title}
                </b>
                <small>
                  {job.time} ·{" "}
                  {
                    data.channels.find(
                      (channel) => channel.id === job.channelId,
                    )?.name
                  }
                </small>
              </span>
              <Icon name="edit" />
            </button>
          ))}
        </Modal>
      )}
    </div>
  );
}

export function Accounts({ data }: WorkspaceProps) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("Все статусы");
  const [wizard, setWizard] = useState(false);
  const [step, setStep] = useState(1);
  return (
    <>
      <div className="metric-row">
        <Metric
          title="Активные сессии"
          value={
            data.accounts.filter((item) => item.state === "Активен").length
          }
          icon="accounts"
          tone="green"
        />
        <Metric
          title="Ожидают входа"
          value={
            data.accounts.filter((item) => item.state === "Ожидает входа")
              .length
          }
          icon="clock"
          tone="orange"
        />
        <Metric
          title="Требуют 2FA"
          value={
            data.accounts.filter((item) => item.state === "Требует 2FA").length
          }
          icon="shield"
          tone="violet"
        />
        <Metric
          title="Ошибки"
          value={data.accounts.filter((item) => item.state === "Ошибка").length}
          icon="close"
          tone="red"
        />
      </div>
      <div className="accounts-layout">
        <Panel>
          <div className="toolbar">
            <PanelTitle title="Подключённые аккаунты" icon="accounts" />
            <Search
              value={query}
              onChange={setQuery}
              placeholder="Поиск по аккаунтам"
            />
            <select
              aria-label="Статус аккаунта"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option>Все статусы</option>
              <option>Активен</option>
              <option>Ожидает входа</option>
              <option>Требует 2FA</option>
              <option>Ошибка</option>
            </select>
          </div>
          <div className="table-scroller">
            <table className="directory-table accounts-table">
              <thead>
                <tr>
                  <th>Аккаунт</th>
                  <th>Статус</th>
                  <th>Доноры / каналы</th>
                  <th>Последняя синхронизация</th>
                  <th>Действие</th>
                </tr>
              </thead>
              <tbody>
                {data.accounts
                  .filter(
                    (item) =>
                      item.name.toLowerCase().includes(query.toLowerCase()) &&
                      (filter === "Все статусы" || item.state === filter),
                  )
                  .map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div className="table-identity">
                          <span className={`account-avatar avatar-${item.id}`}>
                            {item.name[0]}
                          </span>
                          <span>
                            <b>{item.name}</b>
                            <small>{item.phone}</small>
                          </span>
                        </div>
                      </td>
                      <td>
                        <Status value={item.state} />
                      </td>
                      <td>
                        {item.donors} / {item.channels}
                      </td>
                      <td className="small-muted">{item.synced}</td>
                      <td>
                        <button
                          className="small-button"
                          onClick={() => {
                            setWizard(true);
                            setStep(1);
                          }}
                        >
                          {item.state === "Активен"
                            ? "Посмотреть"
                            : "Восстановить"}
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <div className="table-footer">
            Показано аккаунтов: {data.accounts.length}
            <span>Телефоны маскированы</span>
          </div>
        </Panel>
        <Panel className="connect-card">
          <div className="connect-heading">
            <Icon name="channels" size={36} />
            <div>
              <h2>Подключить новый аккаунт</h2>
              <p>Сценарий подключения через Telegram</p>
            </div>
          </div>
          <ol className="connect-steps">
            {[
              ["Номер телефона", "Укажите номер, к которому привязан аккаунт"],
              ["Код Telegram", "Подтвердите вход кодом из приложения"],
              ["2FA при необходимости", "Дополнительная проверка провайдера"],
              ["Сохранённая сессия", "Результат подтверждается сервером"],
            ].map(([title, text], index) => (
              <li key={title}>
                <b>{index + 1}</b>
                <div>
                  <strong>{title}</strong>
                  <p>{text}</p>
                </div>
              </li>
            ))}
          </ol>
          <button
            className="primary-button full"
            onClick={() => {
              setWizard(true);
              setStep(1);
            }}
          >
            <Icon name="plus" />
            Подключить аккаунт DEMO
          </button>
          <div className="policy-note">
            <Icon name="shield" />
            <span>
              В DEMO не вводите телефон, код или пароль. Реальная авторизация
              ожидает live provider.
            </span>
          </div>
        </Panel>
      </div>
      {wizard && (
        <Modal
          title="Подключение Telegram в DEMO"
          onClose={() => setWizard(false)}
        >
          <div className="wizard-progress">
            {[1, 2, 3, 4].map((value) => (
              <span className={value <= step ? "active" : ""} key={value}>
                {value}
              </span>
            ))}
          </div>
          <h3>
            {
              [
                "Номер телефона",
                "Код Telegram",
                "2FA при необходимости",
                "Проверка результата",
              ][step - 1]
            }
          </h3>
          <p>
            {step === 4
              ? "Просмотр сценария завершён. Аккаунт не подключён, Telegram-сессия не создана."
              : "Это безопасный просмотр шага без ввода личных данных. Код и запросы к Telegram не отправляются."}
          </p>
          <div className="wizard-placeholder">
            <Icon name={step === 3 ? "shield" : "accounts"} size={34} />
            <span>
              {
                [
                  "+7 ••• ••• •• ••",
                  "• • • • •",
                  "Пароль не запрашивается",
                  "Live provider не подключён",
                ][step - 1]
              }
            </span>
          </div>
          <div className="action-row">
            {step > 1 && (
              <button onClick={() => setStep((prior) => prior - 1)}>
                Назад
              </button>
            )}
            {step < 4 ? (
              <button
                className="primary-button"
                onClick={() => setStep((prior) => prior + 1)}
              >
                Следующий шаг DEMO
              </button>
            ) : (
              <button
                className="primary-button"
                onClick={() => setWizard(false)}
              >
                Закрыть
              </button>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}

type SettingsValues = {
  language: string;
  timezone: string;
  hints: boolean;
  strictness: string;
  dedup: boolean;
  stopWords: string;
  mode: string;
  notifications: boolean;
  errors: boolean;
  style: string;
  length: string;
  audit: boolean;
  daily: number;
};
const initialSettings: SettingsValues = {
  language: "ru",
  timezone: "Europe/Minsk",
  hints: true,
  strictness: "Стандартная",
  dedup: true,
  stopWords: "Реклама, криптовалюта",
  mode: "Ручной",
  notifications: true,
  errors: true,
  style: "Нейтральный",
  length: "Без изменений",
  audit: true,
  daily: 30,
};
const settingSections = [
  { label: "Общие", icon: "settings", detail: "Рабочее пространство" },
  { label: "Модерация", icon: "shield", detail: "Правила и фильтры" },
  { label: "Публикация", icon: "channels", detail: "Каналы и расписание" },
  { label: "Уведомления", icon: "bell", detail: "Способы оповещений" },
  {
    label: "AI и перефразирование",
    icon: "spark",
    detail: "Настройки нейросети",
  },
  { label: "Безопасность", icon: "shield", detail: "Лимиты и ограничения" },
];
export function Settings({ markDirty }: WorkspaceProps) {
  const [section, setSection] = useState("Общие");
  const [draft, setDraft] = useState(initialSettings);
  const [saved, setSaved] = useState(initialSettings);
  const [notice, setNotice] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  useEffect(() => markDirty("settings", dirty), [dirty, markDirty]);
  const change = <K extends keyof SettingsValues>(
    key: K,
    value: SettingsValues[K],
  ) => {
    setDraft((prior) => ({ ...prior, [key]: value }));
    setNotice("");
  };
  return (
    <div className="settings-layout">
      <Panel className="settings-nav">
        {settingSections.map((item) => (
          <button
            key={item.label}
            aria-label={item.label}
            className={`settings-tab ${section === item.label ? "active" : ""}`}
            onClick={() => setSection(item.label)}
          >
            <Icon name={item.icon} size={25} />
            <span>
              <b>{item.label}</b>
              <small>{item.detail}</small>
            </span>
          </button>
        ))}
      </Panel>
      <div className="settings-content">
        <Panel className="settings-form">
          <PanelTitle
            title={`${section}: настройки`}
            icon={settingSections.find((item) => item.label === section)!.icon}
          />
          <p className="description">
            {settingSections.find((item) => item.label === section)!.detail}.
            Изменения применяются после явного сохранения.
          </p>
          {section === "Общие" && (
            <>
              <div className="settings-subsection">
                <h3>Интерфейс</h3>
                <label className="setting-field">
                  <span>
                    <b>Тема интерфейса</b>
                    <small>Выбранное оформление Content Studio</small>
                  </span>
                  <span className="fixed-setting">
                    <Icon name="moon" size={18} />
                    Тёмно-синяя
                  </span>
                </label>
                <label className="setting-field">
                  <span>
                    <b>Язык интерфейса</b>
                    <small>Язык рабочего пространства</small>
                  </span>
                  <select
                    aria-label="Язык интерфейса"
                    value={draft.language}
                    onChange={(event) => change("language", event.target.value)}
                  >
                    <option value="ru">Русский</option>
                    <option value="en">English · DEMO</option>
                  </select>
                </label>
                <label className="setting-field">
                  <span>
                    <b>Часовой пояс</b>
                    <small>Для планирования и календаря</small>
                  </span>
                  <select
                    aria-label="Часовой пояс"
                    value={draft.timezone}
                    onChange={(event) => change("timezone", event.target.value)}
                  >
                    <option>Europe/Minsk</option>
                  </select>
                </label>
                <p className="help-copy">
                  Перевод интерфейса ожидает интеграции; выбор языка сохраняется
                  только как настройка DEMO.
                </p>
              </div>
              <div className="settings-subsection">
                <h3>Подсказки</h3>
                <Toggle
                  label="Показывать советы и подсказки"
                  checked={draft.hints}
                  onChange={(value) => change("hints", value)}
                />
                <p className="help-copy">
                  Краткие пояснения помогают ориентироваться в ручной модерации.
                </p>
              </div>
            </>
          )}
          {section === "Модерация" && (
            <>
              <div className="settings-subsection">
                <label className="setting-field">
                  <span>
                    <b>Строгость проверки</b>
                    <small>Дополнительные правила поверх hard gate</small>
                  </span>
                  <select
                    aria-label="Строгость проверки"
                    value={draft.strictness}
                    onChange={(event) =>
                      change("strictness", event.target.value)
                    }
                  >
                    <option>Стандартная</option>
                    <option>Строгая</option>
                  </select>
                </label>
                <Toggle
                  label="Проверять точные дубли"
                  checked={draft.dedup}
                  onChange={(value) => change("dedup", value)}
                />
                <label className="field">
                  Стоп-слова
                  <textarea
                    value={draft.stopWords}
                    onChange={(event) =>
                      change("stopWords", event.target.value)
                    }
                  />
                </label>
              </div>
              <div className="policy-note">
                <Icon name="shield" />
                <span>
                  EditorialGate нельзя отключить. Отклонённый материал не
                  передаётся на рерайт.
                </span>
              </div>
            </>
          )}
          {section === "Публикация" && (
            <>
              <label className="setting-field">
                <span>
                  <b>Режим по умолчанию</b>
                  <small>Для новых каналов</small>
                </span>
                <select
                  aria-label="Режим по умолчанию"
                  value={draft.mode}
                  onChange={(event) => change("mode", event.target.value)}
                >
                  <option>Ручной</option>
                  <option>С проверкой</option>
                </select>
              </label>
              <div className="policy-note">
                <Icon name="channels" />
                <span>
                  Одобрение и публикация — разные операции. Автоматическая
                  публикация не включается интерфейсом.
                </span>
              </div>
            </>
          )}
          {section === "Уведомления" && (
            <>
              <Toggle
                label="Новые материалы во входящих"
                checked={draft.notifications}
                onChange={(value) => change("notifications", value)}
              />
              <Toggle
                label="Ошибки и сбои"
                checked={draft.errors}
                onChange={(value) => change("errors", value)}
              />
              <p className="help-copy">
                Настройки DEMO. Доставка уведомлений ожидает рабочий API.
              </p>
            </>
          )}
          {section === "AI и перефразирование" && (
            <>
              <label className="setting-field">
                <span>
                  <b>Стиль перефразирования</b>
                  <small>Сохранять смысл и факты</small>
                </span>
                <select
                  aria-label="Стиль перефразирования"
                  value={draft.style}
                  onChange={(event) => change("style", event.target.value)}
                >
                  <option>Нейтральный</option>
                  <option>Краткий</option>
                </select>
              </label>
              <label className="setting-field">
                <span>
                  <b>Длина текста</b>
                  <small>Предпочтительный объём</small>
                </span>
                <select
                  aria-label="Длина текста"
                  value={draft.length}
                  onChange={(event) => change("length", event.target.value)}
                >
                  <option>Без изменений</option>
                  <option>Кратко</option>
                </select>
              </label>
              <div className="policy-note">
                <Icon name="spark" />
                <span>
                  DEMO не выполняет платные AI-вызовы. Факты и ограничения
                  EditorialGate сохраняются.
                </span>
              </div>
            </>
          )}
          {section === "Безопасность" && (
            <>
              <label className="setting-field">
                <span>
                  <b>Дневной лимит публикаций</b>
                  <small>Настройка DEMO</small>
                </span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  aria-label="Дневной лимит публикаций"
                  value={draft.daily}
                  onChange={(event) =>
                    change("daily", Number(event.target.value))
                  }
                />
              </label>
              <Toggle
                label="Сохранять историю действий"
                checked={draft.audit}
                onChange={(value) => change("audit", value)}
              />
              <p className="help-copy">
                Ключи шифрования и Telegram-сессии управляются сервером. Секреты
                не вводятся в DEMO.
              </p>
            </>
          )}
          <DraftActions
            dirty={dirty}
            onCancel={() => {
              setDraft(saved);
              setNotice("");
            }}
            onSave={() => {
              if (draft.daily < 1 || draft.daily > 100) {
                setNotice("Дневной лимит должен быть от 1 до 100.");
                return;
              }
              setSaved(draft);
              setNotice("Изменения сохранены только в DEMO.");
            }}
          />
          {notice && <Notice>{notice}</Notice>}
        </Panel>
        <Panel className="settings-help">
          <PanelTitle title="О настройках" icon="shield" />
          <p>
            Ручные настройки сохраняются только по кнопке «Сохранить». Переход
            между разделами не стирает черновики.
          </p>
          <p>
            DEMO хранит данные в памяти текущего окна. После перезагрузки
            страницы демонстрационный набор восстанавливается.
          </p>
        </Panel>
      </div>
    </div>
  );
}
