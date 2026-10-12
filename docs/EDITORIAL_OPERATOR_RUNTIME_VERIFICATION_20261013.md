# Packaged editorial operator acceptance — Windows Docker

Status: DEFAULT STARTUP/AUTH DISABLED PASS; OPTIONAL MOUNT/RESTART PENDING.
Not PHASE1 completion, operational activation or live model/Telegram acceptance.

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

After optional operator override independent source review, use only this exact
owned synthetic fixture to attach its existing separate public file. Actual
GET/PUT/ETag/reload/audit/no-jobs, wrong bearer/private401, preserved policy/token
through API restart and down/up, file/hash/mount separation and DB recovery are
still pending. Existing real sessions/operational stack remain unchanged.
Final frontend image/health/browser and exact source CI are independent gates;
default startup alone cannot promote these to verified. Retain all test storage
and evidence, never down-v/prune/reset or reseed an existing fixture.
