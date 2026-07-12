"""Trusted model-artifact loading helpers.

PyTorch pickle checkpoints can execute code while loading.  Spatial inference only
loads tensor/state dictionaries through ``weights_only=True`` unless an operator
explicitly opts into the legacy unsafe format.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .io_utils import sha256_file, validate_input_file


def safe_torch_checkpoint_load(
    torch_module: Any,
    path: Path,
    *,
    expected_sha256_env: str,
    max_bytes: int = 2 * 1024 * 1024 * 1024,
) -> dict[str, Any]:
    candidate = validate_input_file(
        path, allowed_suffixes={".pt", ".pth"}, max_bytes=max_bytes
    )
    expected_hash = os.environ.get(expected_sha256_env, "").strip().lower()
    actual_hash = sha256_file(candidate)
    if expected_hash and actual_hash != expected_hash:
        raise ValueError(
            f"model artifact SHA-256 mismatch for {candidate}; expected {expected_hash}, got {actual_hash}"
        )
    try:
        checkpoint = torch_module.load(candidate, map_location="cpu", weights_only=True)
    except TypeError as exc:
        if os.environ.get("BUILI_ALLOW_UNSAFE_CHECKPOINTS", "").lower() not in {
            "1",
            "true",
            "yes",
        }:
            raise RuntimeError(
                "installed PyTorch lacks safe weights_only loading; upgrade PyTorch or explicitly set "
                "BUILI_ALLOW_UNSAFE_CHECKPOINTS=true for a trusted artifact"
            ) from exc
        checkpoint = torch_module.load(candidate, map_location="cpu")
    if not isinstance(checkpoint, dict):
        raise ValueError("model artifact must contain a checkpoint dictionary")
    checkpoint.setdefault("artifact_sha256", actual_hash)
    return checkpoint
