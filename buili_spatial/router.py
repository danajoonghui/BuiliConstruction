"""Opt-in FastAPI routes for pure spatial runtime operations.

The router does not import application models, sessions, configuration, or storage.
An application must explicitly supply authentication and project-authorization
dependencies when mounting it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from .alignment import create_spatial_alignment
from .field_capture import create_field_asset_from_frames
from .schemas import AnchorPair


class RuntimeAlignmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_graph_id: str = Field(min_length=1, max_length=160)
    field_asset_id: str = Field(default="", max_length=160)
    anchor_pairs: list[AnchorPair] = Field(min_length=2, max_length=10_000)


class RuntimeFieldFrameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: str = Field(min_length=1, max_length=128)
    timestamp: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    rgb_uri: str = Field(default="", max_length=2048)
    depth_uri: str = Field(default="", max_length=2048)
    intrinsics_json: dict[str, Any] = Field(default_factory=dict)
    pose_json: dict[str, Any] = Field(default_factory=dict)
    blur_score: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    room_hint: str = Field(default="", max_length=300)


class RuntimeFieldManifestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frames: list[RuntimeFieldFrameIn] = Field(min_length=1, max_length=2_000)


def _envelope(request: Request, data: Any) -> dict[str, Any]:
    return {
        "data": data,
        "request_id": getattr(request.state, "request_id", ""),
        "meta": {"runtime": "buili_spatial"},
    }


def build_router(
    *,
    auth_dependency: Callable[..., Any],
    project_dependency: Callable[..., Any],
) -> APIRouter:
    """Build an authenticated router; dependencies are mandatory by design."""

    runtime = APIRouter(prefix="/v1", tags=["spatial-runtime"])
    @runtime.get("/spatial-runtime/capabilities")
    async def capabilities(
        request: Request, _user: Any = Depends(auth_dependency)
    ) -> dict[str, Any]:
        return _envelope(
            request,
            {
                "contract": "buili.plan-graph.v2",
                "alignment": "similarity-transform-with-independent-anchors",
                "field_manifest": "buili.field-evidence.v1",
                "persistence": "managed-by-buili-api",
                "official_use": "human-review-required",
            },
        )

    @runtime.post("/projects/{project_id}/spatial-runtime/alignment/solve")
    async def solve_alignment(
        project_id: str,
        payload: RuntimeAlignmentIn,
        request: Request,
        _project: Any = Depends(project_dependency),
    ) -> dict[str, Any]:
        result = create_spatial_alignment(
            project_id,
            plan_graph_id=payload.plan_graph_id,
            field_asset_id=payload.field_asset_id,
            anchor_pairs=[item.model_dump(mode="json") for item in payload.anchor_pairs],
        )
        return _envelope(request, result)

    @runtime.post("/projects/{project_id}/spatial-runtime/field-manifest")
    async def field_manifest(
        project_id: str,
        payload: RuntimeFieldManifestIn,
        request: Request,
        _project: Any = Depends(project_dependency),
    ) -> dict[str, Any]:
        return _envelope(
            request,
            create_field_asset_from_frames(
                project_id,
                [item.model_dump(mode="json") for item in payload.frames],
            ),
        )

    return runtime


__all__ = ["build_router"]
