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
  await expect(page.getByText("Слот #1", { exact: true })).toBeVisible();
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
  await expect(page.getByText("Слот #1", { exact: true })).toBeVisible();
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
