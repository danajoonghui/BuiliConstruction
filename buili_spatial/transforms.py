"""Pure, validated spatial-transform math used by persistence services and tests."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .io_utils import canonical_json_sha256


IDENTITY_2D = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _validated_anchor_arrays(
    anchor_pairs: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    plan_points: list[list[float]] = []
    field_points: list[list[float]] = []
    labels: list[str] = []
    for index, pair in enumerate(anchor_pairs):
        plan = pair.get("plan")
        field = pair.get("field")
        if not isinstance(plan, (list, tuple)) or len(plan) != 2:
            raise ValueError(f"anchor {index} plan coordinate must be [x, y]")
        if not isinstance(field, (list, tuple)) or len(field) != 2:
            raise ValueError(f"anchor {index} field coordinate must be [x, y]")
        plan_row = [float(plan[0]), float(plan[1])]
        field_row = [float(field[0]), float(field[1])]
        if not all(math.isfinite(value) for value in [*plan_row, *field_row]):
            raise ValueError(f"anchor {index} coordinates must be finite")
        plan_points.append(plan_row)
        field_points.append(field_row)
        labels.append(str(pair.get("label") or f"anchor_{index + 1}"))
    return (
        np.asarray(plan_points, dtype=np.float64).reshape((-1, 2)),
        np.asarray(field_points, dtype=np.float64).reshape((-1, 2)),
        labels,
    )


def compute_similarity_transform(anchor_pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate a plan-to-field 2D similarity transform with evidence diagnostics.

    No synthetic field anchors are generated. One anchor can only establish a low-
    confidence translation. Two anchors establish a transform but have no residual
    redundancy, so confidence remains capped until a third independent anchor exists.
    """

    plan, field, labels = _validated_anchor_arrays(anchor_pairs)
    anchor_count = len(plan)
    if anchor_count == 0:
        payload = {
            "matrix": IDENTITY_2D,
            "scale": 1.0,
            "rotation_deg": 0.0,
            "mean_error_m": None,
            "max_error_m": None,
            "method": "identity_no_anchors",
            "confidence": 0.0,
            "requires_user_anchor": True,
            "anchor_count": 0,
            "warnings": ["ANCHORS_REQUIRED"],
            "residuals": [],
        }
        payload["transform_sha256"] = canonical_json_sha256(payload)
        return payload
    if anchor_count == 1:
        translation = field[0] - plan[0]
        matrix = [
            [1.0, 0.0, round(float(translation[0]), 6)],
            [0.0, 1.0, round(float(translation[1]), 6)],
            [0.0, 0.0, 1.0],
        ]
        payload = {
            "matrix": matrix,
            "scale": 1.0,
            "rotation_deg": 0.0,
            "mean_error_m": 0.0,
            "max_error_m": 0.0,
            "method": "single_anchor_translation_only",
            "confidence": 0.2,
            "requires_user_anchor": True,
            "anchor_count": 1,
            "warnings": ["ROTATION_AND_SCALE_UNVERIFIED"],
            "residuals": [{"label": labels[0], "error_m": 0.0}],
        }
        payload["transform_sha256"] = canonical_json_sha256(payload)
        return payload

    plan_center = plan.mean(axis=0)
    field_center = field.mean(axis=0)
    plan_zero = plan - plan_center
    field_zero = field - field_center
    denominator = float((plan_zero**2).sum())
    field_spread_sq = float((field_zero**2).sum())
    if denominator <= 1e-10 or field_spread_sq <= 1e-10:
        raise ValueError(
            "anchors must contain at least two distinct plan and field points"
        )

    covariance = field_zero.T @ plan_zero
    u, singular_values, vt = np.linalg.svd(covariance)
    correction = np.eye(2)
    if np.linalg.det(u @ vt) < 0:
        correction[-1, -1] = -1.0
    rotation = u @ correction @ vt
    scale = float(np.trace(np.diag(singular_values) @ correction) / denominator)
    if not math.isfinite(scale) or not 0.01 <= scale <= 100.0:
        raise ValueError(
            f"computed anchor scale {scale!r} is outside the safe range [0.01, 100]"
        )
    translation = field_center - scale * (rotation @ plan_center)
    projected = (scale * (rotation @ plan.T)).T + translation
    errors = np.linalg.norm(projected - field, axis=1)
    mean_error = float(errors.mean())
    max_error = float(errors.max())
    plan_span = float(
        max(
            math.hypot(*(plan[left] - plan[right]))
            for left in range(anchor_count)
            for right in range(left)
        )
    )
    residual_score = math.exp(-mean_error / 0.35)
    anchor_factor = min(1.0, 0.44 + 0.14 * anchor_count)
    spread_factor = min(1.0, plan_span / 2.0)
    confidence = residual_score * anchor_factor * (0.55 + 0.45 * spread_factor)
    confidence_cap = 0.65 if anchor_count == 2 else (0.9 if anchor_count == 3 else 0.98)
    confidence = max(0.0, min(confidence_cap, confidence))
    rotation_deg = math.degrees(math.atan2(rotation[1, 0], rotation[0, 0]))
    matrix = [
        [
            round(float(scale * rotation[0, 0]), 6),
            round(float(scale * rotation[0, 1]), 6),
            round(float(translation[0]), 6),
        ],
        [
            round(float(scale * rotation[1, 0]), 6),
            round(float(scale * rotation[1, 1]), 6),
            round(float(translation[1]), 6),
        ],
        [0.0, 0.0, 1.0],
    ]
    warnings = []
    if anchor_count == 2:
        warnings.append("NO_REDUNDANT_ANCHOR_FOR_RESIDUAL_VALIDATION")
    if plan_span < 1.0:
        warnings.append("ANCHOR_BASELINE_SHORT")
    if max_error > 0.5:
        warnings.append("ANCHOR_RESIDUAL_HIGH")
    payload = {
        "matrix": matrix,
        "scale": round(scale, 6),
        "rotation_deg": round(rotation_deg, 6),
        "mean_error_m": round(mean_error, 4),
        "max_error_m": round(max_error, 4),
        "method": "validated_umeyama_similarity_transform",
        "confidence": round(confidence, 4),
        "requires_user_anchor": confidence < 0.55,
        "anchor_count": anchor_count,
        "anchor_baseline_m": round(plan_span, 4),
        "warnings": warnings,
        "residuals": [
            {"label": label, "error_m": round(float(error), 4)}
            for label, error in zip(labels, errors, strict=True)
        ],
    }
    payload["transform_sha256"] = canonical_json_sha256(payload)
    return payload


def apply_transform(
    matrix: list[list[float]], point: tuple[float, float]
) -> tuple[float, float]:
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        raise ValueError("matrix must be 3x3")
    vector = np.array([float(point[0]), float(point[1]), 1.0], dtype=np.float64)
    result = np.asarray(matrix, dtype=np.float64) @ vector
    if abs(float(result[2])) <= 1e-12:
        raise ValueError("transform produced an invalid homogeneous coordinate")
    return float(result[0] / result[2]), float(result[1] / result[2])
