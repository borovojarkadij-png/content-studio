"""Test-only create-only PostgreSQL namespaces; never target operational storage."""

import re
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.schema import CreateSchema


def validate_postgres_target(raw):
    try:
        url = make_url(raw)
    except (ArgumentError, ValueError, TypeError):
        raise ValueError("Explicit isolated synthetic PostgreSQL target required") from None
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port != 5432
        or url.database != "newsflow_unattended_ci"
        or url.username != "newsflow_fixture"
        or url.password != "synthetic-unattended-ci-only"
        or url.query
    ):
        raise ValueError("Explicit isolated synthetic PostgreSQL target required")
    return url


def scoped_postgres_url(raw, schema):
    url = validate_postgres_target(raw)
    if not isinstance(schema, str) or re.fullmatch(r"unattended_[a-f0-9]{32}", schema) is None:
        raise ValueError("Create-only synthetic schema identity required")
    return url.update_query_dict({"options": "-csearch_path=" + schema})


def create_postgres_namespace(raw):
    url = validate_postgres_target(raw)
    schema = "unattended_" + uuid4().hex
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            # No IF NOT EXISTS, DROP, delete, truncate or public-schema migration.
            # An existing namespace is an error, never permission to reuse/reset it.
            connection.execute(CreateSchema(schema))
    finally:
        engine.dispose()
    scoped = scoped_postgres_url(raw, schema)
    scoped_engine = create_engine(scoped)
    try:
        with scoped_engine.connect() as connection:
            if connection.scalar(select(func.current_schema())) != schema:
                raise RuntimeError("Synthetic migration namespace could not be verified")
    finally:
        scoped_engine.dispose()
    return scoped.render_as_string(hide_password=False)
