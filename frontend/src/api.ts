import type { Post } from "./studio";

type IncomingRecord = {
  source_key: string;
  state: string;
  revision_number: number;
  source_text: string;
  editorial_status: string | null;
  rewrite_allowed: boolean | null;
  editorial_reason_codes: string[];
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
    row.editorial_reason_codes.every((reason) => typeof reason === "string")
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
      item.editorial_status === "REJECT" || item.state.startsWith("REJECTED")
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
      item.rewrite_allowed === true && item.editorial_status === "PASS",
    revision: item.revision_number,
  }));
}
