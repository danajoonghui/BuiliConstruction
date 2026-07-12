from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from buili_api.core.config import Settings, get_settings
from buili_api.db import SessionFactory
from buili_api.main import create_app
from buili_api.models import User
from buili_api.routes import create_one_time_token


def test_production_rejects_short_secrets_and_insecure_public_urls():
    common = {
        "_env_file": None,
        "BUILI_ENVIRONMENT": "production",
        "BUILI_AUTO_CREATE_SCHEMA": "false",
        "BUILI_COOKIE_SECURE": "true",
        "BUILI_DEMO_MODE": "false",
        "BUILI_EMAIL_BACKEND": "disabled",
        "BUILI_MALWARE_SCANNER_BACKEND": "clamav",
        "BUILI_CORS_ORIGINS": "https://app.builiconstruction.com",
        "BUILI_DATABASE_URL": "postgresql+asyncpg://api:secret@db.internal/buili",
        "BUILI_STORAGE_BACKEND": "s3",
        "BUILI_S3_BUCKET": "buili-production-objects",
        "BUILI_JOB_BACKEND": "sqs",
        "BUILI_SQS_QUEUE_URL": "https://sqs.us-west-1.amazonaws.com/123456789012/buili-jobs",
    }
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            **common,
            BUILI_JWT_SECRET="too-short",
            BUILI_ORIGIN_VERIFY_SECRET="origin-secret-that-is-long-enough-123",
            BUILI_PUBLIC_API_URL="https://api.builiconstruction.com",
            BUILI_FRONTEND_URL="https://app.builiconstruction.com",
        )
    with pytest.raises(ValidationError, match="ORIGIN_VERIFY_SECRET"):
        Settings(
            **common,
            BUILI_JWT_SECRET="jwt-secret-that-is-long-enough-for-prod",
            BUILI_ORIGIN_VERIFY_SECRET="too-short",
            BUILI_PUBLIC_API_URL="https://api.builiconstruction.com",
            BUILI_FRONTEND_URL="https://app.builiconstruction.com",
        )
    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(
            **common,
            BUILI_JWT_SECRET="jwt-secret-that-is-long-enough-for-prod",
            BUILI_ORIGIN_VERIFY_SECRET="origin-secret-that-is-long-enough-123",
            BUILI_PUBLIC_API_URL="http://api.internal",
            BUILI_FRONTEND_URL="https://app.builiconstruction.com",
        )


def test_production_rejects_placeholder_secrets_and_local_durability_backends():
    secure = {
        "_env_file": None,
        "BUILI_ENVIRONMENT": "production",
        "BUILI_AUTO_CREATE_SCHEMA": "false",
        "BUILI_COOKIE_SECURE": "true",
        "BUILI_DEMO_MODE": "false",
        "BUILI_EMAIL_BACKEND": "disabled",
        "BUILI_MALWARE_SCANNER_BACKEND": "clamav",
        "BUILI_CORS_ORIGINS": "https://app.builiconstruction.com",
        "BUILI_PUBLIC_API_URL": "https://api.builiconstruction.com",
        "BUILI_FRONTEND_URL": "https://app.builiconstruction.com",
        "BUILI_ORIGIN_VERIFY_SECRET": "origin-secret-that-is-long-enough-123",
    }
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            **secure,
            BUILI_JWT_SECRET="replace-with-at-least-32-random-characters",
            BUILI_DATABASE_URL="postgresql+asyncpg://api:secret@db.internal/buili",
            BUILI_STORAGE_BACKEND="s3",
            BUILI_S3_BUCKET="buili-production-objects",
            BUILI_JOB_BACKEND="sqs",
            BUILI_SQS_QUEUE_URL="https://sqs.us-west-1.amazonaws.com/123456789012/buili-jobs",
        )

    durable = {
        **secure,
        "BUILI_JWT_SECRET": "jwt-secret-that-is-long-enough-for-production",
    }
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(**durable)
    with pytest.raises(ValidationError, match="STORAGE_BACKEND=s3"):
        Settings(
            **durable,
            BUILI_DATABASE_URL="postgresql+asyncpg://api:secret@db.internal/buili",
        )
    with pytest.raises(ValidationError, match="JOB_BACKEND=sqs"):
        Settings(
            **durable,
            BUILI_DATABASE_URL="postgresql+asyncpg://api:secret@db.internal/buili",
            BUILI_STORAGE_BACKEND="s3",
            BUILI_S3_BUCKET="buili-production-objects",
        )


def test_external_ai_requires_a_key_and_explicit_model_pin():
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(_env_file=None, BUILI_EXTERNAL_AI_ENABLED="true", OPENAI_MODEL="pinned-model")
    with pytest.raises(ValidationError, match="OPENAI_MODEL"):
        Settings(
            _env_file=None,
            BUILI_EXTERNAL_AI_ENABLED="true",
            OPENAI_API_KEY="test-provider-key-that-is-never-used",
        )


def verification_settings() -> Settings:
    return Settings(
        _env_file=None,
        BUILI_ENVIRONMENT="test",
        BUILI_DATABASE_URL=get_settings().database_url,
        BUILI_STORAGE_BACKEND="local",
        BUILI_STORAGE_ROOT=str(get_settings().storage_root),
        BUILI_JWT_SECRET=get_settings().jwt_secret.get_secret_value(),
        BUILI_PUBLIC_API_URL="http://testserver",
        BUILI_REQUIRE_EMAIL_VERIFICATION="true",
        BUILI_EMAIL_BACKEND="disabled",
        BUILI_MALWARE_SCANNER_BACKEND="test",
        BUILI_DEMO_MODE="false",
    )


async def test_required_verification_issues_no_session_and_blocks_existing_tokens(client):
    settings = verification_settings()
    verification_app = create_app(settings)
    verification_app.dependency_overrides[get_settings] = lambda: settings
    transport = httpx.ASGITransport(app=verification_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as secured:
        pending = await secured.post(
            "/v1/auth/signup?transport=body",
            json={
                "email": "pending-verification@example.com",
                "password": "PendingPassword123!",
                "display_name": "Pending User",
                "organization_name": "Pending Team",
            },
        )
        assert pending.status_code == 201, pending.text
        assert pending.json()["data"]["verification_required"] is True
        assert pending.json()["data"]["access_token"] is None
        assert pending.json()["data"]["refresh_token"] is None
        assert "buili_access" not in secured.cookies
        assert (
            await secured.post(
                "/v1/auth/login?transport=body",
                json={"email": "pending-verification@example.com", "password": "PendingPassword123!"},
            )
        ).status_code == 403

        legacy = await client.post(
            "/v1/auth/signup?transport=body",
            json={
                "email": "legacy-unverified@example.com",
                "password": "LegacyPassword123!",
                "display_name": "Legacy User",
                "organization_name": "Legacy Team",
            },
        )
        tokens = legacy.json()["data"]
        blocked_access = await secured.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        assert blocked_access.status_code == 403
        blocked_refresh = await secured.post(
            "/v1/auth/refresh?transport=body", json={"refresh_token": tokens["refresh_token"]}
        )
        assert blocked_refresh.status_code == 403


async def test_refresh_rotation_detects_replay_and_revokes_family(client):
    signup = await client.post(
        "/v1/auth/signup?transport=body",
        json={
            "email": "refresh-replay@example.com",
            "password": "RefreshPassword123!",
            "display_name": "Refresh User",
            "organization_name": "Refresh Team",
        },
    )
    first = signup.json()["data"]
    native_headers = {"Authorization": f"Bearer {first['access_token']}"}
    rotated = await client.post(
        "/v1/auth/refresh?transport=body",
        headers=native_headers,
        json={"refresh_token": first["refresh_token"]},
    )
    assert rotated.status_code == 200, rotated.text
    second = rotated.json()["data"]

    replay = await client.post(
        "/v1/auth/refresh?transport=body",
        headers=native_headers,
        json={"refresh_token": first["refresh_token"]},
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "REFRESH_TOKEN_REUSE_DETECTED"

    family_revoked = await client.post(
        "/v1/auth/refresh?transport=body",
        headers={"Authorization": f"Bearer {second['access_token']}"},
        json={"refresh_token": second["refresh_token"]},
    )
    assert family_revoked.status_code == 401
    access_revoked = await client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"}
    )
    assert access_revoked.status_code == 401
    assert access_revoked.json()["error"]["code"] == "TOKEN_REVOKED"


async def test_host_only_csrf_can_recover_after_access_expiry_but_requires_session_cookie(client):
    login = await client.post(
        "/v1/auth/login",
        json={"email": "jordan@demo.builiconstruction.com", "password": "ChangeMe-Demo-2026!"},
    )
    assert login.status_code == 200
    assert login.json()["data"]["csrf_token"]
    csrf_cookie = client.cookies.get("buili_csrf")
    refresh_cookie = client.cookies.get("buili_refresh")
    client.cookies.delete("buili_access")
    recovered = await client.get("/v1/auth/csrf")
    assert recovered.status_code == 200
    assert recovered.json()["data"]["csrf_token"] == csrf_cookie
    refreshed = await client.post(
        "/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_cookie},
    )
    assert refreshed.status_code == 200, refreshed.text
    assert client.cookies.get("buili_refresh") != refresh_cookie

    anonymous = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=client._transport.app, raise_app_exceptions=False),
        base_url="http://testserver",
    )
    async with anonymous:
        unavailable = await anonymous.get("/v1/auth/csrf")
        assert unavailable.status_code == 401
        assert unavailable.json()["error"]["code"] == "CSRF_TOKEN_UNAVAILABLE"


async def test_only_latest_reset_token_is_single_use(client):
    signup = await client.post(
        "/v1/auth/signup?transport=body",
        json={
            "email": "single-reset@example.com",
            "password": "OriginalPassword123!",
            "display_name": "Reset User",
            "organization_name": "Reset Team",
        },
    )
    auth = signup.json()["data"]
    async with SessionFactory() as session:
        user = await session.scalar(select(User).where(User.email == "single-reset@example.com"))
        first = await create_one_time_token(session, user, "password_reset", get_settings())
        second = await create_one_time_token(session, user, "password_reset", get_settings())
        await session.commit()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    stale = await client.post(
        "/v1/auth/reset-password",
        headers=headers,
        json={"token": first, "new_password": "ReplacementPassword123!"},
    )
    assert stale.status_code == 400
    accepted = await client.post(
        "/v1/auth/reset-password",
        headers=headers,
        json={"token": second, "new_password": "ReplacementPassword123!"},
    )
    assert accepted.status_code == 200
    replay = await client.post(
        "/v1/auth/reset-password",
        headers=headers,
        json={"token": second, "new_password": "AnotherPassword123!"},
    )
    assert replay.status_code == 400
