import base64
import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.bootstrap_dev_actor import (
    BOOTSTRAP_ACTOR_ID,
    BOOTSTRAP_ORGANIZATION_ID,
    BootstrapError,
    bootstrap,
)


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _env(path: Path, *, public_keys: str = "{}", api_key: str = "existing-key") -> None:
    path.write_text(
        "\n".join(
            [
                f"PAI_INTEGRATION_API_KEY={api_key}",
                f"ACTOR_CONTEXT_PUBLIC_KEYS_JSON={public_keys}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_first_bootstrap_creates_key_registers_public_key_and_sanitizes_output(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    secret_dir = tmp_path / "secrets"
    _env(env_file)

    result = bootstrap(env_file=env_file, secret_dir=secret_dir)

    assert result.organization_id == str(BOOTSTRAP_ORGANIZATION_ID)
    assert result.actor_id == str(BOOTSTRAP_ACTOR_ID)
    assert result.key_id == "lms-key-2026-01"
    assert result.generated_private_key is True
    assert result.public_key_registered is True
    assert "existing-key" not in result.sanitized_summary
    assert len(_decode(secret_dir.joinpath("actor_ed25519.key").read_text())) == 32
    assert os.stat(secret_dir / "actor_ed25519.key").st_mode & 0o777 == 0o600

    values = dict(
        line.split("=", 1)
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    public_keys = json.loads(values["ACTOR_CONTEXT_PUBLIC_KEYS_JSON"])
    public_raw = _decode(public_keys[result.key_id])
    assert len(public_raw) == 32
    private = Ed25519PrivateKey.from_private_bytes(
        _decode((secret_dir / "actor_ed25519.key").read_text(encoding="utf-8"))
    )
    assert private.public_key().public_bytes_raw() == public_raw
    signature = private.sign(b"bootstrap-test")
    private.public_key().verify(signature, b"bootstrap-test")


def test_second_bootstrap_reuses_key_without_rotation_or_duplicates(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    secret_dir = tmp_path / "secrets"
    _env(env_file)

    first = bootstrap(env_file=env_file, secret_dir=secret_dir)
    private_before = (secret_dir / "actor_ed25519.key").read_text(encoding="utf-8")
    env_before = env_file.read_text(encoding="utf-8")
    second = bootstrap(env_file=env_file, secret_dir=secret_dir)

    assert second.generated_private_key is False
    assert second.public_key_registered is False
    assert second.key_id == first.key_id
    assert (secret_dir / "actor_ed25519.key").read_text(encoding="utf-8") == private_before
    assert env_file.read_text(encoding="utf-8") == env_before


def test_mismatched_registered_public_key_fails_closed(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    secret_dir = tmp_path / "secrets"
    _env(env_file)
    bootstrap(env_file=env_file, secret_dir=secret_dir)
    _env(env_file, public_keys=json.dumps({"lms-key-2026-01": base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")}))

    with pytest.raises(BootstrapError, match="does not match"):
        bootstrap(env_file=env_file, secret_dir=secret_dir)


def test_existing_public_key_without_private_key_fails_without_rotation(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    secret_dir = tmp_path / "secrets"
    public_key = base64.urlsafe_b64encode(b"p" * 32).decode().rstrip("=")
    _env(env_file, public_keys=json.dumps({"lms-key-2026-01": public_key}))

    with pytest.raises(BootstrapError, match="private key is missing"):
        bootstrap(env_file=env_file, secret_dir=secret_dir)
