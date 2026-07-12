from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import Settings
from .models import (
    Document,
    DocumentRevision,
    Evidence,
    Issue,
    IssueEvidence,
    IssueSource,
    Organization,
    OrganizationMember,
    Project,
    ProjectMember,
    Report,
    ReportArtifact,
    User,
)
from .security import hash_password
from .services.reports import ReportService
from .services.search import SearchService
from .services.storage import ObjectStorage

TRANSCRIPT = (
    "Mike at the Cooper Residence, garage east wall near the entry door. We checked the GFCI "
    "box shown on E1.1. Its centerline is at twelve inches above the floor, but electrical note "
    "three calls for a minimum of eighteen inches in garages. I left the stud bay open and "
    "tagged the location. Please confirm whether Delta Electrical should raise the box before close-in."
)


def _locate_assets(settings: Settings) -> Path | None:
    candidates = [settings.demo_evidence_path, Path.cwd() / settings.demo_evidence_path]
    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidates.append(parent / "buili_demo_evidence")
    return next((candidate.resolve() for candidate in candidates if candidate.exists()), None)


async def seed_demo(
    session: AsyncSession,
    settings: Settings,
    storage: ObjectStorage,
    search: SearchService,
    reports: ReportService,
) -> None:
    if not settings.demo_mode:
        return
    user = await session.scalar(select(User).where(User.email == settings.demo_email.lower()))
    if user is None:
        user = User(
            email=settings.demo_email.lower(),
            display_name="Jordan Cho",
            password_hash=hash_password(settings.demo_password.get_secret_value()),
            email_verified=True,
        )
        session.add(user)
        await session.flush()
    organization = await session.scalar(select(Organization).where(Organization.slug == "northstar-builders"))
    if organization is None:
        organization = Organization(name="Northstar Builders", slug="northstar-builders")
        session.add(organization)
        await session.flush()
    if not await session.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id == user.id,
        )
    ):
        session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    foreman = await session.scalar(select(User).where(User.email == "mike.alvarez@demo.buili.local"))
    if foreman is None:
        foreman = User(email="mike.alvarez@demo.buili.local", display_name="Mike Alvarez")
        session.add(foreman)
        await session.flush()
        session.add(OrganizationMember(organization_id=organization.id, user_id=foreman.id, role="member"))
    project = await session.scalar(
        select(Project).where(Project.organization_id == organization.id, Project.code == "CR-2026-017")
    )
    if project is None:
        project = Project(
            organization_id=organization.id,
            name="Cooper Residence Renovation",
            code="CR-2026-017",
            project_type="residential_renovation",
            address="San Jose, CA",
            metadata_json={"demo": True, "phase": "rough-in", "responsible_trade": "Delta Electrical"},
        )
        session.add(project)
        await session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role="manager"))
        session.add(ProjectMember(project_id=project.id, user_id=foreman.id, role="field_user"))

    assets = _locate_assets(settings)
    asset_map: dict[str, str] = {}
    if assets:
        for filename in [
            "garage-east-wall-context.png",
            "box-elevation-measurement.png",
            "receptacle-rough-in-detail.png",
            "foreman-voice-note.mp3",
            "foreman-voice-note.vtt",
            "cooper-residence-E1.1-demo.pdf",
            "BUI-1042-issue-package.pdf",
            "BUI-1042-issue-package.docx",
        ]:
            source = assets / filename
            if source.exists():
                key = f"org/{organization.id}/project/{project.id}/demo/{filename}"
                media_type = (
                    "application/pdf"
                    if filename.endswith(".pdf")
                    else (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        if filename.endswith(".docx")
                        else (
                            "audio/mpeg"
                            if filename.endswith(".mp3")
                            else ("text/vtt" if filename.endswith(".vtt") else "image/png")
                        )
                    )
                )
                await storage.put_bytes(key, source.read_bytes(), media_type)
                asset_map[filename] = key

    document = await session.scalar(
        select(Document).where(Document.project_id == project.id, Document.title == "Electrical Power Plan E1.1")
    )
    if document is None:
        document = Document(
            organization_id=organization.id,
            project_id=project.id,
            title="Electrical Power Plan E1.1",
            kind="drawing",
            discipline="electrical",
            created_by=user.id,
        )
        session.add(document)
        await session.flush()
        revision = DocumentRevision(
            document_id=document.id,
            revision="IFC-1",
            status="approved",
            storage_key=asset_map.get("cooper-residence-E1.1-demo.pdf", "demo/source-unavailable"),
            content_type="application/pdf",
            size=(assets / "cooper-residence-E1.1-demo.pdf").stat().st_size
            if assets and (assets / "cooper-residence-E1.1-demo.pdf").exists()
            else 0,
            sha256=hashlib.sha256(
                (assets / "cooper-residence-E1.1-demo.pdf").read_bytes()
            ).hexdigest()
            if assets and (assets / "cooper-residence-E1.1-demo.pdf").exists()
            else "",
            sheet_number="E1.1",
            extracted_text="Electrical Note 3: Garage receptacle centerline shall be minimum 18 inches above finished floor.",
            metadata_json={"demo": True, "source_verified": True},
        )
        session.add(revision)
        await session.flush()
        await search.replace_source(
            session,
            organization_id=organization.id,
            project_id=project.id,
            source_type="document_revision",
            source_id=revision.id,
            text=revision.extracted_text,
            metadata={"title": document.title, "sheet_number": "E1.1", "revision": "IFC-1"},
        )
    else:
        revision = await session.scalar(select(DocumentRevision).where(DocumentRevision.document_id == document.id))
    if revision and assets and (assets / "cooper-residence-E1.1-demo.pdf").exists():
        drawing_payload = (assets / "cooper-residence-E1.1-demo.pdf").read_bytes()
        revision.storage_key = asset_map.get(
            "cooper-residence-E1.1-demo.pdf", revision.storage_key
        )
        revision.size = len(drawing_payload)
        revision.sha256 = hashlib.sha256(drawing_payload).hexdigest()

    evidence_specs = [
        ("Garage east wall context", "photo", "garage-east-wall-context.png", "Open stud wall near garage entry door; GFCI rough-in visible."),
        ("GFCI centerline tape measurement", "measurement", "box-elevation-measurement.png", "Tape shows receptacle centerline at approximately 12 inches AFF."),
        ("Receptacle rough-in detail", "photo", "receptacle-rough-in-detail.png", "Close view of the installed box before wall close-in."),
        ("Foreman voice note", "voice_note", "foreman-voice-note.mp3", "Mike Alvarez field note requesting pre-close-in review."),
    ]
    evidence_items: list[Evidence] = []
    for title, kind, filename, description in evidence_specs:
        item = await session.scalar(select(Evidence).where(Evidence.project_id == project.id, Evidence.title == title))
        if item is None:
            item = Evidence(
                organization_id=organization.id,
                project_id=project.id,
                kind=kind,
                title=title,
                description=description,
                storage_key=asset_map.get(filename),
                content_type="audio/mpeg" if filename.endswith(".mp3") else "image/png",
                location_json={"building": "Residence", "space": "Garage", "wall": "East wall", "near": "Entry door", "confidence": "room_level"},
                metadata_json={
                    "demo": True,
                    "captured_by": "Mike Alvarez",
                    "trade": "electrical",
                    **(
                        {
                            "measurement": {
                                "observed_value": 12,
                                "unit": "inch",
                                "minimum": 18,
                                "tolerance": 0,
                                "source_revision_id": revision.id,
                            }
                        }
                        if kind == "measurement" and revision
                        else {}
                    ),
                },
                transcript=TRANSCRIPT if kind == "voice_note" else "",
                created_by=foreman.id,
                analysis_json={"provider": "seeded", "confidence": 0.98},
            )
            session.add(item)
            await session.flush()
            await search.replace_source(
                session,
                organization_id=organization.id,
                project_id=project.id,
                source_type="evidence",
                source_id=item.id,
                text=f"{title}. {description} {item.transcript}",
                metadata={"kind": kind, "location": item.location_json},
            )
        evidence_items.append(item)

    issue = await session.scalar(select(Issue).where(Issue.project_id == project.id, Issue.number == "BUI-1042"))
    if issue is None:
        issue = Issue(
            organization_id=organization.id,
            project_id=project.id,
            number="BUI-1042",
            title="Garage GFCI receptacle below required elevation",
            description="Correct before wall close-in; designer clarification is optional, not the default route.",
            issue_type="quality_defect",
            status="ready_for_review",
            priority="high",
            observed_condition="GFCI box centerline measures 12 inches above finished floor at the garage east wall.",
            expected_condition="E1.1 Electrical Note 3 requires garage receptacle centerline at a minimum 18 inches AFF.",
            difference="Installed centerline is 6 inches below the explicit approved drawing requirement.",
            classification="unapproved_deviation",
            recommended_action="field_correction_punch",
            evidence_sufficiency="sufficient",
            missing_evidence=[],
            location_json={"space": "Garage", "wall": "East wall", "near": "Entry door"},
            assigned_to=user.id,
            created_by=foreman.id,
        )
        session.add(issue)
        await session.flush()
    for item in evidence_items:
        if not await session.get(IssueEvidence, (issue.id, item.id)):
            session.add(IssueEvidence(issue_id=issue.id, evidence_id=item.id))
    if revision and not await session.scalar(select(IssueSource.id).where(IssueSource.issue_id == issue.id)):
        session.add(
            IssueSource(
                issue_id=issue.id,
                revision_id=revision.id,
                quote="E1.1 Note 3: garage receptacle centerline minimum 18 inches AFF.",
                relationship_type="requirement",
            )
        )
    await session.flush()
    if not list((await session.scalars(select(Report).where(Report.issue_id == issue.id))).all()):
        if asset_map.get("BUI-1042-issue-package.pdf"):
            static_report = Report(
                    organization_id=organization.id,
                    project_id=project.id,
                    issue_id=issue.id,
                    kind="evidence_package",
                    status="review_ready",
                    version=1,
                    title="BUI-1042 review-ready issue package",
                    storage_key=asset_map["BUI-1042-issue-package.pdf"],
                    content_type="application/pdf",
                    template_version="buili.issue-pack.v2",
                    source_index_json=(
                        [
                            {
                                "index": 1,
                                "revision_id": revision.id,
                                "document_title": document.title,
                                "sheet_number": revision.sheet_number,
                                "revision": revision.revision,
                                "status": revision.status,
                                "page": 1,
                                "quote": "E1.1 Note 3: garage receptacle centerline minimum 18 inches AFF.",
                                "sha256": revision.sha256,
                            }
                        ]
                        if revision
                        else []
                    ),
                    generated_by=user.id,
                )
            session.add(static_report)
            await session.flush()
            for format_name, filename, content_type in (
                ("pdf", "BUI-1042-issue-package.pdf", "application/pdf"),
                (
                    "docx",
                    "BUI-1042-issue-package.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ):
                if assets is None or filename not in asset_map:
                    continue
                payload = (assets / filename).read_bytes()
                session.add(
                    ReportArtifact(
                        report_id=static_report.id,
                        organization_id=organization.id,
                        project_id=project.id,
                        format=format_name,
                        storage_key=asset_map[filename],
                        content_type=content_type,
                        size=len(payload),
                        sha256=hashlib.sha256(payload).hexdigest(),
                    )
                )
        await reports.generate(
            session,
            issue=issue,
            kind="punch",
            title="Field correction - raise garage GFCI rough-in before close-in",
            user_id=user.id,
            approve=False,
        )
        await reports.generate(
            session,
            issue=issue,
            kind="rfi",
            title="Optional clarification - garage receptacle elevation",
            user_id=user.id,
            approve=False,
        )
    await session.commit()
