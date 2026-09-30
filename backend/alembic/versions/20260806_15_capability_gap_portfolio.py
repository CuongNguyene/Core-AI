"""capability gap portfolio persistence

Revision ID: 20260806_15
Revises: 20260804_14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_15"
down_revision: str | None = "20260804_14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capability_gap_portfolios",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("cv_profile_id", sa.String(length=128), nullable=False),
        sa.Column("cv_profile_version", sa.Integer(), nullable=False),
        sa.Column("current_target_id", sa.String(length=128), nullable=False),
        sa.Column("current_target_version", sa.String(length=64), nullable=False),
        sa.Column("current_usage_mode", sa.String(length=16), nullable=False),
        sa.Column("future_target_id", sa.String(length=128)),
        sa.Column("future_target_version", sa.String(length=64)),
        sa.Column("future_usage_mode", sa.String(length=16)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_capability_gap_portfolios_cv_profile_id", "capability_gap_portfolios", ["cv_profile_id"]
    )
    op.create_table(
        "capability_gap_assessments",
        sa.Column("record_id", sa.String(length=256), nullable=False),
        sa.Column("portfolio_id", sa.String(length=128), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("requirement_id", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["capability_gap_portfolios.id"]),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint(
            "portfolio_id", "target_type", "requirement_id", name="uq_capability_gap_assessment"
        ),
    )
    op.create_index(
        "ix_capability_gap_assessments_portfolio_id", "capability_gap_assessments", ["portfolio_id"]
    )
    op.create_table(
        "capability_target_gaps",
        sa.Column("id", sa.String(length=256), nullable=False),
        sa.Column("portfolio_id", sa.String(length=128), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("requirement_id", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["capability_gap_portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id", "target_type", "requirement_id", name="uq_capability_target_gap"
        ),
    )
    op.create_index(
        "ix_capability_target_gaps_portfolio_id", "capability_target_gaps", ["portfolio_id"]
    )
    op.create_table(
        "capability_gap_overlap_links",
        sa.Column("record_id", sa.String(length=256), nullable=False),
        sa.Column("portfolio_id", sa.String(length=128), nullable=False),
        sa.Column("source_gap_id", sa.String(length=256), nullable=False),
        sa.Column("target_gap_id", sa.String(length=256), nullable=False),
        sa.Column("shared_theme", sa.String(length=256), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["capability_gap_portfolios.id"]),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint(
            "portfolio_id", "source_gap_id", "target_gap_id", name="uq_capability_gap_overlap_link"
        ),
    )
    op.create_index(
        "ix_capability_gap_overlap_links_portfolio_id",
        "capability_gap_overlap_links",
        ["portfolio_id"],
    )
    op.create_table(
        "capability_gap_audit_events",
        sa.Column("id", sa.String(length=256), nullable=False),
        sa.Column("portfolio_id", sa.String(length=128)),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["portfolio_id"], ["capability_gap_portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("capability_gap_audit_events")
    op.drop_index(
        "ix_capability_gap_overlap_links_portfolio_id", table_name="capability_gap_overlap_links"
    )
    op.drop_table("capability_gap_overlap_links")
    op.drop_index("ix_capability_target_gaps_portfolio_id", table_name="capability_target_gaps")
    op.drop_table("capability_target_gaps")
    op.drop_index(
        "ix_capability_gap_assessments_portfolio_id", table_name="capability_gap_assessments"
    )
    op.drop_table("capability_gap_assessments")
    op.drop_index(
        "ix_capability_gap_portfolios_cv_profile_id", table_name="capability_gap_portfolios"
    )
    op.drop_table("capability_gap_portfolios")
