from __future__ import annotations

from pathlib import Path

import fitz

from buili_spatial.io_utils import sha256_file
from buili_spatial.pipeline import SpatialPipelineError, parse_pdf_to_plan_graph


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
