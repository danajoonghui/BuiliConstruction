from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings
from ..models import Document, DocumentRevision, Job, PlanGraph, SpatialScene, new_id
from .storage import ObjectStorage


class SpatialService:
    def __init__(self, settings: Settings, storage: ObjectStorage):
        self.settings = settings
        self.storage = storage

    async def generate(self, session: AsyncSession, job: Job) -> dict[str, Any]:
        revision_id = str(job.input_json["source_revision_id"])
        # Serializes version allocation for every generation/review originating
        # from the same immutable drawing revision.
        revision = await session.scalar(
            select(DocumentRevision).where(DocumentRevision.id == revision_id).with_for_update()
        )
        document = await session.get(Document, revision.document_id) if revision else None
        if revision is None or document is None:
            raise ValueError("source document revision not found")
        if revision.content_type != "application/pdf" and not revision.storage_key.lower().endswith(".pdf"):
            raise ValueError("the local spatial parser currently requires a PDF drawing revision")
        data = await self.storage.read_bytes(revision.storage_key)
        source_hash = hashlib.sha256(data).hexdigest()
        if revision.sha256 and source_hash != revision.sha256:
            raise ValueError("immutable source checksum does not match the stored revision")
        revision.sha256 = source_hash
        graph_version = int(
            await session.scalar(
                select(func.max(PlanGraph.version)).where(
                    PlanGraph.project_id == document.project_id,
                    PlanGraph.source_revision_id == revision.id,
                )
            )
            or 0
        ) + 1
        scene_version = int(
            await session.scalar(
                select(func.max(SpatialScene.version)).where(
                    SpatialScene.project_id == document.project_id,
                    SpatialScene.source_revision_id == revision.id,
                )
            )
            or 0
        ) + 1
        scene_id = new_id("scn")

        try:
            from buili_spatial.geometry import build_design_glb
            from buili_spatial.pipeline import SpatialPipelineError, parse_pdf_to_plan_graph
        except ImportError:
            for parent in [Path.cwd(), *Path.cwd().parents]:
                if (parent / "buili_spatial" / "pipeline.py").exists():
                    sys.path.insert(0, str(parent))
                    break
            try:
                from buili_spatial.geometry import build_design_glb
                from buili_spatial.pipeline import SpatialPipelineError, parse_pdf_to_plan_graph
            except ImportError as nested:
                raise RuntimeError(
                    "buili_spatial runtime dependencies are unavailable; install the spatial package in the worker image"
                ) from nested

        with tempfile.TemporaryDirectory(prefix="buili-spatial-") as temporary:
            temp_root = Path(temporary)
            input_path = temp_root / "source.pdf"
            input_path.write_bytes(data)
            output_dir = temp_root / "derived"
            try:
                canonical = parse_pdf_to_plan_graph(
                    input_path,
                    output_dir,
                    project_id=document.project_id,
                    sheet_id=revision.sheet_number or document.title,
                    source_doc_id=document.id,
                    source_revision_id=revision.id,
                    source_revision=revision.revision,
                    source_issue_date=revision.issue_date.isoformat() if revision.issue_date else "",
                    source_hash=source_hash,
                    source_filename=revision.storage_key.rsplit("/", 1)[-1],
                    page_no=int((job.input_json.get("options") or {}).get("page_no", 1)),
                    px_per_meter=float((job.input_json.get("options") or {}).get("px_per_meter", 100.0)),
                    scale_source=str((job.input_json.get("options") or {}).get("scale_source", "backend_unverified_default")),
                    scale_confidence=float((job.input_json.get("options") or {}).get("scale_confidence", 0.2)),
                    use_ocr=bool((job.input_json.get("options") or {}).get("use_ocr", True)),
                )
            except SpatialPipelineError as exc:
                detail = exc.to_dict()
                raise RuntimeError(json.dumps(detail, ensure_ascii=False)) from exc

            provenance = canonical.get("provenance") or {}
            confidence = canonical.get("confidence") or {}
            warnings = canonical.get("warnings") or []
            blocking_warning = any(
                isinstance(item, dict) and str(item.get("severity", "")).lower() == "error"
                for item in warnings
            )
            review_required = bool(confidence.get("review_required", True)) or blocking_warning
            graph = PlanGraph(
                organization_id=document.organization_id,
                project_id=document.project_id,
                source_revision_id=revision.id,
                version=graph_version,
                status="review_required" if review_required else "generated",
                graph_json=canonical,
                scale_json=canonical.get("scale") or {},
                source_hash=source_hash,
                pipeline_version=str(provenance.get("pipeline_version") or canonical.get("pipeline_version") or ""),
                created_by=job.created_by,
            )
            session.add(graph)
            await session.flush()

            semantic_key = f"org/{document.organization_id}/project/{document.project_id}/spatial/{scene_id}/semantic.json"
            mapping_key = f"org/{document.organization_id}/project/{document.project_id}/spatial/{scene_id}/source-mapping.json"
            await self.storage.put_bytes(semantic_key, json.dumps(canonical, ensure_ascii=False).encode("utf-8"), "application/json")
            await self.storage.put_bytes(
                mapping_key,
                json.dumps({"sources": canonical.get("sources", []), "provenance": provenance}, ensure_ascii=False).encode("utf-8"),
                "application/json",
            )

            glb_key: str | None = None
            try:
                uri, _metadata = build_design_glb(
                    canonical, document.project_id, scene_id, storage_root=temp_root
                )
                glb_path = Path(uri)
                if not glb_path.is_absolute():
                    glb_path = temp_root / glb_path
                if glb_path.exists():
                    glb_key = f"org/{document.organization_id}/project/{document.project_id}/spatial/{scene_id}/scene.glb"
                    await self.storage.put_bytes(glb_key, glb_path.read_bytes(), "model/gltf-binary")
            except Exception:
                # Semantic output remains reviewable even when optional GLB rendering fails.
                glb_key = None
                warnings = [*warnings, {"severity": "warning", "code": "GLB_RENDER_FAILED"}]

            scene = SpatialScene(
                id=scene_id,
                organization_id=document.organization_id,
                project_id=document.project_id,
                source_revision_id=revision.id,
                plan_graph_id=graph.id,
                version=scene_version,
                status="review_required" if review_required else "generated",
                glb_storage_key=glb_key,
                semantic_storage_key=semantic_key,
                source_mapping_storage_key=mapping_key,
                confidence_json={"confidence": confidence, "warnings": warnings, "official_use_blocked": review_required},
                created_by=job.created_by,
            )
            session.add(scene)
            await session.flush()
            return {
                "scene_id": scene.id,
                "plan_graph_id": graph.id,
                "status": scene.status,
                "review_required": review_required,
                "semantic_storage_key": semantic_key,
                "glb_storage_key": glb_key,
                "run_id": canonical.get("run_id"),
                "contract_hash": canonical.get("contract_hash") or provenance.get("contract_hash"),
            }


def official_use_gate(graph: PlanGraph, scene: SpatialScene) -> list[str]:
    reasons: list[str] = []
    canonical = graph.graph_json or {}
    confidence = canonical.get("confidence") or {}
    warnings = canonical.get("warnings") or []
    attested = bool(graph.review_json.get("scale_verified") and graph.review_json.get("geometry_verified"))
    if confidence.get("review_required") and not attested:
        reasons.append("plan graph confidence requires review")
    for warning in warnings:
        if isinstance(warning, dict) and str(warning.get("severity", "")).lower() == "error":
            reasons.append(str(warning.get("message") or warning.get("code") or "blocking parser warning"))
    if not scene.semantic_storage_key:
        reasons.append("semantic scene output is missing")
    return reasons
