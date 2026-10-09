import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("real protected illustration approve, reject and stale-source revoke preserve publication gates", async ({
  page,
  request,
}, testInfo) => {
  const writes: string[] = [];
  page.on("request", (req) => {
    if (req.method() !== "GET") writes.push(new URL(req.url()).pathname);
  });
  await page.goto("/");
  await page.getByRole("button", { name: /^Планировщик/ }).click();
  await page.getByLabel("Дата плана").fill("2030-01-03");
  const panel = page.getByRole("region", {
    name: "Проверка иллюстрации 1",
    exact: true,
  });
  await expect(panel).toBeVisible();
  const approve = panel.getByRole("button", {
    name: "Одобрить иллюстрацию",
    exact: true,
  });
  await expect(approve).toBeDisabled();
  const load = panel.getByRole("button", {
    name: "Загрузить контекст проверки",
  });
  await panel
    .getByLabel("Токен редактора")
    .fill("synthetic-browser-only-review-token-0001");
  await load.click();
  const photo = panel.getByRole("img", {
    name: "Проверяемая иллюстрация, не фото события",
  });
  await expect(photo).toBeVisible();
  await expect(
    panel.getByText("Завод открыл 3 линии.", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText("Открыты 3 линии на заводе.", { exact: true }),
  ).toBeVisible();
  await panel
    .getByLabel("Комментарий проверки")
    .fill("Synthetic illustrated context reviewed; no event-photo claim");
  await expect(approve).toBeDisabled();
  await panel
    .getByRole("checkbox", { name: /Это иллюстрация, а не фотография события/ })
    .check();
  await expect(approve).toBeEnabled();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: testInfo.outputPath("review-canonical-before-approval-1440.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: testInfo.outputPath("review-canonical-before-approval-390.png"),
    fullPage: true,
  });
  await approve.focus();
  await page.keyboard.press("Enter");
  await expect(panel.getByText(/Проверка сохранена/)).toBeVisible();
  await expect(
    page.getByText(/Текущая проверка иллюстрации подтверждена/),
  ).toBeVisible();
  await expect(photo).toHaveCount(0);
  await load.click();
  await expect(photo).toBeVisible();
  await panel
    .getByLabel("Комментарий проверки")
    .fill("Synthetic rejection after second examination");
  await panel.getByRole("button", { name: "Отклонить иллюстрацию" }).click();
  await expect(panel.getByText(/Иллюстрация отклонена/)).toBeVisible();
  await expect(
    page.getByText(/Публикация иллюстраций заблокирована/),
  ).toBeVisible();
  await load.click();
  await expect(photo).toBeVisible();
  await panel
    .getByLabel("Комментарий проверки")
    .fill("Synthetic illustration approved for stale-source revoke test");
  await panel.getByRole("checkbox", { name: /Это иллюстрация/ }).check();
  await approve.click();
  await expect(panel.getByText(/Иллюстрация одобрена/)).toBeVisible();
  expect(
    (
      await request.post(
        "http://127.0.0.1:5183/api/ui-test/reject-illustration-source",
      )
    ).ok(),
  ).toBe(true);
  await load.click();
  await expect(panel.getByText(/Контекст изменился/)).toBeVisible();
  await panel
    .getByRole("button", { name: "Прочитать последнюю проверку" })
    .click();
  await expect(panel.getByText(/Проверка #3/)).toBeVisible();
  await panel
    .getByLabel("Комментарий проверки")
    .fill("Withdraw after source editorial rejection");
  await panel
    .getByRole("button", { name: "Отозвать последнюю проверку" })
    .click();
  await expect(panel.getByText(/Отзыв сохранён/)).toBeVisible();
  await expect(panel.getByText(/Отозвана/)).toBeVisible();
  await expect(approve).toBeDisabled();
  await page.screenshot({
    path: testInfo.outputPath("review-stale-revoked-390.png"),
    fullPage: true,
  });
  const evidence = await (
    await request.get("http://127.0.0.1:5183/api/ui-test/illustration-evidence")
  ).json();
  expect(evidence).toEqual({
    publication_jobs: 0,
    review_records: 4,
    provider_calls: ["search", "download"],
  });
  expect(writes).toEqual([
    "/api/illustration-review/candidates/1/reviews",
    "/api/illustration-review/candidates/1/reviews",
    "/api/illustration-review/candidates/1/reviews",
    "/api/illustration-review/records/3/revocations",
  ]);
  await panel.getByRole("button", { name: "Отключить проверку" }).click();
  await expect(panel.getByLabel("Токен редактора")).toHaveValue("");
  expect(
    await page.evaluate(() => JSON.stringify([localStorage, sessionStorage])),
  ).not.toContain("synthetic-browser-only-review-token-0001");
  await page.goto("/?demo=1");
  await page.getByRole("button", { name: /^Планировщик/ }).click();
  await expect(page.getByLabel("Токен редактора")).toHaveCount(0);
});
