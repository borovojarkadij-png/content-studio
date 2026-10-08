import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PublicationDelivery } from "./PublicationDelivery";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
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
const json = (value: unknown) => ({ ok: true, json: async () => value });

it("shows unknown delivery honestly, does not offer resend and only uses GET", async () => {
  const methods: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_: string, init: RequestInit) => {
      methods.push(init.method ?? "GET");
      return json({
        ...pending,
        job_id: 3,
        attempts: 1,
        state: "NEEDS_RECONCILIATION",
        reason_code: "PUBLICATION_SEND_OUTCOME_UNKNOWN",
      });
    }),
  );
  render(<PublicationDelivery plannedId={4} />);
  expect(await screen.findByText(/Результат отправки неизвестен/)).toBeTruthy();
  expect(
    screen.getByText(/Повторная отправка запрещена до сверки/),
  ).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain(
    "Повторная отправка запрещена до сверки",
  );
  expect(
    screen.queryByRole("button", { name: /Отправить|Повторить отправку/ }),
  ).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Обновить доставку 4" }));
  await screen.findByText(/Результат отправки неизвестен/);
  expect(methods).toEqual(["GET", "GET"]);
});

it("failed refresh clears previous confirmation rather than displaying stale success", async () => {
  let fail = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      fail
        ? { ok: false, status: 503 }
        : json({
            ...pending,
            job_id: 3,
            attempts: 1,
            state: "SUCCEEDED",
            sent_message_id: 101,
            completed_at: "2026-10-08T00:00:00+00:00",
          }),
    ),
  );
  render(<PublicationDelivery plannedId={4} />);
  expect(await screen.findByText(/Доставка подтверждена/)).toBeTruthy();
  fail = true;
  fireEvent.click(screen.getByRole("button", { name: "Обновить доставку 4" }));
  expect(await screen.findByText(/HTTP 503/)).toBeTruthy();
  expect(screen.queryByText(/Доставка подтверждена/)).toBeNull();
});

it("late old-plan response cannot overwrite the newly selected plan", async () => {
  let resolveOld: (value: unknown) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string) =>
      path.includes("/4/")
        ? new Promise((resolve) => {
            resolveOld = resolve;
          })
        : json({ ...pending, planned_id: 5 }),
    ),
  );
  const view = render(<PublicationDelivery plannedId={4} />);
  view.rerender(<PublicationDelivery plannedId={5} />);
  expect(await screen.findByText(/Задание отправки не создано/)).toBeTruthy();
  resolveOld(
    json({
      ...pending,
      job_id: 3,
      attempts: 1,
      state: "SUCCEEDED",
      sent_message_id: 101,
      completed_at: "2026-10-08T00:00:00+00:00",
    }),
  );
  await waitFor(() =>
    expect(screen.queryByText(/Доставка подтверждена/)).toBeNull(),
  );
});
