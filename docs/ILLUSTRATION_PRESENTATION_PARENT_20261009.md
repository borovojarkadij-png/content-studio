# Protected illustration presentation parent verification — 2026-10-09

Immutable implementation `59cfbab31d96ef9f1d3cee359b637b728348ffc4`, base
`cb0516d1584273d62ab2ddb9fd605a68891fae8c`. Evidence-only `486ace2` follows;
no implementation changes. Branch `codex/dark-navy-ui`, only authorized origin
`borovojarkadij-png/content-studio`. Independent task review completed: spec
compliant / quality approved, no Critical or Important findings. Existing color
warning/untouched broad-format differences remain tracked, not hidden. No
operational reviewer provisioned or real sends activated.

## Actual migrated Windows Docker PostgreSQL

Only the retained explicitly validated synthetic unattended PostgreSQL was used:
container `4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e`,
public fixture role/password/database on loopback5432. Full URL is validated by
`backend/tests/unattended_postgres.py`; each migrated fixture creates a fresh
`unattended_<uuid>` schema. No operational schema or old fixture was reseeded.

From `backend`, with TEMP/TMP and isolated Python cache on
`D:/Codex-Recovery/content-studio-20261008`, existing Telethon1.45 PYTHONPATH
and strict `NEWSFLOW_UNATTENDED_POSTGRES_URL`:

```powershell
python -m pytest tests/test_illustration_presentation.py tests/test_illustration_review_api.py tests/test_illustration_publication.py tests/test_illustration_binding.py -q --tb=short
```

**209 PASS /334.61s /no SKIP /exit0**, session93074, frozen source. Distinct
from implementer local **1793 PASS /1 PostgreSQL-only SKIP /361.83s**. The
four modules cover protected presentation47, immutable review API81, library
publication34 and canonical binding47. Actual SQL is not a live Telegram proof.

## Packaged startup

`docker build -t content-studio-illustration-check:59cfbab backend` exit0.
Build config `sha256:01badf73f0703486fb3102f80abafa1007112ba84c236d1904b7416750c18232`;
Docker image ID/manifest-list `sha256:c4453de4faeecd7665bed2fdafef4084f79fc730d1885c6a65fef3213039fa6c`.
Normal pip root/update notices remain disclosed; no upgrade or suppression.

Owned probe `6432bf842d2762a78702d145221fe12a0d6d974415618eaa6fd7e2f10566b8ea`
ran the packaged API with network none, read-only filesystem, no mounts, all
capabilities dropped and no-new-privileges. Actual in-container HTTP health200;
presentation/latest-review/photo503 with the expected safe missing-auth body.
Container stopped after checks and retained. No production secrets, database
access or network sender. This proves packaged startup/default-disabled reviewer,
**not** authenticated review/snapshot restart. Task4 supplies that separate gate.

Packaged frontend build also exit0, image ID
`sha256:a5d50c2588be63d986de215dff3f4d129b8b1bbbe78448e002929cc58d66dada`,
build config `sha256:cae1e53703d1c4eeefc68d2d1c6a90e7f7a1e7b9fa151d012465e2f2126f5e9d`.
`npm ci` reports zero known vulnerabilities; npm update notice disclosed, no
upgrade. An optional extra-strict no-capabilities frontend probe87877194 failed
at nginx startup because nginx requires CHOWN for its temp directory. That
cap-drop setting is not in application Compose; no application source defect
or normal deployment success is inferred. Failed no-volume container retained;
follow-up smoke uses the existing image with ordinary Compose-equivalent caps,
network none and no-new-privileges. Report its actual result separately.

Follow-up container `353a7931248afcfcb3082b9e179e744135e264dceb17049cc5da7746d1a9e549`:
nginx config test PASS and actual static HTTP index200 with the built JS/CSS
hash-named assets. Network none/no mounts; stopped and retained. No packaged
proxy/API health or integrated browser assertion from this static-only smoke.

## Browser and visual scope

Implementer frontend243/format/typecheck-build, existing33 browser and dedicated1
actual synthetic API review flow PASS. Parent inspected all three new captures:
canonical before approval1440 and390, stale-revoked390. Navy palette/composition
retained, new form wraps without horizontal clipping; fixture blue photo only,
not evidence that an illustration depicts the reported event. No redesign/CSS
change or new whole-eight pixel-perfect assertion.

Later parent inspection opened all eight current1440 DEMO section PNGs. Each
SHA-256 is identical to the same section in the create-only pre-Task3 backup
`D:/Codex-Recovery/content-studio-20261008/task3-captures-20261009-1323/.artifacts/ui-dark-navy/1440x900/`:
Overview, Inbox, Donors, My channels, Connections, Planner, Accounts, Settings.
Thus this increment leaves those accepted captures byte-identical. This is a
comparison to the saved prior application captures, not a fresh pixel-distance
comparison to the original external PNG reference package or the real-data pages.

Captures: `.artifacts/illustration-review-ui/test-results/review-real-protected-illu-d7c61--preserve-publication-gates/`.
Prior captures remain in create-only D: recovery copies documented in the task
report; parent freshly confirmed all three trees exist with85/86/101PNG files.
The exact pushed CI terminal status must be recorded separately. PHASE1 is not
complete.

## Exact remote CI checkpoint

Pushed candidate `dae0e3057b6c3b6b5d6b174b944e2b0babb01c15`, workflow37919045027.
Frontend job113782241745 SUCCESS, including243 units, format/typecheck-build, original33
browser PASS/1.9m and new protected-flow1 PASS/11.4s. Its artifact upload executed.
Admission job also SUCCESS; remaining jobs were still running, not a whole-workflow
PASS at this checkpoint. Actions runtime Node20 fallback-to24 and ubuntu-latest26
transition annotations, and artifact-action punycode/url.parse deprecations are
visible and retained; no checks disabled or unrelated automatic upgrade applied.

Later snapshot: strict PostgreSQL job113782242113, combined unattended restart
job113782241987 and channel-sync job113782242018 also SUCCESS. Backend and both
general Docker provider recovery families still in progress. New Task4 fixture
has not executed; these established recovery families do not substitute for it.

Next snapshot: backend job113782242073 also SUCCESS with the required lint,
compile and migration validation steps. Only OPENAI/OPENROUTER general recovery
jobs remained running, so whole-workflow success still not claimed.

Its actual test log:1793 PASS/1 PostgreSQL-only SKIP/674.29s, Ruff checks PASS
and migration check reports no new upgrade operations. Actual strict PostgreSQL
CI332 PASS/350.55s and combined unattended1 PASS/354.85s/four deselected are
distinct gate results, not a replacement for the parent Windows209 tests.

Subsequent terminal inspection: exact `dae0e30` workflow37919045027 **SUCCESS
in all eight jobs**, including both general OPENAI/OPENROUTER recovery families.
No failed check was disabled. This is supporting Linux CI evidence for accepted
Task3; Task4 source and its new Windows fixture are not yet covered by this run.

NEXT_STEP: isolated owned Windows Docker
HTTP/review/audit/encrypted-snapshot/photo restart and crash acceptance. Credentials-
dependent live authorization/model qualification remain separate pending gates.
