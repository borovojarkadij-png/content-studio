from datetime import UTC, datetime

import pytest


def test_disabled_worker_has_no_database_secret_or_provider_activity():
    from newsflow.worker import run_rewrite_tick

    def forbidden():
        raise AssertionError("Disabled network worker touched database")

    assert (
        run_rewrite_tick(forbidden, enabled=False, cipher=None, now=datetime.now(UTC)) == "DISABLED"
    )


@pytest.mark.parametrize("value", ["yes", "true", "", "2"])
def test_network_enable_policy_rejects_ambiguous_values(value):
    from newsflow.worker import rewrite_enabled

    with pytest.raises(ValueError):
        rewrite_enabled(value)


def test_enabled_worker_requires_stable_cipher_before_claim():
    from newsflow.worker import run_rewrite_tick

    with pytest.raises(ValueError, match="cipher"):
        run_rewrite_tick(lambda: None, enabled=True, cipher=None, now=datetime.now(UTC))
