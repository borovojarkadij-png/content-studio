// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import {
  readEditorialPolicy,
  writeEditorialPolicy,
} from "./editorialPolicyApi";

const token = "synthetic-editorial-operator-token-0001";
const signal = () => new AbortController().signal;
const policy = {
  configured: true,
  enabled: false,
  provider: "OPENAI",
  model: "gpt-pinned",
  policy_version: "legacy-version",
  etag: "a".repeat(64),
  protected_entities: [
    { entity_id: " Организация\n😀", aliases: ["Имя\nА", "Alias"] },
  ],
  diagnostic_only: true,
  real_model_qualified: false,
  execution_authorized: false,
  rewrite_allowed: false,
};
const change = {
  enabled: true,
  provider: "OPENAI" as const,
  model: "gpt-pinned",
  protected_entities: policy.protected_entities,
  expected_etag: policy.etag,
};
const json = (v: unknown) => new Response(JSON.stringify(v));
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
const setup = (value: unknown = policy) => {
  vi.stubGlobal("window", { location: { origin: "https://studio.example" } });
  const fetch = vi.fn(async (_url: string, _init: RequestInit) => json(value));
  vi.stubGlobal("fetch", fetch);
  return fetch;
};
it("uses only the same-origin protected endpoint and header credential", async () => {
  const fetch = setup();
  const abort = signal();
  expect(
    (await readEditorialPolicy(token, abort)).protected_entities[0].entity_id,
  ).toBe(" Организация\n😀");
  expect(fetch).toHaveBeenCalledWith("/api/settings/editorial-policy", {
    signal: abort,
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    referrerPolicy: "no-referrer",
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
});
it.each([
  "https://foreign.example",
  "https://u:p@studio.example",
  "/prefix",
  "/api",
  "/?x=1",
  "/#x",
  "/?",
  "/#",
  "//foreign.example",
])("rejects unsafe base %s before transmitting credentials", async (base) => {
  const fetch = setup();
  vi.stubEnv("VITE_API_BASE_URL", base);
  await expect(readEditorialPolicy(token, signal())).rejects.toThrow();
  expect(fetch).not.toHaveBeenCalled();
});
it.each(["", "short", "x".repeat(129), " " + token, token + "\n"])(
  "rejects invalid credential before fetch",
  async (value) => {
    const fetch = setup();
    await expect(readEditorialPolicy(value, signal())).rejects.toThrow();
    expect(fetch).not.toHaveBeenCalled();
  },
);
it.each([
  { extra: 1 },
  { diagnostic_only: false },
  { real_model_qualified: true },
  { execution_authorized: true },
  { rewrite_allowed: true },
  { etag: "A".repeat(64) },
  { configured: false },
  { enabled: 1 },
  { provider: "OTHER" },
  { model: "x".repeat(256) },
  { policy_version: "" },
  { protected_entities: [{ entity_id: "a", aliases: [] }] },
  { protected_entities: [{ entity_id: "a", aliases: ["b"], extra: true }] },
  { protected_entities: [{ entity_id: "\ud800", aliases: ["b"] }] },
  {
    protected_entities: Array.from({ length: 65 }, (_, i) => ({
      entity_id: `id${i}`,
      aliases: ["a"],
    })),
  },
  { protected_entities: [{ entity_id: "a", aliases: Array(17).fill("b") }] },
  { protected_entities: [{ entity_id: "a".repeat(129), aliases: ["b"] }] },
  { protected_entities: [{ entity_id: "a", aliases: ["b".repeat(256)] }] },
  { protected_entities: [{ entity_id: "a", aliases: [" "] }] },
  { provider: "OPENROUTER", model: "openrouter/free" },
  { provider: "OPENROUTER", model: "openrouter/auto:free" },
  { provider: "OPENROUTER", model: "vendor/model" },
  { provider: "OPENROUTER", model: "vendor/x:y:free" },
])("refuses malformed authority or policy %j", async (patch) => {
  setup({ ...policy, ...patch });
  await expect(readEditorialPolicy(token, signal())).rejects.toThrow();
});
it("permits only the fully empty missing policy", async () => {
  setup({
    ...policy,
    configured: false,
    enabled: false,
    provider: null,
    model: null,
    policy_version: null,
    etag: null,
    protected_entities: [],
  });
  expect((await readEditorialPolicy(token, signal())).configured).toBe(false);
});
it("writes only allowed fields and verifies canonical acknowledgement", async () => {
  const fetch = setup({
    ...policy,
    enabled: true,
    protected_entities: [
      { ...policy.protected_entities[0], aliases: ["Alias", "Имя\nА"] },
    ],
  });
  expect(
    (
      await writeEditorialPolicy(
        token,
        { ...change, actor_id: 999 } as typeof change,
        signal(),
      )
    ).enabled,
  ).toBe(true);
  const init = fetch.mock.calls[0][1] as RequestInit;
  expect(JSON.parse(init.body as string)).toEqual(change);
  expect(init.method).toBe("PUT");
});
it("rejects a contradictory successful PUT", async () => {
  setup();
  await expect(writeEditorialPolicy(token, change, signal())).rejects.toThrow();
});
it.each([500, 502, 504])(
  "reports unexpected PUT HTTP %i as unconfirmed without echoing response data",
  async (status) => {
    setup();
    vi.stubGlobal("fetch", async () => new Response(token, { status }));
    const operation = writeEditorialPolicy(token, change, signal());
    await expect(operation).rejects.toMatchObject({
      status,
      message: expect.stringContaining("не подтверждён"),
    });
    await expect(operation).rejects.not.toThrow(token);
  },
);
it.each([401, 409, 422, 503, 500])(
  "uses fixed private HTTP %i error",
  async (status) => {
    setup();
    vi.stubGlobal("fetch", async () => new Response(token, { status }));
    try {
      await readEditorialPolicy(token, signal());
      throw new Error("unexpected");
    } catch (e) {
      expect((e as Error).message).not.toContain(token);
      expect((e as { status: number }).status).toBe(status);
    }
  },
);
it.each([
  new Uint8Array([0xc3, 0x28]),
  new TextEncoder().encode("{"),
  new Uint8Array(300001),
])("rejects invalid UTF8/JSON/oversized streamed bytes", async (bytes) => {
  setup();
  const cancel = vi.fn();
  vi.stubGlobal(
    "fetch",
    async () =>
      new Response(
        new ReadableStream({
          start(c) {
            c.enqueue(bytes);
          },
          cancel,
        }),
      ),
  );
  if (bytes.length < 300001)
    vi.stubGlobal("fetch", async () => new Response(bytes));
  await expect(readEditorialPolicy(token, signal())).rejects.toThrow();
  if (bytes.length > 300000) expect(cancel).toHaveBeenCalledOnce();
});
it("cancels a chunked response at the bound and releases its reader", async () => {
  setup();
  const cancel = vi.fn();
  const stream = new ReadableStream({
    start(c) {
      c.enqueue(new Uint8Array(150000));
      c.enqueue(new Uint8Array(150001));
    },
    cancel,
  });
  vi.stubGlobal("fetch", async () => new Response(stream));
  await expect(readEditorialPolicy(token, signal())).rejects.toThrow();
  expect(cancel).toHaveBeenCalledOnce();
  expect(stream.locked).toBe(false);
});
it("propagates an abort and keeps network error content private", async () => {
  setup();
  const controller = new AbortController();
  controller.abort();
  await expect(
    readEditorialPolicy(token, controller.signal),
  ).rejects.toMatchObject({ name: "AbortError" });
  vi.stubGlobal("fetch", async () => {
    throw new Error(token);
  });
  await expect(readEditorialPolicy(token, signal())).rejects.not.toThrow(token);
});
it("aborts and releases a pending response reader promptly", async () => {
  setup();
  const cancel = vi.fn();
  const stream = new ReadableStream({ cancel });
  vi.stubGlobal("fetch", async () => new Response(stream));
  const controller = new AbortController();
  const promise = readEditorialPolicy(token, controller.signal);
  await new Promise((resolve) => setTimeout(resolve, 0));
  controller.abort();
  await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  expect(cancel).toHaveBeenCalledOnce();
  expect(stream.locked).toBe(false);
});
it("preserves valid nonblank Unicode and embedded NUL exactly", async () => {
  setup({
    ...policy,
    protected_entities: [{ entity_id: "\ufeff", aliases: ["a\0b"] }],
  });
  expect(
    (await readEditorialPolicy(token, signal())).protected_entities,
  ).toEqual([{ entity_id: "\ufeff", aliases: ["a\0b"] }]);
});
it.each([
  { model: "" },
  { protected_entities: [{ entity_id: "a", aliases: [] }] },
  { expected_etag: "bad" },
  {
    protected_entities: Array.from({ length: 64 }, (_, i) => ({
      entity_id: `id${i}`,
      aliases: Array(16).fill("界".repeat(255)),
    })),
  },
])("rejects invalid submitted bounds before PUT %j", async (patch) => {
  const fetch = setup();
  await expect(
    writeEditorialPolicy(token, { ...change, ...patch }, signal()),
  ).rejects.toThrow();
  expect(fetch).not.toHaveBeenCalled();
});
it.each(["", "/", "https://studio.example", "https://studio.example/"])(
  "accepts same-origin root base %s",
  async (base) => {
    setup();
    vi.stubEnv("VITE_API_BASE_URL", base);
    expect((await readEditorialPolicy(token, signal())).configured).toBe(true);
  },
);
it("accepts exact 128-codepoint supplementary entity IDs and pinned OpenRouter models", async () => {
  setup({
    ...policy,
    provider: "OPENROUTER",
    model: "vendor/pinned:free",
    protected_entities: [{ entity_id: "😀".repeat(128), aliases: ["a"] }],
  });
  expect((await readEditorialPolicy(token, signal())).provider).toBe(
    "OPENROUTER",
  );
});
