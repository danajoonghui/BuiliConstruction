from __future__ import annotations

import struct
import wave

from PIL import Image

from buili_spatial.analysis import DeterministicAnalysisAdapter


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
