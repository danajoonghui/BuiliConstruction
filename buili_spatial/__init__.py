"""Buili Plan2Field spatial evidence services.

The public imports below are intentionally DB-independent so API workers, batch jobs,
and evaluation tooling can share one stable contract.
"""

from .analysis import (
    DeterministicAnalysisAdapter,
    MediaAnalysisResult,
    MediaAnalysisService,
    OpenAIAnalysisAdapter,
    build_default_analysis_service,
)
from .contracts import (
    PLAN_GRAPH_SCHEMA_VERSION,
    SPATIAL_PIPELINE_VERSION,
    PlanGraphContractError,
    finalize_plan_graph_payload,
    validate_plan_graph_payload,
)
from .pipeline import SpatialPipelineError, parse_pdf_to_plan_graph
from .transforms import apply_transform, compute_similarity_transform

__version__ = SPATIAL_PIPELINE_VERSION

__all__ = [
    "PLAN_GRAPH_SCHEMA_VERSION",
    "SPATIAL_PIPELINE_VERSION",
    "DeterministicAnalysisAdapter",
    "MediaAnalysisResult",
    "MediaAnalysisService",
    "OpenAIAnalysisAdapter",
    "PlanGraphContractError",
    "SpatialPipelineError",
    "apply_transform",
    "build_default_analysis_service",
    "compute_similarity_transform",
    "finalize_plan_graph_payload",
    "parse_pdf_to_plan_graph",
    "validate_plan_graph_payload",
]
