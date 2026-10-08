export type UsageSummary = {
  operation: "REWRITE" | "SEMANTIC_VERIFICATION";
  records: number;
  input_tokens: number;
  cached_tokens: number;
  output_tokens: number;
  known_estimated_cost_usd: string;
  unknown_cost_records: number;
  durable_attempts: number;
  unobserved_attempts: number;
};
export type StudioOverview = {
  scope: "ALL_RETAINED_HISTORY";
  generated_at: string;
  network_checked: false;
  billing_complete: false;
  configuration: {
    accounts: number;
    donors: number;
    output_channels: number;
    mappings: number;
  };
  history: {
    source_posts: number;
    source_revisions: number;
    rewrite_jobs: number;
    active_rewrite_jobs: number;
    acknowledged_publications: number;
    uncertain_publications: number;
  };
  usage: UsageSummary[];
};
type Row = Record<string, unknown>;
const row = (value: unknown): value is Row =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const count = (value: unknown): value is number =>
  Number.isSafeInteger(value) && Number(value) >= 0;
const fields = (value: Row, names: string[]) =>
  Object.keys(value).length === names.length &&
  names.every((name) => Object.hasOwn(value, name));
const counts = (
  value: unknown,
  names: string[],
): value is Record<string, number> =>
  row(value) &&
  fields(value, names) &&
  names.every((name) => count(value[name]));
function usage(
  value: unknown,
  operation: UsageSummary["operation"],
): value is UsageSummary {
  const numeric = [
    "records",
    "input_tokens",
    "cached_tokens",
    "output_tokens",
    "unknown_cost_records",
    "durable_attempts",
    "unobserved_attempts",
  ];
  return (
    row(value) &&
    fields(value, [...numeric, "operation", "known_estimated_cost_usd"]) &&
    numeric.every((name) => count(value[name])) &&
    value.operation === operation &&
    typeof value.known_estimated_cost_usd === "string" &&
    /^\d+\.\d{10}$/.test(value.known_estimated_cost_usd) &&
    value.known_estimated_cost_usd.length <= 50 &&
    Number(value.cached_tokens) <= Number(value.input_tokens) &&
    Number(value.unknown_cost_records) <= Number(value.records) &&
    Number(value.unobserved_attempts) <= Number(value.durable_attempts)
  );
}
export async function loadStudioOverview(
  signal: AbortSignal,
): Promise<StudioOverview> {
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/studio/overview`,
    { method: "GET", cache: "no-store", signal },
  );
  if (!response.ok)
    throw new Error(`API обзора вернул HTTP ${response.status}`);
  const value: unknown = await response.json();
  if (
    !row(value) ||
    !fields(value, [
      "scope",
      "generated_at",
      "network_checked",
      "billing_complete",
      "configuration",
      "history",
      "usage",
    ]) ||
    value.scope !== "ALL_RETAINED_HISTORY" ||
    value.network_checked !== false ||
    value.billing_complete !== false ||
    typeof value.generated_at !== "string" ||
    !/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value.generated_at) ||
    !Number.isFinite(Date.parse(value.generated_at)) ||
    !counts(value.configuration, [
      "accounts",
      "donors",
      "output_channels",
      "mappings",
    ]) ||
    !counts(value.history, [
      "source_posts",
      "source_revisions",
      "rewrite_jobs",
      "active_rewrite_jobs",
      "acknowledged_publications",
      "uncertain_publications",
    ]) ||
    value.history.active_rewrite_jobs > value.history.rewrite_jobs ||
    !Array.isArray(value.usage) ||
    value.usage.length !== 2 ||
    !usage(value.usage[0], "REWRITE") ||
    !usage(value.usage[1], "SEMANTIC_VERIFICATION")
  )
    throw new Error("Ответ API обзора не соответствует контракту");
  return value as StudioOverview;
}
