from __future__ import annotations

import asyncio
import io
import struct
import zipfile

import pytest
from pypdf import PdfWriter

from buili_api.core.config import get_settings
from buili_api.core.errors import AppError
from buili_api.services.scanner import FileScanner


async def test_disabled_scanner_never_claims_clean():
    scanner = FileScanner(get_settings().model_copy(update={"malware_scanner_backend": "disabled"}))
    result = await scanner.scan(b"plain field note", "text/plain", "note.txt")
    assert result["status"] == "unverified"
    assert result["bytes_scanned"] == 0


async def test_clamav_instream_verdict_is_required_for_clean():
    received = bytearray()

    async def clamav(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        assert await reader.readexactly(len(b"zINSTREAM\0")) == b"zINSTREAM\0"
        while True:
            size = struct.unpack("!I", await reader.readexactly(4))[0]
            if size == 0:
                break
            received.extend(await reader.readexactly(size))
        writer.write(b"stream: OK\0")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(clamav, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    settings = get_settings().model_copy(
        update={"malware_scanner_backend": "clamav", "clamav_host": "127.0.0.1", "clamav_port": port}
    )
    try:
        result = await FileScanner(settings).scan(b"verified bytes", "text/plain", "note.txt")
    finally:
        server.close()
        await server.wait_closed()
    assert bytes(received) == b"verified bytes"
    assert result["status"] == "clean"
    assert result["scanner"] == "clamav-instream"


async def test_office_archive_expansion_and_pdf_page_limits_are_blocking():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as container:
        container.writestr("[Content_Types].xml", "<Types/>")
        container.writestr("word/document.xml", "A" * 100_000)
    strict_archive = get_settings().model_copy(
        update={
            "malware_scanner_backend": "test",
            "max_archive_compression_ratio": 2,
        }
    )
    with pytest.raises(AppError) as archive_error:
        await FileScanner(strict_archive).scan(
            archive.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "bomb.docx",
        )
    assert archive_error.value.code == "ARCHIVE_COMPRESSION_RATIO_EXCEEDED"

    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    writer.write(pdf)
    strict_pdf = get_settings().model_copy(
        update={"malware_scanner_backend": "test", "max_pdf_pages": 1}
    )
    with pytest.raises(AppError) as pdf_error:
        await FileScanner(strict_pdf).scan(pdf.getvalue(), "application/pdf", "large.pdf")
    assert pdf_error.value.code == "PDF_PAGE_LIMIT_EXCEEDED"
