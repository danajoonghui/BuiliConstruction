from __future__ import annotations

import copy

import pytest

from buili_spatial.contracts import (
    PLAN_GRAPH_SCHEMA_VERSION,
    PlanGraphContractError,
    finalize_plan_graph_payload,
    validate_plan_graph_payload,
)


def test_finalize_is_deterministic_and_traceable(raw_plan_graph: dict) -> None:
    left = finalize_plan_graph_payload(copy.deepcopy(raw_plan_graph))
    right = finalize_plan_graph_payload(copy.deepcopy(raw_plan_graph))
    assert left == right
    assert left["schema_version"] == PLAN_GRAPH_SCHEMA_VERSION
    assert len(left["pipeline"]["content_sha256"]) == 64
    assert left["pipeline"]["run_id"].startswith("spatial_")
    assert left["sources"][0]["source_ref_id"].startswith("src_")
    assert all(row["source_ref_ids"] for row in left["walls"])
    assert left["confidence"]["traceability"] == 1.0
    validate_plan_graph_payload(left)


def test_source_input_order_does_not_change_contract(raw_plan_graph: dict) -> None:
    second = {
        "doc_id": "doc_1",
        "sheet_id": "A-101",
        "bbox": [0, 0, 1, 1],
        "source_type": "detail",
        "source_strength": "strong",
    }
    raw_plan_graph["sources"].append(second)
    left = finalize_plan_graph_payload(copy.deepcopy(raw_plan_graph))
    raw_plan_graph["sources"].reverse()
    right = finalize_plan_graph_payload(copy.deepcopy(raw_plan_graph))
    assert left == right


def test_unknown_wall_reference_is_rejected(raw_plan_graph: dict) -> None:
    raw_plan_graph["openings"][0]["wall_id"] = "missing"
    with pytest.raises(PlanGraphContractError, match="unknown wall"):
        finalize_plan_graph_payload(raw_plan_graph)


def test_collapsed_room_is_rejected(raw_plan_graph: dict) -> None:
    raw_plan_graph["rooms"][0]["polygon"] = [[0, 0], [1, 1], [2, 2]]
    with pytest.raises(PlanGraphContractError, match="non-zero area"):
        finalize_plan_graph_payload(raw_plan_graph)


def test_low_scale_emits_review_warning(raw_plan_graph: dict) -> None:
    raw_plan_graph["scale"]["confidence"] = 0.2
    payload = finalize_plan_graph_payload(raw_plan_graph)
    assert "SCALE_REQUIRES_CALIBRATION" in {row["code"] for row in payload["warnings"]}
    assert payload["confidence"]["review_required"] is True
