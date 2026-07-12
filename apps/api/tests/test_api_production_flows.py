from __future__ import annotations

import asyncio
import hashlib
import re

from sqlalchemy import select

from buili_api.db import SessionFactory
from buili_api.models import AuditLog, Job, OrganizationMember, ProjectMember


async def _organization_id(client, headers: dict[str, str], name: str) -> str:
    response = await client.get("/v1/organizations", headers=headers)
    assert response.status_code == 200, response.text
    return next(item["id"] for item in response.json()["data"] if item["name"] == name)


async def _project(client, headers: dict[str, str], organization_id: str, code: str) -> dict:
    response = await client.post(
        "/v1/projects",
        headers=headers,
        json={
            "organization_id": organization_id,
            "name": f"Production QA {code}",
            "code": code,
            "project_type": "renovation",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class RecordingEmail:
    enabled = True

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, text: str) -> bool:
        self.messages.append({"to": to, "subject": subject, "text": text})
        return True


def _emailed_token(message: dict[str, str]) -> str:
    match = re.search(r"token=([^\s]+)", message["text"])
    assert match
    return match.group(1)


async def test_email_verification_and_password_reset_are_single_use_and_revoke_sessions(client):
    original_email = client._transport.app.state.services.email
    email = RecordingEmail()
    client._transport.app.state.services.email = email
    try:
        signup = await client.post(
            "/v1/auth/signup?transport=body",
            json={
                "email": "email-lifecycle@example.com",
                "password": "OriginalPassword123!",
                "display_name": "Email Lifecycle",
                "organization_name": "Email Lifecycle Team",
            },
        )
        assert signup.status_code == 201, signup.text
        initial = signup.json()["data"]

        requested = await client.post(
            "/v1/auth/request-email-verification",
            json={"email": "email-lifecycle@example.com"},
        )
        assert requested.status_code == 202, requested.text
        verification_token = _emailed_token(email.messages[-1])
        verified = await client.post(
            "/v1/auth/verify-email", json={"token": verification_token}
        )
        assert verified.status_code == 200, verified.text
        assert (
            await client.post("/v1/auth/verify-email", json={"token": verification_token})
        ).status_code == 400

        forgot = await client.post(
            "/v1/auth/forgot-password", json={"email": "email-lifecycle@example.com"}
        )
        assert forgot.status_code == 202, forgot.text
        reset_token = _emailed_token(email.messages[-1])
        weak = await client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "new_password": "aaaaaaaaaaaa"},
        )
        assert weak.status_code == 422
        assert "aaaaaaaaaaaa" not in weak.text
        assert "input" not in weak.json()["error"]["details"]["errors"][0]
        reset = await client.post(
            "/v1/auth/reset-password",
            json={"token": reset_token, "new_password": "ReplacementPassword123!"},
        )
        assert reset.status_code == 200, reset.text
        assert (
            await client.get(
                "/v1/auth/me",
                headers={"Authorization": f"Bearer {initial['access_token']}"},
            )
        ).json()["error"]["code"] == "TOKEN_REVOKED"
        old_refresh = await client.post(
            "/v1/auth/refresh?transport=body",
            json={"refresh_token": initial["refresh_token"]},
        )
        assert old_refresh.status_code == 401
        login = await client.post(
            "/v1/auth/login?transport=body",
            json={
                "email": "email-lifecycle@example.com",
                "password": "ReplacementPassword123!",
            },
        )
        assert login.status_code == 200, login.text
        replacement = login.json()["data"]
        logout = await client.post(
            "/v1/auth/logout",
            headers={"Authorization": f"Bearer {replacement['access_token']}"},
            json={"refresh_token": replacement["refresh_token"]},
        )
        assert logout.status_code == 204, logout.text
        assert (
            await client.post(
                "/v1/auth/refresh?transport=body",
                json={"refresh_token": replacement["refresh_token"]},
            )
        ).status_code == 401
        async with SessionFactory() as session:
            actions = list(
                (
                    await session.scalars(
                        select(AuditLog.action).where(
                            AuditLog.actor_user_id == initial["user"]["id"]
                        )
                    )
                ).all()
            )
        assert "EMAIL_VERIFIED" in actions
        assert "PASSWORD_RESET" in actions
        assert "USER_LOGGED_OUT" in actions
    finally:
        client._transport.app.state.services.email = original_email


async def test_oidc_exchange_and_explicit_linking_use_verified_provider_claims(
    client, account, monkeypatch
):
    async def verified_claims(_self, token: str):
        if token == "existing-account":
            return {
                "iss": "https://accounts.google.com",
                "sub": "google-builder-subject",
                "email": "builder@example.com",
                "email_verified": True,
                "name": "Avery Builder",
            }
        return {
            "iss": "https://accounts.google.com",
            "sub": "google-new-subject",
            "email": "oidc-only@example.com",
            "email_verified": True,
            "name": "OIDC User",
        }

    monkeypatch.setattr("buili_api.routes.OIDCVerifier.verify", verified_claims)
    requires_link = await client.post(
        "/v1/auth/oidc/exchange?transport=body", json={"id_token": "existing-account"}
    )
    assert requires_link.status_code == 409
    assert requires_link.json()["error"]["code"] == "OIDC_LINK_REQUIRED"
    linked = await client.post(
        "/v1/auth/oidc/link",
        headers=account["headers"],
        json={"id_token": "existing-account"},
    )
    assert linked.status_code == 200, linked.text
    linked_login = await client.post(
        "/v1/auth/oidc/exchange?transport=body", json={"id_token": "existing-account"}
    )
    assert linked_login.status_code == 200, linked_login.text
    assert linked_login.json()["data"]["user"]["id"] == account["user"]["id"]

    new_login = await client.post(
        "/v1/auth/oidc/exchange?transport=body",
        json={"id_token": "new-account-id-token", "organization_name": "OIDC QA Team"},
    )
    assert new_login.status_code == 200, new_login.text
    new_headers = {"Authorization": f"Bearer {new_login.json()['data']['access_token']}"}
    organizations = await client.get("/v1/organizations", headers=new_headers)
    assert [item["name"] for item in organizations.json()["data"]] == ["OIDC QA Team"]


async def test_upload_checksum_ownership_project_roles_and_assignee_boundaries(client, account):
    organization_id = await _organization_id(
        client, account["headers"], "Avery Construction"
    )
    project = await _project(client, account["headers"], organization_id, "QA-SEC-001")

    field_signup = await client.post(
        "/v1/auth/signup?transport=body",
        json={
            "email": "field-role@example.com",
            "password": "FieldRolePassword123!",
            "display_name": "Field Role",
            "organization_name": "Field Role Home",
        },
    )
    assert field_signup.status_code == 201, field_signup.text
    field = field_signup.json()["data"]
    async with SessionFactory() as session:
        session.add(
            OrganizationMember(
                organization_id=organization_id,
                user_id=field["user"]["id"],
                role="member",
            )
        )
        session.add(
            ProjectMember(
                project_id=project["id"], user_id=field["user"]["id"], role="field_user"
            )
        )
        await session.commit()
    field_headers = {"Authorization": f"Bearer {field['access_token']}"}
    assert (
        await client.get(f"/v1/projects/{project['id']}", headers=field_headers)
    ).status_code == 200
    assert (
        await client.post(
            f"/v1/projects/{project['id']}/documents",
            headers=field_headers,
            json={"title": "Forbidden document", "kind": "drawing"},
        )
    ).status_code == 403

    data = b"checksum-bound field evidence"
    digest = hashlib.sha256(data).hexdigest()
    malformed = await client.post(
        "/v1/uploads/init",
        headers=account["headers"],
        json={
            "organization_id": organization_id,
            "project_id": project["id"],
            "filename": "bad.txt",
            "content_type": "text/plain",
            "size": len(data),
            "sha256": "z" * 64,
        },
    )
    assert malformed.status_code == 422
    initialized = await client.post(
        "/v1/uploads/init",
        headers=account["headers"],
        json={
            "organization_id": organization_id,
            "project_id": project["id"],
            "filename": "proof.txt",
            "content_type": "text/plain",
            "size": len(data),
            "sha256": digest.upper(),
        },
    )
    assert initialized.status_code == 201, initialized.text
    upload_id = initialized.json()["data"]["upload_id"]
    assert (
        await client.put(
            f"/v1/uploads/{upload_id}/content", headers=field_headers, content=data
        )
    ).status_code == 403
    stored = await client.put(
        f"/v1/uploads/{upload_id}/content", headers=account["headers"], content=data
    )
    assert stored.status_code == 204, stored.text
    wrong_completion = await client.post(
        f"/v1/uploads/{upload_id}/complete",
        headers=account["headers"],
        json={"sha256": "0" * 64},
    )
    assert wrong_completion.status_code == 409
    completed = await client.post(
        f"/v1/uploads/{upload_id}/complete",
        headers=account["headers"],
        json={"sha256": digest},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["scan_status"] == "clean"
    polled = await client.get(f"/v1/uploads/{upload_id}", headers=account["headers"])
    assert polled.status_code == 200, polled.text
    assert polled.json()["data"]["status"] == "complete"
    assert polled.json()["data"]["scan_status"] == "clean"
    assert (
        await client.get(f"/v1/uploads/{upload_id}", headers=field_headers)
    ).status_code == 403
    idempotent_mismatch = await client.post(
        f"/v1/uploads/{upload_id}/complete",
        headers=account["headers"],
        json={"sha256": "0" * 64},
    )
    assert idempotent_mismatch.status_code == 409

    issue = await client.post(
        f"/v1/projects/{project['id']}/issues",
        headers=field_headers,
        json={"title": "Field role can record an issue"},
    )
    assert issue.status_code == 201, issue.text
    issue_id = issue.json()["data"]["id"]
    forbidden_review = await client.post(
        f"/v1/issues/{issue_id}/approve", headers=field_headers
    )
    assert forbidden_review.status_code == 403
    invalid_assignee = await client.patch(
        f"/v1/issues/{issue_id}",
        headers=account["headers"],
        json={"assigned_to": "usr_not-a-project-member"},
    )
    assert invalid_assignee.status_code == 422
    valid_assignee = await client.patch(
        f"/v1/issues/{issue_id}",
        headers=account["headers"],
        json={"assigned_to": field["user"]["id"]},
    )
    assert valid_assignee.status_code == 200, valid_assignee.text
    duplicates = await client.post(
        f"/v1/projects/{project['id']}/issues",
        headers=field_headers,
        json={
            "title": "Duplicate evidence links",
            "evidence_ids": ["evd_same", "evd_same"],
        },
    )
    assert duplicates.status_code == 422

    numbering_project = await _project(
        client, account["headers"], organization_id, "QA-NUM-001"
    )
    custom = await client.post(
        f"/v1/projects/{numbering_project['id']}/issues",
        headers=account["headers"],
        json={"number": "BUI-0002", "title": "Reserved custom number"},
    )
    assert custom.status_code == 201, custom.text
    automatic = await client.post(
        f"/v1/projects/{numbering_project['id']}/issues",
        headers=account["headers"],
        json={"title": "Automatic number skips collision"},
    )
    assert automatic.status_code == 201, automatic.text
    assert automatic.json()["data"]["number"] == "BUI-0003"


async def test_document_audit_keeps_resource_id_and_jobs_claim_exactly_once(client, account):
    organization_id = await _organization_id(
        client, account["headers"], "Avery Construction"
    )
    project = await _project(client, account["headers"], organization_id, "QA-AUD-001")
    document = await client.post(
        f"/v1/projects/{project['id']}/documents",
        headers=account["headers"],
        json={"title": "Audited source", "kind": "drawing"},
    )
    assert document.status_code == 201, document.text
    audit = await client.get(
        f"/v1/projects/{project['id']}/audit?action=DOCUMENT_CREATED",
        headers=account["headers"],
    )
    assert audit.status_code == 200, audit.text
    assert audit.json()["meta"]["total"] == 1
    assert audit.json()["data"][0]["resource_id"] == document.json()["data"]["id"]

    kind = "qa.exactly_once"
    calls = 0

    async def handler(_session, job):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return {"job_id": job.id}

    manager = client._transport.app.state.services.jobs
    manager.register(kind, handler)
    async with SessionFactory() as session:
        job = Job(
            organization_id=organization_id,
            project_id=project["id"],
            kind=kind,
            created_by=account["user"]["id"],
        )
        session.add(job)
        await session.commit()
        job_id = job.id
    await asyncio.gather(manager.run_now(job_id), manager.run_now(job_id))
    assert calls == 1
    status = await client.get(f"/v1/jobs/{job_id}", headers=account["headers"])
    assert status.status_code == 200, status.text
    assert status.json()["data"]["status"] == "succeeded"
    assert status.json()["data"]["attempts"] == 1
