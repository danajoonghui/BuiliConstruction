"""Deterministic contracts and traceability for the PlanGraph pipeline."""

from __future__ import annotations

import copy
from typing import Any, Literal

from pydantic import ValidationError

from .io_utils import canonical_json_sha256
from .schemas import PlanGraphPayload, PipelineWarning


PLAN_GRAPH_SCHEMA_VERSION = "buili.plan-graph.v2"
SPATIAL_PIPELINE_VERSION = "2026.07.1"


class PlanGraphContractError(ValueError):
    """Raised when an extractor emits a payload that violates the pipeline contract."""


def _warning(
    code: str,
    message: str,
    *,
    stage: str,
    severity: Literal["info", "warning", "error"] = "warning",
    remediation: str = "",
) -> dict[str, Any]:
    return PipelineWarning(
        code=code,
        message=message,
        stage=stage,
        severity=severity,
        remediation=remediation,
    ).model_dump(mode="json")


def _source_ref_id(source: dict[str, Any]) -> str:
    stable = {
        "citation_chunk_id": source.get("citation_chunk_id", ""),
        "doc_id": source.get("doc_id", ""),
        "sheet_id": source.get("sheet_id", ""),
        "page": source.get("page"),
        "bbox": source.get("bbox", []),
        "source_type": source.get("source_type", ""),
        "revision": source.get("revision", ""),
    }
    return f"src_{canonical_json_sha256(stable)[:24]}"


def _normalise_legacy_source_bbox(source: dict[str, Any]) -> None:
    bbox = source.get("bbox")
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or any(isinstance(item, list) for item in bbox)
    ):
        return
    try:
        x0, y0, x1, y1 = (float(item) for item in bbox)
    except (TypeError, ValueError):
        return
    # Older room-label records stored [x, y, 0, 0] as a point marker.
    if source.get("source_type") == "room_label" and (x1 < x0 or y1 < y0):
        source["bbox"] = [x0, y0, x0, y0]


def _normalise_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    provenance = payload.get("provenance") or {}
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_source in payload.get("sources") or []:
        if not isinstance(raw_source, dict):
            continue
        source = copy.deepcopy(raw_source)
        _normalise_legacy_source_bbox(source)
        strength = str(source.get("source_strength") or "unverified")
        if strength not in {"strong", "display_review", "display_only", "unverified"}:
            strength = "unverified"
        source["source_strength"] = strength
        source.setdefault("revision", provenance.get("source_revision", ""))
        source.setdefault("source_hash", provenance.get("source_hash", ""))
        source.setdefault("sheet_id", payload.get("sheet_id", ""))
        source.setdefault("doc_id", provenance.get("source_doc_id", ""))
        source.setdefault("source_ref_id", _source_ref_id(source))
        fingerprint = canonical_json_sha256(
            {key: value for key, value in source.items() if key != "source_ref_id"}
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        sources.append(source)
    return sorted(
        sources,
        key=lambda source: (
            str(source.get("doc_id", "")),
            str(source.get("sheet_id", "")),
            int(source.get("page") or 0),
            str(source.get("source_type", "")),
            str(source.get("source_ref_id", "")),
        ),
    )


def _quality_summary(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings = list(payload.get("warnings") or [])
    scale = payload.get("scale") or {}
    rooms = payload.get("rooms") or []
    walls = payload.get("walls") or []
    openings = payload.get("openings") or []
    fixtures = payload.get("fixtures") or []
    sources = payload.get("sources") or []
    provenance = payload.get("provenance") or {}
    extraction = payload.get("extraction") or {}

    scale_confidence = max(0.0, min(1.0, float(scale.get("confidence") or 0.0)))
    geometry_confidence = min(0.95, 0.18 + min(len(walls), 24) / 32.0)
    if not rooms:
        geometry_confidence = min(geometry_confidence, 0.2)
    if len(walls) < 4:
        warnings.append(
            _warning(
                "INSUFFICIENT_WALL_GEOMETRY",
                "Fewer than four valid wall segments were extracted.",
                stage="geometry",
                remediation="Review the source crop or correct wall segments before approval.",
            )
        )
    if scale_confidence < 0.6:
        warnings.append(
            _warning(
                "SCALE_REQUIRES_CALIBRATION",
                "Drawing scale is estimated and is not suitable for dimensional claims.",
                stage="scale",
                remediation="Calibrate two source points with a verified real-world distance.",
            )
        )

    semantic_signals = min(
        1.0, (len(rooms) + min(len(openings), 8) + min(len(fixtures), 8)) / 12
    )
    semantics_confidence = 0.25 + semantic_signals * 0.65
    strong_sources = [
        source for source in sources if source.get("source_strength") == "strong"
    ]
    traceability_confidence = 0.0
    if sources:
        traceability_confidence = 0.35 + 0.35 * (len(strong_sources) / len(sources))
    if provenance.get("source_doc_id"):
        traceability_confidence += 0.15
    if provenance.get("source_hash"):
        traceability_confidence += 0.15
    traceability_confidence = min(1.0, traceability_confidence)
    if not provenance.get("source_hash"):
        warnings.append(
            _warning(
                "SOURCE_HASH_MISSING",
                "The source document has no SHA-256 digest in spatial provenance.",
                stage="provenance",
                remediation="Hash the immutable source revision before approving this graph.",
            )
        )
    if not sources:
        warnings.append(
            _warning(
                "SOURCE_REFERENCES_MISSING",
                "No source references were attached to extracted geometry.",
                stage="provenance",
                severity="error",
                remediation="Attach the source document, sheet and coordinate bounds.",
            )
        )
    if extraction.get("automatic_semantic_error"):
        warnings.append(
            _warning(
                "PRIMARY_EXTRACTOR_FALLBACK",
                "The primary semantic extractor failed and a lower-confidence fallback was used.",
                stage="extraction",
                remediation="Inspect extraction.automatic_semantic_error and manually review output.",
            )
        )
    if not openings:
        warnings.append(
            _warning(
                "NO_OPENINGS_DETECTED",
                "No doors or windows were detected; room connectivity may be incomplete.",
                stage="semantics",
                severity="info",
            )
        )

    overall = (
        geometry_confidence * 0.38
        + semantics_confidence * 0.22
        + scale_confidence * 0.18
        + traceability_confidence * 0.22
    )
    if any(
        item.get("severity") == "error" for item in warnings if isinstance(item, dict)
    ):
        overall = min(overall, 0.49)
    confidence = {
        "overall": round(max(0.0, min(1.0, overall)), 4),
        "geometry": round(max(0.0, min(1.0, geometry_confidence)), 4),
        "semantics": round(max(0.0, min(1.0, semantics_confidence)), 4),
        "scale": round(scale_confidence, 4),
        "traceability": round(traceability_confidence, 4),
        "method": "deterministic_weighted_quality_gates",
        "review_required": overall < 0.85 or bool(warnings),
    }
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in warnings:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("code", "")),
            str(item.get("stage", "")),
            str(item.get("entity_id", "")),
        )
        deduped[key] = item
    ordered_warnings = sorted(
        deduped.values(),
        key=lambda item: (
            {"error": 0, "warning": 1, "info": 2}.get(str(item.get("severity")), 3),
            str(item.get("stage", "")),
            str(item.get("code", "")),
        ),
    )
    return confidence, ordered_warnings


def _attach_default_source_refs(payload: dict[str, Any]) -> None:
    sources = payload.get("sources") or []
    primary_ids = [
        str(source.get("source_ref_id"))
        for source in sources
        if source.get("source_ref_id")
        and source.get("source_strength") in {"strong", "display_review"}
    ][:4]
    if not primary_ids:
        return
    for collection in ("rooms", "walls", "openings", "fixtures"):
        for entity in payload.get(collection) or []:
            if isinstance(entity, dict) and not entity.get("source_ref_ids"):
                entity["source_ref_ids"] = list(primary_ids)


def _sort_entities(payload: dict[str, Any]) -> None:
    payload["rooms"] = sorted(
        payload.get("rooms") or [], key=lambda row: str(row.get("id", ""))
    )
    payload["walls"] = sorted(
        payload.get("walls") or [], key=lambda row: str(row.get("id", ""))
    )
    payload["openings"] = sorted(
        payload.get("openings") or [],
        key=lambda row: (
            str(row.get("wall_id", "")),
            str(row.get("type", "")),
            str(row.get("source_entity_id", "")),
            tuple(row.get("center_m") or []),
            float(row.get("x_m") or 0.0),
        ),
    )
    payload["fixtures"] = sorted(
        payload.get("fixtures") or [],
        key=lambda row: (
            str(row.get("room_id", "")),
            str(row.get("type", "")),
            str(row.get("source_entity_id", "")),
        ),
    )


def finalize_plan_graph_payload(
    raw_payload: dict[str, Any],
    *,
    pipeline_version: str = SPATIAL_PIPELINE_VERSION,
) -> dict[str, Any]:
    """Normalize, validate and fingerprint an extractor payload.

    This is intentionally deterministic: identical source metadata and extraction
    output produce identical entity ordering, run ids, and content digests.
    """

    payload = copy.deepcopy(raw_payload)
    payload["schema_version"] = PLAN_GRAPH_SCHEMA_VERSION
    extraction = payload.setdefault("extraction", {})
    provenance = dict(payload.get("provenance") or {})
    for field in (
        "source_doc_id",
        "source_hash",
        "source_revision",
        "source_issue_date",
        "source_revision_id",
        "source_revision_state",
        "source_filename",
    ):
        provenance.setdefault(field, extraction.get(field, ""))
        if provenance.get(field) is None:
            provenance[field] = ""
        elif not isinstance(provenance.get(field), str):
            provenance[field] = str(provenance[field])
    payload["provenance"] = provenance
    payload["sources"] = _normalise_sources(payload)
    _attach_default_source_refs(payload)
    _sort_entities(payload)
    confidence, warnings = _quality_summary(payload)
    payload["confidence"] = confidence
    payload["warnings"] = warnings

    source_fingerprint = canonical_json_sha256(
        {
            "project_id": payload.get("project_id", ""),
            "sheet_id": payload.get("sheet_id", ""),
            "source_doc_id": provenance.get("source_doc_id", ""),
            "source_hash": provenance.get("source_hash", ""),
            "source_revision": provenance.get("source_revision", ""),
            "method": extraction.get("method", ""),
            "scale": payload.get("scale", {}),
        }
    )
    run_fingerprint = canonical_json_sha256(
        {"source_fingerprint": source_fingerprint, "pipeline_version": pipeline_version}
    )
    payload["pipeline"] = {
        "contract_version": PLAN_GRAPH_SCHEMA_VERSION,
        "pipeline_version": pipeline_version,
        "deterministic": True,
        "source_fingerprint": source_fingerprint,
        "run_id": f"spatial_{run_fingerprint[:24]}",
    }

    try:
        validated = PlanGraphPayload.model_validate(payload)
    except ValidationError as exc:
        raise PlanGraphContractError(str(exc)) from exc
    normalized = validated.model_dump(mode="json", by_alias=True, exclude_none=True)
    content_payload = copy.deepcopy(normalized)
    content_payload["pipeline"].pop("content_sha256", None)
    normalized["pipeline"]["content_sha256"] = canonical_json_sha256(content_payload)
    # Final validation ensures the hash augmentation did not alter the contract.
    return PlanGraphPayload.model_validate(normalized).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


def validate_plan_graph_payload(payload: dict[str, Any]) -> PlanGraphPayload:
    """Validate an already-finalized PlanGraph contract without mutating it."""

    try:
        return PlanGraphPayload.model_validate(payload)
    except ValidationError as exc:
        raise PlanGraphContractError(str(exc)) from exc
