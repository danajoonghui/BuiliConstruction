"""Conservative, DB-independent field-to-plan comparison helpers."""

from __future__ import annotations

import math
from typing import Any


def _room_for_issue(graph: dict[str, Any], issue: dict[str, Any]) -> dict[str, Any]:
    rooms = graph.get("rooms") or []
    location = issue.get("location_json") or issue.get("location") or {}
    issue_room = " ".join(
        str(location.get("space") or location.get("room") or "").lower().split()
    )
    for room in rooms:
        room_name = " ".join(str(room.get("name", "")).lower().split())
        if issue_room and room_name == issue_room:
            return room
    for room in rooms:
        room_name = " ".join(str(room.get("name", "")).lower().split())
        if issue_room and (issue_room in room_name or room_name in issue_room):
            return room
    return rooms[0] if rooms else {"id": "", "name": issue_room, "polygon": []}


def _distance_to_wall(issue: dict[str, Any], room: dict[str, Any]) -> float | None:
    location = issue.get("plan_location") or issue.get("location_json") or {}
    if location.get("x") is None or location.get("y") is None:
        return None
    try:
        x, y = float(location["x"]), float(location["y"])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    polygon = room.get("polygon") or []
    if len(polygon) < 2:
        return None
    distances: list[float] = []
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        vx, vy = end[0] - start[0], end[1] - start[1]
        denominator = vx * vx + vy * vy
        t = 0.0 if denominator == 0 else max(
            0.0,
            min(1.0, ((x - start[0]) * vx + (y - start[1]) * vy) / denominator),
        )
        px, py = start[0] + t * vx, start[1] + t * vy
        distances.append(math.hypot(x - px, y - py))
    return round(min(distances), 3)


def compare_project_spatial(
    *,
    plan_graph: dict[str, Any],
    issue: dict[str, Any],
    observations: list[dict[str, Any]],
    alignment: dict[str, Any] | None,
    field_asset_present: bool,
) -> dict[str, Any]:
    """Return a review candidate without asserting a construction deviation.

    A low-confidence alignment, missing issue coordinate, or absent explicitly
    linked observation always routes to additional evidence.
    """

    room = _room_for_issue(plan_graph, issue)
    alignment_confidence = float((alignment or {}).get("confidence") or 0.0)
    explicitly_linked = [
        item
        for item in observations
        if str(item.get("issue_id") or "") == str(issue.get("id") or issue.get("issue_id") or "")
    ]
    coverage = min(1.0, len(explicitly_linked) / 5.0) if field_asset_present else 0.0
    distance = _distance_to_wall(issue, room)
    warnings: list[str] = []
    if distance is None:
        warnings.append("ISSUE_PLAN_COORDINATE_MISSING")
    if not explicitly_linked:
        warnings.append("ISSUE_OBSERVATIONS_NOT_LINKED")
    needs_more_evidence = (
        alignment_confidence < 0.5
        or coverage < 0.25
        or distance is None
        or not explicitly_linked
    )
    issue_confidence = float(issue.get("confidence") or 0.0)
    geometry_confidence = min(
        0.98, alignment_confidence * 0.55 + coverage * 0.25 + issue_confidence * 0.2
    )
    if needs_more_evidence:
        geometry_confidence = min(0.49, geometry_confidence)
    return {
        "schema_version": "buili.spatial-compare.v2",
        "issue_id": str(issue.get("id") or issue.get("issue_id") or ""),
        "room_graph_id": str(room.get("id") or ""),
        "room_name": str(room.get("name") or ""),
        "features": {
            "room_alignment_confidence": round(alignment_confidence, 3),
            "field_coverage_ratio": round(coverage, 3),
            "distance_to_required_wall_m": distance,
            "linked_observation_count": len(explicitly_linked),
            "needs_more_evidence": needs_more_evidence,
        },
        "confidence": round(geometry_confidence, 3),
        "warnings": warnings,
        "recommended_route": (
            "additional_evidence_required" if needs_more_evidence else "human_review"
        ),
        "official_use_blocked": needs_more_evidence,
        "note": (
            "Spatial comparison is a review candidate. Contract-document and field reviewer "
            "confirmation remain required."
        ),
    }
