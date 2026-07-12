"""versioned report artifacts

Revision ID: 6f1d1aa941f2
Revises: a6aea4f4210b
Create Date: 2026-07-13 01:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f1d1aa941f2"
down_revision: Union[str, None] = "a6aea4f4210b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column(
            "template_version",
            sa.String(length=80),
            nullable=False,
            server_default="buili.issue-pack.v1",
        ),
    )
    op.add_column(
        "reports",
        sa.Column("source_index_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "reports", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "report_artifacts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("report_id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "format", name="uq_report_artifact_format"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_report_artifacts_organization_id"),
        "report_artifacts",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_artifacts_project_id"),
        "report_artifacts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_artifacts_report_id"),
        "report_artifacts",
        ["report_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_report_artifacts_report_id"), table_name="report_artifacts")
    op.drop_index(op.f("ix_report_artifacts_project_id"), table_name="report_artifacts")
    op.drop_index(
        op.f("ix_report_artifacts_organization_id"), table_name="report_artifacts"
    )
    op.drop_table("report_artifacts")
    op.drop_column("reports", "approved_at")
    op.drop_column("reports", "source_index_json")
    op.drop_column("reports", "template_version")
