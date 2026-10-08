import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
const navigate = (name: string) =>
  fireEvent.click(
    within(
      screen.getByRole("navigation", { name: "Основная навигация" }),
    ).getByRole("button", { name }),
  );
const disabled = (name: string) =>
  (screen.getByRole("button", { name }) as HTMLButtonElement).disabled;

describe("Content Studio UI contracts", () => {
  it("observed album has real read-only context while historical PASS cannot enable actions", async () => {
    const fetch = vi.fn(async (_url: string) => ({
      ok: true,
      json: async () => ({
        items: [
          {
            source_key: "1:-1001234567890:20",
            state: "REWRITE_QUEUED",
            revision_number: 1,
            source_text: "Наблюдаемый альбом API",
            editorial_status: "PASS",
            rewrite_allowed: true,
            editorial_reason_codes: [],
            album_observed: true,
          },
        ],
      }),
    }));
    vi.stubGlobal("fetch", fetch);
    render(<App />);
    navigate("Входящие");
    fireEvent.click(
      await screen.findByRole("button", { name: /Наблюдаемый альбом API/ }),
    );
    expect(
      screen.getByRole("region", { name: "Наблюдение альбома" }),
    ).toBeTruthy();
    expect(screen.queryByText(/EDITORIAL REJECT:/)).toBeNull();
    expect(screen.queryByText(/EditorialGate не разрешил рерайт/)).toBeNull();
    expect(disabled("Применить вариант")).toBe(true);
    expect(disabled("Запланировать")).toBe(true);
    expect(disabled("Опубликовать")).toBe(true);
    expect(
      fetch.mock.calls.every(
        ([url]) => !(url as string).includes("source-albums"),
      ),
    ).toBe(true);
    fireEvent.click(screen.getByRole("switch", { name: "DEMO" }));
    expect(
      screen.queryByRole("region", { name: "Наблюдение альбома" }),
    ).toBeNull();
  });
  it("explains sync quarantine without fabricated editorial rejection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          items: [
            {
              source_key: "1:-1001234567890:20",
              state: "SOURCE_SYNC_REQUIRED",
              revision_number: 1,
              source_text: "Исторический источник с gap",
              editorial_status: "PASS",
              rewrite_allowed: true,
              editorial_reason_codes: [],
              source_deleted: false,
            },
          ],
        }),
      }),
    );
    render(<App />);
    navigate("Входящие");
    fireEvent.click(
      await screen.findByRole("button", {
        name: /Исторический источник с gap/,
      }),
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "Нужна синхронизация Telegram",
    );
    expect(screen.queryByText(/EDITORIAL REJECT:/)).toBeNull();
    expect(screen.queryByText(/EditorialGate не разрешил рерайт/)).toBeNull();
    expect(disabled("Применить вариант")).toBe(true);
    expect(disabled("Запланировать")).toBe(true);
  });
  it("shows source deletion separately from historical editorial PASS and disables all processing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          items: [
            {
              source_key: "1:-1001234567890:20",
              state: "REWRITE_QUEUED",
              revision_number: 1,
              source_text: "Исторический удалённый источник",
              editorial_status: "PASS",
              rewrite_allowed: true,
              editorial_reason_codes: [],
              source_deleted: true,
            },
          ],
        }),
      }),
    );
    render(<App />);
    navigate("Входящие");
    fireEvent.click(
      await screen.findByRole("button", {
        name: /Исторический удалённый источник/,
      }),
    );
    expect(screen.getAllByText("Удалён у донора").length).toBeGreaterThan(0);
    expect(screen.getByRole("alert").textContent).toContain(
      "Сохранена историческая копия",
    );
    expect(screen.queryByText(/EDITORIAL REJECT:/)).toBeNull();
    expect(
      screen.getByText(/Входящие сейчас доступны только для чтения/),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Опубликовать" }).textContent,
    ).toContain("не подключено");
    expect(disabled("Применить вариант")).toBe(true);
    expect(disabled("Запланировать")).toBe(true);
    expect(
      (screen.getByLabelText("Черновик варианта") as HTMLTextAreaElement)
        .disabled,
    ).toBe(true);
  });
  it("confirms AI overwrites and retains a read-only manual draft after rejection", () => {
    render(<App initialDemo />);
    navigate("Входящие");
    fireEvent.change(screen.getByLabelText("Черновик варианта"), {
      target: { value: "Важная ручная редактура" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Применить вариант" }));
    expect(
      screen.getByRole("dialog", { name: "Заменить ручной черновик?" }),
    ).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: "Сохранить ручной текст" }),
    );
    expect(
      (screen.getByLabelText("Черновик варианта") as HTMLTextAreaElement).value,
    ).toBe("Важная ручная редактура");
    fireEvent.click(screen.getByRole("button", { name: "Отклонить материал" }));
    expect(
      (screen.getByLabelText("Черновик варианта") as HTMLTextAreaElement).value,
    ).toBe("Важная ручная редактура");
    expect(
      (screen.getByLabelText("Черновик варианта") as HTMLTextAreaElement)
        .disabled,
    ).toBe(true);
  });
  it("requires explicit demo activation and never fetches real APIs in DEMO", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(<App />);
    expect(screen.getByText("Рабочий режим")).toBeTruthy();
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith(
      "/api/studio/overview",
      expect.objectContaining({ method: "GET" }),
    );
    fireEvent.click(screen.getByRole("switch", { name: "DEMO" }));
    fetch.mockClear();
    navigate("Входящие");
    navigate("Аккаунты");
    expect(screen.getByText("Демо-данные — без публикации")).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("keeps original text immutable and preserves editor drafts across selection and navigation", () => {
    render(<App initialDemo />);
    navigate("Входящие");
    const original = screen.getByLabelText("Оригинал материала").textContent;
    fireEvent.click(screen.getByRole("button", { name: "Применить вариант" }));
    fireEvent.change(screen.getByLabelText("Черновик варианта"), {
      target: { value: "Ручная правка редактора" },
    });
    navigate("Доноры");
    navigate("Входящие");
    expect(
      (screen.getByLabelText("Черновик варианта") as HTMLTextAreaElement).value,
    ).toBe("Ручная правка редактора");
    expect(screen.getByLabelText("Оригинал материала").textContent).toBe(
      original,
    );
  });
  it("keeps approval separate from scheduling and blocks every action after reject", () => {
    render(<App initialDemo />);
    navigate("Входящие");
    fireEvent.click(screen.getByRole("button", { name: "Одобрить материал" }));
    expect(
      screen.getByText("Материал одобрен в DEMO. Публикация не выполнена."),
    ).toBeTruthy();
    expect(disabled("Опубликовать")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Отклонить материал" }));
    expect(disabled("Применить вариант")).toBe(true);
    expect(disabled("Одобрить материал")).toBe(true);
    expect(disabled("Запланировать")).toBe(true);
    expect(
      (screen.getByLabelText("Черновик варианта") as HTMLTextAreaElement)
        .disabled,
    ).toBe(true);
  });
  it("retains failed API state and retries without injecting demo fixtures", async () => {
    let inboxReads = 0;
    const fetch = vi.fn(async (path: string) => {
      if (path.endsWith("/overview")) return { ok: false, status: 503 };
      if (!path.endsWith("/incoming-posts"))
        throw new Error(`Unexpected ${path}`);
      return inboxReads++ === 0
        ? { ok: false, status: 503 }
        : { ok: true, json: async () => ({ items: [] }) };
    });
    vi.stubGlobal("fetch", fetch);
    render(<App />);
    navigate("Входящие");
    expect(await screen.findByText("API вернул HTTP 503")).toBeTruthy();
    expect(
      screen.queryByText("На Марсе обнаружены следы древних рек"),
    ).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByText("Очередь входящих пуста.")).toBeTruthy();
    expect(
      fetch.mock.calls.filter(([path]) => path.endsWith("/incoming-posts")),
    ).toHaveLength(2);
  });
  it("uses the existing inbox API contract and disables live mutations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          items: [
            {
              source_key: "account:@donor:42",
              state: "REJECTED_EDITORIAL",
              revision_number: 2,
              source_text: "Отклонённый материал API",
              editorial_status: "REJECT",
              rewrite_allowed: false,
              editorial_reason_codes: ["PROTECTED_ENTITY"],
            },
          ],
        }),
      }),
    );
    render(<App />);
    navigate("Входящие");
    fireEvent.click(
      await screen.findByRole("button", { name: /Отклонённый материал API/ }),
    );
    expect(screen.getByLabelText("Оригинал материала").textContent).toBe(
      "Отклонённый материал API",
    );
    expect(disabled("Применить вариант")).toBe(true);
    expect(disabled("Запланировать")).toBe(true);
  });
  it("reports a malformed response as an API failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({ ok: true, json: async () => ({ wrong: [] }) }),
    );
    render(<App />);
    navigate("Входящие");
    expect(
      await screen.findByText("Ответ API не соответствует контракту входящих"),
    ).toBeTruthy();
  });
  it("saves a replacement OpenAI key only through the live settings API", async () => {
    const fetch = vi.fn(async (path: string, init?: RequestInit) => {
      if (path.endsWith("/overview")) return { ok: false, status: 503 };
      if (path.endsWith("/rewrite-providers"))
        return { ok: true, json: async () => ({ items: [] }) };
      if (path.endsWith("/openai") && init?.method === "PUT")
        return {
          ok: true,
          json: async () => ({
            provider: "OPENAI",
            configured: true,
            primary_model: "gpt-test-rewrite",
            fallback_models: [],
          }),
        };
      if (path.endsWith("/openai/models"))
        return {
          ok: true,
          json: async () => ({ items: ["gpt-test-rewrite", "gpt-another"] }),
        };
      throw new Error(`Unexpected ${path}`);
    });
    vi.stubGlobal("fetch", fetch);
    render(<App />);
    navigate("Настройки");
    fireEvent.click(
      await screen.findByRole("button", { name: "AI и перефразирование" }),
    );
    fireEvent.change(screen.getByLabelText("API-ключ для замены"), {
      target: { value: "synthetic-openai-key" },
    });
    fireEvent.change(screen.getByLabelText("Модель OpenAI"), {
      target: { value: "gpt-test-rewrite" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Сохранить AI-подключение" }),
    );

    await waitFor(() =>
      expect(fetch).toHaveBeenLastCalledWith(
        "/api/settings/rewrite-providers/openai",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            api_key: "synthetic-openai-key",
            model: "gpt-test-rewrite",
          }),
        }),
      ),
    );
    expect(
      (screen.getByLabelText("API-ключ для замены") as HTMLInputElement).value,
    ).toBe("");
    fireEvent.click(
      screen.getByRole("button", { name: "Обновить список моделей" }),
    );
    expect(
      await screen.findByRole("option", { name: "gpt-another" }),
    ).toBeTruthy();
    expect(fetch).toHaveBeenLastCalledWith(
      "/api/settings/rewrite-providers/openai/models",
      expect.objectContaining({ method: "GET" }),
    );
  });
  it("saves route percentages independently for each route and cancels to saved values", () => {
    render(<App initialDemo />);
    navigate("Связи");
    const intake = screen.getByRole("slider", {
      name: "Доля входящих материалов",
    }) as HTMLInputElement;
    const mix = screen.getByRole("slider", {
      name: "Целевая доля в канале",
    }) as HTMLInputElement;
    fireEvent.change(intake, { target: { value: "25" } });
    fireEvent.change(mix, { target: { value: "80" } });
    fireEvent.click(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /Технологии и люди.*Технологии сегодня.*75/,
      }),
    );
    expect(intake.value).toBe("75");
    expect(mix.value).toBe("60");
    fireEvent.click(
      screen.getByRole("button", { name: /Наука сегодня.*Научные факты.*25/ }),
    );
    expect(intake.value).toBe("25");
    expect(mix.value).toBe("80");
    fireEvent.change(intake, { target: { value: "99" } });
    fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(intake.value).toBe("25");
    expect(mix.value).toBe("80");
  });
  it("restores all settings fields on cancel and keeps drafts when changing categories", () => {
    render(<App initialDemo />);
    navigate("Настройки");
    fireEvent.change(screen.getByLabelText("Язык интерфейса"), {
      target: { value: "en" },
    });
    fireEvent.click(
      screen.getByRole("switch", { name: "Показывать советы и подсказки" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Модерация" }));
    fireEvent.change(screen.getByLabelText("Строгость проверки"), {
      target: { value: "Строгая" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(
      (screen.getByLabelText("Строгость проверки") as HTMLSelectElement).value,
    ).toBe("Стандартная");
    fireEvent.click(screen.getByRole("button", { name: "Общие" }));
    expect(
      (screen.getByLabelText("Язык интерфейса") as HTMLSelectElement).value,
    ).toBe("ru");
    expect(
      (
        screen.getByRole("switch", {
          name: "Показывать советы и подсказки",
        }) as HTMLInputElement
      ).checked,
    ).toBe(true);
  });
  it("warns before mode switching discards a manual draft", () => {
    render(<App initialDemo />);
    navigate("Входящие");
    fireEvent.change(screen.getByLabelText("Черновик варианта"), {
      target: { value: "Не терять" },
    });
    fireEvent.click(screen.getByRole("switch", { name: "DEMO" }));
    expect(
      screen.getByRole("dialog", { name: "Переключить режим?" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Остаться" }));
    expect(
      (screen.getByLabelText("Черновик варианта") as HTMLTextAreaElement).value,
    ).toBe("Не терять");
  });
  it("saves channel changes into demo state and does not overwrite them during selection", () => {
    render(<App initialDemo />);
    navigate("Мои каналы");
    fireEvent.change(screen.getByLabelText("Режим", { exact: true }), {
      target: { value: "С проверкой" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Сохранить настройки DEMO" }),
    );
    expect(
      screen.getByText("Настройки канала сохранены только в DEMO."),
    ).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: /Это интересно.*89 441/ }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Технологии сегодня.*124 320/ }),
    );
    expect(
      (screen.getByLabelText("Режим", { exact: true }) as HTMLSelectElement)
        .value,
    ).toBe("С проверкой");
  });
});
