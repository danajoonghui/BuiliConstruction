from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Document, DocumentRevision, Evidence, Issue, IssueEvidence, IssueSource

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.-]+")
STOP_WORDS = {
    "above", "after", "approved", "before", "below", "condition", "drawing", "field",
    "from", "inches", "issue", "minimum", "project", "required", "requirement", "shall",
    "that", "the", "this", "with",
}
LOCATION_KEYS = {"building", "floor", "level", "space", "room", "zone", "wall", "near"}
ACTIONABLE_CLASSIFICATIONS = {
    "approved_field_change",
    "unapproved_deviation",
    "existing_condition_conflict",
    "design_inconsistency",
}


def _tokens(*values: str) -> set[str]:
    return {
        token
        for value in values
        for token in TOKEN_RE.findall(value.lower())
        if len(token) >= 3 and token not in STOP_WORDS
    }


def _location_match(issue_location: dict[str, Any], evidence_location: dict[str, Any]) -> bool:
    shared = LOCATION_KEYS & issue_location.keys() & evidence_location.keys()
    return any(
        str(issue_location[key]).strip().lower() == str(evidence_location[key]).strip().lower()
        for key in shared
        if issue_location.get(key) and evidence_location.get(key)
    )


def _source_relevant(issue: Issue, link: IssueSource, revision: DocumentRevision) -> bool:
    if link.relationship_type not in {"requirement", "authorization", "conflict", "reference"}:
        return False
    source_text = " ".join([link.quote, revision.extracted_text])
    if not source_text.strip():
        return False
    issue_terms = _tokens(issue.title, issue.expected_condition, issue.difference, *map(str, issue.location_json.values()))
    return len(issue_terms & _tokens(source_text)) >= 2


def _evidence_relevant(issue: Issue, evidence: Evidence) -> bool:
    if evidence.project_id != issue.project_id or not _location_match(issue.location_json, evidence.location_json):
        return False
    issue_terms = _tokens(issue.title, issue.observed_condition, issue.difference)
    evidence_terms = _tokens(evidence.title, evidence.description, evidence.transcript)
    return bool(issue_terms & evidence_terms)


def _structured_measurement(
    evidence: Evidence,
    approved_revision_ids: set[str],
) -> dict[str, Any] | None:
    metadata = evidence.metadata_json if isinstance(evidence.metadata_json, dict) else {}
    measurement = metadata.get("measurement")
    raw: dict[str, Any] = measurement if isinstance(measurement, dict) else metadata
    value = raw.get("observed_value", raw.get("value"))
    unit = str(raw.get("unit") or "").strip().lower()
    source_revision_id = str(raw.get("source_revision_id") or "")
    if not isinstance(value, (int, float)) or not unit or source_revision_id not in approved_revision_ids:
        return None
    rule: str | None = None
    threshold: float | None = None
    if isinstance(raw.get("minimum"), (int, float)):
        rule, threshold = "minimum", float(raw["minimum"])
    elif isinstance(raw.get("maximum"), (int, float)):
        rule, threshold = "maximum", float(raw["maximum"])
    elif isinstance(raw.get("expected_value"), (int, float)):
        rule, threshold = "expected", float(raw["expected_value"])
    if rule is None or threshold is None:
        return None
    tolerance = float(raw.get("tolerance", 0.0)) if isinstance(raw.get("tolerance", 0.0), (int, float)) else 0.0
    observed = float(value)
    violates = (
        observed < threshold - tolerance if rule == "minimum"
        else observed > threshold + tolerance if rule == "maximum"
        else abs(observed - threshold) > tolerance
    )
    return {
        "evidence_id": evidence.id,
        "observed": observed,
        "unit": unit,
        "rule": rule,
        "threshold": threshold,
        "tolerance": tolerance,
        "source_revision_id": source_revision_id,
        "violates": violates,
    }


async def analyze_issue(session: AsyncSession, issue: Issue) -> dict[str, Any]:
    """Require relevant field proof and a current approved contractual source.

    Free-form numbers are never used to classify a deviation. Automatic routing
    requires a structured measurement explicitly bound to the approved source
    revision that defines its threshold.
    """

    evidence_links = list(
        (
            await session.execute(
                select(IssueEvidence, Evidence)
                .join(Evidence, Evidence.id == IssueEvidence.evidence_id)
                .where(IssueEvidence.issue_id == issue.id)
            )
        ).all()
    )
    source_rows = list(
        (
            await session.execute(
                select(IssueSource, DocumentRevision, Document)
                .join(DocumentRevision, DocumentRevision.id == IssueSource.revision_id)
                .join(Document, Document.id == DocumentRevision.document_id)
                .where(IssueSource.issue_id == issue.id)
            )
        ).all()
    )
    approved_sources = [
        (link, revision, document)
        for link, revision, document in source_rows
        if document.project_id == issue.project_id
        and revision.status == "approved"
        and _source_relevant(issue, link, revision)
    ]
    approved_revision_ids = {revision.id for _, revision, _ in approved_sources}
    relevant_evidence = [
        evidence
        for link, evidence in evidence_links
        if link.relationship_type in {"supports", "documents", "measurement"} and _evidence_relevant(issue, evidence)
    ]
    relevant_visual = [item for item in relevant_evidence if item.kind in {"photo", "video", "scan"}]
    measurements = [
        structured
        for item in relevant_evidence
        if item.kind == "measurement" and (structured := _structured_measurement(item, approved_revision_ids))
    ]

    missing: list[str] = []
    if not issue.location_json:
        missing.append("Exact floor/room/plan location")
    if not issue.observed_condition.strip():
        missing.append("Explicit observed condition")
    if not issue.expected_condition.strip():
        missing.append("Explicit expected condition")
    if not relevant_visual:
        missing.append("Location-matched field photo or video relevant to this issue")
    if not approved_sources:
        missing.append("Relevant current approved drawing/specification source")
    measurement_required = issue.issue_type in {
        "quality_defect", "field_deviation", "clearance_conflict", "missing_installation"
    }
    if measurement_required and not measurements:
        missing.append("Structured measurement bound to the approved source requirement")

    issue.missing_evidence = missing
    issue.evidence_sufficiency = "sufficient" if not missing else "insufficient"
    authorization_sources = [
        (link, document)
        for link, _revision, document in approved_sources
        if link.relationship_type == "authorization"
        and document.kind in {"rfi_response", "change_directive", "change_order"}
    ]
    violating = [item for item in measurements if item["violates"]]
    if not missing and violating:
        issue.classification = "unapproved_deviation"
        issue.recommended_action = "field_correction"
    elif not missing and authorization_sources:
        issue.classification = "approved_field_change"
        issue.recommended_action = "model_update_request"
    else:
        issue.classification = "insufficient_evidence" if missing else "potential_mismatch"
        issue.recommended_action = "additional_evidence_required" if missing else "review_required"

    issue.status = (
        "ready_for_review"
        if issue.evidence_sufficiency == "sufficient" and issue.classification in ACTIONABLE_CLASSIFICATIONS
        else "evidence_required"
    )
    issue.approved_by = None
    issue.approved_at = None
    issue.verification_json = {
        "schema": "buili.issue-verification.v2",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "linked_evidence_ids": sorted(evidence.id for _link, evidence in evidence_links),
        "relevant_evidence_ids": sorted(evidence.id for evidence in relevant_evidence),
        "linked_source_revision_ids": sorted(revision.id for _link, revision, _document in source_rows),
        "approved_relevant_source_revision_ids": sorted(approved_revision_ids),
        "source_hashes": {revision.id: revision.sha256 for _link, revision, _document in approved_sources},
        "structured_measurements": measurements,
        "blocking_reasons": missing,
    }
    await session.flush()
    return {
        "issue_id": issue.id,
        "evidence_count": len(evidence_links),
        "source_count": len(source_rows),
        "evidence_sufficiency": issue.evidence_sufficiency,
        "missing_evidence": issue.missing_evidence,
        "classification": issue.classification,
        "recommended_action": issue.recommended_action,
        "verification": issue.verification_json,
    }


def approval_blockers(issue: Issue) -> list[str]:
    blockers: list[str] = []
    verification = issue.verification_json or {}
    if issue.evidence_sufficiency != "sufficient":
        blockers.append("evidence sufficiency is not sufficient")
    if issue.status != "ready_for_review":
        blockers.append("issue is not ready for review")
    if issue.classification not in ACTIONABLE_CLASSIFICATIONS:
        blockers.append("classification is not eligible for approval")
    if verification.get("schema") != "buili.issue-verification.v2":
        blockers.append("current verification run is missing")
    if verification.get("blocking_reasons"):
        blockers.append("verification contains blocking reasons")
    if not verification.get("approved_relevant_source_revision_ids"):
        blockers.append("no current approved relevant source is bound")
    return blockers
