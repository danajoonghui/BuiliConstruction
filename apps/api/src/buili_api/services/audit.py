from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog


def audit(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    actor_user_id: str | None,
    resource_id: str | None = None,
    organization_id: str | None = None,
    project_id: str | None = None,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
) -> None:
    session.add(
        AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            project_id=project_id,
            details_json=details or {},
            request_id=request_id,
            ip_address=ip_address,
        )
    )
