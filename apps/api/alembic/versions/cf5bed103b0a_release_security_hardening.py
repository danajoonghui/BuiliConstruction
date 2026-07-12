"""release security hardening

Revision ID: cf5bed103b0a
Revises: 6f1d1aa941f2
Create Date: 2026-07-13 02:12:26.758726
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cf5bed103b0a"
down_revision: Union[str, None] = "6f1d1aa941f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIRECT_TENANT_TABLES = [
    "projects", "documents", "issues", "jobs", "search_chunks", "uploads",
    "evidence", "reports", "plan_graphs", "spatial_scenes",
]
INDIRECT_TENANT_TABLES = [
    "document_revisions", "issue_sources", "issue_evidence", "project_members", "audit_logs",
]


def _membership_sql(organization_expression: str) -> str:
    return f"""(
        current_user = 'buili_worker'
        OR EXISTS (
            SELECT 1 FROM organization_members membership
            WHERE membership.organization_id = {organization_expression}
              AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')
        )
    )"""


def _policy(table: str, expression: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        f"USING ({expression}) WITH CHECK ({expression})"
    )


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # The prior migration's FORCE-RLS policies used this transitional GUC.
        # It is scoped to this migration transaction and all replacement
        # policies below intentionally ignore it.
        op.execute("SELECT set_config('app.is_worker', 'true', true)")
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("auth_sessions", sa.Column("family_id", sa.String(length=40), nullable=True))
    op.add_column("auth_sessions", sa.Column("parent_session_id", sa.String(length=40), nullable=True))
    op.add_column("auth_sessions", sa.Column("replaced_by_session_id", sa.String(length=40), nullable=True))
    op.add_column("auth_sessions", sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_sessions", sa.Column("revocation_reason", sa.String(length=64), nullable=True))
    op.execute("UPDATE auth_sessions SET family_id = id WHERE family_id IS NULL")
    with op.batch_alter_table("auth_sessions") as batch:
        batch.alter_column("family_id", existing_type=sa.String(length=40), nullable=False)
        batch.create_foreign_key(
            "fk_auth_sessions_parent_session_id", "auth_sessions", ["parent_session_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_foreign_key(
            "fk_auth_sessions_replaced_by_session_id", "auth_sessions", ["replaced_by_session_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_auth_sessions_family_id", "auth_sessions", ["family_id"])

    op.add_column("uploads", sa.Column("scan_result_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("uploads", sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("issues", sa.Column("verification_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

    # Normalize legacy rows before enforcing one active revision/approved scene.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            WITH ranked AS (
                SELECT id, row_number() OVER (
                    PARTITION BY document_id ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS position
                FROM document_revisions WHERE status IN ('current', 'approved')
            )
            UPDATE document_revisions revision SET status = 'superseded'
            FROM ranked WHERE revision.id = ranked.id AND ranked.position > 1
        """)
        op.execute("""
            WITH ranked AS (
                SELECT id, row_number() OVER (
                    PARTITION BY project_id, source_revision_id ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS position
                FROM spatial_scenes WHERE status = 'approved'
            )
            UPDATE spatial_scenes scene SET status = 'superseded'
            FROM ranked WHERE scene.id = ranked.id AND ranked.position > 1
        """)
        op.execute("""
            WITH ranked AS (
                SELECT id, row_number() OVER (
                    PARTITION BY project_id, source_revision_id ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS position
                FROM plan_graphs WHERE status = 'approved'
            )
            UPDATE plan_graphs graph SET status = 'superseded'
            FROM ranked WHERE graph.id = ranked.id AND ranked.position > 1
        """)

    op.create_index(
        "uq_document_one_active_revision",
        "document_revisions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('current', 'approved')"),
        sqlite_where=sa.text("status IN ('current', 'approved')"),
    )
    with op.batch_alter_table("spatial_scenes") as batch:
        batch.create_unique_constraint(
            "uq_spatial_scene_version", ["project_id", "source_revision_id", "version"]
        )
    op.create_index(
        "uq_spatial_scene_approved_source",
        "spatial_scenes",
        ["project_id", "source_revision_id"],
        unique=True,
        postgresql_where=sa.text("status = 'approved'"),
        sqlite_where=sa.text("status = 'approved'"),
    )
    op.create_index(
        "uq_plan_graph_approved_source",
        "plan_graphs",
        ["project_id", "source_revision_id"],
        unique=True,
        postgresql_where=sa.text("status = 'approved'"),
        sqlite_where=sa.text("status = 'approved'"),
    )

    if op.get_bind().dialect.name == "postgresql":
        op.create_index(
            "ix_search_chunks_embedding_hnsw",
            "search_chunks",
            ["embedding"],
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )
        for table in DIRECT_TENANT_TABLES:
            _policy(table, _membership_sql(f"{table}.organization_id"))
        _policy(
            "document_revisions",
            "(current_user = 'buili_worker' OR EXISTS ("
            "SELECT 1 FROM documents document JOIN organization_members membership "
            "ON membership.organization_id = document.organization_id "
            "WHERE document.id = document_revisions.document_id "
            "AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')"
            "))",
        )
        _policy(
            "project_members",
            "(current_user = 'buili_worker' OR EXISTS ("
            "SELECT 1 FROM projects project JOIN organization_members membership "
            "ON membership.organization_id = project.organization_id "
            "WHERE project.id = project_members.project_id "
            "AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')"
            "))",
        )
        _policy(
            "issue_sources",
            "(current_user = 'buili_worker' OR EXISTS ("
            "SELECT 1 FROM issues issue "
            "JOIN document_revisions revision ON revision.id = issue_sources.revision_id "
            "JOIN documents document ON document.id = revision.document_id "
            "JOIN organization_members membership ON membership.organization_id = issue.organization_id "
            "WHERE issue.id = issue_sources.issue_id "
            "AND document.organization_id = issue.organization_id "
            "AND document.project_id = issue.project_id "
            "AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')"
            "))",
        )
        _policy(
            "issue_evidence",
            "(current_user = 'buili_worker' OR EXISTS ("
            "SELECT 1 FROM issues issue "
            "JOIN evidence field_evidence ON field_evidence.id = issue_evidence.evidence_id "
            "JOIN organization_members membership ON membership.organization_id = issue.organization_id "
            "WHERE issue.id = issue_evidence.issue_id "
            "AND field_evidence.organization_id = issue.organization_id "
            "AND field_evidence.project_id = issue.project_id "
            "AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')"
            "))",
        )
        _policy(
            "audit_logs",
            "(current_user = 'buili_worker' OR ("
            "audit_logs.organization_id IS NULL "
            "AND audit_logs.actor_user_id = COALESCE(current_setting('app.current_user_id', true), '')"
            ") OR EXISTS ("
            "SELECT 1 FROM organization_members membership "
            "WHERE membership.organization_id = audit_logs.organization_id "
            "AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')"
            "))",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in INDIRECT_TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        for table in DIRECT_TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
            legacy = f"""(
                current_setting('app.is_worker', true) = 'true'
                OR EXISTS (
                    SELECT 1 FROM organization_members membership
                    WHERE membership.organization_id = {table}.organization_id
                      AND membership.user_id = COALESCE(current_setting('app.current_user_id', true), '')
                )
            )"""
            op.execute(
                f"CREATE POLICY {table}_tenant_isolation ON {table} "
                f"USING ({legacy}) WITH CHECK ({legacy})"
            )
        op.drop_index("ix_search_chunks_embedding_hnsw", table_name="search_chunks", postgresql_using="hnsw")

    op.drop_index("uq_plan_graph_approved_source", table_name="plan_graphs")
    op.drop_index("uq_spatial_scene_approved_source", table_name="spatial_scenes")
    with op.batch_alter_table("spatial_scenes") as batch:
        batch.drop_constraint("uq_spatial_scene_version", type_="unique")
    op.drop_index("uq_document_one_active_revision", table_name="document_revisions")
    op.drop_column("issues", "verification_json")
    op.drop_column("uploads", "scanned_at")
    op.drop_column("uploads", "scan_result_json")
    op.drop_index("ix_auth_sessions_family_id", table_name="auth_sessions")
    with op.batch_alter_table("auth_sessions") as batch:
        batch.drop_constraint("fk_auth_sessions_replaced_by_session_id", type_="foreignkey")
        batch.drop_constraint("fk_auth_sessions_parent_session_id", type_="foreignkey")
        batch.drop_column("revocation_reason")
        batch.drop_column("rotated_at")
        batch.drop_column("replaced_by_session_id")
        batch.drop_column("parent_session_id")
        batch.drop_column("family_id")
    op.drop_column("users", "auth_version")
