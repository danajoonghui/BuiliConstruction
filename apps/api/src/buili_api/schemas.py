from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: T
    request_id: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    id: str
    email: EmailStr
    display_name: str
    avatar_url: str | None = None
    email_verified: bool = False


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=2, max_length=160)
    organization_name: str | None = Field(default=None, min_length=2, max_length=200)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        classes = (any(c.islower() for c in value), any(c.isupper() for c in value), any(c.isdigit() for c in value))
        if sum(classes) < 2:
            raise ValueError("password must contain at least two of lowercase, uppercase, and digits")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str | None = None


class LogoutIn(BaseModel):
    refresh_token: str | None = None


class OIDCExchangeIn(BaseModel):
    id_token: str
    organization_name: str | None = None


class TokenOut(BaseModel):
    access_token: str | None
    refresh_token: str | None
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    csrf_token: str | None = None


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    new_password: str = Field(min_length=12, max_length=256)


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class AuthCapabilitiesOut(BaseModel):
    google_oidc_enabled: bool
    password_reset_enabled: bool
    email_verification_required: bool
    email_delivery: str


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str | None = Field(default=None, max_length=120)


class OrganizationOut(ORMModel):
    id: str
    name: str
    slug: str
    created_at: datetime


class ProjectCreate(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=240)
    code: str = Field(min_length=1, max_length=80)
    project_type: str = "renovation"
    address: str = ""
    timezone: str = "America/Los_Angeles"
    units: Literal["imperial", "metric"] = "imperial"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=240)
    status: Literal["draft", "setup", "active", "on_hold", "closed", "archived"] | None = None
    address: str | None = None
    metadata_json: dict[str, Any] | None = None


class ProjectOut(ORMModel):
    id: str
    organization_id: str
    name: str
    code: str
    status: str
    project_type: str
    address: str
    timezone: str
    units: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class UploadInitIn(BaseModel):
    organization_id: str
    project_id: str | None = None
    filename: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)


class UploadInitOut(BaseModel):
    upload_id: str
    method: Literal["PUT"] = "PUT"
    upload_url: str
    headers: dict[str, str] = Field(default_factory=dict)
    expires_in: int


class UploadCompleteIn(BaseModel):
    sha256: str | None = Field(default=None, min_length=64, max_length=64)


class UploadOut(ORMModel):
    id: str
    organization_id: str
    project_id: str | None
    original_filename: str
    content_type: str
    expected_size: int
    actual_size: int | None
    sha256: str | None
    status: str
    scan_status: str
    scan_result_json: dict[str, Any]
    scanned_at: datetime | None
    expires_at: datetime
    created_at: datetime


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    kind: Literal[
        "drawing", "specification", "rfi", "rfi_response", "submittal", "shop_drawing",
        "change_order", "change_directive", "field_report", "daily_report", "meeting_minutes", "other"
    ] = "other"
    discipline: str = "general"


class RevisionCreate(BaseModel):
    upload_id: str
    revision: str = Field(min_length=1, max_length=80)
    issue_date: datetime | None = None
    status: Literal["uploaded", "review_required", "current", "approved", "superseded", "void"] = "current"
    sheet_number: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    process: bool = True


class RevisionOut(ORMModel):
    id: str
    document_id: str
    revision: str
    issue_date: datetime | None
    status: str
    storage_key: str
    content_type: str
    size: int
    sha256: str
    sheet_number: str | None
    extracted_text: str
    metadata_json: dict[str, Any]
    created_at: datetime


class DocumentOut(ORMModel):
    id: str
    organization_id: str
    project_id: str
    title: str
    kind: str
    discipline: str
    created_at: datetime
    revisions: list[RevisionOut] = Field(default_factory=list)


class EvidenceCreate(BaseModel):
    upload_id: str | None = None
    kind: Literal["photo", "video", "voice_note", "measurement", "document", "annotation", "scan"]
    title: str = Field(min_length=1, max_length=512)
    description: str = ""
    captured_at: datetime | None = None
    location_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    transcript: str = ""
    analyze: bool = False


class EvidenceOut(ORMModel):
    id: str
    organization_id: str
    project_id: str
    kind: str
    title: str
    description: str
    storage_key: str | None
    content_type: str | None
    captured_at: datetime | None
    location_json: dict[str, Any]
    metadata_json: dict[str, Any]
    transcript: str
    analysis_json: dict[str, Any]
    created_by: str
    created_at: datetime


class IssueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=1, max_length=512)
    description: str = ""
    issue_type: str = "design_question"
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    observed_condition: str = ""
    expected_condition: str = ""
    difference: str = ""
    location_json: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    revision_ids: list[str] = Field(default_factory=list)


class IssueUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    observed_condition: str | None = None
    expected_condition: str | None = None
    difference: str | None = None
    assigned_to: str | None = None
    location_json: dict[str, Any] | None = None


class IssueOut(ORMModel):
    id: str
    organization_id: str
    project_id: str
    number: str
    title: str
    description: str
    issue_type: str
    status: str
    priority: str
    observed_condition: str
    expected_condition: str
    difference: str
    classification: str
    recommended_action: str
    evidence_sufficiency: str
    missing_evidence: list[str]
    verification_json: dict[str, Any]
    location_json: dict[str, Any]
    assigned_to: str | None
    created_by: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IssueLinkEvidenceIn(BaseModel):
    evidence_id: str
    relationship_type: str = "supports"


class IssueLinkSourceIn(BaseModel):
    revision_id: str
    page: int | None = None
    bbox_json: list[float] = Field(default_factory=list)
    quote: str = ""
    relationship_type: str = "requirement"


class JobOut(ORMModel):
    id: str
    organization_id: str
    project_id: str | None
    kind: str
    status: str
    progress: float
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    error_json: dict[str, Any]
    attempts: int
    created_at: datetime
    updated_at: datetime


class ReportCreate(BaseModel):
    kind: Literal["rfi", "punch", "change_event", "evidence_package", "model_update_request"] = "rfi"
    title: str | None = None
    approve: bool = False


class ReportArtifactOut(ORMModel):
    id: str
    report_id: str
    format: str
    storage_key: str
    content_type: str
    size: int
    sha256: str
    created_at: datetime


class ReportOut(ORMModel):
    id: str
    organization_id: str
    project_id: str
    issue_id: str | None
    kind: str
    status: str
    version: int
    title: str
    storage_key: str
    content_type: str
    template_version: str
    source_index_json: list[dict[str, Any]]
    generated_by: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    artifacts: list[ReportArtifactOut] = Field(default_factory=list)


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=10, ge=1, le=50)
    source_types: list[str] = Field(default_factory=list)


class SearchHit(BaseModel):
    chunk_id: str
    source_type: str
    source_id: str
    content: str
    score: float
    page: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchOut(BaseModel):
    query: str
    hits: list[SearchHit]
    mode: Literal["hybrid", "lexical"]


class AskIn(SearchIn):
    limit: int = Field(default=8, ge=1, le=20)


class Citation(BaseModel):
    index: int
    source_type: str
    source_id: str
    chunk_id: str
    excerpt: str
    page: int | None = None


class AskOut(BaseModel):
    answer: str
    citations: list[Citation]
    provider: str
    model: str | None = None


class SpatialGenerateIn(BaseModel):
    source_revision_id: str
    options: dict[str, Any] = Field(default_factory=dict)


class SpatialSceneOut(ORMModel):
    id: str
    organization_id: str
    project_id: str
    source_revision_id: str
    plan_graph_id: str
    version: int
    status: str
    glb_storage_key: str | None
    semantic_storage_key: str | None
    source_mapping_storage_key: str | None
    confidence_json: dict[str, Any]
    created_at: datetime


class PlanGraphOut(ORMModel):
    id: str
    organization_id: str
    project_id: str
    source_revision_id: str
    version: int
    status: str
    graph_json: dict[str, Any]
    scale_json: dict[str, Any]
    source_hash: str
    pipeline_version: str
    review_json: dict[str, Any]
    reviewer_id: str | None
    reviewed_at: datetime | None
    created_at: datetime


class SpatialReviewIn(BaseModel):
    attestation: str = Field(min_length=20, max_length=4000)
    scale_verified: bool
    geometry_verified: bool
    locked_object_ids: list[str] = Field(default_factory=list, max_length=5000)
