import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";


describe("App", () => {
  it("renders the Telegram navigation workspace in Russian", () => {
    render(<App />);

    expect(screen.getByRole("navigation", { name: "Основная навигация" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Аккаунты" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Доноры" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Входящие" })).toBeTruthy();
  });
});
