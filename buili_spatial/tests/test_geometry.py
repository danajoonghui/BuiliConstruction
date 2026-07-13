from __future__ import annotations

import json
import struct

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


def test_glb_exposes_semantic_floor_wall_and_fixture_meshes(
    tmp_path, finalized_plan_graph: dict
) -> None:
    uri, metadata = build_design_glb(
        finalized_plan_graph,
        "project_semantic",
        "asset_semantic",
        storage_root=tmp_path,
    )
    payload = (tmp_path / uri).read_bytes()
    json_length, json_type = struct.unpack_from("<I4s", payload, 12)
    assert json_type == b"JSON"
    document = json.loads(payload[20 : 20 + json_length].decode("utf-8").rstrip())

    mesh_names = {mesh["name"] for mesh in document["meshes"]}
    node_names = {node["name"] for node in document["nodes"]}
    assert mesh_names == {"Floor slab", "Architectural walls", "Discipline fixtures"}
    assert node_names == mesh_names
    assert metadata["mesh_parts"] == ["floor", "walls", "fixtures"]
