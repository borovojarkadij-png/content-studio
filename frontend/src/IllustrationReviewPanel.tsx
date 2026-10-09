import { useEffect, useRef, useState } from "react";
import { Notice } from "./ui";
import {
  readPresentation,
  readReviewPhoto,
  readLatestReview,
  writeReview,
  revokeReview,
  validNote,
  ReviewApiError,
  type Presentation,
  type ReviewRecord,
  type ReviewOperation,
  type RevocationOperation,
  type Verdict,
} from "./illustrationReviewApi";

type Pending =
  | { kind: "review"; body: ReviewOperation }
  | { kind: "revoke"; body: RevocationOperation; review: ReviewRecord };
const uncertainty =
  "Результат записи неизвестен. Отмена запроса не отменяет возможную запись на сервере. Прочитайте последнюю проверку или явно повторите ту же операцию.";
const verdicts = {
  APPROVED_ILLUSTRATION: "Иллюстрация одобрена",
  REJECTED: "Иллюстрация отклонена",
  UNCERTAIN: "Соответствие не подтверждено",
};

export function IllustrationReviewPanel({
  candidateId,
  onSaved,
}: {
  candidateId: number;
  onSaved: () => Promise<void>;
}) {
  const [token, setToken] = useState("");
  const [context, setContext] = useState<Presentation | null>(null);
  const [latest, setLatest] = useState<ReviewRecord | null>(null);
  const [photo, setPhoto] = useState("");
  const [photoLoaded, setPhotoLoaded] = useState(false);
  const [note, setNote] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const inflight = useRef<AbortController | null>(null);
  const writing = useRef(false);
  const generation = useRef(0);
  const objectUrl = useRef("");
  function clearContext() {
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = "";
    setPhoto("");
    setPhotoLoaded(false);
    setContext(null);
    setAcknowledged(false);
  }
  function disconnect(clearToken = true) {
    const wasWriting = writing.current;
    generation.current++;
    inflight.current?.abort();
    inflight.current = null;
    writing.current = false;
    clearContext();
    setLatest(null);
    setPending(null);
    setNote("");
    setBusy(false);
    setMessage(wasWriting ? uncertainty : "");
    if (clearToken) setToken("");
  }
  useEffect(() => {
    disconnect();
    return () => {
      generation.current++;
      inflight.current?.abort();
      inflight.current = null;
      writing.current = false;
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = "";
    };
  }, [candidateId]);
  const validToken = /^[A-Za-z0-9_-]{32,128}$/.test(token);
  const ready =
    !!context &&
    !!photo &&
    photoLoaded &&
    validToken &&
    validNote(note) &&
    !busy &&
    !pending;
  function begin() {
    if (inflight.current) return null;
    const controller = new AbortController();
    inflight.current = controller;
    setBusy(true);
    const epoch = generation.current;
    return {
      controller,
      current: () =>
        !controller.signal.aborted &&
        generation.current === epoch &&
        inflight.current === controller,
    };
  }
  async function load(latestOnly = false) {
    if (!validToken || (!latestOnly && pending)) return;
    const request = begin();
    if (!request) return;
    const { controller, current } = request;
    setMessage("");
    if (!latestOnly) {
      clearContext();
      setLatest(null);
    }
    try {
      if (latestOnly) {
        const value = await readLatestReview(
          candidateId,
          token,
          controller.signal,
        );
        if (current()) {
          setLatest(value);
          setMessage(
            value
              ? "Последняя проверка прочитана; её статус не подтверждает текущую готовность к публикации."
              : "Сохранённых проверок нет.",
          );
        }
      } else {
        const value = await readPresentation(
          candidateId,
          token,
          controller.signal,
        );
        const blob = await readReviewPhoto(
          candidateId,
          token,
          value,
          controller.signal,
        );
        if (current()) {
          objectUrl.current = URL.createObjectURL(blob);
          setPhoto(objectUrl.current);
          setContext(value);
          setLatest(value.latest_review);
        }
      }
    } catch (cause) {
      if (current()) {
        clearContext();
        if (cause instanceof ReviewApiError && cause.status === 401)
          setLatest(null);
        setMessage(
          cause instanceof ReviewApiError
            ? cause.message
            : "Сеть недоступна; чтение не подтверждено",
        );
      }
    } finally {
      if (current()) {
        inflight.current = null;
        setBusy(false);
      }
    }
  }
  async function submit(operation: Pending) {
    const request = begin();
    if (!request) return;
    const { controller, current } = request;
    writing.current = true;
    setMessage("");
    // Retain the exact payload, including operation key, until authoritative success.
    setPending(operation);
    let confirmed = false;
    try {
      if (operation.kind === "review")
        await writeReview(
          candidateId,
          token,
          operation.body,
          controller.signal,
        );
      else
        await revokeReview(
          candidateId,
          token,
          operation.review,
          operation.body,
          controller.signal,
        );
      if (!current()) return;
      confirmed = true;
      setPending(null);
      clearContext();
      const savedMessage =
        operation.kind === "review"
          ? "Проверка сохранена. Это не подтверждение публикации."
          : "Отзыв сохранён. Публикация не выполнялась.";
      setMessage(savedMessage);
      const value = await readLatestReview(
        candidateId,
        token,
        controller.signal,
      );
      if (!current()) return;
      setLatest(value);
      await onSaved();
      if (current()) setMessage(savedMessage);
    } catch (cause) {
      if (!current()) return;
      if (confirmed) {
        setLatest(null);
        setMessage(
          "Запись подтверждена сервером, но обновить проверку или статус медиа не удалось. Прочитайте последнюю проверку заново.",
        );
      } else if (
        cause instanceof ReviewApiError &&
        cause.status > 0 &&
        cause.status < 500
      ) {
        setPending(null);
        clearContext();
        if (cause.status === 401) setLatest(null);
        setMessage(cause.message);
      } else {
        clearContext();
        setMessage(uncertainty);
      }
    } finally {
      if (current()) {
        inflight.current = null;
        writing.current = false;
        setBusy(false);
      }
    }
  }
  function review(verdict: Verdict) {
    if (
      !ready ||
      !context ||
      (verdict === "APPROVED_ILLUSTRATION" && !acknowledged)
    )
      return;
    void submit({
      kind: "review",
      body: {
        operation_key: crypto.randomUUID(),
        displayed_binding: { ...context.binding },
        verdict,
        illustration_acknowledged: acknowledged,
        review_note: note,
      },
    });
  }
  function revoke() {
    if (
      busy ||
      pending ||
      !validToken ||
      !latest ||
      latest.revoked ||
      !validNote(note)
    )
      return;
    void submit({
      kind: "revoke",
      review: latest,
      body: { operation_key: crypto.randomUUID(), review_note: note },
    });
  }
  return (
    <section
      className="media-preparation"
      aria-label={`Проверка иллюстрации ${candidateId}`}
    >
      <b>Проверка иллюстрации редактором</b>
      <p className="help-copy">
        Отдельно выданный токен хранится только в памяти этой панели. Серверная
        проверка должна быть настроена отдельно. Просмотр и выбор фото не
        означают одобрение.
      </p>
      <label className="field">
        Токен редактора
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          maxLength={128}
          value={token}
          onChange={(event) => {
            disconnect(false);
            setToken(event.target.value);
          }}
        />
      </label>
      <div className="action-row">
        <button
          disabled={busy || !validToken || !!pending}
          onClick={() => void load()}
        >
          Загрузить контекст проверки
        </button>
        <button disabled={busy || !validToken} onClick={() => void load(true)}>
          Прочитать последнюю проверку
        </button>
        <button onClick={() => disconnect()}>Отключить проверку</button>
      </div>
      {busy && <p role="status">Проверка: запрос выполняется…</p>}
      {context && (
        <>
          <p>
            Канал #{context.channel.id}: {context.channel.title} ·{" "}
            {context.channel.telegram_channel_id}
          </p>
          <b>Текущий исходный текст</b>
          <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {context.source_text}
          </p>
          <b>Одобренный вариант для канала</b>
          <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {context.draft_text}
          </p>
          <p>
            Лицензия: {context.license_code} · Авторство:{" "}
            {context.attribution || "Не требуется по CC0"}
          </p>
          <details>
            <summary>Точная привязка проверки</summary>
            <dl>
              {Object.entries(context.binding).map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd style={{ overflowWrap: "anywhere" }}>{value}</dd>
                </div>
              ))}
            </dl>
          </details>
        </>
      )}
      {photo && (
        <img
          className="media-preview"
          src={photo}
          alt="Проверяемая иллюстрация, не фото события"
          onLoad={() => setPhotoLoaded(true)}
          onError={() => {
            clearContext();
            setMessage("Фото не удалось отобразить; загрузите контекст заново");
          }}
        />
      )}
      {latest && (
        <p>
          Проверка #{latest.id} · {verdicts[latest.verdict as Verdict]} ·
          редактор #{latest.reviewer_id} · {latest.reviewed_at} ·{" "}
          {latest.revoked ? "Отозвана" : "Не отозвана"}. Это сохранённая
          история, актуальность привязки проверяется отдельно. Комментарий:{" "}
          {latest.review_note}
        </p>
      )}
      <label className="field">
        Комментарий проверки
        <textarea
          value={note}
          maxLength={2048}
          disabled={busy || !!pending}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      <p className="help-copy">
        Нужен непустой комментарий до 2048 символов. Отклонение и «не уверен» не
        разрешают использование иллюстрации.
      </p>
      <label>
        <input
          type="checkbox"
          checked={acknowledged}
          disabled={!context || busy || !!pending}
          onChange={(event) => setAcknowledged(event.target.checked)}
        />
        Это иллюстрация, а не фотография события; соответствие источнику и
        варианту проверено
      </label>
      <div className="action-row">
        <button
          disabled={!ready || !acknowledged}
          onClick={() => review("APPROVED_ILLUSTRATION")}
        >
          Одобрить иллюстрацию
        </button>
        <button disabled={!ready} onClick={() => review("REJECTED")}>
          Отклонить иллюстрацию
        </button>
        <button disabled={!ready} onClick={() => review("UNCERTAIN")}>
          Не уверен
        </button>
        <button
          disabled={
            busy ||
            !!pending ||
            !validToken ||
            !latest ||
            latest.revoked ||
            !validNote(note)
          }
          onClick={revoke}
        >
          Отозвать последнюю проверку
        </button>
        {pending && (
          <button
            disabled={busy || !validToken}
            onClick={() => void submit(pending)}
          >
            Повторить ту же операцию
          </button>
        )}
      </div>
      <p className="help-copy">
        Отключение, смена материала или токена отменяют ожидание ответа, но не
        возможную запись на сервере. После прерывания прочитайте последнюю
        проверку с действующим токеном.
      </p>
      {message && <Notice>{message}</Notice>}
    </section>
  );
}
