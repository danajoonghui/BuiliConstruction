from __future__ import annotations

import httpx

from buili_api.core.config import Settings
from buili_api.main import create_app


async def test_health_and_auth_flow(client, account):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    assert (await client.get("/health/ready")).status_code == 200
    me = await client.get("/v1/auth/me", headers=account["headers"])
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "builder@example.com"
    refreshed = await client.post("/v1/auth/refresh?transport=body", json={"refresh_token": account["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["refresh_token"] != account["refresh_token"]


async def test_demo_persona_is_a_real_linked_account(client):
    login = await client.post(
        "/v1/auth/login?transport=body",
        json={"email": "jordan@demo.builiconstruction.com", "password": "ChangeMe-Demo-2026!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    projects = await client.get("/v1/projects", headers=headers)
    assert projects.status_code == 200
    project = next(item for item in projects.json()["data"] if item["code"] == "CR-2026-017")
    issues = await client.get(f"/v1/projects/{project['id']}/issues", headers=headers)
    issue = next(item for item in issues.json()["data"] if item["number"] == "BUI-1042")
    assert issue["classification"] == "unapproved_deviation"
    assert issue["recommended_action"] == "field_correction_punch"
    assert issue["evidence_sufficiency"] == "sufficient"
    detail = await client.get(f"/v1/issues/{issue['id']}", headers=headers)
    assert len(detail.json()["data"]["evidence"]) == 4
    assert detail.json()["data"]["sources"][0]["quote"].startswith("E1.1 Note 3")


async def test_cookie_session_and_csrf_contract(client):
    signup = await client.post(
        "/v1/auth/signup",
        json={
            "email": "cookie-user@example.com",
            "password": "CookiePassword123!",
            "display_name": "Cookie User",
            "organization_name": "Cookie Team",
        },
    )
    assert signup.status_code == 201, signup.text
    assert signup.json()["data"]["access_token"] is None
    assert signup.json()["data"]["refresh_token"] is None
    assert client.cookies.get("buili_access")
    csrf = client.cookies.get("buili_csrf")
    assert csrf
    assert (await client.get("/v1/auth/me")).status_code == 200
    rejected = await client.post("/v1/organizations", json={"name": "Missing CSRF"})
    assert rejected.status_code == 403
    accepted = await client.post(
        "/v1/organizations",
        headers={"X-CSRF-Token": csrf},
        json={"name": "CSRF Protected Team"},
    )
    assert accepted.status_code == 201, accepted.text
    refreshed = await client.post("/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["refresh_token"] is None


async def test_password_reset_capability_is_explicit(client):
    capabilities = await client.get("/v1/auth/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["data"]["password_reset_enabled"] is False
    forgot = await client.post("/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert forgot.status_code == 202
    assert forgot.json()["data"] == {"accepted": True}


async def test_production_origin_verification_header():
    production = Settings(
        _env_file=None,
        BUILI_ENVIRONMENT="production",
        BUILI_JWT_SECRET="production-test-secret-that-is-over-thirty-two-characters",
        BUILI_AUTO_CREATE_SCHEMA="false",
        BUILI_COOKIE_SECURE="true",
        BUILI_ORIGIN_VERIFY_SECRET="cloudflare-only-secret",
        BUILI_DEMO_MODE="false",
        BUILI_EMAIL_BACKEND="disabled",
        BUILI_MALWARE_SCANNER_BACKEND="clamav",
        BUILI_CORS_ORIGINS="https://app.builiconstruction.com",
    )
    guarded_app = create_app(production)
    transport = httpx.ASGITransport(app=guarded_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.builiconstruction.com") as guarded:
        health = await guarded.get("/health/live")
        assert health.status_code == 200

        rejected = await guarded.get("/v1/auth/capabilities")
        assert rejected.status_code == 403
        assert rejected.json()["error"]["code"] == "ORIGIN_VERIFICATION_FAILED"

        accepted = await guarded.get(
            "/v1/auth/capabilities",
            headers={"X-Buili-Origin-Verify": "cloudflare-only-secret"},
        )
        assert accepted.status_code == 200

        apex = await guarded.options(
            "/v1/auth/login",
            headers={
                "Origin": "https://builiconstruction.com",
                "Access-Control-Request-Method": "POST",
                "X-Buili-Origin-Verify": "cloudflare-only-secret",
            },
        )
        assert apex.headers.get("access-control-allow-origin") is None
        product = await guarded.options(
            "/v1/auth/login",
            headers={
                "Origin": "https://app.builiconstruction.com",
                "Access-Control-Request-Method": "POST",
                "X-Buili-Origin-Verify": "cloudflare-only-secret",
            },
        )
        assert product.headers.get("access-control-allow-origin") == "https://app.builiconstruction.com"
