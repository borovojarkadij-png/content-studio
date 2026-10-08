export type ApprovalMode = "MANUAL" | "VERIFIED";
export type QualifiedRelease = {
  id: number;
  provider: "OPENAI" | "OPENROUTER";
  model: string;
  prompt_version: string;
  benchmark_version: string;
};
export type ApprovalPolicy = {
  output_channel_id: number;
  mode: ApprovalMode;
  release_id: number | null;
  qualified_releases: QualifiedRelease[];
};
const row = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const id = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0;
const exact = (value: Record<string, unknown>, keys: string[]) =>
  Object.keys(value).length === keys.length &&
  Object.keys(value).every((key) => keys.includes(key));

export async function approvalPolicy(
  channelId: number,
  signal: AbortSignal,
  selection?: { mode: ApprovalMode; release_id: number | null },
): Promise<ApprovalPolicy> {
  if (
    !id(channelId) ||
    (selection &&
      (!["MANUAL", "VERIFIED"].includes(selection.mode) ||
        (selection.mode === "MANUAL"
          ? selection.release_id !== null
          : !id(selection.release_id))))
  )
    throw new Error("Некорректная настройка одобрения");
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/output-channels/${channelId}/approval-policy`,
    {
      method: selection ? "PUT" : "GET",
      signal,
      cache: "no-store",
      ...(selection
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(selection),
          }
        : {}),
    },
  );
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  const invalid = () => {
    throw new Error("Некорректный ответ настройки одобрения");
  };
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    return invalid();
  }
  if (
    !row(value) ||
    !exact(value, [
      "output_channel_id",
      "mode",
      "release_id",
      "qualified_releases",
    ]) ||
    value.output_channel_id !== channelId ||
    (value.mode !== "MANUAL" && value.mode !== "VERIFIED") ||
    (value.mode === "MANUAL"
      ? value.release_id !== null
      : !id(value.release_id)) ||
    !Array.isArray(value.qualified_releases)
  )
    return invalid();
  const seen = new Set<number>();
  for (const release of value.qualified_releases) {
    if (
      !row(release) ||
      !exact(release, [
        "id",
        "provider",
        "model",
        "prompt_version",
        "benchmark_version",
      ]) ||
      !id(release.id) ||
      seen.has(Number(release.id)) ||
      (release.provider !== "OPENAI" && release.provider !== "OPENROUTER") ||
      typeof release.model !== "string" ||
      !/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$/.test(release.model) ||
      release.model === "openrouter/free" ||
      (release.provider === "OPENROUTER" && !release.model.endsWith(":free")) ||
      release.prompt_version !== "semantic-facts-v1" ||
      release.benchmark_version !== "semantic-facts-v1"
    )
      return invalid();
    seen.add(Number(release.id));
  }
  if (
    selection &&
    (value.mode !== selection.mode || value.release_id !== selection.release_id)
  )
    return invalid();
  return value as ApprovalPolicy;
}
