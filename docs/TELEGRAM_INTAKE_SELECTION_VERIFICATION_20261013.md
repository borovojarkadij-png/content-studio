# Telegram intake selection kernel — verification

Scope: pure deterministic ranked selection, not durable ingress activation.
Source920c099fe035cc4757c7c7bbf38d829fb26871e1; exact two new product files.
Accepted dark-navy UI and operational configuration unchanged.

## Source evidence

Actual importability and behavioral RED retained; final new127cases and
covering300cases PASS/native0, Ruff/format/compile/AST import boundary clean.
Commands, intermediate failures, fixtures and exact exits are in
`.superpowers/sdd/TELEGRAM_INTAKE_SELECTION_IMPLEMENTATION/task-1-report.md`
and D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/.
Scoped independent review and final integration review: Compliant/Approved,
no Critical/Important/Minor findings. Verbatim reports retained in the plan
workspace; this is not whole historical branch/release acceptance.

Frozen source SHA256:

- backend/src/newsflow/domain/intake_selection.py:
  B94DB8757C0B354503FA563C24B37EC43477DA7EBD8BDB26CC20CA4C27DDDB39.
- backend/tests/test_intake_selection.py:
  4CE4114DA600663FCE9D23AF708292EE8FFA8AE64DB2B989957BFEBA2528DDB7.

## Actual installed Docker package

Controller verify-package.ps1 and independent packaged-intake-selection-smoke.py
in D:/Codex-Recovery/content-studio-20261008/intake-selection-acceptance-20261013a/.
Executed unchanged backend/Dockerfile at exact candidate
4544143e05d7c8435d934c620e960c2e746bbad2; build native0/smoke native0.
Image sha256:d4862c940b11d71c5403b1267f72ec8d48dc977b12134bc2a2f6a8edec07dbcb,
Python3.12.15. All326 committed backend input hashes captured and independently
matched after completion. Container networknone/readonly/noVolumes/noSecrets,
32MiB tmpfs/capdropALL/no-new-privileges; zero provider calls.

Smoke verifies independent literal TOP_SCORE/RANDOM/HYBRID picks, permutations,
unknown/excluded/threshold reasons, fractional carry and two fresh Python
processes producing identical selection/digest. Output explicitly states
durable_ingress_verified=false and selection_grants_authority=false.

Evidence SHA256:

- package-smoke.log:
  8E5511BF17E95715EDE02B80DDC8527E99A9B275433346D1C1958CC24BD3EC80.
- package-receipt.json:
  322622661B0797520D0250AB1C332BF1B55D755CAC065553DC156E3898F7D227.
- packaged-intake-selection-smoke.py:
  BAE533A0AA85348C76C47567C6AEA446E7AC84B8022536816E3844F0330015BF.

## Remaining boundaries

No persisted ranked window/carry, pre-AI hold/release, targetmix or worker
activation is implemented by this disconnected kernel. Existing editorial,
fact/source/current-policy guards remain mandatory; a selected ID never grants
rewrite or publication authority. Exact new hosted CI is pending. Real Telegram
authorization, real model qualification and PHASE1 completion remain pending.
