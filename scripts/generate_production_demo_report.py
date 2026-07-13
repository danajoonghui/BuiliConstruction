"""Generate the complete, checked-in BUILI demo report portfolio.

The renderer uses original BUILI templates.  The field set follows current
Autodesk Build and Procore operational records, while every demo value remains
synthetic and source-traceable.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from buili_api.services.report_rendering import (  # noqa: E402
    TEMPLATE_VERSION,
    ReportContext,
    ReportEvidence,
    ReportSource,
    render_docx,
    render_pdf,
    validate_report_context,
)


DEMO = ROOT / "buili_demo_evidence"
PUBLIC = ROOT / "apps" / "web" / "public" / "demo"
OUTPUT = ROOT / "output" / "pdf"
GENERATED_AT = datetime(2026, 7, 12, 17, 25, tzinfo=timezone.utc)


def _sha(file_name: str) -> str:
    return hashlib.sha256((DEMO / file_name).read_bytes()).hexdigest()


def _source(sheet: str, title: str, quote: str, relationship: str = "requirement") -> ReportSource:
    filename = f"cooper-residence-{sheet}-demo.pdf"
    return ReportSource(
        index=1,
        revision_id=f"rev_demo_{sheet.lower().replace('.', '')}_03",
        document_title=title,
        sheet_number=sheet,
        revision="03",
        status="approved",
        page=1,
        quote=quote,
        relationship_type=relationship,
        sha256=_sha(filename),
    )


def _field_evidence() -> list[ReportEvidence]:
    records = [
        ("evd_demo_context", "photo", "Garage east wall context", "Open stud wall near the garage entry door; GFCI rough-in visible.", "garage-east-wall-context.png", "2026-07-12T10:18:00-07:00"),
        ("evd_demo_measurement", "measurement", "GFCI centerline tape measurement", "Tape shows receptacle centerline at approximately 12 inches AFF.", "box-elevation-measurement.png", "2026-07-12T10:18:20-07:00"),
        ("evd_demo_detail", "photo", "Receptacle rough-in detail", "Close view of the installed box before wall close-in.", "receptacle-rough-in-detail.png", "2026-07-12T10:18:38-07:00"),
    ]
    return [
        ReportEvidence(
            id=record_id,
            kind=kind,
            title=title,
            description=description,
            transcript="",
            captured_at=captured_at,
            location="Residence / Garage / East wall / Entry door",
            image_bytes=(DEMO / filename).read_bytes(),
        )
        for record_id, kind, title, description, filename, captured_at in records
    ]


def _base(**overrides) -> ReportContext:
    context = ReportContext(
        report_id="rpt_demo_bui_1042",
        version=1,
        kind="evidence_package",
        title="Garage GFCI receptacle below required elevation",
        status="draft",
        generated_at=GENERATED_AT,
        project_name="Cooper Residence Renovation",
        project_code="CR-2026-017",
        project_address="Santa Clara, CA",
        issue_number="BUI-1042",
        issue_status="ready_for_review",
        issue_type="quality_defect",
        priority="high",
        classification="unapproved_deviation",
        recommended_action="field_correction_punch",
        evidence_sufficiency="sufficient",
        location="Residence / Garage / East wall / Entry door",
        observed_condition="GFCI box centerline measures 12 inches above finished floor at the garage east wall.",
        expected_condition="E1.1 Electrical Note 3 requires garage receptacle centerline at a minimum 18 inches AFF.",
        difference="Installed centerline is 6 inches below the explicit approved drawing requirement.",
        evidence=_field_evidence(),
        sources=[_source("E1.1", "Electrical Power and Lighting Plan", "Electrical Note 3: Garage receptacle centerline shall be minimum 18 inches above finished floor.")],
        prepared_by="Jordan Cho / Project Manager",
    )
    return replace(context, **overrides)


def portfolio() -> list[tuple[str, ReportContext]]:
    issue_package = _base()
    punch = _base(
        report_id="rpt_demo_p024",
        kind="punch_item",
        issue_number="P-024",
        title="Raise garage GFCI rough-in before wall close-in",
        issue_status="open",
        responsible_party="Delta Electrical",
        final_approver="Jordan Cho / Project Manager",
        due_date="2026-07-14",
        required_action="Relocate the box so its centerline is at least 18 inches AFF before gypsum board installation.",
        completion_requirement="Provide a completion photo showing the full wall context and a readable tape measurement from finished floor to box centerline.",
        activity_log=[
            {"timestamp":"2026-07-12 10:18 PDT","actor":"Mike Alvarez","event":"Field observation and three evidence assets captured."},
            {"timestamp":"2026-07-12 10:24 PDT","actor":"BUILI","event":"E1.1 Rev 03 requirement linked; evidence package marked sufficient."},
        ],
    )
    rfi_partition = _base(
        report_id="rpt_demo_rfi018",
        kind="rfi",
        issue_number="RFI-018",
        title="Office partition dimension conflict at grid C",
        issue_status="draft",
        priority="normal",
        classification="design_inconsistency",
        recommended_action="designer_clarification",
        evidence_sufficiency="partial",
        location="Residence / Office / Grid C",
        observed_condition="A1.1 locates the office partition from the exterior face, while Detail 4/A5.2 dimensions the same partition from the structural grid.",
        expected_condition="One controlling dimension is required before layout proceeds.",
        difference="The two references produce a 76 mm difference in partition location.",
        evidence=[],
        sources=[_source("A1.1", "Ground Floor Architectural Plan", "Office partition is dimensioned from the west exterior wall face.")],
        ball_in_court="Studio North Architects",
        due_date="2026-07-16",
        question="Please confirm the controlling reference for the office partition and provide the approved offset from grid C.",
        suggested_answer="Use the grid-based dimension shown in the enlarged detail, subject to architect confirmation.",
        cost_impact="Unknown - layout hold only",
        schedule_impact="Two working days if unanswered after July 16",
    )
    rfi_hvac = _base(
        report_id="rpt_demo_rfi017",
        kind="rfi",
        issue_number="RFI-017",
        title="Return-air route at hall opening",
        issue_status="issued",
        priority="high",
        classification="coordination_conflict",
        recommended_action="designer_clarification",
        evidence_sufficiency="partial",
        location="Residence / Hall ceiling / Opening H-2",
        observed_condition="The M1.1 return-air route crosses the framed opening clearance zone at the hall.",
        expected_condition="The return-air path must preserve the approved opening and the scheduled airflow area.",
        difference="The plan route and architectural opening occupy the same coordination zone; elevation information is not stated on plan.",
        evidence=[],
        sources=[_source("M1.1", "HVAC Distribution Plan", "Return-air branch RA-2 passes through the hall coordination zone.")],
        ball_in_court="Vector MEP / Mechanical Engineer",
        due_date="2026-07-14",
        question="Please provide the approved elevation and routing for RA-2 at opening H-2, or confirm an alternate route above the laundry ceiling.",
        suggested_answer="Route above the laundry ceiling with the same free area, subject to engineer approval and fire-rating review.",
        official_response="Pending",
        cost_impact="To be determined",
        schedule_impact="Ceiling framing hold in the hall",
        activity_log=[{"timestamp":"2026-07-11 15:42 PDT","actor":"Jordan Cho","event":"RFI issued to Vector MEP with A1.1 and M1.1 references."}],
    )
    change = _base(
        report_id="rpt_demo_ce007",
        kind="change_event",
        issue_number="CE-007",
        title="Existing footing discovered below new laundry wall",
        issue_status="evidence_collecting",
        priority="high",
        classification="existing_condition_conflict",
        recommended_action="potential_change_event",
        evidence_sufficiency="partial",
        location="Residence / Laundry / South wall",
        observed_condition="Selective demolition exposed an undocumented concrete footing within the new plumbing trench alignment.",
        expected_condition="A1.1 indicates a clear trench path for the new laundry waste line.",
        difference="The concealed footing requires a revised route or engineered penetration and was not shown in the bid documents.",
        evidence=[],
        sources=[_source("A1.1", "Ground Floor Architectural Plan", "Laundry plumbing route is coordinated through the south wall zone.", "original_scope")],
        origin="Field observation BUI-1034",
        change_reason="Unforeseen existing condition",
        scope="TBD - outside original documented condition",
        cost_impact="$3,850 ROM pending subcontractor quote",
        schedule_impact="One working day trench hold; no critical-path impact if direction is received by July 15",
        line_items=[
            {"cost_code":"02-4119","description":"Selective demolition and footing exposure","quantity":6,"unit":"labor hr","rom":"$720"},
            {"cost_code":"22-1316","description":"Re-route laundry waste line","quantity":1,"unit":"lot","rom":"$3,130"},
        ],
        activity_log=[
            {"timestamp":"2026-07-10 08:05 PDT","actor":"Northstar field team","event":"Footing exposed during selective demolition."},
            {"timestamp":"2026-07-10 08:22 PDT","actor":"Jordan Cho","event":"Work in trench zone held and designer notified."},
        ],
    )
    daily = _base(
        report_id="rpt_demo_daily_20260712",
        kind="daily_report",
        issue_number="DR-2026-07-12",
        title="Daily field report - electrical rough-in",
        issue_status="complete",
        priority="normal",
        classification="daily_record",
        recommended_action="observation_only",
        evidence_sufficiency="sufficient",
        location="Cooper Residence / Ground floor",
        observed_condition="Garage GFCI elevation was documented and routed to punch before wall close-in.",
        expected_condition="Electrical rough-in inspection remains scheduled for July 14.",
        difference="No project-wide delay recorded; one localized correction remains open.",
        sources=[],
        report_date="2026-07-12",
        weather="Clear, 72-84 °F; dry access and no weather delay.",
        work_completed="Electrical branch rough-in at garage and living areas; laundry supply rough-in; office partition layout verification.",
        safety_summary="Pre-task plan completed. No incidents, near misses, or failed inspections reported.",
        manpower=[
            {"company":"Northstar Builders","trade":"General","workers":3,"hours":24},
            {"company":"Delta Electrical","trade":"Electrical","workers":4,"hours":32},
            {"company":"ClearFlow Plumbing","trade":"Plumbing","workers":2,"hours":16},
        ],
        activity_log=[
            {"timestamp":"07:00 PDT","actor":"Mike Alvarez","event":"Daily huddle and pre-task plan completed."},
            {"timestamp":"10:18 PDT","actor":"Mike Alvarez","event":"GFCI elevation evidence captured in garage."},
            {"timestamp":"15:30 PDT","actor":"Jordan Cho","event":"Daily report reviewed and marked complete."},
        ],
    )
    return [
        ("BUI-1042-issue-package", issue_package),
        ("P-024-punch-item", punch),
        ("RFI-018-partition-dimension", rfi_partition),
        ("RFI-017-hvac-route", rfi_hvac),
        ("CE-007-existing-footing", change),
        ("DR-2026-07-12-daily-report", daily),
    ]


def main() -> None:
    for directory in (DEMO, PUBLIC, OUTPUT):
        directory.mkdir(parents=True, exist_ok=True)
    manifest = {"template_version": TEMPLATE_VERSION, "generated_at": GENERATED_AT.isoformat(), "reports": []}
    for stem, context in portfolio():
        missing = validate_report_context(context)
        if missing:
            raise ValueError(f"{stem} is missing required fields: {', '.join(missing)}")
        pdf = render_pdf(context)
        docx = render_docx(context)
        for directory in (DEMO, PUBLIC, OUTPUT):
            (directory / f"{stem}.pdf").write_bytes(pdf)
            (directory / f"{stem}.docx").write_bytes(docx)
        manifest["reports"].append(
            {
                "id": context.issue_number,
                "kind": context.kind,
                "title": context.title,
                "status": context.issue_status,
                "pdf": f"/demo/{stem}.pdf",
                "docx": f"/demo/{stem}.docx",
                "sha256": hashlib.sha256(pdf).hexdigest(),
            }
        )
    manifest_payload = json.dumps(manifest, indent=2) + "\n"
    for directory in (DEMO, PUBLIC, OUTPUT):
        (directory / "report-portfolio.json").write_text(manifest_payload, encoding="utf-8")
    print(f"Generated {len(manifest['reports'])} report families with {TEMPLATE_VERSION}")


if __name__ == "__main__":
    main()
