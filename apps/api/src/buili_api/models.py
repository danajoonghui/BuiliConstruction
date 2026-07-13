from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[str]: JSON, list[dict[str, Any]]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("usr"))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    oidc_issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    oidc_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_version: Mapped[int] = mapped_column(Integer, default=0)
    memberships: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_user_oidc"),)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ses"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[str] = mapped_column(String(40), index=True, default=lambda: new_id("fam"))
    parent_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="SET NULL"), nullable=True
    )
    replaced_by_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OneTimeAuthToken(Base):
    __tablename__ = "one_time_auth_tokens"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("otp"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("org"))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("mem"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("prj"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(240))
    code: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="active")
    project_type: Mapped[str] = mapped_column(String(64), default="renovation")
    address: Mapped[str] = mapped_column(String(512), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Los_Angeles")
    units: Mapped[str] = mapped_column(String(16), default="imperial")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_project_code"),)


class ProjectMember(Base):
    __tablename__ = "project_members"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("pmem"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)


class Upload(Base, TimestampMixin):
    __tablename__ = "uploads"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("upl"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(255))
    expected_size: Mapped[int] = mapped_column(Integer)
    actual_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="initiated")
    scan_status: Mapped[str] = mapped_column(String(32), default="pending")
    scan_result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("doc"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(64), default="other")
    discipline: Mapped[str] = mapped_column(String(64), default="general")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revisions: Mapped[list["DocumentRevision"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentRevision(Base, TimestampMixin):
    __tablename__ = "document_revisions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rev"))
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    upload_id: Mapped[str | None] = mapped_column(
        ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
    )
    revision: Mapped[str] = mapped_column(String(80))
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="current")
    storage_key: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    sheet_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    document: Mapped[Document] = relationship(back_populates="revisions")
    __table_args__ = (
        UniqueConstraint("document_id", "revision", name="uq_document_revision"),
        Index(
            "uq_document_one_active_revision",
            "document_id",
            unique=True,
            postgresql_where=text("status IN ('current', 'approved')"),
            sqlite_where=text("status IN ('current', 'approved')"),
        ),
    )


class Evidence(Base, TimestampMixin):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("evd"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    upload_id: Mapped[str | None] = mapped_column(
        ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    transcript: Mapped[str] = mapped_column(Text, default="")
    analysis_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Issue(Base, TimestampMixin):
    __tablename__ = "issues"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("iss"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    issue_type: Mapped[str] = mapped_column(String(64), default="design_question")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    observed_condition: Mapped[str] = mapped_column(Text, default="")
    expected_condition: Mapped[str] = mapped_column(Text, default="")
    difference: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[str] = mapped_column(String(64), default="insufficient_evidence")
    recommended_action: Mapped[str] = mapped_column(
        String(64), default="additional_evidence_required"
    )
    evidence_sufficiency: Mapped[str] = mapped_column(String(32), default="insufficient")
    missing_evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    verification_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    location_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    assigned_to: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_issue_number"),)


class IssueEvidence(Base):
    __tablename__ = "issue_evidence"
    issue_id: Mapped[str] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )
    relationship_type: Mapped[str] = mapped_column(String(32), default="supports")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IssueSource(Base):
    __tablename__ = "issue_sources"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("src"))
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_json: Mapped[list[float]] = mapped_column(JSON, default=list)
    quote: Mapped[str] = mapped_column(Text, default="")
    relationship_type: Mapped[str] = mapped_column(String(32), default="requirement")
    __table_args__ = (UniqueConstraint("issue_id", "revision_id", "page", name="uq_issue_source"),)


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("job"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Report(Base, TimestampMixin):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rpt"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    issue_id: Mapped[str | None] = mapped_column(
        ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(255), default="application/pdf")
    template_version: Mapped[str] = mapped_column(String(80), default="buili.issue-pack.v1")
    source_index_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    generated_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    artifacts: Mapped[list["ReportArtifact"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    __table_args__ = (
        UniqueConstraint("issue_id", "kind", "version", name="uq_report_issue_kind_version"),
    )


class ReportArtifact(Base):
    """An immutable output belonging to one versioned report package."""

    __tablename__ = "report_artifacts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rat"))
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    format: Mapped[str] = mapped_column(String(16))
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    report: Mapped[Report] = relationship(back_populates="artifacts")
    __table_args__ = (UniqueConstraint("report_id", "format", name="uq_report_artifact_format"),)


class SearchChunk(Base, TimestampMixin):
    __tablename__ = "search_chunks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("chk"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(40), index=True)
    content: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_json: Mapped[list[float]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536).with_variant(JSON, "sqlite"), nullable=True
    )
    __table_args__ = (
        Index("ix_search_chunk_project_source", "project_id", "source_type", "source_id"),
        Index(
            "ix_search_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class SpatialScene(Base, TimestampMixin):
    __tablename__ = "spatial_scenes"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("scn"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source_revision_id: Mapped[str] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="RESTRICT"), index=True
    )
    plan_graph_id: Mapped[str] = mapped_column(
        ForeignKey("plan_graphs.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="review_required")
    glb_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    semantic_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_mapping_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    confidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    __table_args__ = (
        UniqueConstraint(
            "project_id", "source_revision_id", "version", name="uq_spatial_scene_version"
        ),
        Index(
            "uq_spatial_scene_approved_source",
            "project_id",
            "source_revision_id",
            unique=True,
            postgresql_where=text("status = 'approved'"),
            sqlite_where=text("status = 'approved'"),
        ),
    )


class FixtureAsset(Base, TimestampMixin):
    """Versioned presentation geometry for a semantic PlanGraph fixture.

    The asset never owns position, dimensions, or contractual meaning. Those
    remain in the approved PlanGraph; this table stores only reviewable visual
    geometry and its provider provenance.
    """

    __tablename__ = "fixture_assets"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("fas"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    semantic_type: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    provider: Mapped[str] = mapped_column(String(32), default="tripo")
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    prompt: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    glb_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    preview_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bounds_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    transform_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    review_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("project_id", "semantic_type", "version", name="uq_fixture_asset_version"),
        Index(
            "uq_fixture_asset_approved_type",
            "project_id",
            "semantic_type",
            unique=True,
            postgresql_where=text("status = 'approved'"),
            sqlite_where=text("status = 'approved'"),
        ),
    )


class PlanGraph(Base, TimestampMixin):
    """Versioned semantic plan graph; immutable once approved or superseded."""

    __tablename__ = "plan_graphs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("pgr"))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source_revision_id: Mapped[str] = mapped_column(
        ForeignKey("document_revisions.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="review_required")
    graph_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scale_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_hash: Mapped[str] = mapped_column(String(64), default="")
    pipeline_version: Mapped[str] = mapped_column(String(80), default="")
    review_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    __table_args__ = (
        UniqueConstraint(
            "project_id", "source_revision_id", "version", name="uq_plan_graph_version"
        ),
        Index("ix_plan_graph_current", "project_id", "status", "created_at"),
        Index(
            "uq_plan_graph_approved_source",
            "project_id",
            "source_revision_id",
            unique=True,
            postgresql_where=text("status = 'approved'"),
            sqlite_where=text("status = 'approved'"),
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("aud"))
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
