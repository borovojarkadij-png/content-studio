// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import {
  readPresentation,
  readReviewPhoto,
  readLatestReview,
  writeReview,
} from "./illustrationReviewApi";
import {
  bindingFixture,
  presentationFixture,
  photoBytes,
  reviewFixture,
} from "./illustrationReviewFixtures";

afterEach(() => vi.unstubAllGlobals());
const signal = () => new AbortController().signal;
const token = "synthetic-test-only-review-token-0001";
const etag = '"' + "a".repeat(64) + '"';
const json = (value: unknown) =>
  new Response(JSON.stringify(value), {
    headers: { "Content-Type": "application/json", ETag: etag },
  });

it("reads canonical UTF-8 texts and binds protected photo to the strong validator", async () => {
  const requests: [string, RequestInit][] = [];
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    requests.push([url, init]);
    return url.endsWith("/photo")
      ? new Response(photoBytes, {
          headers: { "Content-Type": "image/png", ETag: etag },
        })
      : json(presentationFixture);
  });
  const context = await readPresentation(4, token, signal());
  expect(context.source_text).toBe("source");
  expect((await readReviewPhoto(4, token, context, signal())).size).toBe(9);
  expect(requests[1][1].headers).toMatchObject({
    Authorization: "Bearer " + token,
    "If-Match": etag,
  });
  expect(
    requests.every(
      ([url, init]) =>
        !url.includes(token) &&
        init.cache === "no-store" &&
        init.credentials === "omit",
    ),
  ).toBe(true);
});

it.each([
  { source_text: "changed source" },
  { draft_text: "changed draft" },
  { binding: { ...bindingFixture, candidate_id: 5 } },
  { channel: { id: 3, title: "foreign", telegram_channel_id: "-100123456" } },
  { license_code: "OWNED" },
  { attribution: " " },
  { injected: "extra" },
  { license_code: ["CC-BY"] },
  { mime_type: ["image/png"] },
  {
    latest_review: {
      ...reviewFixture,
      verdict: ["REJECTED"],
      illustration_acknowledged: false,
    },
  },
  {
    latest_review: {
      ...reviewFixture,
      binding: { ...bindingFixture, candidate_id: 5 },
    },
  },
])(
  "refuses malformed, foreign or digest-mismatched presentation %j",
  async (changes) => {
    vi.stubGlobal("fetch", async () =>
      json({ ...presentationFixture, ...changes }),
    );
    await expect(readPresentation(4, token, signal())).rejects.toThrow();
  },
);

it.each([null, "W/" + etag, "*"])(
  "refuses missing or weak presentation validator %s",
  async (validator) => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(JSON.stringify(presentationFixture), {
          headers: validator ? { ETag: validator } : {},
        }),
    );
    await expect(readPresentation(4, token, signal())).rejects.toThrow();
  },
);

it.each(["bytes", "mime", "etag", "oversized"])(
  "refuses invalid protected preview %s",
  async (damage) => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(
          damage === "oversized"
            ? new Uint8Array(16 * 1024 * 1024 + 1)
            : damage === "bytes"
              ? new Uint8Array([1, 2])
              : photoBytes,
          {
            headers: {
              "Content-Type": damage === "mime" ? "text/html" : "image/png",
              ETag: damage === "etag" ? '"stale"' : etag,
            },
          },
        ),
    );
    await expect(
      readReviewPhoto(
        4,
        token,
        { ...presentationFixture, etag } as never,
        signal(),
      ),
    ).rejects.toThrow();
  },
);

it("reads immutable latest review without requesting eligible presentation", async () => {
  vi.stubGlobal("fetch", async (url: string) => {
    expect(url.endsWith("/latest-review")).toBe(true);
    return json({ latest_review: { ...reviewFixture, revoked: true } });
  });
  expect((await readLatestReview(4, token, signal()))?.revoked).toBe(true);
});

it("requires response to match the exact submitted review and never exposes transport secrets", async () => {
  vi.stubGlobal("fetch", async () =>
    json({ ...reviewFixture, verdict: "UNCERTAIN" }),
  );
  const operation = {
    displayed_binding: bindingFixture,
    operation_key: "synthetic-op-1",
    review_note: reviewFixture.review_note,
    verdict: "APPROVED_ILLUSTRATION",
    illustration_acknowledged: true,
  } as const;
  await expect(writeReview(4, token, operation, signal())).rejects.toThrow();
  vi.stubGlobal("fetch", async () => {
    throw new Error(token);
  });
  await expect(readLatestReview(4, token, signal())).rejects.toThrow("Сеть");
});
