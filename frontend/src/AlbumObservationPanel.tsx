import { useEffect, useRef, useState } from "react";
import {
  loadAlbumObservation,
  type AlbumObservation,
} from "./albumObservationApi";
import { Notice, PanelTitle } from "./ui";

export function AlbumObservationPanel({ contentKey }: { contentKey: string }) {
  return <AlbumObservationRead key={contentKey} contentKey={contentKey} />;
}
function AlbumObservationRead({ contentKey }: { contentKey: string }) {
  const controller = useRef<AbortController | null>(null);
  const busy = useRef(false);
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [value, setValue] = useState<AlbumObservation | null>(null);
  const [error, setError] = useState("");
  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [],
  );
  const read = async () => {
    if (busy.current) return;
    const request = new AbortController();
    controller.current = request;
    busy.current = true;
    setStarted(true);
    setLoading(true);
    setValue(null);
    setError("");
    try {
      const observation = await loadAlbumObservation(
        contentKey,
        request.signal,
      );
      if (!request.signal.aborted) setValue(observation);
    } catch (cause) {
      if (!request.signal.aborted) {
        // Transport errors can contain untrusted URLs/bodies. Only our fixed contract/status errors are shown.
        const message = cause instanceof Error ? cause.message : "";
        setError(
          /^(?:API вернул HTTP \d{3}|Некорректная ревизия|Некорректный ответ наблюдения альбома)$/.test(
            message,
          )
            ? message
            : "Не удалось прочитать наблюдение альбома. Проверьте доступность API.",
        );
      }
    } finally {
      if (!request.signal.aborted) {
        busy.current = false;
        setLoading(false);
      }
    }
  };
  return (
    <section
      className="detail-section"
      aria-label="Наблюдение альбома"
      aria-busy={loading}
    >
      <PanelTitle title="Элементы альбома" icon="inbox" />
      <p className="notice error" role="status">
        Состав альбома не подтверждён. Рерайт и публикация запрещены. Это
        наблюдаемые сообщения, не полный альбом.
      </p>
      <p className="help-copy">
        Только сохранённые метаданные и подписи. Чтение не скачивает файлы и не
        вызывает Telegram или AI.
      </p>
      <button
        className="small-button"
        disabled={loading}
        onClick={() => void read()}
      >
        {started ? "Обновить элементы альбома" : "Посмотреть элементы альбома"}
      </button>
      {loading && <p role="status">Чтение элементов альбома…</p>}
      {error && <Notice error>{error}</Notice>}
      {value && (
        <>
          <p className="help-copy">
            Наблюдаемых элементов: {value.members.length}. Полнота состава
            неизвестна.
          </p>
          {value.source_sync_blocked && (
            <Notice>
              Нужна синхронизация источника. Эти данные не подтверждают
              актуальность Telegram.
            </Notice>
          )}
          <ol aria-label="Наблюдаемые сообщения альбома">
            {value.members.map((member) => (
              <li key={member.content_key}>
                <p className="help-copy">
                  {
                    {
                      photo: "Фото",
                      video: "Видео",
                      unsupported: "Неподдерживаемое медиа",
                      unknown: "Тип медиа неизвестен",
                    }[member.media_type]
                  }{" "}
                  · сообщение {member.message_id} · ревизия{" "}
                  {member.revision_number}
                </p>
                <p className="help-copy">
                  {member.media_protected === null
                    ? "Защита неизвестна"
                    : member.media_protected
                      ? "Защищён от копирования"
                      : "Защита от копирования не наблюдалась; права использования не подтверждены"}
                  {member.source_deleted &&
                    " · Удалён у донора; сохранена историческая подпись"}
                </p>
                <p>{member.text || "Без подписи"}</p>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
