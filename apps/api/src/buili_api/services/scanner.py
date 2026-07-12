from __future__ import annotations

import asyncio
import io
import struct
import warnings
import zipfile
from typing import Any

from PIL import Image
from pypdf import PdfReader

from ..core.config import Settings
from ..core.errors import AppError

EICAR = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
OFFICE_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word/document.xml",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xl/workbook.xml",
}
ALLOWED_EXACT = {
    "application/pdf",
    "application/json",
    *OFFICE_TYPES,
    "application/octet-stream",
}


class FileScanner:
    """Format-safety gate plus a real ClamAV INSTREAM verdict.

    Signature/container validation never claims that a file is malware-free. A
    `clean` verdict is emitted only after a configured ClamAV daemon returns OK
    (or by the deterministic scanner in the test environment).
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    async def scan(self, data: bytes, content_type: str, filename: str = "") -> dict[str, Any]:
        safety = self._validate_format(data, content_type, filename)
        backend = self.settings.malware_scanner_backend
        if backend == "disabled":
            return {
                "status": "unverified",
                "scanner": "none",
                "bytes_scanned": 0,
                "format_safety": safety,
                "message": "No antivirus backend is configured; object remains quarantined.",
            }
        if backend == "test":
            if EICAR in data:
                raise AppError(422, "MALWARE_DETECTED", "The uploaded object failed malware scanning")
            return {
                "status": "clean",
                "scanner": "deterministic-test-only",
                "bytes_scanned": len(data),
                "format_safety": safety,
            }
        verdict = await self._scan_clamav(data)
        return {**verdict, "format_safety": safety}

    def _validate_format(self, data: bytes, content_type: str, filename: str) -> dict[str, Any]:
        allowed = content_type in ALLOWED_EXACT or content_type.startswith(("image/", "audio/", "video/", "text/"))
        if not allowed:
            raise AppError(415, "UNSUPPORTED_UPLOAD_TYPE", "This file type is not allowed")
        output: dict[str, Any] = {"content_type": content_type, "filename": filename, "bytes": len(data)}
        if content_type == "application/pdf":
            if not data.startswith(b"%PDF"):
                raise AppError(422, "FILE_SIGNATURE_MISMATCH", "PDF signature does not match the declared type")
            try:
                reader = PdfReader(io.BytesIO(data), strict=True)
                if reader.is_encrypted:
                    raise AppError(422, "ENCRYPTED_DOCUMENT_UNSUPPORTED", "Encrypted PDF files cannot be processed safely")
                page_count = len(reader.pages)
            except AppError:
                raise
            except Exception as exc:
                raise AppError(422, "INVALID_PDF", "PDF structure is invalid or unsupported") from exc
            if page_count > self.settings.max_pdf_pages:
                raise AppError(422, "PDF_PAGE_LIMIT_EXCEEDED", "PDF exceeds the configured page limit")
            output["pdf_pages"] = page_count
        elif content_type.startswith("image/"):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(data)) as image:
                        width, height = image.size
                        if width * height > self.settings.max_image_pixels:
                            raise AppError(422, "IMAGE_PIXEL_LIMIT_EXCEEDED", "Image exceeds the configured pixel limit")
                        image.verify()
            except AppError:
                raise
            except Exception as exc:
                raise AppError(422, "INVALID_IMAGE", "Image is corrupt, deceptive, or exceeds safe limits") from exc
            output["image_size"] = [width, height]
        elif content_type in OFFICE_TYPES:
            output.update(self._validate_zip(data, required_member=OFFICE_TYPES[content_type]))
        elif content_type == "application/octet-stream":
            # Neutral 3D/IFC payloads are accepted; arbitrary executables are not.
            if not (data.startswith(b"glTF") or data.lstrip().startswith(b"ISO-10303-21") or data.lstrip().startswith((b"{", b"["))):
                raise AppError(415, "OCTET_STREAM_SIGNATURE_UNSUPPORTED", "Unknown binary payloads are not accepted")
        return output

    def _validate_zip(self, data: bytes, *, required_member: str) -> dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > self.settings.max_archive_entries:
                    raise AppError(422, "ARCHIVE_ENTRY_LIMIT_EXCEEDED", "Archive contains too many entries")
                names = {entry.filename for entry in entries}
                if required_member not in names or "[Content_Types].xml" not in names:
                    raise AppError(422, "OFFICE_CONTAINER_INVALID", "Office container is missing required members")
                uncompressed = 0
                for entry in entries:
                    if entry.flag_bits & 0x1:
                        raise AppError(422, "ENCRYPTED_ARCHIVE_UNSUPPORTED", "Encrypted archive entries are not supported")
                    normalized = entry.filename.replace("\\", "/")
                    if normalized.startswith("/") or "../" in f"/{normalized}":
                        raise AppError(422, "ARCHIVE_PATH_UNSAFE", "Archive contains an unsafe member path")
                    uncompressed += entry.file_size
                    if uncompressed > self.settings.max_archive_uncompressed_bytes:
                        raise AppError(422, "ARCHIVE_EXPANSION_LIMIT_EXCEEDED", "Archive expands beyond the configured limit")
                    if entry.file_size and entry.file_size / max(1, entry.compress_size) > self.settings.max_archive_compression_ratio:
                        raise AppError(422, "ARCHIVE_COMPRESSION_RATIO_EXCEEDED", "Archive compression ratio is unsafe")
        except AppError:
            raise
        except (zipfile.BadZipFile, OSError) as exc:
            raise AppError(422, "FILE_SIGNATURE_MISMATCH", "Office document container is invalid") from exc
        return {"archive_entries": len(entries), "archive_uncompressed_bytes": uncompressed}

    async def _scan_clamav(self, data: bytes) -> dict[str, Any]:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.settings.clamav_host, self.settings.clamav_port),
                timeout=self.settings.clamav_timeout_seconds,
            )
            try:
                writer.write(b"zINSTREAM\0")
                for offset in range(0, len(data), 1024 * 1024):
                    chunk = data[offset : offset + 1024 * 1024]
                    writer.write(struct.pack("!I", len(chunk)))
                    writer.write(chunk)
                    await writer.drain()
                writer.write(struct.pack("!I", 0))
                await writer.drain()
                response = await asyncio.wait_for(
                    reader.readuntil(b"\0"), timeout=self.settings.clamav_timeout_seconds
                )
            finally:
                writer.close()
                await writer.wait_closed()
        except (TimeoutError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
            raise AppError(503, "MALWARE_SCANNER_UNAVAILABLE", "Antivirus service did not return a valid verdict") from exc
        verdict = response.rstrip(b"\0").decode("utf-8", errors="replace")
        if verdict.endswith(" OK"):
            return {"status": "clean", "scanner": "clamav-instream", "bytes_scanned": len(data), "verdict": "OK"}
        if " FOUND" in verdict:
            signature = verdict.rsplit(":", 1)[-1].replace("FOUND", "").strip()[:200]
            raise AppError(422, "MALWARE_DETECTED", "The uploaded object failed malware scanning", {"signature": signature})
        raise AppError(503, "MALWARE_SCANNER_ERROR", "Antivirus service returned an indeterminate verdict")
