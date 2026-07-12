"""Grounded photo, audio, and document analysis adapters.

The deterministic adapter always runs first and never claims visual objects or spoken
content it cannot verify.  An external model adapter is opt-in, environment-driven,
and additive: provider output cannot replace source hashes, quality measurements, or
human-review gates.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import wave
from pathlib import Path
from typing import Any, Literal, Protocol

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from pydantic import BaseModel, ConfigDict, Field

from .io_utils import (
    InputLimitError,
    SpatialIOError,
    sha256_file,
    validate_input_file,
)


AssetKind = Literal["image", "audio", "document"]

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff"}
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}
DOCUMENT_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".json", ".log"}


class AnalysisObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=4000)
    category: str = Field(default="general", max_length=96)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence_type: Literal["measured", "extracted", "model_inference"]
    source_locator: dict[str, Any] = Field(default_factory=dict)


class AnalysisWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=96)
    message: str = Field(min_length=1, max_length=1000)
    remediation: str = Field(default="", max_length=1000)


class MediaAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "buili.media-analysis.v1"
    kind: AssetKind
    filename: str
    source_sha256: str
    source_size_bytes: int = Field(ge=0)
    provider: str = "deterministic_local"
    model: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    observations: list[AnalysisObservation] = Field(default_factory=list)
    extracted_text: str = ""
    transcript: str = ""
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    review_required: bool = True


class RichAnalysisAdapter(Protocol):
    name: str

    def analyze(
        self,
        path: Path,
        kind: AssetKind,
        deterministic: MediaAnalysisResult,
    ) -> dict[str, Any]: ...


def detect_asset_kind(path: Path | str) -> AssetKind:
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in AUDIO_SUFFIXES:
        return "audio"
    if suffix in DOCUMENT_SUFFIXES:
        return "document"
    raise SpatialIOError(f"unsupported analysis file extension: {suffix!r}")


def _warning(code: str, message: str, remediation: str = "") -> AnalysisWarning:
    return AnalysisWarning(code=code, message=message, remediation=remediation)


def _image_analysis(path: Path) -> MediaAnalysisResult:
    candidate = validate_input_file(
        path, allowed_suffixes=IMAGE_SUFFIXES, max_bytes=80 * 1024 * 1024
    )
    warnings: list[AnalysisWarning] = []
    try:
        with Image.open(candidate) as source:
            source.verify()
        with Image.open(candidate) as source:
            orientation = source.getexif().get(274)
            image = ImageOps.exif_transpose(source).convert("RGB")
            width, height = image.size
    except Exception as exc:
        raise SpatialIOError(f"image cannot be decoded safely: {exc}") from exc

    if width * height > 80_000_000:
        raise InputLimitError("decoded image exceeds the 80-megapixel safety limit")
    # Downsample before quality analysis to bound memory while keeping output deterministic.
    sample = image.copy()
    sample.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    sample_gray = np.asarray(sample.convert("L"), dtype=np.float32)
    edges = np.asarray(
        sample.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32
    )
    edge_variance = float(np.var(edges))
    luminance_mean = float(sample_gray.mean()) if sample_gray.size else 0.0
    luminance_std = float(sample_gray.std()) if sample_gray.size else 0.0
    dark_fraction = float(np.mean(sample_gray <= 12)) if sample_gray.size else 0.0
    bright_fraction = float(np.mean(sample_gray >= 243)) if sample_gray.size else 0.0
    blur_quality = max(0.0, min(1.0, edge_variance / 900.0))
    exposure_quality = max(0.0, 1.0 - dark_fraction - bright_fraction)
    resolution_quality = max(0.0, min(1.0, math.sqrt(width * height) / 1600.0))
    confidence = (
        0.45 * blur_quality + 0.35 * exposure_quality + 0.20 * resolution_quality
    )

    if min(width, height) < 720:
        warnings.append(
            _warning(
                "LOW_RESOLUTION",
                "The shorter image edge is below 720 pixels.",
                "Capture a closer, higher-resolution image before making dimensional claims.",
            )
        )
    if blur_quality < 0.22:
        warnings.append(
            _warning(
                "POSSIBLE_BLUR",
                "Local edge energy is low; important installation details may be unreadable.",
                "Retake the photo while stationary and ensure the target is in focus.",
            )
        )
    if dark_fraction > 0.35:
        warnings.append(
            _warning(
                "UNDEREXPOSED",
                "A large fraction of pixels are near black.",
                "Add lighting or flash.",
            )
        )
    if bright_fraction > 0.35:
        warnings.append(
            _warning(
                "OVEREXPOSED",
                "A large fraction of pixels are clipped near white.",
                "Reduce glare or exposure.",
            )
        )

    observations = [
        AnalysisObservation(
            statement=f"Decoded image is {width} by {height} pixels.",
            category="file_integrity",
            confidence=1.0,
            evidence_type="measured",
            source_locator={"full_image": True},
        )
    ]
    return MediaAnalysisResult(
        kind="image",
        filename=candidate.name,
        source_sha256=sha256_file(candidate),
        source_size_bytes=candidate.stat().st_size,
        metadata={
            "width_px": width,
            "height_px": height,
            "megapixels": round(width * height / 1_000_000, 3),
            "exif_orientation": orientation,
            "luminance_mean": round(luminance_mean, 3),
            "luminance_std": round(luminance_std, 3),
            "dark_fraction": round(dark_fraction, 4),
            "bright_fraction": round(bright_fraction, 4),
            "edge_variance": round(edge_variance, 3),
            "blur_quality": round(blur_quality, 4),
            "external_semantic_analysis": "not_run",
        },
        observations=observations,
        warnings=warnings,
        confidence=round(confidence, 4),
        review_required=True,
    )


def _read_sidecar_transcript(path: Path) -> tuple[str, str]:
    candidates = [
        path.with_suffix(".vtt"),
        path.with_suffix(".srt"),
        path.with_suffix(".txt"),
    ]
    for sidecar in candidates:
        if not sidecar.exists() or sidecar.stat().st_size > 5 * 1024 * 1024:
            continue
        raw = sidecar.read_text(encoding="utf-8", errors="replace")
        lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "WEBVTT" or re.fullmatch(r"\d+", stripped):
                continue
            if "-->" in stripped:
                continue
            stripped = re.sub(r"<[^>]+>", "", stripped)
            lines.append(stripped)
        return " ".join(lines).strip(), sidecar.name
    return "", ""


def _audio_metadata(path: Path) -> tuple[dict[str, Any], list[AnalysisWarning]]:
    metadata: dict[str, Any] = {"container": path.suffix.lower().lstrip(".")}
    warnings: list[AnalysisWarning] = []
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as stream:
                frames = stream.getnframes()
                rate = stream.getframerate()
                metadata.update(
                    {
                        "channels": stream.getnchannels(),
                        "sample_rate_hz": rate,
                        "sample_width_bytes": stream.getsampwidth(),
                        "frame_count": frames,
                        "duration_seconds": round(frames / rate, 4) if rate else 0.0,
                    }
                )
        except (wave.Error, EOFError) as exc:
            raise SpatialIOError(f"WAV cannot be decoded safely: {exc}") from exc
        return metadata, warnings
    try:
        from mutagen import File as MutagenFile  # type: ignore[import-not-found]

        audio = MutagenFile(path)
        info = getattr(audio, "info", None)
        if info is not None:
            metadata["duration_seconds"] = round(float(getattr(info, "length", 0.0)), 4)
            sample_rate = getattr(info, "sample_rate", None)
            channels = getattr(info, "channels", None)
            if sample_rate:
                metadata["sample_rate_hz"] = int(sample_rate)
            if channels:
                metadata["channels"] = int(channels)
        else:
            warnings.append(
                _warning(
                    "AUDIO_METADATA_LIMITED",
                    "Audio duration could not be decoded locally.",
                )
            )
    except ImportError:
        warnings.append(
            _warning(
                "AUDIO_METADATA_LIMITED",
                "Install the optional 'mutagen' dependency to inspect non-WAV duration and channels.",
            )
        )
    except Exception as exc:
        warnings.append(
            _warning("AUDIO_METADATA_ERROR", f"Local metadata decoder failed: {exc}")
        )
    return metadata, warnings


def _audio_analysis(path: Path) -> MediaAnalysisResult:
    candidate = validate_input_file(
        path, allowed_suffixes=AUDIO_SUFFIXES, max_bytes=200 * 1024 * 1024
    )
    metadata, warnings = _audio_metadata(candidate)
    transcript, transcript_source = _read_sidecar_transcript(candidate)
    if transcript:
        metadata["transcript_source"] = transcript_source
        confidence = 0.78
    else:
        confidence = 0.45 if metadata.get("duration_seconds") is not None else 0.3
        warnings.append(
            _warning(
                "TRANSCRIPT_UNAVAILABLE",
                "No verified transcript sidecar or enabled transcription provider is available.",
                "Attach a reviewed VTT/SRT transcript or explicitly enable a transcription adapter.",
            )
        )
    return MediaAnalysisResult(
        kind="audio",
        filename=candidate.name,
        source_sha256=sha256_file(candidate),
        source_size_bytes=candidate.stat().st_size,
        metadata=metadata,
        transcript=transcript,
        warnings=warnings,
        confidence=confidence,
        review_required=True,
    )


def _pdf_text(
    path: Path, *, max_pages: int = 250, max_chars: int = 2_000_000
) -> tuple[str, dict[str, Any]]:
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - dependency declared for production
        raise SpatialIOError("PyMuPDF is required for PDF text extraction") from exc
    with fitz.open(path) as pdf:
        if pdf.needs_pass:
            raise SpatialIOError(
                "encrypted PDF requires explicit decryption before analysis"
            )
        if len(pdf) > max_pages:
            raise InputLimitError(
                f"PDF has {len(pdf)} pages; configured limit is {max_pages}"
            )
        parts: list[str] = []
        truncated = False
        for page_index, page in enumerate(pdf):
            text = page.get_text("text", sort=True)
            remaining = max_chars - sum(len(part) for part in parts)
            if remaining <= 0:
                truncated = True
                break
            parts.append(text[:remaining])
            if len(text) > remaining:
                truncated = True
                break
        metadata = {
            "page_count": len(pdf),
            "encrypted": bool(pdf.needs_pass),
            "text_truncated": truncated,
            "pdf_metadata": {
                key: value for key, value in (pdf.metadata or {}).items() if value
            },
        }
    return "\n".join(parts), metadata


def _document_analysis(path: Path) -> MediaAnalysisResult:
    candidate = validate_input_file(
        path, allowed_suffixes=DOCUMENT_SUFFIXES, max_bytes=256 * 1024 * 1024
    )
    warnings: list[AnalysisWarning] = []
    if candidate.suffix.lower() == ".pdf":
        text, metadata = _pdf_text(candidate)
    else:
        raw = candidate.read_bytes()
        text = raw[:2_000_000].decode("utf-8", errors="replace")
        metadata = {"text_truncated": len(raw) > 2_000_000, "page_count": None}
    normalized_text = re.sub(r"\r\n?", "\n", text).strip()
    sheet_numbers = sorted(
        set(
            re.findall(
                r"(?<![A-Z0-9])(?:FP|FA|ID|EL|ME|PL|[AMEPSCLG])-?\d{1,4}"
                r"(?:\.\d{1,3})?(?![A-Z0-9])",
                normalized_text,
                re.I,
            )
        )
    )[:500]
    revisions = sorted(
        set(
            match.group(1).strip()
            for match in re.finditer(
                r"\b(?:REVISION|REV)\b\s*[:#-]?\s*([A-Z0-9][A-Z0-9._-]{0,39})",
                normalized_text,
                re.I,
            )
        )
    )[:100]
    issue_statuses = sorted(
        set(
            match.group(1).strip()
            for match in re.finditer(
                r"\bISSUED\s+FOR\s+([A-Z][A-Z ]{1,40}?)(?=\s*(?:[|;\n]|$))",
                normalized_text,
                re.I,
            )
        )
    )[:100]
    metadata.update(
        {
            "character_count": len(normalized_text),
            "line_count": normalized_text.count("\n") + bool(normalized_text),
            "sheet_number_candidates": sheet_numbers,
            "revision_candidates": revisions,
            "issue_status_candidates": issue_statuses,
            "external_requirement_analysis": "not_run",
        }
    )
    if not normalized_text:
        warnings.append(
            _warning(
                "NO_EXTRACTABLE_TEXT",
                "The document has no embedded text.",
                "Run an OCR adapter and review the resulting text against the source pages.",
            )
        )
    if metadata.get("text_truncated"):
        warnings.append(
            _warning(
                "TEXT_TRUNCATED",
                "Text extraction reached the configured character limit.",
                "Process the document page-by-page for complete indexing.",
            )
        )
    observations = []
    if sheet_numbers:
        observations.append(
            AnalysisObservation(
                statement=f"Found {len(sheet_numbers)} unique drawing-sheet identifier candidates.",
                category="document_structure",
                confidence=0.82,
                evidence_type="extracted",
                source_locator={"sheet_number_candidates": sheet_numbers},
            )
        )
    return MediaAnalysisResult(
        kind="document",
        filename=candidate.name,
        source_sha256=sha256_file(candidate),
        source_size_bytes=candidate.stat().st_size,
        metadata=metadata,
        observations=observations,
        extracted_text=normalized_text,
        warnings=warnings,
        confidence=0.82 if normalized_text else 0.2,
        review_required=True,
    )


class DeterministicAnalysisAdapter:
    name = "deterministic_local"

    def analyze(
        self, path: Path | str, kind: AssetKind | None = None
    ) -> MediaAnalysisResult:
        candidate = Path(path)
        selected_kind = kind or detect_asset_kind(candidate)
        if selected_kind == "image":
            return _image_analysis(candidate)
        if selected_kind == "audio":
            return _audio_analysis(candidate)
        return _document_analysis(candidate)


class OpenAIAnalysisAdapter:
    """Optional model adapter; it never reads a hard-coded credential.

    External upload is disabled unless ``BUILI_EXTERNAL_AI_ENABLED=true`` and an
    explicit model is configured. This avoids silently sending construction records to
    a third party merely because a process happens to have an API key.
    """

    name = "openai"

    def __init__(self) -> None:
        enabled = os.environ.get("BUILI_EXTERNAL_AI_ENABLED", "").lower() in {
            "1",
            "true",
            "yes",
        }
        if not enabled:
            raise RuntimeError(
                "external AI is disabled; set BUILI_EXTERNAL_AI_ENABLED=true"
            )
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.vision_model = os.environ.get("BUILI_OPENAI_VISION_MODEL", "").strip()
        self.text_model = os.environ.get("BUILI_OPENAI_TEXT_MODEL", "").strip()
        self.transcription_model = os.environ.get(
            "BUILI_OPENAI_TRANSCRIPTION_MODEL", ""
        ).strip()
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "install the optional 'openai' package to enable this adapter"
            ) from exc
        self.client = OpenAI()

    @staticmethod
    def _json_output(response: Any) -> dict[str, Any]:
        raw = str(getattr(response, "output_text", "") or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("model response must be a JSON object")
        return parsed

    def _responses_json(
        self, *, model: str, content: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not model:
            raise RuntimeError(
                "an explicit BUILI_OPENAI_*_MODEL environment variable is required"
            )
        response = self.client.responses.create(  # type: ignore[arg-type]
            model=model,
            input=[{"role": "user", "content": content}],
        )
        return self._json_output(response)

    def analyze(
        self,
        path: Path,
        kind: AssetKind,
        deterministic: MediaAnalysisResult,
    ) -> dict[str, Any]:
        if kind == "audio":
            if not self.transcription_model:
                raise RuntimeError("BUILI_OPENAI_TRANSCRIPTION_MODEL is not configured")
            with path.open("rb") as handle:
                transcript = self.client.audio.transcriptions.create(
                    model=self.transcription_model,
                    file=handle,
                )
            return {
                "model": self.transcription_model,
                "transcript": str(getattr(transcript, "text", "") or ""),
                "observations": [],
            }
        prompt = (
            "Return JSON only with keys observations and warnings. Each observation must contain "
            "statement, category, confidence (0..1), evidence_type='model_inference', and "
            "source_locator. Separate directly visible/extracted facts from uncertainty. Never infer "
            "code compliance, dimensions, approval status, responsibility, or a defect unless the "
            "provided source explicitly proves it."
        )
        if kind == "image":
            if path.stat().st_size > 20 * 1024 * 1024:
                raise InputLimitError("external image adapter limit is 20 MB")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            suffix = path.suffix.lower().lstrip(".") or "jpeg"
            return self._responses_json(
                model=self.vision_model,
                content=[
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/{suffix};base64,{encoded}",
                    },
                ],
            ) | {"model": self.vision_model}
        excerpt = deterministic.extracted_text[:120_000]
        return self._responses_json(
            model=self.text_model,
            content=[
                {
                    "type": "input_text",
                    "text": f"{prompt}\n\nSOURCE TEXT (may be truncated):\n{excerpt}",
                }
            ],
        ) | {"model": self.text_model}


class MediaAnalysisService:
    def __init__(self, rich_adapter: RichAnalysisAdapter | None = None) -> None:
        self.deterministic = DeterministicAnalysisAdapter()
        self.rich_adapter = rich_adapter

    def analyze(
        self, path: Path | str, *, kind: AssetKind | None = None
    ) -> MediaAnalysisResult:
        candidate = Path(path).expanduser().resolve(strict=True)
        result = self.deterministic.analyze(candidate, kind)
        if self.rich_adapter is None:
            return result
        try:
            rich = self.rich_adapter.analyze(candidate, result.kind, result)
            observations = list(result.observations)
            for raw in rich.get("observations") or []:
                try:
                    observations.append(
                        AnalysisObservation.model_validate(
                            {**raw, "evidence_type": "model_inference"}
                        )
                    )
                except Exception:
                    continue
            warnings = list(result.warnings)
            for raw in rich.get("warnings") or []:
                try:
                    warnings.append(AnalysisWarning.model_validate(raw))
                except Exception:
                    continue
            update = {
                "provider": self.rich_adapter.name,
                "model": str(rich.get("model") or ""),
                "observations": observations,
                "warnings": warnings,
                "metadata": {
                    **result.metadata,
                    "external_semantic_analysis": "completed",
                    "external_output_requires_review": True,
                },
            }
            if rich.get("transcript"):
                update["transcript"] = str(rich["transcript"])
            return result.model_copy(update=update)
        except Exception as exc:
            return result.model_copy(
                update={
                    "warnings": [
                        *result.warnings,
                        _warning(
                            "EXTERNAL_ADAPTER_FAILED",
                            f"External adapter failed; deterministic analysis was retained: {exc}",
                            "Review provider configuration and retry explicitly.",
                        ),
                    ],
                    "metadata": {
                        **result.metadata,
                        "external_semantic_analysis": "failed_fallback_used",
                    },
                }
            )


class _UnavailableExternalAdapter:
    name = "unavailable_external_adapter"

    def __init__(self, error: Exception) -> None:
        self.error = error

    def analyze(
        self,
        path: Path,
        kind: AssetKind,
        deterministic: MediaAnalysisResult,
    ) -> dict[str, Any]:
        raise RuntimeError(str(self.error))


def build_default_analysis_service(
    *, allow_external: bool = False
) -> MediaAnalysisService:
    if not allow_external:
        return MediaAnalysisService()
    try:
        return MediaAnalysisService(OpenAIAnalysisAdapter())
    except Exception as exc:
        # Service remains usable and explicitly records that the requested adapter did
        # not run instead of silently presenting local metadata as model analysis.
        return MediaAnalysisService(_UnavailableExternalAdapter(exc))
