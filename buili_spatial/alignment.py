"""DB-independent spatial alignment contracts.

Persistence belongs to the API service. Keeping this module pure prevents the
spatial package from importing an application's SQLAlchemy models or settings.
"""

from __future__ import annotations

from typing import Any

from .transforms import compute_similarity_transform


def compute_anchor_transform(anchor_pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Solve a validated 2D similarity transform from independent anchors."""

    return compute_similarity_transform(anchor_pairs)


def create_spatial_alignment(
    project_id: str,
    *,
    plan_graph_id: str,
    field_asset_id: str = "",
    anchor_pairs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a serializable alignment result without performing persistence.

    The caller is responsible for tenant authorization and for persisting this
    record. No-anchor inputs remain explicitly low-confidence; the function never
    fabricates an identity alignment suitable for official use.
    """

    if not project_id or not plan_graph_id:
        raise ValueError("project_id and plan_graph_id are required")
    pairs = list(anchor_pairs or [])
    transform = compute_anchor_transform(pairs)
    return {
        "schema_version": "buili.spatial-alignment.v1",
        "project_id": project_id,
        "plan_graph_id": plan_graph_id,
        "field_asset_id": field_asset_id,
        "transform": transform,
        "anchor_pairs": pairs,
        "confidence": float(transform.get("confidence") or 0.0),
        # A pure solve has not proven that the named graph/field assets are current
        # or within the same tenant. The API must persist and attest it before use.
        "official_use_blocked": True,
        "review_required": True,
        "review_reason": "runtime solve is not a persisted, source-verified alignment",
    }
