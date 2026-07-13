from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.errors import AppError
from ..models import (
    Document,
    DocumentRevision,
    Evidence,
    Issue,
    IssueEvidence,
    IssueSource,
    Project,
    Report,
    ReportArtifact,
    User,
    new_id,
    utcnow,
)
from .report_rendering import (
    TEMPLATE_VERSION,
    ReportContext,
    ReportEvidence,
    ReportSource,
    render_docx,
    render_pdf,
    source_index,
    validate_report_context,
)
from .storage import ObjectStorage


class ReportService:
    """Create immutable, versioned PDF/DOCX issue packages.

    A report row is one immutable version. Approval never mutates a draft artifact;
    it produces a new approved version from the current issue and source state.
    """

    def __init__(self, storage: ObjectStorage):
        self.storage = storage

    @staticmethod
    def _location_text(value: dict[str, Any]) -> str:
        return " / ".join(
            f"{key.replace('_', ' ').title()}: {item}"
            for key, item in value.items()
            if item not in (None, "", [], {})
        ) or "Location not recorded"

    @staticmethod
    def approval_blockers(
        issue: Issue,
        evidence: list[Evidence],
        sources: list[tuple[IssueSource, DocumentRevision, Document]],
    ) -> list[str]:
        blockers: list[str] = []
        if issue.status != "approved" or not issue.approved_by or not issue.approved_at:
            blockers.append("issue must be approved by an authorized reviewer")
        if issue.evidence_sufficiency != "sufficient":
            blockers.append("issue evidence must be marked sufficient")
        if not evidence:
            blockers.append("at least one field evidence item must be linked")
        if not sources:
            blockers.append("at least one project source revision must be linked")
        if sources and not any(revision.status == "approved" for _, revision, _ in sources):
            blockers.append("at least one linked source must be approved")
        verification = issue.verification_json or {}
        if verification.get("schema") != "buili.issue-verification.v2":
            blockers.append("current issue verification run is missing")
        if verification.get("blocking_reasons"):
            blockers.append("issue verification contains blocking reasons")
        approved_ids = set(verification.get("approved_relevant_source_revision_ids") or [])
        current_hashes = {
            revision.id: revision.sha256
            for _link, revision, _document in sources
            if revision.status == "approved"
        }
        if not approved_ids or not approved_ids.issubset(current_hashes):
            blockers.append("verified approved source set is stale")
        verified_hashes = verification.get("source_hashes") or {}
        if any(verified_hashes.get(revision_id) != current_hashes.get(revision_id) for revision_id in approved_ids):
            blockers.append("approved source content changed after issue verification")
        if not issue.observed_condition.strip():
            blockers.append("observed condition is missing")
        if not issue.expected_condition.strip():
            blockers.append("required or expected condition is missing")
        return blockers

    async def _load_context_rows(
        self, session: AsyncSession, issue: Issue
    ) -> tuple[Project, list[Evidence], list[tuple[IssueSource, DocumentRevision, Document]]]:
        project = await session.get(Project, issue.project_id)
        if project is None:
            raise AppError(409, "PROJECT_NOT_FOUND", "Issue project was not found")
        evidence_rows = list(
            (
                await session.execute(
                    select(Evidence)
                    .join(IssueEvidence, IssueEvidence.evidence_id == Evidence.id)
                    .where(IssueEvidence.issue_id == issue.id)
                    .order_by(Evidence.created_at, Evidence.id)
                )
            ).scalars()
        )
        result = await session.execute(
            select(IssueSource, DocumentRevision, Document)
            .join(DocumentRevision, DocumentRevision.id == IssueSource.revision_id)
            .join(Document, Document.id == DocumentRevision.document_id)
            .where(IssueSource.issue_id == issue.id)
            .order_by(Document.title, DocumentRevision.revision, IssueSource.page)
        )
        source_rows = [
            (link, revision, document)
            for link, revision, document in result.tuples().all()
        ]
        return project, evidence_rows, source_rows

    async def _report_context(
        self,
        session: AsyncSession,
        *,
        report_id: str,
        version: int,
        status: str,
        kind: str,
        title: str,
        project: Project,
        issue: Issue,
        evidence_rows: list[Evidence],
        source_rows: list[tuple[IssueSource, DocumentRevision, Document]],
        generated_at: datetime,
        generated_by: str,
    ) -> ReportContext:
        evidence: list[ReportEvidence] = []
        for item in evidence_rows:
            image_bytes: bytes | None = None
            if item.storage_key and (item.content_type or "").lower().startswith("image/"):
                try:
                    image_bytes = await self.storage.read_bytes(item.storage_key)
                except AppError:
                    image_bytes = None
            evidence.append(
                ReportEvidence(
                    id=item.id,
                    kind=item.kind,
                    title=item.title,
                    description=item.description,
                    transcript=item.transcript,
                    captured_at=item.captured_at.isoformat() if item.captured_at else "",
                    location=self._location_text(item.location_json),
                    image_bytes=image_bytes,
                )
            )
        sources = [
            ReportSource(
                index=index,
                revision_id=revision.id,
                document_title=document.title,
                sheet_number=revision.sheet_number or document.title,
                revision=revision.revision,
                status=revision.status,
                page=link.page,
                quote=link.quote,
                relationship_type=link.relationship_type,
                sha256=revision.sha256,
            )
            for index, (link, revision, document) in enumerate(source_rows, start=1)
        ]
        report_fields = dict((issue.verification_json or {}).get("report_fields") or {})
        people_ids = {
            value
            for value in (generated_by, issue.created_by, issue.assigned_to, issue.approved_by)
            if value
        }
        people: dict[str, str] = {}
        if people_ids:
            people = {
                user.id: user.display_name
                for user in (
                    await session.execute(select(User).where(User.id.in_(people_ids)))
                ).scalars()
            }

        def field(name: str, fallback: str = "") -> str:
            value = report_fields.get(name)
            return str(value).strip() if value not in (None, "") else fallback

        assignee = people.get(issue.assigned_to or "", "Project assignee")
        preparer = people.get(generated_by, "BUILI project reviewer")
        approver = people.get(issue.approved_by or "", "Project manager review required")
        due_date = field("due_date", (generated_at + timedelta(days=7)).date().isoformat())
        question = field(
            "question",
            f"Please confirm the governing requirement and direction for {issue.title.lower()}.",
        )
        required_action = field("required_action", issue.recommended_action.replace("_", " ").title())
        completion_requirement = field(
            "completion_requirement",
            "Upload corrected-condition evidence at the same location and obtain reviewer acceptance.",
        )
        line_items = report_fields.get("line_items") if isinstance(report_fields.get("line_items"), list) else []
        manpower = report_fields.get("manpower") if isinstance(report_fields.get("manpower"), list) else []
        activity_log = report_fields.get("activity_log") if isinstance(report_fields.get("activity_log"), list) else []

        return ReportContext(
            report_id=report_id,
            version=version,
            kind=kind,
            title=title,
            status=status,
            generated_at=generated_at,
            project_name=project.name,
            project_code=project.code,
            project_address=project.address,
            issue_number=issue.number,
            issue_status=issue.status,
            issue_type=issue.issue_type,
            priority=issue.priority,
            classification=issue.classification,
            recommended_action=issue.recommended_action,
            evidence_sufficiency=issue.evidence_sufficiency,
            location=self._location_text(issue.location_json),
            observed_condition=issue.observed_condition or issue.description,
            expected_condition=issue.expected_condition,
            difference=issue.difference,
            missing_evidence=list(issue.missing_evidence or []),
            evidence=evidence,
            sources=sources,
            prepared_by=field("prepared_by", preparer),
            responsible_party=field("responsible_party", assignee),
            final_approver=field("final_approver", approver),
            ball_in_court=field("ball_in_court", assignee),
            due_date=due_date,
            question=question,
            suggested_answer=field("suggested_answer"),
            official_response=field("official_response"),
            cost_impact=field("cost_impact", "ROM pending commercial review"),
            schedule_impact=field("schedule_impact", "Impact pending project-controls review"),
            root_cause=field("root_cause", issue.classification.replace("_", " ").title()),
            required_action=required_action,
            completion_requirement=completion_requirement,
            origin=field("origin", issue.number),
            change_reason=field("change_reason", issue.classification.replace("_", " ").title()),
            scope=field("scope", issue.difference or issue.description),
            report_date=field("report_date", generated_at.date().isoformat()),
            weather=field("weather", "Not recorded for this issue-based report"),
            work_completed=field("work_completed", issue.observed_condition or issue.description),
            safety_summary=field("safety_summary", "No safety event linked to this record"),
            manpower=manpower,
            line_items=line_items,
            activity_log=activity_log,
        )

    async def _store_artifact(
        self,
        *,
        report: Report,
        format_name: str,
        payload: bytes,
        content_type: str,
    ) -> ReportArtifact:
        key = (
            f"org/{report.organization_id}/project/{report.project_id}/reports/"
            f"{report.kind}/{report.id}/v{report.version}/report.{format_name}"
        )
        info = await self.storage.put_bytes(key, payload, content_type)
        artifact = ReportArtifact(
            report_id=report.id,
            organization_id=report.organization_id,
            project_id=report.project_id,
            format=format_name,
            storage_key=key,
            content_type=content_type,
            size=info.size,
            sha256=info.sha256 or hashlib.sha256(payload).hexdigest(),
        )
        report.artifacts.append(artifact)
        return artifact

    async def generate(
        self,
        session: AsyncSession,
        *,
        issue: Issue,
        kind: str,
        title: str,
        user_id: str,
        approve: bool,
    ) -> Report:
        # The issue lock serializes version allocation for this issue.
        await session.scalar(select(Issue.id).where(Issue.id == issue.id).with_for_update())
        project, evidence_rows, source_rows = await self._load_context_rows(session, issue)
        if issue.status not in {"ready_for_review", "approved"}:
            raise AppError(
                409,
                "REPORT_DRAFT_BLOCKED",
                "A report draft requires an issue that is ready for review",
                {"issue_status": issue.status},
            )
        blockers = self.approval_blockers(issue, evidence_rows, source_rows)
        if approve and blockers:
            raise AppError(
                409,
                "REPORT_APPROVAL_BLOCKED",
                "Report cannot be approved until its issue and source record are complete",
                {"reasons": blockers},
            )
        version = int(
            await session.scalar(
                select(func.max(Report.version)).where(
                    Report.issue_id == issue.id, Report.kind == kind
                )
            )
            or 0
        ) + 1
        report_id = new_id("rpt")
        generated_at = datetime.now(timezone.utc)
        status = "approved" if approve else "draft"
        context = await self._report_context(
            session,
            report_id=report_id,
            version=version,
            status=status,
            kind=kind,
            title=title,
            project=project,
            issue=issue,
            evidence_rows=evidence_rows,
            source_rows=source_rows,
            generated_at=generated_at,
            generated_by=user_id,
        )
        template_omissions = validate_report_context(context)
        if approve and template_omissions:
            raise AppError(
                409,
                "REPORT_TEMPLATE_INCOMPLETE",
                "Report cannot be issued until its operational template fields are complete",
                {"missing_fields": template_omissions, "kind": kind},
            )
        pdf = render_pdf(context)
        docx = render_docx(context)
        report = Report(
            id=report_id,
            organization_id=issue.organization_id,
            project_id=issue.project_id,
            issue_id=issue.id,
            kind=kind,
            status=status,
            version=version,
            title=title,
            storage_key="pending",
            content_type="application/pdf",
            template_version=TEMPLATE_VERSION,
            source_index_json=source_index(context),
            generated_by=user_id,
            approved_by=user_id if approve else None,
            approved_at=utcnow() if approve else None,
            artifacts=[],
        )
        session.add(report)
        await session.flush()
        pdf_artifact = await self._store_artifact(
            report=report,
            format_name="pdf",
            payload=pdf,
            content_type="application/pdf",
        )
        await self._store_artifact(
            report=report,
            format_name="docx",
            payload=docx,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        manifest = {
            "schema_version": "buili.report-package.v1",
            "report_id": report.id,
            "version": report.version,
            "kind": report.kind,
            "status": report.status,
            "template_version": report.template_version,
            "issue_id": issue.id,
            "source_index": report.source_index_json,
            "generated_at": generated_at.isoformat(),
            "artifacts": [
                {
                    "format": item.format,
                    "storage_key": item.storage_key,
                    "content_type": item.content_type,
                    "size": item.size,
                    "sha256": item.sha256,
                }
                for item in report.artifacts
            ],
        }
        await self._store_artifact(
            report=report,
            format_name="json",
            payload=json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"),
            content_type="application/json",
        )
        report.storage_key = pdf_artifact.storage_key
        await session.flush()
        return report

    async def load_with_artifacts(self, session: AsyncSession, report_id: str) -> Report | None:
        return await session.scalar(
            select(Report)
            .options(selectinload(Report.artifacts))
            .where(Report.id == report_id)
        )
