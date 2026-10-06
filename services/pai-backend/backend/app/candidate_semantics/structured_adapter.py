"""Pure projection of the exact current structured source snapshot to raw evidence."""

import json
from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import BaseModel, ValidationError

from app.candidate_semantics.contracts import (
    CandidateSemanticEvidenceInput,
    CandidateSemanticEvidenceKind,
)
from app.candidate_source.domain import CandidateSourceError
from app.candidate_source.repository import CurrentCandidateSourceSnapshot
from app.candidate_source.schemas import (
    CandidateSourceEnvelope,
    CandidateSourceProjectionV1,
    EmployeeLearningProjectionV1,
)

RecordCollection = tuple[str, Sequence[BaseModel], CandidateSemanticEvidenceKind, tuple[str, ...]]


def adapt_candidate_source_snapshot(
    snapshot: CurrentCandidateSourceSnapshot,
) -> tuple[CandidateSemanticEvidenceInput, ...]:
    """Validate exact schema identity and emit only explicitly eligible raw fields."""
    payload, transport_schema_version = _unwrap_transport(snapshot.payload)
    if (
        payload.get("schema_id") != snapshot.schema_id
        or payload.get("schema_version") != snapshot.schema_version
    ):
        raise CandidateSourceError("candidate_source_schema_identity_mismatch")

    if (
        snapshot.schema_id == "pai.employee-learning-projection"
        and snapshot.schema_version == "1.0"
    ):
        try:
            projection = EmployeeLearningProjectionV1.model_validate_json(json.dumps(payload))
        except ValidationError as exc:
            raise CandidateSourceError("candidate_source_payload_invalid") from exc
        if (
            projection.identity.source_system != snapshot.source_system
            or projection.identity.employee_ref != snapshot.employee_ref
            or projection.snapshot.source_revision != snapshot.source_revision
        ):
            raise CandidateSourceError("candidate_source_snapshot_identity_mismatch")
        candidate_source = projection.candidate_source
        collections: tuple[RecordCollection, ...] = (
            (
                "candidate_source.career_history",
                candidate_source.career_history,
                CandidateSemanticEvidenceKind.EMPLOYMENT,
                ("responsibilities",),
            ),
            (
                "candidate_source.education",
                candidate_source.education,
                CandidateSemanticEvidenceKind.EDUCATION,
                ("institution", "degree", "field"),
            ),
            (
                "candidate_source.certifications",
                candidate_source.certifications,
                CandidateSemanticEvidenceKind.CREDENTIAL,
                ("name", "issuer"),
            ),
            (
                "candidate_source.projects",
                candidate_source.projects,
                CandidateSemanticEvidenceKind.PROJECT,
                ("name", "description", "source_value"),
            ),
        )
    elif snapshot.schema_id == "pai.candidate-source" and snapshot.schema_version == "v1":
        try:
            try:
                source = CandidateSourceEnvelope.model_validate_json(json.dumps(payload))
            except ValidationError:
                legacy_projection = CandidateSourceProjectionV1.model_validate_json(
                    json.dumps(payload)
                )
                source = legacy_projection.to_candidate_source_envelope()
        except ValidationError as exc:
            raise CandidateSourceError("candidate_source_payload_invalid") from exc
        if (
            source.identity.source_system != snapshot.source_system
            or source.identity.employee_ref != snapshot.employee_ref
            or source.source_revision != snapshot.source_revision
        ):
            raise CandidateSourceError("candidate_source_snapshot_identity_mismatch")
        collections = (
            (
                "career_history",
                source.career_history,
                CandidateSemanticEvidenceKind.EMPLOYMENT,
                ("responsibilities",),
            ),
            (
                "education",
                source.education,
                CandidateSemanticEvidenceKind.EDUCATION,
                ("institution", "degree", "field"),
            ),
            (
                "certifications",
                source.certifications,
                CandidateSemanticEvidenceKind.CREDENTIAL,
                ("name", "issuer"),
            ),
            (
                "projects",
                source.projects,
                CandidateSemanticEvidenceKind.PROJECT,
                ("name", "description", "source_value"),
            ),
        )
    else:
        raise CandidateSourceError("candidate_source_schema_unsupported")

    evidence: list[CandidateSemanticEvidenceInput] = []
    for collection_path, records, source_kind, fields in collections:
        for index, record in enumerate(records):
            record_values = cast(dict[str, object], record.model_dump(mode="python"))
            source_record_ref = record_values.get("source_record_ref")
            if not isinstance(source_record_ref, str):
                source_record_ref = None
            for field in fields:
                value = record_values.get(field)
                if not isinstance(value, str) or not value.strip():
                    continue
                evidence.append(
                    CandidateSemanticEvidenceInput(
                        candidate_ref=str(snapshot.candidate_id),
                        source_system=snapshot.source_system,
                        source_revision=snapshot.source_revision,
                        snapshot_ref=str(snapshot.snapshot_id),
                        content_fingerprint=snapshot.content_fingerprint,
                        transport_schema_version=transport_schema_version,
                        source_kind=source_kind,
                        source_record_ref=source_record_ref,
                        field_path=f"{collection_path}[{index}].{field}",
                        content=value,
                    )
                )
    return tuple(evidence)


def _unwrap_transport(payload: dict[str, object]) -> tuple[dict[str, object], str | None]:
    data = payload.get("data")
    if data is None:
        return payload, None
    transport_version = payload.get("schema_version")
    if transport_version != "v1" or not isinstance(data, Mapping):
        raise CandidateSourceError("candidate_source_transport_schema_unsupported")
    if set(payload) != {"schema_version", "data"}:
        raise CandidateSourceError("candidate_source_transport_payload_invalid")
    return dict(data), "v1"
