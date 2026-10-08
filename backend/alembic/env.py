from os import getenv

from sqlalchemy import engine_from_config, pool

from alembic import context
from newsflow.persistence.models import Base

config = context.config
target_metadata = Base.metadata

# Both CLI and programmatic migrations must select a target explicitly. Older
# copied ini files must not revive the working-directory SQLite fallback.
configured_url = config.get_main_option("sqlalchemy.url", "").strip()
if not configured_url or configured_url == "sqlite:///newsflow.db":
    explicit_url = getenv("DATABASE_URL", "").strip()
    if not explicit_url:
        raise ValueError("An explicit DATABASE_URL is required; refusing a local SQLite fallback")
    config.set_main_option("sqlalchemy.url", explicit_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
