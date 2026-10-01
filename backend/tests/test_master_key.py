from pathlib import Path

import pytest

from newsflow.security import master_key


def test_master_key_loader_refuses_to_autogenerate_missing_secret(tmp_path: Path) -> None:
    with pytest.raises(master_key.MasterKeyUnavailable):
        master_key.load_master_key(tmp_path / "missing-key")


def test_master_key_loader_returns_existing_stable_secret(tmp_path: Path) -> None:
    path = tmp_path / "master-key"
    path.write_text("stable-secret\n", encoding="utf-8")

    assert master_key.load_master_key(path) == "stable-secret"
