import { afterEach, expect, it, vi } from "vitest";
import { loadAlbumObservation } from "./albumObservationApi";

afterEach(() => vi.unstubAllGlobals());
const key = "1:-1001234567890:20:revision:1";
const member = {
  content_key: key,
  message_id: 20,
  revision_number: 1,
  text: "Caption",
  media_type: "photo",
  media_protected: false,
  source_deleted: false,
};
const observation = {
  anchor_content_key: key,
  album_id: "77",
  members: [member],
  membership_complete: false,
  rewrite_allowed: false,
  publication_allowed: false,
  source_sync_blocked: false,
  reason_code: "ALBUM_NORMALIZATION_REQUIRED",
};
const provide = (value: unknown) =>
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => value })),
  );

it("reads exact selected revision without writes, caches or permission inference", async () => {
  const fetch = vi.fn(async () => ({
    ok: true,
    json: async () => observation,
  }));
  vi.stubGlobal("fetch", fetch);
  const signal = new AbortController().signal;
  expect(await loadAlbumObservation(key, signal)).toEqual(observation);
  expect(fetch).toHaveBeenCalledWith(
    `/api/telegram/source-albums?content_key=${encodeURIComponent(key)}`,
    { method: "GET", cache: "no-store", signal },
  );
});

it.each([
  { membership_complete: true },
  { rewrite_allowed: true },
  { publication_allowed: true },
  { anchor_content_key: "foreign" },
  { album_id: "077" },
  { album_id: "9223372036854775808" },
  { members: [] },
  { members: Array(11).fill(member) },
  { members: [member, member] },
  { members: [{ ...member, media_protected: "false" }] },
  { members: [{ ...member, source_deleted: "true" }] },
  { members: [{ ...member, encrypted_session: "private" }] },
  { members: [{ ...member, media_type: "executable" }] },
  { api_key: "private" },
])("refuses unsafe/malformed observation %j", async (change) => {
  provide({ ...observation, ...change });
  await expect(
    loadAlbumObservation(key, new AbortController().signal),
  ).rejects.toThrow("Некорректный ответ наблюдения альбома");
});

it.each(["", "  ", "x".repeat(256), true, null])(
  "invalid key %j is refused before HTTP",
  async (value) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(
      loadAlbumObservation(value as string, new AbortController().signal),
    ).rejects.toThrow("Некорректная ревизия");
    expect(fetch).not.toHaveBeenCalled();
  },
);

it("HTTP failure does not echo private payload or invent a DEMO observation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 409,
      json: async () => ({ detail: "private" }),
    })),
  );
  await expect(
    loadAlbumObservation(key, new AbortController().signal),
  ).rejects.toThrow("HTTP 409");
});

it.each(["0", "-9223372036854775808", "9223372036854775807"])(
  "preserves exact signed64 album identity %s without Number rounding",
  async (album_id) => {
    provide({ ...observation, album_id });
    expect(
      (await loadAlbumObservation(key, new AbortController().signal)).album_id,
    ).toBe(album_id);
  },
);

it.each([
  { members: [{ ...member, message_id: 2147483648 }] },
  { members: [{ ...member, message_id: true }] },
  { members: [{ ...member, revision_number: 0 }] },
  { members: [{ ...member, content_key: "" }] },
  { members: [{ ...member, content_key: "foreign" }] },
  {
    members: [
      { ...member, message_id: 29 },
      { ...member, message_id: 20, content_key: "other" },
    ],
  },
  { album_id: "-0" },
  { album_id: "-9223372036854775809" },
])("refuses incoherent member/identity metadata %j", async (change) => {
  provide({ ...observation, ...change });
  await expect(
    loadAlbumObservation(key, new AbortController().signal),
  ).rejects.toThrow("Некорректный ответ наблюдения альбома");
});
