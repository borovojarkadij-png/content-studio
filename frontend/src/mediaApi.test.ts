// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { mediaStatus, mediaPreview } from "./mediaApi";

afterEach(() => vi.unstubAllGlobals());
export const pendingMedia = {
  candidate_id: 4,
  job_id: null,
  state: "NOT_QUEUED",
  attempts: 0,
  media_policy: "LICENSED_LIBRARY",
  acquisition_mode: "LICENSED_LIBRARY",
  queue_allowed: true,
  queue_reason_code: null,
  selected_allowed: false,
  asset: null,
  reason_code: null,
  illustration: true,
};
const response = (value: unknown, status = 200) => ({
  ok: true,
  status,
  json: async () => value,
});

it("binds media status identity and rejects fabricated selection and attempts", async () => {
  for (const payload of [
    { ...pendingMedia, candidate_id: 5 },
    { ...pendingMedia, selected_allowed: true },
    { ...pendingMedia, attempts: 3 },
    { ...pendingMedia, state: "PUBLISHED" },
  ]) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response(payload)),
    );
    await expect(mediaStatus(4, new AbortController().signal)).rejects.toThrow(
      "контракт",
    );
  }
});

it("queue requires actual HTTP 202 and returns persisted state without claiming download", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response(pendingMedia, 200)),
  );
  await expect(
    mediaStatus(4, new AbortController().signal, true),
  ).rejects.toThrow("202");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      response(
        { ...pendingMedia, job_id: 8, state: "QUEUED", queue_allowed: false },
        202,
      ),
    ),
  );
  expect((await mediaStatus(4, new AbortController().signal, true)).state).toBe(
    "QUEUED",
  );
});

it("preview rejects wrong MIME or bytes changed since the selected status", async () => {
  const asset = {
    id: 1,
    storage_key: "library/test.png",
    sha256: "a".repeat(64),
    mime_type: "image/png" as const,
    origin: "LICENSED_LIBRARY" as const,
    source_content_key: null,
    license_code: "CC0" as const,
    attribution: "",
    tags: [],
  };
  for (const mime of ["text/html", "image/png"]) {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(new Uint8Array([1, 2, 3]), {
            headers: { "Content-Type": mime },
          }),
      ),
    );
    await expect(
      mediaPreview(4, asset, new AbortController().signal),
    ).rejects.toThrow(/предпросмотр/);
  }
});
