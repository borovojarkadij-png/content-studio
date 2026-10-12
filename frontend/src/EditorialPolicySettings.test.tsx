import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { EditorialPolicySettings } from "./EditorialPolicySettings";

const token = "synthetic-editorial-operator-token-0001";
const policy = {
  configured: true,
  enabled: false,
  provider: "OPENAI",
  model: "gpt-pinned",
  policy_version: "legacy-v1",
  etag: "a".repeat(64),
  protected_entities: [
    { entity_id: " Организация\n😀", aliases: ["Точное\nИмя", "Alias"] },
  ],
  diagnostic_only: true,
  real_model_qualified: false,
  execution_authorized: false,
  rewrite_allowed: false,
};
const json = (v: unknown) => new Response(JSON.stringify(v));
const button = (name: string) => screen.getByRole("button", { name });
const enter = () =>
  fireEvent.change(screen.getByLabelText("Токен оператора"), {
    target: { value: token },
  });
const load = async () => {
  enter();
  fireEvent.click(button("Загрузить редакционную политику"));
  await screen.findByLabelText("Модель диагностики");
};
const enabled = () =>
  fireEvent.click(
    screen.getByRole("checkbox", { name: "Включить диагностику" }),
  );
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
it("loads only explicitly and saves exact textarea values with the original ETag", async () => {
  const requests: RequestInit[] = [];
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    requests.push(init);
    return json(
      init.method === "PUT"
        ? {
            ...policy,
            ...JSON.parse(init.body as string),
            etag: "b".repeat(64),
            expected_etag: undefined,
          }
        : policy,
    );
  });
  const dirty = vi.fn();
  render(<EditorialPolicySettings onDirtyChange={dirty} />);
  enter();
  expect(requests).toHaveLength(0);
  expect(
    (screen.getByLabelText("Токен оператора") as HTMLInputElement).type,
  ).toBe("password");
  fireEvent.click(button("Загрузить редакционную политику"));
  const id = await screen.findByLabelText("ID сущности 1");
  expect((id as HTMLTextAreaElement).value).toBe(" Организация\n😀");
  expect(id.tagName).toBe("TEXTAREA");
  fireEvent.change(screen.getByLabelText("Псевдоним 1 сущности 1"), {
    target: { value: " Новый\nпсевдоним 😀 " },
  });
  enabled();
  fireEvent.click(button("Сохранить редакционную политику"));
  await screen.findByText(
    "Редакционная политика сохранена; настроена только диагностика.",
  );
  expect(JSON.parse(requests[1].body as string)).toEqual({
    enabled: true,
    provider: "OPENAI",
    model: "gpt-pinned",
    protected_entities: [
      {
        entity_id: " Организация\n😀",
        aliases: [" Новый\nпсевдоним 😀 ", "Alias"],
      },
    ],
    expected_etag: "a".repeat(64),
  });
  expect(dirty).toHaveBeenLastCalledWith(false);
});
it.each([409, 422, 401, 503])(
  "preserves draft on HTTP %i and requires explicit reload for conflicts",
  async (status) => {
    const requests: RequestInit[] = [];
    vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
      requests.push(init);
      return init.method === "PUT"
        ? new Response(token, { status })
        : json(policy);
    });
    render(<EditorialPolicySettings onDirtyChange={() => {}} />);
    await load();
    enabled();
    fireEvent.click(button("Сохранить редакционную политику"));
    await screen.findByRole("alert");
    expect(
      (
        screen.getByRole("checkbox", {
          name: "Включить диагностику",
        }) as HTMLInputElement
      ).checked,
    ).toBe(true);
    if (status === 409 || status === 401)
      expect(
        (button("Сохранить редакционную политику") as HTMLButtonElement)
          .disabled,
      ).toBe(true);
    expect(screen.getByRole("alert").textContent).not.toContain(token);
    fireEvent.click(button("Загрузить редакционную политику"));
    expect(
      screen.getByRole("group", {
        name: "Отбросить черновик редакционной политики?",
      }),
    ).toBeTruthy();
    fireEvent.click(button("Сохранить черновик"));
    expect(requests).toHaveLength(2);
  },
);
it("fences duplicate PUTs, freezes drafts, and invalidates late acknowledgement on token edit", async () => {
  let resolve!: (r: Response) => void;
  let writes = 0;
  let putSignal!: AbortSignal;
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    if (init.method === "PUT") {
      writes++;
      putSignal = init.signal as AbortSignal;
      return new Promise<Response>((r) => {
        resolve = r;
      });
    }
    return json(policy);
  });
  render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  await load();
  enabled();
  fireEvent.click(button("Сохранить редакционную политику"));
  fireEvent.click(button("Сохранить редакционную политику"));
  expect(writes).toBe(1);
  expect(screen.getByLabelText("Модель диагностики").matches(":disabled")).toBe(
    true,
  );
  fireEvent.change(screen.getByLabelText("Токен оператора"), {
    target: { value: token + "x" },
  });
  expect(putSignal.aborted).toBe(true);
  await act(async () => resolve(json({ ...policy, enabled: true })));
  expect(
    screen.queryByText(
      "Редакционная политика сохранена; настроена только диагностика.",
    ),
  ).toBeNull();
  expect(
    (
      screen.getByRole("checkbox", {
        name: "Включить диагностику",
      }) as HTMLInputElement
    ).checked,
  ).toBe(true);
  expect(
    (button("Сохранить редакционную политику") as HTMLButtonElement).disabled,
  ).toBe(true);
});
it("keeps an ambiguous save unconfirmed and never retries it automatically", async () => {
  let writes = 0;
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    if (init.method === "PUT") {
      writes++;
      throw new Error(token);
    }
    return json(policy);
  });
  const dirty = vi.fn();
  render(<EditorialPolicySettings onDirtyChange={dirty} />);
  await load();
  enabled();
  fireEvent.click(button("Сохранить редакционную политику"));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Сохранение не подтверждено",
  );
  expect(writes).toBe(1);
  expect(dirty).toHaveBeenLastCalledWith(true);
  expect(
    (button("Сохранить редакционную политику") as HTMLButtonElement).disabled,
  ).toBe(true);
});
it("dirty disconnect requires confirmation and clears the memory-only session", async () => {
  vi.stubGlobal("fetch", async () => json(policy));
  render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  await load();
  enabled();
  fireEvent.click(button("Отключить редакционную политику"));
  fireEvent.click(button("Сохранить черновик"));
  expect(screen.getByLabelText("Модель диагностики")).toBeTruthy();
  fireEvent.click(button("Отключить редакционную политику"));
  fireEvent.click(button("Отбросить черновик"));
  expect(
    (screen.getByLabelText("Токен оператора") as HTMLInputElement).value,
  ).toBe("");
  expect(screen.queryByLabelText("Модель диагностики")).toBeNull();
});
it("ignores a stale read after credential edit and aborts reads on unmount", async () => {
  const pending: { resolve: (r: Response) => void; signal: AbortSignal }[] = [];
  vi.stubGlobal(
    "fetch",
    (_url: string, init: RequestInit) =>
      new Promise<Response>((resolve) =>
        pending.push({ resolve, signal: init.signal as AbortSignal }),
      ),
  );
  const view = render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  enter();
  fireEvent.click(button("Загрузить редакционную политику"));
  fireEvent.change(screen.getByLabelText("Токен оператора"), {
    target: { value: token + "x" },
  });
  fireEvent.click(button("Загрузить редакционную политику"));
  await act(async () => pending[0].resolve(json(policy)));
  expect(screen.queryByLabelText("Модель диагностики")).toBeNull();
  expect(pending[0].signal.aborted).toBe(true);
  view.unmount();
  expect(pending[1].signal.aborted).toBe(true);
  await act(async () => pending[1].resolve(json(policy)));
});
it("creates a missing policy only after valid GET with null ETag", async () => {
  let body: unknown;
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    if (init.method === "PUT") {
      body = JSON.parse(init.body as string);
      return json({ ...policy, protected_entities: [] });
    }
    return json({
      ...policy,
      configured: false,
      enabled: false,
      provider: null,
      model: null,
      etag: null,
      policy_version: null,
      protected_entities: [],
    });
  });
  render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  expect(screen.queryByLabelText("Модель диагностики")).toBeNull();
  await load();
  fireEvent.change(screen.getByLabelText("Модель диагностики"), {
    target: { value: "gpt-pinned" },
  });
  fireEvent.click(button("Сохранить редакционную политику"));
  await screen.findByText(
    "Редакционная политика сохранена; настроена только диагностика.",
  );
  expect(body).toEqual({
    enabled: false,
    provider: "OPENAI",
    model: "gpt-pinned",
    protected_entities: [],
    expected_etag: null,
  });
});
it("keeps malformed success out of the trusted form", async () => {
  vi.stubGlobal("fetch", async () =>
    json({ ...policy, rewrite_allowed: true }),
  );
  render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  enter();
  fireEvent.click(button("Загрузить редакционную политику"));
  await screen.findByRole("alert");
  expect(screen.queryByLabelText("Модель диагностики")).toBeNull();
});
it("lets the operator correct a locally invalid model without a false ambiguous-save lock", async () => {
  let writes = 0;
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    if (init.method === "PUT") writes++;
    return json(policy);
  });
  render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  await load();
  fireEvent.change(screen.getByLabelText("Модель диагностики"), {
    target: { value: "" },
  });
  fireEvent.click(button("Сохранить редакционную политику"));
  await screen.findByRole("alert");
  expect(writes).toBe(0);
  expect(screen.getByRole("alert").textContent).not.toContain(
    "Сохранение не подтверждено",
  );
  fireEvent.change(screen.getByLabelText("Модель диагностики"), {
    target: { value: "gpt-pinned" },
  });
  fireEvent.click(button("Сохранить редакционную политику"));
  await screen.findByText(
    "Редакционная политика сохранена; настроена только диагностика.",
  );
  expect(writes).toBe(1);
});
it("reloads a conflict only after explicit discard and then uses the newly displayed ETag", async () => {
  let reads = 0;
  let writes = 0;
  const bodies: unknown[] = [];
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    if (init.method === "PUT") {
      bodies.push(JSON.parse(init.body as string));
      if (++writes === 1) return new Response("", { status: 409 });
      return json({ ...policy, enabled: true, etag: "b".repeat(64) });
    }
    return json({
      ...policy,
      etag: ++reads === 1 ? "a".repeat(64) : "b".repeat(64),
    });
  });
  render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  await load();
  enabled();
  fireEvent.click(button("Сохранить редакционную политику"));
  await screen.findByRole("alert");
  fireEvent.click(button("Загрузить редакционную политику"));
  expect(reads).toBe(1);
  fireEvent.click(button("Отбросить черновик"));
  await screen.findByText("Редакционная политика загружена.");
  expect(
    (
      screen.getByRole("checkbox", {
        name: "Включить диагностику",
      }) as HTMLInputElement
    ).checked,
  ).toBe(false);
  enabled();
  fireEvent.click(button("Сохранить редакционную политику"));
  await screen.findByText(
    "Редакционная политика сохранена; настроена только диагностика.",
  );
  expect(bodies).toMatchObject([
    { expected_etag: "a".repeat(64) },
    { expected_etag: "b".repeat(64) },
  ]);
});
it("treats corrupt successful PUT as unconfirmed, preserves dirty and requires explicit reload", async () => {
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) =>
    json(
      init.method === "PUT"
        ? { ...policy, enabled: true, rewrite_allowed: true }
        : policy,
    ),
  );
  render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  await load();
  enabled();
  fireEvent.click(button("Сохранить редакционную политику"));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Сохранение не подтверждено",
  );
  expect(
    (
      screen.getByRole("checkbox", {
        name: "Включить диагностику",
      }) as HTMLInputElement
    ).checked,
  ).toBe(true);
  expect(
    (button("Сохранить редакционную политику") as HTMLButtonElement).disabled,
  ).toBe(true);
});
it("adds and removes individual entity/alias controls without splitting or trimming values", async () => {
  let submitted: unknown;
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    if (init.method === "PUT") {
      submitted = JSON.parse(init.body as string);
      return json({
        ...policy,
        protected_entities: (submitted as typeof policy).protected_entities,
      });
    }
    return json(policy);
  });
  render(<EditorialPolicySettings onDirtyChange={() => {}} />);
  await load();
  fireEvent.click(button("Добавить защищённую сущность"));
  fireEvent.change(screen.getByLabelText("ID сущности 2"), {
    target: { value: " entity\n2 " },
  });
  fireEvent.change(screen.getByLabelText("Псевдоним 1 сущности 2"), {
    target: { value: " alias\n2 " },
  });
  fireEvent.click(button("Добавить псевдоним сущности 2"));
  fireEvent.change(screen.getByLabelText("Псевдоним 2 сущности 2"), {
    target: { value: " keep\nexact " },
  });
  fireEvent.click(button("Удалить псевдоним 1 сущности 2"));
  fireEvent.click(button("Удалить сущность 1"));
  fireEvent.click(button("Сохранить редакционную политику"));
  await screen.findByText(
    "Редакционная политика сохранена; настроена только диагностика.",
  );
  expect(submitted).toMatchObject({
    protected_entities: [
      { entity_id: " entity\n2 ", aliases: [" keep\nexact "] },
    ],
  });
});
