"""Safe, deterministic file IO primitives for spatial processing.

The spatial pipeline handles untrusted project uploads.  This module keeps path
validation and atomic writes in one place so individual extractors do not have to
reimplement (or forget) the same controls.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DEFAULT_MAX_UPLOAD_BYTES = 256 * 1024 * 1024


class SpatialIOError(ValueError):
    """Base class for safe-IO validation failures."""


class UnsafePathError(SpatialIOError):
    """Raised when an identifier or relative path could escape its storage root."""


class InputLimitError(SpatialIOError):
    """Raised when an input exceeds a configured processing limit."""


def validate_identifier(value: str, *, label: str = "identifier") -> str:
    """Validate an identifier before using it as a directory or filename fragment."""

    candidate = str(value or "").strip()
    if not SAFE_IDENTIFIER_RE.fullmatch(candidate) or candidate in {".", ".."}:
        raise UnsafePathError(
            f"{label} must be 1-128 ASCII letters, digits, '.', '_' or '-' and cannot traverse"
        )
    return candidate


def resolve_within(
    root: Path | str,
    *relative_parts: str | Path,
    must_exist: bool = False,
) -> Path:
    """Resolve ``relative_parts`` and prove the result remains below ``root``.

    Absolute components, ``..`` traversal, symlink escapes (when the parent exists),
    and Windows drive switches are rejected.
    """

    base = Path(root).expanduser().resolve()
    candidate = base.joinpath(*(Path(part) for part in relative_parts)).resolve(
        strict=False
    )
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise UnsafePathError(
            f"path escapes configured storage root: {candidate}"
        ) from exc
    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate


def spatial_project_dir(storage_root: Path | str, project_id: str) -> Path:
    """Return a validated project spatial directory, creating it if needed."""

    safe_project_id = validate_identifier(project_id, label="project_id")
    path = resolve_within(storage_root, "spatial", safe_project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_input_file(
    path: Path | str,
    *,
    allowed_suffixes: Iterable[str] | None = None,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    allow_empty: bool = False,
) -> Path:
    """Validate a local input without following user-provided output paths."""

    candidate = Path(path).expanduser().resolve(strict=True)
    if not candidate.is_file():
        raise SpatialIOError(f"input is not a regular file: {candidate}")
    suffixes = {suffix.lower() for suffix in allowed_suffixes or []}
    if suffixes and candidate.suffix.lower() not in suffixes:
        raise SpatialIOError(
            f"unsupported file extension {candidate.suffix!r}; expected one of {sorted(suffixes)}"
        )
    size = candidate.stat().st_size
    if size == 0 and not allow_empty:
        raise SpatialIOError("input file is empty")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if size > max_bytes:
        raise InputLimitError(
            f"input is {size} bytes; configured limit is {max_bytes} bytes"
        )
    return candidate


def sha256_file(path: Path | str, *, chunk_size: int = 1024 * 1024) -> str:
    """Stream a SHA-256 digest without loading a potentially large upload in memory."""

    candidate = Path(path)
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize JSON deterministically for hashing and reproducible artifacts."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _atomic_replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_bytes(path: Path | str, data: bytes) -> Path:
    candidate = Path(path)
    _atomic_replace(candidate, data)
    return candidate


def atomic_write_text(path: Path | str, text: str, *, encoding: str = "utf-8") -> Path:
    return atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path: Path | str, payload: Any, *, pretty: bool = True) -> Path:
    if pretty:
        text = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
        return atomic_write_text(path, text)
    return atomic_write_bytes(path, canonical_json_bytes(payload))


def atomic_save_image(path: Path | str, image: Any, **save_options: Any) -> Path:
    """Encode a Pillow-compatible image in memory, then atomically replace output."""

    candidate = Path(path)
    formats = {
        ".png": "PNG",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".webp": "WEBP",
        ".tif": "TIFF",
        ".tiff": "TIFF",
    }
    image_format = formats.get(candidate.suffix.lower())
    if image_format is None:
        raise SpatialIOError(
            f"unsupported image output extension: {candidate.suffix!r}"
        )
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, **save_options)
    return atomic_write_bytes(candidate, buffer.getvalue())


def require_finite(value: float, *, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number
