# Packaged editorial operator acceptance — Windows Docker

Status: DEFAULT DISABLED AND OPTIONAL MOUNTED WINDOWS RUNTIME/PERSISTENCE PASS.
Not PHASE1 completion, operational activation or live model/Telegram acceptance.

## Current affected-candidate result — 2026-10-13

Optional Compose64ce1e9 independently approved (spec and quality, no blocking
findings); actual197 covering tests/native0. Root attached only the existing
separate public synthetic files in the exact owned fixture below. Actual
production startup/migrations/health/native0; API-only read-only operator,
reviewer and master mounts inspected. No worker container exists. Wrong/no
bearer and reviewer bearer return private401/no-store; correct operator reads
unconfigured200, then actual browser creates and updates the diagnostic policy.
Both browser saves changed the exact ETag and produced exactly2 immutable
EditorialPolicyConfigured outbox events with actor29/unique idempotency keys.
Exact spaced/multiline alias survived SQL and browser reload. A no-op PUT
preserves ETag/audit; stale create-only PUT returns private409/no extra event.

Root actual API restart, Compose down/up without volume deletion, and normal
PostgreSQL restart/recovery each completed native0 with healthy stack and
byte-identical canonical policy/SQL/audit/REJECT/secret-hash snapshots. This is
a normal PG restart, not a newly claimed hard-crash test. After down/up new
owned APIc2e5fe251fe1f25bd30eadb903ceadfaae5aa4263776e8cda8bfe66daccc45ae,
PG2ad14cabdc57f56cfa4281b4a1609a777658c30e960b872ee243106630588341,
weba5c2d02992085ace83ebd8bc3041174960e67cf346168d73e02e11cc0de32060
retain the candidate images and original named PostgreSQL volume. No reseed.
Actual packaged browser reload clears the memory-only token; explicit reload
with the same public synthetic operator reads the original model/ETag/alias.

REJECT row1 remains REJECT/rewrite_allowed=false. All6 counts remain0:
rewrite jobs, diagnostic jobs, diagnostic attempts, publication jobs, rewrite
usage and semantic jobs. Diagnostic policy remains disabled/unqualified and
execution_authorized/rewrite_allowed=false. No Telegram or AI provider IO.
All3 separate synthetic file hashes remain equal to pre-activation values.
Four persistent-*.json files have the same SHA256:
3CBCC5E94CF1ECC3B1532878C2CA2566F350449B7C0EADFD5EA397100022DC6C.

Actual root transcript SHA256 values:
- verification-Baseline.log (guard-only failure):41B178FC96D13071E1FC2EB6E3CBD22EE3CB91F3014F1FB72335A756129DDAF5;
- verification-Baseline-b.log:57057B338BD683DE51AA53ECCA3E929A134FADAF21E71C5CB812EF10D7415A5E;
- verification-ApiRestart-a.log:8A682E2076B0893AB0B442E07A51A239CFAC9BF0F62F22DDBAD07382A01B7146;
- verification-DownUp-a.log:3A96207B058F1B82F5863539D97D4456D2DEAE13EC7DA00F633FBD402D3A07A3;
- verification-PostgresRestart-a.log:9683CE6911F3B2AABE1AB458F4420B66E5252CC2303EC77C2E48C413418C710A.

Root verification script/raw transcripts and exact snapshots are retained at
the fixture root below. Initial guard-only baseline attempt failed before HTTP
or mutation: PowerShell @($null).Count is1 despite actual PG port5432:null;
corrected explicit null check and preserved original log. No application bug
or port exposure. API restart emitted deprecated --time warning; subsequent
PG check uses supported --timeout, original warning retained. Neither failure
nor warning is hidden. Snapshot statements read the actual PostgreSQL rows;
native command statuses are captured immediately in transcripts.

Exact UI CI38319840777/head1bb3463 is terminal FAILURE, not green:8other jobs
SUCCESS; Backend performed2936PASS/15SKIP714.46s then standalone fixture Ruff
I001 failed due backend-cwd bare Alembic import classification. This affects
browser test fixture only, not the immutable runtime image inputs. Original
backend.logSHA256880CD8560FB8D98897B316B68EB268B3BE2297DD27F85ECB7A5595BE6E485970.
Minimal source5413179 changes only import/call to alembic.command.upgrade;
Ruff0.17 backendRED1 then backend/rootGREEN0, compile0 and targeted3browser
PASS8.1s. Fresh scoped review findingADDRESSED/specPASS/qualityPASS/no new
breakage. Final exact branch-head CI remains pending; historical successes do
not replace it. No UI redesign, operational secret or authorization changed.

Reviewed original Compose report SHA256D2B1304A1AC3A6D71233D29AC011ADC1AC8AC8E6BF6AF57D4C5C0E29BBDEBEF4.
Root git whitespace gate caught14 quoted trailing spaces and blank report EOF;
removed presentation whitespace only before evidence commit. Original raw
logs/native receipts are unchanged; no original output/status reconstructed.

## Exact candidate and isolation

Accepted backend sourcec9d12471b0da361d0534be64a48b51f8dd129791. Root checked
backend/src/alembic/pyproject/Dockerfile unchanged through85e1d4c; concurrent
Task2 owns only browser fixture/CI paths, not these inputs. Windows Engine29.8.0/
Linux/API1.56. Actual build native0, image
newsflow-verification-editorial-api:c9d1247-20261013a, digest
sha256:164171b35d2b8f19e21051cc0ab9015619f7f9a44ed2fe3253458957ce5f914e.
Build log/provenance in EDITORIAL_SETTINGS_VERIFICATION_20261013.md.

Create-only fixture root:
D:/Codex-Recovery/content-studio-20261008/newsflow-verification-editorial-win-20261013a/.
Projectnewsflow-verification-editorial-win-20261013a, owner
content-studio-editorial-verification-v1, nonceae88ef7dfeaf44da84e6f8ab563216d3.
ownership.jsonSHA25640388351A47D00C517D3B1521BB3CF28720BE2A2C6F52B43AD8701303CE465DB.
Exact project containers/network/named-volume prefix and ports18240/15391/18340
checked absent before creation; no old fixture/operational volumes reused.
Existing strict-test PostgreSQL on5432 stays untouched. Fixture PostgreSQL has
no published port. All source/ingestion/rewrite/classification/semantic/media/
publication worker opt-ins explicitly0. Separate public deterministic synthetic
master/operator/reviewer files only; no real credential discovery/generation.
Copied process NEWSFLOW_*/POSTGRES_*/DATABASE_URL/REDIS_URL values were cleared
for Compose and restored in finally, never printed or persisted.

## Actual default packaged gate

Actual base compose.yaml + fixture compose.override.yaml, explicit synthetic
--env-file, exact project, both profile definitions. Config JSON captured;
no operator secret definition or operator secret-file environment setting.
`docker compose ... up -d --no-build --wait --wait-timeout 180 api` native0.
Startup uses immutable candidate image for api/migrations; PostgreSQL16-alpine
and Redis7-alpine are healthy. Packaged migrations exited0, API healthy.
Only api/dependencies started; no worker/dev/production frontend runtime claim.
default-startup.logSHA256
E23B7E3ADFE222F6E7E0B316B85302F2CF92D6A3A2FBA5D3190A1E99C0A18926.

Actual urllib HTTP assertions native0:
- /healthz200 with status=ok;
- /api/settings/editorial-policy503 with Cache-Control:no-store, both without
  bearer and with the public synthetic bearer;
- body contains only static detail, no configuration or authority granted.

default-http.logSHA256
F5EE0367106168553BA61928BEB24F5954880147C95E8C09FFDEA88EBCAA74A2.
Container identities/labels actually checked:
api259fe000aa363ed5d3043eaa488d1dfe280c93accafee938bcefa5cf36ef73cf;
postgres7ccf3f4cb1aac9e21567b9a3533712a11d281e9f322341c4f2d556d298c17a2e;
redise4c6b69641789b6b83881b3854d480c175feda41e08b7444176eb3ba3ef44239;
migrations0c9ec28d1878c89010b67cd158c2a3d2e3ab2e6403f8408c78261a32af8fa93d.
api/migrations actual image digest matches candidate; no wrong resource mutated.

Root subsequently checked the exact new PostgreSQL container ID, then actual
read-only psql query of policy/outbox/rewrite/classification/publication counts
returned `0|0|0|0|0`, native0. This initial default snapshot is tool-transcript
evidence, not a later fabricated original raw log. It is unrelated to retained
strict-test namespaces in the separate5432 fixture.

## Pending affected-candidate gate

Optional Compose source64ce1e9 DONE/197coveringPASS/native0/no pytestwarning
or skip; root independently matched3frozenhashes and parsed entire actual
CLI evidence inventory:7JSONrenders (1behaviorRED+2default+4enabled),8refusals,
actual terminal197PASS/native0. Fresh independent source review pending.
Root actual candidate config with both profiles and both optional overrides:
native0, exact source, operator auth/mount exclusivelyAPI; other services do
not receive operator/reviewer auth variables. Create-only operator-runtime.env
contains ordinary synthetic values, process-only IDs/source interpolation.
Original default test.env/ownership/data unchanged; config is not mount proof.
All3publicsyntheticsecret hashes recorded before activation, distinct paths,
nonreparse regularfiles. Create-only synthetic REJECT row id1/statusREJECT/
rewrite_allowedfalse inserted in exact owned PostgreSQL, native0. No job or
provider execution. Mounted startup/recovery waits for source review approval.

Root packaged frontend diagnosis retained under editorial-web-image-20261013a:
original build native1, actual cached npm debug reports failed optional
dependency /app/node_modules/@rolldown/binding-linux-x64-musl while npm exits0.
Same immutable Node image/lockfiles in clean executable-overlay container:
npmci104packages/native0 and actual Rolldown import PASS. Initial diagnostic
used noexec tmpfs (separate load-permission defect, not original root cause).
Cached-layer probe confirms package absent despite successful cached npm step.
No code/lock/version/base-image change or cache/volume deletion. Actual standard
frontend Dockerfile rebuild --no-cache succeeds native0, build-fresh.log SHA256
8C9B01370D54376D8F4E95A3371AC9B9BEEE94C9CB32FCEB8A7C3409311EE27C.
Candidate image newsflow-verification-editorial-web:20261013a actual identity
sha256:7f3f56fafa33ee97dd3a84cf609ff7eedc55c92c9366537457ee5f58986fe666,
source labelddb2c20067470af1558035d4e9029dd39ce18c06. Existing immutable
backend image remains unchanged. Actual frontend startup native0, default
packaged nginx health200 and exact static assetsHTTP200/native0. Asset names
index-BIGfI_fV.js/index-Clz7HfYA.css match local accepted build. HTTP probe
checks503/no-store through nginx with/without public synthetic bearer.
default-web-startup.logSHA2560D6B5F0606D73BDA1074239C99FC2D26371F19276672048AEDD4CC765EC348EC;
default-web-http.logSHA2566FC442E7DDFB53D0631A40290771CB6A4B57FEA8F4686B1F7C207D0EFBF29159.
Actual web container835f4e73357fa82cbfb4876fde5ebf16e7b11e87f0899f07dbaabf96d0bf9064,
correctproject/image/healthy inspected. Root browser opened exact18340, read
actual SQL-backed Overview0records, Settings/Модерация masked memory-only
operator field and explicit synthetic load honest503. Root actual screenshot
visually confirms existing navy layout, not a newdesign. No worker/auth grant.

Root evidence push1bb346351edadd710350310ed0c05f9038b864a8 native0, exact
remote HEAD matched on authorized origin/branch; existing owner process-local
credential restored finally. Exact CI38319840777 all9jobs in progress at
inspection, not accepted yet. Original task2 report presentation had two raw
trailing spaces/blank EOF; root removed only these for git whitespace gate.
Original reviewed report hashA79F... retained in receipt; committed presentation
hash2578BB4995CFA885FE24C9B4D9460E9364B48DF50B9E73331570895622C64A5D.
Actual raw logs/hashes are unchanged; no native receipts fabricated.

After optional operator override independent source review, use only this exact
owned synthetic fixture to attach its existing separate public file. Actual
GET/PUT/ETag/reload/audit/no-jobs, wrong bearer/private401, preserved policy/token
through API restart and down/up, file/hash/mount separation and DB recovery are
still pending. Existing real sessions/operational stack remain unchanged.
Final frontend image/health/browser and exact source CI are independent gates;
default startup alone cannot promote these to verified. Retain all test storage
and evidence, never down-v/prune/reset or reseed an existing fixture.
