import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/20261006_52_candidate_source_foundations.py"
)
REVISION_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/20261006_53_candidate_source_revision_ordering.py"
)


def _load_migration(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_source_migration_creates_explicit_scoped_tables_and_downgrades() -> None:
    spec = importlib.util.spec_from_file_location("candidate_source_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text("CREATE TABLE authorization_organizations (id CHAR(32) PRIMARY KEY)")
        )
        connection.execute(sa.text("CREATE TABLE candidates (id CHAR(32) PRIMARY KEY)"))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        inspector = sa.inspect(connection)
        assert {
            "organization_external_mappings",
            "candidate_external_employee_identities",
            "candidate_source_snapshots",
            "candidate_structured_evidence",
        } <= set(inspector.get_table_names())
        constraints = inspector.get_unique_constraints("candidate_external_employee_identities")
        assert any(
            constraint["name"] == "uq_candidate_external_employee_identity"
            and constraint["column_names"] == ["organization_id", "source_system", "employee_ref"]
            for constraint in constraints
        )
        mapping_constraints = inspector.get_unique_constraints("organization_external_mappings")
        assert any(
            constraint["column_names"] == ["source_system", "external_company_ref"]
            for constraint in mapping_constraints
        )
        with Operations.context(context):
            migration.downgrade()
        assert not {
            "organization_external_mappings",
            "candidate_external_employee_identities",
            "candidate_source_snapshots",
            "candidate_structured_evidence",
        } & set(sa.inspect(connection).get_table_names())
    engine.dispose()


def test_source_revision_migration_backfills_identity_and_downgrades_additively() -> None:
    migration = _load_migration(REVISION_MIGRATION_PATH, "candidate_source_revision_migration")
    migration_52 = _load_migration(MIGRATION_PATH, "candidate_source_migration_for_revision")
    engine = sa.create_engine("sqlite://")
    organization_id, candidate_id, identity_id, snapshot_id = (uuid4() for _ in range(4))
    with engine.begin() as connection:
        connection.execute(
            sa.text("CREATE TABLE authorization_organizations (id CHAR(32) PRIMARY KEY)")
        )
        connection.execute(sa.text("CREATE TABLE candidates (id CHAR(32) PRIMARY KEY)"))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration_52.upgrade()
        metadata = sa.MetaData()
        organization = sa.Table("authorization_organizations", metadata, autoload_with=connection)
        candidate = sa.Table("candidates", metadata, autoload_with=connection)
        snapshots = sa.Table("candidate_source_snapshots", metadata, autoload_with=connection)
        identities = sa.Table(
            "candidate_external_employee_identities", metadata, autoload_with=connection
        )
        connection.execute(organization.insert().values(id=organization_id.hex))
        connection.execute(candidate.insert().values(id=candidate_id.hex))
        connection.execute(
            snapshots.insert().values(
                id=snapshot_id.hex,
                candidate_id=candidate_id.hex,
                organization_id=organization_id.hex,
                source_system="HRM",
                employee_ref="EMP-1",
                schema_id="pai.candidate-source",
                schema_version="v1",
                fingerprint="a" * 64,
                ordering_state="CURRENT",
                payload={},
                ingested_at=datetime.now(UTC),
            )
        )
        connection.execute(
            identities.insert().values(
                id=identity_id.hex,
                candidate_id=candidate_id.hex,
                organization_id=organization_id.hex,
                source_system="HRM",
                employee_ref="EMP-1",
                current_snapshot_id=snapshot_id.hex,
            )
        )
        with Operations.context(context):
            migration.upgrade()
        migrated = sa.Table("candidate_source_snapshots", sa.MetaData(), autoload_with=connection)
        row = connection.execute(
            sa.select(
                migrated.c.external_identity_id,
                migrated.c.source_revision,
                migrated.c.content_fingerprint,
            )
        ).one()
        assert UUID(hex=row.external_identity_id) == identity_id
        assert row.source_revision is None
        assert row.content_fingerprint is None
        assert migrated.c.external_identity_id.nullable is False
        constraints = sa.inspect(connection).get_unique_constraints("candidate_source_snapshots")
        assert any(
            item["name"] == "uq_candidate_source_snapshot_identity_revision"
            and item["column_names"] == ["external_identity_id", "source_revision"]
            for item in constraints
        )
        with Operations.context(context):
            migration.downgrade()
        remaining = {
            column["name"]
            for column in sa.inspect(connection).get_columns("candidate_source_snapshots")
        }
        assert not {"external_identity_id", "source_revision", "content_fingerprint"} & remaining
        assert "candidate_structured_evidence" in sa.inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.parametrize("identity_count", [0, 2])
def test_revision_migration_rejects_snapshot_without_exactly_one_identity(
    identity_count: int,
) -> None:
    migration = _load_migration(
        REVISION_MIGRATION_PATH, "candidate_source_revision_match_validation"
    )
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        metadata = sa.MetaData()
        snapshots = sa.Table(
            "candidate_source_snapshots",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("candidate_id", sa.String),
            sa.Column("organization_id", sa.String),
            sa.Column("source_system", sa.String),
            sa.Column("employee_ref", sa.String),
        )
        identities = sa.Table(
            "candidate_external_employee_identities",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("candidate_id", sa.String),
            sa.Column("organization_id", sa.String),
            sa.Column("source_system", sa.String),
            sa.Column("employee_ref", sa.String),
        )
        metadata.create_all(connection)
        connection.execute(
            snapshots.insert().values(
                id=1,
                candidate_id="candidate",
                organization_id="org",
                source_system="HRM",
                employee_ref="EMP-1",
            )
        )
        for index in range(identity_count):
            connection.execute(
                identities.insert().values(
                    id=index + 1,
                    candidate_id="candidate",
                    organization_id="org",
                    source_system="HRM",
                    employee_ref="EMP-1",
                )
            )
        with pytest.raises(
            RuntimeError, match=f"matched {identity_count} external employee identities"
        ):
            migration._validate_snapshot_identity_matches(connection)
    engine.dispose()
