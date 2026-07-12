"""Public plan-parser facade.

Historic versions of this module mixed application models, filesystem storage, and
the parser. The facade is now pure; API persistence is implemented by
``buili_api.services.spatial``.
"""

from __future__ import annotations

from typing import Any

from .pipeline import SpatialPipelineError, parse_pdf_to_plan_graph


def plan_graph_provenance(graph: dict[str, Any]) -> dict[str, Any]:
    return dict((graph or {}).get("provenance") or {})


def plan_graph_is_current(
    graph: dict[str, Any],
    *,
    source_revision_id: str,
    source_hash: str,
    source_status: str,
) -> bool:
    provenance = plan_graph_provenance(graph)
    return bool(
        source_status in {"current", "approved"}
        and provenance.get("source_revision_id") == source_revision_id
        and provenance.get("source_hash") == source_hash
    )


def spatial_asset_is_current(
    asset_metadata: dict[str, Any], graph: dict[str, Any]
) -> bool:
    provenance = plan_graph_provenance(graph)
    return all(
        asset_metadata.get(key) == provenance.get(key)
        for key in ("source_revision_id", "source_hash", "source_revision")
    )


__all__ = [
    "SpatialPipelineError",
    "parse_pdf_to_plan_graph",
    "plan_graph_is_current",
    "plan_graph_provenance",
    "spatial_asset_is_current",
]
