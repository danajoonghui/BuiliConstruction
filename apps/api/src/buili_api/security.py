from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
from datetime import timedelta
from typing import Any

import httpx
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import Settings
from .core.errors import AppError
from .models import AuthSession, Organization, OrganizationMember, User, new_id, utcnow

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def slugify(value: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:96]
    return candidate or f"organization-{secrets.token_hex(4)}"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(user: User, settings: Settings) -> tuple[str, int]:
    now = utcnow()
    ttl_seconds = settings.access_token_minutes * 60
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.display_name,
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "jti": secrets.token_urlsafe(16),
        "ver": user.auth_version,
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256"), ttl_seconds


async def issue_token_pair(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    rotated_from: AuthSession | None = None,
) -> tuple[str, str, int]:
    access_token, expires_in = create_access_token(user, settings)
    refresh_token = secrets.token_urlsafe(64)
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=token_hash(refresh_token),
        family_id=rotated_from.family_id if rotated_from else new_id("fam"),
        parent_session_id=rotated_from.id if rotated_from else None,
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
    )
    session.add(auth_session)
    await session.flush()
    if rotated_from:
        rotated_from.rotated_at = utcnow()
        rotated_from.revoked_at = rotated_from.rotated_at
        rotated_from.revocation_reason = "rotated"
        rotated_from.replaced_by_session_id = auth_session.id
    return access_token, refresh_token, expires_in


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "sub", "typ", "ver"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError(401, "INVALID_TOKEN", "Access token is invalid or expired") from exc
    if payload.get("typ") != "access":
        raise AppError(401, "INVALID_TOKEN_TYPE", "Expected an access token")
    return payload


class OIDCVerifier:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def verify(self, id_token: str) -> dict[str, Any]:
        if not self.settings.oidc_client_id:
            raise AppError(503, "OIDC_NOT_CONFIGURED", "Google/OIDC login is not configured")
        issuer = self.settings.oidc_issuer.rstrip("/")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{issuer}/.well-known/openid-configuration")
            response.raise_for_status()
            discovery = response.json()
        jwks_uri = discovery["jwks_uri"]

        def _decode() -> dict[str, Any]:
            signing_key = PyJWKClient(jwks_uri, cache_keys=True).get_signing_key_from_jwt(id_token)
            return jwt.decode(
                id_token,
                signing_key.key,
                algorithms=discovery.get("id_token_signing_alg_values_supported", ["RS256"]),
                audience=self.settings.oidc_client_id,
                issuer=discovery.get("issuer", issuer),
                options={"require": ["exp", "iat", "sub"]},
            )

        try:
            claims = await asyncio.to_thread(_decode)
        except (jwt.PyJWTError, httpx.HTTPError) as exc:
            raise AppError(401, "OIDC_TOKEN_INVALID", "The identity provider token could not be verified") from exc
        if not claims.get("email") or claims.get("email_verified") is False:
            raise AppError(401, "OIDC_EMAIL_UNVERIFIED", "A verified email is required")
        return claims


async def provision_oidc_user(
    session: AsyncSession, claims: dict[str, Any], settings: Settings, organization_name: str | None
) -> User:
    issuer = str(claims.get("iss", settings.oidc_issuer))
    subject = str(claims["sub"])
    user = await session.scalar(select(User).where(User.oidc_issuer == issuer, User.oidc_subject == subject))
    email = normalize_email(str(claims["email"]))
    if user is None:
        existing_email = await session.scalar(select(User).where(User.email == email))
        if existing_email is not None:
            raise AppError(
                409,
                "OIDC_LINK_REQUIRED",
                "An account already exists for this email. Sign in with its existing method and link Google explicitly.",
            )
        user = User(
            email=email,
            display_name=str(claims.get("name") or email.split("@", 1)[0]),
            oidc_issuer=issuer,
            oidc_subject=subject,
            avatar_url=claims.get("picture"),
            email_verified=True,
        )
        session.add(user)
        await session.flush()
    has_membership = await session.scalar(select(OrganizationMember.id).where(OrganizationMember.user_id == user.id))
    if not has_membership:
        name = organization_name or f"{user.display_name}'s team"
        slug = slugify(name)
        if await session.scalar(select(Organization.id).where(Organization.slug == slug)):
            slug = f"{slug}-{secrets.token_hex(3)}"
        organization = Organization(name=name, slug=slug)
        session.add(organization)
        await session.flush()
        session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    await session.flush()
    return user
