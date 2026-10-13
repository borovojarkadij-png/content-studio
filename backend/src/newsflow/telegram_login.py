"""Explicit operator-only first Telegram authorization: disabled by default."""

import argparse
import asyncio
import getpass
import os
import re
import sys
import unicodedata
import warnings


class _PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's normal errors include untrusted argument values.
        raise ValueError("Invalid login invocation")


def _positive_id(raw):
    if re.fullmatch(r"[0-9]+", raw) is None or not 0 < int(raw) < 2**63:
        raise ValueError("Invalid identity")
    return int(raw)


def _parse(argv):
    parser = _PrivateParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--enable-login", action="store_true")
    parser.add_argument("--account-name")
    parser.add_argument("--actor-id", type=_positive_id)
    parser.add_argument("--expected-user-id", type=_positive_id)
    args = parser.parse_args(argv)
    if args.enable_login and (
        args.account_name is None
        or not 1 <= len(args.account_name.strip()) <= 100
        or any(unicodedata.category(char) in {"Cc", "Cf"} for char in args.account_name)
        or args.actor_id is None
    ):
        raise ValueError("Required login arguments are missing")
    return args


def _configured_service():
    # Import/configuration happens only after parsing, opt-in and TTY checks.
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy.engine import make_url

    from newsflow.migrate import runtime_migration_config
    from newsflow.persistence.database import configured_session_factory
    from newsflow.providers.telegram_login import TelethonLoginAdapter
    from newsflow.security.master_key import load_runtime_master_key
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_login import SessionProvisioningService
    from newsflow.services.telegram_provider_factory import load_telegram_credentials

    url = make_url(os.getenv("DATABASE_URL", "").strip())
    if (
        url.drivername != "postgresql+psycopg"
        or not url.database
        or not url.database.strip()
        or not url.username
        or not url.username.strip()
    ):
        raise ValueError("Explicit PostgreSQL database and role required")
    credentials_path = os.getenv("NEWSFLOW_TELEGRAM_CREDENTIALS_FILE", "").strip()
    if not credentials_path:
        raise ValueError("Existing credential file required")
    api_id, api_hash = load_telegram_credentials(Path(credentials_path))
    SessionCipher(load_runtime_master_key())
    expected_heads = set(ScriptDirectory.from_config(runtime_migration_config()).get_heads())
    factory = configured_session_factory()
    if factory is None or len(expected_heads) != 1:
        raise ValueError("Migrated database required")
    # Read-only inspection: never upgrade, stamp or check/mutate the schema.
    # The configured factory owns its cached engine; only this session is ours.
    with factory() as session:
        actual_heads = set(MigrationContext.configure(session.connection()).get_current_heads())
    if actual_heads != expected_heads:
        raise ValueError("Database migration heads differ")
    return SessionProvisioningService(
        factory,
        master_key_loader=load_runtime_master_key,
        login_adapter=TelethonLoginAdapter(api_id, api_hash),
    )


def _masked(prompt):
    # getpass warns immediately before falling back to echoed stdin. Converting
    # that warning into an exception stops the fallback before it reads secrets.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt, stream=sys.stderr)


def main(argv=None):
    """Return a fixed public status; never print private exception details."""
    try:
        try:
            args = _parse(argv)
        except SystemExit as result:
            return result.code  # argparse's static help only.
        if not args.enable_login:
            print("LOGIN_DISABLED")
            return 2
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise ValueError("Interactive terminal required")
        service = _configured_service()
        request = service.preflight(args.account_name, args.actor_id, args.expected_user_id)
        phone = _masked("Phone: ")
        account_id = asyncio.run(
            service.provision(
                request,
                phone=phone,
                read_code=lambda: _masked("Code: "),
                read_password=lambda: _masked("2FA password: "),
            )
        )
        print(f"LOGIN_SAVED account_id={account_id}")
        return 0
    except (EOFError, KeyboardInterrupt, asyncio.CancelledError):
        print("LOGIN_CANCELLED")
        return 1
    except Exception:  # noqa: BLE001 -- Config, SQL, SDK and input errors stay private.
        print("LOGIN_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
