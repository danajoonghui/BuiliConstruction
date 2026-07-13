from __future__ import annotations

import struct
import wave
from pathlib import Path

from PIL import Image

from buili_spatial.analysis import DeterministicAnalysisAdapter


DEMO = Path(__file__).resolve().parents[2] / "buili_demo_evidence"


def test_image_analysis_is_source_hashed_and_grounded(tmp_path) -> None:
    path = tmp_path / "capture.png"
    Image.new("RGB", (1200, 800), "white").save(path)
    result = DeterministicAnalysisAdapter().analyze(path)
    assert result.kind == "image"
    assert len(result.source_sha256) == 64
    assert result.metadata["width_px"] == 1200
    assert result.review_required is True
    assert all(row.evidence_type == "measured" for row in result.observations)


def test_audio_sidecar_is_used_without_inventing_transcript(tmp_path) -> None:
    path = tmp_path / "note.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(struct.pack("<h", 0) * 8000)
    path.with_suffix(".vtt").write_text(
        "WEBVTT\n\n00:00.000 --> 00:01.000\nRoom 204 north wall.\n", "utf-8"
    )
    result = DeterministicAnalysisAdapter().analyze(path)
    assert result.kind == "audio"
    assert result.transcript == "Room 204 north wall."
    assert result.metadata["duration_seconds"] == 1.0
    assert "TRANSCRIPT_UNAVAILABLE" not in {warning.code for warning in result.warnings}


def test_document_analysis_extracts_sheet_and_revision(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("Sheet A-101\nRevision: 4\nM-202 coordination note", "utf-8")
    result = DeterministicAnalysisAdapter().analyze(path)
    assert result.kind == "document"
    assert result.metadata["sheet_number_candidates"] == ["A-101", "M-202"]
    assert result.metadata["revision_candidates"] == ["4"]


def test_demo_document_extracts_compact_sheet_revision_and_issue_status() -> None:
    result = DeterministicAnalysisAdapter().analyze(
        DEMO / "cooper-residence-E1.1-demo.pdf"
    )
    assert result.source_sha256
    assert result.metadata["sheet_number_candidates"] == ["E1.1"]
    assert result.metadata["revision_candidates"] == ["03"]
    assert result.metadata["issue_status_candidates"] == ["REVIEW"]
    assert "18 IN. AFF MINIMUM" in result.extracted_text


def test_demo_audio_uses_reviewed_sidecar_and_image_quality_is_measured() -> None:
    adapter = DeterministicAnalysisAdapter()
    audio = adapter.analyze(DEMO / "foreman-voice-note.mp3")
    assert audio.metadata["transcript_source"] == "foreman-voice-note.vtt"
    assert "minimum of eighteen inches" in audio.transcript
    assert "TRANSCRIPT_UNAVAILABLE" not in {row.code for row in audio.warnings}

    image = adapter.analyze(DEMO / "box-elevation-measurement.png")
    assert image.metadata["width_px"] == 1448
    assert image.metadata["height_px"] == 1086
    assert image.metadata["blur_quality"] > 0.8
    assert all(row.evidence_type == "measured" for row in image.observations)
