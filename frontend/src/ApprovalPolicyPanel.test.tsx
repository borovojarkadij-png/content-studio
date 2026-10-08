import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ApprovalPolicyPanel } from "./ApprovalPolicyPanel";
import { approvalPolicy } from "./approvalPolicyApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const release = {
  id: 3,
  provider: "OPENAI",
  model: "synthetic-qualified",
  prompt_version: "semantic-facts-v1",
  benchmark_version: "semantic-facts-v1",
};
const manual = {
  output_channel_id: 1,
  mode: "MANUAL",
  release_id: null,
  qualified_releases: [release],
};
const json = (value: unknown) => ({ ok: true, json: async () => value });
const mount = (props = {}) =>
  render(
    <ApprovalPolicyPanel
      channelId={1}
      onDirty={() => {}}
      onBusy={() => {}}
      onSaved={() => {}}
      {...props}
    />,
  );

it("keeps automatic mode unavailable when no qualified model exists", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ...manual, qualified_releases: [] })),
  );
  mount();
  const mode = await screen.findByRole("combobox", {
    name: "Одобрение рерайтов",
  });
  expect(mode).toHaveProperty("value", "MANUAL");
  expect(
    screen.getByRole("option", { name: "Автоматически после проверки фактов" }),
  ).toHaveProperty("disabled", true);
  expect(screen.getByText(/Нет квалифицированных моделей/)).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Сохранить одобрение" }),
  ).toHaveProperty("disabled", true);
});

it("cancel restores saved policy and PUT persists only the selected qualified release", async () => {
  const requests: RequestInit[] = [];
  let stored: Record<string, unknown> = manual;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init: RequestInit) => {
      requests.push(init);
      if (init.method === "PUT")
        stored = {
          ...manual,
          mode: "VERIFIED",
          release_id: 3,
        };
      return json(stored);
    }),
  );
  const dirty = vi.fn();
  const saved = vi.fn();
  mount({ onDirty: dirty, onSaved: saved });
  const mode = await screen.findByRole("combobox", {
    name: "Одобрение рерайтов",
  });
  fireEvent.change(mode, { target: { value: "VERIFIED" } });
  expect(
    screen.getByRole("combobox", {
      name: "Закреплённая модель проверки фактов",
    }),
  ).toHaveProperty("value", "3");
  expect(dirty).toHaveBeenLastCalledWith(true);
  fireEvent.click(
    screen.getByRole("button", { name: "Отменить правки одобрения" }),
  );
  expect(mode).toHaveProperty("value", "MANUAL");
  expect(dirty).toHaveBeenLastCalledWith(false);
  fireEvent.change(mode, { target: { value: "VERIFIED" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить одобрение" }));
  expect(await screen.findByText(/Настройка одобрения сохранена/)).toBeTruthy();
  expect(
    JSON.parse(
      requests.find((request) => request.method === "PUT")!.body as string,
    ),
  ).toEqual({ mode: "VERIFIED", release_id: 3 });
  expect(saved).toHaveBeenCalledTimes(1);
  // The persisted notice can commit before the passive dirty notification.
  // Wait for the actual settled form contract, not merely the notice render.
  await waitFor(() => {
    expect(dirty).toHaveBeenLastCalledWith(false);
    expect(
      screen.getByRole("button", { name: "Сохранить одобрение" }),
    ).toHaveProperty("disabled", true);
  });
});

it("refused save retains draft without successful notice or side effects", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init: RequestInit) =>
      init.method === "PUT"
        ? { ok: false, status: 409, json: async () => ({ detail: "secret" }) }
        : json(manual),
    ),
  );
  const saved = vi.fn();
  mount({ onSaved: saved });
  fireEvent.change(
    await screen.findByRole("combobox", { name: "Одобрение рерайтов" }),
    { target: { value: "VERIFIED" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Сохранить одобрение" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("HTTP 409"),
  );
  expect(
    screen.getByRole("combobox", { name: "Одобрение рерайтов" }),
  ).toHaveProperty("value", "VERIFIED");
  expect(screen.queryByText(/Настройка одобрения сохранена/)).toBeNull();
  expect(saved).not.toHaveBeenCalled();
  expect(screen.queryByText("secret")).toBeNull();
});

it("allows switching a revoked persisted policy back to MANUAL without qualifying a model", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init: RequestInit) =>
      json(
        init.method === "PUT"
          ? { ...manual, qualified_releases: [] }
          : {
              ...manual,
              mode: "VERIFIED",
              release_id: 4,
              qualified_releases: [],
            },
      ),
    ),
  );
  mount();
  const mode = await screen.findByRole("combobox", {
    name: "Одобрение рерайтов",
  });
  expect(
    await screen.findByText(/Сохранённый release недоступен/),
  ).toBeTruthy();
  fireEvent.change(mode, { target: { value: "MANUAL" } });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить одобрение" }));
  expect(await screen.findByText(/Настройка одобрения сохранена/)).toBeTruthy();
  expect(mode).toHaveProperty("value", "MANUAL");
});

it.each([
  { output_channel_id: 2 },
  { mode: ["MANUAL"] },
  { mode: "MANUAL", release_id: 3 },
  { qualified_releases: [release, release] },
  {
    qualified_releases: [
      { ...release, model: "openrouter/free", provider: "OPENROUTER" },
    ],
  },
  { api_key: "private" },
])("refuses malformed/private policy %j", async (change) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ...manual, ...change })),
  );
  await expect(approvalPolicy(1, new AbortController().signal)).rejects.toThrow(
    "Некорректный ответ",
  );
});

it("ignores old-channel read after unmount and aborts it", async () => {
  let resolve: (value: unknown) => void = () => {};
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: string, init: RequestInit) => {
      signal = init.signal as AbortSignal;
      return new Promise((done) => {
        resolve = done;
      });
    }),
  );
  const { unmount } = mount();
  unmount();
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    resolve(json(manual));
  });
  expect(
    screen.queryByRole("combobox", { name: "Одобрение рерайтов" }),
  ).toBeNull();
});

it("duplicate save stays bounded and late PUT cannot change an unmounted form", async () => {
  let finish: (value: unknown) => void = () => {};
  let signal: AbortSignal | undefined;
  let writes = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, init: RequestInit) => {
      if (init.method !== "PUT") return json(manual);
      writes++;
      signal = init.signal as AbortSignal;
      return new Promise((done) => {
        finish = done;
      });
    }),
  );
  const saved = vi.fn();
  const busy = vi.fn();
  const { unmount } = mount({ onSaved: saved, onBusy: busy });
  fireEvent.change(
    await screen.findByRole("combobox", { name: "Одобрение рерайтов" }),
    { target: { value: "VERIFIED" } },
  );
  const save = screen.getByRole("button", { name: "Сохранить одобрение" });
  fireEvent.click(save);
  fireEvent.click(save);
  expect(writes).toBe(1);
  expect(busy).toHaveBeenLastCalledWith(true);
  expect(save).toHaveProperty("disabled", true);
  unmount();
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    finish(json({ ...manual, mode: "VERIFIED", release_id: 3 }));
  });
  expect(saved).not.toHaveBeenCalled();
});

it("HTTP read failure never renders default manual policy as authoritative and can refresh", async () => {
  let fail = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => (fail ? { ok: false, status: 503 } : json(manual))),
  );
  mount();
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("HTTP 503"),
  );
  expect(
    screen.queryByRole("combobox", { name: "Одобрение рерайтов" }),
  ).toBeNull();
  fail = false;
  fireEvent.click(
    screen.getByRole("button", { name: "Обновить настройку одобрения" }),
  );
  expect(
    await screen.findByRole("combobox", { name: "Одобрение рерайтов" }),
  ).toHaveProperty("value", "MANUAL");
});

it("a successful HTTP with mismatched save response does not claim persistence", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json(manual)),
  );
  const saved = vi.fn();
  mount({ onSaved: saved });
  fireEvent.change(
    await screen.findByRole("combobox", { name: "Одобрение рерайтов" }),
    { target: { value: "VERIFIED" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Сохранить одобрение" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("Некорректный ответ"),
  );
  expect(saved).not.toHaveBeenCalled();
  expect(
    screen.getByRole("combobox", { name: "Одобрение рерайтов" }),
  ).toHaveProperty("value", "VERIFIED");
});

it.each([0, -1, Number.NaN, 1.5])(
  "refuses invalid channel %s before HTTP",
  async (channelId) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(
      approvalPolicy(channelId, new AbortController().signal),
    ).rejects.toThrow("Некорректная настройка");
    expect(fetch).not.toHaveBeenCalled();
  },
);

it("redacts parser content and refuses invalid selections before HTTP", async () => {
  const fetch = vi.fn(async () => ({
    ok: true,
    json: async () => {
      throw new SyntaxError("private-parser");
    },
  }));
  vi.stubGlobal("fetch", fetch);
  await expect(
    approvalPolicy(1, new AbortController().signal, {
      mode: "MANUAL",
      release_id: 3,
    }),
  ).rejects.toThrow("Некорректная настройка");
  expect(fetch).not.toHaveBeenCalled();
  await expect(approvalPolicy(1, new AbortController().signal)).rejects.toThrow(
    "Некорректный ответ",
  );
});
