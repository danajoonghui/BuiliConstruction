# Buili Spatial

CPU-first, source-traceable contracts for PDF plan parsing, lightweight GLB
assembly, field-evidence quality analysis, alignment, and evaluation.

## Backend contract

```python
from buili_spatial import parse_pdf_to_plan_graph

plan_graph = parse_pdf_to_plan_graph(
    revision_file,
    derived_output_dir,
    project_id=project_id,
    sheet_id=sheet_number,
    source_doc_id=document_id,
    source_revision_id=revision_id,
    source_hash=sha256,
    px_per_meter=calibrated_px_per_meter,
    scale_source="user_calibration",
    scale_confidence=0.95,
)
```

Persist the complete returned JSON. Official approval must remain blocked while a
warning has severity `error`, while `confidence.review_required` is true, or while
the source revision is no longer current.

`buili_spatial` is deliberately independent of the application's ORM, storage, and
tenant model. The production API persists parser results through
`buili_api.services.spatial`. Optional runtime endpoints are mounted with
`buili_spatial.router.build_router(...)`; both an authentication dependency and a
project-authorization dependency are mandatory.

The external AI adapter is off by default. A key alone does not enable uploads. An
operator must set `BUILI_EXTERNAL_AI_ENABLED=true` and explicitly configure model
names; provider failures retain deterministic local results.

## CLI

```text
python -m buili_spatial validate-plan plan.json -o canonical.json
python -m buili_spatial analyze capture.jpg -o analysis.json
python -m buili_spatial align anchors.json
python -m buili_spatial parse-pdf drawing.pdf derived/ \
  --project-id project_1 --sheet-id A-101 \
  --source-doc-id doc_1 --source-revision-id rev_1
python -m buili_spatial build-glb canonical.json storage/ \
  --project-id project_1 --asset-id scene_1
```

## Accuracy boundary

The deterministic fallback extracts a lightweight spatial index. It is not survey,
fabrication, code-compliance, entitlement, or autonomous defect evidence. Scale,
openings, hidden conditions, MEP elevation, and model/field discrepancies require
calibration, independent field evidence, and human approval.
