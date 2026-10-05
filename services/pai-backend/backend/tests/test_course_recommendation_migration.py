from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = Path("alembic/versions/20261005_51_course_recommendation_executions.py")


def _load_migration():
    spec = importlib.util.spec_from_file_location("course_recommendation_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_upgrade_schema_unique_scope_and_downgrade() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        inspector = sa.inspect(connection)
        columns = {
            column["name"]: column
            for column in inspector.get_columns("course_recommendation_executions")
        }
        assert {"request_snapshot", "result_snapshot", "governance_snapshot"} <= set(columns)
        assert all(
            isinstance(columns[name]["type"], sa.JSON)
            for name in ("request_snapshot", "result_snapshot", "governance_snapshot")
        )
        constraints = inspector.get_unique_constraints("course_recommendation_executions")
        assert any(
            constraint["name"] == "uq_course_recommendation_execution_scope_key"
            and constraint["column_names"] == ["organization_ref", "actor_ref", "request_key"]
            for constraint in constraints
        )
        indexes = {
            item["name"] for item in inspector.get_indexes("course_recommendation_executions")
        }
        assert "ix_course_recommendation_executions_target_ref" in indexes
        assert "ix_course_recommendation_executions_created_at" in indexes
        with Operations.context(context):
            migration.downgrade()
        assert "course_recommendation_executions" not in sa.inspect(connection).get_table_names()
    engine.dispose()
