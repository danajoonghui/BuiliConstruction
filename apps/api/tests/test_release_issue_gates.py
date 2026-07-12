from __future__ import annotations

from sqlalchemy import select

from buili_api.db import SessionFactory
from buili_api.models import (
    Document,
    DocumentRevision,
    Evidence,
    Issue,
    IssueEvidence,
    IssueSource,
    OrganizationMember,
    Project,
)
from buili_api.services.issues import analyze_issue


async def _seed_issue(account, *, structured: bool, source_status: str) -> str:
    async with SessionFactory() as session:
        organization_id = await session.scalar(
            select(OrganizationMember.organization_id).where(
                OrganizationMember.user_id == account["user"]["id"]
            )
        )
        project = Project(
            organization_id=organization_id,
            name=f"Safety Gate {structured} {source_status}",
            code=f"GATE-{int(structured)}-{source_status}",
        )
        session.add(project)
        await session.flush()
        document = Document(
            organization_id=organization_id,
            project_id=project.id,
            title="Electrical requirement",
            kind="drawing",
            discipline="electrical",
            created_by=account["user"]["id"],
        )
        session.add(document)
        await session.flush()
        revision = DocumentRevision(
            document_id=document.id,
            revision="1",
            status=source_status,
            storage_key=f"test/{project.id}/E1.1.txt",
            content_type="text/plain",
            sheet_number="E1.1",
            sha256="a" * 64,
            extracted_text="Garage receptacle centerline minimum 18 inches AFF.",
        )
        session.add(revision)
        await session.flush()
        location = {"space": "Garage", "wall": "East"}
        photo = Evidence(
            organization_id=organization_id,
            project_id=project.id,
            kind="photo",
            title="Garage receptacle context",
            description="Garage receptacle box is visible at the east wall.",
            location_json=location,
            created_by=account["user"]["id"],
        )
        measurement = Evidence(
            organization_id=organization_id,
            project_id=project.id,
            kind="measurement",
            title="Receptacle centerline measurement",
            description="Centerline appears to be 12 inches AFF while the note says 18 inches.",
            location_json=location,
            metadata_json=(
                {
                    "measurement": {
                        "observed_value": 12,
                        "unit": "inch",
                        "minimum": 18,
                        "source_revision_id": revision.id,
                    }
                }
                if structured
                else {"value": 12, "unit": "inch"}
            ),
            created_by=account["user"]["id"],
        )
        session.add_all([photo, measurement])
        await session.flush()
        issue = Issue(
            organization_id=organization_id,
            project_id=project.id,
            number="BUI-GATE-1",
            title="Garage receptacle elevation",
            issue_type="quality_defect",
            observed_condition="Garage receptacle centerline appears 12 inches AFF.",
            expected_condition="E1.1 requires the garage receptacle centerline at 18 inches AFF.",
            difference="The field and requirement appear different.",
            location_json=location,
            created_by=account["user"]["id"],
        )
        session.add(issue)
        await session.flush()
        session.add_all(
            [
                IssueEvidence(issue_id=issue.id, evidence_id=photo.id),
                IssueEvidence(issue_id=issue.id, evidence_id=measurement.id),
                IssueSource(
                    issue_id=issue.id,
                    revision_id=revision.id,
                    quote="Garage receptacle centerline minimum 18 inches AFF.",
                    relationship_type="requirement",
                ),
            ]
        )
        await session.flush()
        await analyze_issue(session, issue)
        await session.commit()
        return issue.id


async def test_free_form_numbers_do_not_auto_classify_or_approve(client, account):
    issue_id = await _seed_issue(account, structured=False, source_status="approved")
    issue = (await client.get(f"/v1/issues/{issue_id}", headers=account["headers"])).json()["data"]["issue"]
    assert issue["evidence_sufficiency"] == "insufficient"
    assert issue["classification"] == "insufficient_evidence"
    approval = await client.post(f"/v1/issues/{issue_id}/approve", headers=account["headers"])
    assert approval.status_code == 409
    assert approval.json()["error"]["code"] == "ISSUE_APPROVAL_BLOCKED"


async def test_superseded_source_blocks_even_structured_measurement(client, account):
    issue_id = await _seed_issue(account, structured=True, source_status="superseded")
    issue = (await client.get(f"/v1/issues/{issue_id}", headers=account["headers"])).json()["data"]["issue"]
    assert issue["evidence_sufficiency"] == "insufficient"
    assert "Relevant current approved drawing/specification source" in issue["missing_evidence"]
