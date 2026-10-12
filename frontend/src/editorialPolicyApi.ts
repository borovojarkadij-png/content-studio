import { readBoundedResponse } from "./boundedResponse";

export type ProtectedEntity = { entity_id: string; aliases: string[] };
export type EditorialPolicy = {
  configured: boolean;
  enabled: boolean;
  provider: "OPENAI" | "OPENROUTER" | null;
  model: string | null;
  policy_version: string | null;
  etag: string | null;
  protected_entities: ProtectedEntity[];
  diagnostic_only: true;
  real_model_qualified: false;
  execution_authorized: false;
  rewrite_allowed: false;
};
export type EditorialPolicyChange = {
  enabled: boolean;
  provider: "OPENAI" | "OPENROUTER";
  model: string;
  protected_entities: ProtectedEntity[];
  expected_etag: string | null;
};
export class EditorialPolicyApiError extends Error {
  constructor(
    message: string,
    public readonly status = 0,
    public readonly local = false,
  ) {
    super(message);
  }
}
const invalid = () => {
  throw new EditorialPolicyApiError(
    "Ответ редакционной политики не соответствует контракту; загрузите заново",
  );
};
const exact = (v: unknown, keys: string): v is Record<string, unknown> =>
  !!v &&
  typeof v === "object" &&
  !Array.isArray(v) &&
  Object.keys(v).sort().join(",") === keys.split(",").sort().join(",");
const text = (v: unknown, max: number): v is string =>
  // The persisted contract uses Python str.strip whitespace. Do not strip or
  // normalize values (JS trim would incorrectly reject a legacy U+FEFF ID).
  typeof v === "string" &&
  /[^\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/u.test(
    v,
  ) &&
  [...v].length <= max &&
  !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(
    v,
  );
const hash = (v: unknown) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
function entities(v: unknown): v is ProtectedEntity[] {
  if (
    !Array.isArray(v) ||
    v.length > 64 ||
    !v.every(
      (e) =>
        exact(e, "entity_id,aliases") &&
        text(e.entity_id, 128) &&
        Array.isArray(e.aliases) &&
        e.aliases.length >= 1 &&
        e.aliases.length <= 16 &&
        e.aliases.every((a) => text(a, 255)),
    )
  )
    return false;
  if (new Set(v.map((e) => e.entity_id)).size !== v.length) return false;
  // Exact serialization bounds only; Unicode alias ambiguity remains server-owned.
  return (
    new TextEncoder().encode(
      JSON.stringify(
        v.map((e) => ({ aliases: e.aliases, entity_id: e.entity_id })),
      ),
    ).length <= 262144
  );
}
function editable(v: Record<string, unknown>) {
  return (
    typeof v.enabled === "boolean" &&
    (v.provider === "OPENAI" || v.provider === "OPENROUTER") &&
    typeof v.model === "string" &&
    /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$/.test(v.model) &&
    (v.provider !== "OPENROUTER" ||
      (v.model.endsWith(":free") &&
        !v.model.slice(0, -5).includes(":") &&
        !v.model.toLowerCase().startsWith("openrouter/"))) &&
    entities(v.protected_entities)
  );
}
function policy(v: unknown): EditorialPolicy {
  if (
    !exact(
      v,
      "configured,enabled,provider,model,policy_version,etag,protected_entities,diagnostic_only,real_model_qualified,execution_authorized,rewrite_allowed",
    ) ||
    v.diagnostic_only !== true ||
    v.real_model_qualified !== false ||
    v.execution_authorized !== false ||
    v.rewrite_allowed !== false
  )
    return invalid();
  if (
    v.configured === false &&
    v.enabled === false &&
    v.provider === null &&
    v.model === null &&
    v.policy_version === null &&
    v.etag === null &&
    Array.isArray(v.protected_entities) &&
    v.protected_entities.length === 0
  )
    return v as EditorialPolicy;
  if (
    v.configured !== true ||
    !editable(v) ||
    !text(v.policy_version, 255) ||
    !hash(v.etag)
  )
    return invalid();
  return v as EditorialPolicy;
}
function endpoint(): string {
  try {
    const origin = window.location.origin;
    const configuredBase = import.meta.env.VITE_API_BASE_URL || "/";
    const base = new URL(configuredBase, origin);
    if (
      base.origin !== origin ||
      base.username ||
      base.password ||
      base.search ||
      base.hash ||
      configuredBase.includes("?") ||
      configuredBase.includes("#") ||
      base.pathname !== "/"
    )
      throw new Error();
    return "/api/settings/editorial-policy";
  } catch {
    throw new EditorialPolicyApiError(
      "Адрес API редакционной политики должен вести к корню текущего сайта; запрос не отправлен",
      0,
      true,
    );
  }
}
async function request(
  token: string,
  signal: AbortSignal,
  change?: EditorialPolicyChange,
): Promise<EditorialPolicy> {
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token))
    throw new EditorialPolicyApiError(
      "Введите отдельно выданный токен оператора",
      0,
      true,
    );
  const url = endpoint();
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  let response: Response;
  try {
    response = await fetch(url, {
      signal,
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      method: change ? "PUT" : "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(change ? { "Content-Type": "application/json" } : {}),
      },
      ...(change ? { body: JSON.stringify(change) } : {}),
    });
  } catch {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    throw new EditorialPolicyApiError(
      "Сеть недоступна; результат запроса не подтверждён",
    );
  }
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  if (!response.ok) {
    const message =
      response.status === 401
        ? "Токен оператора не принят (401)"
        : response.status === 409
          ? "Политика изменена другим оператором (409); загрузите заново"
          : response.status === 422
            ? "Редакционная политика не прошла проверку (422); черновик сохранён"
            : response.status === 503
              ? "Сервер редакционной политики или хранилище недоступны либо не настроены (503)"
              : change
                ? "Результат сохранения редакционной политики не подтверждён; загрузите заново"
                : "Сервер редакционной политики отклонил запрос";
    throw new EditorialPolicyApiError(message, response.status);
  }
  try {
    return policy(
      JSON.parse(
        new TextDecoder("utf-8", { fatal: true }).decode(
          await readBoundedResponse(response, 300000, signal),
        ),
      ),
    );
  } catch {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    return invalid();
  }
}
export function readEditorialPolicy(
  token: string,
  signal: AbortSignal,
): Promise<EditorialPolicy> {
  return request(token, signal);
}
const canonical = (values: ProtectedEntity[]) =>
  JSON.stringify(
    values
      .map((e) => ({ entity_id: e.entity_id, aliases: [...e.aliases].sort() }))
      .sort((a, b) =>
        a.entity_id < b.entity_id ? -1 : a.entity_id > b.entity_id ? 1 : 0,
      ),
  );
export async function writeEditorialPolicy(
  token: string,
  change: EditorialPolicyChange,
  signal: AbortSignal,
): Promise<EditorialPolicy> {
  if (
    !editable(change) ||
    (change.expected_etag !== null && !hash(change.expected_etag))
  )
    throw new EditorialPolicyApiError(
      "Проверьте модель, сущности, псевдонимы и границы конфигурации; запрос не отправлен",
      0,
      true,
    );
  // Explicit allow-list: runtime callers cannot smuggle authority or provenance fields.
  const submitted: EditorialPolicyChange = {
    enabled: change.enabled,
    provider: change.provider,
    model: change.model,
    protected_entities: change.protected_entities.map((e) => ({
      entity_id: e.entity_id,
      aliases: [...e.aliases],
    })),
    expected_etag: change.expected_etag,
  };
  const result = await request(token, signal, submitted);
  if (
    !result.configured ||
    result.enabled !== submitted.enabled ||
    result.provider !== submitted.provider ||
    result.model !== submitted.model ||
    canonical(result.protected_entities) !==
      canonical(submitted.protected_entities)
  )
    return invalid();
  return result;
}
