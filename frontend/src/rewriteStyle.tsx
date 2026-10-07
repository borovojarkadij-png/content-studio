import { useEffect, useRef, useState } from "react";
import { channelRewriteStyle, type RewriteStyle } from "./plannerApi";
import { Notice, Panel, PanelTitle } from "./ui";

export function RewriteStylePanel({ channelId }: { channelId: number }) {
  const [style, setStyle] = useState<RewriteStyle | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const mutations = useRef(new AbortController());
  useEffect(() => {
    const read = new AbortController();
    setStyle(null);
    setError("");
    void channelRewriteStyle(channelId, read.signal)
      .then((value) => {
        if (!read.signal.aborted) setStyle(value);
      })
      .catch(() => {
        if (!read.signal.aborted)
          setError("Не удалось загрузить стиль рерайта.");
      });
    return () => read.abort();
  }, [channelId, reload]);
  useEffect(() => {
    const controller = new AbortController();
    mutations.current = controller;
    return () => controller.abort();
  }, []);
  const save = async (selected: RewriteStyle) => {
    const controller = mutations.current;
    if (busy || style === null || controller.signal.aborted) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const value = await channelRewriteStyle(
        channelId,
        controller.signal,
        selected,
      );
      if (!controller.signal.aborted) {
        setStyle(value);
        setNotice("Стиль сохранён. Применится к следующим рерайтам.");
      }
    } catch {
      if (!controller.signal.aborted)
        setError("Не удалось сохранить стиль. Выбор не изменён.");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  return (
    <Panel>
      <PanelTitle title="Подача рерайта" icon="settings" />
      <p className="help-copy">
        Настройка для этого канала. Живая, цепкая подача естественными словами —
        без выдуманных сенсаций, подмены фактов и обхода редакционных запретов.
        Существующие черновики не меняются.
      </p>
      <div className="action-row" role="group" aria-label="Стиль рерайта">
        <button
          className={style === "NEUTRAL" ? "primary-button" : ""}
          aria-pressed={style === "NEUTRAL"}
          disabled={busy || style === null}
          onClick={() => void save("NEUTRAL")}
        >
          Обычный стиль
        </button>
        <button
          className={style === "TABLOID" ? "primary-button" : ""}
          aria-pressed={style === "TABLOID"}
          disabled={busy || style === null}
          onClick={() => void save("TABLOID")}
        >
          В стиле жёлтой прессы
        </button>
      </div>
      {error && (
        <>
          <Notice>{error}</Notice>
          {style === null && (
            <button onClick={() => setReload((value) => value + 1)}>
              Повторить загрузку стиля
            </button>
          )}
        </>
      )}
      {notice && <Notice>{notice}</Notice>}
      {!error && style === null && <p role="status">Загрузка стиля…</p>}
    </Panel>
  );
}
