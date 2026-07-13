from pathlib import Path

import pytest
from pydantic import ValidationError

from buili_api.core.config import Settings
from buili_api.services.fixture_assets import inspect_glb


ROOT = Path(__file__).resolve().parents[3]


def test_generated_fixture_asset_is_a_reviewable_glb() -> None:
    registry_path = ROOT / "apps" / "web" / "public" / "demo" / "fixture-assets"
    asset_path = next(registry_path.glob("electrical_panel.*.glb"))

    inspection = inspect_glb(asset_path.read_bytes())

    assert inspection.vertex_count >= 100
    assert inspection.face_count >= 150
    assert inspection.bounds["min"] != inspection.bounds["max"]


def test_fixture_asset_inspection_rejects_non_glb_bytes() -> None:
    with pytest.raises(ValueError, match="not a GLB"):
        inspect_glb(b"not a model")


def test_tripo_requires_a_server_side_api_key() -> None:
    with pytest.raises(ValidationError, match="TRIPO_API_KEY"):
        Settings(_env_file=None, BUILI_TRIPO_ENABLED="true", TRIPO_API_KEY="")


def test_tripo_model_and_download_hosts_are_pinned() -> None:
    settings = Settings(
        _env_file=None,
        BUILI_TRIPO_ENABLED="true",
        TRIPO_API_KEY="server-side-test-key",
        BUILI_TRIPO_MODEL_VERSION="P1-20260311",
        BUILI_TRIPO_DOWNLOAD_HOST_SUFFIXES="tripo3d.ai,tripo3d.com",
    )

    assert settings.tripo_model_version == "P1-20260311"
    assert settings.tripo_download_hosts == ("tripo3d.ai", "tripo3d.com")
