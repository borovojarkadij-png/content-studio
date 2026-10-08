import pytest
from unattended_postgres import validate_postgres_target

BASE = "postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@127.0.0.1:5432/newsflow_unattended_ci"


def test_explicit_postgres_fixture_target_accepts_only_named_local_synthetic_database():
    url = validate_postgres_target(BASE)
    assert url.database == "newsflow_unattended_ci"
    assert url.host == "127.0.0.1"
    assert url.username == "newsflow_fixture"
    assert not url.query


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "not-a-url",
        "sqlite:///newsflow_unattended_ci",
        BASE.replace("127.0.0.1", "production.example.com"),
        BASE.replace("newsflow_unattended_ci", "newsflow"),
        BASE.replace("newsflow_fixture:", "postgres:"),
        BASE.replace("synthetic-unattended-ci-only", "private-credential-never-echo"),
        BASE.replace(":5432/", ":5433/"),
        BASE.replace("postgresql+psycopg:", "postgresql:"),
        BASE + "?options=-csearch_path%3Dpublic",
    ],
)
def test_postgres_fixture_refuses_ambiguous_operational_or_remote_target_before_sql(raw):
    with pytest.raises(ValueError) as error:
        validate_postgres_target(raw)
    assert "private-credential-never-echo" not in str(error.value)
    assert "production.example.com" not in str(error.value)


@pytest.mark.parametrize(
    "schema",
    [
        "public",
        "unattended_not_hex",
        "unattended_" + "a" * 31,
        "unattended_" + "A" * 32,
        "unattended_" + "a" * 32 + ";DROP SCHEMA public",
    ],
)
def test_postgres_fixture_schema_name_is_not_freeform_sql(schema):
    from unattended_postgres import scoped_postgres_url

    with pytest.raises(ValueError):
        scoped_postgres_url(BASE, schema)


def test_each_postgres_fixture_connection_keeps_exact_create_only_schema_binding():
    from unattended_postgres import scoped_postgres_url

    first = scoped_postgres_url(BASE, "unattended_" + "a" * 32)
    second = scoped_postgres_url(BASE, "unattended_" + "b" * 32)
    assert first.query == {"options": "-csearch_path=unattended_" + "a" * 32}
    assert second.query == {"options": "-csearch_path=unattended_" + "b" * 32}
    assert first.database == second.database == "newsflow_unattended_ci"
