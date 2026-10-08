const states = [
  "READY",
  "NOT_ENFORCED",
  "BASELINE_REQUIRED",
  "LEGACY_SYNC_REQUIRED",
  "SYNC_IN_PROGRESS",
  "RECOVERY_DUE",
  "WAIT_RETRY",
  "GAP_UNRESOLVED",
  "INVALID_BASELINE",
  "ACCOUNT_UNAVAILABLE",
  "COOLDOWN",
] as const;
export type DonorSyncState = (typeof states)[number];
export type DonorSyncStatus = {
  donor_id: number;
  state: DonorSyncState;
  enforcement_enabled: boolean;
  source_processing_blocked: boolean;
  network_checked: false;
  pts: number | null;
  retry_at: string | null;
};
const fields = [
  "donor_id",
  "state",
  "enforcement_enabled",
  "source_processing_blocked",
  "network_checked",
  "pts",
  "retry_at",
];

export async function loadDonorSyncStatus(
  donorId: number,
  signal: AbortSignal,
): Promise<DonorSyncStatus> {
  if (!Number.isSafeInteger(donorId) || donorId <= 0 || donorId > 2147483647)
    throw new Error("Некорректный ID донора");
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/donors/${donorId}/sync-status`,
    {
      method: "GET",
      cache: "no-store",
      signal,
    },
  );
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  const value: unknown = await response.json();
  if (value === null || typeof value !== "object" || Array.isArray(value))
    throw new Error("Некорректный ответ диагностики синхронизации");
  const row = value as Record<string, unknown>;
  const baseline =
    row.pts !== null &&
    Number.isSafeInteger(row.pts) &&
    Number(row.pts) > 0 &&
    Number(row.pts) <= 2147483647;
  if (
    Object.keys(row).length !== fields.length ||
    Object.keys(row).some((key) => !fields.includes(key)) ||
    row.donor_id !== donorId ||
    !states.includes(row.state as DonorSyncState) ||
    typeof row.enforcement_enabled !== "boolean" ||
    typeof row.source_processing_blocked !== "boolean" ||
    row.network_checked !== false ||
    (row.pts !== null && !baseline) ||
    (row.retry_at !== null &&
      (typeof row.retry_at !== "string" ||
        !/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(row.retry_at) ||
        !Number.isFinite(Date.parse(row.retry_at)))) ||
    (row.state === "READY" &&
      (!row.enforcement_enabled ||
        row.source_processing_blocked ||
        !baseline)) ||
    (row.state === "NOT_ENFORCED" && row.enforcement_enabled !== false) ||
    (row.state !== "READY" &&
      row.state !== "NOT_ENFORCED" &&
      row.source_processing_blocked !== true)
  )
    throw new Error("Некорректный ответ диагностики синхронизации");
  return row as DonorSyncStatus;
}
