import { afterEach, expect, it, vi } from "vitest";
import { loadInbox } from "./api";
import { canProcess } from "./studio";

afterEach(() => vi.unstubAllGlobals());

it.each([true, "true", 1, null])(
  "observed album metadata %j never grants historical PASS permission",
  async (album) => {
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
              source_text: "Grouped caption",
              editorial_status: "PASS",
              rewrite_allowed: true,
              editorial_reason_codes: [],
              source_deleted: false,
              album_observed: album,
            },
          ],
        }),
      }),
    );
    if (album !== true) {
      await expect(loadInbox(new AbortController().signal)).rejects.toThrow(
        "контракту входящих",
      );
    } else {
      const [post] = await loadInbox(new AbortController().signal);
      expect(post.albumObserved).toBe(true);
      expect(post.rewriteAllowed).toBe(false);
      expect(
        canProcess({ ...post, rewriteAllowed: true, state: "На проверке" }),
      ).toBe(false);
    }
  },
);

it("unresolved sync state overrides contradictory historical PASS permission", async () => {
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
            source_text: "Источник с gap",
            editorial_status: "PASS",
            rewrite_allowed: true,
            editorial_reason_codes: [],
            source_deleted: false,
          },
        ],
      }),
    }),
  );
  const [post] = await loadInbox(new AbortController().signal);
  expect(post.state).toBe("Нужна синхронизация");
  expect(post.rewriteAllowed).toBe(false);
  expect(post.editorial).toBe("PASS");
});

it("malformed deletion flag fails closed instead of enabling historical PASS", async () => {
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
            source_text: "Synthetic original",
            editorial_status: "PASS",
            rewrite_allowed: true,
            editorial_reason_codes: [],
            source_deleted: "true",
          },
        ],
      }),
    }),
  );
  await expect(loadInbox(new AbortController().signal)).rejects.toThrow(
    "контракту входящих",
  );
});

it("legacy state-only deletion blocks processing without fabricated editorial rejection", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [
          {
            source_key: "1:-1001234567890:20",
            state: "SOURCE_DELETED",
            revision_number: 1,
            source_text: "Synthetic original",
            editorial_status: "PASS",
            rewrite_allowed: true,
            editorial_reason_codes: [],
          },
        ],
      }),
    }),
  );
  const [post] = await loadInbox(new AbortController().signal);
  expect(post.state).toBe("Удалён у донора");
  expect(post.editorial).toBe("PASS");
  expect(post.rewriteAllowed).toBe(false);
});
