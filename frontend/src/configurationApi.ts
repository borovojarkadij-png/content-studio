/** Public configuration only. Never accepts sessions, editorial overrides or send actions. */
export type AccountConfig = {
  id: number;
  name: string;
  telegram_user_id: number;
  health_status: string;
  session_provisioned: boolean;
};
export type ChannelConfig = {
  id: number;
  telegram_account_id: number;
  telegram_channel_id: number;
  title: string;
};
export type MappingConfig = {
  id: number;
  donor_channel_id: number;
  output_channel_id: number;
  intake_percent: number;
  target_mix_percent: number;
  eligibility_mode: "IMMEDIATE" | "DELAYED";
  delay_minutes: number;
  priority: number;
  media_policy: "REUSE_SOURCE" | "LICENSED_LIBRARY";
};
export type ImportConfig = {
  id: number;
  telegram_account_id: number;
  identifier: string;
  status: "PENDING_RESOLUTION" | "RESOLVED" | "INVALID_SOURCE";
};
export type FilterConfig = {
  mapping_id: number;
  allowed_media_types: ("text" | "photo" | "video")[];
  blocked_domains: string[];
  ad_markers: string[];
  effective_ad_markers: string[];
};
export type MappingPolicy = Omit<
  MappingConfig,
  "id" | "donor_channel_id" | "output_channel_id"
>;
export type FilterPolicy = Omit<
  FilterConfig,
  "mapping_id" | "effective_ad_markers"
>;
type Configuration = {
  accounts: AccountConfig;
  donors: ChannelConfig;
  "output-channels": ChannelConfig;
  mappings: MappingConfig;
  "donor-imports": ImportConfig;
};
type Row = Record<string, unknown>;
const row = (value: unknown): value is Row =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const positive = (value: unknown): value is number =>
  Number.isSafeInteger(value) && Number(value) > 0;
const integer = (value: unknown, min: number, max: number) =>
  Number.isSafeInteger(value) && Number(value) >= min && Number(value) <= max;
const text = (value: unknown): value is string => typeof value === "string";
const texts = (value: unknown, max: number): value is string[] =>
  Array.isArray(value) && value.length <= max && value.every(text);
const channel = (value: unknown): value is ChannelConfig =>
  row(value) &&
  positive(value.id) &&
  positive(value.telegram_account_id) &&
  Number.isSafeInteger(value.telegram_channel_id) &&
  value.telegram_channel_id !== 0 &&
  text(value.title);
const mapping = (value: unknown): value is MappingConfig =>
  row(value) &&
  positive(value.id) &&
  positive(value.donor_channel_id) &&
  positive(value.output_channel_id) &&
  integer(value.intake_percent, 0, 100) &&
  integer(value.target_mix_percent, 0, 100) &&
  ["IMMEDIATE", "DELAYED"].includes(String(value.eligibility_mode)) &&
  integer(value.delay_minutes, 0, 10080) &&
  (value.eligibility_mode !== "IMMEDIATE" || value.delay_minutes === 0) &&
  integer(value.priority, -1000, 1000) &&
  ["REUSE_SOURCE", "LICENSED_LIBRARY"].includes(String(value.media_policy));
const validators: {
  [K in keyof Configuration]: (value: unknown) => value is Configuration[K];
} = {
  accounts: (value): value is AccountConfig =>
    row(value) &&
    positive(value.id) &&
    positive(value.telegram_user_id) &&
    text(value.name) &&
    [
      "DISCONNECTED",
      "CONNECTED",
      "HEALTHY",
      "COOLDOWN",
      "SESSION_INVALID",
    ].includes(String(value.health_status)) &&
    typeof value.session_provisioned === "boolean",
  donors: channel,
  "output-channels": channel,
  mappings: mapping,
  "donor-imports": (value): value is ImportConfig =>
    row(value) &&
    positive(value.id) &&
    positive(value.telegram_account_id) &&
    text(value.identifier) &&
    ["PENDING_RESOLUTION", "RESOLVED", "INVALID_SOURCE"].includes(
      String(value.status),
    ),
};
const contract = () =>
  new Error("Ответ API не соответствует контракту конфигурации");
async function request(
  path: string,
  signal: AbortSignal,
  body?: unknown,
  method = "POST",
): Promise<unknown> {
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/${path}`,
    {
      signal,
      ...(body === undefined
        ? {}
        : {
            method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
    },
  );
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  return response.json();
}
export async function loadConfiguration<K extends keyof Configuration>(
  path: K,
  signal: AbortSignal,
): Promise<Configuration[K][]> {
  const payload = await request(path, signal);
  if (
    !row(payload) ||
    !Array.isArray(payload.items) ||
    !payload.items.every(validators[path])
  )
    throw contract();
  return payload.items;
}
export async function saveMapping(
  mappingId: number | null,
  policy: MappingPolicy & {
    donor_channel_id?: number;
    output_channel_id?: number;
  },
  signal: AbortSignal,
): Promise<MappingConfig> {
  const payload = await request(
    mappingId === null ? "mappings" : `mappings/${mappingId}`,
    signal,
    policy,
    mappingId === null ? "POST" : "PATCH",
  );
  if (
    !mapping(payload) ||
    (mappingId !== null && payload.id !== mappingId) ||
    (policy.donor_channel_id !== undefined &&
      payload.donor_channel_id !== policy.donor_channel_id) ||
    (policy.output_channel_id !== undefined &&
      payload.output_channel_id !== policy.output_channel_id)
  )
    throw contract();
  return payload;
}
export async function mappingFilters(
  mappingId: number,
  signal: AbortSignal,
  policy?: FilterPolicy,
): Promise<FilterConfig> {
  const payload = await request(
    `mappings/${mappingId}/technical-filters`,
    signal,
    policy,
    "PUT",
  );
  if (
    !row(payload) ||
    payload.mapping_id !== mappingId ||
    !Array.isArray(payload.allowed_media_types) ||
    payload.allowed_media_types.length > 3 ||
    !payload.allowed_media_types.every((type) =>
      ["text", "photo", "video"].includes(String(type)),
    ) ||
    !texts(payload.blocked_domains, 100) ||
    !texts(payload.ad_markers, 20) ||
    !texts(payload.effective_ad_markers, 100)
  )
    throw contract();
  return payload as FilterConfig;
}
export async function bulkImportDonors(
  accountId: number,
  raw: string,
  signal: AbortSignal,
): Promise<{ accepted: string[]; duplicates: string[]; rejected: string[] }> {
  const payload = await request("donors:bulk-import", signal, {
    telegram_account_id: accountId,
    raw_text: raw,
  });
  if (
    !row(payload) ||
    payload.status !== "PENDING_RESOLUTION" ||
    !texts(payload.accepted, 100000) ||
    !texts(payload.duplicates, 100000) ||
    !texts(payload.rejected, 100000)
  )
    throw contract();
  return {
    accepted: payload.accepted,
    duplicates: payload.duplicates,
    rejected: payload.rejected,
  };
}
export async function renameConfiguration(
  path: "accounts" | "donors" | "output-channels",
  configId: number,
  title: string,
  signal: AbortSignal,
): Promise<AccountConfig | ChannelConfig> {
  const payload = await request(
    `${path}/${configId}`,
    signal,
    { [path === "accounts" ? "name" : "title"]: title },
    "PATCH",
  );
  if (!validators[path](payload) || payload.id !== configId) throw contract();
  return payload;
}

export async function createConfiguration(
  path: "accounts" | "output-channels",
  title: string,
  telegramId: number,
  accountId: number,
  signal: AbortSignal,
): Promise<AccountConfig | ChannelConfig> {
  const body =
    path === "accounts"
      ? { name: title, telegram_user_id: telegramId }
      : {
          title,
          telegram_channel_id: telegramId,
          telegram_account_id: accountId,
        };
  const payload = await request(path, signal, body);
  if (
    !validators[path](payload) ||
    (path === "accounts"
      ? !("telegram_user_id" in payload) ||
        payload.telegram_user_id !== telegramId ||
        payload.session_provisioned
      : !("telegram_channel_id" in payload) ||
        payload.telegram_channel_id !== telegramId ||
        payload.telegram_account_id !== accountId)
  )
    throw contract();
  return payload;
}
