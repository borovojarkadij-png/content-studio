// Synthetic contract fixture shared only by review tests (never imported by UI).
export const photoBytes = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10, 1]);
export const bindingFixture = {
  candidate_id: 4,
  output_channel_id: 2,
  mapping_id: 3,
  content_key: "synthetic:4",
  source_revision_id: 5,
  source_sha256:
    "41cf6794ba4200b839c53531555f0f3998df4cbb01a4d5cb0b94e3ca5e23947d",
  rewrite_output_id: 6,
  draft_sha256:
    "7743ce348d9284d677a185f33295b92266cc435a5b5f775029b300066d26693a",
  media_asset_id: 7,
  media_sha256:
    "275f1bcbbb585c71e3b2184304eccfa0e37de92022ca3b6f4e9c10df32318d85",
  asset_metadata_sha256: "d".repeat(64),
};
export const presentationFixture = {
  binding: bindingFixture,
  source_text: "source",
  draft_text: "draft",
  channel: {
    id: 2,
    title: "Synthetic channel",
    telegram_channel_id: "-100123456",
  },
  license_code: "CC-BY",
  attribution: "Synthetic credit",
  mime_type: "image/png",
  latest_review: null,
};
export const reviewFixture = {
  id: 8,
  record_kind: "REVIEW",
  revokes_review_id: null,
  binding: bindingFixture,
  reviewer_id: 17,
  provenance: "AUTHENTICATED_HUMAN_V1",
  verdict: "APPROVED_ILLUSTRATION",
  illustration_acknowledged: true,
  review_note: "Illustration, not event photo",
  reviewed_at: "2026-10-09T10:00:00+00:00",
  revoked: false,
};
