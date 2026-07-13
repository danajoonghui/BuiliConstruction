"""fixture asset registry

Revision ID: d7a8f1c52e31
Revises: cf5bed103b0a
Create Date: 2026-07-13 09:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d7a8f1c52e31"
down_revision: Union[str, None] = "cf5bed103b0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fixture_assets",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("semantic_type", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_task_id", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("glb_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("preview_url", sa.String(length=2048), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("face_count", sa.Integer(), nullable=True),
        sa.Column("bounds_json", sa.JSON(), nullable=False),
        sa.Column("transform_json", sa.JSON(), nullable=False),
        sa.Column("provider_json", sa.JSON(), nullable=False),
        sa.Column("review_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=40), nullable=False),
        sa.Column("approved_by", sa.String(length=40), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "semantic_type", "version", name="uq_fixture_asset_version"
        ),
    )
    op.create_index(
        op.f("ix_fixture_assets_organization_id"),
        "fixture_assets",
        ["organization_id"],
    )
    op.create_index(op.f("ix_fixture_assets_project_id"), "fixture_assets", ["project_id"])
    op.create_index(
        op.f("ix_fixture_assets_semantic_type"),
        "fixture_assets",
        ["semantic_type"],
    )
    op.create_index(
        "uq_fixture_asset_approved_type",
        "fixture_assets",
        ["project_id", "semantic_type"],
        unique=True,
        postgresql_where=sa.text("status = 'approved'"),
        sqlite_where=sa.text("status = 'approved'"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE fixture_assets ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE fixture_assets FORCE ROW LEVEL SECURITY")
        op.execute(
            """CREATE POLICY fixture_assets_tenant_isolation ON fixture_assets
            USING (
                current_user = 'buili_worker'
                OR EXISTS (
                    SELECT 1 FROM organization_members membership
                    WHERE membership.organization_id = fixture_assets.organization_id
                      AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')
                )
            )
            WITH CHECK (
                current_user = 'buili_worker'
                OR EXISTS (
                    SELECT 1 FROM organization_members membership
                    WHERE membership.organization_id = fixture_assets.organization_id
                      AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')
                )
            )"""
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS fixture_assets_tenant_isolation ON fixture_assets")
        op.execute("ALTER TABLE fixture_assets DISABLE ROW LEVEL SECURITY")
    op.drop_index("uq_fixture_asset_approved_type", table_name="fixture_assets")
    op.drop_index(op.f("ix_fixture_assets_semantic_type"), table_name="fixture_assets")
    op.drop_index(op.f("ix_fixture_assets_project_id"), table_name="fixture_assets")
    op.drop_index(op.f("ix_fixture_assets_organization_id"), table_name="fixture_assets")
    op.drop_table("fixture_assets")
