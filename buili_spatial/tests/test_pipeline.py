from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from buili_spatial.geometry import build_design_glb
from buili_spatial.io_utils import sha256_file
from buili_spatial.pipeline import SpatialPipelineError, parse_pdf_to_plan_graph


DEMO_PDF = (
    Path(__file__).resolve().parents[2]
    / "buili_demo_evidence"
    / "cooper-residence-E1.1-demo.pdf"
)


def _make_vector_plan(path) -> None:
    pdf = fitz.open()
    page = pdf.new_page(width=612, height=792)
    # Six long, dark axis segments inside the floor-plan extraction window.
    for start, end in [
        ((100, 180), (500, 180)),
        ((500, 180), (500, 600)),
        ((500, 600), (100, 600)),
        ((100, 600), (100, 180)),
        ((300, 180), (300, 600)),
        ((100, 390), (500, 390)),
    ]:
        page.draw_line(start, end, color=(0, 0, 0), width=4)
    page.insert_text((175, 300), "OFFICE", fontsize=16, color=(0, 0, 0))
    page.insert_text((175, 325), "12'-0\" x 10'-0\"", fontsize=11, color=(0, 0, 0))
    pdf.save(path)
    pdf.close()


def test_pdf_facade_returns_canonical_revision_contract(tmp_path) -> None:
    pdf = tmp_path / "A-101.pdf"
    _make_vector_plan(pdf)
    payload = parse_pdf_to_plan_graph(
        pdf,
        tmp_path / "derived",
        project_id="project_1",
        sheet_id="A-101",
        source_doc_id="doc_1",
        source_revision_id="rev_1",
        source_revision="1",
        source_hash=sha256_file(pdf),
        px_per_meter=100.0,
        scale_source="test_calibration",
        scale_confidence=0.95,
        use_ocr=False,
    )
    assert payload["provenance"]["source_revision_id"] == "rev_1"
    assert payload["provenance"]["source_hash"] == sha256_file(pdf)
    assert payload["pipeline"]["content_sha256"]
    assert payload["extraction"]["source_pdf"] == "A-101.pdf"
    assert (
        payload["extraction"]["scene_build"]["wall_metadata"][
            "selected_geometry_source"
        ]
        == "pdf_vector_primitives"
    )
    assert not Path(payload["extraction"]["source_pdf"]).is_absolute()
    assert len(payload["walls"]) >= 6


def test_pdf_facade_rejects_revision_hash_mismatch(tmp_path) -> None:
    pdf = tmp_path / "A-101.pdf"
    _make_vector_plan(pdf)
    try:
        parse_pdf_to_plan_graph(
            pdf,
            tmp_path / "derived",
            project_id="project_1",
            sheet_id="A-101",
            source_doc_id="doc_1",
            source_revision_id="rev_1",
            source_hash="b" * 64,
        )
    except SpatialPipelineError as exc:
        assert exc.code == "SOURCE_HASH_MISMATCH"
    else:  # pragma: no cover
        raise AssertionError("hash mismatch should fail before parsing")


def test_demo_plan_graph_and_glb_are_reproducible_and_source_mapped(tmp_path) -> None:
    source_hash = sha256_file(DEMO_PDF)
    options = {
        "project_id": "project_demo",
        "sheet_id": "E1.1",
        "source_doc_id": "doc_demo_e11",
        "source_revision_id": "rev_demo_e11_2",
        "source_revision": "2",
        "source_hash": source_hash,
        "px_per_meter": 100.0,
        "scale_source": "verified_demo_calibration",
        "scale_confidence": 0.95,
        "use_ocr": False,
    }
    first = parse_pdf_to_plan_graph(DEMO_PDF, tmp_path / "first", **options)
    second = parse_pdf_to_plan_graph(DEMO_PDF, tmp_path / "second", **options)

    assert first == second
    assert first["pipeline"]["deterministic"] is True
    assert first["provenance"]["source_hash"] == source_hash
    assert first["provenance"]["source_revision_id"] == "rev_demo_e11_2"
    assert len(first["rooms"]) == 1
    assert len(first["walls"]) >= 4
    assert first["sources"]
    assert not {
        row["code"] for row in first["warnings"] if row["severity"] == "error"
    }
    for collection in ("rooms", "walls", "openings", "fixtures"):
        assert all(entity["source_ref_ids"] for entity in first[collection])

    first_uri, first_metadata = build_design_glb(
        first,
        "project_demo",
        "scene_demo",
        storage_root=tmp_path / "glb-first",
    )
    second_uri, second_metadata = build_design_glb(
        second,
        "project_demo",
        "scene_demo",
        storage_root=tmp_path / "glb-second",
    )
    first_glb = (tmp_path / "glb-first" / first_uri).read_bytes()
    second_glb = (tmp_path / "glb-second" / second_uri).read_bytes()
    assert first_glb == second_glb
    assert first_glb[:4] == b"glTF"
    assert first_metadata == second_metadata
    assert first_metadata["plan_graph_content_sha256"] == first["pipeline"][
        "content_sha256"
    ]


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("page_no", 0, "INVALID_PAGE_NUMBER"),
        ("px_per_meter", 0.0, "INVALID_SCALE"),
        ("scale_confidence", 1.01, "INVALID_SCALE_CONFIDENCE"),
    ],
)
def test_pdf_facade_rejects_invalid_spatial_inputs(
    tmp_path, field: str, value: float, code: str
) -> None:
    arguments = {
        "project_id": "project_demo",
        "sheet_id": "E1.1",
        "source_doc_id": "doc_demo_e11",
        "source_revision_id": "rev_demo_e11_2",
        field: value,
    }
    with pytest.raises(SpatialPipelineError) as captured:
        parse_pdf_to_plan_graph(DEMO_PDF, tmp_path / "derived", **arguments)
    assert captured.value.code == code
