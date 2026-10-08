import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";

test("non-first destination restores its saved schedule and keeps each target's manual draft", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Входящие");
  await page
    .getByRole("button", { name: "Запланировать", exact: true })
    .click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Канал", { exact: true }).selectOption("facts");
  await dialog.getByLabel("Дата", { exact: true }).fill("2026-10-01");
  await dialog.getByLabel("Время", { exact: true }).fill("11:00");
  await page.getByRole("button", { name: "Сохранить расписание DEMO" }).click();
  await page
    .getByRole("button", { name: "Запланировать", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Канал", { exact: true }).selectOption("facts");
  await expect(dialog.getByLabel("Дата", { exact: true })).toHaveValue(
    "2026-10-01",
  );
  await expect(dialog.getByLabel("Время", { exact: true })).toHaveValue(
    "11:00",
  );
  await dialog.getByLabel("Время", { exact: true }).fill("12:00");
  await dialog.getByLabel("Канал", { exact: true }).selectOption("tech");
  await dialog.getByLabel("Время", { exact: true }).fill("17:00");
  await dialog.getByLabel("Канал", { exact: true }).selectOption("facts");
  await expect(dialog.getByLabel("Время", { exact: true })).toHaveValue(
    "12:00",
  );
});

const sections = [
  ["Обзор", "overview"],
  ["Входящие", "inbox"],
  ["Доноры", "donors"],
  ["Мои каналы", "my_channels"],
  ["Связи", "connections"],
  ["Планировщик", "planner"],
  ["Аккаунты", "accounts"],
  ["Настройки", "settings"],
] as const;
const navigate = async (page: Page, name: string) => {
  await page
    .getByRole("navigation", { name: "Основная навигация" })
    .getByRole("button", { name, exact: true })
    .click();
};

test("real approval settings persist manual recovery without qualifying a model or losing plan edits", async ({
  page,
}, testInfo) => {
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/") && request.method() !== "GET")
      writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  await page.goto("/");
  await navigate(page, "Планировщик");
  const mode = page.getByRole("combobox", {
    name: "Одобрение рерайтов",
    exact: true,
  });
  await expect(mode).toHaveValue("MANUAL");
  await expect(mode.locator('option[value="VERIFIED"]')).toHaveJSProperty(
    "disabled",
    true,
  );
  await expect(page.getByText(/Нет квалифицированных моделей/)).toBeVisible();
  await page
    .getByLabel("Канал плана")
    .selectOption({ label: "Изолированный канал с отозванным release API" });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(mode).toHaveValue("VERIFIED");
    await expect(page.getByRole("alert")).toContainText(
      "Сохранённый release недоступен",
    );
    await page.getByLabel("Постов в день").fill("5");
    await mode.selectOption("MANUAL");
    await expect(page.getByLabel("Канал плана")).toBeDisabled();
    await page
      .getByRole("button", { name: "Отменить правки одобрения" })
      .click();
    await expect(mode).toHaveValue("VERIFIED");
    await expect(page.getByLabel("Постов в день")).toHaveValue("5");
    await expect(page.getByLabel("Канал плана")).toBeDisabled();
    await page.getByRole("button", { name: "Отменить правки плана" }).click();
    await expect(page.getByLabel("Канал плана")).toBeEnabled();
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
      path: testInfo.outputPath(`approval-policy-revoked-${width}.png`),
      fullPage: true,
    });
  }
  await page.route("**/output-channels/*/approval-policy", (route) =>
    route.request().method() === "PUT"
      ? route.fulfill({
          status: 409,
          contentType: "application/json",
          body: '{"detail":"private-test-error"}',
        })
      : route.continue(),
  );
  await mode.selectOption("MANUAL");
  await page.getByRole("button", { name: "Сохранить одобрение" }).click();
  await expect(page.getByRole("alert")).toContainText("HTTP 409");
  await expect(mode).toHaveValue("MANUAL");
  await expect(page.getByLabel("Канал плана")).toBeDisabled();
  await expect(page.getByText(/Настройка одобрения сохранена/)).toHaveCount(0);
  await expect(page.getByText("private-test-error")).toHaveCount(0);
  await page.unroute("**/output-channels/*/approval-policy");
  await page.getByRole("button", { name: "Сохранить одобрение" }).click();
  await expect(page.getByText(/Настройка одобрения сохранена/)).toBeVisible();
  await expect(page.getByLabel("Канал плана")).toBeEnabled();
  await page.reload();
  await navigate(page, "Планировщик");
  await page
    .getByLabel("Канал плана")
    .selectOption({ label: "Изолированный канал с отозванным release API" });
  await expect(mode).toHaveValue("MANUAL");
  await expect(mode.locator('option[value="VERIFIED"]')).toHaveJSProperty(
    "disabled",
    true,
  );
  await page.screenshot({
    path: testInfo.outputPath("approval-policy-saved-390.png"),
    fullPage: true,
  });
  const beforeDemo = writes.length;
  await page.goto("/?demo=1");
  await navigate(page, "Планировщик");
  await expect(
    page.getByRole("combobox", { name: "Одобрение рерайтов", exact: true }),
  ).toHaveCount(0);
  expect(writes.length).toBe(beforeDemo);
  expect(writes).toHaveLength(2);
  expect(
    writes.every((request) =>
      /^PUT \/api\/telegram\/output-channels\/\d+\/approval-policy$/.test(
        request,
      ),
    ),
  ).toBe(true);
});

test("real planner fact diagnostics are read-only, on demand and separated from DEMO", async ({
  page,
}, testInfo) => {
  const reads: string[] = [];
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/semantic-status"))
      reads.push(request.method());
    if (request.url().includes("/api/") && request.method() !== "GET")
      writes.push(request.url());
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await navigate(page, "Планировщик");
    const toggle = page.getByRole("button", {
      name: "Проверка фактов: статус рерайта 1",
    });
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    const before = reads.length;
    await page.getByLabel("Постов в день").fill("3");
    expect(reads.length).toBe(before);
    await toggle.click();
    const status = page.getByRole("region", {
      name: "Состояние проверки фактов 1",
    });
    await expect(status).toContainText("Настроено ручное одобрение");
    await expect(status).toContainText("Состояние сетевого worker неизвестно");
    await expect(status).toContainText("Задача проверки ещё не создана");
    await expect(page.getByLabel("Постов в день")).toHaveValue("3");
    await status
      .getByRole("button", { name: "Обновить статус проверки фактов 1" })
      .click();
    await expect(status).toContainText("Настроено ручное одобрение");
    // React development StrictMode can abort and repeat the initial GET.
    expect(reads.length).toBeGreaterThanOrEqual(before + 2);
    await page
      .getByRole("button", { name: "Проверка фактов: статус рерайта 2" })
      .click();
    const rejected = page.getByRole("region", {
      name: "Состояние проверки фактов 2",
    });
    await expect(rejected).toContainText(
      "Актуальные ограничения блокируют проверку",
    );
    await expect(rejected).toContainText(
      "EditorialGate не разрешает обработку",
    );
    await expect(
      page.getByRole("button", { name: "Одобрить рерайт 2" }),
    ).toBeDisabled();
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
      path: testInfo.outputPath(`semantic-status-live-${width}.png`),
      fullPage: true,
    });
    await page.getByLabel("Постов в день").fill("1");
    await page
      .getByLabel("Канал плана")
      .selectOption({ label: "Изолированный канал фото API" });
    await page
      .getByRole("button", { name: "Проверка фактов: статус рерайта 3" })
      .click();
    await expect(
      page.getByRole("region", { name: "Состояние проверки фактов 3" }),
    ).toContainText("Вариант не ожидает автоматической проверки");
    await page.reload();
    await navigate(page, "Планировщик");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await toggle.click();
    await expect(status).toContainText("Настроено ручное одобрение");
  }
  const beforeDemo = reads.length;
  await page.goto("/?demo=1");
  await navigate(page, "Планировщик");
  await expect(
    page.getByRole("button", { name: /Проверка фактов: статус/ }),
  ).toHaveCount(0);
  expect(reads.length).toBe(beforeDemo);
  expect(reads.every((method) => method === "GET")).toBe(true);
  expect(writes).toEqual([]);
});

test("real overview shows retained aggregates and unknown AI charges without fabricated charts", async ({
  page,
}, testInfo) => {
  const methods: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/studio/overview"))
      methods.push(request.method());
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await navigate(page, "Обзор");
    await expect(
      page.getByText("История источников", { exact: true }),
    ).toBeVisible();
    const usage = page.getByRole("region", { name: "Usage рерайта" });
    await expect(usage).toContainText(
      "Наблюдений usage: 1; без известной стоимости: 1",
    );
    await expect(usage).toContainText(
      "Сохранённых попыток: 2; без наблюдения usage: 1",
    );
    await expect(page.getByText(/Нет live-проверки Telegram/)).toBeVisible();
    const summaryBox = await page
      .locator(".workspace-view > .panel")
      .first()
      .boundingBox();
    const metricsBox = await page.locator(".metric-row").boundingBox();
    expect(summaryBox).not.toBeNull();
    expect(metricsBox!.y).toBeGreaterThan(summaryBox!.y + summaryBox!.height);
    await expect(
      page.getByText(/Стоимость части обращений неизвестна/),
    ).toBeVisible();
    await expect(
      page.getByRole("img", { name: /поток материалов/ }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "Обновить обзор" }).click();
    await expect(usage).toContainText("Наблюдений usage: 1");
    await page.reload();
    await navigate(page, "Обзор");
    await expect(usage).toContainText("без известной стоимости: 1");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
        .violations,
    ).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`overview-live-${width}.png`),
      fullPage: true,
    });
  }
  expect(methods.length).toBeGreaterThanOrEqual(6);
  expect(methods.every((method) => method === "GET")).toBe(true);
});

test("real persisted donor diagnostics survive reload and never authorize live actions", async ({
  page,
}, testInfo) => {
  const methods: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/sync-status")) methods.push(request.method());
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await navigate(page, "Доноры");
    const diagnostics = page.getByRole("region", {
      name: "Синхронизация источника",
    });
    await expect(diagnostics).toContainText("Разрыв истории не устранён");
    await expect(diagnostics).toContainText(
      "Обработка источника заблокирована",
    );
    await expect(diagnostics).toContainText(
      "live-проверка Telegram не выполнялась",
    );
    await page
      .getByLabel("Название", { exact: true })
      .fill("Несохранённое ручное название");
    await diagnostics
      .getByRole("button", { name: "Обновить синхронизацию" })
      .click();
    await expect(diagnostics).toContainText("Разрыв истории не устранён");
    await expect(page.getByLabel("Название", { exact: true })).toHaveValue(
      "Несохранённое ручное название",
    );
    await page
      .getByRole("button", { name: "Отменить правки названия" })
      .click();
    await page
      .getByRole("button", { name: /Другой изолированный донор API/ })
      .click();
    await expect(diagnostics).toContainText(
      "Контроль синхронизации не включён",
    );
    await expect(diagnostics).not.toContainText("Разрыв истории не устранён");
    await page.reload();
    await navigate(page, "Доноры");
    await expect(diagnostics).toContainText("Разрыв истории не устранён");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(diagnostics.getByRole("button")).toHaveCount(1);
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`donor-sync-${width}.png`),
      fullPage: true,
    });
  }
  expect(methods.length).toBeGreaterThanOrEqual(6);
  expect(methods.every((method) => method === "GET")).toBe(true);
});

test("real deleted-source inbox keeps historical copy and forbids processing after reload", async ({
  page,
}) => {
  const inboxMethods: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/incoming-posts"))
      inboxMethods.push(request.method());
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await navigate(page, "Входящие");
    await page
      .getByRole("button", { name: /Изолированный удалённый источник API/ })
      .click();
    await expect(page.getByRole("alert")).toContainText(
      "Сохранена историческая копия",
    );
    await expect(page.getByLabel("Оригинал материала")).toHaveText(
      "Изолированный удалённый источник API",
    );
    await expect(
      page.getByRole("button", { name: "Применить вариант" }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Запланировать", exact: true }),
    ).toBeDisabled();
    await expect(page.getByLabel("Черновик варианта")).toBeDisabled();
    await expect(page.getByText(/EDITORIAL REJECT:/)).toHaveCount(0);
    await page.getByRole("button", { name: /^Удалён у донора/ }).click();
    await expect(page.locator(".inbox-card")).toHaveCount(1);
    await page
      .getByRole("button", { name: /Изолированный удалённый источник API/ })
      .click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    const violations = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(violations.violations).toEqual([]);
    await page.evaluate(() => {
      (document.activeElement as HTMLElement)?.blur();
      window.scrollTo(0, 0);
    });
    await page.screenshot({
      path: path.resolve(
        `../.artifacts/ui-dark-navy/live-inbox-deleted-${width}.png`,
      ),
      fullPage: true,
    });
    await page.reload();
    await navigate(page, "Входящие");
    await page
      .getByRole("button", { name: /Изолированный удалённый источник API/ })
      .click();
    await expect(page.getByRole("alert")).toContainText(
      "Источник удалён у донора",
    );
  }
  expect(inboxMethods.length).toBeGreaterThanOrEqual(4);
  expect(inboxMethods.every((method) => method === "GET")).toBe(true);
});

test("real sync-gap inbox is readonly, distinct from editorial reject and survives reload", async ({
  page,
}) => {
  const methods: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/incoming-posts"))
      methods.push(request.method());
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await navigate(page, "Входящие");
    await page
      .getByRole("button", { name: /Изолированный источник с gap API/ })
      .click();
    await expect(page.getByRole("alert")).toContainText(
      "Нужна синхронизация Telegram",
    );
    await expect(page.getByLabel("Оригинал материала")).toHaveText(
      "Изолированный источник с gap API",
    );
    await expect(
      page.getByRole("button", { name: "Применить вариант" }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Запланировать", exact: true }),
    ).toBeDisabled();
    await expect(page.getByLabel("Черновик варианта")).toBeDisabled();
    await expect(page.getByText(/EDITORIAL REJECT:/)).toHaveCount(0);
    await expect(
      page.getByText(/EditorialGate не разрешил рерайт/),
    ).toHaveCount(0);
    await page.getByRole("button", { name: /^Нужна синхронизация/ }).click();
    await expect(page.locator(".inbox-card")).toHaveCount(1);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(result.violations).toEqual([]);
    await page.evaluate(() => {
      (document.activeElement as HTMLElement)?.blur();
      window.scrollTo(0, 0);
    });
    await page.screenshot({
      path: path.resolve(
        `../.artifacts/ui-dark-navy/live-inbox-sync-gap-${width}.png`,
      ),
      fullPage: true,
    });
    await page.reload();
    await navigate(page, "Входящие");
    await page
      .getByRole("button", { name: /Изолированный источник с gap API/ })
      .click();
    await expect(page.getByRole("alert")).toContainText(
      "история изменений источника не подтверждена",
    );
  }
  expect(methods.length).toBeGreaterThanOrEqual(4);
  expect(methods.every((method) => method === "GET")).toBe(true);
});

test("real configuration persists filters, delay, imports and names through reload without auth or publication", async ({
  page,
}) => {
  const unsafeCalls: string[] = [];
  page.on("request", (request) => {
    if (/publish-now|login|openai|openrouter/.test(request.url()))
      unsafeCalls.push(request.url());
  });
  await page.goto("/");
  await navigate(page, "Аккаунты");
  await expect(
    page.getByText("Сессия не подключена", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Название", { exact: true })
    .fill("Ручное название API");
  await page
    .getByRole("button", { name: "Сохранить название", exact: true })
    .click();
  await expect(
    page.getByText("Название сохранено в базе данных."),
  ).toBeVisible();
  await page.reload();
  await navigate(page, "Аккаунты");
  await expect(page.getByLabel("Название", { exact: true })).toHaveValue(
    "Ручное название API",
  );
  await page.getByLabel("Название новой записи").fill("Новая конфигурация API");
  await page.getByLabel("Telegram User ID").fill("9009");
  await page.getByRole("button", { name: "Создать запись аккаунта" }).click();
  await expect(
    page.getByText(
      "Запись сохранена. Telegram-подключение и права не проверены.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Подключить Telegram" }),
  ).toBeDisabled();
  await navigate(page, "Доноры");
  await page
    .getByLabel("Список доноров")
    .fill(
      "https://t.me/synthetic_new_donor\n@synthetic_new_donor\nnot a channel",
    );
  await page.getByRole("button", { name: "Импортировать доноров" }).click();
  await expect(
    page.getByText(/В очередь разрешения: 1; дубли: 1;/),
  ).toBeVisible();
  await expect(
    page.getByText(/@synthetic_new_donor · PENDING_RESOLUTION/),
  ).toBeVisible();
  await page.reload();
  await navigate(page, "Доноры");
  await expect(
    page.getByText(/@synthetic_new_donor · PENDING_RESOLUTION/),
  ).toBeVisible();
  await navigate(page, "Мои каналы");
  await page.getByLabel("Название новой записи").fill("Новый выходной API");
  await page.getByLabel("Telegram Channel ID").fill("-1004444444444");
  await page.getByRole("button", { name: "Создать запись канала" }).click();
  await expect(
    page.getByText(
      "Запись сохранена. Telegram-подключение и права не проверены.",
    ),
  ).toBeVisible();
  await navigate(page, "Связи");
  await page.getByLabel("Допуск к планированию").selectOption("DELAYED");
  await page.getByLabel("Задержка, минут").fill("45");
  await page.getByLabel("Приоритет", { exact: true }).fill("10");
  await page
    .getByRole("button", { name: "Сохранить маршрут", exact: true })
    .click();
  await expect(page.getByText("Маршрут сохранён в базе данных.")).toBeVisible();
  await page.getByLabel("Запрещённые домены").fill("EXAMPLE.org\nрф.рф");
  await page.getByLabel("Дополнительные рекламные маркеры").fill("buy now");
  await page
    .getByRole("button", { name: "Сохранить фильтры", exact: true })
    .click();
  await expect(
    page.getByText("Фильтры сохранены в базе данных."),
  ).toBeVisible();
  await expect(page.getByLabel("Запрещённые домены")).toHaveValue(
    "example.org\nxn--p1ai.xn--p1ai",
  );
  await page.reload();
  await navigate(page, "Связи");
  await expect(page.getByLabel("Задержка, минут")).toHaveValue("45");
  await expect(page.getByLabel("Запрещённые домены")).toHaveValue(
    "example.org\nxn--p1ai.xn--p1ai",
  );
  await expect(page.getByLabel("Дополнительные рекламные маркеры")).toHaveValue(
    "buy now",
  );
  await expect(page.getByLabel("Права на исходное фото")).toHaveValue(
    "UNDECLARED",
  );
  await page.getByLabel("Права на исходное фото").selectOption("PERMISSION");
  await page
    .getByLabel("Основание / авторство")
    .fill("Разрешение синтетического правообладателя");
  await page
    .getByRole("button", { name: "Сохранить права на фото", exact: true })
    .click();
  await expect(page.getByText("Права сохранены в базе данных.")).toBeVisible();
  await page.reload();
  await navigate(page, "Связи");
  await expect(page.getByLabel("Права на исходное фото")).toHaveValue(
    "PERMISSION",
  );
  await expect(page.getByLabel("Основание / авторство")).toHaveValue(
    "Разрешение синтетического правообладателя",
  );
  await page.getByLabel("Права на исходное фото").selectOption("UNDECLARED");
  await page
    .getByRole("button", { name: "Сохранить права на фото", exact: true })
    .click();
  await expect(page.getByText("Права сохранены в базе данных.")).toBeVisible();
  await page
    .getByLabel("Донор нового маршрута")
    .selectOption({ label: "Другой изолированный донор API" });
  await page
    .getByRole("button", { name: "Создать маршрут", exact: true })
    .click();
  await expect(page.getByLabel("Доля входящих материалов, %")).toHaveValue(
    "100",
  );
  await expect(page.getByLabel("Задержка, минут")).toHaveValue("0");
  await expect(
    page.getByRole("combobox", { name: "Маршрут", exact: true }),
  ).toHaveValue("2");
  await page
    .getByRole("combobox", { name: "Маршрут", exact: true })
    .selectOption("1");
  await expect(page.getByLabel("Задержка, минут")).toHaveValue("45");
  expect(unsafeCalls).toEqual([]);
});

test("working configuration sections are accessible and fit desktop/mobile with honest pending states", async ({
  page,
}) => {
  await page.goto("/");
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    for (const [name, slug] of [
      ["Доноры", "donors"],
      ["Мои каналы", "channels"],
      ["Связи", "connections"],
      ["Аккаунты", "accounts"],
    ]) {
      await navigate(page, name);
      await expect(
        page.getByRole("button", {
          name: name === "Связи" ? "Обновить связи" : "Обновить список",
        }),
      ).toBeEnabled();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      const audit = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(audit.violations).toEqual([]);
      await page.screenshot({
        path: path.resolve(
          `../.artifacts/ui-dark-navy/live-config-${slug}-${viewport.width}.png`,
        ),
        fullPage: true,
      });
    }
  }
});

test("live planner persists approval and per-channel daily plan through the migrated isolated API", async ({
  page,
}) => {
  const unsafeCalls: string[] = [];
  page.on("request", (request) => {
    if (/publish-now|openai|openrouter/.test(request.url()))
      unsafeCalls.push(request.url());
  });
  await page.goto("/");
  await navigate(page, "Планировщик");
  await expect(page.getByLabel("Постов в день")).toHaveValue("1");
  await page.getByRole("button", { name: "В стиле жёлтой прессы" }).click();
  await expect(
    page.getByText("Стиль сохранён. Применится к следующим рерайтам."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Одобрить рерайт 2" }),
  ).toBeDisabled();
  await page.getByLabel("Режим планирования").selectOption("AUTOMATIC");
  await page.getByLabel("Постов в день").fill("2");
  await page.getByLabel("Слоты публикаций").fill("09:00, 15:00");
  await page
    .getByRole("button", { name: "Сохранить план", exact: true })
    .click();
  await expect(page.getByText("План сохранён в базе данных.")).toBeVisible();
  await page.getByRole("button", { name: "Одобрить рерайт 1" }).click();
  await expect(
    page.getByText("Рерайт одобрен. Публикация не выполнена."),
  ).toBeVisible();
  await page.getByLabel("Дата плана").fill("2030-01-02");
  await page
    .getByRole("button", { name: "Подобрать публикации на день" })
    .click();
  await expect(
    page.getByText("ui-planner:@planner_donor:1:revision:1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Задание отправки не создано · попыток: 0/2"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Подготовить медиа 1" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Подготовить медиа 1" }).click();
  await expect(page.getByText("В очереди · попыток: 0/2")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Подготовить медиа 1" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("img", { name: /Выбранная иллюстрация/ }),
  ).toHaveCount(0);
  await page.reload();
  await navigate(page, "Планировщик");
  await expect(page.getByLabel("Постов в день")).toHaveValue("2");
  await expect(
    page.getByRole("button", { name: "В стиле жёлтой прессы" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("button", { name: "В стиле жёлтой прессы" }),
  ).toHaveCSS("border-top-color", "rgb(38, 186, 255)");
  await expect(page.getByLabel("Слоты публикаций")).toHaveValue("09:00, 15:00");
  await page.getByLabel("Дата плана").fill("2030-01-02");
  await expect(
    page.getByText("ui-planner:@planner_donor:1:revision:1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Задание отправки не создано · попыток: 0/2"),
  ).toBeVisible();
  await expect(page.getByText("В очереди · попыток: 0/2")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Одобрить рерайт 1" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Одобрить рерайт 2" }),
  ).toBeDisabled();
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.evaluate(() => {
    (document.activeElement as HTMLElement)?.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: path.resolve("../.artifacts/ui-dark-navy/live-planner-1440x900.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel("Слоты публикаций")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => {
    (document.activeElement as HTMLElement)?.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: path.resolve("../.artifacts/ui-dark-navy/live-planner-390x844.png"),
    fullPage: true,
  });
  expect(unsafeCalls).toEqual([]);
});

test("guarded real media preview renders exact fixture bytes and releases it on refresh", async ({
  page,
}) => {
  await page.goto("/");
  await navigate(page, "Планировщик");
  await page
    .getByLabel("Канал плана")
    .selectOption({ label: "Изолированный канал фото API" });
  await page.getByLabel("Режим планирования").selectOption("AUTOMATIC");
  await page
    .getByRole("button", { name: "Сохранить план", exact: true })
    .click();
  await expect(page.getByText("План сохранён в базе данных.")).toBeVisible();
  await page.getByLabel("Дата плана").fill("2030-01-03");
  await page
    .getByRole("button", { name: "Подобрать публикации на день" })
    .click();
  const preview = page.getByRole("button", { name: "Предпросмотр медиа 3" });
  await expect(preview).toBeVisible();
  await preview.click();
  const image = page.getByRole("img", {
    name: "Выбранная иллюстрация: соответствие событию не подтверждено",
  });
  await expect(image).toBeVisible();
  expect(
    await image.evaluate((element: HTMLImageElement) => element.naturalWidth),
  ).toBe(64);
  await page.evaluate(() => {
    (document.activeElement as HTMLElement)?.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: path.resolve(
      "../.artifacts/ui-dark-navy/live-media-preview-1440.png",
    ),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: path.resolve("../.artifacts/ui-dark-navy/live-media-preview-390.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Обновить медиа 3" }).click();
  await expect(image).toHaveCount(0);
  await expect(preview).toBeVisible();
});

test("real read-only delivery history distinguishes unknown from acknowledged after reload", async ({
  page,
}) => {
  const deliveryMethods: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/delivery-status"))
      deliveryMethods.push(request.method());
  });
  await page.goto("/");
  await navigate(page, "Планировщик");
  await page
    .getByLabel("Канал плана")
    .selectOption({ label: "Изолированная история доставки API" });
  await page.getByLabel("Дата плана").fill("2026-10-08");
  await expect(
    page.getByText("Результат отправки неизвестен · попыток: 1/2"),
  ).toBeVisible();
  await expect(
    page.getByText(/Повторная отправка запрещена до сверки/),
  ).toBeVisible();
  await expect(
    page.getByText("Доставка подтверждена · попыток: 1/2"),
  ).toBeVisible();
  await expect(page.getByText(/Сообщение #502/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Повторить отправку|Отправить сейчас/ }),
  ).toHaveCount(0);
  await page.reload();
  await navigate(page, "Планировщик");
  await page
    .getByLabel("Канал плана")
    .selectOption({ label: "Изолированная история доставки API" });
  await page.getByLabel("Дата плана").fill("2026-10-08");
  await expect(page.getByText(/Результат отправки неизвестен/)).toBeVisible();
  await expect(page.getByText(/Сообщение #502/)).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.evaluate(() => {
      (document.activeElement as HTMLElement)?.blur();
      window.scrollTo(0, 0);
    });
    await page.screenshot({
      path: path.resolve(
        `../.artifacts/ui-dark-navy/live-delivery-${width}.png`,
      ),
      fullPage: true,
    });
  }
  expect(deliveryMethods.length).toBeGreaterThanOrEqual(4);
  expect(deliveryMethods.every((method) => method === "GET")).toBe(true);
});

test("read-only receipt conflict warning survives refresh and fits narrow screens", async ({
  page,
}) => {
  // Inject only the HTTP reason on existing isolated history; no operational
  // job mutation, Telegram send, or false claim of real conflict delivery.
  await page.route(
    "**/api/telegram/planned-publications/*/delivery-status",
    async (route) => {
      const response = await route.fetch();
      const payload = await response.json();
      if (payload.state === "NEEDS_RECONCILIATION")
        payload.reason_code = "PUBLICATION_OBSERVATION_CONFLICT";
      await route.fulfill({ response, json: payload });
    },
  );
  await page.goto("/");
  await navigate(page, "Планировщик");
  await page
    .getByLabel("Канал плана")
    .selectOption({ label: "Изолированная история доставки API" });
  await page.getByLabel("Дата плана").fill("2026-10-08");
  const warning = page.getByText(/Получены противоречивые подтверждения/);
  await expect(warning).toBeVisible();
  await expect(warning).toHaveAttribute("role", "alert");
  await expect(
    page.getByRole("button", { name: /Повторить отправку|Отправить сейчас/ }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Обновить доставку 1", exact: true })
    .click();
  await expect(warning).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.evaluate(() => {
    (document.activeElement as HTMLElement)?.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: path.resolve(
      "../.artifacts/ui-dark-navy/live-delivery-conflict-390.png",
    ),
    fullPage: true,
  });
});

test("inbox repeated scheduling keeps saved date and time", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Входящие");
  await page
    .getByRole("button", { name: /Технологии и люди.*Новые инструменты/ })
    .click();
  await page
    .getByRole("button", { name: "Запланировать", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByLabel("Дата", { exact: true }),
  ).toHaveValue("2026-09-29");
  await expect(
    page.getByRole("dialog").getByLabel("Время", { exact: true }),
  ).toHaveValue("11:00");
});

test("overlapping calendar jobs remain individually accessible through a grouped slot", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Входящие");
  await page
    .getByRole("button", { name: "Запланировать", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByLabel("Дата", { exact: true })
    .fill("2026-10-01");
  await page.getByRole("button", { name: "Сохранить расписание DEMO" }).click();
  await navigate(page, "Планировщик");
  await page.getByRole("button", { name: /Открыть 2 публикации/ }).click();
  const slot = page.getByRole("dialog", {
    name: "Публикации выбранного слота",
  });
  await expect(
    slot.getByRole("button", { name: /На Марсе обнаружены/ }),
  ).toBeVisible();
  await expect(
    slot.getByRole("button", { name: /Почему кошки мурлыкают/ }),
  ).toBeVisible();
  await slot.getByRole("button", { name: /Почему кошки мурлыкают/ }).click();
  await expect(
    page
      .getByRole("dialog", { name: "Планирование в DEMO" })
      .getByLabel("Канал", { exact: true }),
  ).toHaveValue("curious");
});

test("all eight sections meet automated WCAG AA checks", async ({ page }) => {
  await page.goto("/?demo=1");
  for (const [name] of sections) {
    await navigate(page, name);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(
      result.violations.map((item) => ({
        id: item.id,
        nodes: item.nodes.map((node) => node.target),
      })),
      name,
    ).toEqual([]);
  }
});

test("actual FastAPI + migrated isolated database + Vite proxy renders rejection without provider calls", async ({
  page,
  request,
}) => {
  await expect(await request.get("http://127.0.0.1:5181/healthz")).toBeOK();
  await page.goto("/");
  await navigate(page, "Входящие");
  await page.getByRole("button", { name: /Изолированный API fixture/ }).click();
  await expect(page.getByLabel("Оригинал материала")).toContainText(
    "материал отклонён",
  );
  await expect(
    page.getByRole("button", { name: "Применить вариант", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Запланировать", exact: true }),
  ).toBeDisabled();
  await expect(page.getByLabel("Черновик варианта")).toBeDisabled();
  await expect(page.getByText("Демо-данные — без публикации")).toHaveCount(0);
});

for (const [width, height] of [
  [1366, 768],
  [1440, 900],
  [1586, 992],
  [1920, 1080],
  [390, 844],
]) {
  test(`eight sections at ${width}x${height}: layout, screenshots, no real API traffic`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height });
    const errors: string[] = [],
      api: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => {
      if (request.url().includes("/api/")) api.push(request.url());
    });
    await page.goto("/?demo=1");
    for (const [index, [name, file]] of sections.entries()) {
      await navigate(page, name);
      await expect(page.locator(".workspace-view:visible")).toHaveCount(1);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(
        name === "Обзор" ? "Обзор системы" : name,
      );
      const dimensions = await page.evaluate(() => ({
        content: document.documentElement.scrollWidth,
        window: document.documentElement.clientWidth,
      }));
      expect(
        dimensions.content,
        `${name} must not overflow the viewport`,
      ).toBeLessThanOrEqual(dimensions.window);
      await page.screenshot({
        path: path.resolve(
          `../.artifacts/ui-dark-navy/${width}x${height}/${String(index + 1).padStart(2, "0")}_${file}.png`,
        ),
        fullPage: true,
        animations: "disabled",
      });
    }
    expect(errors).toEqual([]);
    expect(api).toEqual([]);
  });
}

test("manual draft survives navigation; reject blocks rewrite/schedule and removes durable-demo plans", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Входящие");
  const original = await page.getByLabel("Оригинал материала").textContent();
  await page
    .getByRole("button", { name: "Применить вариант", exact: true })
    .click();
  await page
    .getByLabel("Черновик варианта")
    .fill("Ручная редактура без изменения источника");
  await navigate(page, "Доноры");
  await navigate(page, "Входящие");
  await expect(page.getByLabel("Черновик варианта")).toHaveValue(
    "Ручная редактура без изменения источника",
  );
  await expect(page.getByLabel("Оригинал материала")).toHaveText(original);
  await page
    .getByRole("button", { name: "Запланировать", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByLabel("Канал", { exact: true })
    .selectOption("facts");
  await page
    .getByRole("dialog")
    .getByLabel("Время", { exact: true })
    .fill("21:00");
  await page.getByRole("button", { name: "Сохранить расписание DEMO" }).click();
  await expect(page.getByRole("alert")).toContainText("вне окна");
  await page
    .getByRole("dialog")
    .getByLabel("Время", { exact: true })
    .fill("15:00");
  await page.getByRole("button", { name: "Сохранить расписание DEMO" }).click();
  await navigate(page, "Планировщик");
  await expect(page.locator('[data-job="mars-facts"]')).toHaveCount(1);
  await navigate(page, "Входящие");
  await page.getByRole("button", { name: "Отклонить материал" }).click();
  for (const name of [
    "Применить вариант",
    "Одобрить материал",
    "Запланировать",
    "Опубликовать",
  ])
    await expect(
      page.getByRole("button", { name, exact: true }),
    ).toBeDisabled();
  await navigate(page, "Планировщик");
  await expect(page.locator('[data-job="mars-facts"]')).toHaveCount(0);
});

test("calendar edit replaces a job instead of duplicate delivery", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Планировщик");
  await page.locator('[data-job="model-tech"]').click();
  await expect(
    page.getByRole("dialog").getByLabel("Дата", { exact: true }),
  ).toHaveValue("2026-09-29");
  await expect(
    page.getByRole("dialog").getByLabel("Время", { exact: true }),
  ).toHaveValue("11:00");
  await page
    .getByRole("dialog")
    .getByLabel("Время", { exact: true })
    .fill("16:00");
  await page.getByRole("button", { name: "Сохранить расписание DEMO" }).click();
  await expect(page.locator('[data-job="model-tech"]')).toHaveCount(1);
  await expect(page.locator('[data-job="model-tech"]')).toContainText("16:00");
});

test("modal keyboard trap and restoration; account wizard never pretends authentication", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Аккаунты");
  const trigger = page.getByRole("button", { name: "Подключить аккаунт DEMO" });
  await trigger.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Закрыть", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  expect(
    await page.evaluate(
      () => document.activeElement?.closest('[role="dialog"]') !== null,
    ),
  ).toBe(true);
  for (let i = 0; i < 3; i++)
    await dialog
      .getByRole("button", { name: "Следующий шаг DEMO", exact: true })
      .click();
  await expect(dialog).toContainText(
    "Аккаунт не подключён, Telegram-сессия не создана",
  );
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("settings draft categories and cancel restore the complete saved form", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Настройки");
  await page.getByLabel("Язык интерфейса").selectOption("en");
  await page.getByRole("button", { name: "Модерация", exact: true }).click();
  await page.getByLabel("Строгость проверки").selectOption("Строгая");
  await page.getByRole("button", { name: "Отмена", exact: true }).click();
  await expect(page.getByLabel("Строгость проверки")).toHaveValue(
    "Стандартная",
  );
  await page.getByRole("button", { name: "Общие", exact: true }).click();
  await expect(page.getByLabel("Язык интерфейса")).toHaveValue("ru");
});

test("real inbox retries HTTP errors without fallback fixtures", async ({
  page,
}) => {
  let attempt = 0;
  let failing = true;
  await page.route("**/api/telegram/incoming-posts", (route) => {
    attempt++;
    return route.fulfill({
      status: failing ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(
        failing
          ? {}
          : {
              items: [
                {
                  source_key: "account:@donor:42",
                  source_text: "Реальный контракт, синтетический ответ",
                  state: "REJECTED_EDITORIAL",
                  revision_number: 2,
                  editorial_status: "REJECT",
                  rewrite_allowed: false,
                  editorial_reason_codes: ["PROTECTED_ENTITY"],
                },
              ],
            },
      ),
    });
  });
  await page.goto("/");
  await navigate(page, "Входящие");
  await expect(page.getByRole("alert")).toHaveText("API вернул HTTP 503");
  failing = false;
  await page.getByRole("button", { name: "Повторить" }).click();
  await page
    .getByRole("button", { name: /Реальный контракт, синтетический ответ/ })
    .click();
  await expect(page.getByLabel("Оригинал материала")).toContainText(
    "синтетический ответ",
  );
  await expect(
    page.getByRole("button", { name: "Запланировать", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("На Марсе обнаружены следы древних рек", { exact: true }),
  ).toHaveCount(0);
  expect(attempt).toBeGreaterThanOrEqual(2);
});

test("bulk import previews duplicates and invalid identifiers before adding only valid DEMO donors", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Доноры");
  await page.getByRole("button", { name: "Импорт", exact: true }).click();
  await page
    .getByLabel("Список доноров для импорта")
    .fill(
      "@SCIENCE_today\nhttps://t.me/new_source\n@NEW_SOURCE\ninvalid value",
    );
  await expect(page.getByText("Дубликат", { exact: true })).toHaveCount(2);
  await expect(
    page.getByText("Неверный username", { exact: true }),
  ).toHaveCount(1);
  await page
    .getByRole("button", { name: "Добавить корректные в DEMO" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Добавлено в память DEMO: 1",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Закрыть", exact: true })
    .last()
    .click();
  await page.getByLabel("Поиск по источникам").fill("new_source");
  await expect(
    page.getByRole("button", { name: /new_source.*@new_source/ }),
  ).toHaveCount(1);
});

test("malformed live API data fails closed, with no DEMO material", async ({
  page,
}) => {
  await page.route("**/api/telegram/incoming-posts", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            source_key: "fake",
            state: "NEW",
            source_text: "Untrusted incomplete record",
            revision_number: 1,
          },
        ],
      }),
    }),
  );
  await page.goto("/");
  await navigate(page, "Входящие");
  await expect(page.getByRole("alert")).toHaveText(
    "Ответ API не соответствует контракту входящих",
  );
  await expect(page.locator(".inbox-card")).toHaveCount(0);
});

test("routing sliders have distinct semantics and save into selected route only", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await navigate(page, "Связи");
  const intake = page.getByRole("slider", { name: "Доля входящих материалов" });
  const mix = page.getByRole("slider", { name: "Целевая доля в канале" });
  await intake.fill("25");
  await mix.fill("80");
  await page
    .getByRole("button", { name: "Сохранить изменения", exact: true })
    .click();
  await page
    .getByRole("button", { name: /Технологии и люди.*Технологии сегодня.*75/ })
    .click();
  await expect(intake).toHaveValue("75");
  await expect(mix).toHaveValue("60");
  await page
    .getByRole("button", { name: /Наука сегодня.*Научные факты.*25/ })
    .click();
  await expect(intake).toHaveValue("25");
  await expect(mix).toHaveValue("80");
});
