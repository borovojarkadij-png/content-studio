import { useEffect, useRef, useState } from "react";
import type { WorkspaceProps } from "./App";
import { Icon, Notice, Panel, PanelTitle } from "./ui";
import {
  bulkImportDonors,
  createConfiguration,
  loadConfiguration,
  mappingFilters,
  renameConfiguration,
  saveMapping,
  sourceMediaRights,
  type AccountConfig,
  type ChannelConfig,
  type FilterConfig,
  type ImportConfig,
  type MappingConfig,
  type MappingPolicy,
  type SourceRightsConfig,
  type SourceRightsPolicy,
} from "./configurationApi";

type Props = Pick<WorkspaceProps, "markDirty">;
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "Ошибка запроса API";
const equal = (left: unknown, right: unknown) =>
  JSON.stringify(left) === JSON.stringify(right);
const policy = ({
  intake_percent,
  target_mix_percent,
  eligibility_mode,
  delay_minutes,
  priority,
  media_policy,
}: MappingConfig): MappingPolicy => ({
  intake_percent,
  target_mix_percent,
  eligibility_mode,
  delay_minutes,
  priority,
  media_policy,
});
const defaultPolicy: MappingPolicy = {
  intake_percent: 100,
  target_mix_percent: 100,
  eligibility_mode: "IMMEDIATE",
  delay_minutes: 0,
  priority: 0,
  media_policy: "REUSE_SOURCE",
};

/** Abort on unmount; stale reads/writes never update a remounted workspace. */
function useLifetime() {
  const lifetime = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    return () => controller.abort();
  }, []);
  return lifetime;
}

export function LiveDirectory({
  section,
  markDirty,
}: Props & { section: "accounts" | "donors" | "channels" }) {
  const path = section === "channels" ? "output-channels" : section;
  const lifetime = useLifetime();
  const [rows, setRows] = useState<(AccountConfig | ChannelConfig)[]>([]);
  const [accounts, setAccounts] = useState<AccountConfig[]>([]);
  const [imports, setImports] = useState<ImportConfig[]>([]);
  const [selectedId, setSelectedId] = useState(0);
  const [title, setTitle] = useState("");
  const [accountId, setAccountId] = useState(0);
  const [raw, setRaw] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [createDirty, setCreateDirty] = useState(false);
  const selected = rows.find((item) => item.id === selectedId);
  const selectedTitle = selected
    ? "name" in selected
      ? selected.name
      : selected.title
    : "";
  const dirty = title !== selectedTitle || Boolean(raw) || createDirty;
  useEffect(() => {
    markDirty(section, dirty);
    return () => markDirty(section, false);
  }, [section, dirty, markDirty]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void Promise.all([
      loadConfiguration(path, controller.signal),
      section !== "accounts"
        ? loadConfiguration("accounts", controller.signal)
        : Promise.resolve([]),
      section === "donors"
        ? loadConfiguration("donor-imports", controller.signal)
        : Promise.resolve([]),
    ])
      .then(([items, available, queued]) => {
        if (controller.signal.aborted) return;
        setRows(items);
        setAccounts(available);
        setImports(queued);
        setAccountId(available[0]?.id ?? 0);
        setSelectedId(items[0]?.id ?? 0);
        setTitle(
          items[0] ? ("name" in items[0] ? items[0].name : items[0].title) : "",
        );
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setError(errorText(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, section, reload]);
  const saveTitle = async () => {
    if (!selected || !lifetime.current || busy) return;
    const controller = lifetime.current;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const saved = await renameConfiguration(
        path,
        selected.id,
        title.trim(),
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setRows((prior) =>
        prior.map((item) => (item.id === saved.id ? saved : item)),
      );
      setTitle("name" in saved ? saved.name : saved.title);
      setNotice("Название сохранено в базе данных.");
    } catch (error) {
      if (!controller.signal.aborted)
        setError(`Не удалось сохранить название. ${errorText(error)}`);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const importDonors = async () => {
    if (!accountId || !raw.trim() || !lifetime.current || busy) return;
    const controller = lifetime.current;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const report = await bulkImportDonors(accountId, raw, controller.signal);
      if (controller.signal.aborted) return;
      setRaw("");
      setNotice(
        `В очередь разрешения: ${report.accepted.length}; дубли: ${report.duplicates.length}; отклонено: ${report.rejected.length}. Подключение к Telegram не подтверждено.${report.rejected.length ? ` Отклонены: ${report.rejected.join(", ")}` : ""}`,
      );
      // The mutation already committed: a failed subsequent read must not claim rollback.
      try {
        const queued = await loadConfiguration(
          "donor-imports",
          controller.signal,
        );
        if (!controller.signal.aborted) setImports(queued);
      } catch (error) {
        if (!controller.signal.aborted)
          setError(
            `Импорт сохранён, но очередь не обновлена. ${errorText(error)}`,
          );
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setError(`Не удалось импортировать доноров. ${errorText(error)}`);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  return (
    <div className="donors-layout live-configuration">
      <Panel>
        <PanelTitle
          title={
            section === "accounts"
              ? "Telegram-аккаунты"
              : section === "donors"
                ? "Источники из API"
                : "Мои каналы из API"
          }
          icon={section}
        />
        <div className="toolbar">
          <label className="field">
            Поиск в списке
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <button
            disabled={busy || dirty || loading}
            onClick={() => setReload((value) => value + 1)}
          >
            Обновить список
          </button>
        </div>
        {loading && <p role="status">Загрузка конфигурации…</p>}
        {error && <Notice error>{error}</Notice>}
        {notice && <Notice>{notice}</Notice>}
        {!loading && !rows.length && (
          <p>Записей нет. DEMO не добавляется в рабочую базу.</p>
        )}
        <div className="live-config-list">
          {rows
            .filter((item) =>
              ("name" in item ? item.name : item.title)
                .toLowerCase()
                .includes(query.toLowerCase()),
            )
            .map((item) => (
              <button
                className={`source-row ${selectedId === item.id ? "selected" : ""}`}
                aria-pressed={selectedId === item.id}
                key={item.id}
                disabled={busy || dirty}
                onClick={() => {
                  setSelectedId(item.id);
                  setTitle("name" in item ? item.name : item.title);
                  setNotice("");
                }}
              >
                <Icon name={section} />
                <span>
                  <b>{"name" in item ? item.name : item.title}</b>
                  <small>
                    {"telegram_user_id" in item
                      ? `User ID: ${item.telegram_user_id}`
                      : `Channel ID: ${item.telegram_channel_id}`}
                  </small>
                </span>
              </button>
            ))}
        </div>
        {section === "donors" && (
          <section className="detail-section">
            <h3>Очередь импорта</h3>
            {!imports.length && <p>Очередь пуста.</p>}
            {imports.map((item) => (
              <p key={item.id}>
                {item.identifier} · {item.status} · аккаунт #
                {item.telegram_account_id}
              </p>
            ))}
          </section>
        )}
      </Panel>
      <Panel>
        <PanelTitle title="Ручные настройки" />
        <p className="help-copy">
          Данные PostgreSQL. Название можно менять, Telegram identity неизменна.
          Сохранение не запускает AI или публикацию.
        </p>
        {selected && (
          <>
            <label className="field">
              Название
              <input
                value={title}
                maxLength={section === "accounts" ? 100 : 255}
                disabled={busy || loading}
                onChange={(event) => {
                  setTitle(event.target.value);
                  setNotice("");
                }}
              />
            </label>
            {"session_provisioned" in selected && (
              <>
                <p>
                  {selected.session_provisioned
                    ? "Сессия сохранена; live-проверка отдельная"
                    : "Сессия не подключена"}
                </p>
                <p>Состояние: {selected.health_status}</p>
                <button
                  disabled
                  title="Требуются безопасный login flow и ручная Telegram-авторизация"
                >
                  Подключить Telegram
                </button>
              </>
            )}
            <div className="action-row">
              <button
                className="primary-button"
                disabled={
                  busy || loading || !title.trim() || title === selectedTitle
                }
                onClick={() => void saveTitle()}
              >
                Сохранить название
              </button>
              <button
                disabled={busy || loading || title === selectedTitle}
                onClick={() => {
                  setTitle(selectedTitle);
                  setNotice("");
                }}
              >
                Отменить правки названия
              </button>
            </div>
          </>
        )}
        {section === "donors" && (
          <section className="detail-section">
            <h3>Массовый импорт</h3>
            <p className="help-copy">
              Ссылки t.me, @username или числовые IDs. Пока нет авторизованной
              сессии и включённого ingestion worker, импорт остаётся в очереди.
              Импорт не создаёт маршруты автоматически.
            </p>
            <label className="field">
              Аккаунт импорта
              <select
                disabled={busy || Boolean(raw)}
                value={accountId}
                onChange={(event) => setAccountId(Number(event.target.value))}
              >
                {!accounts.length && <option value={0}>Нет аккаунтов</option>}
                {accounts.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Список доноров
              <textarea
                value={raw}
                maxLength={100000}
                disabled={busy || loading || !accountId}
                onChange={(event) => {
                  setRaw(event.target.value);
                  setNotice("");
                }}
              />
            </label>
            <div className="action-row">
              <button
                disabled={busy || loading || !accountId || !raw.trim()}
                onClick={() => void importDonors()}
              >
                Импортировать доноров
              </button>
              <button disabled={busy || !raw} onClick={() => setRaw("")}>
                Очистить список
              </button>
            </div>
          </section>
        )}
        {section !== "donors" && !loading && (
          <ConfigurationCreator
            path={path as "accounts" | "output-channels"}
            accounts={accounts}
            setDirty={setCreateDirty}
            setBusy={setBusy}
            disabled={busy || title !== selectedTitle}
            onCreated={(saved) => {
              setRows((prior) => [
                ...prior.filter((item) => item.id !== saved.id),
                saved,
              ]);
              setSelectedId(saved.id);
              setTitle("name" in saved ? saved.name : saved.title);
            }}
          />
        )}
        {section === "channels" && (
          <p className="help-copy">
            Лимит постов в день и автоматический подбор задаются в Планировщике.
            Создание записи канала — не проверка прав отправки.
          </p>
        )}
      </Panel>
    </div>
  );
}

function ConfigurationCreator({
  path,
  accounts,
  setDirty,
  setBusy,
  disabled,
  onCreated,
}: {
  path: "accounts" | "output-channels";
  accounts: AccountConfig[];
  setDirty: (dirty: boolean) => void;
  setBusy: (busy: boolean) => void;
  disabled: boolean;
  onCreated: (row: AccountConfig | ChannelConfig) => void;
}) {
  const [title, setTitle] = useState("");
  const [identity, setIdentity] = useState("");
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? 0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const lifetime = useLifetime();
  const activeWrite = useRef(false);
  const dirty = Boolean(title || identity);
  useEffect(() => {
    setDirty(dirty);
    return () => setDirty(false);
  }, [dirty, setDirty]);
  const create = async () => {
    if (disabled || activeWrite.current || !lifetime.current) return;
    setNotice("");
    setError("");
    const numeric = Number(identity);
    if (
      !/^-?[1-9]\d*$/.test(identity) ||
      !Number.isSafeInteger(numeric) ||
      (path === "accounts" ? numeric <= 0 : numeric >= -1000000000000)
    ) {
      setError(
        "Укажите точный безопасный Telegram ID; округление больших чисел недопустимо.",
      );
      return;
    }
    if (!title.trim() || (path !== "accounts" && !accountId)) return;
    const controller = lifetime.current;
    activeWrite.current = true;
    setBusy(true);
    try {
      const saved = await createConfiguration(
        path,
        title.trim(),
        numeric,
        accountId,
        controller.signal,
      );
      if (!controller.signal.aborted) {
        onCreated(saved);
        setTitle("");
        setIdentity("");
        setNotice(
          "Запись сохранена. Telegram-подключение и права не проверены.",
        );
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setError(`Не удалось создать запись. ${errorText(error)}`);
    } finally {
      activeWrite.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  return (
    <section className="detail-section">
      <h3>
        {path === "accounts"
          ? "Добавить запись аккаунта"
          : "Добавить выходной канал"}
      </h3>
      <p className="help-copy">
        Только конфигурация. Авторизация и подтверждение доступа к Telegram
        выполняются отдельно. Секреты не вводятся в эти поля.
      </p>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void create();
        }}
      >
        <fieldset className="live-planner-fields" disabled={disabled}>
          <label className="field">
            Название новой записи
            <input
              required
              maxLength={path === "accounts" ? 100 : 255}
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
                setNotice("");
              }}
            />
          </label>
          <label className="field">
            {path === "accounts" ? "Telegram User ID" : "Telegram Channel ID"}
            <input
              required
              inputMode="numeric"
              value={identity}
              placeholder={path === "accounts" ? "123456789" : "-1001234567890"}
              onChange={(event) => {
                setIdentity(event.target.value);
                setNotice("");
              }}
            />
          </label>
          {path !== "accounts" && (
            <label className="field">
              Аккаунт выходного канала
              <select
                value={accountId}
                disabled={dirty}
                onChange={(event) => setAccountId(Number(event.target.value))}
              >
                {!accounts.length && <option value={0}>Нет аккаунтов</option>}
                {accounts.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="action-row">
            <button
              disabled={
                !title.trim() ||
                !identity ||
                (path !== "accounts" && !accountId)
              }
            >
              {path === "accounts"
                ? "Создать запись аккаунта"
                : "Создать запись канала"}
            </button>
            <button
              type="button"
              disabled={!dirty}
              onClick={() => {
                setTitle("");
                setIdentity("");
                setError("");
                setNotice("");
              }}
            >
              Очистить новую запись
            </button>
          </div>
        </fieldset>
      </form>
    </section>
  );
}

export function LiveConnections({ markDirty }: Props) {
  const [mappings, setMappings] = useState<MappingConfig[]>([]);
  const [donors, setDonors] = useState<ChannelConfig[]>([]);
  const [outputs, setOutputs] = useState<ChannelConfig[]>([]);
  const [mappingId, setMappingId] = useState(0);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [donorId, setDonorId] = useState(0);
  const [outputId, setOutputId] = useState(0);
  const lifetime = useLifetime();
  useEffect(() => {
    markDirty("connections", dirty);
    return () => markDirty("connections", false);
  }, [dirty, markDirty]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void Promise.all([
      loadConfiguration("mappings", controller.signal),
      loadConfiguration("donors", controller.signal),
      loadConfiguration("output-channels", controller.signal),
    ])
      .then(([routes, sources, destinations]) => {
        if (controller.signal.aborted) return;
        setMappings(routes);
        setDonors(sources);
        setOutputs(destinations);
        setMappingId(routes[0]?.id ?? 0);
        setDonorId(sources[0]?.id ?? 0);
        setOutputId(destinations[0]?.id ?? 0);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(errorText(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reload]);
  const selected = mappings.find((item) => item.id === mappingId);
  const title = (item: MappingConfig) =>
    `${donors.find((source) => source.id === item.donor_channel_id)?.title ?? `Донор #${item.donor_channel_id}`} → ${outputs.find((output) => output.id === item.output_channel_id)?.title ?? `Канал #${item.output_channel_id}`}`;
  const create = async () => {
    if (busy || dirty || !donorId || !outputId || !lifetime.current) return;
    const controller = lifetime.current;
    setBusy(true);
    setError("");
    try {
      const saved = await saveMapping(
        null,
        {
          ...defaultPolicy,
          donor_channel_id: donorId,
          output_channel_id: outputId,
        },
        controller.signal,
      );
      if (!controller.signal.aborted) {
        setMappings((prior) => [
          ...prior.filter((item) => item.id !== saved.id),
          saved,
        ]);
        setMappingId(saved.id);
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setError(`Не удалось создать маршрут. ${errorText(error)}`);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  return (
    <div className="connections-layout live-configuration">
      <Panel>
        <PanelTitle title="Источники и каналы" icon="donors" />
        <p className="help-copy">
          Создание связи сохраняет настройки в PostgreSQL. Это не отправка
          поста.
        </p>
        <label className="field">
          Донор нового маршрута
          <select
            value={donorId}
            disabled={busy || dirty || loading}
            onChange={(event) => setDonorId(Number(event.target.value))}
          >
            {!donors.length && <option value={0}>Нет доноров</option>}
            {donors.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Канал нового маршрута
          <select
            value={outputId}
            disabled={busy || dirty || loading}
            onChange={(event) => setOutputId(Number(event.target.value))}
          >
            {!outputs.length && <option value={0}>Нет каналов</option>}
            {outputs.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={
            busy ||
            dirty ||
            loading ||
            !donorId ||
            !outputId ||
            mappings.some(
              (item) =>
                item.donor_channel_id === donorId &&
                item.output_channel_id === outputId,
            )
          }
          onClick={() => void create()}
        >
          Создать маршрут
        </button>
      </Panel>
      <Panel>
        <PanelTitle title="Маршруты из API" icon="connections" />
        <button
          disabled={busy || dirty || loading}
          onClick={() => setReload((value) => value + 1)}
        >
          Обновить связи
        </button>
        {loading && <p role="status">Загрузка связей…</p>}
        {error && <Notice error>{error}</Notice>}
        <label className="field">
          Маршрут
          <select
            value={mappingId}
            disabled={dirty || busy || loading}
            onChange={(event) => setMappingId(Number(event.target.value))}
          >
            {!mappings.length && <option value={0}>Нет маршрутов</option>}
            {mappings.map((item) => (
              <option key={item.id} value={item.id}>
                {title(item)}
              </option>
            ))}
          </select>
        </label>
        {mappings.map((item) => (
          <button
            className={`route-card ${item.id === mappingId ? "selected" : ""}`}
            key={item.id}
            aria-pressed={item.id === mappingId}
            disabled={dirty || busy || loading}
            onClick={() => setMappingId(item.id)}
          >
            <b>{title(item)}</b>
            <p className="help-copy">
              Входящих: {item.intake_percent}% · целевая доля:{" "}
              {item.target_mix_percent}%
            </p>
          </button>
        ))}
        {dirty && (
          <p className="help-copy">
            Сохраните или отмените правки перед сменой маршрута.
          </p>
        )}
      </Panel>
      {!loading && !error && selected ? (
        <MappingEditor
          key={selected.id}
          mapping={selected}
          title={title(selected)}
          setDirty={setDirty}
          setBusy={setBusy}
          onSaved={(saved) =>
            setMappings((prior) =>
              prior.map((item) => (item.id === saved.id ? saved : item)),
            )
          }
        />
      ) : (
        <Panel>
          <PanelTitle title="Настройки маршрута" />
          <p>
            Выберите настроенный маршрут. Технические фильтры не заменяют
            EditorialGate.
          </p>
        </Panel>
      )}
    </div>
  );
}

function MappingEditor({
  mapping,
  title,
  setDirty,
  setBusy,
  onSaved,
}: {
  mapping: MappingConfig;
  title: string;
  setDirty: (dirty: boolean) => void;
  setBusy: (busy: boolean) => void;
  onSaved: (mapping: MappingConfig) => void;
}) {
  const [draft, setDraft] = useState(() => policy(mapping));
  const [filters, setFilters] = useState<FilterConfig | null>(null);
  const [media, setMedia] = useState<FilterConfig["allowed_media_types"]>([]);
  const [domains, setDomains] = useState("");
  const [markers, setMarkers] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [busy, busyState] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [rightsDirty, setRightsDirty] = useState(false);
  const [rightsBusy, setRightsBusy] = useState(false);
  const lifetime = useLifetime();
  const mappingDirty = !equal(draft, policy(mapping));
  const filtersDirty =
    filters !== null &&
    (!equal([...media].sort(), [...filters.allowed_media_types].sort()) ||
      domains !== filters.blocked_domains.join("\n") ||
      markers !== filters.ad_markers.join("\n"));
  useEffect(() => {
    setDirty(mappingDirty || filtersDirty || rightsDirty);
    return () => setDirty(false);
  }, [mappingDirty, filtersDirty, rightsDirty, setDirty]);
  useEffect(() => {
    setBusy(busy || loading || rightsBusy);
    return () => setBusy(false);
  }, [busy, loading, rightsBusy, setBusy]);
  const resetFilters = (saved: FilterConfig) => {
    setFilters(saved);
    setMedia(saved.allowed_media_types);
    setDomains(saved.blocked_domains.join("\n"));
    setMarkers(saved.ad_markers.join("\n"));
  };
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void mappingFilters(mapping.id, controller.signal)
      .then((saved) => {
        if (!controller.signal.aborted) resetFilters(saved);
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setError(`Не удалось загрузить фильтры. ${errorText(error)}`);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [mapping.id, reload]);
  const save = async (kind: "mapping" | "filters") => {
    if (busy || loading || !lifetime.current) return;
    const controller = lifetime.current;
    busyState(true);
    setError("");
    setNotice("");
    try {
      if (kind === "mapping") {
        const saved = await saveMapping(mapping.id, draft, controller.signal);
        if (
          saved.donor_channel_id !== mapping.donor_channel_id ||
          saved.output_channel_id !== mapping.output_channel_id
        )
          throw new Error("API изменил immutable identity маршрута");
        if (!controller.signal.aborted) {
          onSaved(saved);
          setDraft(policy(saved));
          setNotice("Маршрут сохранён в базе данных.");
        }
      } else {
        const split = (value: string) =>
          value
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean);
        const saved = await mappingFilters(mapping.id, controller.signal, {
          allowed_media_types: media,
          blocked_domains: split(domains),
          ad_markers: split(markers),
        });
        if (!controller.signal.aborted) {
          resetFilters(saved);
          setNotice("Фильтры сохранены в базе данных.");
        }
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setError(
          `Не удалось сохранить ${kind === "mapping" ? "маршрут" : "фильтры"}. Правки сохранены в форме. ${errorText(error)}`,
        );
    } finally {
      if (!controller.signal.aborted) busyState(false);
    }
  };
  return (
    <Panel className="route-editor">
      <PanelTitle title="Настройки маршрута" />
      <p className="help-copy">{title}</p>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save("mapping");
        }}
      >
        <fieldset className="live-planner-fields" disabled={busy || loading}>
          <label className="field">
            Доля входящих материалов, %
            <input
              type="number"
              min={0}
              max={100}
              step={1}
              required
              value={draft.intake_percent}
              onChange={(event) => {
                setDraft({
                  ...draft,
                  intake_percent: Number(event.target.value),
                });
                setNotice("");
              }}
            />
          </label>
          <label className="field">
            Целевая доля донора, %
            <input
              type="number"
              min={0}
              max={100}
              step={1}
              required
              value={draft.target_mix_percent}
              onChange={(event) => {
                setDraft({
                  ...draft,
                  target_mix_percent: Number(event.target.value),
                });
                setNotice("");
              }}
            />
          </label>
          <label className="field">
            Допуск к планированию
            <select
              value={draft.eligibility_mode}
              onChange={(event) => {
                setDraft({
                  ...draft,
                  eligibility_mode: event.target
                    .value as MappingPolicy["eligibility_mode"],
                  delay_minutes:
                    event.target.value === "IMMEDIATE"
                      ? 0
                      : draft.delay_minutes,
                });
                setNotice("");
              }}
            >
              <option value="IMMEDIATE">
                Сразу после обязательных проверок
              </option>
              <option value="DELAYED">С настраиваемой задержкой</option>
            </select>
          </label>
          <label className="field">
            Задержка, минут
            <input
              type="number"
              min={0}
              max={10080}
              step={1}
              required
              disabled={draft.eligibility_mode === "IMMEDIATE"}
              value={draft.delay_minutes}
              onChange={(event) => {
                setDraft({
                  ...draft,
                  delay_minutes: Number(event.target.value),
                });
                setNotice("");
              }}
            />
          </label>
          <label className="field">
            Приоритет
            <input
              type="number"
              min={-1000}
              max={1000}
              step={1}
              required
              value={draft.priority}
              onChange={(event) => {
                setDraft({ ...draft, priority: Number(event.target.value) });
                setNotice("");
              }}
            />
          </label>
          <label className="field">
            Изображения
            <select
              value={draft.media_policy}
              onChange={(event) => {
                setDraft({
                  ...draft,
                  media_policy: event.target
                    .value as MappingPolicy["media_policy"],
                });
                setNotice("");
              }}
            >
              <option value="REUSE_SOURCE">Фото исходного поста</option>
              <option value="LICENSED_LIBRARY">
                Лицензированная медиатека / поиск
              </option>
            </select>
          </label>
          <p className="help-copy">
            Допуск не означает немедленную публикацию: остаются EditorialGate,
            проверка рерайта и план канала. Интернет-поиск требует отдельно
            включённого media worker; права и релевантность проверяются
            отдельно.
          </p>
          <div className="action-row">
            <button className="primary-button" disabled={!mappingDirty}>
              Сохранить маршрут
            </button>
            <button
              type="button"
              disabled={!mappingDirty}
              onClick={() => {
                setDraft(policy(mapping));
                setNotice("");
              }}
            >
              Отменить правки маршрута
            </button>
          </div>
        </fieldset>
      </form>
      <SourceRightsEditor
        mappingId={mapping.id}
        setDirty={setRightsDirty}
        setBusy={setRightsBusy}
      />
      <section className="detail-section">
        <h3>Технические фильтры</h3>
        {loading && <p role="status">Загрузка фильтров…</p>}
        {!filters && !loading && (
          <button onClick={() => setReload((value) => value + 1)}>
            Повторить загрузку фильтров
          </button>
        )}
        {filters && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void save("filters");
            }}
          >
            <fieldset
              className="live-planner-fields"
              disabled={busy || loading}
            >
              <div className="checkbox-row">
                {(["text", "photo", "video"] as const).map((type) => (
                  <label key={type}>
                    <input
                      type="checkbox"
                      checked={media.includes(type)}
                      onChange={(event) => {
                        setMedia((prior) =>
                          event.target.checked
                            ? [...prior, type]
                            : prior.filter((item) => item !== type),
                        );
                        setNotice("");
                      }}
                    />
                    {type === "text"
                      ? "Текст"
                      : type === "photo"
                        ? "Фото"
                        : "Видео"}
                  </label>
                ))}
              </div>
              <label className="field">
                Запрещённые домены
                <textarea
                  value={domains}
                  maxLength={30000}
                  placeholder="example.org — один домен на строку"
                  onChange={(event) => {
                    setDomains(event.target.value);
                    setNotice("");
                  }}
                />
              </label>
              <label className="field">
                Дополнительные рекламные маркеры
                <textarea
                  value={markers}
                  maxLength={2100}
                  onChange={(event) => {
                    setMarkers(event.target.value);
                    setNotice("");
                  }}
                />
              </label>
              <p className="help-copy">
                Встроенные рекламные проверки обязательны и не отключаются.
                Пустой список типов отклоняет весь контент. Даже разрешённое
                видео требует реализованной безопасной media-публикации.
              </p>
              <p className="help-copy">
                Эффективные маркеры: {filters.effective_ad_markers.join(", ")}
              </p>
              <div className="action-row">
                <button className="primary-button" disabled={!filtersDirty}>
                  Сохранить фильтры
                </button>
                <button
                  type="button"
                  disabled={!filtersDirty}
                  onClick={() => {
                    resetFilters(filters);
                    setNotice("");
                  }}
                >
                  Отменить правки фильтров
                </button>
              </div>
            </fieldset>
          </form>
        )}
      </section>
      <p className="help-copy">
        Маршрут и фильтры сохраняются отдельно. Ни одна настройка не разрешает
        рерайт для EDITORIAL REJECT и не отправляет публикацию.
      </p>
    </Panel>
  );
}

function SourceRightsEditor({
  mappingId,
  setDirty,
  setBusy,
}: {
  mappingId: number;
  setDirty: (dirty: boolean) => void;
  setBusy: (busy: boolean) => void;
}) {
  const [saved, setSaved] = useState<SourceRightsConfig | null>(null);
  const [draft, setDraft] = useState<SourceRightsPolicy>({
    license_code: "UNDECLARED",
    attribution: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const lifetime = useLifetime();
  const dirty =
    saved !== null &&
    (draft.license_code !== saved.license_code ||
      draft.attribution !== saved.attribution);
  const reset = (value: SourceRightsConfig) => {
    setSaved(value);
    setDraft({
      license_code: value.license_code,
      attribution: value.attribution,
    });
  };
  useEffect(() => {
    setDirty(dirty);
    return () => setDirty(false);
  }, [dirty, setDirty]);
  useEffect(() => {
    setBusy(loading || saving);
    return () => setBusy(false);
  }, [loading, saving, setBusy]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void sourceMediaRights(mappingId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) reset(value);
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setError(`Не удалось загрузить права. ${errorText(error)}`);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [mappingId, reload]);
  const save = async () => {
    if (loading || saving || !saved || !dirty || !lifetime.current) return;
    const controller = lifetime.current;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const value = await sourceMediaRights(
        mappingId,
        controller.signal,
        draft,
      );
      if (!controller.signal.aborted) {
        reset(value);
        setNotice("Права сохранены в базе данных.");
      }
    } catch (error) {
      if (!controller.signal.aborted)
        setError(
          `Не удалось сохранить права. Правки сохранены в форме. ${errorText(error)}`,
        );
    } finally {
      if (!controller.signal.aborted) setSaving(false);
    }
  };
  return (
    <section className="detail-section">
      <h3>Права на фото донора</h3>
      <p className="help-copy">
        Доступ к каналу не даёт разрешения на копирование. Без явного
        подтверждения прав исходные фото не скачиваются. Защищённый контент и
        альбомы блокируются. Сохранение не подключает Telegram и не публикует
        посты; source-photo worker включается отдельно.
      </p>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      {loading && <p role="status">Загрузка прав…</p>}
      {!saved && !loading && (
        <button onClick={() => setReload((value) => value + 1)}>
          Повторить загрузку прав
        </button>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <fieldset
          className="live-planner-fields"
          disabled={loading || saving || saved === null}
        >
          <label className="field">
            Права на исходное фото
            <select
              value={draft.license_code}
              onChange={(event) => {
                const license_code = event.target
                  .value as SourceRightsPolicy["license_code"];
                setDraft({
                  license_code,
                  attribution:
                    license_code === "UNDECLARED" ? "" : draft.attribution,
                });
                setNotice("");
              }}
            >
              <option value="UNDECLARED">Не подтверждены — не скачивать</option>
              <option value="OWNED">Я владею правами</option>
              <option value="PERMISSION">
                Есть разрешение правообладателя
              </option>
            </select>
          </label>
          <label className="field">
            Основание / авторство
            <textarea
              maxLength={2048}
              required={draft.license_code === "PERMISSION"}
              disabled={draft.license_code === "UNDECLARED"}
              value={draft.attribution}
              onChange={(event) => {
                setDraft({ ...draft, attribution: event.target.value });
                setNotice("");
              }}
            />
          </label>
          <div className="action-row">
            <button
              className="primary-button"
              disabled={
                !dirty ||
                (draft.license_code === "PERMISSION" &&
                  !draft.attribution.trim())
              }
            >
              Сохранить права на фото
            </button>
            <button
              type="button"
              disabled={!dirty}
              onClick={() => {
                if (saved) reset(saved);
                setNotice("");
              }}
            >
              Отменить правки прав
            </button>
          </div>
        </fieldset>
      </form>
    </section>
  );
}
