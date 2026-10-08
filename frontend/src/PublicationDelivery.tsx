import { useEffect, useState } from "react";
import { deliveryStatus, type DeliveryStatus } from "./deliveryApi";
import { Notice } from "./ui";

const labels: Record<DeliveryStatus["state"], string> = {
  NOT_QUEUED: "Задание отправки не создано",
  QUEUED: "Задание отправки в очереди",
  CLAIMED: "Проверка перед отправкой",
  SENDING: "Отправка начата, подтверждение не получено",
  SUCCEEDED: "Доставка подтверждена",
  BLOCKED: "Отправка заблокирована",
  FAILED: "Задание отправки остановлено",
  NEEDS_RECONCILIATION: "Результат отправки неизвестен",
};
export function PublicationDelivery({ plannedId }: { plannedId: number }) {
  const [status, setStatus] = useState<DeliveryStatus | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setStatus(null);
    setBusy(true);
    setError("");
    void deliveryStatus(plannedId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setStatus(value);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error
              ? cause.message
              : "История доставки недоступна",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [plannedId, refresh]);
  return (
    <section
      className="media-preparation"
      aria-label={`Доставка публикации ${plannedId}`}
    >
      <b>Доставка</b>
      {busy && <p role="status">Загрузка истории доставки…</p>}
      {error && <Notice error>{error}</Notice>}
      {status && (
        <>
          <p>
            {labels[status.state]} · попыток: {status.attempts}/2
          </p>
          {status.state === "SUCCEEDED" && (
            <p className="help-copy">
              Сообщение #{status.sent_message_id} ·{" "}
              {new Date(status.completed_at!).toLocaleString("ru-RU")}
            </p>
          )}
          {status.state === "NEEDS_RECONCILIATION" && (
            <Notice error>
              Повторная отправка запрещена до сверки с Telegram. Неизвестный
              результат продолжает занимать дневной лимит.
            </Notice>
          )}
          {status.state === "SENDING" && (
            <p className="help-copy">
              Повторная отправка недоступна до подтверждения результата.
            </p>
          )}
          {status.reason_code && (
            <p className="help-copy">{status.reason_code}</p>
          )}
          {!status.live_publication_available && (
            <p className="help-copy">
              Автоматическая отправка пока не подключена. Подготовка и одобрение
              поста сами по себе его не публикуют.
            </p>
          )}
        </>
      )}
      <div className="action-row">
        <button
          disabled={busy}
          aria-label={`Обновить доставку ${plannedId}`}
          onClick={() => {
            setStatus(null);
            setRefresh((value) => value + 1);
          }}
        >
          Обновить статус доставки
        </button>
      </div>
    </section>
  );
}
