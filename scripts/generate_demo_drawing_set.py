"""Generate a coherent multi-discipline drawing set and review GLB for the demo.

The sheets are synthetic contract-style documents, but every discipline uses
the same calibrated CAD coordinate system. Architecture, electrical, and
mechanical overlays are intentionally different and remain traceable to the
generated PlanGraph and GLB artifacts.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import TABLOID, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from buili_spatial.contracts import finalize_plan_graph_payload
from buili_spatial.geometry import build_design_glb


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "buili_demo_evidence"
WEB = ROOT / "apps" / "web" / "public" / "demo"
GENERATED = ROOT / "output" / "generated_spatial"

INK = colors.HexColor("#18201B")
MUTED = colors.HexColor("#69736D")
LINE = colors.HexColor("#AEB8B2")
GREEN = colors.HexColor("#2E8B57")
BLUE = colors.HexColor("#2468B4")
ORANGE = colors.HexColor("#C8792E")
PALE = colors.HexColor("#F3F7F4")


ROOMS = [
    ("garage", "GARAGE", 0.0, 0.0, 5.4, 5.8),
    ("entry", "ENTRY", 5.4, 0.0, 7.3, 2.4),
    ("laundry", "LAUNDRY", 5.4, 2.4, 7.3, 5.8),
    ("kitchen", "KITCHEN", 7.3, 2.4, 11.4, 5.8),
    ("living", "LIVING ROOM", 11.4, 0.0, 15.0, 5.8),
    ("bedroom_1", "BEDROOM 1", 0.0, 5.8, 5.4, 10.0),
    ("hall", "HALL", 5.4, 5.8, 7.3, 7.2),
    ("bath", "BATH", 5.4, 7.2, 7.3, 10.0),
    ("bedroom_2", "BEDROOM 2", 7.3, 5.8, 11.2, 10.0),
    ("office", "OFFICE", 11.2, 5.8, 15.0, 10.0),
]

WALLS = [
    ("w_south", [0.0, 0.0], [15.0, 0.0], 0.22),
    ("w_east", [15.0, 0.0], [15.0, 10.0], 0.22),
    ("w_north", [15.0, 10.0], [0.0, 10.0], 0.22),
    ("w_west", [0.0, 10.0], [0.0, 0.0], 0.22),
    ("w_v1", [5.4, 0.0], [5.4, 10.0], 0.13),
    ("w_v2", [7.3, 0.0], [7.3, 10.0], 0.13),
    ("w_v3_s", [11.4, 0.0], [11.4, 5.8], 0.13),
    ("w_v3_n", [11.2, 5.8], [11.2, 10.0], 0.13),
    ("w_h1", [0.0, 5.8], [15.0, 5.8], 0.13),
    ("w_h2", [5.4, 2.4], [11.4, 2.4], 0.13),
    ("w_h3", [5.4, 7.2], [7.3, 7.2], 0.13),
]

OPENINGS = [
    ("garage_door", "door", "w_south", [2.7, 0.0], 4.2, 2.35, 0.0),
    ("entry_door", "door", "w_south", [6.35, 0.0], 0.95, 2.1, 0.0),
    ("living_slider", "door", "w_east", [15.0, 2.9], 2.2, 2.2, 0.0),
    ("bedroom_window", "window", "w_north", [2.7, 10.0], 1.8, 1.25, 0.9),
    ("bath_window", "window", "w_north", [6.35, 10.0], 0.9, 0.8, 1.3),
    ("bedroom_2_window", "window", "w_north", [9.2, 10.0], 1.6, 1.25, 0.9),
    ("office_window", "window", "w_north", [13.0, 10.0], 1.6, 1.25, 0.9),
    ("garage_to_entry", "door", "w_v1", [5.4, 1.35], 0.9, 2.1, 0.0),
    ("laundry_door", "door", "w_v1", [5.4, 4.4], 0.82, 2.1, 0.0),
    ("hall_door", "door", "w_v2", [7.3, 6.5], 0.9, 2.1, 0.0),
    ("kitchen_opening", "door", "w_v2", [7.3, 4.0], 1.4, 2.4, 0.0),
    ("living_opening", "door", "w_v3_s", [11.4, 3.8], 1.8, 2.4, 0.0),
    ("office_door", "door", "w_v3_n", [11.2, 6.7], 0.9, 2.1, 0.0),
    ("bedroom_1_door", "door", "w_h1", [4.4, 5.8], 0.9, 2.1, 0.0),
    ("bedroom_2_door", "door", "w_h1", [8.2, 5.8], 0.9, 2.1, 0.0),
    ("bath_door", "door", "w_h3", [6.35, 7.2], 0.8, 2.1, 0.0),
]

ARCH_FIXTURES = [
    ("kitchen_island", "casework", "kitchen", [9.4, 4.1]),
    ("kitchen_sink", "sink", "kitchen", [10.7, 5.25]),
    ("bath_vanity", "vanity", "bath", [6.7, 8.9]),
    ("laundry_casework", "casework", "laundry", [6.6, 3.1]),
]

ELECTRICAL_FIXTURES = [
    ("panel_ep1", "electrical_panel", "garage", [0.45, 3.2]),
    ("gfci_issue", "receptacle", "garage", [5.18, 2.15]),
    ("garage_light_1", "ceiling_light", "garage", [1.8, 2.0]),
    ("garage_light_2", "ceiling_light", "garage", [3.7, 2.0]),
    ("entry_light", "ceiling_light", "entry", [6.35, 1.25]),
    ("kitchen_light_1", "ceiling_light", "kitchen", [8.5, 4.0]),
    ("kitchen_light_2", "ceiling_light", "kitchen", [10.2, 4.0]),
    ("living_light_1", "ceiling_light", "living", [12.5, 2.5]),
    ("living_light_2", "ceiling_light", "living", [14.0, 3.8]),
    ("bedroom_1_light", "ceiling_light", "bedroom_1", [2.7, 7.8]),
    ("bedroom_2_light", "ceiling_light", "bedroom_2", [9.2, 7.8]),
    ("office_light", "ceiling_light", "office", [13.1, 7.8]),
]

MECHANICAL_FIXTURES = [
    ("ahu_1", "mechanical_equipment", "laundry", [6.35, 4.65]),
    ("supply_garage", "ceiling_diffuser", "garage", [2.7, 3.7]),
    ("supply_kitchen", "ceiling_diffuser", "kitchen", [9.4, 4.8]),
    ("supply_living", "ceiling_diffuser", "living", [13.2, 3.5]),
    ("supply_bedroom_1", "ceiling_diffuser", "bedroom_1", [2.7, 8.0]),
    ("supply_bedroom_2", "ceiling_diffuser", "bedroom_2", [9.2, 8.0]),
    ("supply_office", "ceiling_diffuser", "office", [13.1, 8.0]),
    ("return_hall", "ceiling_return", "hall", [6.35, 6.5]),
]


def _xy(
    x: float, y: float, plan_x: float, plan_y: float, scale: float
) -> tuple[float, float]:
    return plan_x + x * scale, plan_y + y * scale


def _draw_dimensions(
    c: canvas.Canvas, plan_x: float, plan_y: float, scale: float
) -> None:
    c.saveState()
    c.setStrokeColor(MUTED)
    c.setFillColor(MUTED)
    c.setLineWidth(0.45)
    c.setFont("Helvetica", 5.4)
    y = plan_y - 18
    x_values = [0.0, 5.4, 7.3, 11.4, 15.0]
    for value in x_values:
        x, _ = _xy(value, 0, plan_x, plan_y, scale)
        c.line(x, plan_y - 3, x, y - 5)
    for start, end in zip(x_values, x_values[1:]):
        x0, _ = _xy(start, 0, plan_x, plan_y, scale)
        x1, _ = _xy(end, 0, plan_x, plan_y, scale)
        c.line(x0, y, x1, y)
        c.line(x0, y - 2, x0 + 4, y + 2)
        c.line(x1 - 4, y - 2, x1, y + 2)
        c.drawCentredString((x0 + x1) / 2, y + 3, f"{end - start:.2f} m")
    x = plan_x - 18
    y_values = [0.0, 2.4, 5.8, 7.2, 10.0]
    for value in y_values:
        _, yp = _xy(0, value, plan_x, plan_y, scale)
        c.line(plan_x - 3, yp, x - 5, yp)
    for start, end in zip(y_values, y_values[1:]):
        _, y0 = _xy(0, start, plan_x, plan_y, scale)
        _, y1 = _xy(0, end, plan_x, plan_y, scale)
        c.line(x, y0, x, y1)
        c.line(x - 2, y0, x + 2, y0 + 4)
        c.line(x - 2, y1 - 4, x + 2, y1)
        c.saveState()
        c.translate(x - 4, (y0 + y1) / 2)
        c.rotate(90)
        c.drawCentredString(0, 1, f"{end - start:.2f} m")
        c.restoreState()
    c.setFont("Helvetica-Bold", 5.5)
    for index, value in enumerate([0.0, 5.4, 7.3, 11.3, 15.0], start=1):
        gx, gy = _xy(value, 10.0, plan_x, plan_y, scale)
        c.circle(gx, gy + 17, 6, fill=0, stroke=1)
        c.drawCentredString(gx, gy + 15, str(index))
        c.line(gx, gy + 11, gx, gy + 2)
    c.restoreState()


def _draw_base_plan(
    c: canvas.Canvas, plan_x: float, plan_y: float, scale: float
) -> None:
    c.setFillColor(colors.white)
    c.rect(plan_x, plan_y, 15 * scale, 10 * scale, fill=1, stroke=0)
    for wall_id, start, end, thickness in WALLS:
        del wall_id
        sx, sy = _xy(start[0], start[1], plan_x, plan_y, scale)
        ex, ey = _xy(end[0], end[1], plan_x, plan_y, scale)
        c.setStrokeColor(INK)
        c.setLineWidth(max(1.1, thickness * scale))
        c.line(sx, sy, ex, ey)
    c.setFillColor(MUTED)
    for room_index, (_, label, x0, y0, x1, y1) in enumerate(ROOMS, start=101):
        cx, cy = _xy((x0 + x1) / 2, (y0 + y1) / 2, plan_x, plan_y, scale)
        c.setFont("Helvetica-Bold", 7.3)
        c.drawCentredString(cx, cy + 5, label)
        c.setFont("Helvetica", 5.7)
        c.drawCentredString(cx, cy - 3, str(room_index))
        c.drawCentredString(cx, cy - 11, f"{(x1 - x0) * (y1 - y0):.1f} m²")
    for _, opening_type, wall_id, center, width, _, _ in OPENINGS:
        cx, cy = _xy(center[0], center[1], plan_x, plan_y, scale)
        c.setStrokeColor(colors.white)
        c.setLineWidth(max(4, width * scale))
        horizontal = wall_id in {"w_south", "w_north", "w_h1", "w_h2", "w_h3"}
        if horizontal:
            c.line(cx - width * scale / 2, cy, cx + width * scale / 2, cy)
        else:
            c.line(cx, cy - width * scale / 2, cx, cy + width * scale / 2)
        c.setStrokeColor(LINE if opening_type == "window" else INK)
        c.setLineWidth(0.75)
        if opening_type == "window":
            half = width * scale / 2
            if horizontal:
                c.line(cx - half, cy - 2, cx + half, cy - 2)
                c.line(cx - half, cy + 2, cx + half, cy + 2)
            else:
                c.line(cx - 2, cy - half, cx - 2, cy + half)
                c.line(cx + 2, cy - half, cx + 2, cy + half)
        else:
            leaf = min(width * scale, 23)
            if horizontal:
                c.line(cx - leaf / 2, cy, cx - leaf / 2, cy + leaf)
                c.arc(cx - leaf * 1.5, cy, cx + leaf / 2, cy + leaf * 2, 0, 90)
            else:
                c.line(cx, cy - leaf / 2, cx + leaf, cy - leaf / 2)
                c.arc(cx, cy - leaf * 1.5, cx + leaf * 2, cy + leaf / 2, 90, 90)
    _draw_dimensions(c, plan_x, plan_y, scale)


def _draw_architecture(c: canvas.Canvas, px: float, py: float, scale: float) -> None:
    c.setStrokeColor(GREEN)
    c.setFillColor(colors.HexColor("#EAF6EE"))
    for _, fixture_type, _, center in ARCH_FIXTURES:
        x, y = _xy(center[0], center[1], px, py, scale)
        if fixture_type == "sink":
            c.ellipse(x - 8, y - 5, x + 8, y + 5, fill=0, stroke=1)
        else:
            c.roundRect(x - 15, y - 7, 30, 14, 3, fill=1, stroke=1)
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 6)
    c.drawString(
        px + 7.4 * scale, py + 2.55 * scale, "FULL-HEIGHT OPENING / ALIGN WITH ISLAND"
    )
    c.setStrokeColor(colors.HexColor("#7E8B83"))
    c.setFillColor(colors.HexColor("#F4F6F5"))
    c.setLineWidth(0.65)
    for x, y, width, height in [(1.0, 7.0, 2.1, 1.7), (8.0, 7.0, 2.0, 1.7)]:
        left, bottom = _xy(x, y, px, py, scale)
        c.roundRect(left, bottom, width * scale, height * scale, 4, fill=1, stroke=1)
        c.line(
            left,
            bottom + height * scale * 0.72,
            left + width * scale,
            bottom + height * scale * 0.72,
        )
    sofa_x, sofa_y = _xy(12.0, 1.0, px, py, scale)
    c.roundRect(sofa_x, sofa_y, 2.1 * scale, 0.72 * scale, 4, fill=1, stroke=1)
    table_x, table_y = _xy(12.6, 2.25, px, py, scale)
    c.ellipse(
        table_x - 0.45 * scale,
        table_y - 0.28 * scale,
        table_x + 0.45 * scale,
        table_y + 0.28 * scale,
        fill=1,
        stroke=1,
    )
    desk_x, desk_y = _xy(12.0, 8.7, px, py, scale)
    c.rect(desk_x, desk_y, 2.0 * scale, 0.48 * scale, fill=1, stroke=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.2)
    c.drawString(desk_x, desk_y - 8, "BUILT-IN WORK SURFACE")


def _draw_electrical(c: canvas.Canvas, px: float, py: float, scale: float) -> None:
    c.setStrokeColor(BLUE)
    c.setFillColor(colors.white)
    c.setLineWidth(0.8)
    circuit_points = []
    for entity_id, fixture_type, _, center in ELECTRICAL_FIXTURES:
        x, y = _xy(center[0], center[1], px, py, scale)
        if "light" in fixture_type:
            c.circle(x, y, 5, fill=0, stroke=1)
            c.line(x - 3.5, y - 3.5, x + 3.5, y + 3.5)
            c.line(x - 3.5, y + 3.5, x + 3.5, y - 3.5)
            circuit_points.append((x, y))
        elif "panel" in fixture_type:
            c.rect(x - 6, y - 11, 12, 22, fill=0, stroke=1)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawString(x + 8, y - 2, "EP-1")
        else:
            c.circle(x, y, 4.5, fill=0, stroke=1)
            c.line(x - 3, y, x + 3, y)
            c.setFillColor(colors.HexColor("#C84343"))
            c.circle(x, y, 1.7, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 5.5)
            c.setFillColor(colors.HexColor("#C84343"))
            c.drawString(x + 6, y + 3, "GFCI / BUI-1042")
            c.setFillColor(colors.white)
    c.setDash(3, 2)
    for left, right in zip(circuit_points, circuit_points[1:]):
        c.line(left[0], left[1], right[0], right[1])
    c.setDash()


def _draw_mechanical(c: canvas.Canvas, px: float, py: float, scale: float) -> None:
    c.setStrokeColor(ORANGE)
    c.setFillColor(colors.HexColor("#FAF1E8"))
    c.setLineWidth(1.5)
    ahu = _xy(6.35, 4.65, px, py, scale)
    c.roundRect(ahu[0] - 12, ahu[1] - 9, 24, 18, 2, fill=1, stroke=1)
    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString(ahu[0], ahu[1] - 2, "AHU-1")
    branches = []
    for _, fixture_type, _, center in MECHANICAL_FIXTURES:
        if "equipment" in fixture_type:
            continue
        x, y = _xy(center[0], center[1], px, py, scale)
        c.setFillColor(colors.white)
        c.rect(x - 5, y - 4, 10, 8, fill=1, stroke=1)
        c.line(x - 4, y, x + 4, y)
        branches.append((x, y))
    trunk_x = px + 7.0 * scale
    c.setLineWidth(5.5)
    c.setStrokeColor(colors.HexColor("#D89A5B"))
    c.line(ahu[0], ahu[1], trunk_x, py + 8.2 * scale)
    c.setLineWidth(2.2)
    for x, y in branches:
        c.line(trunk_x, y, x, y)


def _draw_sheet(path: Path, discipline: str, sheet: str, title: str) -> None:
    width, height = landscape(TABLOID)
    c = canvas.Canvas(
        str(path), pagesize=(width, height), pageCompression=1, invariant=1
    )
    c.setTitle(f"Cooper Residence Renovation - {title} {sheet}")
    c.setAuthor("Northstar Builders / BUILI synthetic coordinated demo")
    c.setFillColor(colors.white)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    margin = 0.32 * inch
    c.setStrokeColor(LINE)
    c.rect(margin, margin, width - margin * 2, height - margin * 2, fill=0, stroke=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(margin + 12, height - margin - 24, "COOPER RESIDENCE RENOVATION")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(
        margin + 12,
        height - margin - 39,
        f"{discipline.upper()} / {title.upper()} / COORDINATED DEMO SET",
    )
    c.setStrokeColor(
        {"Architectural": GREEN, "Electrical": BLUE, "Mechanical": ORANGE}[discipline]
    )
    c.setLineWidth(3)
    c.line(
        margin,
        height - margin - 0.72 * inch,
        width - margin,
        height - margin - 0.72 * inch,
    )

    plan_x, plan_y, scale = margin + 0.56 * inch, margin + 1.18 * inch, 46.0
    _draw_base_plan(c, plan_x, plan_y, scale)
    if discipline == "Architectural":
        _draw_architecture(c, plan_x, plan_y, scale)
    elif discipline == "Electrical":
        _draw_electrical(c, plan_x, plan_y, scale)
    else:
        _draw_mechanical(c, plan_x, plan_y, scale)

    notes_x = plan_x + 15 * scale + 28
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(notes_x, plan_y + 10 * scale - 5, f"{discipline.upper()} NOTES")
    notes = {
        "Architectural": [
            "1. VERIFY ALL DIMENSIONS IN FIELD BEFORE WORK.",
            "2. ALIGN NEW PARTITIONS WITH CONTROL DIMENSIONS.",
            "3. COORDINATE OPENINGS WITH STRUCTURAL AND MEP WORK.",
        ],
        "Electrical": [
            "1. VERIFY DEVICE LOCATIONS BEFORE ROUGH-IN.",
            "2. PROVIDE GFCI PROTECTION IN GARAGE AREAS.",
            "3. GARAGE RECEPTACLE CENTERLINES: 18 IN. AFF MINIMUM.",
            "4. CIRCUIT HOMERUNS TO PANEL EP-1.",
        ],
        "Mechanical": [
            "1. VERIFY ROUTING ABOVE CEILING BEFORE FABRICATION.",
            "2. COORDINATE DIFFUSERS WITH LIGHTING AND STRUCTURE.",
            "3. PROVIDE FLEX CONNECTIONS AT AHU-1.",
        ],
    }[discipline]
    c.setFont("Helvetica", 7)
    y = plan_y + 10 * scale - 26
    for note in notes:
        c.drawString(notes_x, y, note)
        y -= 18

    c.setStrokeColor(LINE)
    c.line(margin, margin + 0.65 * inch, width - margin, margin + 0.65 * inch)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(
        margin + 10, margin + 27, "NORTHSTAR BUILDERS / BUILI COORDINATED DEMO"
    )
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.7)
    c.drawString(
        margin + 10, margin + 14, "Synthetic project record / not for construction"
    )
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(width - margin - 12, margin + 27, sheet)
    c.setFont("Helvetica", 6.7)
    c.drawRightString(
        width - margin - 12, margin + 13, "REV 03 / 2026-07-11 / ISSUED FOR REVIEW"
    )
    c.save()


def _fixture_rows(
    rows: list[tuple[str, str, str, list[float]]],
) -> list[dict[str, Any]]:
    return [
        {
            "type": fixture_type,
            "room_id": room_id,
            "center_m": center,
            "source_entity_id": entity_id,
            "confidence": 0.99,
        }
        for entity_id, fixture_type, room_id, center in rows
    ]


def _fixture_manifest_rows() -> list[dict[str, Any]]:
    registry_path = WEB / "fixture-assets" / "registry.json"
    asset_registry = (
        json.loads(registry_path.read_text(encoding="utf-8")).get("assets", {})
        if registry_path.exists()
        else {}
    )
    rows: list[dict[str, Any]] = []
    for discipline, fixtures in (
        ("architectural", ARCH_FIXTURES),
        ("electrical", ELECTRICAL_FIXTURES),
        ("mechanical", MECHANICAL_FIXTURES),
    ):
        for entity_id, fixture_type, room_id, center in fixtures:
            registered_asset = asset_registry.get(fixture_type, {})
            if fixture_type in {"ceiling_light", "ceiling_diffuser", "ceiling_return"}:
                elevation = 2.55
            elif fixture_type == "electrical_panel":
                elevation = 1.35
            elif fixture_type == "receptacle":
                elevation = 0.46
            elif fixture_type == "mechanical_equipment":
                elevation = 0.72
            else:
                elevation = 0.45
            rows.append(
                {
                    "id": entity_id,
                    "type": fixture_type,
                    "discipline": discipline,
                    "roomId": room_id,
                    "position": [center[0], elevation, center[1]],
                    "geometryRole": "review_visualization",
                    "asset": {
                        "uri": registered_asset.get(
                            "uri", f"/demo/fixture-assets/{fixture_type}.glb"
                        ),
                        "registry": "/demo/fixture-assets/registry.json",
                        "sha256": registered_asset.get("sha256"),
                        "scale": [1.0, 1.0, 1.0],
                        "rotationEuler": [0.0, 0.0, 0.0],
                        "status": "approved_demo_seed",
                    },
                    "source": "approved_glb_asset_registry_v1",
                }
            )
    return rows


def _graph(
    sheet: str, source_path: Path, fixtures: list[tuple[str, str, str, list[float]]]
) -> dict[str, Any]:
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    raw = {
        "project_id": "cooper_demo",
        "sheet_id": sheet,
        "scale": {
            "px_per_meter": 46.0,
            "source": "coordinated_demo_cad",
            "confidence": 0.99,
        },
        "rooms": [
            {
                "id": room_id,
                "name": name.title(),
                "polygon": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                "confidence": 0.99,
            }
            for room_id, name, x0, y0, x1, y1 in ROOMS
        ],
        "walls": [
            {
                "id": wall_id,
                "room_id": "",
                "from": start,
                "to": end,
                "height_m": 2.8,
                "thickness_m": thickness,
                "confidence": 0.99,
            }
            for wall_id, start, end, thickness in WALLS
        ],
        "openings": [
            {
                "type": opening_type,
                "wall_id": wall_id,
                "center_m": center,
                "width_m": width,
                "height_m": height,
                "sill_height_m": sill,
                "source_entity_id": entity_id,
                "confidence": 0.99,
            }
            for entity_id, opening_type, wall_id, center, width, height, sill in OPENINGS
        ],
        "fixtures": _fixture_rows(fixtures),
        "sources": [
            {
                "doc_id": f"doc_{sheet.lower().replace('.', '_')}",
                "sheet_id": sheet,
                "page": 1,
                "bbox": [0, 0, 15, 10],
                "source_type": "coordinated_cad_plan",
                "source_strength": "strong",
                "revision": "03",
                "source_hash": digest,
            }
        ],
        "provenance": {
            "source_doc_id": f"doc_{sheet.lower().replace('.', '_')}",
            "source_hash": digest,
            "source_revision": "03",
            "source_revision_id": f"rev_{sheet.lower().replace('.', '_')}_03",
            "source_revision_state": "current",
            "source_issue_date": "2026-07-11",
            "source_filename": source_path.name,
        },
        "extraction": {
            "method": "coordinated_demo_cad_to_plan_graph_v1",
            "source_doc_id": f"doc_{sheet.lower().replace('.', '_')}",
        },
    }
    return finalize_plan_graph_payload(raw)


def _render_preview(pdf_path: Path, output: Path) -> None:
    document = fitz.open(pdf_path)
    try:
        page = document.load_page(0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
        pixmap.save(output)
    finally:
        document.close()


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)
    GENERATED.mkdir(parents=True, exist_ok=True)
    sheets = [
        ("Architectural", "A1.1", "GROUND FLOOR ARCHITECTURAL PLAN", ARCH_FIXTURES),
        ("Electrical", "E1.1", "POWER AND LIGHTING PLAN", ELECTRICAL_FIXTURES),
        ("Mechanical", "M1.1", "HVAC DISTRIBUTION PLAN", MECHANICAL_FIXTURES),
    ]
    manifest_sheets = []
    graphs: dict[str, dict[str, Any]] = {}
    for discipline, sheet, title, fixtures in sheets:
        filename = f"cooper-residence-{sheet}-demo.pdf"
        pdf_path = DEMO / filename
        _draw_sheet(pdf_path, discipline, sheet, title)
        preview_name = f"{sheet}-preview.png"
        preview_path = WEB / preview_name
        _render_preview(pdf_path, preview_path)
        shutil.copy2(pdf_path, WEB / filename)
        graph = _graph(sheet, pdf_path, fixtures)
        graphs[sheet] = graph
        graph_name = f"{sheet}-plan-graph.json"
        (DEMO / graph_name).write_text(json.dumps(graph, indent=2), encoding="utf-8")
        shutil.copy2(DEMO / graph_name, WEB / graph_name)
        manifest_sheets.append(
            {
                "sheet": sheet,
                "discipline": discipline,
                "title": title.title(),
                "revision": "03",
                "pdf": f"/demo/{filename}",
                "preview": f"/demo/{preview_name}",
                "planGraph": f"/demo/{graph_name}",
                "roomCount": len(graph["rooms"]),
                "fixtureCount": len(graph["fixtures"]),
            }
        )

    combined = _graph(
        "A1.1/E1.1/M1.1",
        DEMO / "cooper-residence-A1.1-demo.pdf",
        ARCH_FIXTURES + ELECTRICAL_FIXTURES + MECHANICAL_FIXTURES,
    )
    combined["extraction"]["coordinated_sheets"] = ["A1.1", "E1.1", "M1.1"]
    combined = finalize_plan_graph_payload(combined)
    combined_path = DEMO / "cooper-residence-coordinated-plan-graph.json"
    combined_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    shutil.copy2(combined_path, WEB / combined_path.name)

    uri, model_metadata = build_design_glb(
        combined,
        "cooper_demo",
        "coordinated_review",
        storage_root=GENERATED,
    )
    model_path = GENERATED / uri
    model_name = "cooper-residence-coordinated-review.glb"
    shutil.copy2(model_path, DEMO / model_name)
    shutil.copy2(model_path, WEB / model_name)

    manifest = {
        "project": "Cooper Residence Renovation",
        "coordinateSystem": "BUILI-DEMO-METRIC-01",
        "units": "meters",
        "calibrationConfidence": 0.99,
        "sheets": manifest_sheets,
        "model": {"uri": f"/demo/{model_name}", **model_metadata},
        "rooms": [
            {
                "id": room_id,
                "name": name.title(),
                "position": [(x0 + x1) / 2, 0.08, (y0 + y1) / 2],
            }
            for room_id, name, x0, y0, x1, y1 in ROOMS
        ],
        "fixtures": _fixture_manifest_rows(),
        "fixtureAssetStrategy": {
            "spatialTruth": "PlanGraph coordinates and source dimensions",
            "visualLayer": "approved_glb_asset_registry_v1",
            "fallback": "procedural_asset_library_v1",
            "futureGeneratedAssets": "Tripo or curated GLB assets are copied into BUILI storage, validated, manually approved, and remain non-authoritative presentation geometry",
        },
        "issues": [
            {
                "id": "BUI-1042",
                "position": [5.12, 0.72, 2.15],
                "sheet": "E1.1",
                "tone": "critical",
            },
            {
                "id": "BUI-1038",
                "position": [11.2, 1.0, 7.1],
                "sheet": "A1.1",
                "tone": "warning",
            },
            {
                "id": "RFI-017",
                "position": [7.05, 2.35, 6.5],
                "sheet": "M1.1",
                "tone": "info",
            },
        ],
    }
    manifest_path = DEMO / "drawing-set.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copy2(manifest_path, WEB / manifest_path.name)
    print(
        json.dumps(
            {
                "sheets": len(manifest_sheets),
                "model": model_name,
                "metadata": model_metadata,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
