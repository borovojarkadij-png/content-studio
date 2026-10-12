import { useEffect, useRef, useState } from "react";
import {
  EditorialPolicyApiError,
  readEditorialPolicy,
  writeEditorialPolicy,
  type EditorialPolicy,
  type EditorialPolicyChange,
} from "./editorialPolicyApi";

type Draft = Omit<EditorialPolicyChange, "expected_etag">;
const draftOf = (policy: EditorialPolicy): Draft => ({
  enabled: policy.enabled,
  provider: policy.provider ?? "OPENAI",
  model: policy.model ?? "",
  protected_entities: policy.protected_entities.map((e) => ({
    ...e,
    aliases: [...e.aliases],
  })),
});

export function EditorialPolicySettings({
  onDirtyChange,
}: {
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [token, setToken] = useState("");
  const [saved, setSaved] = useState<EditorialPolicy | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [phase, setPhase] = useState<"GET" | "PUT" | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(false);
  const [discard, setDiscard] = useState<"reload" | "disconnect" | null>(null);
  const request = useRef({
    generation: 0,
    controller: null as AbortController | null,
    inFlight: false,
  });
  const dirty =
    !!draft &&
    !!saved &&
    JSON.stringify(draft) !== JSON.stringify(draftOf(saved));
  useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);
  useEffect(
    () => () => {
      request.current.generation++;
      request.current.controller?.abort();
      request.current.inFlight = false;
    },
    [],
  );

  const invalidate = () => {
    request.current.generation++;
    request.current.controller?.abort();
    request.current.controller = null;
    request.current.inFlight = false;
    setPhase(null);
    setAuthorized(false);
  };
  const disconnect = () => {
    invalidate();
    setToken("");
    setSaved(null);
    setDraft(null);
    setBlocked(false);
    setDiscard(null);
    setError(false);
    setNotice("Оператор отключён.");
  };
  const run = async (method: "GET" | "PUT") => {
    if (
      request.current.inFlight ||
      (method === "PUT" && (!authorized || blocked || !draft || !saved))
    )
      return;
    const submitted =
      method === "PUT" && draft && saved
        ? { ...draft, expected_etag: saved.etag }
        : null;
    request.current.controller?.abort();
    const generation = ++request.current.generation;
    const controller = new AbortController();
    request.current.controller = controller;
    request.current.inFlight = true;
    setDiscard(null);
    setPhase(method);
    setNotice("");
    setError(false);
    if (method === "GET") setAuthorized(false);
    try {
      const value = submitted
        ? await writeEditorialPolicy(token, submitted, controller.signal)
        : await readEditorialPolicy(token, controller.signal);
      if (generation !== request.current.generation) return;
      setSaved(value);
      setDraft(draftOf(value));
      setAuthorized(true);
      setBlocked(false);
      setNotice(
        method === "PUT"
          ? "Редакционная политика сохранена; настроена только диагностика."
          : value.configured
            ? "Редакционная политика загружена."
            : "Редакционная политика ещё не настроена. Можно создать конфигурацию диагностики.",
      );
    } catch (cause) {
      if (generation !== request.current.generation) return;
      const status =
        cause instanceof EditorialPolicyApiError ? cause.status : 0;
      const ambiguous =
        method === "PUT" &&
        status === 0 &&
        !(cause instanceof EditorialPolicyApiError && cause.local);
      if (status === 401) setAuthorized(false);
      if (status === 409 || ambiguous) setBlocked(true);
      setError(true);
      setNotice(
        ambiguous
          ? "Сохранение не подтверждено; черновик сохранён. Явно загрузите политику заново для проверки текущего состояния."
          : cause instanceof EditorialPolicyApiError
            ? cause.message
            : "Запрос редакционной политики не подтверждён; загрузите заново.",
      );
    } finally {
      if (generation === request.current.generation) {
        request.current.inFlight = false;
        request.current.controller = null;
        setPhase(null);
      }
    }
  };
  const reload = () => {
    if (request.current.inFlight) return;
    if (dirty) setDiscard("reload");
    else void run("GET");
  };
  const edit = (change: Partial<Draft>) => {
    setDraft((prior) => (prior ? { ...prior, ...change } : prior));
  };
  const editEntity = (
    index: number,
    change: Partial<Draft["protected_entities"][number]>,
  ) => {
    setDraft((prior) =>
      prior
        ? {
            ...prior,
            protected_entities: prior.protected_entities.map((e, i) =>
              i === index ? { ...e, ...change } : e,
            ),
          }
        : prior,
    );
  };
  return (
    <section aria-label="Редакционная политика" className="settings-subsection">
      <h3>Редакционная политика</h3>
      <p className="help-copy">
        Отдельный токен оператора хранится только в памяти до отключения или
        смены режима. Загрузка выполняется по кнопке.
      </p>
      <label className="setting-field">
        <span>
          <b>Токен оператора</b>
          <small>Отдельно выданный токен</small>
        </span>
        <input
          aria-label="Токен оператора"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={token}
          onChange={(event) => {
            const writing = phase === "PUT";
            invalidate();
            setToken(event.target.value);
            setDiscard(null);
            setError(writing);
            setNotice(
              writing
                ? "Сохранение не подтверждено; токен изменён, черновик сохранён. Загрузите политику заново."
                : "Токен изменён; загрузите редакционную политику для подтверждения доступа.",
            );
            if (writing) setBlocked(true);
          }}
        />
      </label>
      <div className="action-row">
        <button disabled={!!phase} onClick={reload}>
          Загрузить редакционную политику
        </button>
        <button
          onClick={() => (dirty ? setDiscard("disconnect") : disconnect())}
        >
          Отключить редакционную политику
        </button>
      </div>
      {discard && (
        <div
          role="group"
          aria-label="Отбросить черновик редакционной политики?"
          className="policy-note"
        >
          <span>Отбросить черновик редакционной политики?</span>
          <button onClick={() => setDiscard(null)}>Сохранить черновик</button>
          <button
            className="danger-button"
            onClick={() =>
              discard === "disconnect" ? disconnect() : void run("GET")
            }
          >
            Отбросить черновик
          </button>
        </div>
      )}
      {phase && (
        <p role="status">
          {phase === "PUT"
            ? "Сохранение редакционной политики… Редактирование временно недоступно."
            : "Загрузка редакционной политики…"}
        </p>
      )}
      {notice && <p role={error ? "alert" : "status"}>{notice}</p>}
      <p className="policy-note">
        Только диагностика. Реальная модель не квалифицирована; выполнение,
        рерайт и публикация не разрешены. EditorialGate сохраняет обязательные
        ограничения.
      </p>
      {saved && draft && (
        <>
          <p>
            Конфигурация: {saved.configured ? "настроена" : "отсутствует"}.{" "}
            {dirty
              ? "Есть несохранённый черновик."
              : "Черновик соответствует загруженному состоянию."}
          </p>
          <label className="setting-field">
            <span>
              <b>Версия политики</b>
            </span>
            <input
              aria-label="Версия политики"
              readOnly
              value={saved.policy_version ?? "Не задана"}
            />
          </label>
          <label className="setting-field">
            <span>
              <b>ETag политики</b>
            </span>
            <input
              aria-label="ETag политики"
              readOnly
              value={saved.etag ?? "Нет (создание)"}
            />
          </label>
          <fieldset className="live-planner-fields" disabled={!!phase}>
            <legend>Диагностическая конфигурация</legend>
            <label className="setting-field">
              <span>
                <b>Включить диагностику</b>
              </span>
              <input
                aria-label="Включить диагностику"
                type="checkbox"
                checked={draft.enabled}
                onChange={(e) => edit({ enabled: e.target.checked })}
              />
            </label>
            <label className="setting-field">
              <span>
                <b>Поставщик диагностики</b>
              </span>
              <select
                aria-label="Поставщик диагностики"
                value={draft.provider}
                onChange={(e) =>
                  edit({ provider: e.target.value as Draft["provider"] })
                }
              >
                <option value="OPENAI">OpenAI</option>
                <option value="OPENROUTER">OpenRouter</option>
              </select>
            </label>
            <label className="setting-field">
              <span>
                <b>Модель диагностики</b>
                <small>
                  Закреплённый идентификатор; OpenRouter требует :free без
                  динамического маршрутизатора. Каталог не загружается.
                </small>
              </span>
              <input
                aria-label="Модель диагностики"
                value={draft.model}
                onChange={(e) => edit({ model: e.target.value })}
              />
            </label>
            <p className="help-copy">
              До 64 сущностей, от 1 до 16 псевдонимов каждой. Значения
              передаются точно, включая пробелы и переводы строк;
              неоднозначность проверяет сервер.
            </p>
            {draft.protected_entities.map((entity, index) => (
              <div className="settings-subsection" key={index}>
                <label className="field">
                  ID сущности {index + 1}
                  <textarea
                    aria-label={`ID сущности ${index + 1}`}
                    value={entity.entity_id}
                    onChange={(e) =>
                      editEntity(index, { entity_id: e.target.value })
                    }
                  />
                </label>
                {entity.aliases.map((alias, aliasIndex) => (
                  <div key={aliasIndex}>
                    <label className="field">
                      Псевдоним {aliasIndex + 1} сущности {index + 1}
                      <textarea
                        aria-label={`Псевдоним ${aliasIndex + 1} сущности ${index + 1}`}
                        value={alias}
                        onChange={(e) =>
                          editEntity(index, {
                            aliases: entity.aliases.map((v, i) =>
                              i === aliasIndex ? e.target.value : v,
                            ),
                          })
                        }
                      />
                    </label>
                    <button
                      disabled={entity.aliases.length <= 1}
                      onClick={() =>
                        editEntity(index, {
                          aliases: entity.aliases.filter(
                            (_, i) => i !== aliasIndex,
                          ),
                        })
                      }
                    >
                      Удалить псевдоним {aliasIndex + 1} сущности {index + 1}
                    </button>
                  </div>
                ))}
                <button
                  disabled={entity.aliases.length >= 16}
                  onClick={() =>
                    editEntity(index, { aliases: [...entity.aliases, ""] })
                  }
                >
                  Добавить псевдоним сущности {index + 1}
                </button>
                <button
                  onClick={() =>
                    edit({
                      protected_entities: draft.protected_entities.filter(
                        (_, i) => i !== index,
                      ),
                    })
                  }
                >
                  Удалить сущность {index + 1}
                </button>
              </div>
            ))}
            <button
              disabled={draft.protected_entities.length >= 64}
              onClick={() =>
                edit({
                  protected_entities: [
                    ...draft.protected_entities,
                    { entity_id: "", aliases: [""] },
                  ],
                })
              }
            >
              Добавить защищённую сущность
            </button>
          </fieldset>
          <button
            className="primary-button"
            disabled={!!phase || !authorized || blocked || !!discard}
            onClick={() => void run("PUT")}
          >
            Сохранить редакционную политику
          </button>
          {(!authorized || blocked) && (
            <p className="help-copy">
              Сохранение недоступно до явной загрузки актуальной политики и
              подтверждения доступа.
            </p>
          )}
        </>
      )}
    </section>
  );
}
