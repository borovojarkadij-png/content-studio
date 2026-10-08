import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SemanticVerificationStatus } from "./SemanticVerificationStatus";
import { loadSemanticStatus } from "./semanticStatusApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
const status = {
  rewrite_output_id: 1,
  output_channel_id: 1,
  approval_state: "PENDING",
  current_gate: "READY_SNAPSHOT",
  reason_code: null,
  network_checked: false,
  execution_authorized: false,
  worker_enabled: null,
  policy_mode: "VERIFIED",
  configured_release_id: 3,
  qualified_release: true,
  latest_job: {
    id: 8,
    state: "RUNNING",
    attempts: 1,
    max_attempts: 2,
    release_id: 3,
    binding_current: true,
    available_at: "2030-01-01T00:00:00+00:00",
    lease_expires_at: "2030-01-01T00:01:00+00:00",
    lease_expired: true,
  },
};
const json = (value: unknown) => ({ ok: true, json: async () => value });

it("opens on demand, reports persisted lease/budget without starting a model", async () => {
  const fetch = vi.fn(async (_path: string, _init: RequestInit) =>
    json(status),
  );
  vi.stubGlobal("fetch", fetch);
  render(<SemanticVerificationStatus outputId={1} channelId={1} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole("button", { name: "Проверка фактов: статус рерайта 1" }),
  );
  expect(
    await screen.findByText("Ожидается восстановление worker"),
  ).toBeTruthy();
  expect(screen.getByText(/Попытки процесса: 1 из 2/)).toBeTruthy();
  expect(screen.getByText(/не число оплаченных AI-вызовов/)).toBeTruthy();
  expect(screen.getByText(/Состояние сетевого worker неизвестно/)).toBeTruthy();
  expect(fetch.mock.calls[0]).toEqual([
    "/api/telegram/rewrite-outputs/1/semantic-status",
    expect.objectContaining({
      method: "GET",
      cache: "no-store",
      signal: expect.any(AbortSignal),
    }),
  ]);
  expect(
    screen.queryByRole("button", {
      name: /Запустить|Повторить AI|Опубликовать/,
    }),
  ).toBeNull();
});

it.each([
  { rewrite_output_id: 2 },
  { output_channel_id: 2 },
  { network_checked: true },
  { execution_authorized: true },
  { worker_enabled: true },
  { current_gate: "CONNECTED" },
  { qualified_release: false },
  { configured_release_id: null },
  { policy_mode: "MANUAL" },
  { claim_token: "private" },
  { latest_job: { ...status.latest_job, attempts: 3 } },
  { latest_job: { ...status.latest_job, max_attempts: 5 } },
  { latest_job: { ...status.latest_job, release_id: 99 } },
  { latest_job: { ...status.latest_job, lease_expires_at: null } },
  { latest_job: { ...status.latest_job, claim_token: "private" } },
])("refuses contradictory/private diagnostics %j", async (change) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ...status, ...change })),
  );
  await expect(
    loadSemanticStatus(1, 1, new AbortController().signal),
  ).rejects.toThrow();
});

it("uses configured API base and never sends write bodies", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "https://synthetic-api.invalid");
  const fetch = vi.fn(async (_path: string, _init: RequestInit) =>
    json(status),
  );
  vi.stubGlobal("fetch", fetch);
  await loadSemanticStatus(1, 1, new AbortController().signal);
  expect(fetch.mock.calls[0][0]).toBe(
    "https://synthetic-api.invalid/api/telegram/rewrite-outputs/1/semantic-status",
  );
  expect(fetch.mock.calls[0][1].body).toBeUndefined();
});

it("clears previous history on refresh failure then allows read-only retry", async () => {
  let fail = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => (fail ? { ok: false, status: 503 } : json(status))),
  );
  render(<SemanticVerificationStatus outputId={1} channelId={1} />);
  fireEvent.click(
    screen.getByRole("button", { name: "Проверка фактов: статус рерайта 1" }),
  );
  await screen.findByText("Ожидается восстановление worker");
  fail = true;
  fireEvent.click(
    screen.getByRole("button", { name: "Обновить статус проверки фактов 1" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("HTTP 503"),
  );
  expect(screen.queryByText("Ожидается восстановление worker")).toBeNull();
  fail = false;
  fireEvent.click(
    screen.getByRole("button", { name: "Обновить статус проверки фактов 1" }),
  );
  expect(
    await screen.findByText("Ожидается восстановление worker"),
  ).toBeTruthy();
});

it("aborts and ignores late responses after draft identity changes", async () => {
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
  const { rerender } = render(
    <SemanticVerificationStatus outputId={1} channelId={1} />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Проверка фактов: статус рерайта 1" }),
  );
  rerender(<SemanticVerificationStatus outputId={2} channelId={1} />);
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    resolve(json(status));
  });
  expect(screen.queryByText("Ожидается восстановление worker")).toBeNull();
  expect(
    screen
      .getByRole("button", { name: "Проверка фактов: статус рерайта 2" })
      .getAttribute("aria-expanded"),
  ).toBe("false");
});

it("aborts on collapse and issues a fresh GET when reopened", async () => {
  let resolve: (value: unknown) => void = () => {};
  let signal: AbortSignal | undefined;
  const fetch = vi.fn((_path: string, init: RequestInit) => {
    signal = init.signal as AbortSignal;
    return new Promise((done) => {
      resolve = done;
    });
  });
  vi.stubGlobal("fetch", fetch);
  render(<SemanticVerificationStatus outputId={1} channelId={1} />);
  const toggle = screen.getByRole("button", {
    name: "Проверка фактов: статус рерайта 1",
  });
  fireEvent.click(toggle);
  fireEvent.click(toggle);
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    resolve(json(status));
  });
  expect(screen.queryByText("Ожидается восстановление worker")).toBeNull();
  fireEvent.click(toggle);
  expect(fetch).toHaveBeenCalledTimes(2);
  await act(async () => {
    resolve(json(status));
  });
  expect(
    await screen.findByText("Ожидается восстановление worker"),
  ).toBeTruthy();
});

it.each(["approval_state", "policy_mode"])(
  "refuses coercible arrays for %s",
  async (field) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          ...status,
          current_gate: "MANUAL",
          reason_code: "SEMANTIC_AUTOMATIC_POLICY_DISABLED",
          latest_job: null,
          [field]: [status[field as keyof typeof status]],
        }),
      ),
    );
    await expect(
      loadSemanticStatus(1, 1, new AbortController().signal),
    ).rejects.toThrow("Некорректный ответ");
  },
);

it("redacts malformed private JSON instead of displaying parser content", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => {
        throw new SyntaxError("secret-parser-content");
      },
    })),
  );
  await expect(
    loadSemanticStatus(1, 1, new AbortController().signal),
  ).rejects.toThrow("Некорректный ответ");
});
