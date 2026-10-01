"""Bootstrap the local Frappe actor signing key without storing private key in PAI."""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.authorization.fixtures import ADMIN_ID, ORG_PAI_ID

BOOTSTRAP_ORGANIZATION_ID = ORG_PAI_ID
BOOTSTRAP_ACTOR_ID = ADMIN_ID
DEFAULT_KEY_ID = "lms-key-2026-01"
PRIVATE_KEY_FILENAME = "actor_ed25519.key"


class BootstrapError(RuntimeError):
    """A local credential bootstrap invariant failed."""


@dataclass(frozen=True)
class BootstrapResult:
    organization_id: str
    actor_id: str
    key_id: str
    api_key_created: bool
    generated_private_key: bool
    public_key_registered: bool
    private_key_path: Path

    @property
    def sanitized_summary(self) -> str:
        return "\n".join(
            (
                f"Organization UUID: {self.organization_id}",
                f"Actor UUID: {self.actor_id}",
                f"Actor key ID: {self.key_id}",
                f"API key: {'CREATED (MASKED)' if self.api_key_created else 'EXISTING (MASKED)'}",
                f"Private key path: {self.private_key_path}",
                f"Public key registration: {'UPDATED' if self.public_key_registered else 'UNCHANGED'}",
                f"Private key: {'CREATED' if self.generated_private_key else 'REUSED'}",
                "Idempotency: READY",
            )
        )


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _key_bytes(value: str, label: str) -> bytes | None:
    try:
        raw = _decode(value.strip())
    except (ValueError, TypeError):
        return None
    if len(raw) != 32:
        return None
    return raw


def _parse_env(lines: Iterable[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, value = stripped.split("=", 1)
            values[key] = value
    return values


def _set_env_value(lines: list[str], key: str, value: str) -> tuple[list[str], bool]:
    prefix = f"{key}="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            replacement = f"{prefix}{value}"
            if line == replacement:
                return lines, False
            lines[index] = replacement
            return lines, True
    lines.append(f"{prefix}{value}")
    return lines, True


def _write_private_key(path: Path, encoded: str) -> None:
    path.write_text(encoded, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def bootstrap(
    *,
    env_file: Path,
    secret_dir: Path,
    key_id: str = DEFAULT_KEY_ID,
    rotate_actor_key: bool = False,
) -> BootstrapResult:
    if not env_file.is_file():
        raise BootstrapError(f"Environment file does not exist: {env_file}")
    if not key_id or any(char.isspace() for char in key_id):
        raise BootstrapError("Actor key ID must be a non-empty token.")

    original_lines = env_file.read_text(encoding="utf-8").splitlines()
    lines = list(original_lines)
    values = _parse_env(lines)
    raw_registry = values.get("ACTOR_CONTEXT_PUBLIC_KEYS_JSON", "{}")
    try:
        registry = json.loads(raw_registry or "{}")
    except json.JSONDecodeError as exc:
        raise BootstrapError("ACTOR_CONTEXT_PUBLIC_KEYS_JSON is not valid JSON.") from exc
    if not isinstance(registry, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in registry.items()):
        raise BootstrapError("ACTOR_CONTEXT_PUBLIC_KEYS_JSON must map key IDs to strings.")

    private_path = secret_dir / PRIVATE_KEY_FILENAME
    private_raw: bytes | None = None
    generated = False
    if private_path.exists():
        private_raw = _key_bytes(private_path.read_text(encoding="utf-8"), "private key")
        if private_raw is None:
            raise BootstrapError(f"Private key file is invalid: {private_path}")

    registered_raw = _key_bytes(registry.get(key_id, ""), "public key")
    if private_raw is None and registered_raw is not None and not rotate_actor_key:
        raise BootstrapError("Registered public key exists but local private key is missing; refusing to rotate.")
    if private_raw is not None and registered_raw is not None:
        derived = Ed25519PrivateKey.from_private_bytes(private_raw).public_key().public_bytes_raw()
        if derived != registered_raw and not rotate_actor_key:
            raise BootstrapError("Local private key does not match the registered public key; refusing to rotate.")

    if private_raw is None or rotate_actor_key:
        private_raw = Ed25519PrivateKey.generate().private_bytes_raw()
        generated = True
        secret_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            secret_dir.chmod(0o700)
        except OSError:
            pass
        _write_private_key(private_path, _encode(private_raw))

    assert private_raw is not None
    public_encoded = _encode(Ed25519PrivateKey.from_private_bytes(private_raw).public_key().public_bytes_raw())
    registered_encoded = registry.get(key_id)
    if registered_encoded != public_encoded:
        registry[key_id] = public_encoded
        lines, _ = _set_env_value(lines, "ACTOR_CONTEXT_PUBLIC_KEYS_JSON", json.dumps(registry, separators=(",", ":")))
        public_registered = True
    else:
        public_registered = False

    api_key = values.get("PAI_INTEGRATION_API_KEY", "").strip()
    api_key_created = not api_key or api_key.startswith("replace-")
    if api_key_created:
        lines, _ = _set_env_value(lines, "PAI_INTEGRATION_API_KEY", secrets.token_urlsafe(32))

    if lines != original_lines:
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return BootstrapResult(
        organization_id=str(BOOTSTRAP_ORGANIZATION_ID),
        actor_id=str(BOOTSTRAP_ACTOR_ID),
        key_id=key_id,
        api_key_created=api_key_created,
        generated_private_key=generated,
        public_key_registered=public_registered,
        private_key_path=private_path,
    )


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Bootstrap the local Frappe actor signing key.")
    parser.add_argument("--env-file", type=Path, default=repository_root / "backend/.env")
    parser.add_argument(
        "--secret-dir",
        type=Path,
        default=repository_root / ".local-secrets/frappe-lms-local",
    )
    parser.add_argument("--key-id", default=DEFAULT_KEY_ID)
    parser.add_argument("--rotate-actor-key", action="store_true")
    args = parser.parse_args()
    try:
        result = bootstrap(
            env_file=args.env_file,
            secret_dir=args.secret_dir,
            key_id=args.key_id,
            rotate_actor_key=args.rotate_actor_key,
        )
    except BootstrapError as exc:
        parser.error(str(exc))
    print(result.sanitized_summary)


if __name__ == "__main__":
    main()
