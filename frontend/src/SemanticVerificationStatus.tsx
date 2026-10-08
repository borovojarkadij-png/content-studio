import { useEffect, useId, useState } from "react";
import { loadSemanticStatus, type SemanticStatus } from "./semanticStatusApi";
import { Notice } from "./ui";

const gateLabels: Record<SemanticStatus["current_gate"], string> = {
  READY_SNAPSHOT: "Предварительные условия проверки сохранены",
  MANUAL: "Настроено ручное одобрение",
  BLOCKED: "Актуальные ограничения блокируют проверку",
  NOT_PENDING: "Вариант не ожидает автоматической проверки",
};
const reasonLabels: Record<
  NonNullable<SemanticStatus["reason_code"]>,
  string
> = {
  SEMANTIC_REWRITE_JOB_INVALID:
    "Рерайт не завершён или его привязка некорректна.",
  EDITORIAL_HARD_CONSTRAINT_BLOCKED:
    "EditorialGate не разрешает обработку. AI не должен вызываться.",
  SEMANTIC_DRAFT_NOT_PENDING_OR_MISMATCHED:
    "Вариант уже рассмотрен или не соответствует исходной задаче.",
  SOURCE_REVISION_NOT_CURRENT_OR_MISSING:
    "Источник изменён, удалён, недоступен или требует синхронизации.",
  SEMANTIC_AUTOMATIC_POLICY_DISABLED:
    "Автоматическое одобрение не включено для этого канала.",
  SEMANTIC_VERIFIER_NOT_QUALIFIED:
    "Нет действующей квалификации закреплённого verifier release.",
  FACT_PRESERVATION_BLOCKED:
    "Детерминированная проверка фактов отклонила текст.",
  CURRENT_SEMANTIC_GUARD_BLOCKED:
    "Актуальная привязка не подтверждена. Требуется ручная проверка.",
};
const jobLabels = {
  QUEUED: "В очереди проверки фактов",
  RUNNING: "Сохранена активная задача проверки",
  SUCCEEDED: "Задача завершена (сохранённая история)",
  REVIEW: "Нужен ручной разбор результата",
  BLOCKED: "Задача проверки заблокирована",
  FAILED: "Задача проверки завершилась ошибкой",
};

export function SemanticVerificationStatus({
  outputId,
  channelId,
  refreshKey = 0,
}: {
  outputId: number;
  channelId: number;
  refreshKey?: number;
}) {
  return (
    <Disclosure
      key={`${outputId}:${channelId}:${refreshKey}`}
      outputId={outputId}
      channelId={channelId}
    />
  );
}

function Disclosure({
  outputId,
  channelId,
}: {
  outputId: number;
  channelId: number;
}) {
  const [open, setOpen] = useState(false);
  const regionId = useId();
  return (
    <div className="detail-section">
      <button
        aria-expanded={open}
        aria-controls={regionId}
        aria-label={`Проверка фактов: статус рерайта ${outputId}`}
        onClick={() => setOpen((value) => !value)}
      >
        Проверка фактов: статус
      </button>
      <section
        id={regionId}
        hidden={!open}
        aria-label={`Состояние проверки фактов ${outputId}`}
      >
        {open && <Diagnostic outputId={outputId} channelId={channelId} />}
      </section>
    </div>
  );
}

function Diagnostic({
  outputId,
  channelId,
}: {
  outputId: number;
  channelId: number;
}) {
  const [status, setStatus] = useState<SemanticStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setStatus(null);
    setError("");
    setLoading(true);
    void loadSemanticStatus(outputId, channelId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setStatus(value);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted)
          setError(reason instanceof Error ? reason.message : "Ошибка API");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [outputId, channelId, reload]);
  const job = status?.latest_job;
  return (
    <div aria-busy={loading}>
      <h4>Диагностика проверки фактов</h4>
      <p className="help-copy">
        Только сохранённое состояние SQL. Состояние сетевого worker неизвестно;
        GET не запускает AI, одобрение или публикацию.
      </p>
      {loading && <p role="status">Загрузка состояния проверки…</p>}
      {error && (
        <Notice error>Не удалось прочитать проверку фактов. {error}</Notice>
      )}
      {!loading && status && (
        <>
          <p role="status">
            <strong>{gateLabels[status.current_gate]}</strong>
          </p>
          {status.reason_code && (
            <p className="help-copy">{reasonLabels[status.reason_code]}</p>
          )}
          <p className="help-copy">
            Это снимок условий, а не разрешение на AI или публикацию. Worker
            обязан повторно проверить все ограничения.
          </p>
          {job ? (
            <>
              <p>
                <strong>
                  {job.lease_expired
                    ? "Ожидается восстановление worker"
                    : jobLabels[job.state]}
                </strong>
              </p>
              <p>
                Попытки процесса: {job.attempts} из {job.max_attempts}; не число
                оплаченных AI-вызовов.
              </p>
              {job.binding_current === false && (
                <Notice error>
                  История задачи не подтверждает текущую привязку.
                </Notice>
              )}
              <p className="help-copy">
                Задача #{job.id} · release #{job.release_id}
              </p>
            </>
          ) : (
            <p>
              Задача проверки ещё не создана. Это не подтверждение запуска
              worker.
            </p>
          )}
        </>
      )}
      <button
        disabled={loading}
        aria-label={`Обновить статус проверки фактов ${outputId}`}
        onClick={() => {
          setStatus(null);
          setError("");
          setLoading(true);
          setReload((value) => value + 1);
        }}
      >
        Обновить статус проверки
      </button>
    </div>
  );
}
