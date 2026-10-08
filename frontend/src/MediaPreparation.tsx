import { useEffect, useRef, useState } from "react";
import { mediaStatus, mediaPreview, type MediaStatus } from "./mediaApi";
import { Notice } from "./ui";

const labels: Record<MediaStatus["state"], string> = {
  NOT_QUEUED: "Не поставлено в очередь",
  QUEUED: "В очереди",
  RUNNING: "Подготовка",
  SUCCEEDED: "Задание завершено",
  FAILED: "Ошибка задания",
  BLOCKED: "Задание заблокировано",
  NO_MATCH: "Подходящее фото не найдено",
};
export function MediaPreparation({ candidateId }: { candidateId: number }) {
  const [status, setStatus] = useState<MediaStatus | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const url = useRef("");
  const clearPreview = () => {
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = "";
    setPreviewUrl("");
  };
  const request = useRef<AbortController | null>(null);
  const load = async (queue = false) => {
    if (queue && (request.current || !status?.queue_allowed)) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    clearPreview();
    setBusy(true);
    setError("");
    setStatus(null);
    try {
      const value = await mediaStatus(candidateId, controller.signal, queue);
      if (!controller.signal.aborted) setStatus(value);
    } catch (cause: unknown) {
      if (!controller.signal.aborted)
        setError(cause instanceof Error ? cause.message : "Ошибка API медиа");
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setBusy(false);
      }
    }
  };
  const preview = async () => {
    if (request.current || !status?.selected_allowed || !status.asset) return;
    const controller = new AbortController();
    request.current = controller;
    clearPreview();
    setError("");
    setBusy(true);
    try {
      const blob = await mediaPreview(
        candidateId,
        status.asset,
        controller.signal,
      );
      if (!controller.signal.aborted) {
        url.current = URL.createObjectURL(blob);
        setPreviewUrl(url.current);
      }
    } catch (cause: unknown) {
      if (!controller.signal.aborted) {
        setStatus(null);
        setError(
          cause instanceof Error ? cause.message : "Ошибка предпросмотра",
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setBusy(false);
      }
    }
  };
  useEffect(() => {
    void load();
    return () => {
      request.current?.abort();
      request.current = null;
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = "";
    };
  }, [candidateId]);
  return (
    <section
      className="media-preparation"
      aria-label={`Медиа материала ${candidateId}`}
    >
      <b>Подготовка фото</b>
      {busy && <p role="status">Загрузка состояния медиа…</p>}
      {status && (
        <>
          <p>
            {status.media_policy === "REUSE_SOURCE"
              ? "Исходное фото донора"
              : "Иллюстрация из открытой библиотеки"}
          </p>
          <p>
            {labels[status.state]} · попыток: {status.attempts}/2
          </p>
          {status.reason_code && <p>Причина задания: {status.reason_code}</p>}
          {status.queue_reason_code && (
            <p>Постановка: {status.queue_reason_code}</p>
          )}
          {status.media_policy === "LICENSED_LIBRARY" && (
            <p className="help-copy">
              Подбор по теме не подтверждает изображение события. Проверьте
              соответствие фото вручную.
            </p>
          )}
          {status.asset && (
            <p>
              Медиа #{status.asset.id} · {status.asset.license_code} ·{" "}
              {status.asset.attribution || "Собственное фото"}
            </p>
          )}
        </>
      )}
      <p className="help-copy">
        Worker включается отдельно. Постановка в очередь не означает скачивание
        или публикацию.
      </p>
      <div className="action-row">
        <button
          disabled={busy || !status?.queue_allowed}
          aria-label={`Подготовить медиа ${candidateId}`}
          onClick={() => void load(true)}
        >
          Подготовить фото
        </button>
        <button
          disabled={busy}
          aria-label={`Обновить медиа ${candidateId}`}
          onClick={() => void load()}
        >
          Обновить статус
        </button>
        {status?.selected_allowed && (
          <button
            disabled={busy}
            aria-label={`Предпросмотр медиа ${candidateId}`}
            onClick={() => void preview()}
          >
            Предпросмотр
          </button>
        )}
      </div>
      {previewUrl && (
        <img
          className="media-preview"
          src={previewUrl}
          alt={
            status?.illustration
              ? "Выбранная иллюстрация: соответствие событию не подтверждено"
              : "Исходное фото донора"
          }
        />
      )}
      {error && <Notice>{error}</Notice>}
    </section>
  );
}
