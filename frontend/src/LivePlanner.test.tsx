import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { StrictMode } from "react";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const channel = {
  id: 1,
  telegram_account_id: 1,
  telegram_channel_id: -1001234567890,
  title: "Рабочий канал",
};
const plan = {
  id: 7,
  output_channel_id: 1,
  mode: "AUTOMATIC",
  daily_limit: 2,
  timezone: "Europe/Minsk",
  slot_minutes: [540, 900],
};
const draft = {
  id: 5,
  rewrite_job_id: 3,
  output_channel_id: 1,
  content_key: "synthetic:revision:1",
  rewritten_text: "Рерайт для рабочего канала",
  approval_state: "PENDING",
  editorial_status: "PASS",
  approve_allowed: true,
};
const navigate = () =>
  fireEvent.click(
    within(
      screen.getByRole("navigation", {
        name: "Основная навигация",
      }),
    ).getByRole("button", { name: "Планировщик" }),
  );
const json = (value: unknown) => ({ ok: true, json: async () => value });

it("planning does not claim a configured server worker is absent or that a slot proves delivery", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      json({ items: path.endsWith("output-channels") ? [channel] : [] }),
    ),
  );
  render(<App initialDemo={false} />);
  navigate();
  await screen.findByText(/Доставка подтверждается только в истории/);
  expect(screen.queryByText(/отправка в Telegram не подключена/)).toBeNull();
  expect(
    screen.queryByRole("button", {
      name: /Отправить сейчас|Повторить отправку/,
    }),
  ).toBeNull();
});

it("persists tabloid style only after successful API response and never generates or publishes", async () => {
  let style = "NEUTRAL";
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    if (path.endsWith("output-channels")) return json({ items: [channel] });
    if (path.endsWith("publication-plans")) return json({ items: [plan] });
    if (path.endsWith("rewrite-style")) {
      if (init?.method === "PUT") style = JSON.parse(String(init.body)).style;
      return json({ output_channel_id: 1, style });
    }
    return json({ items: [] });
  });
  vi.stubGlobal("fetch", fetch);
  render(
    <StrictMode>
      <App initialDemo={false} />
    </StrictMode>,
  );
  navigate();
  const button = await screen.findByRole("button", {
    name: "В стиле жёлтой прессы",
  });
  await waitFor(() =>
    expect((button as HTMLButtonElement).disabled).toBe(false),
  );
  fireEvent.click(button);
  expect(
    await screen.findByText("Стиль сохранён. Применится к следующим рерайтам."),
  ).toBeTruthy();
  expect(button.getAttribute("aria-pressed")).toBe("true");
  const write = fetch.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(String(write?.[1]?.body))).toEqual({ style: "TABLOID" });
  expect(
    fetch.mock.calls.some(([path]) => /openai|publish-now/.test(path)),
  ).toBe(false);
});

it("does not claim saved style or change selection after a failed write", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path.endsWith("output-channels")) return json({ items: [channel] });
      if (path.endsWith("publication-plans")) return json({ items: [plan] });
      if (path.endsWith("rewrite-style"))
        return init?.method === "PUT"
          ? { ok: false, status: 503 }
          : json({ output_channel_id: 1, style: "NEUTRAL" });
      return json({ items: [] });
    }),
  );
  render(<App initialDemo={false} />);
  navigate();
  const button = await screen.findByRole("button", {
    name: "В стиле жёлтой прессы",
  });
  await waitFor(() =>
    expect((button as HTMLButtonElement).disabled).toBe(false),
  );
  fireEvent.click(button);
  expect(
    await screen.findByText("Не удалось сохранить стиль. Выбор не изменён."),
  ).toBeTruthy();
  expect(button.getAttribute("aria-pressed")).toBe("false");
  expect(
    screen.queryByText("Стиль сохранён. Применится к следующим рерайтам."),
  ).toBeNull();
});

it("loads persisted planner state, explicitly saves configuration and reserves without publishing", async () => {
  let planned = false;
  let approved = false;
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    if (path.endsWith("output-channels")) return json({ items: [channel] });
    if (path.endsWith("publication-plans")) return json({ items: [plan] });
    if (path.includes("rewrite-outputs?"))
      return json({
        items: [
          { ...draft, approval_state: approved ? "APPROVED" : "PENDING" },
        ],
      });
    if (path.endsWith(":approve")) {
      approved = true;
      return json({ ...draft, approval_state: "APPROVED" });
    }
    if (path.endsWith("publication-plan")) {
      return json({ ...plan, ...JSON.parse(String(init?.body)) });
    }
    if (path.endsWith(":plan-day")) {
      planned = true;
      return json({ items: [] });
    }
    if (path.includes("/publications?"))
      return json({
        items: planned
          ? [
              {
                id: 8,
                candidate_id: 4,
                output_channel_id: 1,
                content_key: draft.content_key,
                scheduled_for: "2030-01-02T06:00:00+00:00",
                state: "PLANNED",
                editorial_allowed: true,
              },
            ]
          : [],
      });
    throw new Error(`Unexpected API path ${path}`);
  });
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo={false} />);
  navigate();
  const limit = await screen.findByLabelText("Постов в день");
  expect((limit as HTMLInputElement).value).toBe("2");
  expect(
    (screen.getByLabelText("Слоты публикаций") as HTMLInputElement).value,
  ).toBe("09:00, 15:00");
  expect(
    fetch.mock.calls.every(
      ([, init]) => !init?.method || init.method === "GET",
    ),
  ).toBe(true);
  fireEvent.change(limit, { target: { value: "1" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить план" }));
  expect(await screen.findByText("План сохранён в базе данных.")).toBeTruthy();
  const saved = fetch.mock.calls.find(([path]) =>
    path.endsWith("publication-plan"),
  );
  expect(JSON.parse(String(saved?.[1]?.body))).toEqual({
    mode: "AUTOMATIC",
    daily_limit: 1,
    timezone: "Europe/Minsk",
    slot_minutes: [540, 900],
  });
  fireEvent.click(
    await screen.findByRole("button", { name: "Одобрить рерайт 5" }),
  );
  expect(
    await screen.findByText("Рерайт одобрен. Публикация не выполнена."),
  ).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Дата плана"), {
    target: { value: "2030-01-02" },
  });
  fireEvent.click(
    await screen.findByRole("button", { name: "Подобрать публикации на день" }),
  );
  expect(await screen.findByText("Слот #8")).toBeTruthy();
  expect(
    fetch.mock.calls.some(([path]) => /publish|openai|openrouter/.test(path)),
  ).toBe(false);
});

it("disables stale editorial reviews and does not fall back to demo on failure", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path.endsWith("output-channels")) return json({ items: [channel] });
      if (path.endsWith("publication-plans")) return json({ items: [plan] });
      if (path.includes("rewrite-outputs?"))
        return json({
          items: [
            { ...draft, editorial_status: "REJECT", approve_allowed: false },
          ],
        });
      return { ok: false, status: 503 };
    }),
  );
  render(<App initialDemo={false} />);
  navigate();
  expect(
    (
      (await screen.findByRole("button", {
        name: "Одобрить рерайт 5",
      })) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(await screen.findByText("API вернул HTTP 503")).toBeTruthy();
  expect(
    screen.queryByText("На Марсе обнаружены следы древних рек"),
  ).toBeNull();
});

it("retries unavailable initial state without pretending to save", async () => {
  let fail = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      fail
        ? { ok: false, status: 503 }
        : json({ items: path.endsWith("output-channels") ? [channel] : [] }),
    ),
  );
  render(<App initialDemo={false} />);
  navigate();
  expect(await screen.findByText("API вернул HTTP 503")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Сохранить план" })).toBeNull();
  fail = false;
  fireEvent.click(
    screen.getByRole("button", { name: "Повторить загрузку планировщика" }),
  );
  expect(await screen.findByLabelText("Постов в день")).toBeTruthy();
});

it("keeps demo planning isolated from the real API", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(<App initialDemo />);
  navigate();
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Сохранить план" })).toBeNull();
});

it("restores the newly saved plan after switching channels without accepting stale queue responses", async () => {
  let resolveOldReviews: (value: unknown) => void = () => {};
  let reviewReads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init?: RequestInit) => {
      if (path.endsWith("output-channels"))
        return json({
          items: [channel, { ...channel, id: 2, title: "Другой канал" }],
        });
      if (path.endsWith("publication-plans")) return json({ items: [plan] });
      if (path.endsWith("publication-plan"))
        return json({ ...plan, ...JSON.parse(String(init?.body)) });
      if (path.includes("rewrite-outputs?output_channel_id=1")) {
        reviewReads++;
        if (reviewReads === 1)
          return new Promise((resolve) => {
            resolveOldReviews = resolve;
          });
      }
      return json({ items: [] });
    }),
  );
  render(<App initialDemo={false} />);
  navigate();
  fireEvent.change(await screen.findByLabelText("Постов в день"), {
    target: { value: "1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить план" }));
  await screen.findByText("План сохранён в базе данных.");
  fireEvent.change(screen.getByLabelText("Канал плана"), {
    target: { value: "2" },
  });
  resolveOldReviews(json({ items: [draft] }));
  expect(
    await screen.findByText(/Сохранённых вариантов пока нет/),
  ).toBeTruthy();
  expect(screen.queryByText(/rewrite-worker ещё не подключён/)).toBeNull();
  expect(screen.queryByText(draft.rewritten_text)).toBeNull();
  fireEvent.change(screen.getByLabelText("Канал плана"), {
    target: { value: "1" },
  });
  expect(
    (screen.getByLabelText("Постов в день") as HTMLInputElement).value,
  ).toBe("1");
});
