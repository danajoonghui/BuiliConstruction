"""Build deterministic, recognizable GLB seed assets for the BUILI demo.

These are presentation-only objects. PlanGraph remains the source of truth for
position and dimensions. In production an approved Tripo-generated GLB can
replace any seed asset through the fixture asset registry without changing the
spatial record.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "apps" / "web" / "public" / "demo" / "fixture-assets",
    ROOT / "buili_demo_evidence" / "fixture-assets",
]

MATERIALS = [
    ("Powder-coated white", [0.78, 0.82, 0.8, 1.0], 0.05, 0.58),
    ("Brushed metal", [0.34, 0.39, 0.37, 1.0], 0.68, 0.3),
    ("Dark detail", [0.07, 0.09, 0.08, 1.0], 0.15, 0.5),
    ("Warm oak", [0.62, 0.39, 0.18, 1.0], 0.0, 0.72),
    ("Porcelain", [0.93, 0.95, 0.93, 1.0], 0.0, 0.32),
    ("Lens", [0.92, 0.91, 0.72, 1.0], 0.0, 0.28),
    ("BUILI green", [0.19, 0.57, 0.34, 1.0], 0.08, 0.46),
]


@dataclass
class Part:
    name: str
    vertices: list[tuple[float, float, float]]
    indices: list[int]
    material: int


def box(name: str, center, size, material: int) -> Part:
    cx, cy, cz = center
    sx, sy, sz = (item / 2 for item in size)
    vertices = [
        (cx - sx, cy - sy, cz - sz),
        (cx + sx, cy - sy, cz - sz),
        (cx + sx, cy + sy, cz - sz),
        (cx - sx, cy + sy, cz - sz),
        (cx - sx, cy - sy, cz + sz),
        (cx + sx, cy - sy, cz + sz),
        (cx + sx, cy + sy, cz + sz),
        (cx - sx, cy + sy, cz + sz),
    ]
    indices = [
        0,
        2,
        1,
        0,
        3,
        2,
        4,
        5,
        6,
        4,
        6,
        7,
        0,
        1,
        5,
        0,
        5,
        4,
        3,
        7,
        6,
        3,
        6,
        2,
        0,
        4,
        7,
        0,
        7,
        3,
        1,
        2,
        6,
        1,
        6,
        5,
    ]
    return Part(name, vertices, indices, material)


def cylinder(
    name: str,
    center,
    radius: float,
    length: float,
    axis: str,
    material: int,
    segments: int = 24,
) -> Part:
    vertices = []
    for direction in (-1, 1):
        for step in range(segments):
            angle = 2 * math.pi * step / segments
            a, b = radius * math.cos(angle), radius * math.sin(angle)
            longitudinal = direction * length / 2
            local = {
                "x": (longitudinal, a, b),
                "y": (a, longitudinal, b),
                "z": (a, b, longitudinal),
            }[axis]
            vertices.append(tuple(center[index] + local[index] for index in range(3)))
    vertices.extend(
        [
            tuple(
                center[index] - (length / 2 if axis == "xyz"[index] else 0)
                for index in range(3)
            ),
            tuple(
                center[index] + (length / 2 if axis == "xyz"[index] else 0)
                for index in range(3)
            ),
        ]
    )
    indices: list[int] = []
    bottom_center, top_center = 2 * segments, 2 * segments + 1
    for step in range(segments):
        nxt = (step + 1) % segments
        indices.extend(
            [step, nxt, segments + nxt, step, segments + nxt, segments + step]
        )
        indices.extend(
            [bottom_center, nxt, step, top_center, segments + step, segments + nxt]
        )
    return Part(name, vertices, indices, material)


def torus(
    name: str,
    center,
    major: float,
    minor: float,
    material: int,
    major_steps: int = 30,
    minor_steps: int = 10,
) -> Part:
    vertices = []
    for outer in range(major_steps):
        a = 2 * math.pi * outer / major_steps
        for inner in range(minor_steps):
            b = 2 * math.pi * inner / minor_steps
            radial = major + minor * math.cos(b)
            vertices.append(
                (
                    center[0] + radial * math.cos(a),
                    center[1] + minor * math.sin(b),
                    center[2] + radial * math.sin(a),
                )
            )
    indices = []
    for outer in range(major_steps):
        for inner in range(minor_steps):
            a = outer * minor_steps + inner
            b = ((outer + 1) % major_steps) * minor_steps + inner
            c = ((outer + 1) % major_steps) * minor_steps + (inner + 1) % minor_steps
            d = outer * minor_steps + (inner + 1) % minor_steps
            indices.extend([a, b, c, a, c, d])
    return Part(name, vertices, indices, material)


def combine(parts: list[Part], name: str, material: int) -> Part:
    selected = [part for part in parts if part.material == material]
    vertices: list[tuple[float, float, float]] = []
    indices: list[int] = []
    for part in selected:
        offset = len(vertices)
        vertices.extend(part.vertices)
        indices.extend(offset + item for item in part.indices)
    return Part(name, vertices, indices, material)


def pad4(data: bytes, value: bytes = b"\x00") -> bytes:
    return data + value * ((4 - len(data) % 4) % 4)


def write_glb(path: Path, parts: list[Part]) -> dict:
    parts = [
        combine(parts, MATERIALS[index][0], index) for index in range(len(MATERIALS))
    ]
    parts = [part for part in parts if part.vertices]
    binary = bytearray()
    views, accessors, meshes, nodes = [], [], [], []
    vertex_count = triangle_count = 0
    for mesh_index, part in enumerate(parts):
        positions = np.asarray(part.vertices, dtype=np.float32)
        triangles = np.asarray(part.indices, dtype=np.uint32)
        vertex_count += len(part.vertices)
        triangle_count += len(part.indices) // 3
        position_offset = len(binary)
        position_bytes = positions.tobytes()
        binary.extend(pad4(position_bytes))
        index_offset = len(binary)
        index_bytes = triangles.tobytes()
        binary.extend(pad4(index_bytes))
        pview = len(views)
        views.append(
            {
                "buffer": 0,
                "byteOffset": position_offset,
                "byteLength": len(position_bytes),
                "target": 34962,
            }
        )
        iview = len(views)
        views.append(
            {
                "buffer": 0,
                "byteOffset": index_offset,
                "byteLength": len(index_bytes),
                "target": 34963,
            }
        )
        paccessor = len(accessors)
        accessors.append(
            {
                "bufferView": pview,
                "componentType": 5126,
                "count": len(part.vertices),
                "type": "VEC3",
                "min": positions.min(axis=0).round(5).tolist(),
                "max": positions.max(axis=0).round(5).tolist(),
            }
        )
        iaccessor = len(accessors)
        accessors.append(
            {
                "bufferView": iview,
                "componentType": 5125,
                "count": len(part.indices),
                "type": "SCALAR",
            }
        )
        meshes.append(
            {
                "name": part.name,
                "primitives": [
                    {
                        "attributes": {"POSITION": paccessor},
                        "indices": iaccessor,
                        "mode": 4,
                        "material": part.material,
                    }
                ],
            }
        )
        nodes.append({"mesh": mesh_index, "name": part.name})
    blob = pad4(bytes(binary))
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "BUILI fixture seed asset generator v1",
        },
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": [
            {
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": color,
                    "metallicFactor": metal,
                    "roughnessFactor": rough,
                },
            }
            for name, color, metal, rough in MATERIALS
        ],
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": views,
        "accessors": accessors,
    }
    json_blob = pad4(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    total = 12 + 8 + len(json_blob) + 8 + len(blob)
    data = b"".join(
        [
            struct.pack("<4sII", b"glTF", 2, total),
            struct.pack("<I4s", len(json_blob), b"JSON"),
            json_blob,
            struct.pack("<I4s", len(blob), b"BIN\x00"),
            blob,
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "vertices": vertex_count,
        "triangles": triangle_count,
    }


def assets() -> dict[str, list[Part]]:
    light = [
        cylinder("Recessed housing", (0, 0.015, 0), 0.14, 0.16, "y", 2),
        torus("Trim ring", (0, -0.075, 0), 0.17, 0.025, 0),
        cylinder("Warm lens", (0, -0.07, 0), 0.135, 0.025, "y", 5),
    ]
    diffuser = [
        box("Diffuser face", (0, 0, 0), (0.52, 0.035, 0.52), 0),
        box("Central cone", (0, -0.03, 0), (0.24, 0.04, 0.24), 1),
    ]
    for offset in (-0.18, -0.09, 0, 0.09, 0.18):
        diffuser.extend(
            [
                box("Diffuser vane", (offset, -0.045, 0), (0.012, 0.025, 0.42), 1),
                box("Diffuser vane", (0, -0.045, offset), (0.42, 0.025, 0.012), 1),
            ]
        )
    return_grille = [box("Return frame", (0, 0, 0), (0.76, 0.04, 0.5), 0)]
    for offset in [-0.27, -0.18, -0.09, 0, 0.09, 0.18, 0.27]:
        return_grille.append(
            box("Return louver", (offset, -0.04, 0), (0.035, 0.035, 0.4), 2)
        )
    panel = [
        box("Panel cabinet", (0, 0, 0), (0.46, 0.82, 0.15), 1),
        box("Panel door", (0, 0, 0.086), (0.43, 0.78, 0.035), 0),
        box("Panel handle", (0.16, 0, 0.113), (0.035, 0.22, 0.025), 2),
    ]
    for row in range(6):
        panel.extend(
            [
                box(
                    "Breaker",
                    (-0.07, 0.24 - row * 0.095, 0.118),
                    (0.08, 0.045, 0.018),
                    2,
                ),
                box(
                    "Breaker",
                    (0.07, 0.24 - row * 0.095, 0.118),
                    (0.08, 0.045, 0.018),
                    2,
                ),
            ]
        )
    receptacle = [
        box("Faceplate", (0, 0, 0), (0.2, 0.3, 0.055), 0),
        cylinder("Upper outlet", (0, 0.07, 0.035), 0.045, 0.025, "z", 2, 16),
        cylinder("Lower outlet", (0, -0.07, 0.035), 0.045, 0.025, "z", 2, 16),
    ]
    ahu = [
        box("AHU cabinet", (0, 0.03, 0), (1.0, 1.3, 0.76), 0),
        box("Access panel", (0, 0.03, 0.395), (0.76, 0.92, 0.035), 1),
        cylinder("Supply collar", (0, 0.78, 0), 0.24, 0.35, "y", 1),
    ]
    for row in (-0.28, -0.14, 0, 0.14, 0.28):
        ahu.append(box("AHU louver", (0, row, 0.42), (0.62, 0.045, 0.035), 2))
    casework = [
        box("Cabinet carcass", (0, 0, 0), (1.28, 0.86, 0.58), 0),
        box("Countertop", (0, 0.47, 0), (1.36, 0.06, 0.64), 1),
    ]
    for x in (-0.42, 0, 0.42):
        casework.extend(
            [
                box("Cabinet door", (x, 0, 0.305), (0.37, 0.68, 0.025), 0),
                cylinder(
                    "Cabinet pull", (x + 0.12, 0.08, 0.33), 0.012, 0.16, "y", 1, 12
                ),
            ]
        )
    sink = [
        box("Sink rim", (0, 0, 0), (0.86, 0.08, 0.56), 1),
        torus("Sink basin rim", (0, 0.055, 0), 0.19, 0.025, 4),
        cylinder("Faucet riser", (0, 0.22, -0.2), 0.018, 0.36, "y", 1, 14),
        cylinder("Faucet spout", (0, 0.39, -0.1), 0.018, 0.2, "z", 1, 14),
    ]
    vanity = [
        box("Vanity body", (0, 0, 0), (0.88, 0.82, 0.54), 0),
        box("Vanity counter", (0, 0.45, 0), (0.94, 0.06, 0.6), 4),
        torus("Vanity basin", (0, 0.49, 0), 0.16, 0.024, 4),
        cylinder("Vanity faucet", (0, 0.64, -0.18), 0.016, 0.26, "y", 1, 12),
    ]
    return {
        "ceiling_light": light,
        "ceiling_diffuser": diffuser,
        "ceiling_return": return_grille,
        "electrical_panel": panel,
        "receptacle": receptacle,
        "mechanical_equipment": ahu,
        "casework": casework,
        "sink": sink,
        "vanity": vanity,
    }


def main() -> None:
    registry = {"schema": "buili.fixture-asset-registry.v1", "assets": {}}
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for stale in target.glob("*.glb"):
            stale.unlink()
    for semantic_type, parts in assets().items():
        staging = TARGETS[0] / f".{semantic_type}.staging.glb"
        metadata = write_glb(staging, parts)
        filename = f"{semantic_type}.{metadata['sha256'][:12]}.glb"
        staging.replace(TARGETS[0] / filename)
        for target in TARGETS[1:]:
            current = write_glb(target / filename, parts)
            if current["sha256"] != metadata["sha256"]:
                raise RuntimeError(f"Non-deterministic GLB output for {semantic_type}")
        registry["assets"][semantic_type] = {
            "uri": f"/demo/fixture-assets/{filename}",
            "status": "approved_demo_seed",
            "provider": "buili_deterministic_seed",
            "license": "BUILI-owned generated demo asset",
            **(metadata or {}),
        }
    for target in TARGETS:
        (target / "registry.json").write_text(
            json.dumps(registry, indent=2), encoding="utf-8"
        )
    print(json.dumps(registry, indent=2))


if __name__ == "__main__":
    main()
