import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Content Studio dark navy UI", () => {
  it("renders all eight Russian workspaces in primary navigation", () => {
    render(<App />);

    const navigation = screen.getByRole("navigation", { name: "Основная навигация" });
    [
      "Обзор",
      "Входящие",
      "Доноры",
      "Мои каналы",
      "Связи",
      "Планировщик",
      "Аккаунты",
      "Настройки",
    ].forEach((item) => expect(navigation.textContent).toContain(item));
  });

  it("only displays fixture content after the user explicitly enables demo mode", () => {
    render(<App />);

    expect(screen.getByText("Рабочий режим")).toBeTruthy();
    expect(screen.queryByText("Демо-данные — без публикации")).toBeNull();

    fireEvent.click(screen.getByRole("switch", { name: "Включить демо-режим" }));

    expect(screen.getByText("Демо-данные — без публикации")).toBeTruthy();
  });

  it("keeps approval, scheduling and publication as separate moderation actions", async () => {
    render(<App initialDemo />);

    fireEvent.click(screen.getByRole("button", { name: /Входящие/ }));
    fireEvent.click(screen.getByRole("button", { name: "Одобрить материал" }));
    expect(await screen.findByText("Материал одобрен. Публикация не выполнена.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Запланировать" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Опубликовать" })).toBeTruthy();
  });

  it("allows an editor to explicitly apply an available demo draft", () => {
    render(<App initialDemo />);

    fireEvent.click(screen.getByRole("button", { name: /Входящие/ }));

    expect((screen.getByRole("button", { name: "Применить вариант" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("restores a settings draft when the editor cancels unsaved changes", () => {
    render(<App initialDemo />);

    fireEvent.click(screen.getByRole("button", { name: "Настройки" }));
    const language = screen.getByLabelText("Язык интерфейса") as HTMLSelectElement;
    fireEvent.change(language, { target: { value: "en" } });
    expect(language.value).toBe("en");

    fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(language.value).toBe("ru");
  });

  it("makes channel persistence explicitly demo-only instead of silently succeeding", () => {
    render(<App initialDemo />);

    fireEvent.click(screen.getByRole("button", { name: "Мои каналы" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить настройки DEMO" }));

    expect(screen.getByText("Настройки канала сохранены только в DEMO.")).toBeTruthy();
  });

  it("validates demo donor input without claiming that it was imported", () => {
    render(<App initialDemo />);

    fireEvent.click(screen.getByRole("button", { name: "Доноры" }));
    fireEvent.click(screen.getByRole("button", { name: /Импорт/ }));
    fireEvent.change(screen.getByLabelText("Список доноров для импорта"), { target: { value: "@science_today" } });
    fireEvent.click(screen.getByRole("button", { name: "Проверить строки" }));

    expect(screen.getByText("Проверка DEMO завершена: строки не были импортированы.")).toBeTruthy();
  });
});
