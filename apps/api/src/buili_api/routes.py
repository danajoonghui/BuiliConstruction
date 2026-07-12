from __future__ import annotations

import hashlib
import base64
import secrets
import tempfile
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .core.config import Settings, get_settings
from .core.errors import AppError
from .db import database_ready, get_session
from .deps import current_user, ensure_org_access, project_for_resource, require_project
from .models import (
    AuthSession,
    AuditLog,
    Document,
    DocumentRevision,
    Evidence,
    Issue,
    IssueEvidence,
    IssueSource,
    Job,
    Organization,
    OrganizationMember,
    OneTimeAuthToken,
    PlanGraph,
    Project,
    ProjectMember,
    Report,
    SearchChunk,
    ReportArtifact,
    SpatialScene,
    Upload,
    User,
    utcnow,
)
from .schemas import (
    AskIn,
    AskOut,
    Citation,
    DocumentCreate,
    DocumentOut,
    EvidenceCreate,
    EvidenceOut,
    ForgotPasswordIn,
    IssueCreate,
    IssueLinkEvidenceIn,
    IssueLinkSourceIn,
    IssueOut,
    IssueUpdate,
    JobOut,
    LoginIn,
    LogoutIn,
    OIDCExchangeIn,
    AuthCapabilitiesOut,
    OrganizationCreate,
    OrganizationOut,
    PlanGraphOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    RefreshIn,
    ResetPasswordIn,
    ReportCreate,
    ReportArtifactOut,
    ReportOut,
    RevisionCreate,
    SearchIn,
    SearchOut,
    SignupIn,
    SpatialGenerateIn,
    SpatialReviewIn,
    SpatialSceneOut,
    TokenOut,
    UploadCompleteIn,
    UploadInitIn,
    UploadInitOut,
    UploadOut,
    UserOut,
    VerifyEmailIn,
)
from .security import (
    OIDCVerifier,
    hash_password,
    issue_token_pair,
    normalize_email,
    provision_oidc_user,
    slugify,
    token_hash,
    verify_password,
)
from .services.audit import audit
from .services.issues import analyze_issue as verify_issue
from .services.issues import approval_blockers
from .services.spatial import official_use_gate

router = APIRouter()


def envelope(request: Request, data: Any, **meta: Any) -> dict[str, Any]:
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif isinstance(data, list):
        data = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in data]
    return {"data": data, "request_id": request.state.request_id, "meta": meta}


def services(request: Request):
    return request.app.state.services


async def bind_database_actor(session: AsyncSession, user_id: str, settings: Settings) -> None:
    if not settings.is_sqlite:
        await session.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": user_id},
        )


def safe_display_filename(value: str) -> str:
    basename = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    cleaned = "".join(character for character in basename if character.isalnum() or character in " ._()-")
    cleaned = cleaned.strip(" .")[:200]
    if not cleaned:
        raise AppError(422, "INVALID_FILENAME", "Filename is invalid")
    return cleaned


async def _token_response(session: AsyncSession, user: User, settings: Settings) -> TokenOut:
    access, refresh, expires = await issue_token_pair(session, user, settings)
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires,
        user=UserOut.model_validate(user),
    )


def set_auth_cookies(response: Response, token: TokenOut, settings: Settings) -> None:
    csrf = secrets.token_urlsafe(32)
    token.csrf_token = csrf
    common = {
        "domain": settings.cookie_domain,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }
    response.set_cookie(
        "buili_access",
        token.access_token or "",
        httponly=True,
        path="/",
        max_age=token.expires_in,
        **common,
    )
    response.set_cookie(
        "buili_refresh",
        token.refresh_token or "",
        httponly=True,
        path="/v1/auth",
        max_age=settings.refresh_token_days * 86400,
        **common,
    )
    response.set_cookie(
        "buili_csrf",
        csrf,
        httponly=False,
        path="/",
        max_age=settings.refresh_token_days * 86400,
        **common,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie("buili_access", path="/", domain=settings.cookie_domain)
    response.delete_cookie("buili_refresh", path="/v1/auth", domain=settings.cookie_domain)
    response.delete_cookie("buili_csrf", path="/", domain=settings.cookie_domain)


def token_for_transport(token: TokenOut, transport: str) -> TokenOut:
    if transport == "cookie":
        return token.model_copy(update={"access_token": None, "refresh_token": None})
    return token


async def create_one_time_token(
    session: AsyncSession, user: User, purpose: str, settings: Settings
) -> str:
    # Only the newest token for a purpose remains usable. The update and insert
    # occur in the same transaction as email delivery bookkeeping.
    await session.execute(
        update(OneTimeAuthToken)
        .where(
            OneTimeAuthToken.user_id == user.id,
            OneTimeAuthToken.purpose == purpose,
            OneTimeAuthToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    raw = secrets.token_urlsafe(48)
    session.add(
        OneTimeAuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=token_hash(raw),
            expires_at=utcnow() + timedelta(minutes=settings.auth_token_minutes),
        )
    )
    await session.flush()
    return raw


@router.get("/health/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
async def ready(request: Request) -> Response:
    db_ready = await database_ready()
    payload = {"status": "ready" if db_ready else "not_ready", "database": db_ready}
    return Response(
        content=request.app.state.json_dumps(payload),
        status_code=200 if db_ready else 503,
        media_type="application/json",
    )


@router.post("/v1/auth/signup", status_code=201)
async def signup(
    payload: SignupIn,
    request: Request,
    response: Response,
    transport: str = Query(default="cookie", pattern="^(cookie|body)$"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    email = normalize_email(payload.email)
    if await session.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "EMAIL_ALREADY_REGISTERED", "An account already exists for this email")
    user = User(email=email, display_name=payload.display_name.strip(), password_hash=hash_password(payload.password), email_verified=False)
    session.add(user)
    await session.flush()
    name = payload.organization_name or f"{payload.display_name}'s team"
    slug = slugify(name)
    if await session.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug = f"{slug}-{secrets.token_hex(3)}"
    organization = Organization(name=name, slug=slug)
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    await session.flush()
    await bind_database_actor(session, user.id, settings)
    audit(session, action="USER_SIGNED_UP", resource_type="user", resource_id=user.id, actor_user_id=user.id, organization_id=organization.id, request_id=request.state.request_id)
    verification = None
    if services(request).email.enabled:
        verification = await create_one_time_token(session, user, "email_verify", settings)
        await services(request).email.send(
            to=user.email,
            subject="Verify your BUILI email",
            text=f"Verify your BUILI email: {settings.frontend_url.rstrip('/')}/verify-email?token={verification}",
        )
    if settings.require_email_verification:
        await session.commit()
        return envelope(
            request,
            {
                "user": UserOut.model_validate(user).model_dump(mode="json"),
                "verification_required": True,
                "access_token": None,
                "refresh_token": None,
                "csrf_token": None,
            },
        )
    token = await _token_response(session, user, settings)
    await session.commit()
    if transport == "cookie":
        set_auth_cookies(response, token, settings)
    return envelope(request, token_for_transport(token, transport))


@router.post("/v1/auth/login")
async def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    transport: str = Query(default="cookie", pattern="^(cookie|body)$"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    user = await session.scalar(
        select(User).where(User.email == normalize_email(payload.email)).with_for_update()
    )
    if user is None or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
    if settings.require_email_verification and not user.email_verified:
        raise AppError(403, "EMAIL_NOT_VERIFIED", "Verify your email before signing in")
    await bind_database_actor(session, user.id, settings)
    token = await _token_response(session, user, settings)
    audit(session, action="USER_LOGGED_IN", resource_type="user", resource_id=user.id, actor_user_id=user.id, request_id=request.state.request_id)
    await session.commit()
    if transport == "cookie":
        set_auth_cookies(response, token, settings)
    return envelope(request, token_for_transport(token, transport))


@router.post("/v1/auth/refresh")
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshIn | None = None,
    transport: str = Query(default="cookie", pattern="^(cookie|body)$"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    raw_refresh = (payload.refresh_token if payload else None) or request.cookies.get("buili_refresh")
    if not raw_refresh:
        raise AppError(401, "INVALID_REFRESH_TOKEN", "Refresh token is required")
    auth_session = await session.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == token_hash(raw_refresh))
        .with_for_update()
    )
    if auth_session is not None and auth_session.rotated_at is not None:
        user = await session.scalar(select(User).where(User.id == auth_session.user_id).with_for_update())
        now = utcnow()
        first_detection = auth_session.revocation_reason != "refresh_token_reuse"
        if first_detection:
            await session.execute(
                update(AuthSession)
                .where(AuthSession.family_id == auth_session.family_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=now, revocation_reason="refresh_token_reuse")
            )
            auth_session.revocation_reason = "refresh_token_reuse"
            if user:
                user.auth_version += 1
        await session.commit()
        raise AppError(401, "REFRESH_TOKEN_REUSE_DETECTED", "Refresh token reuse was detected; this session family was revoked")
    expires_at = auth_session.expires_at if auth_session else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if auth_session is None or auth_session.revoked_at is not None or not expires_at or expires_at <= utcnow():
        raise AppError(401, "INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired")
    user = await session.scalar(select(User).where(User.id == auth_session.user_id).with_for_update())
    if user is None or not user.is_active:
        raise AppError(401, "USER_UNAVAILABLE", "User is unavailable")
    if settings.require_email_verification and not user.email_verified:
        auth_session.revoked_at = utcnow()
        auth_session.revocation_reason = "email_unverified"
        await session.commit()
        raise AppError(403, "EMAIL_NOT_VERIFIED", "Verify your email before refreshing a session")
    pair = await issue_token_pair(session, user, settings, rotated_from=auth_session)
    token = TokenOut(
        access_token=pair[0],
        refresh_token=pair[1],
        expires_in=pair[2],
        user=UserOut.model_validate(user),
    )
    await session.commit()
    if transport == "cookie":
        set_auth_cookies(response, token, settings)
    return envelope(request, token_for_transport(token, transport))


@router.post("/v1/auth/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    payload: LogoutIn | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    raw_refresh = (payload.refresh_token if payload else None) or request.cookies.get("buili_refresh")
    auth_session = await session.scalar(
        select(AuthSession).where(AuthSession.refresh_token_hash == token_hash(raw_refresh)).with_for_update()
    ) if raw_refresh else None
    if auth_session and auth_session.revoked_at is None:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.family_id == auth_session.family_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=utcnow(), revocation_reason="logout")
        )
        await session.commit()
    clear_auth_cookies(response, settings)
    response.status_code = 204
    return response


@router.post("/v1/auth/oidc/exchange")
async def oidc_exchange(
    payload: OIDCExchangeIn,
    request: Request,
    response: Response,
    transport: str = Query(default="cookie", pattern="^(cookie|body)$"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    claims = await OIDCVerifier(settings).verify(payload.id_token)
    user = await provision_oidc_user(session, claims, settings, payload.organization_name)
    await bind_database_actor(session, user.id, settings)
    token = await _token_response(session, user, settings)
    audit(session, action="OIDC_LOGIN", resource_type="user", resource_id=user.id, actor_user_id=user.id, request_id=request.state.request_id)
    await session.commit()
    if transport == "cookie":
        set_auth_cookies(response, token, settings)
    return envelope(request, token_for_transport(token, transport))


@router.post("/v1/auth/oidc/link")
async def oidc_link(
    payload: OIDCExchangeIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    claims = await OIDCVerifier(settings).verify(payload.id_token)
    if normalize_email(str(claims.get("email", ""))) != user.email:
        raise AppError(409, "OIDC_EMAIL_MISMATCH", "Google email must match the signed-in BUILI account")
    existing = await session.scalar(
        select(User.id).where(
            User.oidc_issuer == str(claims.get("iss", settings.oidc_issuer)),
            User.oidc_subject == str(claims["sub"]),
            User.id != user.id,
        )
    )
    if existing:
        raise AppError(409, "OIDC_IDENTITY_IN_USE", "This Google identity is already linked")
    user.oidc_issuer = str(claims.get("iss", settings.oidc_issuer))
    user.oidc_subject = str(claims["sub"])
    user.avatar_url = claims.get("picture") or user.avatar_url
    user.email_verified = True
    audit(session, action="OIDC_IDENTITY_LINKED", resource_type="user", resource_id=user.id, actor_user_id=user.id, request_id=request.state.request_id)
    await session.commit()
    return envelope(request, {"linked": True})


@router.get("/v1/auth/me")
async def me(request: Request, user: User = Depends(current_user)) -> dict:
    return envelope(request, UserOut.model_validate(user))


@router.get("/v1/auth/capabilities")
async def auth_capabilities(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    output = AuthCapabilitiesOut(
        google_oidc_enabled=bool(settings.oidc_client_id),
        password_reset_enabled=services(request).email.enabled,
        email_verification_required=settings.require_email_verification,
        email_delivery="configured" if services(request).email.enabled else "disabled",
    )
    return envelope(request, output)


@router.post("/v1/auth/forgot-password", status_code=202)
async def forgot_password(
    payload: ForgotPasswordIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    user = await session.scalar(
        select(User).where(User.email == normalize_email(payload.email)).with_for_update()
    )
    if user and services(request).email.enabled:
        raw = await create_one_time_token(session, user, "password_reset", settings)
        await services(request).email.send(
            to=user.email,
            subject="Reset your BUILI password",
            text=f"Reset your BUILI password: {settings.frontend_url.rstrip('/')}/reset-password?token={raw}",
        )
        await session.commit()
    # Deliberately non-enumerating, including when email delivery is disabled.
    return envelope(request, {"accepted": True})


@router.post("/v1/auth/reset-password")
async def reset_password(
    payload: ResetPasswordIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    record = await session.scalar(
        select(OneTimeAuthToken).where(
            OneTimeAuthToken.token_hash == token_hash(payload.token),
            OneTimeAuthToken.purpose == "password_reset",
        ).with_for_update()
    )
    expires_at = record.expires_at if record else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if record is None or record.used_at is not None or not expires_at or expires_at <= utcnow():
        raise AppError(400, "RESET_TOKEN_INVALID", "Password reset token is invalid or expired")
    user = await session.scalar(select(User).where(User.id == record.user_id).with_for_update())
    if user is None:
        raise AppError(400, "RESET_TOKEN_INVALID", "Password reset token is invalid or expired")
    await bind_database_actor(session, user.id, settings)
    user.password_hash = hash_password(payload.new_password)
    user.auth_version += 1
    record.used_at = utcnow()
    await session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow(), revocation_reason="password_reset")
    )
    await session.execute(
        update(OneTimeAuthToken)
        .where(
            OneTimeAuthToken.user_id == user.id,
            OneTimeAuthToken.purpose == "password_reset",
            OneTimeAuthToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    audit(session, action="PASSWORD_RESET", resource_type="user", resource_id=user.id, actor_user_id=user.id, request_id=request.state.request_id)
    await session.commit()
    return envelope(request, {"reset": True})


@router.post("/v1/auth/request-email-verification", status_code=202)
async def request_email_verification(
    payload: ForgotPasswordIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not services(request).email.enabled:
        raise AppError(503, "EMAIL_DELIVERY_DISABLED", "Email verification delivery is not configured")
    user = await session.scalar(
        select(User).where(User.email == normalize_email(payload.email)).with_for_update()
    )
    if user and not user.email_verified:
        raw = await create_one_time_token(session, user, "email_verify", settings)
        await services(request).email.send(
            to=user.email,
            subject="Verify your BUILI email",
            text=f"Verify your BUILI email: {settings.frontend_url.rstrip('/')}/verify-email?token={raw}",
        )
        await session.commit()
    return envelope(request, {"accepted": True})


@router.post("/v1/auth/verify-email")
async def verify_email(
    payload: VerifyEmailIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    record = await session.scalar(
        select(OneTimeAuthToken).where(
            OneTimeAuthToken.token_hash == token_hash(payload.token),
            OneTimeAuthToken.purpose == "email_verify",
        ).with_for_update()
    )
    expires_at = record.expires_at if record else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if record is None or record.used_at is not None or not expires_at or expires_at <= utcnow():
        raise AppError(400, "VERIFY_TOKEN_INVALID", "Email verification token is invalid or expired")
    user = await session.scalar(select(User).where(User.id == record.user_id).with_for_update())
    if user is None:
        raise AppError(400, "VERIFY_TOKEN_INVALID", "Email verification token is invalid or expired")
    user.email_verified = True
    record.used_at = utcnow()
    await session.execute(
        update(OneTimeAuthToken)
        .where(
            OneTimeAuthToken.user_id == user.id,
            OneTimeAuthToken.purpose == "email_verify",
            OneTimeAuthToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    await session.commit()
    return envelope(request, {"verified": True})


@router.get("/v1/auth/csrf")
async def csrf_token(
    request: Request,
    user: User = Depends(current_user),
) -> dict:
    del user
    token = request.cookies.get("buili_csrf")
    if not token:
        raise AppError(401, "CSRF_TOKEN_UNAVAILABLE", "No browser CSRF session is available")
    return envelope(request, {"csrf_token": token})


@router.get("/v1/organizations")
async def list_organizations(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = list(
        (
            await session.scalars(
                select(Organization)
                .join(OrganizationMember)
                .where(OrganizationMember.user_id == user.id)
                .order_by(Organization.name)
            )
        ).all()
    )
    return envelope(request, [OrganizationOut.model_validate(item) for item in rows])


@router.post("/v1/organizations", status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    slug = slugify(payload.slug or payload.name)
    if await session.scalar(select(Organization.id).where(Organization.slug == slug)):
        raise AppError(409, "ORGANIZATION_SLUG_TAKEN", "Organization slug is already in use")
    organization = Organization(name=payload.name, slug=slug)
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    audit(session, action="ORGANIZATION_CREATED", resource_type="organization", resource_id=organization.id, actor_user_id=user.id, organization_id=organization.id, request_id=request.state.request_id)
    await session.commit()
    return envelope(request, OrganizationOut.model_validate(organization))


@router.get("/v1/projects")
async def list_projects(
    request: Request,
    organization_id: str | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    statement = (
        select(Project)
        .outerjoin(
            OrganizationMember,
            (OrganizationMember.organization_id == Project.organization_id) & (OrganizationMember.user_id == user.id),
        )
        .outerjoin(ProjectMember, (ProjectMember.project_id == Project.id) & (ProjectMember.user_id == user.id))
        .where(or_(OrganizationMember.id.is_not(None), ProjectMember.id.is_not(None)))
        .distinct()
        .order_by(Project.updated_at.desc())
    )
    if organization_id:
        statement = statement.where(Project.organization_id == organization_id)
    rows = list((await session.scalars(statement)).all())
    return envelope(request, [ProjectOut.model_validate(item) for item in rows])


@router.post("/v1/projects", status_code=201)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await ensure_org_access(session, user.id, payload.organization_id, "admin")
    if await session.scalar(select(Project.id).where(Project.organization_id == payload.organization_id, Project.code == payload.code)):
        raise AppError(409, "PROJECT_CODE_TAKEN", "Project code already exists in this organization")
    project = Project(**payload.model_dump())
    session.add(project)
    await session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role="admin"))
    audit(session, action="PROJECT_CREATED", resource_type="project", resource_id=project.id, actor_user_id=user.id, organization_id=project.organization_id, project_id=project.id, request_id=request.state.request_id)
    await session.commit()
    return envelope(request, ProjectOut.model_validate(project))


@router.get("/v1/projects/{project_id}")
async def get_project(
    request: Request,
    project: Project = Depends(require_project("project:read")),
) -> dict:
    return envelope(request, ProjectOut.model_validate(project))


@router.patch("/v1/projects/{project_id}")
async def update_project(
    payload: ProjectUpdate,
    request: Request,
    project: Project = Depends(require_project("project:update")),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    audit(session, action="PROJECT_UPDATED", resource_type="project", resource_id=project.id, actor_user_id=user.id, organization_id=project.organization_id, project_id=project.id, request_id=request.state.request_id)
    await session.commit()
    return envelope(request, ProjectOut.model_validate(project))


@router.post("/v1/uploads/init", status_code=201)
async def init_upload(
    payload: UploadInitIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    if payload.size > settings.max_upload_bytes:
        raise AppError(413, "UPLOAD_TOO_LARGE", "File exceeds the configured upload limit")
    if payload.project_id:
        project = await project_for_resource(session, payload.project_id, user, "evidence:create")
        if project.organization_id != payload.organization_id:
            raise AppError(409, "UPLOAD_SCOPE_MISMATCH", "Project does not belong to organization")
    else:
        await ensure_org_access(session, user.id, payload.organization_id)
    if settings.storage_backend == "s3" and not payload.sha256:
        raise AppError(422, "UPLOAD_CHECKSUM_REQUIRED", "SHA-256 is required for direct object storage uploads")
    filename = safe_display_filename(payload.filename)
    upload = Upload(
        organization_id=payload.organization_id,
        project_id=payload.project_id,
        created_by=user.id,
        object_key=f"org/{payload.organization_id}/project/{payload.project_id or '_unassigned'}/uploads/{secrets.token_hex(16)}/{filename}",
        original_filename=filename,
        content_type=payload.content_type,
        expected_size=payload.size,
        sha256=payload.sha256,
        expires_at=utcnow() + timedelta(seconds=settings.upload_url_expiry_seconds),
    )
    session.add(upload)
    await session.flush()
    if settings.storage_backend == "local":
        upload_url = f"{settings.public_api_url.rstrip('/')}/v1/uploads/{upload.id}/content"
    else:
        upload_url = await services(request).storage.create_upload_url(upload.object_key, upload.content_type, settings.upload_url_expiry_seconds, upload.sha256)
    await session.commit()
    output = UploadInitOut(
        upload_id=upload.id,
        upload_url=upload_url,
        headers={
            "Content-Type": upload.content_type,
            **({"x-amz-checksum-sha256": base64.b64encode(bytes.fromhex(upload.sha256)).decode("ascii")} if settings.storage_backend == "s3" and upload.sha256 else {}),
        },
        expires_in=settings.upload_url_expiry_seconds,
    )
    return envelope(request, output)


@router.put("/v1/uploads/{upload_id}/content", status_code=204)
async def local_upload_content(
    upload_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    if settings.storage_backend != "local":
        raise AppError(404, "LOCAL_UPLOAD_DISABLED", "Direct API upload is only available with local storage")
    upload = await session.get(Upload, upload_id)
    if upload is None:
        raise AppError(404, "UPLOAD_NOT_FOUND", "Upload was not found")
    await ensure_org_access(session, user.id, upload.organization_id)
    if upload.created_by != user.id:
        await ensure_org_access(session, user.id, upload.organization_id, "admin")
    if upload.status != "initiated" or upload.expires_at.replace(tzinfo=timezone.utc) <= utcnow():
        raise AppError(409, "UPLOAD_NOT_WRITABLE", "Upload is expired or no longer writable")
    digest = hashlib.sha256()
    size = 0
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temporary:
            temporary_path = temporary.name
            async for chunk in request.stream():
                size += len(chunk)
                if size > upload.expected_size or size > settings.max_upload_bytes:
                    raise AppError(413, "UPLOAD_TOO_LARGE", "Upload exceeded its declared or configured size")
                digest.update(chunk)
                temporary.write(chunk)
        if size != upload.expected_size:
            raise AppError(409, "UPLOAD_SIZE_MISMATCH", "Uploaded bytes do not match the declared size")
        computed = digest.hexdigest()
        if upload.sha256 and upload.sha256 != computed:
            raise AppError(409, "UPLOAD_CHECKSUM_MISMATCH", "Uploaded bytes do not match the declared checksum")
        info = await services(request).storage.put_file(upload.object_key, Path(temporary_path), upload.content_type)
        temporary_path = None
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)
    upload.actual_size = info.size
    upload.sha256 = info.sha256
    upload.status = "uploaded"
    await session.commit()
    return Response(status_code=204)


@router.post("/v1/uploads/{upload_id}/complete")
async def complete_upload(
    upload_id: str,
    payload: UploadCompleteIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    upload = await session.get(Upload, upload_id)
    if upload is None:
        raise AppError(404, "UPLOAD_NOT_FOUND", "Upload was not found")
    await ensure_org_access(session, user.id, upload.organization_id)
    expires_at = upload.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if upload.status == "complete" and upload.scan_status == "clean":
        return envelope(request, UploadOut.model_validate(upload), idempotent=True)
    if expires_at <= utcnow():
        raise AppError(410, "UPLOAD_EXPIRED", "Upload completion window has expired")
    if upload.status not in {"initiated", "uploaded"}:
        raise AppError(409, "UPLOAD_STATE_INVALID", "Upload is not ready for completion")
    info = await services(request).storage.stat(upload.object_key)
    if info.size != upload.expected_size:
        raise AppError(409, "UPLOAD_SIZE_MISMATCH", "Stored object does not match the declared size")
    checksum = info.sha256
    if upload.sha256 and checksum and upload.sha256 != checksum:
        raise AppError(409, "UPLOAD_CHECKSUM_MISMATCH", "Stored object checksum does not match")
    upload.actual_size = info.size
    upload.sha256 = checksum or upload.sha256
    upload.status = "quarantined"
    upload.scan_status = "pending"
    job = None
    if settings.storage_backend == "local":
        try:
            result = await services(request).scanner.scan(
                await services(request).storage.read_bytes(upload.object_key),
                upload.content_type,
                upload.original_filename,
            )
        except AppError as exc:
            upload.scan_status = "infected" if exc.code == "MALWARE_DETECTED" else "error"
            upload.scan_result_json = {"code": exc.code, "message": exc.message, "details": exc.details}
            upload.scanned_at = utcnow()
            upload.status = "rejected" if exc.code == "MALWARE_DETECTED" else "quarantined"
            await session.commit()
            raise
        upload.scan_status = str(result["status"])
        upload.scan_result_json = result
        upload.scanned_at = utcnow()
        upload.status = "complete" if upload.scan_status == "clean" else "quarantined"
    else:
        job = Job(organization_id=upload.organization_id, project_id=upload.project_id, kind="upload.scan", input_json={"upload_id": upload.id}, created_by=user.id)
        session.add(job)
    audit(session, action="UPLOAD_COMPLETED", resource_type="upload", resource_id=upload.id, actor_user_id=user.id, organization_id=upload.organization_id, project_id=upload.project_id, request_id=request.state.request_id)
    await session.commit()
    if job:
        await services(request).jobs.enqueue(job.id)
    return envelope(request, UploadOut.model_validate(upload), scan_job_id=job.id if job else None)


@router.post("/v1/projects/{project_id}/documents", status_code=201)
async def create_document(
    payload: DocumentCreate,
    request: Request,
    project: Project = Depends(require_project("document:create")),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    document = Document(
        organization_id=project.organization_id,
        project_id=project.id,
        created_by=user.id,
        **payload.model_dump(),
    )
    session.add(document)
    audit(session, action="DOCUMENT_CREATED", resource_type="document", resource_id=document.id, actor_user_id=user.id, organization_id=project.organization_id, project_id=project.id, request_id=request.state.request_id)
    await session.commit()
    return envelope(
        request,
        DocumentOut(
            id=document.id,
            organization_id=document.organization_id,
            project_id=document.project_id,
            title=document.title,
            kind=document.kind,
            discipline=document.discipline,
            created_at=document.created_at,
            revisions=[],
        ),
    )


@router.get("/v1/projects/{project_id}/documents")
async def list_documents(
    request: Request,
    project: Project = Depends(require_project("document:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    documents = list(
        (
            await session.scalars(
                select(Document).where(Document.project_id == project.id).options(selectinload(Document.revisions)).order_by(Document.updated_at.desc())
            )
        ).unique().all()
    )
    return envelope(request, [DocumentOut.model_validate(item) for item in documents])


@router.get("/v1/documents/{document_id}")
async def get_document(
    document_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    document = await session.scalar(select(Document).where(Document.id == document_id).options(selectinload(Document.revisions)))
    if document is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document was not found")
    await project_for_resource(session, document.project_id, user, "document:read")
    return envelope(request, DocumentOut.model_validate(document))


@router.post("/v1/documents/{document_id}/revisions", status_code=201)
async def create_revision(
    document_id: str,
    payload: RevisionCreate,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    document = await session.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document was not found")
    await project_for_resource(session, document.project_id, user, "document:create")
    upload = await session.get(Upload, payload.upload_id)
    if upload is None or upload.status != "complete" or upload.scan_status != "clean" or upload.project_id != document.project_id:
        raise AppError(409, "UPLOAD_NOT_READY", "A completed upload from this project is required")
    if payload.status in {"current", "approved"}:
        superseded_ids = list(
            (
                await session.scalars(
                    select(DocumentRevision.id).where(
                        DocumentRevision.document_id == document.id,
                        DocumentRevision.status.in_(["current", "approved"]),
                    )
                )
            ).all()
        )
        await session.execute(
            update(DocumentRevision)
            .where(DocumentRevision.document_id == document.id, DocumentRevision.status.in_(["current", "approved"]))
            .values(status="superseded")
        )
        if superseded_ids:
            await session.execute(
                delete(SearchChunk).where(
                    SearchChunk.source_type == "document_revision",
                    SearchChunk.source_id.in_(superseded_ids),
                )
            )
    revision = DocumentRevision(
        document_id=document.id,
        upload_id=upload.id,
        revision=payload.revision,
        issue_date=payload.issue_date,
        status=payload.status,
        storage_key=upload.object_key,
        content_type=upload.content_type,
        size=upload.actual_size or upload.expected_size,
        sha256=upload.sha256 or "",
        sheet_number=payload.sheet_number,
        metadata_json=payload.metadata_json,
    )
    session.add(revision)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "DOCUMENT_REVISION_CONFLICT",
            "Another active or identically named revision already exists",
        ) from exc
    job = None
    if payload.process:
        job = Job(
            organization_id=document.organization_id,
            project_id=document.project_id,
            kind="document.ingest",
            input_json={"revision_id": revision.id},
            created_by=user.id,
        )
        session.add(job)
    audit(session, action="DOCUMENT_REVISION_CREATED", resource_type="document_revision", resource_id=revision.id, actor_user_id=user.id, organization_id=document.organization_id, project_id=document.project_id, details={"revision": revision.revision, "status": revision.status}, request_id=request.state.request_id)
    await session.commit()
    if job:
        await services(request).jobs.enqueue(job.id)
    return envelope(request, {"revision": RevisionCreate.model_validate(payload).model_dump(mode="json"), "revision_id": revision.id, "job_id": job.id if job else None})


@router.post("/v1/projects/{project_id}/evidence", status_code=201)
async def create_evidence(
    payload: EvidenceCreate,
    request: Request,
    project: Project = Depends(require_project("evidence:create")),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    upload = None
    if payload.upload_id:
        upload = await session.get(Upload, payload.upload_id)
        if upload is None or upload.status != "complete" or upload.scan_status != "clean" or upload.project_id != project.id:
            raise AppError(409, "UPLOAD_NOT_READY", "A completed upload from this project is required")
    evidence = Evidence(
        organization_id=project.organization_id,
        project_id=project.id,
        upload_id=upload.id if upload else None,
        storage_key=upload.object_key if upload else None,
        content_type=upload.content_type if upload else None,
        created_by=user.id,
        **payload.model_dump(exclude={"upload_id", "analyze"}),
    )
    session.add(evidence)
    await session.flush()
    job = None
    if payload.analyze:
        job = Job(
            organization_id=project.organization_id,
            project_id=project.id,
            kind="evidence.analyze",
            input_json={"evidence_id": evidence.id},
            created_by=user.id,
        )
        session.add(job)
    audit(session, action="EVIDENCE_CREATED", resource_type="evidence", resource_id=evidence.id, actor_user_id=user.id, organization_id=project.organization_id, project_id=project.id, request_id=request.state.request_id)
    await session.commit()
    if job:
        await services(request).jobs.enqueue(job.id)
    return envelope(request, {"evidence": EvidenceOut.model_validate(evidence).model_dump(mode="json"), "job_id": job.id if job else None})


@router.get("/v1/projects/{project_id}/evidence")
async def list_evidence(
    request: Request,
    kind: str | None = None,
    project: Project = Depends(require_project("evidence:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    statement = select(Evidence).where(Evidence.project_id == project.id).order_by(Evidence.created_at.desc())
    if kind:
        statement = statement.where(Evidence.kind == kind)
    rows = list((await session.scalars(statement)).all())
    return envelope(request, [EvidenceOut.model_validate(item) for item in rows])


@router.post("/v1/evidence/{evidence_id}/analyze", status_code=202)
async def analyze_evidence(
    evidence_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    evidence = await session.get(Evidence, evidence_id)
    if evidence is None:
        raise AppError(404, "EVIDENCE_NOT_FOUND", "Evidence was not found")
    await project_for_resource(session, evidence.project_id, user, "evidence:create")
    job = Job(organization_id=evidence.organization_id, project_id=evidence.project_id, kind="evidence.analyze", input_json={"evidence_id": evidence.id}, created_by=user.id)
    session.add(job)
    await session.commit()
    await services(request).jobs.enqueue(job.id)
    return envelope(request, JobOut.model_validate(job))


@router.post("/v1/projects/{project_id}/issues", status_code=201)
async def create_issue(
    payload: IssueCreate,
    request: Request,
    project: Project = Depends(require_project("issue:create")),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    number = payload.number
    if not number:
        await session.scalar(select(Project.id).where(Project.id == project.id).with_for_update())
        count = int(await session.scalar(select(func.count(Issue.id)).where(Issue.project_id == project.id)) or 0)
        number = f"BUI-{count + 1:04d}"
    if await session.scalar(select(Issue.id).where(Issue.project_id == project.id, Issue.number == number)):
        raise AppError(409, "ISSUE_NUMBER_TAKEN", "Issue number already exists in this project")
    issue = Issue(
        organization_id=project.organization_id,
        project_id=project.id,
        created_by=user.id,
        **payload.model_dump(
            exclude={"number", "evidence_ids", "revision_ids", "classification", "recommended_action"}
        ),
        number=number,
    )
    session.add(issue)
    await session.flush()
    for evidence_id in payload.evidence_ids:
        evidence = await session.get(Evidence, evidence_id)
        if evidence is None or evidence.project_id != project.id:
            raise AppError(409, "EVIDENCE_SCOPE_MISMATCH", "Linked evidence must belong to this project")
        session.add(IssueEvidence(issue_id=issue.id, evidence_id=evidence.id))
    for revision_id in payload.revision_ids:
        revision = await session.get(DocumentRevision, revision_id)
        document = await session.get(Document, revision.document_id) if revision else None
        if revision is None or document is None or document.project_id != project.id:
            raise AppError(409, "SOURCE_SCOPE_MISMATCH", "Linked source must belong to this project")
        session.add(IssueSource(issue_id=issue.id, revision_id=revision.id))
    audit(session, action="ISSUE_CREATED", resource_type="issue", resource_id=issue.id, actor_user_id=user.id, organization_id=project.organization_id, project_id=project.id, request_id=request.state.request_id)
    await session.commit()
    return envelope(request, IssueOut.model_validate(issue))


@router.get("/v1/projects/{project_id}/issues")
async def list_issues(
    request: Request,
    status: str | None = None,
    classification: str | None = None,
    project: Project = Depends(require_project("issue:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    statement = select(Issue).where(Issue.project_id == project.id).order_by(Issue.updated_at.desc())
    if status:
        statement = statement.where(Issue.status == status)
    if classification:
        statement = statement.where(Issue.classification == classification)
    rows = list((await session.scalars(statement)).all())
    return envelope(request, [IssueOut.model_validate(item) for item in rows])


@router.get("/v1/issues/{issue_id}")
async def get_issue(
    issue_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    issue = await session.get(Issue, issue_id)
    if issue is None:
        raise AppError(404, "ISSUE_NOT_FOUND", "Issue was not found")
    await project_for_resource(session, issue.project_id, user, "issue:read")
    evidence = list(
        (
            await session.scalars(
                select(Evidence).join(IssueEvidence, IssueEvidence.evidence_id == Evidence.id).where(IssueEvidence.issue_id == issue.id)
            )
        ).all()
    )
    sources = list((await session.scalars(select(IssueSource).where(IssueSource.issue_id == issue.id))).all())
    return envelope(request, {"issue": IssueOut.model_validate(issue).model_dump(mode="json"), "evidence": [EvidenceOut.model_validate(item).model_dump(mode="json") for item in evidence], "sources": [{"id": item.id, "revision_id": item.revision_id, "page": item.page, "quote": item.quote, "relationship_type": item.relationship_type} for item in sources]})


@router.patch("/v1/issues/{issue_id}")
async def update_issue(
    issue_id: str,
    payload: IssueUpdate,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    issue = await session.scalar(select(Issue).where(Issue.id == issue_id).with_for_update())
    if issue is None:
        raise AppError(404, "ISSUE_NOT_FOUND", "Issue was not found")
    await project_for_resource(session, issue.project_id, user, "issue:update")
    changes = payload.model_dump(exclude_unset=True)
    protected = {"status", "classification", "recommended_action", "evidence_sufficiency", "missing_evidence"}
    if protected & changes.keys():
        raise AppError(
            422,
            "VERIFICATION_FIELDS_READ_ONLY",
            "Verification, classification, and approval state can be changed only by their dedicated workflows",
            {"fields": sorted(protected & changes.keys())},
        )
    for field, value in changes.items():
        setattr(issue, field, value)
    issue.status = "draft"
    issue.verification_json = {}
    issue.approved_by = None
    issue.approved_at = None
    audit(session, action="ISSUE_UPDATED", resource_type="issue", resource_id=issue.id, actor_user_id=user.id, organization_id=issue.organization_id, project_id=issue.project_id, details=payload.model_dump(exclude_unset=True), request_id=request.state.request_id)
    await session.commit()
    return envelope(request, IssueOut.model_validate(issue))


@router.post("/v1/issues/{issue_id}/evidence", status_code=201)
async def link_issue_evidence(
    issue_id: str,
    payload: IssueLinkEvidenceIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    issue = await session.scalar(select(Issue).where(Issue.id == issue_id).with_for_update())
    evidence = await session.get(Evidence, payload.evidence_id)
    if issue is None or evidence is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Issue or evidence was not found")
    await project_for_resource(session, issue.project_id, user, "issue:update")
    if evidence.project_id != issue.project_id:
        raise AppError(409, "EVIDENCE_SCOPE_MISMATCH", "Evidence belongs to a different project")
    link = await session.get(IssueEvidence, (issue.id, evidence.id))
    if link is None:
        link = IssueEvidence(issue_id=issue.id, evidence_id=evidence.id, relationship_type=payload.relationship_type)
        session.add(link)
    issue.status = "draft"
    issue.verification_json = {}
    issue.approved_by = None
    issue.approved_at = None
    await session.commit()
    return envelope(request, {"issue_id": issue.id, "evidence_id": evidence.id})


@router.post("/v1/issues/{issue_id}/sources", status_code=201)
async def link_issue_source(
    issue_id: str,
    payload: IssueLinkSourceIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    issue = await session.scalar(select(Issue).where(Issue.id == issue_id).with_for_update())
    revision = await session.get(DocumentRevision, payload.revision_id)
    document = await session.get(Document, revision.document_id) if revision else None
    if issue is None or revision is None or document is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Issue or source revision was not found")
    await project_for_resource(session, issue.project_id, user, "issue:update")
    if document.project_id != issue.project_id:
        raise AppError(409, "SOURCE_SCOPE_MISMATCH", "Source belongs to a different project")
    link = IssueSource(issue_id=issue.id, **payload.model_dump())
    session.add(link)
    issue.status = "draft"
    issue.verification_json = {}
    issue.approved_by = None
    issue.approved_at = None
    await session.commit()
    return envelope(request, {"id": link.id, "issue_id": issue.id, "revision_id": revision.id})


@router.post("/v1/issues/{issue_id}/analyze", status_code=202)
async def analyze_issue_route(
    issue_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    issue = await session.scalar(select(Issue).where(Issue.id == issue_id).with_for_update())
    if issue is None:
        raise AppError(404, "ISSUE_NOT_FOUND", "Issue was not found")
    await project_for_resource(session, issue.project_id, user, "issue:update")
    job = Job(organization_id=issue.organization_id, project_id=issue.project_id, kind="issue.analyze", input_json={"issue_id": issue.id}, created_by=user.id)
    session.add(job)
    await session.commit()
    await services(request).jobs.enqueue(job.id)
    return envelope(request, JobOut.model_validate(job))


@router.post("/v1/issues/{issue_id}/approve")
async def approve_issue(
    issue_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    issue = await session.scalar(select(Issue).where(Issue.id == issue_id).with_for_update())
    if issue is None:
        raise AppError(404, "ISSUE_NOT_FOUND", "Issue was not found")
    await project_for_resource(session, issue.project_id, user, "issue:review")
    await verify_issue(session, issue)
    blockers = approval_blockers(issue)
    if blockers:
        raise AppError(
            409,
            "ISSUE_APPROVAL_BLOCKED",
            "Issue must have current, relevant, sufficient evidence before approval",
            {"reasons": blockers},
        )
    issue.status = "approved"
    issue.approved_by = user.id
    issue.approved_at = utcnow()
    audit(session, action="ISSUE_APPROVED", resource_type="issue", resource_id=issue.id, actor_user_id=user.id, organization_id=issue.organization_id, project_id=issue.project_id, request_id=request.state.request_id)
    await session.commit()
    return envelope(request, IssueOut.model_validate(issue))


@router.post("/v1/issues/{issue_id}/reports", status_code=201)
async def create_report(
    issue_id: str,
    payload: ReportCreate,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    issue = await session.get(Issue, issue_id)
    if issue is None:
        raise AppError(404, "ISSUE_NOT_FOUND", "Issue was not found")
    await project_for_resource(session, issue.project_id, user, "report:create")
    if payload.approve:
        await project_for_resource(session, issue.project_id, user, "report:approve")
    report = await services(request).reports.generate(
        session,
        issue=issue,
        kind=payload.kind,
        title=payload.title or issue.title,
        user_id=user.id,
        approve=payload.approve,
    )
    audit(session, action="REPORT_GENERATED", resource_type="report", resource_id=report.id, actor_user_id=user.id, organization_id=report.organization_id, project_id=report.project_id, details={"kind": report.kind, "version": report.version}, request_id=request.state.request_id)
    await session.commit()
    return envelope(request, ReportOut.model_validate(report))


@router.post("/v1/reports/{report_id}/approve", status_code=201)
async def approve_report(
    report_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    source = await services(request).reports.load_with_artifacts(session, report_id)
    if source is None:
        raise AppError(404, "REPORT_NOT_FOUND", "Report was not found")
    await project_for_resource(session, source.project_id, user, "report:approve")
    if source.status == "approved":
        raise AppError(409, "REPORT_ALREADY_APPROVED", "Report is already approved")
    issue = await session.get(Issue, source.issue_id) if source.issue_id else None
    if issue is None:
        raise AppError(409, "REPORT_ISSUE_MISSING", "Report issue was not found")
    approved = await services(request).reports.generate(
        session,
        issue=issue,
        kind=source.kind,
        title=source.title,
        user_id=user.id,
        approve=True,
    )
    source.status = "superseded"
    audit(
        session,
        action="REPORT_APPROVED",
        resource_type="report",
        resource_id=approved.id,
        actor_user_id=user.id,
        organization_id=approved.organization_id,
        project_id=approved.project_id,
        details={
            "source_report_id": source.id,
            "kind": approved.kind,
            "version": approved.version,
        },
        request_id=request.state.request_id,
    )
    await session.commit()
    return envelope(request, ReportOut.model_validate(approved))


@router.get("/v1/reports/{report_id}")
async def get_report(
    report_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    report = await services(request).reports.load_with_artifacts(session, report_id)
    if report is None:
        raise AppError(404, "REPORT_NOT_FOUND", "Report was not found")
    await project_for_resource(session, report.project_id, user, "report:read")
    download_url = await services(request).storage.create_download_url(report.storage_key, 300)
    artifacts = []
    for artifact in sorted(report.artifacts, key=lambda item: item.format):
        artifacts.append(
            {
                **ReportArtifactOut.model_validate(artifact).model_dump(mode="json"),
                "download_url": await services(request).storage.create_download_url(
                    artifact.storage_key, 300
                ),
            }
        )
    return envelope(
        request,
        {
            "report": ReportOut.model_validate(report).model_dump(mode="json"),
            "download_url": download_url,
            "artifacts": artifacts,
        },
    )


@router.get("/v1/projects/{project_id}/reports")
async def list_reports(
    request: Request,
    project: Project = Depends(require_project("report:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = list(
        (
            await session.scalars(
                select(Report)
                .options(selectinload(Report.artifacts))
                .where(Report.project_id == project.id)
                .order_by(Report.created_at.desc())
            )
        ).all()
    )
    return envelope(request, [ReportOut.model_validate(item) for item in rows])


@router.get("/v1/projects/{project_id}/audit")
async def project_audit(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = None,
    project: Project = Depends(require_project("audit:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    statement = select(AuditLog).where(AuditLog.project_id == project.id).order_by(AuditLog.created_at.desc())
    count_statement = select(func.count(AuditLog.id)).where(AuditLog.project_id == project.id)
    if action:
        statement = statement.where(AuditLog.action == action)
        count_statement = count_statement.where(AuditLog.action == action)
    total = int(await session.scalar(count_statement) or 0)
    rows = list((await session.scalars(statement.offset(offset).limit(limit))).all())
    data = [
        {
            "id": item.id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "actor_user_id": item.actor_user_id,
            "details": item.details_json,
            "request_id": item.request_id,
            "created_at": item.created_at.isoformat(),
        }
        for item in rows
    ]
    return envelope(request, data, total=total, limit=limit, offset=offset)


@router.post("/v1/projects/{project_id}/search")
async def search_project(
    payload: SearchIn,
    request: Request,
    project: Project = Depends(require_project("search:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    external_allowed = bool(project.metadata_json.get("external_ai_allowed", False))
    hits, mode = await services(request).search.search(session, project_id=project.id, organization_id=project.organization_id, query=payload.query, limit=payload.limit, source_types=payload.source_types, external_ai_allowed=external_allowed)
    return envelope(request, SearchOut(query=payload.query, hits=hits, mode=mode))


@router.post("/v1/projects/{project_id}/ask")
async def ask_project(
    payload: AskIn,
    request: Request,
    project: Project = Depends(require_project("search:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    external_allowed = bool(project.metadata_json.get("external_ai_allowed", False))
    hits, _ = await services(request).search.search(session, project_id=project.id, organization_id=project.organization_id, query=payload.query, limit=payload.limit, source_types=payload.source_types, external_ai_allowed=external_allowed)
    answer, cited, provider = await services(request).ai.grounded_answer(payload.query, [item.content for item in hits], external_allowed=external_allowed)
    citations = [
        Citation(index=index, source_type=hits[index - 1].source_type, source_id=hits[index - 1].source_id, chunk_id=hits[index - 1].chunk_id, excerpt=hits[index - 1].content[:300], page=hits[index - 1].page)
        for index in cited
    ]
    output = AskOut(answer=answer, citations=citations, provider=provider, model=services(request).ai.settings.openai_model if provider == "openai" else None)
    return envelope(request, output)


@router.get("/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await session.get(Job, job_id)
    if job is None:
        raise AppError(404, "JOB_NOT_FOUND", "Job was not found")
    if job.project_id:
        await project_for_resource(session, job.project_id, user, "project:read")
    else:
        await ensure_org_access(session, user.id, job.organization_id)
    return envelope(request, JobOut.model_validate(job))


@router.post("/v1/projects/{project_id}/spatial-scenes/generate", status_code=202)
async def generate_spatial_scene(
    payload: SpatialGenerateIn,
    request: Request,
    project: Project = Depends(require_project("spatial:create")),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    revision = await session.get(DocumentRevision, payload.source_revision_id)
    document = await session.get(Document, revision.document_id) if revision else None
    if revision is None or document is None or document.project_id != project.id:
        raise AppError(409, "SOURCE_SCOPE_MISMATCH", "Spatial source revision must belong to this project")
    job = Job(
        organization_id=project.organization_id,
        project_id=project.id,
        kind="spatial.generate",
        input_json={"source_revision_id": revision.id, "options": payload.options},
        created_by=user.id,
    )
    session.add(job)
    await session.commit()
    await services(request).jobs.enqueue(job.id)
    return envelope(request, JobOut.model_validate(job))


@router.get("/v1/projects/{project_id}/spatial-scenes")
async def list_spatial_scenes(
    request: Request,
    project: Project = Depends(require_project("project:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = list((await session.scalars(select(SpatialScene).where(SpatialScene.project_id == project.id).order_by(SpatialScene.created_at.desc()))).all())
    return envelope(request, [SpatialSceneOut.model_validate(item) for item in rows])


@router.get("/v1/projects/{project_id}/plan-graphs")
async def list_plan_graphs(
    request: Request,
    project: Project = Depends(require_project("project:read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = list(
        (
            await session.scalars(
                select(PlanGraph)
                .where(PlanGraph.project_id == project.id)
                .order_by(PlanGraph.created_at.desc())
            )
        ).all()
    )
    return envelope(request, [PlanGraphOut.model_validate(item) for item in rows])


@router.post("/v1/spatial-scenes/{scene_id}/approve")
async def approve_spatial_scene(
    scene_id: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    scene = await session.scalar(
        select(SpatialScene).where(SpatialScene.id == scene_id).with_for_update()
    )
    if scene is None:
        raise AppError(404, "SPATIAL_SCENE_NOT_FOUND", "Spatial scene was not found")
    await project_for_resource(session, scene.project_id, user, "spatial:create")
    await session.scalar(
        select(DocumentRevision)
        .where(DocumentRevision.id == scene.source_revision_id)
        .with_for_update()
    )
    graph = await session.scalar(
        select(PlanGraph).where(PlanGraph.id == scene.plan_graph_id).with_for_update()
    )
    if graph is None:
        raise AppError(409, "PLAN_GRAPH_MISSING", "Spatial scene plan graph is missing")
    reasons = official_use_gate(graph, scene)
    if reasons:
        raise AppError(409, "SPATIAL_REVIEW_BLOCKED", "Spatial output cannot be approved for official use", {"reasons": reasons})
    await session.execute(
        update(SpatialScene)
        .where(
            SpatialScene.project_id == scene.project_id,
            SpatialScene.source_revision_id == scene.source_revision_id,
            SpatialScene.status == "approved",
            SpatialScene.id != scene.id,
        )
        .values(status="superseded")
    )
    await session.execute(
        update(PlanGraph)
        .where(
            PlanGraph.project_id == graph.project_id,
            PlanGraph.source_revision_id == graph.source_revision_id,
            PlanGraph.status == "approved",
            PlanGraph.id != graph.id,
        )
        .values(status="superseded")
    )
    scene.status = "approved"
    graph.status = "approved"
    audit(
        session,
        action="SPATIAL_SCENE_APPROVED",
        resource_type="spatial_scene",
        resource_id=scene.id,
        actor_user_id=user.id,
        organization_id=scene.organization_id,
        project_id=scene.project_id,
        details={"plan_graph_id": graph.id, "source_revision_id": scene.source_revision_id},
        request_id=request.state.request_id,
    )
    await session.commit()
    return envelope(request, SpatialSceneOut.model_validate(scene))


@router.post("/v1/spatial-scenes/{scene_id}/review", status_code=201)
async def attest_spatial_scene(
    scene_id: str,
    payload: SpatialReviewIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    source_scene = await session.scalar(
        select(SpatialScene).where(SpatialScene.id == scene_id).with_for_update()
    )
    if source_scene is None:
        raise AppError(404, "SPATIAL_SCENE_NOT_FOUND", "Spatial scene was not found")
    await project_for_resource(session, source_scene.project_id, user, "spatial:create")
    source_revision = await session.scalar(
        select(DocumentRevision)
        .where(DocumentRevision.id == source_scene.source_revision_id)
        .with_for_update()
    )
    if source_revision is None:
        raise AppError(409, "SOURCE_REVISION_MISSING", "Spatial source revision is missing")
    source_graph = await session.get(PlanGraph, source_scene.plan_graph_id)
    if source_graph is None:
        raise AppError(409, "PLAN_GRAPH_MISSING", "Spatial scene plan graph is missing")
    canonical = source_graph.graph_json or {}
    known_ids = {
        str(item.get("id"))
        for collection in ("rooms", "walls", "openings", "fixtures")
        for item in canonical.get(collection, [])
        if isinstance(item, dict) and item.get("id")
    }
    unknown = sorted(set(payload.locked_object_ids) - known_ids)
    if unknown:
        raise AppError(422, "UNKNOWN_SPATIAL_OBJECT", "Cannot lock unknown spatial objects", {"object_ids": unknown})
    graph_version = int(
        await session.scalar(
            select(func.max(PlanGraph.version)).where(
                PlanGraph.project_id == source_graph.project_id,
                PlanGraph.source_revision_id == source_graph.source_revision_id,
            )
        )
        or 0
    ) + 1
    scene_version = int(
        await session.scalar(
            select(func.max(SpatialScene.version)).where(
                SpatialScene.project_id == source_scene.project_id,
                SpatialScene.source_revision_id == source_scene.source_revision_id,
            )
        )
        or 0
    ) + 1
    graph = PlanGraph(
        organization_id=source_graph.organization_id,
        project_id=source_graph.project_id,
        source_revision_id=source_graph.source_revision_id,
        version=graph_version,
        status="reviewed",
        graph_json=canonical,
        scale_json=source_graph.scale_json,
        source_hash=source_graph.source_hash,
        pipeline_version=source_graph.pipeline_version,
        review_json={
            **payload.model_dump(),
            "source_plan_graph_id": source_graph.id,
            "immutable_geometry": True,
        },
        reviewer_id=user.id,
        reviewed_at=utcnow(),
        created_by=user.id,
    )
    session.add(graph)
    await session.flush()
    scene = SpatialScene(
        organization_id=source_scene.organization_id,
        project_id=source_scene.project_id,
        source_revision_id=source_scene.source_revision_id,
        plan_graph_id=graph.id,
        version=scene_version,
        status="reviewed",
        glb_storage_key=source_scene.glb_storage_key,
        semantic_storage_key=source_scene.semantic_storage_key,
        source_mapping_storage_key=source_scene.source_mapping_storage_key,
        confidence_json={
            **source_scene.confidence_json,
            "reviewer_attestation": graph.review_json,
            "official_use_blocked": False,
        },
        created_by=user.id,
    )
    session.add(scene)
    await session.flush()
    reasons = official_use_gate(graph, scene)
    if reasons:
        raise AppError(409, "SPATIAL_REVIEW_BLOCKED", "Blocking parser errors cannot be overridden by attestation", {"reasons": reasons})
    await session.execute(
        update(SpatialScene)
        .where(
            SpatialScene.project_id == scene.project_id,
            SpatialScene.source_revision_id == scene.source_revision_id,
            SpatialScene.status == "approved",
            SpatialScene.id.not_in([source_scene.id, scene.id]),
        )
        .values(status="superseded")
    )
    await session.execute(
        update(PlanGraph)
        .where(
            PlanGraph.project_id == graph.project_id,
            PlanGraph.source_revision_id == graph.source_revision_id,
            PlanGraph.status == "approved",
            PlanGraph.id.not_in([source_graph.id, graph.id]),
        )
        .values(status="superseded")
    )
    source_scene.status = "superseded"
    source_graph.status = "superseded"
    scene.status = "approved"
    graph.status = "approved"
    audit(
        session,
        action="SPATIAL_REVIEW_ATTESTED",
        resource_type="spatial_scene",
        resource_id=scene.id,
        actor_user_id=user.id,
        organization_id=scene.organization_id,
        project_id=scene.project_id,
        details={"source_scene_id": source_scene.id, "plan_graph_id": graph.id},
        request_id=request.state.request_id,
    )
    await session.commit()
    return envelope(
        request,
        {"scene": SpatialSceneOut.model_validate(scene).model_dump(mode="json"), "plan_graph": PlanGraphOut.model_validate(graph).model_dump(mode="json")},
    )


@router.get("/v1/files/{object_key:path}")
async def download_file(
    object_key: str,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    project_id = await session.scalar(select(Evidence.project_id).where(Evidence.storage_key == object_key))
    if not project_id:
        project_id = await session.scalar(select(Report.project_id).where(Report.storage_key == object_key))
    if not project_id:
        project_id = await session.scalar(
            select(ReportArtifact.project_id).where(
                ReportArtifact.storage_key == object_key
            )
        )
    if not project_id:
        document = await session.scalar(
            select(Document).join(DocumentRevision).where(DocumentRevision.storage_key == object_key)
        )
        project_id = document.project_id if document else None
    if not project_id:
        project_id = await session.scalar(
            select(SpatialScene.project_id).where(
                or_(
                    SpatialScene.glb_storage_key == object_key,
                    SpatialScene.semantic_storage_key == object_key,
                    SpatialScene.source_mapping_storage_key == object_key,
                )
            )
        )
    if not project_id:
        raise AppError(404, "FILE_NOT_FOUND", "File was not found")
    await project_for_resource(session, project_id, user, "project:read")
    if settings.storage_backend == "s3":
        return RedirectResponse(await services(request).storage.create_download_url(object_key, 300), status_code=307)
    data = await services(request).storage.read_bytes(object_key)
    content_type = "application/octet-stream"
    evidence = await session.scalar(select(Evidence).where(Evidence.storage_key == object_key))
    report = await session.scalar(select(Report).where(Report.storage_key == object_key))
    report_artifact = await session.scalar(
        select(ReportArtifact).where(ReportArtifact.storage_key == object_key)
    )
    content_type = (
        (evidence.content_type if evidence else None)
        or (report_artifact.content_type if report_artifact else None)
        or (report.content_type if report else None)
        or content_type
    )
    if object_key.endswith(".glb"):
        content_type = "model/gltf-binary"
    elif object_key.endswith(".json"):
        content_type = "application/json"
    filename = safe_display_filename(object_key.rsplit("/", 1)[-1])
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Cross-Origin-Resource-Policy": "same-site",
        },
    )
