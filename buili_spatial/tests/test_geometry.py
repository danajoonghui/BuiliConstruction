from __future__ import annotations

from buili_spatial.geometry import build_design_glb


def test_glb_is_atomic_hashed_and_cuts_opening(
    tmp_path, finalized_plan_graph: dict
) -> None:
    uri, metadata = build_design_glb(
        finalized_plan_graph,
        "project_1",
        "asset_1",
        storage_root=tmp_path,
    )
    path = tmp_path / uri
    assert path.read_bytes()[:4] == b"glTF"
    assert metadata["opening_cut_count"] == 1
    assert len(metadata["artifact_sha256"]) == 64
    assert metadata["triangle_count"] > 0
    assert (
        metadata["plan_graph_content_sha256"]
        == finalized_plan_graph["pipeline"]["content_sha256"]
    )
