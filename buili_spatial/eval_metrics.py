from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .semantic_scene import SemanticObject, SemanticOpening, SemanticScene, SemanticWall


BBox = tuple[float, float, float, float]
Segment = tuple[float, float, float, float]


@dataclass(frozen=True)
class EvalItem:
    id: str
    kind: str
    bbox: BBox
    angle_deg: float = 0.0
    length_px: float = 0.0

    @property
    def center(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.bbox
        return (x0 + x1) / 2, (y0 + y1) / 2


@dataclass(frozen=True)
class EvalWall:
    id: str
    segment: Segment
    wall_type: str = "interior"

    @property
    def length_px(self) -> float:
        x0, y0, x1, y1 = self.segment
        return math.hypot(x1 - x0, y1 - y0)


def object_to_eval_item(obj: SemanticObject) -> EvalItem:
    cx, cy = obj.center_px
    return EvalItem(
        id=obj.id,
        kind=str(obj.kind),
        bbox=(
            cx - obj.width_px / 2,
            cy - obj.depth_px / 2,
            cx + obj.width_px / 2,
            cy + obj.depth_px / 2,
        ),
        angle_deg=float(obj.angle_deg),
        length_px=max(float(obj.width_px), float(obj.depth_px)),
    )


def opening_to_eval_item(opening: SemanticOpening) -> EvalItem:
    cx, cy = opening.center_px
    angle = math.radians(opening.angle_deg)
    long_x = abs(math.cos(angle)) * opening.length_px
    long_y = abs(math.sin(angle)) * opening.length_px
    width = max(12.0, long_x if long_x > long_y else 24.0)
    height = max(12.0, long_y if long_y >= long_x else 24.0)
    return EvalItem(
        id=opening.id,
        kind=str(opening.kind),
        bbox=(cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2),
        angle_deg=float(opening.angle_deg),
        length_px=float(opening.length_px),
    )


def wall_to_eval_wall(wall: SemanticWall) -> EvalWall:
    return EvalWall(
        id=wall.id,
        segment=(
            float(wall.start_px[0]),
            float(wall.start_px[1]),
            float(wall.end_px[0]),
            float(wall.end_px[1]),
        ),
        wall_type=str(wall.wall_type),
    )


def scene_to_eval_payload(scene: SemanticScene) -> dict[str, list[dict[str, Any]]]:
    return {
        "objects": [object_to_eval_item(obj).__dict__ for obj in scene.objects],
        "openings": [
            opening_to_eval_item(opening).__dict__ for opening in scene.openings
        ],
        "walls": [wall_to_eval_wall(wall).__dict__ for wall in scene.walls],
    }


def _item_from_dict(row: dict[str, Any]) -> EvalItem:
    if "bbox" not in row and "center_px" in row:
        cx, cy = row["center_px"]
        width = float(row.get("width_px", row.get("length_px", 24.0)))
        height = float(row.get("depth_px", row.get("length_px", 24.0)))
        row = {
            **row,
            "bbox": [cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2],
        }
    return EvalItem(
        id=str(row.get("id", "")),
        kind=str(row.get("kind", row.get("label", "unknown"))),
        bbox=tuple(float(value) for value in row["bbox"]),  # type: ignore[arg-type]
        angle_deg=float(row.get("angle_deg", 0.0)),
        length_px=float(row.get("length_px", 0.0)),
    )


def _wall_from_dict(row: dict[str, Any]) -> EvalWall:
    segment = row.get("segment")
    if segment is None and "start_px" in row and "end_px" in row:
        sx, sy = row["start_px"]
        ex, ey = row["end_px"]
        segment = [sx, sy, ex, ey]
    if segment is None or len(segment) != 4:
        raise ValueError("wall requires a four-value segment or start_px/end_px")
    return EvalWall(
        id=str(row.get("id", "")),
        segment=tuple(float(value) for value in segment),  # type: ignore[arg-type]
        wall_type=str(row.get("wall_type", "interior")),
    )


def iou_bbox(left: BBox, right: BBox) -> float:
    lx0, ly0, lx1, ly1 = left
    rx0, ry0, rx1, ry1 = right
    ix0, iy0 = max(lx0, rx0), max(ly0, ry0)
    ix1, iy1 = min(lx1, rx1), min(ly1, ry1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    left_area = max((lx1 - lx0) * (ly1 - ly0), 1e-6)
    right_area = max((rx1 - rx0) * (ry1 - ry0), 1e-6)
    return inter / (left_area + right_area - inter)


def _angle_delta_deg(left: float, right: float) -> float:
    diff = abs((left - right + 180.0) % 360.0 - 180.0)
    return min(diff, abs(diff - 180.0))


def match_bbox_items(
    predicted: list[dict[str, Any]] | list[EvalItem],
    ground_truth: list[dict[str, Any]] | list[EvalItem],
    *,
    iou_threshold: float = 0.5,
    class_aware: bool = True,
) -> dict[str, Any]:
    if not 0 <= iou_threshold <= 1:
        raise ValueError("iou_threshold must be between 0 and 1")
    preds = [
        item if isinstance(item, EvalItem) else _item_from_dict(item)
        for item in predicted
    ]
    gts = [
        item if isinstance(item, EvalItem) else _item_from_dict(item)
        for item in ground_truth
    ]
    candidates: list[tuple[float, int, int]] = []
    for pred_index, pred in enumerate(preds):
        for gt_index, gt in enumerate(gts):
            if class_aware and pred.kind != gt.kind:
                continue
            iou = iou_bbox(pred.bbox, gt.bbox)
            if iou >= iou_threshold:
                candidates.append((iou, pred_index, gt_index))
    matched_pred: set[int] = set()
    matched_gt: set[int] = set()
    matches: list[dict[str, Any]] = []
    for iou, pred_index, gt_index in sorted(
        candidates,
        key=lambda row: (-row[0], preds[row[1]].id, gts[row[2]].id),
    ):
        if pred_index in matched_pred or gt_index in matched_gt:
            continue
        pred, gt = preds[pred_index], gts[gt_index]
        pcx, pcy = pred.center
        gcx, gcy = gt.center
        matched_pred.add(pred_index)
        matched_gt.add(gt_index)
        matches.append(
            {
                "pred_id": pred.id,
                "gt_id": gt.id,
                "kind": gt.kind,
                "iou": round(float(iou), 4),
                "center_error_px": round(math.hypot(pcx - gcx, pcy - gcy), 4),
                "angle_error_deg": round(
                    _angle_delta_deg(pred.angle_deg, gt.angle_deg), 4
                ),
                "length_error_px": round(abs(pred.length_px - gt.length_px), 4),
            }
        )
    precision = 1.0 if not preds and not gts else len(matches) / max(len(preds), 1)
    recall = 1.0 if not preds and not gts else len(matches) / max(len(gts), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    center_errors = [row["center_error_px"] for row in matches]
    angle_errors = [row["angle_error_deg"] for row in matches]
    length_errors = [
        row["length_error_px"] for row in matches if row["length_error_px"] > 0
    ]
    return {
        "count_pred": len(preds),
        "count_gt": len(gts),
        "true_positive": len(matches),
        "false_positive": len(preds) - len(matches),
        "false_negative": len(gts) - len(matches),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "mean_iou": round(float(np.mean([row["iou"] for row in matches])), 4)
        if matches
        else 0.0,
        "mean_center_error_px": round(float(np.mean(center_errors)), 4)
        if center_errors
        else 0.0,
        "p95_center_error_px": round(float(np.percentile(center_errors, 95)), 4)
        if center_errors
        else 0.0,
        "mean_angle_error_deg": round(float(np.mean(angle_errors)), 4)
        if angle_errors
        else 0.0,
        "mean_length_error_px": round(float(np.mean(length_errors)), 4)
        if length_errors
        else 0.0,
        "matches": matches,
        "definition": {
            "matching": "greedy class-aware one-to-one by descending IoU",
            "iou_threshold": iou_threshold,
            "class_aware": class_aware,
        },
    }


def _point_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return math.hypot(px - ax, py - ay)
    ratio = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    x = ax + dx * ratio
    y = ay + dy * ratio
    return math.hypot(px - x, py - y)


def _segment_distance(left: Segment, right: Segment) -> float:
    ax, ay, bx, by = left
    cx, cy, dx, dy = right
    return min(
        max(
            _point_segment_distance(ax, ay, cx, cy, dx, dy),
            _point_segment_distance(bx, by, cx, cy, dx, dy),
        ),
        max(
            _point_segment_distance(cx, cy, ax, ay, bx, by),
            _point_segment_distance(dx, dy, ax, ay, bx, by),
        ),
    )


def _segment_angle(segment: Segment) -> float:
    x0, y0, x1, y1 = segment
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


def _sample_segment(segment: Segment, step_px: float) -> list[tuple[float, float]]:
    x0, y0, x1, y1 = segment
    length = max(math.hypot(x1 - x0, y1 - y0), 1.0)
    count = max(2, int(math.ceil(length / step_px)) + 1)
    return [
        (x0 + (x1 - x0) * index / (count - 1), y0 + (y1 - y0) * index / (count - 1))
        for index in range(count)
    ]


def match_wall_segments(
    predicted: list[dict[str, Any]] | list[EvalWall],
    ground_truth: list[dict[str, Any]] | list[EvalWall],
    *,
    distance_threshold_px: float = 12.0,
    angle_threshold_deg: float = 12.0,
    sample_step_px: float = 10.0,
) -> dict[str, Any]:
    if distance_threshold_px < 0 or angle_threshold_deg < 0 or sample_step_px <= 0:
        raise ValueError(
            "wall thresholds must be non-negative and sample_step_px must be positive"
        )
    preds = [
        item if isinstance(item, EvalWall) else _wall_from_dict(item)
        for item in predicted
    ]
    gts = [
        item if isinstance(item, EvalWall) else _wall_from_dict(item)
        for item in ground_truth
    ]
    candidates: list[tuple[float, int, int, float]] = []
    for pred_index, pred in enumerate(preds):
        for gt_index, gt in enumerate(gts):
            angle_error = _angle_delta_deg(
                _segment_angle(pred.segment), _segment_angle(gt.segment)
            )
            if angle_error > angle_threshold_deg:
                continue
            distance = _segment_distance(pred.segment, gt.segment)
            if distance <= distance_threshold_px:
                candidates.append((distance, pred_index, gt_index, angle_error))
    matched_pred: set[int] = set()
    matched_gt: set[int] = set()
    matches: list[dict[str, Any]] = []
    for distance, pred_index, gt_index, angle_error in sorted(
        candidates,
        key=lambda row: (row[0], row[3], preds[row[1]].id, gts[row[2]].id),
    ):
        if pred_index in matched_pred or gt_index in matched_gt:
            continue
        pred, gt = preds[pred_index], gts[gt_index]
        matched_pred.add(pred_index)
        matched_gt.add(gt_index)
        matches.append(
            {
                "pred_id": pred.id,
                "gt_id": gt.id,
                "distance_px": round(float(distance), 4),
                "angle_error_deg": round(float(angle_error), 4),
                "length_error_px": round(abs(pred.length_px - gt.length_px), 4),
            }
        )
    precision = 1.0 if not preds and not gts else len(matches) / max(len(preds), 1)
    recall = 1.0 if not preds and not gts else len(matches) / max(len(gts), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    coverage_distances: list[float] = []
    for gt in gts:
        for x, y in _sample_segment(gt.segment, sample_step_px):
            if not preds:
                coverage_distances.append(float("inf"))
                continue
            coverage_distances.append(
                min(_point_segment_distance(x, y, *pred.segment) for pred in preds)
            )
    finite = [value for value in coverage_distances if math.isfinite(value)]
    coverage = (
        sum(value <= distance_threshold_px for value in finite) / max(len(finite), 1)
        if finite
        else (1.0 if not preds and not gts else 0.0)
    )
    distances = [row["distance_px"] for row in matches]
    return {
        "count_pred": len(preds),
        "count_gt": len(gts),
        "true_positive": len(matches),
        "false_positive": len(preds) - len(matches),
        "false_negative": len(gts) - len(matches),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "mean_distance_px": round(float(np.mean(distances)), 4) if distances else 0.0,
        "p95_distance_px": round(float(np.percentile(distances, 95)), 4)
        if distances
        else 0.0,
        "gt_coverage_at_threshold": round(float(coverage), 4),
        "matches": matches,
        "definition": {
            "matching": "greedy one-to-one by segment distance under angular gate",
            "distance_threshold_px": distance_threshold_px,
            "angle_threshold_deg": angle_threshold_deg,
            "coverage": "fraction of GT wall samples within distance_threshold_px of any prediction",
        },
    }


def evaluate_plan_elements(
    prediction: dict[str, Any],
    ground_truth: dict[str, Any],
    *,
    object_iou_threshold: float = 0.5,
    opening_iou_threshold: float = 0.35,
    wall_distance_threshold_px: float = 12.0,
) -> dict[str, Any]:
    result = {
        "objects": match_bbox_items(
            prediction.get("objects", []),
            ground_truth.get("objects", []),
            iou_threshold=object_iou_threshold,
            class_aware=True,
        ),
        "openings": match_bbox_items(
            prediction.get("openings", []),
            ground_truth.get("openings", []),
            iou_threshold=opening_iou_threshold,
            class_aware=True,
        ),
        "walls": match_wall_segments(
            prediction.get("walls", []),
            ground_truth.get("walls", []),
            distance_threshold_px=wall_distance_threshold_px,
        ),
        "metric_contract": {
            "object": "class-aware bbox IoU, precision/recall/F1, center error",
            "opening": "door/window class-aware bbox IoU plus center/angle/length error",
            "wall": "segment distance, angular gate, endpoint/coverage quality",
        },
    }
    component_f1 = [result[key]["f1"] for key in ("objects", "openings", "walls")]
    result["summary"] = {
        "macro_f1": round(float(np.mean(component_f1)), 4),
        "minimum_component_f1": round(float(min(component_f1)), 4),
        "quality_gate_passed": all(value >= 0.8 for value in component_f1),
        "quality_gate_definition": "objects/openings/walls F1 must each be >= 0.80",
    }
    return result


def _polygon_area(points: list[list[float]] | list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    return (
        abs(
            sum(
                float(left[0]) * float(right[1]) - float(right[0]) * float(left[1])
                for left, right in zip(points, [*points[1:], points[0]], strict=True)
            )
        )
        / 2.0
    )


def _wall_length(row: dict[str, Any]) -> float:
    start = row.get("from") or row.get("start") or [0.0, 0.0]
    end = row.get("to") or row.get("end") or [0.0, 0.0]
    return math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))


def evaluate_plan_graph(
    prediction: dict[str, Any],
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate metric-space PlanGraph structure and source traceability.

    This complements pixel-space element metrics. It intentionally reports room area,
    total wall length, entity counts, and traceability rather than pretending a single
    benchmark number proves construction-grade dimensional accuracy.
    """

    pred_rooms = prediction.get("rooms") or []
    gt_rooms = ground_truth.get("rooms") or []
    gt_by_id = {str(room.get("id", "")): room for room in gt_rooms if room.get("id")}
    gt_by_name: dict[str, list[dict[str, Any]]] = {}
    for room in gt_rooms:
        gt_by_name.setdefault(str(room.get("name", "")).strip().lower(), []).append(
            room
        )
    room_rows: list[dict[str, Any]] = []
    matched_gt: set[int] = set()
    for room in sorted(
        pred_rooms, key=lambda row: (str(row.get("id", "")), str(row.get("name", "")))
    ):
        gt = gt_by_id.get(str(room.get("id", "")))
        match_method = "id"
        if gt is None:
            candidates = gt_by_name.get(str(room.get("name", "")).strip().lower(), [])
            gt = next((item for item in candidates if id(item) not in matched_gt), None)
            match_method = "name"
        if gt is None:
            continue
        matched_gt.add(id(gt))
        pred_area = _polygon_area(room.get("polygon") or [])
        gt_area = _polygon_area(gt.get("polygon") or [])
        room_rows.append(
            {
                "pred_id": str(room.get("id", "")),
                "gt_id": str(gt.get("id", "")),
                "match_method": match_method,
                "pred_area_m2": round(pred_area, 4),
                "gt_area_m2": round(gt_area, 4),
                "absolute_area_error_m2": round(abs(pred_area - gt_area), 4),
                "relative_area_error": round(
                    abs(pred_area - gt_area) / max(gt_area, 1e-9), 4
                ),
            }
        )
    pred_wall_length = sum(_wall_length(row) for row in prediction.get("walls") or [])
    gt_wall_length = sum(_wall_length(row) for row in ground_truth.get("walls") or [])
    room_precision = len(room_rows) / max(len(pred_rooms), 1)
    room_recall = len(room_rows) / max(len(gt_rooms), 1)
    room_f1 = 2 * room_precision * room_recall / max(room_precision + room_recall, 1e-9)
    sources = prediction.get("sources") or []
    entities = [
        *(prediction.get("rooms") or []),
        *(prediction.get("walls") or []),
        *(prediction.get("openings") or []),
        *(prediction.get("fixtures") or []),
    ]
    traced_entities = sum(bool(entity.get("source_ref_ids")) for entity in entities)
    traceability = traced_entities / max(len(entities), 1)
    mean_room_area_error = (
        float(np.mean([row["relative_area_error"] for row in room_rows]))
        if room_rows
        else 1.0
    )
    wall_length_error = abs(pred_wall_length - gt_wall_length) / max(
        gt_wall_length, 1e-9
    )
    return {
        "rooms": {
            "count_pred": len(pred_rooms),
            "count_gt": len(gt_rooms),
            "matched": len(room_rows),
            "precision": round(room_precision, 4),
            "recall": round(room_recall, 4),
            "f1": round(room_f1, 4),
            "mean_relative_area_error": round(mean_room_area_error, 4),
            "matches": room_rows,
        },
        "walls": {
            "count_pred": len(prediction.get("walls") or []),
            "count_gt": len(ground_truth.get("walls") or []),
            "total_length_pred_m": round(pred_wall_length, 4),
            "total_length_gt_m": round(gt_wall_length, 4),
            "relative_total_length_error": round(wall_length_error, 4),
        },
        "counts": {
            key: {
                "pred": len(prediction.get(key) or []),
                "gt": len(ground_truth.get(key) or []),
                "delta": len(prediction.get(key) or [])
                - len(ground_truth.get(key) or []),
            }
            for key in ("rooms", "walls", "openings", "fixtures")
        },
        "traceability": {
            "source_count": len(sources),
            "entity_count": len(entities),
            "entities_with_source_refs": traced_entities,
            "coverage": round(traceability, 4),
        },
        "quality_gate": {
            "passed": (
                room_f1 >= 0.9
                and mean_room_area_error <= 0.07
                and wall_length_error <= 0.07
                and traceability == 1.0
            ),
            "targets": {
                "room_f1_min": 0.9,
                "mean_room_relative_area_error_max": 0.07,
                "wall_total_length_relative_error_max": 0.07,
                "traceability_coverage": 1.0,
            },
            "scope": "product acceptance target, not a claim of achieved field accuracy",
        },
    }
