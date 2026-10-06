"""Explicit local smoke: retains uniquely named synthetic source rows for audit.

Run from backend with PYTHONPATH=. uv run python test/results/candidate-input-01c-3/runtime_smoke.py.
Uses existing local integration credentials; never prints them or source bodies.
"""

import argparse
import base64
import copy
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.authorization.fixtures import ADMIN_ID, ORG_PAI_ID
from app.integration.actor_context import actor_context_headers
from app.shared.config import Settings

READ_SNAPSHOTS = """
import asyncio, json, sys
from uuid import UUID
from sqlalchemy import select, text
from app.shared.config import Settings
from app.shared.database import Database
from app.candidate_source.models import CandidateSourceSnapshotRecord, CandidateExternalEmployeeIdentityRecord
async def main():
    candidate_id = UUID(sys.stdin.read().strip())
    database = Database(Settings().database_url)
    async with database.session() as session:
        revision = await session.scalar(text('select version_num from alembic_version'))
        identity = await session.scalar(select(CandidateExternalEmployeeIdentityRecord).where(
            CandidateExternalEmployeeIdentityRecord.candidate_id == candidate_id))
        rows = (await session.scalars(select(CandidateSourceSnapshotRecord).where(
            CandidateSourceSnapshotRecord.candidate_id == candidate_id).order_by(
            CandidateSourceSnapshotRecord.source_revision))).all()
        print(json.dumps({'db_revision': revision, 'current_snapshot_id': str(identity.current_snapshot_id),
            'snapshots': [{'id': str(row.id), 'revision': row.source_revision, 'payload': row.payload,
            'content_fingerprint': row.content_fingerprint} for row in rows]}, ensure_ascii=False))
    await database.dispose()
asyncio.run(main())
"""

SEED_MAPPING = """
import asyncio, sys
from app.authorization.fixtures import ORG_PAI_ID
from app.candidate_source.repository import SqlAlchemyCandidateSourceRepository
from app.shared.config import Settings
from app.shared.database import Database
async def main():
    database = Database(Settings().database_url)
    mapping_id = await SqlAlchemyCandidateSourceRepository(database.session_factory).add_organization_mapping(
        organization_id=ORG_PAI_ID, source_system='HRM', external_company_ref=sys.stdin.read().strip())
    print(mapping_id)
    await database.dispose()
asyncio.run(main())
"""


def container_python(code: str, value: str) -> str:
    return subprocess.run(
        ["docker", "exec", "-i", "pai-local-backend-1", "uv", "run", "python", "-c", code],
        input=value,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def main(existing_marker: str | None = None) -> None:
    settings = Settings()
    encoded = Path("../.local-secrets/frappe-lms-local/actor_ed25519.key").read_text().strip()
    key = Ed25519PrivateKey.from_private_bytes(
        base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    )
    data = json.loads(Path("tests/fixtures/employee_learning_projection_v1.json").read_text())
    marker = existing_marker or uuid4().hex
    data["identity"]["employee_ref"] = f"01C3-SMOKE-{marker}"
    data["employment_context"]["company"] = f"PAI-01C3-SMOKE-{marker}"
    data["snapshot"]["source_revision"] = 1

    def headers() -> dict[str, str]:
        now = datetime.now(UTC)
        return {
            "Authorization": f"Bearer {settings.integration_api_key.get_secret_value()}",
            **actor_context_headers(
                private_key=key,
                key_id="lms-key-2026-01",
                actor_id=ADMIN_ID,
                organization_id=ORG_PAI_ID,
                issued_at=now,
                expires_at=now + timedelta(seconds=30),
                nonce=str(uuid4()),
            ),
        }

    route = "/api/v1/candidate-sources/learning-projections"
    with httpx.Client(base_url="http://localhost:18000", timeout=30) as client:
        ready = client.get("/health/ready")
        assert ready.status_code == 200, ready.status_code
        openapi = client.get("/openapi.json").json()
        assert route in openapi["paths"]
        assert "/api/v1/candidate-sources/snapshots" in openapi["paths"]
        assert (
            "source_revision"
            in openapi["components"]["schemas"]["LearningProjectionSnapshot"]["required"]
        )
        if existing_marker:
            original = copy.deepcopy(data)
            data["snapshot"]["source_revision"] = 2
            replay = client.post(
                route, headers=headers(), json={"schema_version": "v1", "data": data}
            )
            assert replay.status_code == 200 and replay.json()["data"]["disposition"] == "REPLAY"
            stored = json.loads(
                container_python(READ_SNAPSHOTS, replay.json()["data"]["candidate_id"])
            )
            assert stored["db_revision"] == "20261006_53"
            assert [row["payload"] for row in stored["snapshots"]] == [original, data]
            assert stored["current_snapshot_id"] == replay.json()["data"]["snapshot_id"]
            print(
                json.dumps(
                    {
                        "final_image_reverification": "PASS",
                        "replay_http": 200,
                        "full_projection_roundtrip": True,
                        "snapshot_count": 2,
                        "new_source_rows_created": False,
                    }
                )
            )
            return
        mapping = client.post(
            "/api/v1/candidate-sources/organization-mappings",
            headers=headers(),
            json={
                "schema_version": "v1",
                "data": {
                    "source_system": "HRM",
                    "external_company_ref": data["employment_context"]["company"],
                    "organization_id": str(ORG_PAI_ID),
                },
            },
        )
        # The pre-existing strict mapping DTO rejects JSON UUID strings (422).
        # Seed only this uniquely named synthetic mapping through the same repository;
        # the new ingress below still uses real integration auth and signed actors.
        assert mapping.status_code == 422, mapping.status_code
        mapping_id = container_python(SEED_MAPPING, data["employment_context"]["company"])

        def post(value):
            return client.post(
                route, headers=headers(), json={"schema_version": "v1", "data": value}
            )

        accepted = post(data)
        assert accepted.status_code == 201, (accepted.status_code, accepted.json().get("error"))
        replay = post(data)
        assert replay.status_code == 200 and replay.json()["data"]["disposition"] == "REPLAY"
        newer = copy.deepcopy(data)
        newer["snapshot"]["source_revision"] = 2
        promoted = post(newer)
        assert promoted.status_code == 201 and promoted.json()["data"]["disposition"] == "NEWER"
        stale = post(data)
        assert (
            stale.status_code == 409
            and stale.json()["error"]["code"] == "candidate_source_snapshot_stale"
        )
        changed = copy.deepcopy(newer)
        changed["auxiliary_signals"]["ats_ai_profile"]["summary"] = "Different source text"
        conflict = post(changed)
        assert (
            conflict.status_code == 409
            and conflict.json()["error"]["code"] == "candidate_source_snapshot_revision_conflict"
        )
    candidate_id = accepted.json()["data"]["candidate_id"]
    stored = json.loads(container_python(READ_SNAPSHOTS, candidate_id))
    assert stored["db_revision"] == "20261006_53"
    assert [row["payload"] for row in stored["snapshots"]] == [data, newer]
    assert stored["current_snapshot_id"] == promoted.json()["data"]["snapshot_id"]
    assert (
        stored["snapshots"][0]["content_fingerprint"]
        == stored["snapshots"][1]["content_fingerprint"]
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "db_revision": stored["db_revision"],
                "ready_http": 200,
                "flow_http": [
                    accepted.status_code,
                    replay.status_code,
                    promoted.status_code,
                    stale.status_code,
                    conflict.status_code,
                ],
                "full_projection_roundtrip": True,
                "snapshot_count": len(stored["snapshots"]),
                "current_revision": 2,
                "candidate_id": candidate_id,
                "mapping_id": mapping_id,
                "mapping_setup": "existing server repository; pre-existing mapping API returns 422 for JSON UUID",
                "employee_ref": data["identity"]["employee_ref"],
                "synthetic_rows_retained": True,
                "secrets_printed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--existing-marker",
        help="Verify previously retained smoke snapshots without creating new source rows",
    )
    main(parser.parse_args().existing_marker)
