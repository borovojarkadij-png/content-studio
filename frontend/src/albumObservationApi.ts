export type AlbumMember = {
  content_key: string;
  message_id: number;
  revision_number: number;
  text: string;
  media_type: "photo" | "video" | "unsupported" | "unknown";
  media_protected: boolean | null;
  source_deleted: boolean;
};
export type AlbumObservation = {
  anchor_content_key: string;
  album_id: string;
  members: AlbumMember[];
  membership_complete: false;
  rewrite_allowed: false;
  publication_allowed: false;
  source_sync_blocked: boolean;
  reason_code: "ALBUM_NORMALIZATION_REQUIRED";
};
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const exact = (value: Record<string, unknown>, keys: string[]) =>
  Object.keys(value).length === keys.length &&
  Object.keys(value).every((key) => keys.includes(key));
const contentKey = (value: unknown): value is string =>
  typeof value === "string" &&
  value.length > 0 &&
  value.length <= 255 &&
  value.trim() === value;
const positive = (value: unknown) =>
  Number.isSafeInteger(value) && Number(value) > 0;
const albumId = (value: unknown) => {
  if (
    typeof value !== "string" ||
    !/^(?:0|-?[1-9]\d*)$/.test(value) ||
    value.length > 20
  )
    return false;
  const id = BigInt(value);
  return id >= -(2n ** 63n) && id < 2n ** 63n;
};
export async function loadAlbumObservation(
  key: string,
  signal: AbortSignal,
): Promise<AlbumObservation> {
  if (!contentKey(key)) throw new Error("Некорректная ревизия");
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/telegram/source-albums?content_key=${encodeURIComponent(key)}`,
    { method: "GET", cache: "no-store", signal },
  );
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}`);
  const invalid = (): never => {
    throw new Error("Некорректный ответ наблюдения альбома");
  };
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    return invalid();
  }
  if (
    !object(value) ||
    !exact(value, [
      "anchor_content_key",
      "album_id",
      "members",
      "membership_complete",
      "rewrite_allowed",
      "publication_allowed",
      "source_sync_blocked",
      "reason_code",
    ]) ||
    value.anchor_content_key !== key ||
    !albumId(value.album_id) ||
    value.membership_complete !== false ||
    value.rewrite_allowed !== false ||
    value.publication_allowed !== false ||
    typeof value.source_sync_blocked !== "boolean" ||
    value.reason_code !== "ALBUM_NORMALIZATION_REQUIRED" ||
    !Array.isArray(value.members) ||
    value.members.length < 1 ||
    value.members.length > 10
  )
    return invalid();
  const keys = new Set<string>();
  let previousId = 0;
  for (const member of value.members) {
    if (
      !object(member) ||
      !exact(member, [
        "content_key",
        "message_id",
        "revision_number",
        "text",
        "media_type",
        "media_protected",
        "source_deleted",
      ]) ||
      !contentKey(member.content_key) ||
      keys.has(member.content_key) ||
      !positive(member.message_id) ||
      Number(member.message_id) > 2147483647 ||
      Number(member.message_id) <= previousId ||
      !positive(member.revision_number) ||
      typeof member.text !== "string" ||
      !["photo", "video", "unsupported", "unknown"].includes(
        member.media_type as string,
      ) ||
      (member.media_protected !== null &&
        typeof member.media_protected !== "boolean") ||
      typeof member.source_deleted !== "boolean"
    )
      return invalid();
    keys.add(member.content_key);
    previousId = Number(member.message_id);
  }
  if (!keys.has(key)) return invalid();
  return value as AlbumObservation;
}
