"""Generate synthetic, traceable PDF artifacts for the BUILI demo persona.

The files are intentionally generated from source so the visual template and
the contractual note can be reviewed, versioned, and reproduced.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import TABLOID, letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "buili_demo_evidence"
OUT = ROOT / "output" / "pdf"
GREEN = colors.HexColor("#50C878")
GREEN_DARK = colors.HexColor("#167A47")
INK = colors.HexColor("#17211B")
MUTED = colors.HexColor("#69736D")
LINE = colors.HexColor("#DDE5E0")
PALE = colors.HexColor("#EFF9F3")


def _drawing_pdf(path: Path) -> None:
    width, height = landscape(TABLOID)
    c = canvas.Canvas(str(path), pagesize=(width, height), pageCompression=1)
    margin = 0.42 * inch
    title_h = 0.76 * inch

    c.setFillColor(colors.white)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#AAB4AE"))
    c.setLineWidth(0.7)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin, fill=0, stroke=1)

    # Sheet header
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(margin + 14, height - margin - 24, "COOPER RESIDENCE RENOVATION")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(margin + 14, height - margin - 39, "GARAGE ELECTRICAL PLAN - DEMO CONTRACT DOCUMENT")
    c.setStrokeColor(GREEN)
    c.setLineWidth(3)
    c.line(margin, height - margin - title_h, width - margin, height - margin - title_h)

    # Plan area
    plan_x = margin + 0.42 * inch
    plan_y = margin + 1.22 * inch
    plan_w = 10.3 * inch
    plan_h = 4.35 * inch
    c.setStrokeColor(INK)
    c.setLineWidth(2.8)
    c.rect(plan_x, plan_y, plan_w, plan_h, fill=0, stroke=1)

    # Garage door and entry door
    c.setLineWidth(0.8)
    c.setDash(4, 3)
    c.line(plan_x + 1.15 * inch, plan_y, plan_x + 7.8 * inch, plan_y)
    c.setDash()
    entry_y = plan_y + 0.68 * inch
    c.setFillColor(colors.white)
    c.rect(plan_x + plan_w - 3, entry_y, 6, 1.15 * inch, fill=1, stroke=0)
    c.setStrokeColor(INK)
    c.line(plan_x + plan_w, entry_y, plan_x + plan_w - 0.86 * inch, entry_y)
    c.arc(plan_x + plan_w - 1.72 * inch, entry_y, plan_x + plan_w, entry_y + 1.72 * inch, 270, 90)

    # Receptacle symbol and callout on east wall
    gx = plan_x + plan_w - 0.06 * inch
    gy = plan_y + 2.2 * inch
    c.setStrokeColor(GREEN_DARK)
    c.setFillColor(colors.white)
    c.setLineWidth(1.5)
    c.circle(gx, gy, 8, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(GREEN_DARK)
    c.drawCentredString(gx, gy - 2.5, "G")
    c.setStrokeColor(GREEN_DARK)
    c.setLineWidth(0.8)
    c.line(gx - 8, gy, plan_x + 8.55 * inch, plan_y + 3.25 * inch)
    c.setFillColor(PALE)
    c.roundRect(plan_x + 7.0 * inch, plan_y + 3.1 * inch, 1.55 * inch, 0.34 * inch, 4, fill=1, stroke=0)
    c.setFillColor(GREEN_DARK)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(plan_x + 7.12 * inch, plan_y + 3.23 * inch, "GFCI - SEE NOTE 3")

    # Plan labels and dimensions
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 19)
    c.drawCentredString(plan_x + plan_w / 2, plan_y + plan_h / 2, "GARAGE")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawCentredString(plan_x + plan_w / 2, plan_y + plan_h / 2 - 18, "EAST WALL AT ENTRY DOOR")
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(INK)
    c.drawString(plan_x + plan_w + 8, entry_y + 0.47 * inch, "ENTRY")

    # General notes panel
    notes_x = plan_x + plan_w + 0.45 * inch
    notes_y = plan_y + 0.7 * inch
    notes_w = width - margin - notes_x - 0.25 * inch
    notes_h = 3.7 * inch
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(notes_x, notes_y + notes_h, "ELECTRICAL NOTES")
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.line(notes_x, notes_y + notes_h - 8, notes_x + notes_w, notes_y + notes_h - 8)

    notes = [
        "1. VERIFY ALL DEVICE LOCATIONS WITH OWNER PRIOR TO ROUGH-IN.",
        "2. PROVIDE GFCI PROTECTION FOR RECEPTACLES IN GARAGE AREAS.",
        "3. GARAGE RECEPTACLE BOX CENTERLINES SHALL BE MOUNTED 18 INCHES MINIMUM ABOVE FINISHED FLOOR UNLESS NOTED OTHERWISE.",
        "4. COORDINATE DEVICE LOCATIONS WITH DOOR TRIM AND BUILT-IN WORK.",
    ]
    ty = notes_y + notes_h - 29
    for index, note in enumerate(notes, 1):
        if index == 3:
            c.setFillColor(PALE)
            c.roundRect(notes_x - 6, ty - 25, notes_w + 8, 42, 4, fill=1, stroke=0)
            c.setStrokeColor(GREEN)
            c.setLineWidth(2)
            c.line(notes_x - 6, ty - 25, notes_x - 6, ty + 17)
            c.setFillColor(GREEN_DARK)
        else:
            c.setFillColor(INK)
        words = note.split()
        line = ""
        lines: list[str] = []
        for word in words:
            candidate = f"{line} {word}".strip()
            if stringWidth(candidate, "Helvetica", 7.6) > notes_w - 8:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        c.setFont("Helvetica-Bold" if index == 3 else "Helvetica", 7.6)
        for row in lines:
            c.drawString(notes_x, ty, row)
            ty -= 11
        ty -= 10

    # Bottom title block
    block_y = margin
    c.setStrokeColor(colors.HexColor("#AAB4AE"))
    c.setLineWidth(0.7)
    c.line(margin, block_y + 0.68 * inch, width - margin, block_y + 0.68 * inch)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin + 12, block_y + 29, "NORTHSTAR BUILDERS")
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawString(margin + 12, block_y + 16, "Synthetic demo document - not for construction")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(width - margin - 12, block_y + 26, "E1.1")
    c.setFont("Helvetica", 6.8)
    c.setFillColor(MUTED)
    c.drawRightString(width - margin - 12, block_y + 13, "REV 2  |  2026-07-09  |  ISSUED FOR REVIEW")
    c.save()


def _report_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=24,
            leading=28, textColor=INK, spaceAfter=8,
        ),
        "eyebrow": ParagraphStyle(
            "eyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8,
            leading=10, textColor=GREEN_DARK, spaceAfter=5,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11,
            leading=14, textColor=INK, spaceBefore=13, spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Helvetica", fontSize=9,
            leading=14, textColor=INK,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5,
            leading=11, textColor=MUTED,
        ),
        "label": ParagraphStyle(
            "label", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7,
            leading=9, textColor=MUTED,
        ),
    }


def _footer(canvas_obj: canvas.Canvas, doc: SimpleDocTemplate) -> None:
    canvas_obj.saveState()
    width, _ = letter
    canvas_obj.setStrokeColor(LINE)
    canvas_obj.line(doc.leftMargin, 0.46 * inch, width - doc.rightMargin, 0.46 * inch)
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColor(MUTED)
    canvas_obj.drawString(doc.leftMargin, 0.28 * inch, "BUILI | Source-cited issue package | Demo")
    canvas_obj.drawRightString(width - doc.rightMargin, 0.28 * inch, f"Page {doc.page}")
    canvas_obj.restoreState()


def _issue_pdf(path: Path) -> None:
    styles = _report_styles()
    doc = SimpleDocTemplate(
        str(path), pagesize=letter, rightMargin=0.58 * inch, leftMargin=0.58 * inch,
        topMargin=0.54 * inch, bottomMargin=0.62 * inch,
        title="BUI-1042 Issue Package",
        author="BUILI",
    )
    story = []
    header = Table(
        [[Paragraph("<b>BUILI</b>", styles["body"]), Paragraph("READY FOR REVIEW", styles["eyebrow"])]],
        colWidths=[5.5 * inch, 1.2 * inch],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("LINEBELOW", (0, 0), (-1, -1), 2, GREEN),
    ]))
    story.extend([
        header,
        Spacer(1, 0.2 * inch),
        Paragraph("CONSTRUCTION VERIFICATION / BUI-1042", styles["eyebrow"]),
        Paragraph("Garage GFCI receptacle below required elevation", styles["title"]),
        Paragraph(
            "Cooper Residence Renovation / Garage east wall at entry door / Electrical rough-in",
            styles["small"],
        ),
        Spacer(1, 0.18 * inch),
    ])

    summary_data = [
        [Paragraph("OBSERVED", styles["label"]), Paragraph("REQUIRED", styles["label"]), Paragraph("DIFFERENCE", styles["label"])],
        [Paragraph("12 in AFF", styles["body"]), Paragraph("18 in AFF minimum", styles["body"]), Paragraph("6 in below minimum", styles["body"])],
    ]
    summary = Table(summary_data, colWidths=[2.16 * inch] * 3)
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("TEXTCOLOR", (0, 1), (-1, 1), INK),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("LINEAFTER", (0, 0), (1, -1), 0.5, colors.HexColor("#C8DDD0")),
    ]))
    story.extend([
        summary,
        Paragraph("Verification finding", styles["h2"]),
        Paragraph(
            "Field evidence confirms that the GFCI receptacle box centerline is 12 inches above the finished floor. "
            "The current approved source, E1.1 Rev 2 Electrical Note 3, requires garage receptacle box centerlines "
            "to be at least 18 inches above finished floor unless noted otherwise.",
            styles["body"],
        ),
        Paragraph("Recommended route", styles["h2"]),
    ])

    action = Table(
        [[Paragraph("FIELD CORRECTION / PUNCH", styles["eyebrow"]), Paragraph("Raise box before wall close-in. RFI is not required unless a reviewer identifies a conflicting approved source.", styles["body"])]],
        colWidths=[1.72 * inch, 4.76 * inch],
    )
    action.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LINEBEFORE", (0, 0), (0, 0), 3, GREEN),
    ]))
    story.extend([action, Paragraph("Field evidence", styles["h2"])])

    image_paths = [
        DEMO / "garage-east-wall-context-thumb.webp",
        DEMO / "box-elevation-measurement-thumb.webp",
        DEMO / "receptacle-rough-in-detail-thumb.webp",
    ]
    image_cells = []
    caption_cells = []
    captions = ["Context", "Tape measurement", "Installation detail"]
    for source, caption in zip(image_paths, captions):
        img = Image(str(source), width=2.08 * inch, height=1.56 * inch, kind="proportional")
        image_cells.append(img)
        caption_cells.append(Paragraph(caption, styles["small"]))
    evidence = Table([image_cells, caption_cells], colWidths=[2.16 * inch] * 3)
    evidence.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
    ]))
    story.extend([
        evidence,
        Paragraph("Source citation", styles["h2"]),
        Paragraph(
            "E1.1 Rev 2, Electrical Note 3: GARAGE RECEPTACLE BOX CENTERLINES SHALL BE MOUNTED 18 INCHES MINIMUM ABOVE FINISHED FLOOR UNLESS NOTED OTHERWISE.",
            styles["body"],
        ),
        PageBreak(),
        Paragraph("Evidence sufficiency", styles["h2"]),
    ])

    checks = [
        ["Location", "Garage east wall at entry door", "Verified"],
        ["Context photo", "Whole stud bay and adjacent entry", "Verified"],
        ["Measurement", "Tape from floor to centerline", "Verified"],
        ["Approved requirement", "E1.1 Rev 2, Note 3", "Verified"],
    ]
    check_table = Table(
        [[Paragraph("CHECK", styles["label"]), Paragraph("EVIDENCE", styles["label"]), Paragraph("STATUS", styles["label"])]]
        + [[Paragraph(a, styles["small"]), Paragraph(b, styles["small"]), Paragraph(c, styles["eyebrow"])] for a, b, c in checks],
        colWidths=[1.25 * inch, 4.35 * inch, 0.88 * inch],
    )
    check_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([
        check_table,
        Spacer(1, 0.24 * inch),
        Paragraph("FIELD NOTE / 2026-07-12 10:18", styles["eyebrow"]),
        Paragraph("Foreman observation", styles["title"]),
        Paragraph(
            "Mike Alvarez reported that the GFCI box shown on E1.1 is installed with its centerline at 12 inches above the floor. "
            "He left the stud bay open, tagged the location, and uploaded context, detail, and tape-measurement photos before close-in.",
            styles["body"],
        ),
        Paragraph("Review decision", styles["h2"]),
        Paragraph(
            "The requirement and measurement are both directly evidenced. Route to Delta Electrical for correction and require an after-correction photo. "
            "Escalate to an RFI only if another approved detail conflicts with Note 3 or field conditions prevent the documented elevation.",
            styles["body"],
        ),
        Paragraph("Approval trail", styles["h2"]),
    ])
    audit_rows = [
        ["10:18", "Mike Alvarez", "Uploaded three photos and voice note"],
        ["10:19", "BUILI", "Localized to garage east wall / entry door"],
        ["10:20", "BUILI", "Matched E1.1 Rev 2 Electrical Note 3"],
        ["10:20", "BUILI", "Classified unapproved deviation; evidence sufficient"],
        ["Pending", "Jordan Cho", "Approve, edit, or request additional evidence"],
    ]
    audit = Table(
        [[Paragraph("TIME", styles["label"]), Paragraph("ACTOR", styles["label"]), Paragraph("EVENT", styles["label"])]]
        + [[Paragraph(a, styles["small"]), Paragraph(b, styles["small"]), Paragraph(c, styles["small"])] for a, b, c in audit_rows],
        colWidths=[0.75 * inch, 1.3 * inch, 4.43 * inch],
    )
    audit.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([
        audit,
        Spacer(1, 0.28 * inch),
        Paragraph("Reviewer", styles["label"]),
        Spacer(1, 0.28 * inch),
        Table([["Jordan Cho", "Decision", "Date"]], colWidths=[2.16 * inch] * 3, style=TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
            ("TEXTCOLOR", (0, 0), (-1, -1), MUTED),
            ("LINEABOVE", (0, 0), (-1, -1), 0.7, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ])),
    ])
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    drawing = OUT / "cooper-residence-E1.1-demo.pdf"
    _drawing_pdf(drawing)
    (DEMO / drawing.name).write_bytes(drawing.read_bytes())
    # Keep one report renderer as the design and traceability authority.
    from generate_production_demo_report import main as generate_report

    generate_report()
    print(drawing)


if __name__ == "__main__":
    main()
