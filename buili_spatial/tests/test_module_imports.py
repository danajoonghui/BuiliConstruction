from __future__ import annotations

import importlib


def test_public_spatial_modules_import_without_application_package() -> None:
    for module in (
        "buili_spatial.alignment",
        "buili_spatial.compare",
        "buili_spatial.field_capture",
        "buili_spatial.plan_parser",
        "buili_spatial.router",
    ):
        assert importlib.import_module(module)


def test_field_manifest_never_claims_metric_verification_without_depth_pose() -> None:
    from buili_spatial.field_capture import create_field_asset_from_frames

    result = create_field_asset_from_frames(
        "project-1",
        [
            {
                "media_id": "evidence-1",
                "timestamp": 1,
                "rgb_uri": "evidence/photo.jpg",
                "blur_score": 0.8,
            }
        ],
    )
    assert result["coverage"]["mode"] == "rgb_fallback"
    assert result["official_use_blocked"] is True
    assert {item["code"] for item in result["warnings"]} == {
        "DEPTH_UNAVAILABLE",
        "POSE_UNAVAILABLE",
    }
