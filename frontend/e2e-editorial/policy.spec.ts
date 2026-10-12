import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const token = "synthetic-browser-only-operator-token-0001";
const endpoint = "/api/settings/editorial-policy";
const evidenceURL = "http://127.0.0.1:5193/api/ui-test/editorial-evidence";
const headers = { Authorization: `Bearer ${token}` };
const panelOf = (page: Page) =>
  page.getByRole("region", { name: "Редакционная политика", exact: true });
async function settings(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Настройки", exact: true }).click();
  await page.getByRole("button", { name: "Модерация", exact: true }).click();
}
async function load(page: Page) {
  await panelOf(page).getByLabel("Токен оператора").fill(token);
  await panelOf(page)
    .getByRole("button", { name: "Загрузить редакционную политику" })
    .click();
  await expect(panelOf(page).getByLabel("Модель диагностики")).toBeVisible();
}
async function evidence(request: APIRequestContext) {
  const response = await request.get(evidenceURL, { headers });
  expect(response.status()).toBe(200);
  return response.json();
}
function noExecution(value: Awaited<ReturnType<typeof evidence>>) {
  expect(value.rejected_decisions).toEqual([
    { status: "REJECT", rewrite_allowed: false },
  ]);
  for (const key of [
    "rewrite_jobs",
    "diagnostic_jobs",
    "diagnostic_attempts",
    "publication_jobs",
    "rewrite_calls",
    "semantic_jobs",
  ])
    expect(value[key], key).toBe(0);
  expect(value.policy).toMatchObject({
    diagnostic_only: true,
    real_model_qualified: false,
    execution_authorized: false,
    rewrite_allowed: false,
  });
}

test("protected browser GET has isolated SQL evidence", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Настройки", exact: true }).click();
  await page.getByRole("button", { name: "Модерация", exact: true }).click();
  await page.getByLabel("Токен оператора").fill(token);
  const response = page.waitForResponse(
    (r) => new URL(r.url()).pathname === endpoint,
  );
  await page
    .getByRole("button", { name: "Загрузить редакционную политику" })
    .click();
  expect((await response).status()).toBe(200);
  await expect(
    page.getByText(/Редакционная политика ещё не настроена/),
  ).toBeVisible();
  const evidence = await request.get(evidenceURL, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(evidence.status()).toBe(200);
  expect((await evidence.json()).outbox_count).toBe(0);
});

test("real create, disable, aliases, noop and stale ETag preserve exact drafts and audit", async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = [];
  const urls: string[] = [];
  const writes: string[] = [];
  const initialPolicyRequests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !/Failed to load resource: the server responded with a status of (401|409)/.test(
        message.text(),
      )
    )
      errors.push(message.text());
  });
  page.on("request", (req) => {
    urls.push(req.url());
    if (new URL(req.url()).pathname === endpoint)
      initialPolicyRequests.push(req.method());
    if (req.method() !== "GET") writes.push(new URL(req.url()).pathname);
  });
  await settings(page);
  const panel = panelOf(page);
  await expect(panel.getByLabel("Токен оператора")).toBeVisible();
  expect(initialPolicyRequests).toEqual([]);
  // Invalid bearer still reaches the real protected API and stays private.
  await panel
    .getByLabel("Токен оператора")
    .fill("invalid-synthetic-operator-token-00000001");
  const denied = page.waitForResponse(
    (r) => new URL(r.url()).pathname === endpoint,
  );
  await panel
    .getByRole("button", { name: "Загрузить редакционную политику" })
    .click();
  const privateResponse = await denied;
  expect(privateResponse.status()).toBe(401);
  expect(privateResponse.headers()["cache-control"]).toBe("no-store");
  const deniedBody = await request.get("http://127.0.0.1:5193" + endpoint, {
    headers: {
      Authorization: "Bearer invalid-synthetic-operator-token-00000001",
    },
  });
  expect(deniedBody.status()).toBe(401);
  expect(await deniedBody.json()).toEqual({
    detail: "Editorial operator authentication required",
  });
  await expect(panel.getByRole("alert")).toContainText("401");
  await load(page);
  await expect(panel.getByLabel("Токен оператора")).toHaveAttribute(
    "type",
    "password",
  );
  await panel.getByLabel("Модель диагностики").fill("gpt-4.1-mini");
  await panel.getByLabel("Включить диагностику").check();
  await panel
    .getByRole("button", { name: "Добавить защищённую сущность" })
    .click();
  await panel
    .getByLabel("ID сущности 1", { exact: true })
    .fill("synthetic-entity");
  await panel
    .getByLabel("Псевдоним 1 сущности 1", { exact: true })
    .fill(" Synthetic alias\nsecond line ");
  const save = panel.getByRole("button", {
    name: "Сохранить редакционную политику",
    exact: true,
  });
  await save.focus();
  await page.keyboard.press("Enter");
  await expect(
    panel.getByText(/Редакционная политика сохранена;/),
  ).toBeVisible();
  let sql = await evidence(request);
  expect(sql.outbox_count).toBe(1);
  expect(sql.policy).toMatchObject({
    enabled: true,
    provider: "OPENAI",
    model: "gpt-4.1-mini",
    protected_entities: [
      {
        entity_id: "synthetic-entity",
        aliases: [" Synthetic alias\nsecond line "],
      },
    ],
  });
  const originalVersion = sql.policy.policy_version;
  const originalEtag = sql.policy.etag;
  await panel.getByLabel("Включить диагностику").uncheck();
  await save.click();
  await expect(panel.getByLabel("ETag политики")).not.toHaveValue(originalEtag);
  sql = await evidence(request);
  expect(sql.outbox_count).toBe(2);
  expect(sql.policy.enabled).toBe(false);
  expect(sql.policy.policy_version).toBe(originalVersion);
  // No-op is a real PUT; it must not produce a duplicate event or new version.
  const noop = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === endpoint && r.request().method() === "PUT",
  );
  await save.click();
  expect((await noop).status()).toBe(200);
  expect((await evidence(request)).outbox_count).toBe(2);
  await panel.getByLabel("Поставщик диагностики").selectOption("OPENROUTER");
  await panel
    .getByLabel("Модель диагностики")
    .fill("synthetic/fixed-model:free");
  await panel
    .getByRole("button", { name: "Добавить псевдоним сущности 1", exact: true })
    .click();
  await panel
    .getByLabel("Псевдоним 2 сущности 1", { exact: true })
    .fill("Другой синтетический псевдоним");
  await save.click();
  await expect(panel.getByLabel("Версия политики")).not.toHaveValue(
    originalVersion,
  );
  sql = await evidence(request);
  expect(sql.outbox_count).toBe(3);
  expect(sql.policy.model).toBe("synthetic/fixed-model:free");
  expect(sql.policy.protected_entities[0].aliases).toEqual([
    " Synthetic alias\nsecond line ",
    "Другой синтетический псевдоним",
  ]);
  await page.reload();
  await page.getByRole("button", { name: "Настройки", exact: true }).click();
  await page.getByRole("button", { name: "Модерация", exact: true }).click();
  await expect(panel.getByLabel("Токен оператора")).toHaveValue("");
  await load(page);
  await expect(panel.getByLabel("Модель диагностики")).toHaveValue(
    "synthetic/fixed-model:free",
  );
  // An unrelated AI-key draft survives policy operations; it is never submitted.
  await page
    .getByRole("button", { name: "AI и перефразирование", exact: true })
    .click();
  await page
    .getByLabel("API-ключ для замены")
    .fill("synthetic-unsaved-ai-key-only");
  await page.getByRole("button", { name: "Модерация", exact: true }).click();
  await panel
    .getByLabel("Модель диагностики")
    .fill("synthetic/local-draft:free");
  const beforeConcurrent = await evidence(request);
  const concurrent = await request.put("http://127.0.0.1:5193" + endpoint, {
    headers,
    data: {
      enabled: false,
      provider: "OPENROUTER",
      model: "synthetic/concurrent:free",
      protected_entities: [
        {
          entity_id: "synthetic-entity",
          aliases: [
            " Synthetic alias\nsecond line ",
            "Другой синтетический псевдоним",
          ],
        },
      ],
      expected_etag: beforeConcurrent.policy.etag,
    },
  });
  expect(concurrent.status()).toBe(200);
  const conflict = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === endpoint && r.request().method() === "PUT",
  );
  await save.click();
  expect((await conflict).status()).toBe(409);
  await expect(panel.getByRole("alert")).toContainText("409");
  await expect(panel.getByLabel("Модель диагностики")).toHaveValue(
    "synthetic/local-draft:free",
  );
  await expect(
    panel.getByLabel("Псевдоним 1 сущности 1", { exact: true }),
  ).toHaveValue(" Synthetic alias\nsecond line ");
  await expect(save).toBeDisabled();
  expect((await evidence(request)).outbox_count).toBe(4);
  await page.screenshot({
    path: testInfo.outputPath("editorial-policy-conflict-1440.png"),
    fullPage: true,
  });
  await panel
    .getByRole("button", { name: "Загрузить редакционную политику" })
    .click();
  const discard = panel.getByRole("group", {
    name: "Отбросить черновик редакционной политики?",
  });
  await discard.getByRole("button", { name: "Сохранить черновик" }).click();
  await expect(panel.getByLabel("Модель диагностики")).toHaveValue(
    "synthetic/local-draft:free",
  );
  await page.getByRole("switch", { name: "DEMO", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Остаться", exact: true })
    .click();
  await expect(panel.getByLabel("Модель диагностики")).toHaveValue(
    "synthetic/local-draft:free",
  );
  await panel
    .getByRole("button", { name: "Загрузить редакционную политику" })
    .click();
  await discard
    .getByRole("button", { name: "Отбросить черновик", exact: true })
    .click();
  await expect(panel.getByLabel("Модель диагностики")).toHaveValue(
    "synthetic/concurrent:free",
  );
  await expect(save).toBeEnabled();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`editorial-policy-saved-${width}.png`),
      fullPage: true,
    });
  }
  await page
    .getByRole("button", { name: "AI и перефразирование", exact: true })
    .click();
  await expect(page.getByLabel("API-ключ для замены")).toHaveValue(
    "synthetic-unsaved-ai-key-only",
  );
  await page.getByRole("button", { name: "Модерация", exact: true }).click();
  sql = await evidence(request);
  noExecution(sql);
  expect(sql.events).toHaveLength(4);
  expect(
    sql.events.every(
      (event: { actor_id: number; event_type: string }) =>
        event.actor_id === 29 &&
        event.event_type === "EditorialPolicyConfigured",
    ),
  ).toBe(true);
  expect(sql.events[0].before_etag).toBe("none");
  expect(sql.events[0].after_etag).toBe(originalEtag);
  expect(sql.events[3].after_etag).toBe(sql.policy.etag);
  expect(
    new Set(
      sql.events.map(
        (event: { idempotency_key: string }) => event.idempotency_key,
      ),
    ).size,
  ).toBe(4);
  await testInfo.attach("sql-evidence", {
    body: JSON.stringify(sql, null, 2),
    contentType: "application/json",
  });
  await panel
    .getByRole("button", { name: "Отключить редакционную политику" })
    .click();
  await expect(panel.getByLabel("Токен оператора")).toHaveValue("");
  expect(
    await page.evaluate(() => JSON.stringify([localStorage, sessionStorage])),
  ).not.toContain(token);
  expect(await page.context().cookies()).toEqual([]);
  expect(urls.every((url) => new URL(url).hostname === "127.0.0.1")).toBe(true);
  expect(urls.join("\n")).not.toContain(token);
  expect(writes).toEqual(Array(5).fill(endpoint));
  expect(errors).toEqual([]);
  const policyRequests: string[] = [];
  page.on("request", (req) => {
    if (new URL(req.url()).pathname === endpoint)
      policyRequests.push(req.url());
  });
  await page.getByRole("switch", { name: "DEMO", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Переключить и сбросить" })
    .click();
  await expect(page.getByLabel("Токен оператора")).toHaveCount(0);
  await page.getByRole("button", { name: "Общие", exact: true }).click();
  await page.getByRole("button", { name: "Модерация", exact: true }).click();
  await page.screenshot({
    path: testInfo.outputPath("editorial-demo-390.png"),
    fullPage: true,
  });
  expect(policyRequests).toEqual([]);
});

test("pending real responses cannot restore cancelled authorization or duplicate a save", async ({
  page,
  request,
}) => {
  await settings(page);
  const panel = panelOf(page);
  let release!: () => void;
  let fetched!: () => void;
  let delivered!: () => void;
  const delivery = new Promise<void>((resolve) => {
    delivered = resolve;
  });
  const ready = new Promise<void>((resolve) => {
    fetched = resolve;
  });
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    "**" + endpoint,
    async (route) => {
      const response = await route.fetch();
      fetched();
      await held;
      await route.fulfill({ response });
      delivered();
    },
    { times: 1 },
  );
  await panel.getByLabel("Токен оператора").fill(token);
  await panel
    .getByRole("button", { name: "Загрузить редакционную политику" })
    .click();
  await ready;
  await expect(
    panel.getByRole("button", { name: "Загрузить редакционную политику" }),
  ).toBeDisabled();
  await panel.getByLabel("Токен оператора").fill("");
  release();
  await delivery;
  await expect(panel.getByLabel("Модель диагностики")).toHaveCount(0);
  await load(page);
  await panel
    .getByLabel("Модель диагностики")
    .fill("synthetic/pending-save:free");
  const before = await evidence(request);
  let releaseSave!: () => void;
  let saveFetched!: () => void;
  let saveDelivered!: () => void;
  const saveDelivery = new Promise<void>((resolve) => {
    saveDelivered = resolve;
  });
  const saveReady = new Promise<void>((resolve) => {
    saveFetched = resolve;
  });
  const holdSave = new Promise<void>((resolve) => {
    releaseSave = resolve;
  });
  let puts = 0;
  page.on("request", (req) => {
    if (new URL(req.url()).pathname === endpoint && req.method() === "PUT")
      puts++;
  });
  await page.route(
    "**" + endpoint,
    async (route) => {
      const response = await route.fetch();
      saveFetched();
      await holdSave;
      await route.fulfill({ response });
      saveDelivered();
    },
    { times: 1 },
  );
  const save = panel.getByRole("button", {
    name: "Сохранить редакционную политику",
    exact: true,
  });
  await save.evaluate((button) => {
    (button as HTMLButtonElement).click();
    (button as HTMLButtonElement).click();
  });
  await saveReady;
  await expect(save).toBeDisabled();
  await expect(panel.getByLabel("Модель диагностики")).toBeDisabled();
  expect(puts).toBe(1);
  await panel.getByLabel("Токен оператора").fill("");
  await expect(panel.getByRole("alert")).toContainText(
    "Сохранение не подтверждено",
  );
  releaseSave();
  await saveDelivery;
  await expect(panel.getByLabel("Модель диагностики")).toHaveValue(
    "synthetic/pending-save:free",
  );
  await expect(save).toBeDisabled();
  const after = await evidence(request);
  expect(after.outbox_count).toBe(before.outbox_count + 1);
  expect(after.policy.model).toBe("synthetic/pending-save:free");
  noExecution(after);
  await panel.getByLabel("Токен оператора").fill(token);
  await panel
    .getByRole("button", { name: "Загрузить редакционную политику" })
    .click();
  await panel
    .getByRole("button", { name: "Отбросить черновик", exact: true })
    .click();
  await expect(panel.getByLabel("ETag политики")).toHaveValue(
    after.policy.etag,
  );
  await expect(save).toBeEnabled();
});
