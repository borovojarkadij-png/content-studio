import { useEffect, useRef, useState } from "react";
import type { WorkspaceProps } from "./App";
import {
  loadOutputChannels,
  loadPublicationPlans,
  loadRewriteDrafts,
  loadPlannedPublications,
  savePublicationPlan,
  reviewRewriteDraft,
  planPublications,
  type OutputChannel,
  type PublicationPlan,
  type RewriteDraft,
  type PlannedPublication,
} from "./plannerApi";
import { Notice, Panel, PanelTitle } from "./ui";
import { RewriteStylePanel } from "./rewriteStyle";

const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "Ошибка запроса API";
const formatSlots = (minutes: number[]) =>
  minutes
    .map(
      (minute) =>
        `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`,
    )
    .join(", ");

export function LivePlanner({ markDirty }: Pick<WorkspaceProps, "markDirty">) {
  const [channels, setChannels] = useState<OutputChannel[]>([]);
  const [plans, setPlans] = useState<PublicationPlan[]>([]);
  const [channelId, setChannelId] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void Promise.all([
      loadOutputChannels(controller.signal),
      loadPublicationPlans(controller.signal),
    ])
      .then(([outputs, policies]) => {
        if (controller.signal.aborted) return;
        setChannels(outputs);
        setPlans(policies);
        setChannelId(outputs[0]?.id ?? 0);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setError(errorText(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reload]);
  useEffect(() => {
    markDirty("planner", dirty);
    return () => markDirty("planner", false);
  }, [dirty, markDirty]);
  return (
    <div className="live-planner">
      <Panel>
        <PanelTitle title="Планы каналов" icon="planner" />
        <p className="help-copy">
          Данные из API. Подбор только резервирует слоты — отправка в Telegram
          не подключена.
        </p>
        {loading && <p role="status">Загрузка планировщика…</p>}
        {error && (
          <>
            <Notice>{error}</Notice>
            <button onClick={() => setReload((value) => value + 1)}>
              Повторить загрузку планировщика
            </button>
          </>
        )}
        {!loading &&
          !error &&
          (channels.length ? (
            <label className="field">
              Канал плана
              <select
                value={channelId}
                disabled={busy || dirty}
                onChange={(event) => setChannelId(Number(event.target.value))}
              >
                {channels.map((channel) => (
                  <option value={channel.id} key={channel.id}>
                    {channel.title}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p>
              Выходные каналы ещё не настроены. Добавьте канал через API
              конфигурации.
            </p>
          ))}
        {dirty && (
          <p className="help-copy">
            Сохраните или отмените правки перед сменой канала.
          </p>
        )}
      </Panel>
      {!loading && !error && channelId > 0 && (
        <ChannelPlanner
          key={channelId}
          channelId={channelId}
          initialPlan={plans.find(
            (plan) => plan.output_channel_id === channelId,
          )}
          onDirty={setDirty}
          onBusy={setBusy}
          onSaved={(plan) =>
            setPlans((prior) => [
              ...prior.filter(
                (item) => item.output_channel_id !== plan.output_channel_id,
              ),
              plan,
            ])
          }
        />
      )}
    </div>
  );
}

function ChannelPlanner({
  channelId,
  initialPlan,
  onDirty,
  onBusy,
  onSaved,
}: {
  channelId: number;
  initialPlan?: PublicationPlan;
  onDirty: (dirty: boolean) => void;
  onBusy: (busy: boolean) => void;
  onSaved: (plan: PublicationPlan) => void;
}) {
  const [saved, setSaved] = useState(initialPlan);
  const [mode, setMode] = useState<PublicationPlan["mode"]>(
    initialPlan?.mode ?? "MANUAL",
  );
  const [limit, setLimit] = useState(String(initialPlan?.daily_limit ?? 1));
  const [zone, setZone] = useState(initialPlan?.timezone ?? "Europe/Minsk");
  const [slots, setSlots] = useState(
    formatSlots(initialPlan?.slot_minutes ?? [540]),
  );
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [drafts, setDrafts] = useState<RewriteDraft[]>([]);
  const [publications, setPublications] = useState<PlannedPublication[]>([]);
  const [readError, setReadError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const mutations = useRef(new AbortController());
  const planId = saved?.id;
  const dirty =
    mode !== (saved?.mode ?? "MANUAL") ||
    limit !== String(saved?.daily_limit ?? 1) ||
    zone !== (saved?.timezone ?? "Europe/Minsk") ||
    slots !== formatSlots(saved?.slot_minutes ?? [540]);
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  useEffect(() => {
    onBusy(busy);
  }, [busy, onBusy]);
  useEffect(() => {
    const controller = new AbortController();
    mutations.current = controller;
    return () => {
      controller.abort();
      onDirty(false);
      onBusy(false);
    };
  }, [onDirty, onBusy]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setReadError("");
    setDrafts([]);
    setPublications([]);
    void Promise.allSettled([
      loadRewriteDrafts(channelId, controller.signal),
      planId && day
        ? loadPlannedPublications(planId, day, controller.signal)
        : Promise.resolve([]),
    ]).then(([reviews, schedule]) => {
      if (controller.signal.aborted) return;
      if (reviews.status === "fulfilled") setDrafts(reviews.value);
      if (schedule.status === "fulfilled") setPublications(schedule.value);
      const failed = [reviews, schedule].find(
        (result) => result.status === "rejected",
      );
      if (failed?.status === "rejected") setReadError(errorText(failed.reason));
      setLoading(false);
    });
    return () => controller.abort();
  }, [channelId, planId, day, refresh]);
  const mutate = async (
    action: (signal: AbortSignal) => Promise<void>,
    message: string,
  ) => {
    if (busy || mutations.current.signal.aborted) return;
    setBusy(true);
    setError("");
    setNotice("");
    const signal = mutations.current.signal;
    try {
      await action(signal);
      if (!signal.aborted) {
        setNotice(message);
        setRefresh((value) => value + 1);
      }
    } catch (error) {
      if (!signal.aborted) setError(errorText(error));
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  };
  const save = () =>
    mutate(async (signal) => {
      const parts = slots.split(",").map((part) => part.trim());
      if (parts.some((part) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(part)))
        throw new Error("Введите слоты в формате ЧЧ:ММ через запятую.");
      const minutes = parts.map(
        (part) => Number(part.slice(0, 2)) * 60 + Number(part.slice(3)),
      );
      const savedPlan = await savePublicationPlan(
        channelId,
        {
          mode,
          daily_limit: Number(limit),
          timezone: zone.trim(),
          slot_minutes: minutes,
        },
        signal,
      );
      if (!signal.aborted) {
        setSaved(savedPlan);
        onSaved(savedPlan);
        setMode(savedPlan.mode);
        setLimit(String(savedPlan.daily_limit));
        setZone(savedPlan.timezone);
        setSlots(formatSlots(savedPlan.slot_minutes));
      }
    }, "План сохранён в базе данных.");
  const cancel = () => {
    setMode(saved?.mode ?? "MANUAL");
    setLimit(String(saved?.daily_limit ?? 1));
    setZone(saved?.timezone ?? "Europe/Minsk");
    setSlots(formatSlots(saved?.slot_minutes ?? [540]));
    setError("");
    setNotice("");
  };
  return (
    <>
      <RewriteStylePanel key={channelId} channelId={channelId} />
      <Panel>
        <PanelTitle title="Правила подбора" icon="settings" />
        <fieldset disabled={busy} className="live-planner-fields">
          <div className="form-grid">
            <label className="field">
              Режим планирования
              <select
                value={mode}
                onChange={(event) =>
                  setMode(event.target.value as PublicationPlan["mode"])
                }
              >
                <option value="MANUAL">
                  Ручной — без автоматического подбора
                </option>
                <option value="AUTOMATIC">Автоматический подбор</option>
              </select>
            </label>
            <label className="field">
              Постов в день
              <input
                type="number"
                min="1"
                max="24"
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
              />
            </label>
            <label className="field">
              Часовой пояс
              <input
                value={zone}
                onChange={(event) => setZone(event.target.value)}
              />
            </label>
            <label className="field">
              Слоты публикаций
              <input
                value={slots}
                onChange={(event) => setSlots(event.target.value)}
                placeholder="09:00, 15:00"
              />
            </label>
          </div>
        </fieldset>
        <p className="help-copy">
          Слоты заданы в часовом поясе канала. Отбираются одобренные варианты по
          приоритету, с учётом задержки связи и дневного лимита.
        </p>
        <div className="action-row">
          <button
            className="primary"
            disabled={busy}
            onClick={() => void save()}
          >
            Сохранить план
          </button>
          <button disabled={busy || !dirty} onClick={cancel}>
            Отменить правки плана
          </button>
        </div>
        {error && <Notice>{error}</Notice>}
        {notice && <Notice>{notice}</Notice>}
      </Panel>
      <Panel>
        <PanelTitle title="Слоты выбранного дня" icon="planner" />
        <div className="action-row">
          <label className="field">
            Дата плана
            <input
              type="date"
              value={day}
              disabled={busy}
              onChange={(event) => setDay(event.target.value)}
            />
          </label>
          <button
            disabled={
              busy ||
              loading ||
              !!readError ||
              dirty ||
              !planId ||
              !day ||
              saved?.mode !== "AUTOMATIC"
            }
            onClick={() =>
              void mutate(
                (signal) => planPublications(planId!, day, signal),
                "Подбор завершён. Публикация не выполнена.",
              )
            }
          >
            Подобрать публикации на день
          </button>
          <button
            disabled={busy || loading}
            onClick={() => setRefresh((value) => value + 1)}
          >
            Обновить очередь
          </button>
        </div>
        {!planId && <p>Сначала сохраните план канала.</p>}
        {readError && <Notice>{readError}</Notice>}
        {loading ? (
          <p role="status">Загрузка очереди…</p>
        ) : publications.length ? (
          <ul className="live-slot-list">
            {publications.map((item) => (
              <li key={item.id}>
                <b>Слот #{item.id}</b>
                <time dateTime={item.scheduled_for}>
                  {new Date(item.scheduled_for).toLocaleString("ru-RU", {
                    timeZone: saved?.timezone,
                  })}
                </time>
                <span>{item.content_key}</span>
                <span>
                  {item.editorial_allowed
                    ? item.state
                    : "Заблокирован EditorialGate"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          !readError && (
            <p>
              На выбранный день нет резервов. Это не означает, что публикация
              выполнена.
            </p>
          )
        )}
      </Panel>
      <Panel>
        <PanelTitle title="Рерайты на проверке" icon="shield" />
        <p className="help-copy">
          Варианты независимы для каждого канала. Одобрение разрешает
          планирование, но не отправляет пост.
        </p>
        {!loading && !drafts.length && (
          <p>
            Сохранённых вариантов пока нет. Рабочий rewrite-worker ещё не
            подключён.
          </p>
        )}
        <div className="live-review-list">
          {drafts.map((draft) => (
            <article key={draft.id}>
              <b>
                Вариант #{draft.id} · {draft.approval_state}
              </b>
              <small>
                {draft.content_key} · EditorialGate:{" "}
                {draft.editorial_status ?? "нет решения"}
              </small>
              <p className="live-rewrite-text">{draft.rewritten_text}</p>
              <div className="action-row">
                <button
                  aria-label={`Одобрить рерайт ${draft.id}`}
                  disabled={
                    busy ||
                    !draft.approve_allowed ||
                    draft.approval_state !== "PENDING" ||
                    draft.editorial_status !== "PASS"
                  }
                  onClick={() =>
                    void mutate(
                      (signal) => reviewRewriteDraft(draft.id, true, signal),
                      "Рерайт одобрен. Публикация не выполнена.",
                    )
                  }
                >
                  Одобрить
                </button>
                <button
                  aria-label={`Отклонить рерайт ${draft.id}`}
                  disabled={busy || draft.approval_state !== "PENDING"}
                  onClick={() =>
                    void mutate(
                      (signal) => reviewRewriteDraft(draft.id, false, signal),
                      "Рерайт отклонён. Планирование запрещено.",
                    )
                  }
                >
                  Отклонить
                </button>
              </div>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}
