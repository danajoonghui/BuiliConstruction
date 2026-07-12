from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import Settings, get_settings
from .core.errors import AppError
from .db import get_session
from .models import OrganizationMember, Project, ProjectMember, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)

ORG_RANK = {"member": 10, "admin": 80, "owner": 100}
PROJECT_PERMISSIONS = {
    "viewer": {"project:read", "document:read", "evidence:read", "issue:read", "report:read", "search:read"},
    "field_user": {"project:read", "document:read", "evidence:read", "evidence:create", "issue:read", "issue:create", "report:read", "search:read"},
    "reviewer": {"project:read", "document:read", "evidence:read", "issue:read", "issue:update", "issue:review", "report:read", "search:read"},
    "manager": {"project:read", "project:update", "document:read", "document:create", "document:approve", "evidence:read", "evidence:create", "issue:read", "issue:create", "issue:update", "issue:review", "report:read", "report:create", "report:approve", "search:read", "spatial:create", "audit:read"},
    "admin": {"*"},
}


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    raw_token = credentials.credentials if credentials else request.cookies.get("buili_access")
    if not raw_token:
        raise AppError(401, "AUTHENTICATION_REQUIRED", "Bearer authentication is required")
    payload = decode_access_token(raw_token, settings)
    user = await session.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise AppError(401, "USER_UNAVAILABLE", "The authenticated user is unavailable")
    if int(payload.get("ver", -1)) != user.auth_version:
        raise AppError(401, "TOKEN_REVOKED", "The access token has been revoked")
    if settings.require_email_verification and not user.email_verified:
        raise AppError(403, "EMAIL_NOT_VERIFIED", "Verify your email before accessing BUILI")
    if not settings.is_sqlite:
        await session.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), {"user_id": user.id})
    return user


async def ensure_org_access(session: AsyncSession, user_id: str, organization_id: str, minimum_role: str = "member") -> OrganizationMember:
    membership = await session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if membership is None or ORG_RANK.get(membership.role, 0) < ORG_RANK[minimum_role]:
        raise AppError(403, "ORGANIZATION_FORBIDDEN", "You do not have access to this organization")
    return membership


async def ensure_project_permission(session: AsyncSession, user_id: str, project: Project, permission: str) -> str:
    org_membership = await session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == project.organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if org_membership and org_membership.role in {"owner", "admin"}:
        return "admin"
    project_role = await session.scalar(
        select(ProjectMember.role).where(ProjectMember.project_id == project.id, ProjectMember.user_id == user_id)
    )
    permissions = PROJECT_PERMISSIONS.get(project_role or "", set())
    if "*" not in permissions and permission not in permissions:
        raise AppError(403, "PROJECT_FORBIDDEN", f"Missing project permission: {permission}")
    return project_role or ""


def require_project(permission: str) -> Callable:
    async def dependency(
        request: Request,
        user: User = Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ) -> Project:
        project_id = request.path_params.get("project_id")
        if not project_id:
            raise AppError(500, "PROJECT_DEPENDENCY_MISCONFIGURED", "Project route parameter is missing")
        project = await session.get(Project, project_id)
        if project is None:
            raise AppError(404, "PROJECT_NOT_FOUND", "Project was not found")
        await ensure_project_permission(session, user.id, project, permission)
        return project
    return dependency


async def project_for_resource(session: AsyncSession, project_id: str, user: User, permission: str) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise AppError(404, "PROJECT_NOT_FOUND", "Project was not found")
    await ensure_project_permission(session, user.id, project, permission)
    return project
