import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MediaPreparation } from "./MediaPreparation";
// @ts-expect-error Vitest supplies real Node Web Crypto for the browser API contract.
import { webcrypto } from "node:crypto";
import {
  presentationFixture,
  photoBytes,
  reviewFixture,
} from "./illustrationReviewFixtures";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("post-review media refresh cannot replace a changed candidate with a late old status", async () => {
  vi.stubGlobal("crypto", webcrypto);
  vi.spyOn(URL, "createObjectURL").mockReturnValue(
    "blob:synthetic-parent-review",
  );
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  let reads = 0;
  let finish!: (value: unknown) => void;
  let oldSignal!: AbortSignal;
  const etag = '"' + "a".repeat(64) + '"';
  vi.stubGlobal("fetch", async (path: string, init: RequestInit) => {
    if (path.includes("illustration-review")) {
      if (path.endsWith("/photo"))
        return new Response(photoBytes, {
          headers: { ETag: etag, "Content-Type": "image/png" },
        });
      const value = path.endsWith("/presentation")
        ? presentationFixture
        : path.endsWith("/latest-review")
          ? { latest_review: reviewFixture }
          : reviewFixture;
      return new Response(JSON.stringify(value), {
        headers: { ETag: etag, "Content-Type": "application/json" },
      });
    }
    if (path.includes("/5/"))
      return json({
        ...pending,
        candidate_id: 5,
        media_policy: "REUSE_SOURCE",
        acquisition_mode: "REUSE_SOURCE",
        illustration: false,
      });
    reads++;
    if (reads === 2) {
      oldSignal = init.signal as AbortSignal;
      return new Promise((resolve) => {
        finish = resolve;
      });
    }
    return json(pending);
  });
  const view = render(<MediaPreparation candidateId={4} />);
  fireEvent.change(await screen.findByLabelText("Токен редактора"), {
    target: { value: "synthetic-test-only-review-token-0001" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Загрузить контекст проверки" }),
  );
  fireEvent.load(
    await screen.findByRole("img", {
      name: "Проверяемая иллюстрация, не фото события",
    }),
  );
  fireEvent.change(screen.getByLabelText("Комментарий проверки"), {
    target: { value: reviewFixture.review_note },
  });
  fireEvent.click(screen.getByRole("checkbox", { name: /Это иллюстрация/ }));
  fireEvent.click(screen.getByRole("button", { name: "Одобрить иллюстрацию" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  view.rerender(<MediaPreparation candidateId={5} />);
  expect(await screen.findByText("Исходное фото донора")).toBeTruthy();
  expect(oldSignal.aborted).toBe(true);
  finish(json(pending));
  await waitFor(() =>
    expect(screen.queryByLabelText("Токен редактора")).toBeNull(),
  );
  expect(screen.queryByText(/Проверка сохранена/)).toBeNull();
});
const pending = {
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
const json = (value: unknown, status = 200) => ({
  ok: true,
  status,
  json: async () => value,
});

it("explains library publication hold without implying a manual glance grants approval", async () => {
  const fetch = vi.fn(async () =>
    json({
      ...pending,
      publication_hold_reason_code: "HUMAN_ILLUSTRATION_REVIEW_REQUIRED",
    }),
  );
  vi.stubGlobal("fetch", fetch);
  render(<MediaPreparation candidateId={4} />);
  expect(
    await screen.findByText(/Публикация иллюстраций заблокирована/),
  ).toBeTruthy();
  expect(
    screen.getByText(
      /Требуется актуальная проверка иллюстрации авторизованным редактором/,
    ),
  ).toBeTruthy();
  expect(screen.queryByText(/Проверьте соответствие фото вручную/)).toBeNull();
  expect(fetch.mock.calls).toHaveLength(1);
  expect(screen.getByLabelText("Токен редактора")).toBeTruthy();
});

it("queues once and shows durable queue state, never download or publication success", async () => {
  let writes = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        writes++;
        return json(
          { ...pending, job_id: 8, state: "QUEUED", queue_allowed: false },
          202,
        );
      }
      return json(pending);
    }),
  );
  render(<MediaPreparation candidateId={4} />);
  const queue = await screen.findByRole("button", {
    name: "Подготовить медиа 4",
  });
  await waitFor(() =>
    expect((queue as HTMLButtonElement).disabled).toBe(false),
  );
  fireEvent.click(queue);
  fireEvent.click(queue);
  expect(await screen.findByText("В очереди · попыток: 0/2")).toBeTruthy();
  expect(writes).toBe(1);
  expect(screen.queryByRole("img")).toBeNull();
  expect(screen.getByText(/Worker включается отдельно/)).toBeTruthy();
});

it("cleared narrow review hold still explains independent publication checks", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      json({
        ...pending,
        job_id: 8,
        state: "SUCCEEDED",
        selected_allowed: true,
        publication_hold_reason_code: null,
        asset: {
          id: 1,
          storage_key: "library/test.png",
          sha256: "a".repeat(64),
          mime_type: "image/png",
          origin: "LICENSED_LIBRARY",
          source_content_key: null,
          license_code: "CC0",
          attribution: "Synthetic library",
          tags: [],
        },
      }),
    ),
  );
  render(<MediaPreparation candidateId={4} />);
  expect(
    await screen.findByText(/не подтверждение готовности к публикации/),
  ).toBeTruthy();
  expect(screen.queryByText(/Публикация иллюстраций заблокирована/)).toBeNull();
  expect(
    screen.queryByRole("button", { name: /Подтвердить|Отправить/ }),
  ).toBeNull();
});

it("queue failure removes stale eligibility and refreshes before allowing another attempt", async () => {
  let revoked = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        revoked = true;
        return { ok: false, status: 409 };
      }
      return json({
        ...pending,
        queue_allowed: !revoked,
        queue_reason_code: revoked ? "CURRENT_MEDIA_GATE_BLOCKED" : null,
      });
    }),
  );
  render(<MediaPreparation candidateId={4} />);
  const queue = await screen.findByRole("button", {
    name: "Подготовить медиа 4",
  });
  await waitFor(() =>
    expect((queue as HTMLButtonElement).disabled).toBe(false),
  );
  fireEvent.click(queue);
  expect(await screen.findByText(/HTTP 409/)).toBeTruthy();
  expect((queue as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Обновить медиа 4" }));
  expect(await screen.findByText(/CURRENT_MEDIA_GATE_BLOCKED/)).toBeTruthy();
});

it("late old-candidate status cannot replace a newly selected candidate", async () => {
  let resolveOld: (value: unknown) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path.includes("/4/"))
        return new Promise((resolve) => {
          resolveOld = resolve;
        });
      return json({
        ...pending,
        candidate_id: 5,
        media_policy: "REUSE_SOURCE",
        acquisition_mode: "REUSE_SOURCE",
        illustration: false,
      });
    }),
  );
  const view = render(<MediaPreparation candidateId={4} />);
  view.rerender(<MediaPreparation candidateId={5} />);
  expect(await screen.findByText("Исходное фото донора")).toBeTruthy();
  resolveOld(json(pending));
  await waitFor(() =>
    expect(screen.queryByText("Иллюстрация из открытой библиотеки")).toBeNull(),
  );
});

it("historical success with revoked selection never requests or displays a preview", async () => {
  const fetch = vi.fn(async () =>
    json({
      ...pending,
      job_id: 8,
      state: "SUCCEEDED",
      attempts: 1,
      queue_allowed: false,
      reason_code: "CURRENT_MEDIA_GATE_BLOCKED",
    }),
  );
  vi.stubGlobal("fetch", fetch);
  render(<MediaPreparation candidateId={4} />);
  expect(await screen.findByText(/CURRENT_MEDIA_GATE_BLOCKED/)).toBeTruthy();
  expect(
    screen.queryByRole("button", { name: "Предпросмотр медиа 4" }),
  ).toBeNull();
  expect(screen.queryByRole("img")).toBeNull();
  expect(fetch.mock.calls.length).toBe(1);
});

it("current selected asset offers preview, and a revoked preview cannot leave an old image", async () => {
  const asset = {
    id: 1,
    storage_key: "library/test.png",
    sha256: "a".repeat(64),
    mime_type: "image/png",
    origin: "LICENSED_LIBRARY",
    source_content_key: null,
    license_code: "CC0",
    attribution: "Test library",
    tags: [],
  };
  let statusReads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) => {
      if (path.endsWith("media-preview")) return { ok: false, status: 409 };
      statusReads++;
      return json({
        ...pending,
        job_id: 8,
        state: "SUCCEEDED",
        attempts: 1,
        queue_allowed: false,
        selected_allowed: statusReads === 1,
        asset: statusReads === 1 ? asset : null,
      });
    }),
  );
  render(<MediaPreparation candidateId={4} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Предпросмотр медиа 4" }),
  );
  expect(await screen.findByText(/HTTP 409/)).toBeTruthy();
  expect(screen.queryByRole("img")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Обновить медиа 4" }));
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Предпросмотр медиа 4" }),
    ).toBeNull(),
  );
});
