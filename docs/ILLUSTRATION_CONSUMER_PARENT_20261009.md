# Illustration consumer parent verification — 2026-10-09

Reviewed source: `6b3ea491d153b780c939f111b574bc4c36e6b57c`, base
`f2f2092db85fda1fe369fc8b5485a91471f1d32d`. Only authorized origin
`borovojarkadij-png/content-studio`, branch `codex/dark-navy-ui`.

Independent task review: spec compliant / quality approved, no Critical or
Important findings. Outside-diff checks covered final durable guard ordering,
canonical rights/binding resolution, transport/session closure and old snapshot
compatibility. Unrelated pre-existing broad formatting noise remains disclosed;
changed-file formatting passed. Cross-task reviewer auth/storage was accepted
separately; review of this consumer is not a fresh audit of the entire product.

## Actual Windows PostgreSQL

Only the retained label/ID/volume-validated synthetic unattended PostgreSQL was
started. It serves the strict public synthetic database/role on loopback 5432;
every migrated fixture creates a fresh `unattended_<uuid>` schema. No operational
database, old fixture reseed, truncate or volume deletion.

From `backend`, with TEMP/TMP on the task recovery drive, isolated Telethon1.45
PYTHONPATH and the strict `NEWSFLOW_UNATTENDED_POSTGRES_URL` documented by
`backend/tests/unattended_postgres.py`:

```powershell
python -m pytest tests/test_illustration_publication.py tests/test_illustration_review_api.py -q
```

**115 PASS /202.67s, exit0**, session14196, frozen Task2 source. Both modules use
the migrated library fixture's strict create-only PostgreSQL harness. Includes
canonical review/audit and newest review, revocation, byte/caption/rights changes,
stale retries, encrypted snapshot corruption and uncertain-delivery zero resend.
No skipped PostgreSQL boundary. Actual SQL verification is not Telegram login.

The implementer's distinct final local gate was **1746 PASS/1 PostgreSQL-only
SKIP/302.04s**; frontend **208 PASS**, format/typecheck-build and one focused real
synthetic API browser PASS. The local SKIP is not relabeled PASS by implication.

## Packaged startup

```powershell
docker build -t content-studio-illustration-check:6b3ea49 backend
```

Build exit0; exact image config
`sha256:8dd159b4e55fae3daf57b47f051fd4f85184eb00f960ba92c5c2e41f39e50eee`.
Normal pip root-user/update notices were visible; no dependency upgrade command
or warning suppression was used. The image contains packaged source, not tests,
real keys or operational configuration.

Owned container
`b80a88ff179176924622c7c1a2629e2bc35f5339b72a59d172acce96382c63ce` ran that
image with network none, read-only filesystem, no volumes, all capabilities
dropped and no-new-privileges. In-container actual HTTP `/healthz` returned200;
unconfigured reviewer returned503 with the safe expected body. Probe stopped
after checking; container/image retained. This proves packaged startup and
default-disabled reviewer, **not** illustration review/snapshot down-up, runtime
database acceptance, real reviewer activation or live publication.

## CI / visual boundary

Exact Task1/documentation `f2f2092` workflow37912841383 finished SUCCESS in all
eight jobs. That is not Task2 CI evidence. Task2 plus documentation was pushed
as `cb0516d1584273d62ab2ddb9fd605a68891fae8c`; workflow37915759740 was running at
this checkpoint. Record its terminal result separately.

Fresh completed job logs of that exact candidate: backend1746PASS/1SKIP/389.24s,
lint and migrations/no drift PASS; strict migrated PostgreSQL332PASS/332.16s;
frontend208 units/33 browser/format/typecheck-build PASS. Sync, admission and
combined unattended restart jobs also SUCCESS. The two general Docker provider
families were still running at inspection, so no whole-workflow success inferred.

Subsequent terminal inspection of exact `cb0516d` workflow37915759740: **all
eight jobs and whole workflow SUCCESS**, including both OPENAI/OPENROUTER Docker
recovery families. This is Linux CI support for Task2, not the new Task3 source,
Windows illustration-specific down/up or live authorization.

Focused Task2 Planner desktop/mobile captures remain in
`.artifacts/ui-dark-navy/test-results/studio-guarded-real-media--1e3e2--and-releases-it-on-refresh/`.
The parent inspected the narrow390 capture: existing navy composition retained,
warning fits without horizontal clipping, no new approval controls yet. Previous
accepted captures were preserved create-only at
`D:/Codex-Recovery/content-studio-20261008/task2-browser-before-20261009-1249`.
Not a fresh eight-section pixel-perfect acceptance assertion.

NEXT_STEP: protected current source/draft/photo presentation and human review UI,
then owned actual Docker illustration review/snapshot restart acceptance. All
network workers and real credentials remain unactivated. PHASE1 is not complete.
