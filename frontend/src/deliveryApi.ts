const states = [
  "NOT_QUEUED",
  "QUEUED",
  "CLAIMED",
  "SENDING",
  "SUCCEEDED",
  "BLOCKED",
  "FAILED",
  "NEEDS_RECONCILIATION",
] as const;
export type DeliveryStatus = {
  planned_id: number;
  candidate_id: number;
  output_channel_id: number;
  job_id: number | null;
  state: (typeof states)[number];
  attempts: number;
  sent_message_id: number | null;
  completed_at: string | null;
  reason_code: string | null;
  live_publication_available: false;
};
const id = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0;
function valid(value: unknown, plannedId: number): value is DeliveryStatus {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  if (
    row.planned_id !== plannedId ||
    !id(row.candidate_id) ||
    !id(row.output_channel_id) ||
    !states.includes(row.state as DeliveryStatus["state"]) ||
    !Number.isInteger(row.attempts) ||
    Number(row.attempts) < 0 ||
    Number(row.attempts) > 2 ||
    (row.reason_code !== null &&
      (typeof row.reason_code !== "string" ||
        !/^[A-Z0-9_]{1,64}$/.test(row.reason_code))) ||
    row.live_publication_available !== false
  )
    return false;
  if (row.state === "NOT_QUEUED")
    return (
      row.job_id === null &&
      row.attempts === 0 &&
      row.sent_message_id === null &&
      row.completed_at === null &&
      row.reason_code === null
    );
  if (!id(row.job_id)) return false;
  if (
    ["CLAIMED", "SENDING", "SUCCEEDED", "NEEDS_RECONCILIATION"].includes(
      String(row.state),
    ) &&
    Number(row.attempts) < 1
  )
    return false;
  if (row.state === "SUCCEEDED")
    return (
      id(row.sent_message_id) &&
      Number(row.sent_message_id) <= 2147483647 &&
      typeof row.completed_at === "string" &&
      /(Z|[+-]\d{2}:\d{2})$/.test(row.completed_at) &&
      Number.isFinite(Date.parse(row.completed_at))
    );
  return row.sent_message_id === null && row.completed_at === null;
}
export async function deliveryStatus(
  plannedId: number,
  signal: AbortSignal,
): Promise<DeliveryStatus> {
  if (!id(plannedId)) throw new Error("Некорректный идентификатор публикации");
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/planned-publications/${plannedId}/delivery-status`,
    { method: "GET", signal, cache: "no-store" },
  );
  if (!response.ok)
    throw new Error(`API доставки вернул HTTP ${response.status}`);
  const payload: unknown = await response.json();
  if (!valid(payload, plannedId))
    throw new Error("Ответ API не соответствует контракту доставки");
  return payload;
}
