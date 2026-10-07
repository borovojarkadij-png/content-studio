export type OutputChannel = {
  id: number;
  telegram_account_id: number;
  telegram_channel_id: number;
  title: string;
};
export type PublicationPlan = {
  id: number;
  output_channel_id: number;
  mode: "MANUAL" | "AUTOMATIC";
  daily_limit: number;
  timezone: string;
  slot_minutes: number[];
};
export type RewriteDraft = {
  id: number;
  rewrite_job_id: number;
  output_channel_id: number;
  content_key: string;
  rewritten_text: string;
  approval_state: "PENDING" | "APPROVED" | "REJECTED";
  editorial_status: string | null;
  approve_allowed: boolean;
};
export type PlannedPublication = {
  id: number;
  candidate_id: number;
  output_channel_id: number;
  content_key: string;
  scheduled_for: string;
  state: string;
  editorial_allowed: boolean;
};
type Row = Record<string, unknown>;
const row = (value: unknown): value is Row =>
  value !== null && typeof value === "object";
const id = (value: unknown): value is number =>
  Number.isSafeInteger(value) && Number(value) > 0;
const isChannel = (value: unknown): value is OutputChannel =>
  row(value) &&
  id(value.id) &&
  id(value.telegram_account_id) &&
  Number.isSafeInteger(value.telegram_channel_id) &&
  typeof value.title === "string";
const isPlan = (value: unknown): value is PublicationPlan =>
  row(value) &&
  id(value.id) &&
  id(value.output_channel_id) &&
  ["MANUAL", "AUTOMATIC"].includes(String(value.mode)) &&
  id(value.daily_limit) &&
  value.daily_limit <= 24 &&
  typeof value.timezone === "string" &&
  Array.isArray(value.slot_minutes) &&
  value.slot_minutes.length >= value.daily_limit &&
  value.slot_minutes.every(
    (minute: unknown) =>
      Number.isInteger(minute) && Number(minute) >= 0 && Number(minute) < 1440,
  );
const isDraft = (value: unknown): value is RewriteDraft =>
  row(value) &&
  id(value.id) &&
  id(value.rewrite_job_id) &&
  id(value.output_channel_id) &&
  typeof value.content_key === "string" &&
  typeof value.rewritten_text === "string" &&
  ["PENDING", "APPROVED", "REJECTED"].includes(String(value.approval_state)) &&
  (typeof value.editorial_status === "string" ||
    value.editorial_status === null) &&
  typeof value.approve_allowed === "boolean";
const isPublication = (value: unknown): value is PlannedPublication =>
  row(value) &&
  id(value.id) &&
  id(value.candidate_id) &&
  id(value.output_channel_id) &&
  typeof value.content_key === "string" &&
  typeof value.state === "string" &&
  typeof value.scheduled_for === "string" &&
  Number.isFinite(Date.parse(value.scheduled_for)) &&
  typeof value.editorial_allowed === "boolean";

async function request(path: string, init: RequestInit): Promise<unknown> {
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/${path}`,
    init,
  );
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  return response.json();
}
async function list<T>(
  path: string,
  validate: (value: unknown) => value is T,
  signal: AbortSignal,
): Promise<T[]> {
  const payload = await request(path, { signal });
  if (
    !row(payload) ||
    !Array.isArray(payload.items) ||
    !payload.items.every(validate)
  )
    throw new Error("Ответ API не соответствует контракту планировщика");
  return payload.items;
}
const mutation = (
  body: unknown,
  signal: AbortSignal,
  method = "POST",
): RequestInit => ({
  method,
  signal,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export type RewriteStyle = "NEUTRAL" | "TABLOID";
export async function channelRewriteStyle(
  channelId: number,
  signal: AbortSignal,
  style?: RewriteStyle,
): Promise<RewriteStyle> {
  const payload = await request(
    `output-channels/${channelId}/rewrite-style`,
    style ? mutation({ style }, signal, "PUT") : { signal },
  );
  if (
    !row(payload) ||
    payload.output_channel_id !== channelId ||
    (payload.style !== "NEUTRAL" && payload.style !== "TABLOID")
  )
    throw new Error("Ответ API не соответствует контракту стиля рерайта");
  return payload.style;
}
export const loadOutputChannels = (signal: AbortSignal) =>
  list("output-channels", isChannel, signal);
export const loadPublicationPlans = (signal: AbortSignal) =>
  list("publication-plans", isPlan, signal);
export const loadRewriteDrafts = (channelId: number, signal: AbortSignal) =>
  list(`rewrite-outputs?output_channel_id=${channelId}`, isDraft, signal);
export const loadPlannedPublications = (
  planId: number,
  day: string,
  signal: AbortSignal,
) =>
  list(
    `publication-plans/${planId}/publications?day=${encodeURIComponent(day)}`,
    isPublication,
    signal,
  );

export async function savePublicationPlan(
  channelId: number,
  config: Omit<PublicationPlan, "id" | "output_channel_id">,
  signal: AbortSignal,
): Promise<PublicationPlan> {
  const payload = await request(
    `output-channels/${channelId}/publication-plan`,
    mutation(config, signal, "PUT"),
  );
  if (!isPlan(payload) || payload.output_channel_id !== channelId)
    throw new Error("Ответ API не соответствует контракту планировщика");
  return payload;
}
export async function reviewRewriteDraft(
  draftId: number,
  approve: boolean,
  signal: AbortSignal,
): Promise<void> {
  const payload = await request(
    `rewrite-outputs/${draftId}:${approve ? "approve" : "reject"}`,
    mutation({}, signal),
  );
  if (
    !row(payload) ||
    payload.id !== draftId ||
    payload.approval_state !== (approve ? "APPROVED" : "REJECTED")
  )
    throw new Error("Ответ API не подтверждает результат проверки рерайта");
}
export async function planPublications(
  planId: number,
  day: string,
  signal: AbortSignal,
): Promise<void> {
  const payload = await request(
    `publication-plans/${planId}:plan-day`,
    mutation({ day }, signal),
  );
  if (!row(payload) || !Array.isArray(payload.items))
    throw new Error("Ответ API не соответствует контракту планировщика");
}
