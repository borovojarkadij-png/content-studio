import { afterEach, expect, it, vi } from "vitest";
import { deliveryStatus } from "./deliveryApi";

afterEach(() => vi.unstubAllGlobals());
const pending = {
  planned_id: 4,
  candidate_id: 8,
  output_channel_id: 1,
  job_id: null,
  state: "NOT_QUEUED",
  attempts: 0,
  sent_message_id: null,
  completed_at: null,
  reason_code: null,
  live_publication_available: false,
};

it("requires exact plan identity, valid persisted state and receipt before accepting success", async () => {
  for (const payload of [
    { ...pending, planned_id: 5 },
    { ...pending, job_id: 1, state: "SUCCEEDED" },
    { ...pending, state: "PUBLISHED" },
    { ...pending, attempts: 3 },
    { ...pending, sent_message_id: 101 },
    { ...pending, live_publication_available: true },
    { ...pending, job_id: 1, state: "SENDING", attempts: 0 },
  ]) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => payload })),
    );
    await expect(
      deliveryStatus(4, new AbortController().signal),
    ).rejects.toThrow("контракт");
  }
});

it("loads read-only status and accepts a bounded exact acknowledgement", async () => {
  let url = "";
  let method: string | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, init: RequestInit) => {
      url = path;
      method = init.method;
      return {
        ok: true,
        json: async () => ({
          ...pending,
          job_id: 2,
          state: "SUCCEEDED",
          attempts: 1,
          sent_message_id: 101,
          completed_at: "2026-10-08T00:00:00+00:00",
        }),
      };
    }),
  );
  const result = await deliveryStatus(4, new AbortController().signal);
  expect(result.sent_message_id).toBe(101);
  expect(url).toBe("/api/telegram/planned-publications/4/delivery-status");
  expect(method).toBe("GET");
});
