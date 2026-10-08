import { useEffect, useRef, useState } from "react";
import {
  approvalPolicy,
  type ApprovalMode,
  type ApprovalPolicy,
} from "./approvalPolicyApi";
import { Notice, Panel, PanelTitle } from "./ui";

type Props = {
  channelId: number;
  onDirty: (dirty: boolean) => void;
  onBusy: (busy: boolean) => void;
  onSaved: () => void;
};

export function ApprovalPolicyPanel(props: Props) {
  return <PolicyForm key={props.channelId} {...props} />;
}

function PolicyForm({ channelId, onDirty, onBusy, onSaved }: Props) {
  const [policy, setPolicy] = useState<ApprovalPolicy | null>(null);
  const [mode, setMode] = useState<ApprovalMode>("MANUAL");
  const [releaseId, setReleaseId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const mutations = useRef(new AbortController());
  const inFlight = useRef(false);
  const dirty =
    policy !== null &&
    (mode !== policy.mode || releaseId !== policy.release_id);
  const releaseAvailable =
    policy?.qualified_releases.some((release) => release.id === releaseId) ??
    false;
  const selectionValid = mode === "MANUAL" || releaseAvailable;
  const adopt = (value: ApprovalPolicy) => {
    setPolicy(value);
    setMode(value.mode);
    setReleaseId(value.release_id);
  };
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
    setError("");
    setNotice("");
    setPolicy(null);
    void approvalPolicy(channelId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) adopt(value);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(reason instanceof Error ? reason.message : "Ошибка API");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [channelId, reload]);
  const save = async () => {
    const signal = mutations.current.signal;
    if (
      inFlight.current ||
      signal.aborted ||
      !policy ||
      !dirty ||
      !selectionValid
    )
      return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = await approvalPolicy(channelId, signal, {
        mode,
        release_id: mode === "MANUAL" ? null : releaseId,
      });
      if (!signal.aborted) {
        adopt(value);
        onSaved();
        setNotice(
          "Настройка одобрения сохранена. Worker не включён, публикация не выполнена.",
        );
      }
    } catch (reason: unknown) {
      if (!signal.aborted)
        setError(reason instanceof Error ? reason.message : "Ошибка API");
    } finally {
      inFlight.current = false;
      if (!signal.aborted) setBusy(false);
    }
  };
  return (
    <Panel>
      <PanelTitle title="Одобрение рерайтов" icon="shield" />
      <p className="help-copy">
        Ручное одобрение по умолчанию. Автоматическое возможно только после
        проверки фактов закреплённой квалифицированной моделью. EditorialGate и
        актуальные ограничения обязательны для каждого варианта.
      </p>
      <p className="help-copy">
        Настройка не квалифицирует модели и не включает сетевой worker. Подбор
        расписания, подготовка медиа и отправка настраиваются отдельно.
      </p>
      {loading && <p role="status">Загрузка настройки одобрения…</p>}
      {!loading && policy && (
        <>
          <fieldset className="live-planner-fields" disabled={busy}>
            <div className="form-grid">
              <label className="field">
                Одобрение рерайтов
                <select
                  value={mode}
                  onChange={(event) => {
                    const next = event.target.value as ApprovalMode;
                    setMode(next);
                    setReleaseId(
                      next === "MANUAL"
                        ? null
                        : releaseAvailable
                          ? releaseId
                          : (policy.qualified_releases[0]?.id ?? null),
                    );
                    setError("");
                    setNotice("");
                  }}
                >
                  <option value="MANUAL">Вручную для каждого варианта</option>
                  <option
                    value="VERIFIED"
                    disabled={!policy.qualified_releases.length}
                  >
                    Автоматически после проверки фактов
                  </option>
                </select>
              </label>
              {mode === "VERIFIED" && (
                <label className="field">
                  Закреплённая модель проверки фактов
                  <select
                    value={releaseId ?? ""}
                    onChange={(event) => {
                      setReleaseId(Number(event.target.value));
                      setError("");
                      setNotice("");
                    }}
                  >
                    {!releaseAvailable && (
                      <option value={releaseId ?? ""} disabled>
                        Release #{releaseId ?? "не выбран"} недоступен
                      </option>
                    )}
                    {policy.qualified_releases.map((release) => (
                      <option key={release.id} value={release.id}>
                        {release.provider} · {release.model} · #{release.id}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          </fieldset>
          {!policy.qualified_releases.length && (
            <p className="help-copy">
              Нет квалифицированных моделей. Необходим проверенный benchmark и
              отдельно зарегистрированный release; произвольную модель нельзя
              одобрить этой формой.
            </p>
          )}
          {mode === "VERIFIED" && !releaseAvailable && (
            <Notice error>
              Сохранённый release недоступен или отозван. Автоматическое
              одобрение заблокировано; выберите доступную модель или ручной
              режим.
            </Notice>
          )}
          <div className="action-row">
            <button
              disabled={busy || !dirty || !selectionValid}
              onClick={() => void save()}
            >
              Сохранить одобрение
            </button>
            <button
              disabled={busy || !dirty}
              onClick={() => {
                adopt(policy);
                setError("");
                setNotice("");
              }}
            >
              Отменить правки одобрения
            </button>
          </div>
        </>
      )}
      {error && <Notice error>Настройка одобрения: {error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      <div className="action-row">
        <button
          disabled={loading || busy || dirty}
          onClick={() => setReload((value) => value + 1)}
        >
          Обновить настройку одобрения
        </button>
      </div>
    </Panel>
  );
}
