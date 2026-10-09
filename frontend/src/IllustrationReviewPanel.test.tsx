// @ts-expect-error Vitest supplies Node's real Web Crypto; browser source has no Node dependency.
import { webcrypto } from "node:crypto";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { IllustrationReviewPanel } from "./IllustrationReviewPanel";
import {
  presentationFixture,
  photoBytes,
  reviewFixture,
} from "./illustrationReviewFixtures";

const token = "synthetic-test-only-review-token-0001";
const etag = '"' + "a".repeat(64) + '"';
const json = (v: unknown, status = 200) =>
  new Response(JSON.stringify(v), {
    status,
    headers: { ETag: etag, "Content-Type": "application/json" },
  });
let latest: unknown;
let writes: {
  url: string;
  body: Record<string, unknown>;
  signal: AbortSignal;
}[];
let writeResponse: (
  body: Record<string, unknown>,
  url: string,
) => Promise<Response>;
beforeEach(() => {
  latest = null;
  writes = [];
  vi.stubGlobal("crypto", webcrypto);
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:synthetic-review");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  writeResponse = async (body, url) => {
    const record = url.endsWith("/revocations")
      ? {
          ...reviewFixture,
          id: 9,
          record_kind: "REVOCATION",
          revokes_review_id: 8,
          verdict: null,
          illustration_acknowledged: null,
          review_note: body.review_note,
        }
      : {
          ...reviewFixture,
          verdict: body.verdict,
          illustration_acknowledged: body.illustration_acknowledged,
          review_note: body.review_note,
        };
    latest = url.endsWith("/revocations")
      ? { ...reviewFixture, revoked: true }
      : record;
    return json(record);
  };
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    if (init.method === "POST") {
      const body = JSON.parse(String(init.body));
      writes.push({ url, body, signal: init.signal as AbortSignal });
      return writeResponse(body, url);
    }
    if (url.endsWith("/latest-review")) return json({ latest_review: latest });
    if (url.endsWith("/photo"))
      return new Response(photoBytes, {
        headers: { "Content-Type": "image/png", ETag: etag },
      });
    return json({ ...presentationFixture, latest_review: latest });
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
async function load() {
  fireEvent.change(screen.getByLabelText("Токен редактора"), {
    target: { value: token },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Загрузить контекст проверки" }),
  );
  const img = await screen.findByRole("img", {
    name: "Проверяемая иллюстрация, не фото события",
  });
  fireEvent.load(img);
}
const note = () =>
  fireEvent.change(screen.getByLabelText("Комментарий проверки"), {
    target: { value: "Illustration, not event photo" },
  });
const acknowledge = () =>
  fireEvent.click(
    screen.getByRole("checkbox", {
      name: /Это иллюстрация, а не фотография события/,
    }),
  );

it("requires exact loaded photo, bounded note and explicit illustration acknowledgment", async () => {
  render(<IllustrationReviewPanel candidateId={4} onSaved={async () => {}} />);
  const approve = screen.getByRole("button", { name: "Одобрить иллюстрацию" });
  expect((approve as HTMLButtonElement).disabled).toBe(true);
  await load();
  note();
  expect((approve as HTMLButtonElement).disabled).toBe(true);
  acknowledge();
  expect((approve as HTMLButtonElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText("Комментарий проверки"), {
    target: { value: "x".repeat(2049) },
  });
  expect((approve as HTMLButtonElement).disabled).toBe(true);
  note();
  expect(screen.getByText("source")).toBeTruthy();
  expect(screen.getByText("draft")).toBeTruthy();
  expect(screen.getByText(/Synthetic credit/)).toBeTruthy();
  fireEvent.click(approve);
  fireEvent.click(approve);
  await screen.findByText(/Проверка сохранена/);
  expect(writes).toHaveLength(1);
  expect(writes[0].body).toMatchObject({
    displayed_binding: presentationFixture.binding,
    verdict: "APPROVED_ILLUSTRATION",
    illustration_acknowledged: true,
    review_note: "Illustration, not event photo",
  });
  expect(writes[0].body.operation_key).toMatch(
    /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/,
  );
});

it.each(["Отклонить иллюстрацию", "Не уверен"])(
  "records %s without illustration permission",
  async (name) => {
    render(
      <IllustrationReviewPanel candidateId={4} onSaved={async () => {}} />,
    );
    await load();
    note();
    fireEvent.click(screen.getByRole("button", { name }));
    await screen.findByText(/Проверка сохранена/);
    expect(writes[0].body.verdict).toBe(
      name === "Не уверен" ? "UNCERTAIN" : "REJECTED",
    );
    expect(writes[0].body.illustration_acknowledged).toBe(false);
  },
);

it("keeps exact uncertain operation for explicit retry and never resubmits automatically", async () => {
  let attempts = 0;
  const normal = writeResponse;
  writeResponse = async (body, url) => {
    attempts++;
    if (attempts === 1) throw new Error(token);
    return normal(body, url);
  };
  render(<IllustrationReviewPanel candidateId={4} onSaved={async () => {}} />);
  await load();
  note();
  acknowledge();
  fireEvent.click(screen.getByRole("button", { name: "Одобрить иллюстрацию" }));
  expect(await screen.findByText(/Результат записи неизвестен/)).toBeTruthy();
  expect(writes).toHaveLength(1);
  expect(screen.queryByText(token)).toBeNull();
  fireEvent.click(
    screen.getByRole("button", { name: "Повторить ту же операцию" }),
  );
  await screen.findByText(/Проверка сохранена/);
  expect(writes).toHaveLength(2);
  expect(writes[1].body).toEqual(writes[0].body);
});

it("discards late write after token change and clears canonical photo and token on disconnect", async () => {
  let resolve!: (r: Response) => void;
  writeResponse = () =>
    new Promise((r) => {
      resolve = r;
    });
  const saved = vi.fn(async () => {});
  render(<IllustrationReviewPanel candidateId={4} onSaved={saved} />);
  await load();
  note();
  acknowledge();
  fireEvent.click(screen.getByRole("button", { name: "Одобрить иллюстрацию" }));
  fireEvent.change(screen.getByLabelText("Токен редактора"), {
    target: { value: "synthetic-test-only-rotated-token-0002" },
  });
  expect(writes[0].signal.aborted).toBe(true);
  resolve(json(reviewFixture));
  await waitFor(() =>
    expect(screen.queryByText(/Проверка сохранена/)).toBeNull(),
  );
  expect(saved).not.toHaveBeenCalled();
  expect(screen.queryByRole("img")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Отключить проверку" }));
  expect(
    (screen.getByLabelText("Токен редактора") as HTMLInputElement).value,
  ).toBe("");
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:synthetic-review");
});

it("candidate change and unmount abort reads without token persistence", async () => {
  const signals: AbortSignal[] = [];
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    signals.push(init.signal as AbortSignal);
    return new Promise(() => {});
  });
  const local = vi.spyOn(Storage.prototype, "setItem");
  const view = render(
    <IllustrationReviewPanel candidateId={4} onSaved={async () => {}} />,
  );
  const input = screen.getByLabelText("Токен редактора") as HTMLInputElement;
  expect(input.type).toBe("password");
  expect(input.autocomplete).toBe("off");
  fireEvent.change(input, { target: { value: token } });
  fireEvent.click(
    screen.getByRole("button", { name: "Загрузить контекст проверки" }),
  );
  view.rerender(
    <IllustrationReviewPanel candidateId={5} onSaved={async () => {}} />,
  );
  expect(signals[0].aborted).toBe(true);
  expect(input.value).toBe("");
  fireEvent.change(input, { target: { value: token } });
  fireEvent.click(
    screen.getByRole("button", { name: "Загрузить контекст проверки" }),
  );
  view.unmount();
  expect(signals[1].aborted).toBe(true);
  expect(local).not.toHaveBeenCalled();
});

it("candidate change during post-save media refresh suppresses old success", async () => {
  let finish!: () => void;
  const saved = () =>
    new Promise<void>((resolve) => {
      finish = resolve;
    });
  const view = render(
    <IllustrationReviewPanel candidateId={4} onSaved={saved} />,
  );
  await load();
  note();
  acknowledge();
  fireEvent.click(screen.getByRole("button", { name: "Одобрить иллюстрацию" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  view.rerender(<IllustrationReviewPanel candidateId={5} onSaved={saved} />);
  finish();
  await waitFor(() =>
    expect(screen.queryByText(/Проверка сохранена/)).toBeNull(),
  );
  expect(
    (screen.getByLabelText("Токен редактора") as HTMLInputElement).value,
  ).toBe("");
  expect(screen.queryByRole("img")).toBeNull();
});

it("late old read cannot restore context after token change", async () => {
  let finish!: (r: Response) => void;
  let aborted!: AbortSignal;
  vi.stubGlobal("fetch", (_url: string, init: RequestInit) => {
    aborted = init.signal as AbortSignal;
    return new Promise<Response>((resolve) => {
      finish = resolve;
    });
  });
  render(<IllustrationReviewPanel candidateId={4} onSaved={async () => {}} />);
  fireEvent.change(screen.getByLabelText("Токен редактора"), {
    target: { value: token },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Загрузить контекст проверки" }),
  );
  fireEvent.change(screen.getByLabelText("Токен редактора"), {
    target: { value: "synthetic-test-only-rotated-token-0002" },
  });
  expect(aborted.aborted).toBe(true);
  finish(json(presentationFixture));
  await waitFor(() => expect(screen.queryByText("source")).toBeNull());
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});

it("write conflict clears photo and forces a new load without automatic or uncertain retry", async () => {
  writeResponse = async () => json({}, 409);
  render(<IllustrationReviewPanel candidateId={4} onSaved={async () => {}} />);
  await load();
  note();
  acknowledge();
  fireEvent.click(screen.getByRole("button", { name: "Одобрить иллюстрацию" }));
  await screen.findByText(/Контекст изменился/);
  expect(screen.queryByRole("img")).toBeNull();
  expect(writes).toHaveLength(1);
  expect(
    screen.queryByRole("button", { name: "Повторить ту же операцию" }),
  ).toBeNull();
  expect(
    (
      screen.getByRole("button", {
        name: "Одобрить иллюстрацию",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});

it("latest immutable review can be revoked while canonical presentation is stale", async () => {
  latest = reviewFixture;
  const normal = globalThis.fetch;
  vi.stubGlobal("fetch", (url: string, init: RequestInit) =>
    url.endsWith("/presentation")
      ? Promise.resolve(json({}, 409))
      : normal(url, init),
  );
  render(<IllustrationReviewPanel candidateId={4} onSaved={async () => {}} />);
  fireEvent.change(screen.getByLabelText("Токен редактора"), {
    target: { value: token },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Загрузить контекст проверки" }),
  );
  await screen.findByText(/Контекст изменился/);
  fireEvent.click(
    screen.getByRole("button", { name: "Прочитать последнюю проверку" }),
  );
  await screen.findByText(/Проверка #8/);
  note();
  fireEvent.click(
    screen.getByRole("button", { name: "Отозвать последнюю проверку" }),
  );
  await screen.findByText(/Отзыв сохранён/);
  expect(writes[0].url).toMatch(/records\/8\/revocations$/);
  expect(screen.queryByRole("img")).toBeNull();
});

it.each([401, 409, 503])(
  "shows honest HTTP %s without saved success or enabled approval",
  async (status) => {
    vi.stubGlobal("fetch", async () => json({ secret: token }, status));
    render(
      <IllustrationReviewPanel candidateId={4} onSaved={async () => {}} />,
    );
    fireEvent.change(screen.getByLabelText("Токен редактора"), {
      target: { value: token },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Загрузить контекст проверки" }),
    );
    await screen.findByText(new RegExp(String(status)));
    expect(screen.queryByText(/Проверка сохранена/)).toBeNull();
    expect(
      (
        screen.getByRole("button", {
          name: "Одобрить иллюстрацию",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  },
);
