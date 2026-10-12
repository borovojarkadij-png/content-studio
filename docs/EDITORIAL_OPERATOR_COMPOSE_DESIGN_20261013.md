# Optional persistent editorial operator mount

Status: prepared only; implementation follows independently reviewed Settings
tasks. No credential provisioning, container mutation or runtime acceptance.

The existing protected API must remain disabled without a separately provisioned
operator file and identity. Add an optional compose.editorial-operator.yaml,
following the existing illustration-review override, rather than putting a
credential dependency into the default stack or reusing the reviewer/master key.
This is deployment configuration for the approved API, not a new auth system.

Mount one existing host persistent regular secret as editorial_operator at
/run/secrets/editorial_operator, into api only. Require explicit
NEWSFLOW_EDITORIAL_OPERATOR_SECRET_SOURCE and NEWSFLOW_EDITORIAL_OPERATOR_ID;
runtime validates the positive signed64 identity and bounded token as before.
Compose rendering must never create a missing source, generate a credential,
read its contents, or forward it to frontend, worker, migrations or Redis.
The host path is outside Git, separately owner-ACL controlled and independent
of reviewer/master/provider/session credentials. Runtime reopen/alias/inode
refusal remains authoritative; Compose config is not a credential-validity test.

Keep compose.yaml, compose.dev.yaml, Telegram/reviewer overrides and service
business logic unchanged. Support explicit development and production file
combinations, including reviewer coexistence. Document loopback/TLS requirements,
host secret backup separate from encrypted SQL, explicit rotation/recreate
semantics, and default-disabled503. Never promise file-content rotation through
a retained mounted inode without recreating api. No automatic authorization.

Verify actual docker compose config --format json with synthetic env only,
independent development/production combinations and both overrides. Assert
default has no operator secret or auth variables, missing interpolation refuses,
enabled mount belongs exclusively to api and secret source is exact, existing
master/reviewer mounts remain, and rendering does not create source files.
Preserve all CLI native failures/output; expected missing-input negatives are
not stack failures. Existing auth/API/reviewer tests remain targeted regression.

Source/config verification is not Docker persistence E2E or live acceptance.
At the final candidate, actual isolated packaged api restart/down-up and a stable
synthetic operator file must be checked without reusing operational volumes.
Real credential provisioning and Telegram/model acceptance remain consolidated
external actions. No new secret, real session, provider call or publication.
