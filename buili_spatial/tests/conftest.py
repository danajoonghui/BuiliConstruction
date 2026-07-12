from __future__ import annotations

import copy

import pytest


@pytest.fixture
def raw_plan_graph() -> dict:
    room_id = "room_101"
    walls = [
        {"id": "w1", "room_id": room_id, "from": [0, 0], "to": [4, 0], "height_m": 2.7},
        {"id": "w2", "room_id": room_id, "from": [4, 0], "to": [4, 3], "height_m": 2.7},
        {"id": "w3", "room_id": room_id, "from": [4, 3], "to": [0, 3], "height_m": 2.7},
        {"id": "w4", "room_id": room_id, "from": [0, 3], "to": [0, 0], "height_m": 2.7},
    ]
    return {
        "project_id": "project_1",
        "sheet_id": "A-101",
        "scale": {
            "px_per_meter": 100.0,
            "source": "user_calibration",
            "confidence": 0.95,
        },
        "rooms": [
            {
                "id": room_id,
                "name": "Room 101",
                "polygon": [[0, 0], [4, 0], [4, 3], [0, 3]],
            }
        ],
        "walls": walls,
        "openings": [
            {
                "type": "door",
                "wall_id": "w1",
                "center_m": [2.0, 0.0],
                "width_m": 0.9,
                "source_entity_id": "door_1",
            }
        ],
        "fixtures": [
            {
                "type": "sink",
                "room_id": room_id,
                "wall_id": "w2",
                "center_m": [3.5, 1.5],
                "source_entity_id": "sink_1",
            }
        ],
        "sources": [
            {
                "doc_id": "doc_1",
                "sheet_id": "A-101",
                "bbox": [[0, 0], [4, 0], [4, 3], [0, 3]],
                "source_type": "drawing_region",
                "source_strength": "strong",
            }
        ],
        "provenance": {
            "source_doc_id": "doc_1",
            "source_hash": "a" * 64,
            "source_revision": "2",
            "source_revision_id": "revision_2",
            "source_revision_state": "current",
            "source_filename": "A-101.pdf",
        },
        "extraction": {"method": "unit_test_fixture", "source_doc_id": "doc_1"},
    }


@pytest.fixture
def finalized_plan_graph(raw_plan_graph: dict) -> dict:
    from buili_spatial.contracts import finalize_plan_graph_payload

    return finalize_plan_graph_payload(copy.deepcopy(raw_plan_graph))
