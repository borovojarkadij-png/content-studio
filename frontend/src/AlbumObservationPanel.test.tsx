import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AlbumObservationPanel } from "./AlbumObservationPanel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const key = "1:-1001234567890:20:revision:1";
const observation = {
  anchor_content_key: key,
  album_id: "77",
  membership_complete: false,
  rewrite_allowed: false,
  publication_allowed: false,
  source_sync_blocked: false,
  reason_code: "ALBUM_NORMALIZATION_REQUIRED",
  members: [
    {
      content_key: key,
      message_id: 20,
      revision_number: 1,
      text: "Первая подпись",
      media_type: "photo",
      media_protected: false,
      source_deleted: false,
    },
    {
      content_key: "other-video",
      message_id: 29,
      revision_number: 2,
      text: "Историческая подпись видео",
      media_type: "video",
      media_protected: true,
      source_deleted: true,
    },
    {
      content_key: "other-photo",
      message_id: 34,
      revision_number: 1,
      text: "",
      media_type: "photo",
      media_protected: null,
      source_deleted: false,
    },
  ],
};
const json = (value: unknown) => ({ ok: true, json: async () => value });
const open = () =>
  fireEvent.click(
    screen.getByRole("button", { name: "Посмотреть элементы альбома" }),
  );
const refresh = () =>
  fireEvent.click(
    screen.getByRole("button", { name: "Обновить элементы альбома" }),
  );
it("shows only on-demand retained observations, not a complete or usable album", async () => {
  const fetch = vi.fn(async (_path: string, _init: RequestInit) =>
    json(observation),
  );
  vi.stubGlobal("fetch", fetch);
  render(<AlbumObservationPanel contentKey={key} />);
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByText(/Состав альбома не подтверждён/)).toBeTruthy();
  open();
  await screen.findByText("Первая подпись");
  expect(screen.getByText(/Видео · сообщение 29 · ревизия 2/)).toBeTruthy();
  expect(screen.getByText(/Удалён у донора/)).toBeTruthy();
  expect(screen.getByText(/Защищён от копирования/)).toBeTruthy();
  expect(screen.getByText(/Защита неизвестна/)).toBeTruthy();
  expect(screen.getByText("Без подписи")).toBeTruthy();
  expect(screen.getByText(/Наблюдаемых элементов: 3/)).toBeTruthy();
  expect(fetch.mock.calls[0][1]).toEqual({
    method: "GET",
    cache: "no-store",
    signal: expect.any(AbortSignal),
  });
  expect(
    screen.queryByRole("button", { name: /Рерайт|Опубликовать|Скачать/ }),
  ).toBeNull();
});
it("clears old observations on failed refresh and permits read-only retry", async () => {
  let fail = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      fail
        ? { ok: false, status: 409, json: async () => ({ detail: "private" }) }
        : json(observation),
    ),
  );
  render(<AlbumObservationPanel contentKey={key} />);
  open();
  await screen.findByText("Первая подпись");
  fail = true;
  refresh();
  expect((await screen.findByRole("alert")).textContent).toContain("HTTP 409");
  expect(screen.queryByText("Первая подпись")).toBeNull();
  expect(screen.queryByText(/private/)).toBeNull();
  fail = false;
  refresh();
  await screen.findByText("Первая подпись");
});
it("one pending read only, abort on key change, and ignore late old response", async () => {
  let finish: (value: unknown) => void = () => {};
  let previousSignal: AbortSignal | undefined;
  const fetch = vi.fn((_path: string, init: RequestInit) => {
    previousSignal = init.signal as AbortSignal;
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  vi.stubGlobal("fetch", fetch);
  const { rerender } = render(<AlbumObservationPanel contentKey={key} />);
  const button = screen.getByRole("button", {
    name: "Посмотреть элементы альбома",
  });
  fireEvent.click(button);
  fireEvent.click(button);
  expect(fetch).toHaveBeenCalledTimes(1);
  rerender(<AlbumObservationPanel contentKey="another-current-revision" />);
  expect(previousSignal?.aborted).toBe(true);
  await act(async () => finish(json(observation)));
  expect(screen.queryByText("Первая подпись")).toBeNull();
  expect(
    screen.getByRole("button", { name: "Посмотреть элементы альбома" }),
  ).toBeTruthy();
});
it("aborts an active read when unmounted", () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_path: string, init: RequestInit) => {
      signal = init.signal as AbortSignal;
      return new Promise(() => {});
    }),
  );
  const { unmount } = render(<AlbumObservationPanel contentKey={key} />);
  open();
  unmount();
  expect(signal?.aborted).toBe(true);
});
it("forged permission is not displayed; corrupted payload does not authorize action", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      json({ ...observation, publication_allowed: true, api_key: "private" }),
    ),
  );
  render(<AlbumObservationPanel contentKey={key} />);
  open();
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Некорректный ответ",
  );
  expect(screen.queryByText("Первая подпись")).toBeNull();
});

it("transport exception containing private data is redacted, never a displayed error body", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new Error("private-key-and-url");
    }),
  );
  render(<AlbumObservationPanel contentKey={key} />);
  open();
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Проверьте доступность API",
  );
  expect(screen.queryByText(/private-key/)).toBeNull();
});

it("known sync gap is reported but never interpreted as a successful source check", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ...observation, source_sync_blocked: true })),
  );
  render(<AlbumObservationPanel contentKey={key} />);
  open();
  expect(await screen.findByText(/Нужна синхронизация источника/)).toBeTruthy();
  expect(screen.getByText(/Состав альбома не подтверждён/)).toBeTruthy();
});
