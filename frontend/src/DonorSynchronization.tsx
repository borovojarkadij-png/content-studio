import { useEffect, useState } from "react";
import {
  loadDonorSyncStatus,
  type DonorSyncState,
  type DonorSyncStatus,
} from "./donorSyncApi";
import { Notice } from "./ui";

const descriptions: Record<DonorSyncState, [string, string]> = {
  READY: [
    "Синхронизация завершена (сохранённое состояние)",
    "Рерайт и публикация по-прежнему требуют актуального EditorialGate и всех остальных проверок.",
  ],
  NOT_ENFORCED: [
    "Контроль синхронизации не включён",
    "Legacy-режим не подтверждает полноту истории. Этот статус не является разрешением на публикацию.",
  ],
  BASELINE_REQUIRED: [
    "Требуется начальный checkpoint",
    "Без авторизованной сессии и маршрутов worker не может безопасно начать обработку нового источника.",
  ],
  LEGACY_SYNC_REQUIRED: [
    "Требуется явная ресинхронизация",
    "У источника уже есть сохранённая история. Автоматический сброс checkpoint недоступен.",
  ],
  SYNC_IN_PROGRESS: [
    "Синхронизация выполняется",
    "Сохранена активная lease. Обработка ждёт завершения проверки истории.",
  ],
  RECOVERY_DUE: [
    "Ожидается восстановление worker",
    "Повтор уже допустим по сохранённому состоянию; GET не запускает worker.",
  ],
  WAIT_RETRY: [
    "Ожидается повтор синхронизации",
    "Время следующей попытки сохранено в PostgreSQL.",
  ],
  GAP_UNRESOLVED: [
    "Разрыв истории не устранён",
    "TooLong или другой известный разрыв не позволяет подтвердить полноту источника. Автоматический сброс недоступен.",
  ],
  INVALID_BASELINE: [
    "Checkpoint не соответствует источнику",
    "Сохранённое состояние не подтверждает текущую привязку аккаунта и канала.",
  ],
  ACCOUNT_UNAVAILABLE: [
    "Аккаунт недоступен для синхронизации",
    "Проверьте авторизацию и сохранённое состояние аккаунта. Эта диагностика не выполняет Telegram login.",
  ],
  COOLDOWN: [
    "Пауза Telegram / FloodWait",
    "Worker должен дождаться сохранённого cooldown и повторно проверить аккаунт.",
  ],
};

export function DonorSynchronization({
  donorId,
  refreshKey = 0,
}: {
  donorId: number;
  refreshKey?: number;
}) {
  // Identity-keyed child clears the old donor before its replacement's first render.
  return <Diagnostic key={`${donorId}:${refreshKey}`} donorId={donorId} />;
}

function Diagnostic({ donorId }: { donorId: number }) {
  const [status, setStatus] = useState<DonorSyncStatus | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setStatus(null);
    setError("");
    void loadDonorSyncStatus(donorId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setStatus(value);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setError(error instanceof Error ? error.message : "Ошибка API");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [donorId, reload]);
  return (
    <section
      className="detail-section"
      aria-label="Синхронизация источника"
      aria-busy={loading}
    >
      <h3>Синхронизация источника</h3>
      <p className="help-copy">
        Сохранённое состояние PostgreSQL; live-проверка Telegram не выполнялась.
      </p>
      {loading && <p role="status">Загрузка состояния синхронизации…</p>}
      {error && (
        <Notice error>
          Не удалось прочитать состояние синхронизации. {error}
        </Notice>
      )}
      {!loading && status && (
        <>
          <p role="status">
            <strong>{descriptions[status.state][0]}</strong>
          </p>
          <p className="help-copy">{descriptions[status.state][1]}</p>
          {status.source_processing_blocked && (
            <Notice error>
              Обработка источника заблокирована синхронизацией. GET не снимает
              ограничения и не запускает AI или публикацию.
            </Notice>
          )}
          {status.pts !== null && <p>Сохранённый pts: {status.pts}</p>}
          {status.retry_at &&
            ["WAIT_RETRY", "RECOVERY_DUE", "COOLDOWN"].includes(
              status.state,
            ) && (
              <p>
                Повтор не ранее:{" "}
                <time dateTime={status.retry_at}>
                  {new Date(status.retry_at).toLocaleString("ru-RU")}
                </time>
              </p>
            )}
        </>
      )}
      <button
        disabled={loading}
        onClick={() => {
          setStatus(null);
          setError("");
          setLoading(true);
          setReload((value) => value + 1);
        }}
      >
        Обновить синхронизацию
      </button>
    </section>
  );
}
