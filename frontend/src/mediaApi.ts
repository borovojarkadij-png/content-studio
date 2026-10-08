export type MediaAsset = {
  id: number;
  storage_key: string;
  sha256: string;
  mime_type: "image/png" | "image/jpeg";
  origin: "SOURCE" | "LICENSED_LIBRARY";
  source_content_key: string | null;
  license_code: "OWNED" | "PERMISSION" | "CC0" | "CC-BY";
  attribution: string;
  tags: string[];
};
export type MediaStatus = {
  candidate_id: number;
  job_id: number | null;
  state:
    | "NOT_QUEUED"
    | "QUEUED"
    | "RUNNING"
    | "SUCCEEDED"
    | "FAILED"
    | "BLOCKED"
    | "NO_MATCH";
  attempts: number;
  media_policy: string;
  acquisition_mode: string;
  queue_allowed: boolean;
  queue_reason_code: string | null;
  selected_allowed: boolean;
  asset: MediaAsset | null;
  reason_code: string | null;
  illustration: boolean;
  publication_hold_reason_code?:
    "ILLUSTRATION_RELEVANCE_APPROVAL_NOT_IMPLEMENTED" | null;
};
type Row = Record<string, unknown>;
const row = (value: unknown): value is Row =>
  value !== null && typeof value === "object";
const id = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0;
const optionalString = (value: unknown) =>
  value === null || typeof value === "string";
function isAsset(value: unknown): value is MediaAsset {
  if (!row(value)) return false;
  return (
    id(value.id) &&
    typeof value.storage_key === "string" &&
    typeof value.sha256 === "string" &&
    /^[a-f0-9]{64}$/.test(value.sha256) &&
    ["image/png", "image/jpeg"].includes(String(value.mime_type)) &&
    typeof value.attribution === "string" &&
    value.attribution.length <= 2048 &&
    Array.isArray(value.tags) &&
    value.tags.every((tag) => typeof tag === "string") &&
    ((value.origin === "SOURCE" &&
      ["OWNED", "PERMISSION"].includes(String(value.license_code)) &&
      typeof value.source_content_key === "string" &&
      !!value.source_content_key) ||
      (value.origin === "LICENSED_LIBRARY" &&
        ["CC0", "CC-BY"].includes(String(value.license_code)) &&
        value.source_content_key === null)) &&
    (!["PERMISSION", "CC-BY"].includes(String(value.license_code)) ||
      !!value.attribution.trim())
  );
}
function isStatus(value: unknown, candidateId: number): value is MediaStatus {
  if (!row(value)) return false;
  return (
    value.candidate_id === candidateId &&
    (value.job_id === null || id(value.job_id)) &&
    [
      "NOT_QUEUED",
      "QUEUED",
      "RUNNING",
      "SUCCEEDED",
      "FAILED",
      "BLOCKED",
      "NO_MATCH",
    ].includes(String(value.state)) &&
    (value.state === "NOT_QUEUED") === (value.job_id === null) &&
    Number.isInteger(value.attempts) &&
    Number(value.attempts) >= 0 &&
    Number(value.attempts) <= 2 &&
    ["LICENSED_LIBRARY", "REUSE_SOURCE"].includes(String(value.media_policy)) &&
    ["LICENSED_LIBRARY", "REUSE_SOURCE"].includes(
      String(value.acquisition_mode),
    ) &&
    typeof value.queue_allowed === "boolean" &&
    optionalString(value.queue_reason_code) &&
    typeof value.selected_allowed === "boolean" &&
    optionalString(value.reason_code) &&
    typeof value.illustration === "boolean" &&
    (value.publication_hold_reason_code === undefined ||
      value.publication_hold_reason_code ===
        (value.media_policy === "LICENSED_LIBRARY"
          ? "ILLUSTRATION_RELEVANCE_APPROVAL_NOT_IMPLEMENTED"
          : null)) &&
    value.illustration === (value.acquisition_mode !== "REUSE_SOURCE") &&
    (value.selected_allowed
      ? value.state === "SUCCEEDED" &&
        isAsset(value.asset) &&
        value.asset.origin ===
          (value.illustration ? "LICENSED_LIBRARY" : "SOURCE")
      : value.asset === null)
  );
}
export const mediaPath = (candidateId: number, action: string) =>
  `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/publication-candidates/${candidateId}/${action}`;
export async function mediaStatus(
  candidateId: number,
  signal: AbortSignal,
  queue = false,
): Promise<MediaStatus> {
  if (!id(candidateId)) throw new Error("Неверный идентификатор материала");
  const response = await fetch(mediaPath(candidateId, "media-acquisition"), {
    signal,
    method: queue ? "POST" : "GET",
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`API медиа вернул HTTP ${response.status}`);
  if (queue && response.status !== 202)
    throw new Error("API медиа не подтвердил очередь HTTP 202");
  const payload: unknown = await response.json();
  if (!isStatus(payload, candidateId))
    throw new Error("Ответ API медиа не соответствует контракту");
  return payload;
}

export async function mediaPreview(
  candidateId: number,
  asset: MediaAsset,
  signal: AbortSignal,
): Promise<Blob> {
  const response = await fetch(mediaPath(candidateId, "media-preview"), {
    signal,
    cache: "no-store",
  });
  if (!response.ok)
    throw new Error(`API предпросмотра вернул HTTP ${response.status}`);
  if (
    !response.body ||
    response.headers.get("content-type") !== asset.mime_type
  )
    throw new Error("Неверный формат предпросмотра");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > 16 * 1024 * 1024)
        throw new Error("Размер предпросмотра превышает лимит");
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  const digest = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    (byte) => byte.toString(16).padStart(2, "0"),
  ).join("");
  if (signal.aborted) throw new DOMException("Request aborted", "AbortError");
  if (digest !== asset.sha256)
    throw new Error("Байты предпросмотра изменились; обновите статус");
  return new Blob([bytes], { type: asset.mime_type });
}
