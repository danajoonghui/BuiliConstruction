from __future__ import annotations

from pathlib import Path

from buili_spatial.floorplan_extractor import AxisSegment
from buili_spatial.pipeline import parse_pdf_to_plan_graph
from buili_spatial.semantic_auto import (
    _dominant_plan_segments,
    _embedded_pdf_text_items,
    _fixture_from_compact_text,
    _is_room_label,
    build_semantic_scene_from_pdf,
)


def test_room_and_fixture_text_requires_compact_exact_tags() -> None:
    assert _is_room_label("GARAGE") == "GARAGE"
    assert _is_room_label("GARAGE 101") == "GARAGE"
    assert _is_room_label("Provide GFCI receptacles in garage areas") is None
    assert _fixture_from_compact_text("GFCI") == ("duplex_outlet", "gfci")
    assert _fixture_from_compact_text("GFCI - SEE NOTE 3") is None
    assert (
        _fixture_from_compact_text(
            "GARAGE RECEPTACLE BOX CENTERLINES SHALL BE MOUNTED 18 INCHES"
        )
        is None
    )


def test_dominant_plan_network_excludes_title_and_note_components() -> None:
    segments = [
        AxisSegment("h", 300, 100, 900, 6),
        AxisSegment("h", 800, 100, 900, 6),
        AxisSegment("v", 100, 300, 800, 6),
        AxisSegment("v", 900, 300, 620, 6),
        AxisSegment("v", 900, 700, 800, 6),
        AxisSegment("h", 700, 820, 900, 6),
        # Header rule and note box are separate page furniture.
        AxisSegment("h", 100, 50, 950, 2),
        AxisSegment("h", 360, 980, 1450, 2),
        AxisSegment("h", 430, 980, 1450, 2),
        AxisSegment("v", 980, 360, 430, 2),
    ]

    selected, metadata = _dominant_plan_segments(segments, 1600, 1000)

    assert metadata["applied"] is True
    assert metadata["dominant_component_segments"] == 6
    assert len(selected) == 6
    assert all(segment.fixed_px < 950 for segment in selected)
    assert all(
        not (segment.orientation == "h" and segment.fixed_px in {50, 360, 430})
        for segment in selected
    )


def test_cooper_demo_sheet_keeps_plan_and_rejects_note_prose(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    pdf_path = repository_root / "output" / "pdf" / "cooper-residence-E1.1-demo.pdf"
    assert pdf_path.is_file(), "The checked-in Cooper Residence regression sheet is missing."

    scene, metadata = build_semantic_scene_from_pdf(
        pdf_path,
        output_dir=tmp_path,
        use_ocr=False,
        use_micro_vlm=False,
    )

    crop_bbox = tuple(metadata["crop_bbox_px"])
    page_width, page_height = metadata["page_image_size_px"]
    crop_text = _embedded_pdf_text_items(
        pdf_path,
        page_no=1,
        zoom=2.5,
        crop_bbox=crop_bbox,
    )
    crop_strings = [item.text.upper() for item in crop_text]

    assert crop_bbox[1] > page_height * 0.35
    assert crop_bbox[2] < page_width * 0.75
    assert metadata["wall_metadata"]["vector_plan_roi"]["applied"] is True
    assert [label.name for label in scene.labels] == ["GARAGE"]
    assert all("COOPER RESIDENCE" not in text for text in crop_strings)
    assert all("ELECTRICAL NOTES" not in text for text in crop_strings)
    assert all("CENTERLINES SHALL BE MOUNTED" not in text for text in crop_strings)
    assert scene.objects == []

    plan_graph = parse_pdf_to_plan_graph(
        pdf_path,
        tmp_path / "pipeline",
        project_id="project_cooper",
        sheet_id="E1.1",
        source_doc_id="document_e11",
        source_revision_id="revision_2",
        source_revision="2",
        source_issue_date="2026-07-09",
        use_ocr=False,
    )
    assert plan_graph["fixtures"] == []
    assert len(plan_graph["walls"]) == 6
    assert [
        label["name"] for label in plan_graph["extraction"]["room_labels"]
    ] == ["GARAGE"]
