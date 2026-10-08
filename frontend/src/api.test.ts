import { afterEach, expect, it, vi } from "vitest";
import { loadInbox } from "./api";

afterEach(() => vi.unstubAllGlobals());

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
