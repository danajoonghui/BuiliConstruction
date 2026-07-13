from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import triangulate, unary_union

from .contracts import validate_plan_graph_payload
from .io_utils import (
    atomic_write_bytes,
    sha256_file,
    spatial_project_dir,
    validate_identifier,
)


def _spatial_dir(project_id: str, *, storage_root: Path | None = None) -> Path:
    if storage_root is None:
        from ..config import get_settings

        storage_root = get_settings().storage_root
    return spatial_project_dir(storage_root, project_id)


def _as_polygon_parts(geometry: Any) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry] if not geometry.is_empty and geometry.area > 1e-8 else []
    if isinstance(geometry, MultiPolygon):
        return [
            polygon
            for polygon in geometry.geoms
            if not polygon.is_empty and polygon.area > 1e-8
        ]
    return [
        polygon
        for polygon in getattr(geometry, "geoms", [])
        if isinstance(polygon, Polygon) and not polygon.is_empty and polygon.area > 1e-8
    ]


def _clean_polygon_union(polygons: list[Polygon], *, simplify_m: float = 0.01) -> Any:
    if not polygons:
        return MultiPolygon([])
    merged = unary_union(polygons).buffer(0)
    # Square-join close/open removes tiny raster/vector slivers without rounding wall corners.
    merged = merged.buffer(0.002, join_style=2).buffer(-0.002, join_style=2).buffer(0)
    if simplify_m > 0:
        merged = merged.simplify(simplify_m, preserve_topology=True).buffer(0)
    return merged


def _add_polygon_cap(
    vertices: list[tuple[float, float, float]],
    indices: list[int],
    polygon: Polygon,
    *,
    y: float,
    top: bool,
) -> None:
    for triangle in triangulate(polygon):
        if triangle.area <= 1e-8 or not polygon.covers(triangle.representative_point()):
            continue
        coords = list(triangle.exterior.coords)[:3]
        points = [(float(x), y, float(z)) for x, z in coords]
        if top:
            points = [points[0], points[2], points[1]]
        start = len(vertices)
        vertices.extend(points)
        indices.extend([start, start + 1, start + 2])


def _add_ring_sides(
    vertices: list[tuple[float, float, float]],
    indices: list[int],
    coords: Any,
    *,
    bottom: float,
    top: float,
) -> None:
    points = list(coords)
    for (x0, z0), (x1, z1) in zip(points, points[1:], strict=False):
        if abs(float(x1) - float(x0)) + abs(float(z1) - float(z0)) <= 1e-8:
            continue
        start = len(vertices)
        vertices.extend(
            [
                (float(x0), bottom, float(z0)),
                (float(x1), bottom, float(z1)),
                (float(x1), top, float(z1)),
                (float(x0), top, float(z0)),
            ]
        )
        indices.extend(
            [
                start,
                start + 1,
                start + 2,
                start,
                start + 2,
                start + 3,
            ]
        )


def _add_extruded_polygon(
    vertices: list[tuple[float, float, float]],
    indices: list[int],
    geometry: Any,
    *,
    bottom: float,
    height: float,
) -> int:
    top = bottom + height
    part_count = 0
    for polygon in _as_polygon_parts(geometry):
        _add_polygon_cap(vertices, indices, polygon, y=top, top=True)
        if bottom != top:
            _add_polygon_cap(vertices, indices, polygon, y=bottom, top=False)
            _add_ring_sides(
                vertices, indices, polygon.exterior.coords, bottom=bottom, top=top
            )
            for interior in polygon.interiors:
                _add_ring_sides(
                    vertices, indices, interior.coords, bottom=bottom, top=top
                )
        part_count += 1
    return part_count


def _floor_union(graph: dict[str, Any]) -> Any:
    polygons: list[Polygon] = []
    for room in graph.get("rooms", []):
        coords = room.get("polygon") or []
        if len(coords) < 3:
            continue
        try:
            polygon = Polygon([(float(x), float(y)) for x, y in coords]).buffer(0)
        except (TypeError, ValueError):
            continue
        if polygon.area > 1e-8:
            polygons.append(polygon)
    return _clean_polygon_union(polygons, simplify_m=0.0)


def _wall_polygon(
    start_2d: list[float],
    end_2d: list[float],
    *,
    thickness: float,
) -> Polygon | None:
    sx, sy = float(start_2d[0]), float(start_2d[1])
    ex, ey = float(end_2d[0]), float(end_2d[1])
    dx = ex - sx
    dy = ey - sy
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        return None
    ux = dx / length
    uy = dy / length
    px = -uy * thickness / 2
    py = ux * thickness / 2
    return Polygon(
        [
            (sx + px, sy + py),
            (ex + px, ey + py),
            (ex - px, ey - py),
            (sx - px, sy - py),
        ]
    ).buffer(0)


def _wall_union(graph: dict[str, Any], *, thickness: float) -> tuple[Any, int]:
    polygons: list[Polygon] = []
    heights: list[float] = []
    for wall in graph.get("walls", []):
        polygon = _wall_polygon(
            wall.get("from") or [0, 0],
            wall.get("to") or [0, 0],
            thickness=thickness,
        )
        if polygon is None or polygon.area <= 1e-8:
            continue
        polygons.append(polygon)
        heights.append(float(wall.get("height_m") or 2.7))
    return _clean_polygon_union(polygons, simplify_m=0.006), len(polygons)


def _add_oriented_box(
    vertices: list[tuple[float, float, float]],
    indices: list[int],
    start_2d: list[float],
    end_2d: list[float],
    *,
    thickness: float,
    height: float,
    bottom: float = 0.0,
) -> None:
    sx, sy = float(start_2d[0]), float(start_2d[1])
    ex, ey = float(end_2d[0]), float(end_2d[1])
    dx = ex - sx
    dy = ey - sy
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        return
    ux = dx / length
    uy = dy / length
    px = -uy * thickness / 2
    py = ux * thickness / 2
    top = bottom + height
    corners = [
        (sx + px, bottom, sy + py),
        (ex + px, bottom, ey + py),
        (ex - px, bottom, ey - py),
        (sx - px, bottom, sy - py),
        (sx + px, top, sy + py),
        (ex + px, top, ey + py),
        (ex - px, top, ey - py),
        (sx - px, top, sy - py),
    ]
    base = len(vertices)
    vertices.extend(corners)
    faces = [
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 4, 5),
        (0, 5, 1),
        (1, 5, 6),
        (1, 6, 2),
        (2, 6, 7),
        (2, 7, 3),
        (3, 7, 4),
        (3, 4, 0),
    ]
    for face in faces:
        indices.extend([base + face[0], base + face[1], base + face[2]])


def _point_along_segment(
    start: list[float], end: list[float], distance: float
) -> list[float]:
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    length = math.hypot(ex - sx, ey - sy)
    if length <= 1e-9:
        return [sx, sy]
    ratio = max(0.0, min(1.0, distance / length))
    return [sx + (ex - sx) * ratio, sy + (ey - sy) * ratio]


def _opening_interval(
    wall: dict[str, Any], opening: dict[str, Any]
) -> tuple[float, float] | None:
    start = wall.get("from") or [0.0, 0.0]
    end = wall.get("to") or [0.0, 0.0]
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        return None
    center_m = opening.get("center_m")
    if isinstance(center_m, (list, tuple)) and len(center_m) >= 2:
        along = (
            (float(center_m[0]) - sx) * dx + (float(center_m[1]) - sy) * dy
        ) / length
        perpendicular = (
            abs((float(center_m[0]) - sx) * dy - (float(center_m[1]) - sy) * dx)
            / length
        )
        if perpendicular > max(0.5, float(opening.get("width_m") or 0.9)):
            return None
    elif opening.get("x_m") is not None:
        along = float(opening["x_m"])
    else:
        return None
    width = max(0.05, float(opening.get("width_m") or 0.9))
    left = max(0.0, along - width / 2)
    right = min(length, along + width / 2)
    if right - left <= 0.04:
        return None
    return left, right


def _add_wall_with_openings(
    vertices: list[tuple[float, float, float]],
    indices: list[int],
    wall: dict[str, Any],
    openings: list[dict[str, Any]],
) -> tuple[int, list[str]]:
    start = list(wall.get("from") or [0.0, 0.0])
    end = list(wall.get("to") or [0.0, 0.0])
    length = math.hypot(
        float(end[0]) - float(start[0]), float(end[1]) - float(start[1])
    )
    if length <= 1e-6:
        return 0, [f"DEGENERATE_WALL:{wall.get('id', '')}"]
    wall_height = float(wall.get("height_m") or 2.7)
    thickness = float(wall.get("thickness_m") or 0.12)
    intervals: list[tuple[float, float, dict[str, Any]]] = []
    warnings: list[str] = []
    for opening in openings:
        interval = _opening_interval(wall, opening)
        if interval is None:
            warnings.append(
                f"OPENING_NOT_ON_WALL:{opening.get('source_entity_id') or opening.get('type', '')}:"
                f"{wall.get('id', '')}"
            )
            continue
        intervals.append((interval[0], interval[1], opening))
    intervals.sort(
        key=lambda row: (
            row[0],
            row[1],
            str(row[2].get("type", "")),
            str(row[2].get("source_entity_id", "")),
        )
    )
    cursor = 0.0
    cut_count = 0
    for left, right, opening in intervals:
        if right <= cursor + 1e-6:
            warnings.append(f"OVERLAPPING_OPENING_SKIPPED:{wall.get('id', '')}")
            continue
        left = max(left, cursor)
        if left > cursor + 1e-6:
            _add_oriented_box(
                vertices,
                indices,
                _point_along_segment(start, end, cursor),
                _point_along_segment(start, end, left),
                thickness=thickness,
                height=wall_height,
            )
        opening_type = str(opening.get("type") or "door").lower()
        opening_height = float(
            opening.get("height_m") or (1.2 if opening_type == "window" else 2.1)
        )
        if opening_type == "window":
            sill = float(opening.get("sill_height_m") or 0.9)
            if sill > 0:
                _add_oriented_box(
                    vertices,
                    indices,
                    _point_along_segment(start, end, left),
                    _point_along_segment(start, end, right),
                    thickness=thickness,
                    height=min(sill, wall_height),
                )
            top = min(wall_height, sill + opening_height)
        else:
            top = min(wall_height, opening_height)
        if wall_height > top + 1e-6:
            _add_oriented_box(
                vertices,
                indices,
                _point_along_segment(start, end, left),
                _point_along_segment(start, end, right),
                thickness=thickness,
                height=wall_height - top,
                bottom=top,
            )
        cursor = right
        cut_count += 1
    if cursor < length - 1e-6:
        _add_oriented_box(
            vertices,
            indices,
            _point_along_segment(start, end, cursor),
            end,
            thickness=thickness,
            height=wall_height,
        )
    return cut_count, warnings


def _room_centers(graph: dict[str, Any]) -> dict[str, tuple[float, float]]:
    centers: dict[str, tuple[float, float]] = {}
    for room in graph.get("rooms", []):
        polygon = room.get("polygon") or []
        if not polygon:
            continue
        xs = [float(point[0]) for point in polygon]
        ys = [float(point[1]) for point in polygon]
        centers[str(room.get("id", ""))] = (sum(xs) / len(xs), sum(ys) / len(ys))
    return centers


def _add_fixture_proxy(
    vertices: list[tuple[float, float, float]],
    indices: list[int],
    center: tuple[float, float],
    fixture_type: str,
) -> None:
    x, z = center
    if "ceiling" in fixture_type or "diffuser" in fixture_type:
        bottom = 2.65
        height = 0.06
        size = 0.28
    elif "panel" in fixture_type or "equipment" in fixture_type:
        bottom = 0.6
        height = 1.0
        size = 0.35
    else:
        bottom = 0.35
        height = 0.18
        size = 0.16
    _add_oriented_box(
        vertices,
        indices,
        [x - size / 2, z],
        [x + size / 2, z],
        thickness=size,
        height=height,
        bottom=bottom,
    )


def _grid_metadata(vertices: list[tuple[float, float, float]]) -> dict[str, Any]:
    if not vertices:
        return {
            "origin_m": [0.0, 0.0],
            "spacing_m": 1.0,
            "bounds_m": [[0.0, 0.0], [0.0, 0.0]],
        }
    array = np.array(vertices, dtype=np.float32)
    min_x = float(array[:, 0].min())
    max_x = float(array[:, 0].max())
    min_z = float(array[:, 2].min())
    max_z = float(array[:, 2].max())
    spacing = 1.0
    origin_x = math.floor(min_x / spacing) * spacing
    origin_z = math.floor(min_z / spacing) * spacing
    return {
        "origin_m": [round(origin_x, 4), round(origin_z, 4)],
        "spacing_m": spacing,
        "bounds_m": [
            [round(min_x, 4), round(min_z, 4)],
            [round(max_x, 4), round(max_z, 4)],
        ],
    }


def _pad4(data: bytes, pad_byte: bytes = b"\x00") -> bytes:
    padding = (4 - (len(data) % 4)) % 4
    return data + pad_byte * padding


def _write_glb(
    path: Path, vertices: list[tuple[float, float, float]], indices: list[int]
) -> None:
    if not vertices:
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
        indices = [0, 1, 2]
    position_array = np.array(vertices, dtype=np.float32)
    index_array = np.array(indices, dtype=np.uint32)
    position_bytes = position_array.tobytes()
    position_padded = _pad4(position_bytes)
    index_offset = len(position_padded)
    index_bytes = index_array.tobytes()
    bin_blob = _pad4(position_padded + index_bytes)
    mins = position_array.min(axis=0).round(5).tolist()
    maxs = position_array.max(axis=0).round(5).tolist()
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "Buili Plan2Field-3D deterministic assembler",
        },
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "PlanGraph design reference"}],
        "meshes": [
            {
                "name": "PlanGraph parametric proxy mesh",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "indices": 1,
                        "mode": 4,
                        "material": 0,
                    }
                ],
            }
        ],
        "materials": [
            {
                "name": "Buili neutral material",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.72, 0.72, 0.68, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.85,
                },
            }
        ],
        "buffers": [{"byteLength": len(bin_blob)}],
        "bufferViews": [
            {
                "buffer": 0,
                "byteOffset": 0,
                "byteLength": len(position_bytes),
                "target": 34962,
            },
            {
                "buffer": 0,
                "byteOffset": index_offset,
                "byteLength": len(index_bytes),
                "target": 34963,
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(vertices),
                "type": "VEC3",
                "min": mins,
                "max": maxs,
            },
            {
                "bufferView": 1,
                "componentType": 5125,
                "count": len(indices),
                "type": "SCALAR",
            },
        ],
    }
    json_blob = _pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    total_length = 12 + 8 + len(json_blob) + 8 + len(bin_blob)
    blob = b"".join(
        [
            struct.pack("<4sII", b"glTF", 2, total_length),
            struct.pack("<I4s", len(json_blob), b"JSON"),
            json_blob,
            struct.pack("<I4s", len(bin_blob), b"BIN\x00"),
            bin_blob,
        ]
    )
    atomic_write_bytes(path, blob)


def _write_segmented_glb(
    path: Path,
    parts: list[tuple[str, list[tuple[float, float, float]], list[int], int]],
) -> None:
    """Write review-friendly GLB parts with stable semantic mesh names.

    Keeping floors, walls, and fixtures as separate primitives lets the web
    viewer apply transparency, edge outlines, and selection without rebuilding
    geometry client-side. The output remains deterministic and dependency-free.
    """

    populated = [part for part in parts if part[1] and part[2]]
    if not populated:
        populated = [
            (
                "Fallback geometry",
                [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
                [0, 1, 2],
                0,
            )
        ]

    binary = bytearray()
    buffer_views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []

    for mesh_index, (name, vertices, indices, material_index) in enumerate(populated):
        positions = np.array(vertices, dtype=np.float32)
        triangles = np.array(indices, dtype=np.uint32)

        position_offset = len(binary)
        position_bytes = positions.tobytes()
        binary.extend(_pad4(position_bytes))
        index_offset = len(binary)
        index_bytes = triangles.tobytes()
        binary.extend(_pad4(index_bytes))

        position_view = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": position_offset,
                "byteLength": len(position_bytes),
                "target": 34962,
            }
        )
        index_view = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": index_offset,
                "byteLength": len(index_bytes),
                "target": 34963,
            }
        )
        position_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": position_view,
                "componentType": 5126,
                "count": len(vertices),
                "type": "VEC3",
                "min": positions.min(axis=0).round(5).tolist(),
                "max": positions.max(axis=0).round(5).tolist(),
            }
        )
        index_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": index_view,
                "componentType": 5125,
                "count": len(indices),
                "type": "SCALAR",
            }
        )
        meshes.append(
            {
                "name": name,
                "primitives": [
                    {
                        "attributes": {"POSITION": position_accessor},
                        "indices": index_accessor,
                        "mode": 4,
                        "material": material_index,
                    }
                ],
                "extras": {"builiSemanticPart": name.lower().replace(" ", "_")},
            }
        )
        nodes.append({"mesh": mesh_index, "name": name})

    materials = [
        {
            "name": "Floor slab",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.92, 0.94, 0.93, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.92,
            },
            "doubleSided": True,
            "extensions": {"KHR_materials_unlit": {}},
        },
        {
            "name": "Review walls",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.72, 0.78, 0.75, 0.58],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.7,
            },
            "alphaMode": "BLEND",
            "doubleSided": True,
            "extensions": {"KHR_materials_unlit": {}},
        },
        {
            "name": "Discipline fixtures",
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.69, 0.55, 0.32, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.62,
            },
            "doubleSided": True,
            "extensions": {"KHR_materials_unlit": {}},
        },
    ]
    bin_blob = _pad4(bytes(binary))
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "BUILI SemanticScene deterministic review assembler",
        },
        "extensionsUsed": ["KHR_materials_unlit"],
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes))), "name": "BUILI review scene"}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "buffers": [{"byteLength": len(bin_blob)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }
    json_blob = _pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    total_length = 12 + 8 + len(json_blob) + 8 + len(bin_blob)
    atomic_write_bytes(
        path,
        b"".join(
            [
                struct.pack("<4sII", b"glTF", 2, total_length),
                struct.pack("<I4s", len(json_blob), b"JSON"),
                json_blob,
                struct.pack("<I4s", len(bin_blob), b"BIN\x00"),
                bin_blob,
            ]
        ),
    )


def build_design_glb(
    graph: dict[str, Any],
    project_id: str,
    asset_id: str,
    *,
    storage_root: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    validate_identifier(project_id, label="project_id")
    validate_identifier(asset_id, label="asset_id")
    validated = validate_plan_graph_payload(graph)
    graph = validated.model_dump(mode="json", by_alias=True, exclude_none=True)
    floor_vertices: list[tuple[float, float, float]] = []
    floor_indices: list[int] = []
    wall_vertices: list[tuple[float, float, float]] = []
    wall_indices: list[int] = []
    fixture_vertices: list[tuple[float, float, float]] = []
    fixture_indices: list[int] = []
    floor_geometry = _floor_union(graph)
    floor_parts = _add_extruded_polygon(
        floor_vertices, floor_indices, floor_geometry, bottom=-0.04, height=0.04
    )
    openings_by_wall: dict[str, list[dict[str, Any]]] = {}
    for opening in graph.get("openings", []):
        openings_by_wall.setdefault(str(opening.get("wall_id") or ""), []).append(
            opening
        )
    opening_cut_count = 0
    geometry_warnings: list[str] = []
    for wall in sorted(graph.get("walls", []), key=lambda row: str(row.get("id", ""))):
        cuts, warnings = _add_wall_with_openings(
            wall_vertices,
            wall_indices,
            wall,
            openings_by_wall.get(str(wall.get("id") or ""), []),
        )
        opening_cut_count += cuts
        geometry_warnings.extend(warnings)
    centers = _room_centers(graph)
    fixture_counts: dict[str, int] = {}
    for fixture in graph.get("fixtures", []):
        room_id = str(fixture.get("room_id", ""))
        count = fixture_counts.get(room_id, 0)
        fixture_counts[room_id] = count + 1
        center_m = fixture.get("center_m")
        if isinstance(center_m, list | tuple) and len(center_m) >= 2:
            center = (float(center_m[0]), float(center_m[1]))
            offset = 0.0
        else:
            center = centers.get(room_id, (0.5, 0.5))
            offset = ((count % 4) - 1.5) * 0.35
        _add_fixture_proxy(
            fixture_vertices,
            fixture_indices,
            (center[0] + offset, center[1] + math.floor(count / 4) * 0.25),
            str(fixture.get("type") or "fixture"),
        )

    out_dir = _spatial_dir(project_id, storage_root=storage_root)
    filename = f"{asset_id}_design.glb"
    path = out_dir / filename
    _write_segmented_glb(
        path,
        [
            ("Floor slab", floor_vertices, floor_indices, 0),
            ("Architectural walls", wall_vertices, wall_indices, 1),
            ("Discipline fixtures", fixture_vertices, fixture_indices, 2),
        ],
    )
    vertices = floor_vertices + wall_vertices + fixture_vertices
    triangle_count = (
        len(floor_indices) + len(wall_indices) + len(fixture_indices)
    ) // 3
    uri = f"spatial/{project_id}/{filename}"
    metadata = {
        "format": "glb",
        "assembly": "deterministic_plangraph_aperture_geometry_v2",
        "rooms": len(graph.get("rooms", [])),
        "walls": len(graph.get("walls", [])),
        "openings": len(graph.get("openings", [])),
        "fixtures": len(graph.get("fixtures", [])),
        "vertex_count": len(vertices),
        "triangle_count": triangle_count,
        "mesh_parts": ["floor", "walls", "fixtures"],
        "floor_polygon_parts": floor_parts,
        "wall_source_segments": len(graph.get("walls", [])),
        "wall_polygon_parts": len(graph.get("walls", [])),
        "wall_union_enabled": False,
        "opening_cut_count": opening_cut_count,
        "geometry_warnings": sorted(set(geometry_warnings)),
        "grid": _grid_metadata(vertices),
        "source_required_for_strong_evidence": True,
        "plan_graph_schema_version": graph.get("schema_version", ""),
        "source_fingerprint": (graph.get("pipeline") or {}).get(
            "source_fingerprint", ""
        ),
        "plan_graph_content_sha256": (graph.get("pipeline") or {}).get(
            "content_sha256", ""
        ),
        "artifact_sha256": sha256_file(path),
    }
    return uri, metadata
