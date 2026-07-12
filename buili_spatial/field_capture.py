"""Pure field-capture validation and manifest assembly."""

from __future__ import annotations

import math
from typing import Any

from .io_utils import canonical_json_sha256, validate_identifier


def _validate_numeric_tree(value: Any, *, label: str, depth: int = 0) -> None:
    if depth > 8:
        raise ValueError(f"{label} nesting exceeds the supported depth")
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError(f"{label} contains a non-finite number")
        return
    if isinstance(value, list):
        if len(value) > 10_000:
            raise ValueError(f"{label} contains too many values")
        for item in value:
            _validate_numeric_tree(item, label=label, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 1_000:
            raise ValueError(f"{label} contains too many keys")
        for item in value.values():
            _validate_numeric_tree(item, label=label, depth=depth + 1)
        return
    raise ValueError(f"{label} contains an unsupported value type")


def normalize_field_pose_frame(frame: dict[str, Any]) -> dict[str, Any]:
    media_id = validate_identifier(str(frame.get("media_id") or ""), label="media_id")
    timestamp = float(frame.get("timestamp") or 0.0)
    blur_score = float(frame.get("blur_score") or 0.0)
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("timestamp must be a non-negative finite number")
    if not math.isfinite(blur_score) or not 0 <= blur_score <= 1:
        raise ValueError("blur_score must be between 0 and 1")
    intrinsics = dict(frame.get("intrinsics_json") or {})
    pose = dict(frame.get("pose_json") or {})
    _validate_numeric_tree(intrinsics, label="intrinsics_json")
    _validate_numeric_tree(pose, label="pose_json")
    rgb_uri = str(frame.get("rgb_uri") or "")
    depth_uri = str(frame.get("depth_uri") or "")
    room_hint = str(frame.get("room_hint") or "")
    if len(rgb_uri) > 2048 or len(depth_uri) > 2048 or len(room_hint) > 300:
        raise ValueError("field-frame string value exceeds its contract limit")
    return {
        "media_id": media_id,
        "timestamp": timestamp,
        "rgb_uri": rgb_uri,
        "depth_uri": depth_uri,
        "intrinsics_json": intrinsics,
        "pose_json": pose,
        "has_depth": bool(depth_uri),
        "has_pose": bool(pose),
        "room_hint": room_hint,
        "blur_score": blur_score,
    }


def create_field_asset_from_frames(
    project_id: str, frames: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create the immutable JSON payload stored by the API storage adapter."""

    validate_identifier(project_id, label="project_id")
    normalized = sorted(
        (normalize_field_pose_frame(item) for item in frames),
        key=lambda item: (item["timestamp"], item["media_id"]),
    )
    if not normalized:
        raise ValueError("at least one field frame is required")
    has_depth = any(item["has_depth"] for item in normalized)
    has_pose = any(item["has_pose"] for item in normalized)
    low_quality_count = sum(item["blur_score"] < 0.22 for item in normalized)
    warnings: list[dict[str, str]] = []
    if not has_depth:
        warnings.append(
            {
                "code": "DEPTH_UNAVAILABLE",
                "message": "Depth is unavailable; dimensional claims require measurement evidence.",
            }
        )
    if not has_pose:
        warnings.append(
            {
                "code": "POSE_UNAVAILABLE",
                "message": "Camera pose is unavailable; localization must remain user anchored.",
            }
        )
    if low_quality_count:
        warnings.append(
            {
                "code": "LOW_IMAGE_QUALITY",
                "message": f"{low_quality_count} frame(s) have low blur-quality scores.",
            }
        )
    payload: dict[str, Any] = {
        "schema_version": "buili.field-evidence.v1",
        "project_id": project_id,
        "frames": normalized,
        "coverage": {
            "frame_count": len(normalized),
            "has_depth": has_depth,
            "has_pose": has_pose,
            "mode": "rgb_depth_pose" if has_depth and has_pose else "rgb_fallback",
            "low_quality_frame_count": low_quality_count,
        },
        "warnings": warnings,
        # This manifest is an intake contract, not a persisted or reviewer-attested
        # field model. Depth and pose improve quality but never authorize use alone.
        "official_use_blocked": True,
        "capture_quality_gate": "candidate" if has_depth and has_pose else "incomplete",
    }
    payload["manifest_sha256"] = canonical_json_sha256(payload)
    return payload


def ingest_field_pose_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible pure normalizer for one frame."""

    return normalize_field_pose_frame(frame)
