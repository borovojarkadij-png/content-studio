import { StrictMode } from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const account = {
  id: 1,
  name: "Настоящий ответ API",
  telegram_user_id: 2002,
  health_status: "DISCONNECTED",
  session_provisioned: false,
};
const donor = {
  id: 1,
  telegram_account_id: 1,
  telegram_channel_id: -1001234567890,
  title: "Донор API",
};
const output = { ...donor, id: 2, title: "Мой канал API" };
const route = {
  id: 3,
  donor_channel_id: 1,
  output_channel_id: 2,
  intake_percent: 100,
  target_mix_percent: 50,
  eligibility_mode: "IMMEDIATE",
  delay_minutes: 0,
  priority: 2,
  media_policy: "REUSE_SOURCE",
};
const filter = {
  mapping_id: 3,
  allowed_media_types: ["text", "photo"],
  blocked_domains: [],
  ad_markers: [],
  effective_ad_markers: ["реклама"],
};
const json = (value: unknown) => ({ ok: true, json: async () => value });
const navigate = (name: string) =>
  fireEvent.click(
    within(
      screen.getByRole("navigation", { name: "Основная навигация" }),
    ).getByRole("button", { name }),
  );
function fixture(handler?: (path: string, init?: RequestInit) => unknown) {
  return vi.fn(async (path: string, init?: RequestInit) => {
    const override = handler?.(path, init);
    if (override !== undefined) return override;
    if (path.endsWith("technical-filters")) return json(filter);
    if (path.endsWith("source-media-rights"))
      return json({
        mapping_id: 3,
        license_code: "UNDECLARED",
        attribution: "",
        revision: 0,
      });
    if (path.endsWith("accounts")) return json({ items: [account] });
    if (path.endsWith("donors")) return json({ items: [donor] });
    if (path.endsWith("output-channels")) return json({ items: [output] });
    if (path.endsWith("mappings")) return json({ items: [route] });
    if (path.endsWith("donor-imports")) return json({ items: [] });
    if (path.endsWith("sync-status"))
      return json({
        donor_id: 1,
        state: "NOT_ENFORCED",
        enforcement_enabled: false,
        source_processing_blocked: false,
        network_checked: false,
        pts: null,
        retry_at: null,
      });
    throw new Error(`Unexpected ${path}`);
  });
}
it("reads selected donor sync diagnostics without discarding a manual name draft", async () => {
  vi.stubGlobal(
    "fetch",
    fixture((path) => {
      if (path.endsWith("sync-status"))
        return json({
          donor_id: 1,
          state: "GAP_UNRESOLVED",
          enforcement_enabled: false,
          source_processing_blocked: true,
          network_checked: false,
          pts: 10,
          retry_at: null,
        });
    }),
  );
  render(
    <StrictMode>
      <App initialDemo={false} />
    </StrictMode>,
  );
  navigate("Доноры");
  expect(await screen.findByText("Разрыв истории не устранён")).toBeTruthy();
  const input = screen.getByLabelText("Название") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "Мой несохранённый draft" } });
  fireEvent.click(
    screen.getByRole("button", { name: "Обновить синхронизацию" }),
  );
  await screen.findByText("Разрыв истории не устранён");
  expect(input.value).toBe("Мой несохранённый draft");
  expect(screen.queryByText("Название сохранено в базе данных.")).toBeNull();
});
it("persists source permission explicitly, preserves failed drafts and never pretends download or send", async () => {
  let fail = true;
  const fetch = fixture((path, init) => {
    if (path.endsWith("source-media-rights") && init?.method === "PUT") {
      if (fail) return { ok: false, status: 503 };
      return json({
        mapping_id: 3,
        ...JSON.parse(String(init.body)),
        revision: 1,
      });
    }
  });
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate("Связи");
  const license = await screen.findByLabelText("Права на исходное фото");
  await waitFor(() =>
    expect((license as HTMLSelectElement).disabled).toBe(false),
  );
  expect((license as HTMLSelectElement).value).toBe("UNDECLARED");
  fireEvent.change(license, { target: { value: "PERMISSION" } });
  fireEvent.change(screen.getByLabelText("Основание / авторство"), {
    target: { value: "Разрешение автора" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: /^Сохранить права на фото$/ }),
  );
  expect(await screen.findByText(/Не удалось сохранить права/)).toBeTruthy();
  expect(
    (screen.getByLabelText("Основание / авторство") as HTMLTextAreaElement)
      .value,
  ).toBe("Разрешение автора");
  expect(screen.queryByText("Права сохранены в базе данных.")).toBeNull();
  fail = false;
  fireEvent.click(
    screen.getByRole("button", { name: /^Сохранить права на фото$/ }),
  );
  expect(
    await screen.findByText("Права сохранены в базе данных."),
  ).toBeTruthy();
  expect(
    fetch.mock.calls.filter(([, init]) => init?.method).map(([path]) => path),
  ).toEqual([
    "/api/telegram/mappings/3/source-media-rights",
    "/api/telegram/mappings/3/source-media-rights",
  ]);
});
it("loads real account health without claiming authorization or creating demo rows", async () => {
  const fetch = fixture();
  vi.stubGlobal("fetch", fetch);
  render(
    <StrictMode>
      <App initialDemo={false} />
    </StrictMode>,
  );
  navigate("Аккаунты");
  expect(await screen.findByText(account.name)).toBeTruthy();
  expect(screen.getByText("Сессия не подключена")).toBeTruthy();
  expect(fetch.mock.calls.every(([, init]) => !init?.method)).toBe(true);
  expect(screen.queryByText("Наука и факты")).toBeNull();
});
it("bulk imports into durable pending resolution and never claims Telegram connection", async () => {
  const fetch = fixture((path) =>
    path.endsWith("donors:bulk-import")
      ? json({
          status: "PENDING_RESOLUTION",
          accepted: ["@new_donor"],
          duplicates: [],
          rejected: [],
        })
      : undefined,
  );
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate("Доноры");
  await screen.findByText(donor.title);
  fireEvent.change(screen.getByLabelText("Список доноров"), {
    target: { value: "https://t.me/new_donor" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Импортировать доноров" }),
  );
  expect(await screen.findByText(/В очередь разрешения: 1/)).toBeTruthy();
  const write = fetch.mock.calls.find(([path]) =>
    path.endsWith("donors:bulk-import"),
  );
  expect(JSON.parse(String(write?.[1]?.body))).toEqual({
    telegram_account_id: 1,
    raw_text: "https://t.me/new_donor",
  });
  expect(
    fetch.mock.calls.some(([path]) => /publish|rewrite|login/.test(path)),
  ).toBe(false);
});
it("persists mapping delivery settings only from authoritative API response", async () => {
  const fetch = fixture((path, init) =>
    path.endsWith("mappings/3") && init?.method === "PATCH"
      ? json({ ...route, ...JSON.parse(String(init.body)) })
      : undefined,
  );
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate("Связи");
  const mode = await screen.findByLabelText("Допуск к планированию");
  fireEvent.change(mode, { target: { value: "DELAYED" } });
  fireEvent.change(screen.getByLabelText("Задержка, минут"), {
    target: { value: "45" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить маршрут" }));
  expect(
    await screen.findByText("Маршрут сохранён в базе данных."),
  ).toBeTruthy();
  const write = fetch.mock.calls.find(([, init]) => init?.method === "PATCH");
  expect(JSON.parse(String(write?.[1]?.body))).toEqual({
    intake_percent: 100,
    target_mix_percent: 50,
    eligibility_mode: "DELAYED",
    delay_minutes: 45,
    priority: 2,
    media_policy: "REUSE_SOURCE",
  });
});
it("keeps failed filter edits and manual dirty state across section navigation", async () => {
  const fetch = fixture((path, init) =>
    path.endsWith("technical-filters") && init?.method === "PUT"
      ? { ok: false, status: 503 }
      : undefined,
  );
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate("Связи");
  const domains = await screen.findByLabelText("Запрещённые домены");
  fireEvent.change(domains, { target: { value: "example.org" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить фильтры" }));
  expect(await screen.findByText(/Не удалось сохранить фильтры/)).toBeTruthy();
  expect((domains as HTMLTextAreaElement).value).toBe("example.org");
  expect(screen.queryByText("Фильтры сохранены в базе данных.")).toBeNull();
  navigate("Обзор");
  navigate("Связи");
  expect(
    (screen.getByLabelText("Запрещённые домены") as HTMLTextAreaElement).value,
  ).toBe("example.org");
});
it("loads and saves filters without exposing editorial overrides or disabling builtin advertising checks", async () => {
  const fetch = fixture((path, init) =>
    path.endsWith("technical-filters") && init?.method === "PUT"
      ? json({
          ...filter,
          ...JSON.parse(String(init.body)),
          effective_ad_markers: ["реклама", "buy now"],
        })
      : undefined,
  );
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate("Связи");
  await screen.findByLabelText("Запрещённые домены");
  fireEvent.change(screen.getByLabelText("Дополнительные рекламные маркеры"), {
    target: { value: "buy now" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить фильтры" }));
  expect(
    await screen.findByText("Фильтры сохранены в базе данных."),
  ).toBeTruthy();
  const write = fetch.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(String(write?.[1]?.body))).toEqual({
    allowed_media_types: ["text", "photo"],
    blocked_domains: [],
    ad_markers: ["buy now"],
  });
  expect(screen.queryByLabelText("rewrite_allowed")).toBeNull();
});
it("blocks mapping selection while dirty and does not overwrite edits with refresh", async () => {
  vi.stubGlobal("fetch", fixture());
  render(<App initialDemo={false} />);
  navigate("Связи");
  const intake = await screen.findByLabelText("Доля входящих материалов, %");
  fireEvent.change(intake, { target: { value: "25" } });
  await waitFor(() =>
    expect(
      (screen.getByLabelText("Маршрут") as HTMLSelectElement).disabled,
    ).toBe(true),
  );
  expect(
    (
      screen.getByRole("button", {
        name: "Обновить связи",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  fireEvent.click(
    screen.getByRole("button", { name: "Отменить правки маршрута" }),
  );
  expect((intake as HTMLInputElement).value).toBe("100");
});
it("does not let account configuration masquerade as a Telegram login", async () => {
  const fetch = fixture((path, init) =>
    path.endsWith("accounts") && init?.method === "POST"
      ? json({
          ...account,
          id: 2,
          name: "Новый аккаунт",
          telegram_user_id: 3003,
        })
      : undefined,
  );
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate("Аккаунты");
  await screen.findByText(account.name);
  fireEvent.change(screen.getByLabelText("Название новой записи"), {
    target: { value: "Новый аккаунт" },
  });
  fireEvent.change(screen.getByLabelText("Telegram User ID"), {
    target: { value: "3003" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Создать запись аккаунта" }),
  );
  expect(
    await screen.findByText(
      "Запись сохранена. Telegram-подключение и права не проверены.",
    ),
  ).toBeTruthy();
  expect(screen.getByText("Сессия не подключена")).toBeTruthy();
  const write = fetch.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(write?.[1]?.body))).toEqual({
    name: "Новый аккаунт",
    telegram_user_id: 3003,
  });
});
it("rejects unsafe numeric output identity locally and never submits a rounded Telegram ID", async () => {
  const fetch = fixture();
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate("Мои каналы");
  await screen.findByText(output.title);
  fireEvent.change(screen.getByLabelText("Название новой записи"), {
    target: { value: "Канал" },
  });
  fireEvent.change(screen.getByLabelText("Telegram Channel ID"), {
    target: { value: "-10099999999999999" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Создать запись канала" }),
  );
  expect(await screen.findByText(/точный безопасный Telegram ID/)).toBeTruthy();
  expect(fetch.mock.calls.every(([, init]) => !init?.method)).toBe(true);
});
it("reports committed import separately when the follow-up queue read fails", async () => {
  let committed = false;
  vi.stubGlobal(
    "fetch",
    fixture((path) => {
      if (path.endsWith("donors:bulk-import")) {
        committed = true;
        return json({
          status: "PENDING_RESOLUTION",
          accepted: ["@donor"],
          duplicates: [],
          rejected: [],
        });
      }
      if (committed && path.endsWith("donor-imports"))
        return { ok: false, status: 503 };
      return undefined;
    }),
  );
  render(<App initialDemo={false} />);
  navigate("Доноры");
  await screen.findByText(donor.title);
  fireEvent.change(screen.getByLabelText("Список доноров"), {
    target: { value: "@donor" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Импортировать доноров" }),
  );
  expect(
    await screen.findByText(/Импорт сохранён, но очередь не обновлена/),
  ).toBeTruthy();
  expect(screen.getByText(/В очередь разрешения: 1/)).toBeTruthy();
  expect(screen.queryByText(/Не удалось импортировать доноров/)).toBeNull();
});
it("does not populate editable default filters when their actual API read fails", async () => {
  vi.stubGlobal(
    "fetch",
    fixture((path) =>
      path.endsWith("technical-filters")
        ? { ok: false, status: 503 }
        : undefined,
    ),
  );
  render(<App initialDemo={false} />);
  navigate("Связи");
  expect(await screen.findByText(/Не удалось загрузить фильтры/)).toBeTruthy();
  expect(
    screen.queryByRole("button", { name: "Сохранить фильтры" }),
  ).toBeNull();
  expect(
    screen.getByRole("button", { name: "Повторить загрузку фильтров" }),
  ).toBeTruthy();
});
it("late filter response after leaving real mode cannot overwrite DEMO or claim success", async () => {
  let resolve: ((value: unknown) => void) | undefined;
  let signal: AbortSignal | undefined;
  const fetch = fixture((path, init) => {
    if (path.endsWith("technical-filters") && init?.method === "PUT") {
      signal = init.signal as AbortSignal;
      return new Promise((done) => {
        resolve = done;
      });
    }
    return undefined;
  });
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate("Связи");
  fireEvent.change(await screen.findByLabelText("Запрещённые домены"), {
    target: { value: "example.org" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить фильтры" }));
  await waitFor(() => expect(resolve).toBeDefined());
  fireEvent.click(screen.getByRole("switch", { name: "DEMO" }));
  fireEvent.click(
    screen.getByRole("button", { name: "Переключить и сбросить" }),
  );
  expect(signal?.aborted).toBe(true);
  resolve?.(json({ ...filter, blocked_domains: ["example.org"] }));
  await waitFor(() =>
    expect(screen.getByText("Демо-данные — без публикации")).toBeTruthy(),
  );
  expect(screen.queryByText("Фильтры сохранены в базе данных.")).toBeNull();
  expect(screen.queryByDisplayValue("example.org")).toBeNull();
});
