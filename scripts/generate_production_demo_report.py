"""Regenerate the checked-in demo issue package with the production renderer."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from buili_api.services.report_rendering import (  # noqa: E402
    ReportContext,
    ReportEvidence,
    ReportSource,
    render_docx,
    render_pdf,
)


DEMO = ROOT / "buili_demo_evidence"
OUTPUT = ROOT / "output" / "pdf"


def context() -> ReportContext:
    drawing = DEMO / "cooper-residence-E1.1-demo.pdf"
    evidence = [
        ReportEvidence(
            id="evd_demo_context",
            kind="photo",
            title="Garage east wall context",
            description="Open stud wall near the garage entry door; GFCI rough-in visible.",
            transcript="",
            captured_at="2026-07-12T10:18:00-07:00",
            location="Building: Residence / Space: Garage / Wall: East wall / Near: Entry door",
            image_bytes=(DEMO / "garage-east-wall-context.png").read_bytes(),
        ),
        ReportEvidence(
            id="evd_demo_measurement",
            kind="measurement",
            title="GFCI centerline tape measurement",
            description="Tape shows receptacle centerline at approximately 12 inches AFF.",
            transcript="",
            captured_at="2026-07-12T10:18:20-07:00",
            location="Building: Residence / Space: Garage / Wall: East wall / Near: Entry door",
            image_bytes=(DEMO / "box-elevation-measurement.png").read_bytes(),
        ),
        ReportEvidence(
            id="evd_demo_detail",
            kind="photo",
            title="Receptacle rough-in detail",
            description="Close view of the installed box before wall close-in.",
            transcript="",
            captured_at="2026-07-12T10:18:38-07:00",
            location="Building: Residence / Space: Garage / Wall: East wall / Near: Entry door",
            image_bytes=(DEMO / "receptacle-rough-in-detail.png").read_bytes(),
        ),
    ]
    return ReportContext(
        report_id="rpt_demo_bui_1042",
        version=1,
        kind="evidence_package",
        title="Garage GFCI receptacle below required elevation",
        status="draft",
        generated_at=datetime(2026, 7, 12, 17, 25, tzinfo=timezone.utc),
        project_name="Cooper Residence Renovation",
        project_code="CR-2026-017",
        project_address="San Jose, CA",
        issue_number="BUI-1042",
        issue_status="ready_for_review",
        issue_type="quality_defect",
        priority="high",
        classification="unapproved_deviation",
        recommended_action="field_correction_punch",
        evidence_sufficiency="sufficient",
        location="Building: Residence / Space: Garage / Wall: East wall / Near: Entry door",
        observed_condition="GFCI box centerline measures 12 inches above finished floor at the garage east wall.",
        expected_condition="E1.1 Electrical Note 3 requires garage receptacle centerline at a minimum 18 inches AFF.",
        difference="Installed centerline is 6 inches below the explicit approved drawing requirement.",
        evidence=evidence,
        sources=[
            ReportSource(
                index=1,
                revision_id="rev_demo_e11_ifc1",
                document_title="Electrical Power Plan E1.1",
                sheet_number="E1.1",
                revision="IFC-1",
                status="approved",
                page=1,
                quote="Electrical Note 3: Garage receptacle centerline shall be minimum 18 inches above finished floor.",
                relationship_type="requirement",
                sha256=hashlib.sha256(drawing.read_bytes()).hexdigest(),
            )
        ],
    )


def main() -> None:
    payload = context()
    pdf = render_pdf(payload)
    docx = render_docx(payload)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for directory in (DEMO, OUTPUT):
        (directory / "BUI-1042-issue-package.pdf").write_bytes(pdf)
        (directory / "BUI-1042-issue-package.docx").write_bytes(docx)
    print(DEMO / "BUI-1042-issue-package.pdf")
    print(DEMO / "BUI-1042-issue-package.docx")


if __name__ == "__main__":
    main()
