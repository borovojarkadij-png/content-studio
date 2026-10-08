import { useEffect, useState } from "react";
import { loadStudioOverview, type StudioOverview } from "./overviewApi";
import { Metric, Notice, Panel, PanelTitle } from "./ui";

export function LiveOverview() {
  const [data, setData] = useState<StudioOverview | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    setError("");
    setData(null);
    void loadStudioOverview(controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : "Ошибка API");
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [reload]);
  return (
    <>
      <Panel className="overview-live-summary">
        <PanelTitle title="Сохранённые метрики" icon="overview">
          <button
            disabled={busy}
            onClick={() => {
              setData(null);
              setBusy(true);
              setError("");
              setReload((value) => value + 1);
            }}
          >
            Обновить обзор
          </button>
        </PanelTitle>
        <p className="help-copy">
          Вся сохранённая история базы, не только сегодня. Удалённые и
          устаревшие материалы сохраняются в счётчиках. Нет live-проверки
          Telegram, подписчиков или состояния внешних сервисов.
        </p>
        {busy && <p role="status">Загрузка метрик…</p>}
        {error && <Notice error>Не удалось загрузить обзор. {error}</Notice>}
        {data && (
          <p className="help-copy">
            Отчёт сформирован:{" "}
            <time dateTime={data.generated_at}>
              {new Date(data.generated_at).toLocaleString("ru-RU")}
            </time>
            . Чтение не запускает AI или публикации.
          </p>
        )}
      </Panel>
      {data && (
        <>
          <div className="metric-row">
            <Metric
              title="История источников"
              value={data.history.source_posts}
              icon="download"
              tone="blue"
              detail="Уникальные исходные сообщения, включая сохранённые удалённые"
            />
            <Metric
              title="Активные rewrite jobs"
              value={data.history.active_rewrite_jobs}
              icon="clock"
              tone="orange"
              detail="QUEUED / DISPATCHED / RUNNING / RETRY; не подтверждение вызова AI"
            />
            <Metric
              title="Подтверждённые доставки"
              value={data.history.acknowledged_publications}
              icon="check"
              tone="green"
              detail="Сохранённые SUCCEEDED intents; не live-проверка канала"
            />
            <Metric
              title="Неопределённые доставки"
              value={data.history.uncertain_publications}
              icon="shield"
              tone="violet"
              detail="NEEDS_RECONCILIATION; автоматический resend запрещён"
            />
          </div>
          <div className="overview-grid">
            <Panel>
              <PanelTitle title="Конфигурация и история" icon="donors" />
              <dl className="detail-section">
                <dt>Аккаунты</dt>
                <dd>{data.configuration.accounts}</dd>
                <dt>Доноры</dt>
                <dd>{data.configuration.donors}</dd>
                <dt>Мои каналы</dt>
                <dd>{data.configuration.output_channels}</dd>
                <dt>Связи</dt>
                <dd>{data.configuration.mappings}</dd>
                <dt>Неизменяемые версии источников</dt>
                <dd>{data.history.source_revisions}</dd>
                <dt>Все rewrite jobs (включая завершённые)</dt>
                <dd>{data.history.rewrite_jobs}</dd>
              </dl>
              <p className="help-copy">
                Это количество записей, не разрешение на обработку: workers
                повторно проверяют EditorialGate, актуальность источника и
                остальные ограничения.
              </p>
            </Panel>
            <Panel>
              <PanelTitle title="Известный AI usage" icon="chart" />
              <Notice>
                Стоимость части обращений неизвестна или не подтверждена.
                Сохранённые оценки не являются полным счётом провайдера.
              </Notice>
              {data.usage.map((item) => (
                <section
                  className="detail-section"
                  key={item.operation}
                  aria-label={
                    item.operation === "REWRITE"
                      ? "Usage рерайта"
                      : "Usage проверки фактов"
                  }
                >
                  <h3>
                    {item.operation === "REWRITE"
                      ? "Рерайт"
                      : "Semantic verification"}
                  </h3>
                  <p>
                    Наблюдений usage: {item.records}; без известной стоимости:{" "}
                    {item.unknown_cost_records}
                  </p>
                  <p>
                    Токены input / cached / output: {item.input_tokens} /{" "}
                    {item.cached_tokens} / {item.output_tokens}
                  </p>
                  <p>
                    Оценка известной части: {item.known_estimated_cost_usd} USD
                    (не счёт)
                  </p>
                  <p>
                    Сохранённых попыток: {item.durable_attempts}; без наблюдения
                    usage: {item.unobserved_attempts}
                  </p>
                </section>
              ))}
              <p className="help-copy">
                Попытка резервируется до возможного запроса и не равна числу
                provider calls. После crash расход может быть неизвестен;
                отсутствие usage не означает бесплатный вызов.
              </p>
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
