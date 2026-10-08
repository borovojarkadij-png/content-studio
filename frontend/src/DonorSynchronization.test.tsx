import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DonorSynchronization } from "./DonorSynchronization";
import { loadDonorSyncStatus } from "./donorSyncApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
const status = {
  donor_id: 1,
  state: "READY",
  enforcement_enabled: true,
  source_processing_blocked: false,
  network_checked: false,
  pts: 10,
  retry_at: null,
};
const json = (value: unknown) => ({ ok: true, json: async () => value });

it("uses the configured API base instead of silently reading a different database", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "https://synthetic-api.invalid");
  const fetch = vi.fn(async (_path: string, _init: RequestInit) =>
    json(status),
  );
  vi.stubGlobal("fetch", fetch);
  await loadDonorSyncStatus(1, new AbortController().signal);
  expect(fetch.mock.calls[0][0]).toBe(
    "https://synthetic-api.invalid/api/telegram/donors/1/sync-status",
  );
});

it.each([
  { donor_id: 2 },
  { state: "CONNECTED" },
  { network_checked: true },
  { source_processing_blocked: true },
  { enforcement_enabled: false },
  { pts: 0 },
  { pts: 2147483648 },
  { pts: null },
  { retry_at: "not-a-date" },
  { claim_token: "private-secret" },
  { source_processing_blocked: "false" },
])(
  "rejects contradictory or unsafe persisted diagnostics %j",
  async (change) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ ...status, ...change })),
    );
    await expect(
      loadDonorSyncStatus(1, new AbortController().signal),
    ).rejects.toThrow();
  },
);

it("renders persisted READY without claiming live connectivity and uses GET only", async () => {
  const fetch = vi.fn(async () => json(status));
  vi.stubGlobal("fetch", fetch);
  render(<DonorSynchronization donorId={1} />);
  expect(
    await screen.findByText(
      /Синхронизация завершена \(сохранённое состояние\)/,
    ),
  ).toBeTruthy();
  expect(
    screen.getByText(/live-проверка Telegram не выполнялась/),
  ).toBeTruthy();
  expect(screen.queryByText(/Подключено к Telegram/)).toBeNull();
  expect(fetch.mock.calls[0]).toEqual([
    "/api/telegram/donors/1/sync-status",
    expect.objectContaining({
      method: "GET",
      cache: "no-store",
      signal: expect.any(AbortSignal),
    }),
  ]);
});

it("clears prior READY on refresh failure and permits a truthful retry", async () => {
  let fail = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => (fail ? { ok: false, status: 503 } : json(status))),
  );
  render(<DonorSynchronization donorId={1} />);
  await screen.findByText(/Синхронизация завершена/);
  fail = true;
  fireEvent.click(
    screen.getByRole("button", { name: "Обновить синхронизацию" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("HTTP 503"),
  );
  expect(screen.queryByText(/Синхронизация завершена/)).toBeNull();
  fail = false;
  fireEvent.click(
    screen.getByRole("button", { name: "Обновить синхронизацию" }),
  );
  expect(await screen.findByText(/Синхронизация завершена/)).toBeTruthy();
});

it("does not display an old donor response after identity changes even if fetch ignores abort", async () => {
  let resolve: (value: unknown) => void = () => {};
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init: RequestInit) => {
      if (path.includes("/1/")) {
        signal = init.signal as AbortSignal;
        return new Promise((done) => {
          resolve = done;
        });
      }
      return Promise.resolve(
        json({
          ...status,
          donor_id: 2,
          state: "GAP_UNRESOLVED",
          source_processing_blocked: true,
        }),
      );
    }),
  );
  const { rerender } = render(<DonorSynchronization donorId={1} />);
  rerender(<DonorSynchronization donorId={2} />);
  expect(await screen.findByText("Разрыв истории не устранён")).toBeTruthy();
  await act(async () => {
    resolve(json(status));
  });
  expect(signal?.aborted).toBe(true);
  expect(screen.queryByText(/Синхронизация завершена/)).toBeNull();
  expect(screen.getByText(/Обработка источника заблокирована/)).toBeTruthy();
});

it("aborts selected-donor diagnostics on unmount", () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_path: string, init: RequestInit) => {
      signal = init.signal as AbortSignal;
      return new Promise(() => {});
    }),
  );
  const { unmount } = render(<DonorSynchronization donorId={1} />);
  unmount();
  expect(signal?.aborted).toBe(true);
});
