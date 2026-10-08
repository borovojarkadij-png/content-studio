import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LiveOverview } from "./LiveOverview";
import { App } from "./App";
import { loadStudioOverview } from "./overviewApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const usage = {
  operation: "REWRITE",
  records: 1,
  input_tokens: 100,
  cached_tokens: 40,
  output_tokens: 20,
  known_estimated_cost_usd: "0.0000000000",
  unknown_cost_records: 1,
  durable_attempts: 2,
  unobserved_attempts: 1,
};
const overview = {
  scope: "ALL_RETAINED_HISTORY",
  generated_at: "2030-01-01T00:00:00+00:00",
  network_checked: false,
  billing_complete: false,
  configuration: { accounts: 1, donors: 2, output_channels: 3, mappings: 4 },
  history: {
    source_posts: 5,
    source_revisions: 6,
    rewrite_jobs: 7,
    active_rewrite_jobs: 2,
    acknowledged_publications: 1,
    uncertain_publications: 1,
  },
  usage: [usage, { ...usage, operation: "SEMANTIC_VERIFICATION" }],
};
const json = (value: unknown) => ({ ok: true, json: async () => value });

it("working-mode Overview uses the actual API instead of an unavailable or DEMO dashboard", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      path.endsWith("/overview") ? json(overview) : json({ items: [] }),
    ),
  );
  render(<App initialDemo={false} />);
  fireEvent.click(screen.getByRole("button", { name: /^Обзор$/ }));
  expect(await screen.findByText("История источников")).toBeTruthy();
  expect(screen.queryByText("Метрики пока недоступны")).toBeNull();
});

it.each([
  { billing_complete: true },
  { network_checked: true },
  { scope: "TODAY" },
  { configuration: { ...overview.configuration, donors: -1 } },
  { history: { ...overview.history, active_rewrite_jobs: 8 } },
  { usage: [usage, usage] },
  { usage: [{ ...usage, cached_tokens: 101 }, overview.usage[1]] },
  { usage: [{ ...usage, unknown_cost_records: 2 }, overview.usage[1]] },
  { usage: [{ ...usage, known_estimated_cost_usd: null }, overview.usage[1]] },
  { generated_at: "2030-01-01" },
  { encrypted_session: "private" },
])("fails closed on unsafe aggregate payload %j", async (change) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ...overview, ...change })),
  );
  await expect(
    loadStudioOverview(new AbortController().signal),
  ).rejects.toThrow();
});

it("shows real historical counts and unknown charges without DEMO or live health claims", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json(overview)),
  );
  render(<LiveOverview />);
  expect(await screen.findByText("История источников")).toBeTruthy();
  expect(screen.getByText(/Стоимость части обращений неизвестна/)).toBeTruthy();
  expect(
    screen.getAllByText("Оценка известной части: 0.0000000000 USD (не счёт)"),
  ).toHaveLength(2);
  expect(screen.getByText(/Нет live-проверки Telegram/)).toBeTruthy();
  expect(screen.queryByText(/DEMO/)).toBeNull();
  expect(screen.queryByText(/Расходы: \$0/)).toBeNull();
});

it("clears old metrics on failed refresh and recovers only with a new validated response", async () => {
  let fail = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => (fail ? { ok: false, status: 503 } : json(overview))),
  );
  render(<LiveOverview />);
  await screen.findByText("История источников");
  fail = true;
  fireEvent.click(screen.getByRole("button", { name: "Обновить обзор" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("HTTP 503"),
  );
  expect(screen.queryByText("История источников")).toBeNull();
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Обновить обзор" }));
  expect(await screen.findByText("История источников")).toBeTruthy();
});

it("ignores late dashboard response after unmount", async () => {
  let resolve: (value: unknown) => void = () => {};
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_path: string, init: RequestInit) => {
      signal = init.signal as AbortSignal;
      return new Promise((done) => {
        resolve = done;
      });
    }),
  );
  const { unmount } = render(<LiveOverview />);
  unmount();
  await act(async () => {
    resolve(json(overview));
  });
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText("История источников")).toBeNull();
});
