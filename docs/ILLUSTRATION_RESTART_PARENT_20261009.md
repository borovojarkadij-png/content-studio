# Parent Windows illustration restart acceptance — in progress

Base: `dae0e3057b6c3b6b5d6b174b944e2b0babb01c15`, authorized
`codex/dark-navy-ui`; Windows Docker Desktop Linux Engine29.8.0, local
`desktop-linux` npipe. Exact owned synthetic project:
`newsflow-verification-illustration-win-20261009a`, API18237/dev15394/prod18337.
No operational queues, credentials or providers are activated.

## Immutable packaged identities

Original create-only runtime manifest SHA-256:
`239fe7796c246ce1a5763f10e1897658c89868569a69d2ad5698623d0407ce34`.
Exact runtime image identities, not mutable tag names:

| Service | Docker image ID |
| --- | --- |
| api | `sha256:40a8904aaa5bf6d8600319cb2ad2efcce39d7ddf225c1a183160eaff12126fed` |
| migrations | `sha256:57a2a648d6f21361dd18a4f9db6edc75fde6959424ae41476e4520dcb4833c18` |
| worker | `sha256:1e6ef273b11eecfef105b5a3670a1f6f9f78e10b0d09fd67a34e7180daf5ec74` |
| postgres | `sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea` |
| redis | `sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499` |
| web | `sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1` |
| web-production | `sha256:6dad9afd03b97857cf2f706b0098307be640619aa9e7bd84de8fe11ef6a6c8ab` |

API/worker/backend inputs are unchanged by the test-controller comparison fix;
no replacement build or volume cleanup is needed. Fresh C:7.21GB/D:64.76GB free
at diagnosis. Later capacity must be rechecked before further packaged builds.

## Actual first execution

Parent session79669 built all packaged services, upgraded migrations/no drift,
validated API and production proxy health, and executed authenticated HTTP
presentation/photo/review/revocation plus immutable original manifests. Seed,
invalidate and pending verification passed. First down/up and exact-ID PostgreSQL
SIGKILL/crash recovery passed with independent pending reopen. Execution passed:
one approved fake-photo receipt, revoked/stale refusal, abandoned SENDING
quarantine without resend. All provider flags stayed0.

The second down/up recreated healthy services but the controller exited1 before
final verification. This execution is **FAIL, not an overall acceptance PASS**.
All original files, manifests, volumes and rows are preserved; no reseed.

Read-only parent diagnosis reproduced `Retained immutable image/mount/environment
changed`. Only the web bind source representation differed: Windows native
`C:\Users\borov\Documents\Codex\2026-09-08\files-pasted-by-the-user-software-2\frontend`
versus Docker Desktop
`/run/desktop/mnt/host/c/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/frontend`.
No image/environment or other mount difference was observed. The original writer
is correcting strict comparison with regression tests; original runtime.json
must remain unchanged. No broad path relaxation or foreign mounts are authorized.

The create-only PowerShell transcript
`D:/Codex-Recovery/content-studio-20261008/task4-windows-20261009-1104.log`
contains invocation/start/end metadata, not native child output. Tool output
records the observed stages; do not describe that file as a full execution log.
Fresh retained verification will capture native output separately without
recreating the fixture. Actual final acceptance, source review and new CI remain
pending. Live Telegram/AI tests and model qualification remain separate pending
gates; this synthetic procedure never grants production publication permission.

NEXT_STEP: finish strict Desktop mount-alias regression fix, then verify original
retained final rows twice and repeat guarded down/up/crash/reopen without reseed.

## Corrected comparison and retained reopen

Frozen controller SHA-256
`5175a05685d6e10a1befbaed5e860ef5c94f5d0007289bf73db283e626aad813`;
probe unchanged `d917cef2d8e7156d5df7ce00ef006f637b8a1bd00c85e2f4d581eb4bb9483039`.
Original runtime.json hash remains unchanged. Scoped94 regression cases passed,
including the actual resource-validator RED/GREEN and rejected foreign paths,
traversal, mount modes/types/destinations, images and environments.

Parent retained Mode verify: two independent verify-final processes PASS,
real Telegram/AI calls0; outer exit0. Native output is actually captured in
`D:/Codex-Recovery/content-studio-20261008/task4-retained-verify-20261009a.log`.

A parent follow-up logging wrapper used unsupported PowerShell
`Tee-Object -LiteralPath -Append`. Its parameter error cancelled the pipeline
after the owned down, leaving only original volumes/files; this wrapper execution
is FAIL. No controller/platform success is claimed for it. Fresh read-only
inventory confirmed no running controller or project containers/network. Recovery
validates original ownership/config/secrets, absent containers/network and each
original volume's exact name/project/volume labels/options before starting only
the original Compose graph; no build, reseed or manifest overwrite. Its actual
result is still pending. The corrected log sink uses fixed FilePath for append.

Subsequent actual results supersede only that pending recovery status:

- Recovery session32247 exit0: original retained graph up, packaged API/proxy
  health and two verify-final reopens PASS; no build/reseed. Native output saved
  in `D:/Codex-Recovery/content-studio-20261008/task4-retained-recovery-20261009a.log`.
- Corrected boundary session36991 exit0: whole-stack down/up, two independent
  final reopens, exact-ID PostgreSQL crash/recovery, two final reopens, separate
  Redis/worker restart, packaged API/proxy health, two final reopens and final
  Alembic no-drift all PASS. Native output saved in
  `D:/Codex-Recovery/content-studio-20261008/task4-retained-boundaries-20261009a.log`.

These combined actual Windows stages verify retained review/audit/encrypted
snapshot/photo/receipt and quarantine persistence on the corrected test
controller. The original failed create invocation is not relabeled successful.
The original manifests remain create-only; all final reopen checks retain exactly
one approved fake receipt, revoked/stale blocked intents and abandoned SENDING
quarantine with no resend, no rejected-content rewrite jobs and real provider
calls0. Separate Redis/worker restart was performed after execution, not while
the intents were pending; earlier pending recovery covers whole down/up and PG
crash only. Current source review and exact new CI remain pending.

## Independent review and corrective gate

Source `bfba7ede98d775510abd5353f4182c68ceb60b18`, full backend1871 PASS/1
local PG-only SKIP/326.78s and scoped94 PASS. Independent review did not approve
the test controller: redirected build/bind inputs need prewrite/retained checks;
retained up must not execute mutable replacement images before detecting them.
Actual parent Windows inputs had been checked non-reparse and recorded images
remained unchanged, but those facts do not remove the general CLI guard defects.
Original writer owns fix round1/5 and regressions. No Task4 source acceptance,
push or exact new CI success is claimed before the fix and scoped re-review.

Fix1 frozen controller SHA-256
`0af2eed48878a5007071956eb049d512703ba15dd24bd1654f4bf1ba1ef4e12d`.
Production/probe/crash-helper inputs remain unchanged. Actual RED junction/tag
regressions preceded covering152 PASS/27.79s plus lint/format/compile. The earlier
full1871 result is pre-fix historical; exact new full remote CI remains required.

Parent session10576 exit0: original input/runtime validation and seven exact
image-ID/tag resolutions PASS; retained full down/up pinned by stdin original
IDs with no-build/pull-never, two final reopens, exact PostgreSQL crash/recovery
and two final reopens all PASS. Native output:
`D:/Codex-Recovery/content-studio-20261008/task4-fix1-immutable-boundaries-20261009a.log`.
No new fixture files, image build, seed or secret generation. Original runtime
manifest SHA remains239fe779 above. Scoped independent re-review is still pending.

Subsequent independent re-review at source
`a6981f26d52130331ba5bd5b0fe9bcb9acd9f712`: both Important findings ADDRESSED,
no new Critical/Important/Minor. Task4 source and corrected retained synthetic
Windows acceptance are accepted; exact new full nine-job CI and broader
cross-task commercial QA remain pending. PHASE1 and live acceptance are not
complete. Preserve the original fixture and every failed/historical log.

## Exact nine-job baseline CI

Source `7af4324cac284b8bd3085eecb80e14c166149ccc`, run37924345507: all nine
jobs SUCCESS. Backend1929 PASS/1 PG-only SKIP/433.72s; strict migrated
PostgreSQL332 PASS/323.18s; frontend243/format/build plus33 browser and1 real
protected-review browser PASS; unattended full-stack1 PASS/4 deselected/354.31s.
Illustration job113799583934:136 focused PASS/44.68s, packaged build/migrations/
no-drift/HTTP health/seed/invalidate/pending first down-up/PG crash/fake execution/
final down-up/create PASS and two final read-only reopens PASS. Synthetic
ownership/image evidence artifact11613471511 contains six files, zip digest
`d6fee2938b0a8abbf4497fae176169d2b6dea19a38ef71ee389a13a5cd24bbe0`.
No real RPCs. All other recovery families passed. Runner deprecation warnings
remain visible. Broad review subsequently found four Important cross-task
defects; their new correction wave is not covered by this baseline CI. Neither
PHASE1 nor operational/live release acceptance is complete.
