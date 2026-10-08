import type { Post } from "./studio";

export type RewriteProvider = "OPENAI" | "OPENROUTER";

export type RewriteProviderSetting = {
  provider: RewriteProvider;
  configured: boolean;
  primary_model: string;
  fallback_models: string[];
};

type IncomingRecord = {
  source_key: string;
  state: string;
  revision_number: number;
  source_text: string;
  editorial_status: string | null;
  rewrite_allowed: boolean | null;
  editorial_reason_codes: string[];
  source_deleted?: boolean;
};

function isRecord(value: unknown): value is IncomingRecord {
  if (!value || typeof value !== "object") return false;
  const row = value as Partial<IncomingRecord>;
  return (
    typeof row.source_key === "string" &&
    typeof row.state === "string" &&
    typeof row.source_text === "string" &&
    Number.isInteger(row.revision_number) &&
    (row.revision_number ?? 0) > 0 &&
    ["PASS", "REJECT", "MANUAL_REVIEW", null].includes(
      row.editorial_status === undefined ? "MISSING" : row.editorial_status,
    ) &&
    (row.rewrite_allowed === true ||
      row.rewrite_allowed === false ||
      row.rewrite_allowed === null) &&
    Array.isArray(row.editorial_reason_codes) &&
    row.editorial_reason_codes.every((reason) => typeof reason === "string") &&
    (row.source_deleted === undefined ||
      typeof row.source_deleted === "boolean")
  );
}

export async function loadInbox(signal: AbortSignal): Promise<Post[]> {
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/incoming-posts`,
    { signal },
  );
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  const payload: unknown = await response.json();
  if (
    !payload ||
    typeof payload !== "object" ||
    !("items" in payload) ||
    !Array.isArray(payload.items) ||
    !payload.items.every(isRecord)
  )
    throw new Error("Ответ API не соответствует контракту входящих");
  return payload.items.map((item) => ({
    id: item.source_key,
    source: item.source_key.split(":").slice(1, -1).join(":") || "Telegram",
    title: item.source_text.split("\n")[0] || "Материал без текста",
    original: item.source_text,
    suggestion: "",
    draft: "",
    state:
      item.source_deleted === true || item.state === "SOURCE_DELETED"
        ? "Удалён у донора"
        : item.state === "SOURCE_SYNC_REQUIRED"
          ? "Нужна синхронизация"
          : item.editorial_status === "REJECT" ||
              item.state.startsWith("REJECTED")
            ? "Отклонён"
            : "На проверке",
    time: `Ревизия ${item.revision_number}`,
    art: "",
    destinations: [],
    editorial:
      item.editorial_status === "PASS"
        ? "PASS"
        : item.editorial_status === "REJECT"
          ? "REJECT"
          : "PENDING",
    rewriteAllowed:
      item.source_deleted !== true &&
      item.state !== "SOURCE_DELETED" &&
      item.state !== "SOURCE_SYNC_REQUIRED" &&
      item.rewrite_allowed === true &&
      item.editorial_status === "PASS",
    revision: item.revision_number,
    sourceDeleted:
      item.source_deleted === true || item.state === "SOURCE_DELETED",
    sourceSyncBlocked: item.state === "SOURCE_SYNC_REQUIRED",
  }));
}

function isRewriteProviderSetting(
  value: unknown,
): value is RewriteProviderSetting {
  if (!value || typeof value !== "object") return false;
  const setting = value as Partial<RewriteProviderSetting>;
  return (
    (setting.provider === "OPENAI" || setting.provider === "OPENROUTER") &&
    typeof setting.configured === "boolean" &&
    typeof setting.primary_model === "string" &&
    Array.isArray(setting.fallback_models) &&
    setting.fallback_models.every((model) => typeof model === "string")
  );
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

async function providerResponse(
  path: string,
  init?: RequestInit,
): Promise<RewriteProviderSetting> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  const payload: unknown = await response.json();
  if (!isRewriteProviderSetting(payload)) {
    throw new Error("Ответ API не соответствует контракту AI-подключения");
  }
  return payload;
}

export async function loadRewriteProviders(
  signal: AbortSignal,
): Promise<RewriteProviderSetting[]> {
  const response = await fetch(`${apiBaseUrl}/api/settings/rewrite-providers`, {
    signal,
  });
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  const payload: unknown = await response.json();
  if (
    !payload ||
    typeof payload !== "object" ||
    !("items" in payload) ||
    !Array.isArray(payload.items) ||
    !payload.items.every(isRewriteProviderSetting)
  ) {
    throw new Error("Ответ API не соответствует контракту AI-подключений");
  }
  return payload.items;
}

export function saveOpenAIRewriteProvider(
  apiKey: string,
  model: string,
): Promise<RewriteProviderSetting> {
  return providerResponse("/api/settings/rewrite-providers/openai", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, model }),
  });
}

export function saveOpenRouterRewriteProvider(
  apiKey: string,
  fallbackModels: string[],
): Promise<RewriteProviderSetting> {
  return providerResponse("/api/settings/rewrite-providers/openrouter", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, fallback_models: fallbackModels }),
  });
}

export async function loadRewriteProviderModels(
  provider: RewriteProvider,
): Promise<string[]> {
  const response = await fetch(
    `${apiBaseUrl}/api/settings/rewrite-providers/${provider.toLowerCase()}/models`,
    { method: "GET" },
  );
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  const payload: unknown = await response.json();
  if (
    !payload ||
    typeof payload !== "object" ||
    !("items" in payload) ||
    !Array.isArray(payload.items) ||
    !payload.items.every((model) => typeof model === "string")
  ) {
    throw new Error("Ответ API не соответствует каталогу моделей");
  }
  return payload.items;
}
