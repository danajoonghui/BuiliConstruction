"""Stable callable facade for backend spatial jobs."""

from __future__ import annotations

import math
import copy
from pathlib import Path
from typing import Any

from .contracts import finalize_plan_graph_payload
from .io_utils import sha256_file, validate_input_file


class SpatialPipelineError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.retryable = retryable
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "stage": self.stage,
            "retryable": self.retryable,
            "details": self.details,
        }


def _stable_scene_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return only reproducible scene-build metadata for the immutable graph.

    Wall-clock timings belong in worker telemetry, not in a content-addressed
    PlanGraph. Persisting them made identical source PDFs produce different
    ``content_sha256`` values and therefore different immutable scene records.
    """

    def without_timings(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: without_timings(item)
                for key, item in value.items()
                if key != "stages"
                and key != "seconds"
                and not key.endswith("_seconds")
            }
        if isinstance(value, list):
            return [without_timings(item) for item in value]
        return copy.deepcopy(value)

    return without_timings(metadata)


def parse_pdf_to_plan_graph(
    pdf_path: Path | str,
    output_dir: Path | str,
    *,
    project_id: str,
    sheet_id: str,
    source_doc_id: str,
    source_revision_id: str,
    source_revision: str = "",
    source_issue_date: str = "",
    source_hash: str = "",
    source_filename: str = "",
    page_no: int = 1,
    px_per_meter: float = 100.0,
    scale_source: str = "backend_unverified_default",
    scale_confidence: float = 0.2,
    use_ocr: bool = True,
) -> dict[str, Any]:
    """Parse an immutable PDF revision into a canonical PlanGraph contract.

    The backend should pass the revision's immutable identifiers. If ``source_hash``
    is supplied it is verified against the file before parsing. The returned dict is
    canonical and safe to persist directly as the immutable SpatialScene input.
    """

    candidate = validate_input_file(pdf_path, allowed_suffixes={".pdf"})
    actual_hash = sha256_file(candidate)
    if source_hash and actual_hash.lower() != source_hash.strip().lower():
        raise SpatialPipelineError(
            "SOURCE_HASH_MISMATCH",
            "PDF bytes do not match the immutable document revision hash.",
            stage="input_validation",
            details={"expected": source_hash.lower(), "actual": actual_hash},
        )
    if page_no < 1:
        raise SpatialPipelineError(
            "INVALID_PAGE_NUMBER",
            "page_no must be one-based and >= 1",
            stage="input_validation",
        )
    if not math.isfinite(px_per_meter) or px_per_meter <= 0:
        raise SpatialPipelineError(
            "INVALID_SCALE",
            "px_per_meter must be a positive finite number",
            stage="input_validation",
        )
    if not math.isfinite(scale_confidence) or not 0 <= scale_confidence <= 1:
        raise SpatialPipelineError(
            "INVALID_SCALE_CONFIDENCE",
            "scale_confidence must be between 0 and 1",
            stage="input_validation",
        )
    destination = Path(output_dir).expanduser().resolve(strict=False)
    destination.mkdir(parents=True, exist_ok=True)
    try:
        from .semantic_auto import (
            build_semantic_scene_from_pdf,
            semantic_scene_to_plan_graph_payload,
        )

        scene, scene_metadata = build_semantic_scene_from_pdf(
            candidate,
            output_dir=destination,
            page_no=page_no,
            use_ocr=use_ocr,
        )
        scale = {
            "px_per_meter": px_per_meter,
            "source": scale_source,
            "confidence": scale_confidence,
            "calibrated_at_zoom": 2.5,
        }
        payload = semantic_scene_to_plan_graph_payload(
            scene,
            project_id=project_id,
            sheet_id=sheet_id,
            scale=scale,
            source_doc_id=source_doc_id,
            source_filename=source_filename or candidate.name,
        )
        # Persist stable storage-relative artifact names, never worker filesystem paths.
        payload["extraction"]["source_pdf"] = source_filename or candidate.name
        payload["extraction"]["derived_artifacts"] = {
            "source_page_png": Path(scene.source_page_png).name,
            "source_crop_png": Path(scene.source_crop_png).name,
        }
        payload["extraction"].pop("source_page_png", None)
        payload["extraction"].pop("source_crop_png", None)
        provenance = {
            "source_doc_id": source_doc_id,
            "source_hash": actual_hash,
            "source_revision": source_revision,
            "source_issue_date": source_issue_date,
            "source_revision_id": source_revision_id,
            "source_revision_state": "current",
            "source_filename": source_filename or candidate.name,
        }
        payload["provenance"] = provenance
        payload["extraction"].update(provenance)
        payload["extraction"]["scene_build"] = _stable_scene_metadata(scene_metadata)
        return finalize_plan_graph_payload(payload)
    except SpatialPipelineError:
        raise
    except Exception as exc:
        raise SpatialPipelineError(
            "PDF_SPATIAL_PARSE_FAILED",
            str(exc),
            stage="semantic_extraction",
            retryable=False,
            details={"source_doc_id": source_doc_id, "page_no": page_no},
        ) from exc
