from __future__ import annotations

import pytest

from buili_spatial.transforms import apply_transform, compute_similarity_transform


def test_similarity_transform_recovers_known_mapping() -> None:
    # field = 2 * rotate90(plan) + [10, -3]
    pairs = [
        {"plan": [0, 0], "field": [10, -3], "label": "a"},
        {"plan": [2, 0], "field": [10, 1], "label": "b"},
        {"plan": [2, 2], "field": [6, 1], "label": "c"},
        {"plan": [0, 2], "field": [6, -3], "label": "d"},
    ]
    result = compute_similarity_transform(pairs)
    assert result["scale"] == pytest.approx(2.0)
    assert result["rotation_deg"] == pytest.approx(90.0)
    assert result["mean_error_m"] == pytest.approx(0.0)
    assert apply_transform(result["matrix"], (1, 1)) == pytest.approx((8, -1))
    assert result["confidence"] > 0.85
    assert len(result["transform_sha256"]) == 64


def test_no_anchor_never_fabricates_alignment() -> None:
    result = compute_similarity_transform([])
    assert result["method"] == "identity_no_anchors"
    assert result["confidence"] == 0.0
    assert result["requires_user_anchor"] is True


def test_two_anchors_are_confidence_capped() -> None:
    result = compute_similarity_transform(
        [{"plan": [0, 0], "field": [1, 1]}, {"plan": [2, 0], "field": [3, 1]}]
    )
    assert result["confidence"] <= 0.65
    assert "NO_REDUNDANT_ANCHOR_FOR_RESIDUAL_VALIDATION" in result["warnings"]


def test_degenerate_anchors_are_rejected() -> None:
    with pytest.raises(ValueError, match="distinct"):
        compute_similarity_transform(
            [{"plan": [1, 1], "field": [2, 2]}, {"plan": [1, 1], "field": [2, 2]}]
        )
