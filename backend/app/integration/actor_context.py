import base64
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Request

from app.authorization.repository import SubjectRepository
from app.authorization.schemas import ActorContext
from app.authorization.service import DevelopmentIdentityAdapter
from app.integration.nonce_store import (
    ActorContextNonceStoreUnavailable,
    InMemoryActorContextNonceStore,
    SqlAlchemyActorContextNonceStore,
)
from app.shared.config import Settings
from app.shared.database import Database
from app.shared.errors import APIError

CONTEXT_HEADER = "X-PAI-Actor-Context"
KEY_ID_HEADER = "X-PAI-Actor-Context-Key-Id"
SIGNATURE_HEADER = "X-PAI-Actor-Context-Signature"


class SigningKey(Protocol):
    def sign(self, data: bytes) -> bytes: ...


class ActorContextNonceStore(Protocol):
    async def consume(self, nonce: str, expires_at: datetime) -> bool: ...


@dataclass(frozen=True)
class VerifiedActorContext:
    actor: ActorContext
    nonce: str
    expires_at: datetime


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _canonical(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def actor_context_headers(
    *,
    private_key: SigningKey,
    key_id: str,
    actor_id: UUID,
    organization_id: UUID,
    issued_at: datetime,
    expires_at: datetime,
    nonce: str,
) -> dict[str, str]:
    payload = {
        "actor_reference": str(actor_id),
        "expires_at": expires_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "issued_at": issued_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "issuer": "lms",
        "nonce": nonce,
        "organization_reference": str(organization_id),
        "version": "v1",
    }
    signature = private_key.sign(_canonical(payload))
    return {
        CONTEXT_HEADER: _b64(_canonical(payload)),
        KEY_ID_HEADER: key_id,
        SIGNATURE_HEADER: f"ed25519:{_b64(signature)}",
    }


class SignedActorContextVerifier:
    def __init__(
        self,
        *,
        public_keys: Mapping[str, Ed25519PublicKey],
        actor_resolver: Callable[[UUID, UUID], ActorContext] | None = None,
        now: Callable[[], datetime] | None = None,
        max_lifetime_seconds: int = 60,
    ) -> None:
        self._public_keys = dict(public_keys)
        self._actor_resolver = actor_resolver
        self._now = now or (lambda: datetime.now(UTC))
        self._max_lifetime_seconds = max_lifetime_seconds
        self._seen_nonces: set[str] = set()

    def verify(self, headers: Mapping[str, str]) -> ActorContext:
        verified = self.verify_with_nonce(headers)
        if verified.nonce in self._seen_nonces:
            raise ValueError("ACTOR_CONTEXT_REPLAYED")
        self._seen_nonces.add(verified.nonce)
        return verified.actor

    def verify_with_nonce(self, headers: Mapping[str, str]) -> VerifiedActorContext:
        raw = headers.get(CONTEXT_HEADER)
        key_id = headers.get(KEY_ID_HEADER)
        signature = headers.get(SIGNATURE_HEADER, "")
        if not raw or not key_id or not signature:
            raise ValueError("ACTOR_CONTEXT_MISSING")
        public_key = self._public_keys.get(key_id)
        if public_key is None or not signature.startswith("ed25519:"):
            raise ValueError("ACTOR_CONTEXT_SIGNATURE_INVALID")
        try:
            payload = json.loads(_unb64(raw))
            if not isinstance(payload, dict):
                raise ValueError
            public_key.verify(_unb64(signature.removeprefix("ed25519:")), _canonical(payload))
        except (ValueError, TypeError, json.JSONDecodeError, InvalidSignature) as exc:
            raise ValueError("ACTOR_CONTEXT_INVALID") from exc
        if payload.get("version") != "v1" or payload.get("issuer") != "lms":
            raise ValueError("ACTOR_CONTEXT_INVALID")
        try:
            issued_at = _parse_time(payload["issued_at"])
            expires_at = _parse_time(payload["expires_at"])
            actor_id = UUID(str(payload["actor_reference"]))
            organization_id = UUID(str(payload["organization_reference"]))
            nonce = str(payload["nonce"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("ACTOR_CONTEXT_INVALID") from exc
        now = self._now().astimezone(UTC)
        if (
            expires_at <= now
            or issued_at > now
            or expires_at - issued_at > timedelta(seconds=self._max_lifetime_seconds)
        ):
            raise ValueError("ACTOR_CONTEXT_EXPIRED")
        if self._actor_resolver is not None:
            actor = self._actor_resolver(actor_id, organization_id)
            if actor.organization_id != organization_id:
                raise ValueError("ORGANIZATION_NOT_ALLOWED")
            return VerifiedActorContext(
                actor=actor.model_copy(update={"authentication_method": "signed_actor_context"}),
                nonce=nonce,
                expires_at=expires_at,
            )
        return VerifiedActorContext(
            actor=ActorContext(
                actor_id=actor_id,
                organization_id=organization_id,
                roles=frozenset(),
                authentication_method="signed_actor_context",
            ),
            nonce=nonce,
            expires_at=expires_at,
        )


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("invalid timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _public_keys(settings: Settings) -> dict[str, Ed25519PublicKey]:
    try:
        configured = json.loads(settings.actor_context_public_keys_json)
        return {
            key_id: Ed25519PublicKey.from_public_bytes(_unb64(value))
            for key_id, value in configured.items()
        }
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise APIError(
            503, "actor_context_unavailable", "Actor context verification is unavailable."
        ) from exc


async def get_signed_actor_context(request: Request) -> ActorContext:
    verifier = getattr(request.app.state, "actor_context_verifier", None)
    if verifier is None:
        settings = cast(Settings, request.app.state.settings)
        verifier = SignedActorContextVerifier(public_keys=_public_keys(settings))
        request.app.state.actor_context_verifier = verifier
    try:
        verified = verifier.verify_with_nonce(request.headers)
        nonce_store = _nonce_store(request)
        if not await nonce_store.consume(verified.nonce, verified.expires_at):
            raise ValueError("ACTOR_CONTEXT_REPLAYED")
        actor = verified.actor
        if actor.roles:
            return actor
        identity = DevelopmentIdentityAdapter(
            cast(SubjectRepository, request.app.state.subject_repository)
        )
        resolved = await identity.resolve(actor.actor_id)
        if resolved.organization_id != actor.organization_id:
            raise ValueError("ORGANIZATION_NOT_ALLOWED")
        return resolved.model_copy(update={"authentication_method": "signed_actor_context"})
    except ValueError as exc:
        code = str(exc)
        statuses = {
            "ACTOR_CONTEXT_MISSING": 401,
            "ACTOR_CONTEXT_EXPIRED": 401,
            "ACTOR_CONTEXT_REPLAYED": 401,
            "ACTOR_CONTEXT_SIGNATURE_INVALID": 401,
            "ACTOR_CONTEXT_INVALID": 401,
            "ACTOR_NOT_FOUND": 401,
            "ORGANIZATION_NOT_ALLOWED": 403,
        }
        raise APIError(statuses.get(code, 401), code, "Actor context is not authorized.") from exc
    except PermissionError as exc:
        code = str(exc)
        mapped = "ACTOR_NOT_FOUND" if code == "identity_unknown" else "ORGANIZATION_NOT_ALLOWED"
        raise APIError(
            401 if mapped == "ACTOR_NOT_FOUND" else 403, mapped, "Actor context is not authorized."
        ) from exc
    except ActorContextNonceStoreUnavailable as exc:
        raise APIError(
            503,
            "actor_context_unavailable",
            "Actor context verification is unavailable.",
        ) from exc


def _nonce_store(request: Request) -> ActorContextNonceStore:
    store = getattr(request.app.state, "actor_context_nonce_store", None)
    if store is not None:
        return cast(ActorContextNonceStore, store)
    database = getattr(request.app.state, "database", None)
    if isinstance(database, Database):
        store = SqlAlchemyActorContextNonceStore(database.session_factory)
    else:
        # FastAPI unit fixtures intentionally do not instantiate a database.
        store = InMemoryActorContextNonceStore()
    request.app.state.actor_context_nonce_store = store
    return cast(ActorContextNonceStore, store)
