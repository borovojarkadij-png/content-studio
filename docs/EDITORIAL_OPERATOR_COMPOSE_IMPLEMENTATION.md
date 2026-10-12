# Optional editorial operator Compose implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development. One writer, actual configuration
> behavior tests and independent spec/quality review. Prepared, not dispatched.

**Goal:** Supply an explicit API-only persistent operator credential mount for
both existing Windows dev and production configurations, disabled by default.

**Architecture:** One optional override, strict interpolation and existing
runtime authentication. No default-stack or business-logic change.

**Tech Stack:** Existing Docker Compose CLI/PyYAML/pytest; no dependencies.

**Spec:** EDITORIAL_OPERATOR_COMPOSE_DESIGN_20261013.md and accepted protected API.

## Global Constraints

- Telegram Content Studio only; accepted navy UI unchanged.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no worker push, merge, force-push or PR.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- No real credentials/env files/sessions/provider calls/publication/operational
  SQL or containers. No credential creation/rotation or runtime activation.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN and actual candidate acceptance.
- Default Compose stack has no operator credential dependency. api only receives
  the separate optional mount; workers/frontend/migrations never receive it.

### Task 1: Optional mount, actual CLI behavior regressions and operator docs

**Files:**
- Create compose.editorial-operator.yaml.
- Create backend/tests/test_editorial_operator_compose.py.
- Create docs/EDITORIAL_OPERATOR_AUTH.md.
- Own SDD task-1-report.md only; no existing Compose/API/CI/UI/source changes.

**Interfaces:** Existing operator reads
NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE and NEWSFLOW_EDITORIAL_OPERATOR_ID.
Override requires NEWSFLOW_EDITORIAL_OPERATOR_SECRET_SOURCE, uses secret name
editorial_operator and target /run/secrets/editorial_operator. Do not add defaults.

- [ ] Write actual config behavior test first; a temporary minimal override
  scaffold `services: {api: {}}` allows CLI rendering before the feature exists.
  Run RED against actual successfully rendered JSON lacking the required
  api-only operator mount/variables, not missing-file/import/startup errors.
  Then replace that no-behavior scaffold with the real override below.
  Use subprocess.run Docker
  Compose config with timeout30/capture/native code and a synthetic tmp env file,
  never load host .env. Clear copied NEWSFLOW_* and POSTGRES_* inputs and supply
  only fixture env/master/reviewer/operator values. No daemon startup/build.
- [ ] Implement this complete override:

```yaml
# Explicit opt-in API-only persistent operator credential. Never auto-provisioned.
services:
  api:
    environment:
      NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE: /run/secrets/editorial_operator
      NEWSFLOW_EDITORIAL_OPERATOR_ID: ${NEWSFLOW_EDITORIAL_OPERATOR_ID:?configure an explicit positive single-human operator identity}
    secrets:
      - editorial_operator
secrets:
  editorial_operator:
    file: ${NEWSFLOW_EDITORIAL_OPERATOR_SECRET_SOURCE:?provision a separate existing persistent operator secret outside Git}
```

- [ ] Test default both profiles: actual JSON has no operator secret definition,
  api auth variable or service mount, even if external source/ID variables are
  present. No reading/creating referenced source files.
- [ ] Test source/ID each missing and empty: config native nonzero, no successful
  JSON acknowledgment; preserve returned diagnostics without real values.
- [ ] Test dev using base+dev+operator and production base+operator separately,
  then each with illustration-review too. Assert source path exact, api target
  variable and actor string exact; only api has operator mount/env. Existing
  master mount remains api+worker, reviewer remains api only, all other services
  lack operator source/mount/auth environment. Source stays uncreated.

  Minimal actual-boundary example (expand into the combinations/negatives above):

```python
def test_operator_mount_is_api_only(tmp_path):
    import json
    import os
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    environment = tmp_path / 'synthetic.env'
    environment.write_text('POSTGRES_PASSWORD=synthetic-only\n'
                           'DATABASE_URL=sqlite:///synthetic.db\n', encoding='ascii')
    child = {key: value for key, value in os.environ.items()
             if not key.startswith(('NEWSFLOW_', 'POSTGRES_'))}
    source = tmp_path / 'uncreated-operator-source'
    child.update(NEWSFLOW_ENV_FILE=environment.as_posix(),
                 NEWSFLOW_MASTER_KEY_SOURCE=(tmp_path / 'uncreated-master').as_posix(),
                 NEWSFLOW_EDITORIAL_OPERATOR_SECRET_SOURCE=source.as_posix(),
                 NEWSFLOW_EDITORIAL_OPERATOR_ID='29')
    result = subprocess.run(
        ['docker', 'compose', '--env-file', str(environment),
         '-f', str(root / 'compose.yaml'), '-f', str(root / 'compose.dev.yaml'),
         '-f', str(root / 'compose.editorial-operator.yaml'),
         '--profile', 'dev', 'config', '--format', 'json'],
        env=child, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed['services']['api']['environment'][
        'NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE'] == '/run/secrets/editorial_operator'
    assert parsed['services']['api']['environment']['NEWSFLOW_EDITORIAL_OPERATOR_ID'] == '29'
    assert any(item['source'] == 'editorial_operator'
               for item in parsed['services']['api']['secrets'])
    assert all(all(item['source'] != 'editorial_operator'
                   for item in service.get('secrets', []))
               for name, service in parsed['services'].items() if name != 'api')
    assert not source.exists()
```

- [ ] Human docs: complete explicit dev/prod/coexist command lines, mandatory
  separate existing file/positive signed64 ID/32–128 ASCII token optional LF,
  no runtime generation, owner ACLs/untracked outside Git/TLS or localhost.
  No real secrets/examples suggesting provider/master/reviewer reuse. Backup
  separately from encrypted SQL; restart/rebuild preserve host file; explicit
  rotation/recreate API for retained inode; default503 versus missing/wrong401.
  Saving diagnostic policy is not gate disable/qualification/publication.
- [ ] Run focused new CLI tests plus existing reviewer Compose/auth API tests;
  explicit Telethon1.45/backendcwd, unique D: temp/cache and no host auth paths.
  Ruff0.17 changed-test lint/format, YAML/diff checks. No repeated full backend,
  old Docker persistence or frontend gate for configuration-only bytes.
- [ ] Freeze owned hashes, report exact commands/native/RED/GREEN/SKIP/warnings/
  limitations and self-review; commit only owned3paths/report, no push. Root
  reads evidence and fresh spec/quality review before actual candidate gate.
