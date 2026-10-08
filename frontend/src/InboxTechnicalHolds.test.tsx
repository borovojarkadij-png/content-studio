import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { loadInbox } from "./api";
import { canProcess } from "./studio";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function response(reasons: unknown) {
  return {
    ok: true,
    json: async () => ({
      items: [
        {
          source_key: "1:-1001234567890:20",
          state: "MANUAL_REVIEW",
          revision_number: 1,
          source_text: "Изолированный технический источник",
          editorial_status: "PASS",
          rewrite_allowed: true,
          editorial_reason_codes: [],
          source_deleted: false,
          album_observed: false,
          technical_reason_codes: reasons,
        },
      ],
    }),
  };
}

it.each([
  ["VIDEO_MANUAL_REVIEW_REQUIRED", "Видео: только ручная проверка"],
  ["YOUTUBE_LINK", "Ссылка YouTube"],
  ["INVALID_LINK", "Некорректная ссылка"],
  ["SOURCE_LINKS_UNKNOWN", "Ссылки источника не проверены"],
  ["SOURCE_LINKS_INVALID", "Метаданные ссылок повреждены"],
  ["ALBUM_NORMALIZATION_REQUIRED", "Состав альбома не подтверждён"],
  ["PROTECTED_CONTENT", "Источник защищён от копирования"],
])(
  "%s explains technical hold without fabricated editorial rejection or writes",
  async (code, explanation) => {
    const fetch = vi.fn(async (_url: string, _init?: RequestInit) =>
      response([code]),
    );
    vi.stubGlobal("fetch", fetch);
    const [post] = await loadInbox(new AbortController().signal);
    expect(post.editorial).toBe("PASS");
    expect(post.rewriteAllowed).toBe(false);
    expect(canProcess({ ...post, rewriteAllowed: true })).toBe(false);
    render(<App />);
    fireEvent.click(
      within(
        screen.getByRole("navigation", { name: "Основная навигация" }),
      ).getByRole("button", { name: "Входящие" }),
    );
    fireEvent.click(
      await screen.findByRole("button", {
        name: /Изолированный технический источник/,
      }),
    );
    const panel = screen.getByRole("region", {
      name: "Технические ограничения",
    });
    expect(panel.textContent).toContain(explanation);
    expect(panel.textContent).toContain("Историческое editorial-решение: PASS");
    expect(panel.querySelector("p p, p h3")).toBeNull();
    expect(screen.queryByText(/EDITORIAL REJECT:/)).toBeNull();
    expect(screen.queryByText(/EditorialGate не разрешил рерайт/)).toBeNull();
    for (const name of ["Применить вариант", "Запланировать", "Опубликовать"])
      expect(
        (screen.getByRole("button", { name }) as HTMLButtonElement).disabled,
      ).toBe(true);
    expect(
      (screen.getByLabelText("Черновик варианта") as HTMLTextAreaElement)
        .disabled,
    ).toBe(true);
    expect(
      fetch.mock.calls.every(
        ([, init]) => !init?.method || init.method === "GET",
      ),
    ).toBe(true);
    fireEvent.click(screen.getByRole("switch", { name: "DEMO" }));
    expect(
      screen.queryByRole("region", { name: "Технические ограничения" }),
    ).toBeNull();
  },
);

it.each([
  null,
  "YOUTUBE_LINK",
  ["UNKNOWN"],
  [1],
  ["YOUTUBE_LINK", "YOUTUBE_LINK"],
  Array(8).fill("YOUTUBE_LINK"),
])(
  "malformed or unknown diagnostics %j fail closed instead of granting PASS permission",
  async (reasons) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response(reasons)),
    );
    await expect(loadInbox(new AbortController().signal)).rejects.toThrow(
      "контракту входящих",
    );
  },
);

it("inbox requests bypass HTTP caches; empty diagnostics do not claim full readiness", async () => {
  const fetch = vi.fn(async (_url: string, _init: RequestInit) => response([]));
  vi.stubGlobal("fetch", fetch);
  const [post] = await loadInbox(new AbortController().signal);
  expect(canProcess(post)).toBe(true);
  expect(fetch.mock.calls[0][1].cache).toBe("no-store");
});

it("late aborted inbox response cannot replace current technical hold after DEMO round trip", async () => {
  let resolveOld!: (value: ReturnType<typeof response>) => void;
  const old = new Promise<ReturnType<typeof response>>((resolve) => {
    resolveOld = resolve;
  });
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (!url.endsWith("incoming-posts")) return { ok: false, status: 503 };
      return reads++ === 0 ? old : response(["SOURCE_LINKS_UNKNOWN"]);
    }),
  );
  render(<App />);
  const navigate = () =>
    fireEvent.click(
      within(
        screen.getByRole("navigation", { name: "Основная навигация" }),
      ).getByRole("button", { name: "Входящие" }),
    );
  navigate();
  fireEvent.click(screen.getByRole("switch", { name: "DEMO" }));
  fireEvent.click(screen.getByRole("switch", { name: "DEMO" }));
  fireEvent.click(
    await screen.findByRole("button", {
      name: /Изолированный технический источник/,
    }),
  );
  expect(
    screen.getByRole("region", { name: "Технические ограничения" }).textContent,
  ).toContain("Ссылки источника не проверены");
  await act(async () => {
    resolveOld(response([]));
  });
  expect(
    screen.getByRole("region", { name: "Технические ограничения" }).textContent,
  ).toContain("Ссылки источника не проверены");
  expect(reads).toBe(2);
});
