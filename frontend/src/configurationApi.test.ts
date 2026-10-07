import { afterEach, expect, it, vi } from "vitest";
import {
  loadConfiguration,
  mappingFilters,
  saveMapping,
  bulkImportDonors,
  type MappingConfig,
} from "./configurationApi";

afterEach(() => vi.unstubAllGlobals());
const mapping: MappingConfig = {
  id: 3,
  donor_channel_id: 1,
  output_channel_id: 2,
  intake_percent: 100,
  target_mix_percent: 50,
  eligibility_mode: "IMMEDIATE",
  delay_minutes: 0,
  priority: 2,
  media_policy: "REUSE_SOURCE",
};
const filters = {
  mapping_id: 3,
  allowed_media_types: ["text", "photo"],
  blocked_domains: [],
  ad_markers: [],
  effective_ad_markers: ["реклама"],
};
const json = (value: unknown) => ({ ok: true, json: async () => value });
it("fails closed on malformed identities and transport failures rather than demo fallback", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      json({
        items: [
          {
            id: 1,
            telegram_account_id: 1,
            telegram_channel_id: Number.MAX_SAFE_INTEGER + 1,
            title: "Unsafe",
          },
        ],
      }),
    ),
  );
  await expect(
    loadConfiguration("donors", new AbortController().signal),
  ).rejects.toThrow("контракт");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: false, status: 503 })),
  );
  await expect(
    loadConfiguration("accounts", new AbortController().signal),
  ).rejects.toThrow("503");
});
it("binds returned filter and mapping identities to the request", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ...filters, mapping_id: 4 })),
  );
  await expect(mappingFilters(3, new AbortController().signal)).rejects.toThrow(
    "контракт",
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ...mapping, id: 4 })),
  );
  const { id, donor_channel_id, output_channel_id, ...policy } = mapping;
  await expect(
    saveMapping(id, policy, new AbortController().signal),
  ).rejects.toThrow("контракт");
});
it("rejects unknown media and an invalid donor import status without successful-save claims", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => json({ ...filters, allowed_media_types: ["UNKNOWN"] })),
  );
  await expect(mappingFilters(3, new AbortController().signal)).rejects.toThrow(
    "контракт",
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      json({
        status: "RESOLVED",
        accepted: ["@donor"],
        duplicates: [],
        rejected: [],
      }),
    ),
  );
  await expect(
    bulkImportDonors(1, "@donor", new AbortController().signal),
  ).rejects.toThrow("контракт");
});
