export type Binding = {
  candidate_id: number;
  output_channel_id: number;
  mapping_id: number;
  content_key: string;
  source_revision_id: number;
  source_sha256: string;
  rewrite_output_id: number;
  draft_sha256: string;
  media_asset_id: number;
  media_sha256: string;
  asset_metadata_sha256: string;
};
export type Verdict = "APPROVED_ILLUSTRATION" | "REJECTED" | "UNCERTAIN";
export type ReviewRecord = {
  id: number;
  record_kind: "REVIEW" | "REVOCATION";
  revokes_review_id: number | null;
  binding: Binding;
  reviewer_id: number;
  provenance: "AUTHENTICATED_HUMAN_V1";
  verdict: Verdict | null;
  illustration_acknowledged: boolean | null;
  review_note: string;
  reviewed_at: string;
  revoked: boolean;
};
export type Presentation = {
  binding: Binding;
  source_text: string;
  draft_text: string;
  channel: { id: number; title: string; telegram_channel_id: string };
  license_code: "CC0" | "CC-BY";
  attribution: string;
  mime_type: "image/png" | "image/jpeg";
  latest_review: ReviewRecord | null;
  etag: string;
};
export type ReviewOperation = {
  operation_key: string;
  review_note: string;
  displayed_binding: Binding;
  verdict: Verdict;
  illustration_acknowledged: boolean;
};
export type RevocationOperation = {
  operation_key: string;
  review_note: string;
};
export class ReviewApiError extends Error {
  constructor(
    message: string,
    public readonly status = 0,
  ) {
    super(message);
  }
}
type Row = Record<string, unknown>;
const row = (v: unknown): v is Row =>
  !!v && typeof v === "object" && !Array.isArray(v);
const exact = (v: unknown, keys: string): v is Row =>
  row(v) &&
  Object.keys(v).sort().join(",") === keys.split(",").sort().join(",");
const id = (v: unknown) =>
  typeof v === "number" && Number.isSafeInteger(v) && v > 0;
const text = (v: unknown, max: number) =>
  typeof v === "string" && v.length <= max && !v.includes("\0");
const hash = (v: unknown) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const fail = () => {
  throw new ReviewApiError(
    "Ответ проверки не соответствует контракту; загрузите заново",
  );
};
const bindingKeys =
  "candidate_id,output_channel_id,mapping_id,content_key,source_revision_id,source_sha256,rewrite_output_id,draft_sha256,media_asset_id,media_sha256,asset_metadata_sha256";
function validBinding(v: unknown, candidate: number): v is Binding {
  return (
    exact(v, bindingKeys) &&
    v.candidate_id === candidate &&
    [
      v.candidate_id,
      v.output_channel_id,
      v.mapping_id,
      v.source_revision_id,
      v.rewrite_output_id,
      v.media_asset_id,
    ].every(id) &&
    text(v.content_key, 255) &&
    typeof v.content_key === "string" &&
    !!v.content_key.trim() &&
    v.content_key === v.content_key.trim() &&
    !/[\x00-\x1f\x7f]/.test(v.content_key) &&
    [
      v.source_sha256,
      v.draft_sha256,
      v.media_sha256,
      v.asset_metadata_sha256,
    ].every(hash)
  );
}
const verdict = (v: unknown): v is Verdict =>
  typeof v === "string" &&
  ["APPROVED_ILLUSTRATION", "REJECTED", "UNCERTAIN"].includes(v);
export const validNote = (v: string) =>
  !!v.trim() && v.length <= 2048 && !/[\x00-\x08\x0b-\x1f]/.test(v);
function validRecord(v: unknown, candidate: number): v is ReviewRecord {
  return (
    exact(
      v,
      "id,record_kind,revokes_review_id,binding,reviewer_id,provenance,verdict,illustration_acknowledged,review_note,reviewed_at,revoked",
    ) &&
    id(v.id) &&
    id(v.reviewer_id) &&
    validBinding(v.binding, candidate) &&
    v.provenance === "AUTHENTICATED_HUMAN_V1" &&
    typeof v.review_note === "string" &&
    validNote(v.review_note) &&
    typeof v.reviewed_at === "string" &&
    /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(
      v.reviewed_at,
    ) &&
    Number.isFinite(Date.parse(v.reviewed_at)) &&
    typeof v.revoked === "boolean" &&
    ((v.record_kind === "REVIEW" &&
      v.revokes_review_id === null &&
      verdict(v.verdict) &&
      typeof v.illustration_acknowledged === "boolean" &&
      (v.verdict !== "APPROVED_ILLUSTRATION" ||
        v.illustration_acknowledged === true)) ||
      (v.record_kind === "REVOCATION" &&
        id(v.revokes_review_id) &&
        v.verdict === null &&
        v.illustration_acknowledged === null &&
        v.revoked === false))
  );
}
async function digest(bytes: Uint8Array): Promise<string> {
  return Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", bytes as BufferSource),
    ),
    (b) => b.toString(16).padStart(2, "0"),
  ).join("");
}
async function bounded(
  response: Response,
  limit: number,
  signal: AbortSignal,
): Promise<Uint8Array> {
  if (!response.body) return fail();
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    for (;;) {
      if (signal.aborted) throw new DOMException("Aborted", "AbortError");
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > limit) return fail();
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
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  return bytes;
}
const path = (suffix: string) =>
  `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/illustration-review/${suffix}`;
async function request(
  suffix: string,
  token: string,
  signal: AbortSignal,
  operation?: object,
  etag?: string,
): Promise<Response> {
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token))
    throw new ReviewApiError("Введите отдельно выданный токен редактора");
  try {
    const response = await fetch(path(suffix), {
      signal,
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      method: operation ? "POST" : "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(operation ? { "Content-Type": "application/json" } : {}),
        ...(etag ? { "If-Match": etag } : {}),
      },
      ...(operation ? { body: JSON.stringify(operation) } : {}),
    });
    if (!response.ok) {
      const message =
        response.status === 401
          ? "Токен редактора не принят (401)"
          : response.status === 409
            ? "Контекст изменился (409); загрузите заново"
            : response.status === 503
              ? "Сервер проверки недоступен или не настроен (503)"
              : `Сервер проверки вернул HTTP ${response.status}`;
      throw new ReviewApiError(message, response.status);
    }
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    return response;
  } catch (cause) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    if (cause instanceof ReviewApiError) throw cause;
    throw new ReviewApiError(
      "Сеть недоступна; результат запроса не подтверждён",
    );
  }
}
async function json(response: Response, signal: AbortSignal): Promise<unknown> {
  try {
    return JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(
        await bounded(response, 600000, signal),
      ),
    );
  } catch {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    return fail();
  }
}
export async function readPresentation(
  candidate: number,
  token: string,
  signal: AbortSignal,
): Promise<Presentation> {
  if (!id(candidate)) return fail();
  const response = await request(
    `candidates/${candidate}/presentation`,
    token,
    signal,
  );
  const v = await json(response, signal);
  const etag = response.headers.get("ETag");
  if (
    !etag ||
    !/^"[a-f0-9]{64}"$/.test(etag) ||
    !exact(
      v,
      "binding,source_text,draft_text,channel,license_code,attribution,mime_type,latest_review",
    ) ||
    !validBinding(v.binding, candidate) ||
    !text(v.source_text, 262144) ||
    !text(v.draft_text, 262144) ||
    !exact(v.channel, "id,title,telegram_channel_id") ||
    v.channel.id !== v.binding.output_channel_id ||
    !text(v.channel.title, 255) ||
    typeof v.channel.telegram_channel_id !== "string" ||
    !/^-100\d{1,16}$/.test(v.channel.telegram_channel_id) ||
    (v.license_code !== "CC0" && v.license_code !== "CC-BY") ||
    !text(v.attribution, 2048) ||
    (v.license_code === "CC-BY" && !(v.attribution as string).trim()) ||
    (v.mime_type !== "image/png" && v.mime_type !== "image/jpeg") ||
    (v.latest_review !== null &&
      (!validRecord(v.latest_review, candidate) ||
        v.latest_review.record_kind !== "REVIEW"))
  )
    return fail();
  const encoder = new TextEncoder();
  const source = encoder.encode(v.source_text as string);
  const draft = encoder.encode(v.draft_text as string);
  if (
    source.length > 262144 ||
    draft.length > 262144 ||
    (await digest(source)) !== v.binding.source_sha256 ||
    (await digest(draft)) !== v.binding.draft_sha256
  )
    return fail();
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  return { ...v, etag } as Presentation;
}
export async function readReviewPhoto(
  candidate: number,
  token: string,
  context: Presentation,
  signal: AbortSignal,
): Promise<Blob> {
  if (
    !validBinding(context.binding, candidate) ||
    !/^"[a-f0-9]{64}"$/.test(context.etag)
  )
    return fail();
  const response = await request(
    `candidates/${candidate}/photo`,
    token,
    signal,
    undefined,
    context.etag,
  );
  if (
    response.headers.get("ETag") !== context.etag ||
    response.headers.get("Content-Type") !== context.mime_type
  )
    return fail();
  const bytes = await bounded(response, 16 * 1024 * 1024, signal);
  const signature =
    context.mime_type === "image/png"
      ? [137, 80, 78, 71, 13, 10, 26, 10]
      : [255, 216, 255];
  if (
    !signature.every((b, i) => bytes[i] === b) ||
    (await digest(bytes)) !== context.binding.media_sha256
  )
    return fail();
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  return new Blob([bytes as BlobPart], { type: context.mime_type });
}
export async function readLatestReview(
  candidate: number,
  token: string,
  signal: AbortSignal,
): Promise<ReviewRecord | null> {
  if (!id(candidate)) return fail();
  const v = await json(
    await request(`candidates/${candidate}/latest-review`, token, signal),
    signal,
  );
  if (
    !exact(v, "latest_review") ||
    (v.latest_review !== null &&
      (!validRecord(v.latest_review, candidate) ||
        v.latest_review.record_kind !== "REVIEW"))
  )
    return fail();
  return v.latest_review as ReviewRecord | null;
}
function validOperation(operation: RevocationOperation) {
  return (
    /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(operation.operation_key) &&
    validNote(operation.review_note)
  );
}
export async function writeReview(
  candidate: number,
  token: string,
  operation: ReviewOperation,
  signal: AbortSignal,
): Promise<ReviewRecord> {
  if (
    !validOperation(operation) ||
    !validBinding(operation.displayed_binding, candidate) ||
    !verdict(operation.verdict) ||
    typeof operation.illustration_acknowledged !== "boolean" ||
    (operation.verdict === "APPROVED_ILLUSTRATION" &&
      !operation.illustration_acknowledged)
  )
    return fail();
  const v = await json(
    await request(`candidates/${candidate}/reviews`, token, signal, operation),
    signal,
  );
  if (
    !validRecord(v, candidate) ||
    v.record_kind !== "REVIEW" ||
    v.review_note !== operation.review_note ||
    v.verdict !== operation.verdict ||
    v.illustration_acknowledged !== operation.illustration_acknowledged ||
    !Object.entries(operation.displayed_binding).every(
      ([key, value]) => v.binding[key as keyof Binding] === value,
    )
  )
    return fail();
  return v;
}
export async function revokeReview(
  candidate: number,
  token: string,
  review: ReviewRecord,
  operation: RevocationOperation,
  signal: AbortSignal,
): Promise<ReviewRecord> {
  if (
    !validOperation(operation) ||
    !validRecord(review, candidate) ||
    review.record_kind !== "REVIEW" ||
    review.revoked
  )
    return fail();
  const v = await json(
    await request(`records/${review.id}/revocations`, token, signal, operation),
    signal,
  );
  if (
    !validRecord(v, candidate) ||
    v.record_kind !== "REVOCATION" ||
    v.revokes_review_id !== review.id ||
    v.review_note !== operation.review_note ||
    !Object.entries(review.binding).every(
      ([key, value]) => v.binding[key as keyof Binding] === value,
    )
  )
    return fail();
  return v;
}
