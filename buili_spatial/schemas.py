"""Versioned API and pipeline schemas for Buili spatial processing.

These models validate untrusted API payloads as well as the JSON contract passed
between the 2D parser, geometry assembler, evidence pipeline, and persistence layer.
The models intentionally accept additive entity metadata so older extractors remain
compatible while malformed coordinates and broken references are rejected.
"""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
PositiveFiniteFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Point2D = tuple[FiniteFloat, FiniteFloat]


class PipelineWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=96)
    message: str = Field(min_length=1, max_length=1000)
    severity: Literal["info", "warning", "error"] = "warning"
    stage: str = Field(default="", max_length=96)
    entity_id: str = Field(default="", max_length=160)
    remediation: str = Field(default="", max_length=1000)


class ConfidenceSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    overall: Confidence = 0.0
    geometry: Confidence = 0.0
    semantics: Confidence = 0.0
    scale: Confidence = 0.0
    traceability: Confidence = 0.0
    method: str = "deterministic_weighted_quality_gates"


class SourceRevisionTrace(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_doc_id: str = ""
    source_hash: str = ""
    source_revision: str = ""
    source_revision_id: str = ""
    source_revision_state: str = "unclassified"
    source_issue_date: str = ""
    source_filename: str = ""

    @field_validator("source_hash")
    @classmethod
    def validate_source_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized and (
            len(normalized) != 64
            or any(char not in "0123456789abcdef" for char in normalized)
        ):
            raise ValueError("source_hash must be a 64-character SHA-256 hex digest")
        return normalized


class SpatialSourceRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_ref_id: str = ""
    citation_chunk_id: str = ""
    doc_id: str = ""
    sheet_id: str = ""
    page: int | None = Field(default=None, ge=1)
    bbox: list[FiniteFloat] | list[list[FiniteFloat]] = Field(default_factory=list)
    source_type: str = "citation_chunk"
    source_strength: Literal[
        "strong", "display_review", "display_only", "unverified"
    ] = "strong"
    revision: str = ""
    source_hash: str = ""

    @field_validator("bbox")
    @classmethod
    def validate_bbox(
        cls, value: list[float] | list[list[float]]
    ) -> list[float] | list[list[float]]:
        if not value:
            return value
        if isinstance(value[0], list):
            polygon = cast(list[list[float]], value)
            if len(polygon) < 3 or any(len(point) != 2 for point in polygon):
                raise ValueError(
                    "polygon bbox must contain at least three [x, y] points"
                )
            return value
        flat = cast(list[float], value)
        if len(flat) != 4:
            raise ValueError("flat bbox must contain [x0, y0, x1, y1]")
        x0, y0, x1, y1 = (float(item) for item in flat)
        if x1 < x0 or y1 < y0:
            raise ValueError("bbox maximum coordinates must be >= minimum coordinates")
        return value


class PlanGraphScale(BaseModel):
    model_config = ConfigDict(extra="allow")

    px_per_meter: PositiveFiniteFloat = 126.4
    source: str = "default_estimate"
    confidence: Confidence = 0.35
    calibrated_at_zoom: PositiveFiniteFloat | None = None


class PlanGraphRoom(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=300)
    polygon: list[Point2D] = Field(min_length=3, max_length=20_000)
    confidence: Confidence = 0.5
    source_ref_ids: list[str] = Field(default_factory=list)

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, polygon: list[Point2D]) -> list[Point2D]:
        # Shoelace area rejects collinear or collapsed rooms without requiring Shapely.
        area2 = sum(
            left[0] * right[1] - right[0] * left[1]
            for left, right in zip(polygon, [*polygon[1:], polygon[0]], strict=True)
        )
        if abs(area2) <= 1e-9:
            raise ValueError("room polygon must have non-zero area")
        return polygon


class PlanGraphWall(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(min_length=1, max_length=160)
    room_id: str = Field(default="", max_length=160)
    from_: Point2D = Field(alias="from")
    to: Point2D
    height_m: PositiveFiniteFloat = 2.7
    thickness_m: PositiveFiniteFloat = 0.12
    confidence: Confidence = 0.5
    source_ref_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_length(self) -> "PlanGraphWall":
        if math.hypot(self.to[0] - self.from_[0], self.to[1] - self.from_[1]) <= 1e-6:
            raise ValueError("wall endpoints must define a non-zero segment")
        return self


class PlanGraphOpening(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1, max_length=96)
    wall_id: str = Field(default="", max_length=160)
    x_m: NonNegativeFiniteFloat | None = None
    center_m: Point2D | None = None
    width_m: PositiveFiniteFloat = 0.9
    height_m: PositiveFiniteFloat | None = None
    sill_height_m: NonNegativeFiniteFloat | None = None
    source_entity_id: str = Field(default="", max_length=160)
    confidence: Confidence = 0.5
    source_ref_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_location(self) -> "PlanGraphOpening":
        if self.x_m is None and self.center_m is None:
            raise ValueError("opening requires x_m (distance along wall) or center_m")
        return self


class PlanGraphFixture(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1, max_length=96)
    room_id: str = Field(default="", max_length=160)
    wall_id: str = Field(default="", max_length=160)
    required_count: int = Field(default=1, ge=0, le=1_000_000)
    observed_count: int = Field(default=0, ge=0, le=1_000_000)
    bbox: list[FiniteFloat] = Field(default_factory=list, max_length=4)
    center_m: Point2D | None = None
    source_entity_id: str = Field(default="", max_length=160)
    confidence: Confidence = 0.5
    source_ref_ids: list[str] = Field(default_factory=list)

    @field_validator("bbox")
    @classmethod
    def validate_fixture_bbox(cls, bbox: list[float]) -> list[float]:
        if bbox and len(bbox) != 4:
            raise ValueError("fixture bbox must be empty or [x0, y0, x1, y1]")
        if bbox and (bbox[2] < bbox[0] or bbox[3] < bbox[1]):
            raise ValueError(
                "fixture bbox maximum coordinates must be >= minimum coordinates"
            )
        return bbox


class PlanGraphPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "buili.plan-graph.v2"
    project_id: str = Field(min_length=1, max_length=160)
    sheet_id: str = Field(min_length=1, max_length=160)
    scale: PlanGraphScale
    rooms: list[PlanGraphRoom] = Field(default_factory=list, max_length=10_000)
    walls: list[PlanGraphWall] = Field(default_factory=list, max_length=100_000)
    openings: list[PlanGraphOpening] = Field(default_factory=list, max_length=100_000)
    fixtures: list[PlanGraphFixture] = Field(default_factory=list, max_length=250_000)
    sources: list[SpatialSourceRef] = Field(default_factory=list, max_length=250_000)
    extraction: dict[str, Any] = Field(default_factory=dict)
    provenance: SourceRevisionTrace = Field(default_factory=SourceRevisionTrace)
    confidence: ConfidenceSummary = Field(default_factory=ConfidenceSummary)
    warnings: list[PipelineWarning] = Field(default_factory=list, max_length=10_000)
    pipeline: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_references(self) -> "PlanGraphPayload":
        room_ids = [room.id for room in self.rooms]
        wall_ids = [wall.id for wall in self.walls]
        if len(set(room_ids)) != len(room_ids):
            raise ValueError("room ids must be unique")
        if len(set(wall_ids)) != len(wall_ids):
            raise ValueError("wall ids must be unique")
        known_rooms = set(room_ids)
        known_walls = set(wall_ids)
        for wall in self.walls:
            if wall.room_id and wall.room_id not in known_rooms:
                raise ValueError(
                    f"wall {wall.id!r} references unknown room {wall.room_id!r}"
                )
        for opening in self.openings:
            if opening.wall_id and opening.wall_id not in known_walls:
                raise ValueError(f"opening references unknown wall {opening.wall_id!r}")
        for fixture in self.fixtures:
            if fixture.room_id and fixture.room_id not in known_rooms:
                raise ValueError(f"fixture references unknown room {fixture.room_id!r}")
            if fixture.wall_id and fixture.wall_id not in known_walls:
                raise ValueError(f"fixture references unknown wall {fixture.wall_id!r}")
        return self


class PlanGraphCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_doc_id: str | None = Field(default=None, max_length=160)
    sheet_id: str | None = Field(default=None, max_length=160)
    calibration_px: PositiveFiniteFloat | None = None
    calibration_m: PositiveFiniteFloat | None = None

    @model_validator(mode="after")
    def validate_calibration_pair(self) -> "PlanGraphCreateRequest":
        if (self.calibration_px is None) != (self.calibration_m is None):
            raise ValueError(
                "calibration_px and calibration_m must be supplied together"
            )
        return self


class PlanGraphOut(BaseModel):
    id: str
    project_id: str
    sheet_id: str
    graph_json: dict[str, Any]
    scale_json: dict[str, Any]
    source_doc_id: str
    version: int

    model_config = ConfigDict(from_attributes=True)


class Design3DRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_graph_id: str | None = Field(default=None, max_length=160)
    force: bool = False


class SpatialAssetOut(BaseModel):
    id: str
    project_id: str
    type: str
    uri: str
    metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class FieldPoseFrameCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: str = Field(min_length=1, max_length=160)
    timestamp: NonNegativeFiniteFloat = 0.0
    rgb_uri: str = Field(default="", max_length=2048)
    depth_uri: str = Field(default="", max_length=2048)
    intrinsics_json: dict[str, Any] = Field(default_factory=dict)
    pose_json: dict[str, Any] = Field(default_factory=dict)
    blur_score: Confidence = 0.0
    room_hint: str = Field(default="", max_length=300)


class FieldPoseFrameOut(BaseModel):
    id: str
    media_id: str
    timestamp: float
    rgb_uri: str
    depth_uri: str
    intrinsics_json: dict[str, Any]
    pose_json: dict[str, Any]
    blur_score: float
    room_hint: str

    model_config = ConfigDict(from_attributes=True)


class AnchorPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: Point2D
    field: Point2D
    label: str = Field(default="", max_length=160)


class SpatialAlignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_graph_id: str | None = Field(default=None, max_length=160)
    field_asset_id: str | None = Field(default=None, max_length=160)
    anchor_pairs: list[AnchorPair] = Field(default_factory=list, max_length=10_000)
    allow_low_confidence: bool = True


class SpatialAlignmentOut(BaseModel):
    id: str
    project_id: str
    plan_graph_id: str
    field_asset_id: str
    transform_json: dict[str, Any]
    anchor_pairs_json: list[dict[str, Any]]
    confidence: float

    model_config = ConfigDict(from_attributes=True)


class SpatialCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_graph_id: str | None = Field(default=None, max_length=160)
    alignment_id: str | None = Field(default=None, max_length=160)
    issue_ids: list[str] = Field(default_factory=list, max_length=10_000)
    update_issue_status: bool = True


class SpatialEvidenceOut(BaseModel):
    id: str
    issue_id: str
    room_graph_id: str
    design_asset_id: str
    field_asset_id: str
    geometry_features_json: dict[str, Any]
    snapshot_uri: str
    spatial_note: str

    model_config = ConfigDict(from_attributes=True)


class SpatialCompareOut(BaseModel):
    plan_graph_id: str
    alignment_id: str
    evidence: list[SpatialEvidenceOut]
