from __future__ import annotations

import json

import pytest

from buili_spatial.io_utils import (
    UnsafePathError,
    atomic_write_json,
    canonical_json_sha256,
    resolve_within,
    spatial_project_dir,
)


def test_path_traversal_is_rejected(tmp_path) -> None:
    with pytest.raises(UnsafePathError):
        resolve_within(tmp_path, "..", "escape.txt")
    with pytest.raises(UnsafePathError):
        spatial_project_dir(tmp_path, "../../escape")


def test_atomic_json_is_canonical_in_content(tmp_path) -> None:
    path = tmp_path / "nested" / "artifact.json"
    atomic_write_json(path, {"z": 1, "a": [2, 3]})
    assert json.loads(path.read_text("utf-8")) == {"a": [2, 3], "z": 1}
    assert canonical_json_sha256({"a": 1, "b": 2}) == canonical_json_sha256(
        {"b": 2, "a": 1}
    )
