const gates = ["READY_SNAPSHOT", "MANUAL", "BLOCKED", "NOT_PENDING"] as const;
const states = [
  "QUEUED",
  "RUNNING",
  "SUCCEEDED",
  "REVIEW",
  "BLOCKED",
  "FAILED",
] as const;
const reasons = [
  "SEMANTIC_REWRITE_JOB_INVALID",
  "EDITORIAL_HARD_CONSTRAINT_BLOCKED",
  "SEMANTIC_DRAFT_NOT_PENDING_OR_MISMATCHED",
  "SOURCE_REVISION_NOT_CURRENT_OR_MISSING",
  "SEMANTIC_AUTOMATIC_POLICY_DISABLED",
  "SEMANTIC_VERIFIER_NOT_QUALIFIED",
  "FACT_PRESERVATION_BLOCKED",
  "CURRENT_SEMANTIC_GUARD_BLOCKED",
] as const;
export type SemanticStatus = {
  rewrite_output_id: number;
  output_channel_id: number;
  approval_state: "PENDING" | "APPROVED" | "REJECTED";
  current_gate: (typeof gates)[number];
  reason_code: (typeof reasons)[number] | null;
  network_checked: false;
  execution_authorized: false;
  worker_enabled: null;
  policy_mode: "MANUAL" | "VERIFIED";
  configured_release_id: number | null;
  qualified_release: boolean;
  latest_job: null | {
    id: number;
    state: (typeof states)[number];
    attempts: number;
    max_attempts: 2;
    release_id: number;
    binding_current: boolean | null;
    available_at: string;
    lease_expires_at: string | null;
    lease_expired: boolean;
  };
};
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const exact = (value: Record<string, unknown>, keys: string[]) =>
  Object.keys(value).length === keys.length &&
  Object.keys(value).every((key) => keys.includes(key));
const id = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0;
const date = (value: unknown) =>
  typeof value === "string" &&
  /^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
  Number.isFinite(Date.parse(value));

export async function loadSemanticStatus(
  outputId: number,
  channelId: number,
  signal: AbortSignal,
): Promise<SemanticStatus> {
  if (!id(outputId) || !id(channelId))
    throw new Error("Некорректный ID варианта или канала");
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/rewrite-outputs/${outputId}/semantic-status`,
    { method: "GET", cache: "no-store", signal },
  );
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  const invalid = () => {
    throw new Error("Некорректный ответ состояния проверки фактов");
  };
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    return invalid();
  }
  if (!object(value)) return invalid();
  if (
    !exact(value, [
      "rewrite_output_id",
      "output_channel_id",
      "approval_state",
      "current_gate",
      "reason_code",
      "network_checked",
      "execution_authorized",
      "worker_enabled",
      "policy_mode",
      "configured_release_id",
      "qualified_release",
      "latest_job",
    ]) ||
    value.rewrite_output_id !== outputId ||
    value.output_channel_id !== channelId ||
    typeof value.approval_state !== "string" ||
    !["PENDING", "APPROVED", "REJECTED"].includes(value.approval_state) ||
    !gates.includes(value.current_gate as SemanticStatus["current_gate"]) ||
    (value.reason_code !== null &&
      !reasons.includes(value.reason_code as (typeof reasons)[number])) ||
    value.network_checked !== false ||
    value.execution_authorized !== false ||
    value.worker_enabled !== null ||
    typeof value.policy_mode !== "string" ||
    !["MANUAL", "VERIFIED"].includes(value.policy_mode) ||
    (value.configured_release_id !== null &&
      !id(value.configured_release_id)) ||
    typeof value.qualified_release !== "boolean" ||
    (value.qualified_release && value.configured_release_id === null) ||
    (value.current_gate === "READY_SNAPSHOT" &&
      (value.approval_state !== "PENDING" ||
        value.reason_code !== null ||
        value.policy_mode !== "VERIFIED" ||
        !value.qualified_release ||
        value.configured_release_id === null)) ||
    (value.current_gate !== "READY_SNAPSHOT" && value.reason_code === null)
  )
    return invalid();
  const job = value.latest_job;
  if (job !== null) {
    if (
      !object(job) ||
      !exact(job, [
        "id",
        "state",
        "attempts",
        "max_attempts",
        "release_id",
        "binding_current",
        "available_at",
        "lease_expires_at",
        "lease_expired",
      ]) ||
      !id(job.id) ||
      !id(job.release_id) ||
      !states.includes(job.state as (typeof states)[number]) ||
      !Number.isSafeInteger(job.attempts) ||
      Number(job.attempts) < 0 ||
      Number(job.attempts) > 2 ||
      job.max_attempts !== 2 ||
      ![null, true, false].includes(job.binding_current as boolean | null) ||
      !date(job.available_at) ||
      (job.lease_expires_at !== null && !date(job.lease_expires_at)) ||
      typeof job.lease_expired !== "boolean" ||
      (job.state === "RUNNING" &&
        (Number(job.attempts) < 1 || job.lease_expires_at === null)) ||
      (job.lease_expired && job.state !== "RUNNING") ||
      (job.binding_current === true &&
        (value.current_gate !== "READY_SNAPSHOT" ||
          job.release_id !== value.configured_release_id))
    )
      return invalid();
  }
  return value as SemanticStatus;
}
