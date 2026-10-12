"""Internal persisted diagnostic configuration. This grants no execution authority."""

import json
import re
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import Text, cast, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.persistence.models import EditorialClassifierPolicyModel, OutboxEventModel
from newsflow.services.editorial_admission import EditorialAdmissionBlocked, _policy_request


class EditorialPolicyInvalid(ValueError):
    """Fixed public validation code; never includes supplied or stored values."""

    def __init__(self, code="EDITORIAL_POLICY_INVALID"):
        super().__init__(code)


class EditorialPolicyConflict(ValueError):
    """A stale or create-only configuration request cannot overwrite authority."""

    def __init__(self):
        super().__init__("EDITORIAL_POLICY_CONFLICT")


def _digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _validate(policy):
    if type(policy.enabled) is not bool or type(policy.provider) is not str:
        raise EditorialPolicyInvalid()
    try:
        _policy_request(policy, "internal-policy-validation", "Internal policy validation.")
    except EditorialAdmissionBlocked:
        raise EditorialPolicyInvalid() from None


def _entities(entities):
    return [
        {"entity_id": entity["entity_id"], "aliases": sorted(entity["aliases"])}
        for entity in sorted(entities, key=lambda entity: entity["entity_id"])
    ]


def _body(policy):
    return {
        "provider": policy.provider,
        "model": policy.model,
        "protected_entities": _entities(policy.protected_entities),
    }


def _snapshot(policy):
    values = {
        "enabled": False,
        "provider": None,
        "model": None,
        "policy_version": None,
        "protected_entities": [],
    }
    etag = None
    if policy is not None:
        _validate(policy)
        values = {name: deepcopy(getattr(policy, name)) for name in values}
        etag = _digest(values)
    return {
        "configured": policy is not None,
        **values,
        "etag": etag,
        "diagnostic_only": True,
        "real_model_qualified": False,
        "execution_authorized": False,
        "rewrite_allowed": False,
    }


def _singleton_collision(error):
    """Only the singleton PK violation can become verified create arbitration."""
    original = error.orig
    if getattr(original, "sqlite_errorcode", None) == 1555:
        return str(original) == "UNIQUE constraint failed: editorial_classifier_policy.id"
    diagnostic = getattr(original, "diag", None)
    return (
        getattr(original, "sqlstate", None) == "23505"
        and getattr(diagnostic, "constraint_name", None) == "editorial_classifier_policy_pkey"
        and getattr(diagnostic, "table_name", None) == "editorial_classifier_policy"
    )


class EditorialPolicyConfigurationService:
    def __init__(self, session: Session):
        self._session = session

    def _pristine(self):
        session = self._session
        if session.in_transaction() or session.new or session.dirty or session.deleted:
            raise EditorialPolicyInvalid("EDITORIAL_POLICY_SESSION_NOT_PRISTINE")

    def _row(self, *, lock=False):
        policy = EditorialClassifierPolicyModel
        statement = (
            select(
                policy,
                cast(policy.protected_entities, Text).label("raw_entities"),
                cast(policy.enabled, Text).label("raw_enabled"),
            )
            .where(policy.id == 1)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        row = self._session.execute(statement).one_or_none()
        if row is not None:
            expected = (
                ("true" if row[0].enabled else "false")
                if self._session.get_bind().dialect.name == "postgresql"
                else ("1" if row[0].enabled else "0")
            )
            if row[2] != expected:
                raise EditorialPolicyInvalid()
            return row[0], row[1]
        return None

    def read(self) -> dict:
        self._pristine()
        with self._session.begin():
            row = self._row()
            result = _snapshot(row[0] if row is not None else None)
        return result

    def configure(
        self, *, enabled, provider, model, protected_entities, expected_etag, actor_id
    ) -> dict:
        self._pristine()
        if (
            type(actor_id) is not int
            or not 1 <= actor_id <= 2**63 - 1
            or (
                expected_etag is not None
                and (
                    type(expected_etag) is not str
                    or re.fullmatch(r"[a-f0-9]{64}", expected_etag) is None
                )
            )
        ):
            raise EditorialPolicyInvalid()
        candidate = SimpleNamespace(
            enabled=enabled,
            provider=provider,
            model=model,
            policy_version="internal-policy-validation-v1",
            protected_entities=protected_entities,
        )
        _validate(candidate)
        body = _body(candidate)
        candidate.protected_entities = body["protected_entities"]
        candidate.policy_version = "editorial-policy-v1:" + _digest(body)
        # Validate again with the actual persisted version and canonical entity JSON.
        _validate(candidate)
        create_collision = None
        try:
            with self._session.begin():
                row = self._row(lock=True)
                policy, raw_entities = row if row is not None else (None, None)
                before = _snapshot(policy)
                if before["etag"] != expected_etag:
                    raise EditorialPolicyConflict()
                if policy is not None:
                    same_content = _body(policy) == body
                    if same_content and policy.enabled == enabled:
                        result = before
                    else:
                        if same_content:
                            # Enabled-only changes retain the legacy body and version exactly.
                            candidate.protected_entities = deepcopy(policy.protected_entities)
                            candidate.policy_version = policy.policy_version
                        table = EditorialClassifierPolicyModel.__table__
                        condition = [
                            table.c.id == 1,
                            cast(table.c.protected_entities, Text) == raw_entities,
                        ]
                        for name in ("enabled", "provider", "model", "policy_version"):
                            condition.append(table.c[name] == getattr(policy, name))
                        values = {"enabled": enabled}
                        if not same_content:
                            values.update(
                                provider=provider,
                                model=model,
                                policy_version=candidate.policy_version,
                                protected_entities=candidate.protected_entities,
                            )
                        changed = self._session.execute(
                            update(table).where(*condition).values(**values)
                        )
                        if changed.rowcount != 1:
                            raise EditorialPolicyConflict()
                        result = self._record(before, actor_id)
                else:
                    self._session.add(
                        EditorialClassifierPolicyModel(
                            id=1,
                            enabled=enabled,
                            provider=provider,
                            model=model,
                            policy_version=candidate.policy_version,
                            protected_entities=candidate.protected_entities,
                        )
                    )
                    try:
                        self._session.flush()
                    except IntegrityError as error:
                        # Keep this catch scoped to policy INSERT, never outbox/commit.
                        if _singleton_collision(error):
                            create_collision = error
                        raise
                    result = self._record(before, actor_id)
        except IntegrityError:
            if create_collision is None:
                raise
            # begin() has rolled back before checking a separate committed singleton.
            with self._session.begin():
                competing = self._row()
                if competing is not None:
                    _snapshot(competing[0])
            if competing is not None:
                raise EditorialPolicyConflict() from None
            raise
        return result

    def _record(self, before, actor_id):
        self._session.flush()
        row = self._row()
        after = _snapshot(row[0])
        self._session.add(
            OutboxEventModel(
                event_type="EditorialPolicyConfigured",
                aggregate_key=f"editorial-policy:{actor_id}:{before['etag'] or 'none'}:{after['etag']}",
                idempotency_key="editorial-policy-update:" + uuid4().hex,
            )
        )
        self._session.flush()
        return after
