"""add candidate profile governance version and repair invalid current pointers

Revision ID: 20260916_43
Revises: 20260916_42
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260916_43"
down_revision: str | Sequence[str] | None = "20260916_42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INVALID_CURRENT_POINTERS = (
    (
        "6777ec73-1042-412d-9723-2aab53340578",
        "6d0152b1-4253-43cb-8f34-b886a6a1721c",
        "pending_review",
    ),
    (
        "737e267a-6276-43f6-8c79-e244027ef926",
        "729236e6-e8a7-4377-b49f-f21a3bed3f32",
        "pending_review",
    ),
    (
        "9ae6fb14-9545-4723-b448-b3047c8d33fe",
        "89a4a4a2-1ee2-43e9-8245-b44632ed6039",
        "pending_review",
    ),
    (
        "9c19ceb5-64ec-4f76-9c1a-6fea1c811fe7",
        "f19201ec-4075-4874-b96f-c55bc0c1792d",
        "pending_review",
    ),
    (
        "a96c4e05-6224-424f-b1cf-8316a7499be0",
        "93234cdb-7501-4ac0-b146-30aec530582f",
        "pending_review",
    ),
    (
        "d1cfb6ed-8465-47c1-bcbf-00ef5bc4246b",
        "9aafe0f0-a5a2-496f-8d2a-30bfb68b0533",
        "pending_review",
    ),
    ("daf67644-9931-4ef6-a136-ddeb977be6c4", "02313b2f-3938-4372-8997-959469692d04", "rejected"),
)


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("governance_version", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE candidate_profiles AS cp
        SET governance_version = cv.version
        FROM candidate_cv_versions AS cv
        WHERE cp.document_id = cv.document_id
        """
    )
    op.execute(
        """
        UPDATE candidate_profiles AS cp
        SET governance_version = 1
        WHERE cp.governance_version IS NULL
          AND (
              SELECT COUNT(*)
              FROM candidate_profiles AS sibling
              WHERE sibling.candidate_id = cp.candidate_id
          ) = 1
        """
    )

    # A legacy candidate can have more than one profile linked to the same CV
    # document. The first backfill maps both profiles to that CV's version,
    # which makes the later unique constraint impossible to create. Preserve
    # every profile and give each candidate a deterministic governance sequence
    # instead of dropping a duplicate profile. Ordering by the mapped CV
    # version keeps the authoritative CV history first; link time and row ID
    # make ties stable.
    op.execute(
        """
        WITH ranked_profiles AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY candidate_id
                       ORDER BY governance_version, linked_at, id
                   ) AS normalized_governance_version
            FROM candidate_profiles
        )
        UPDATE candidate_profiles AS cp
        SET governance_version = ranked_profiles.normalized_governance_version
        FROM ranked_profiles
        WHERE cp.id = ranked_profiles.id
        """
    )

    bind = op.get_bind()
    ambiguous = bind.execute(
        sa.text("SELECT COUNT(*) FROM candidate_profiles WHERE governance_version IS NULL")
    ).scalar_one()
    if ambiguous:
        raise RuntimeError(f"candidate governance backfill is ambiguous for {ambiguous} profile(s)")

    op.alter_column("candidate_profiles", "governance_version", nullable=False)
    op.create_unique_constraint(
        "uq_candidate_profile_governance_version",
        "candidate_profiles",
        ["candidate_id", "governance_version"],
    )

    for candidate_id, profile_id, review_state in _INVALID_CURRENT_POINTERS:
        result = bind.execute(
            sa.text(
                """
                UPDATE candidates AS c
                SET current_profile_id = NULL,
                    current_profile_version = NULL
                WHERE c.id = :candidate_id
                  AND c.current_profile_id = :profile_id
                  AND EXISTS (
                      SELECT 1
                      FROM candidate_profiles AS cp
                      WHERE cp.candidate_id = c.id
                        AND cp.profile_id = c.current_profile_id
                        AND cp.review_state = :review_state
                  )
                """
            ),
            {
                "candidate_id": candidate_id,
                "profile_id": profile_id,
                "review_state": review_state,
            },
        )
        # This remediation list was captured from an earlier data snapshot.
        # Applying the migration to another environment is valid when the
        # already-invalid pointer is absent; update only the exact bad pointer
        # when it still exists. More than one matching row would still signal a
        # corrupt primary-key invariant.
        if result.rowcount > 1:
            raise RuntimeError(
                "candidate current-pointer remediation matched multiple rows: "
                f"{candidate_id}/{profile_id}"
            )


def downgrade() -> None:
    op.drop_constraint(
        "uq_candidate_profile_governance_version",
        "candidate_profiles",
        type_="unique",
    )
    op.drop_column("candidate_profiles", "governance_version")
