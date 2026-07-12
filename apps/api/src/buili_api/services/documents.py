from __future__ import annotations

import io

from docx import Document as DocxDocument
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings
from ..core.errors import AppError
from ..models import Document, DocumentRevision, Project
from .search import SearchService
from .storage import ObjectStorage


def extract_text(data: bytes, content_type: str, settings: Settings, filename: str = "") -> str:
    lowered = filename.lower()
    if content_type == "application/pdf" or lowered.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise AppError(422, "ENCRYPTED_DOCUMENT_UNSUPPORTED", "Encrypted PDFs cannot be indexed")
        if len(reader.pages) > settings.max_pdf_pages:
            raise AppError(422, "PDF_PAGE_LIMIT_EXCEEDED", "PDF exceeds the configured page limit")
        parts: list[str] = []
        characters = 0
        for page in reader.pages:
            value = (page.extract_text() or "").strip()
            characters += len(value)
            if characters > settings.max_extracted_text_chars:
                raise AppError(422, "EXTRACTED_TEXT_LIMIT_EXCEEDED", "Document text exceeds the indexing limit")
            parts.append(value)
        return "\n\n".join(parts).strip()
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or lowered.endswith(".docx"):
        document = DocxDocument(io.BytesIO(data))
        parts = []
        characters = 0
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                characters += len(paragraph.text)
                if characters > settings.max_extracted_text_chars:
                    raise AppError(422, "EXTRACTED_TEXT_LIMIT_EXCEEDED", "Document text exceeds the indexing limit")
                parts.append(paragraph.text)
        return "\n".join(parts)
    if content_type.startswith("text/") or lowered.endswith((".txt", ".csv", ".vtt")):
        value = data.decode("utf-8", errors="replace")
        if len(value) > settings.max_extracted_text_chars:
            raise AppError(422, "EXTRACTED_TEXT_LIMIT_EXCEEDED", "Document text exceeds the indexing limit")
        return value
    return ""


class DocumentService:
    def __init__(self, settings: Settings, storage: ObjectStorage, search: SearchService):
        self.settings = settings
        self.storage = storage
        self.search = search

    async def ingest_revision(self, session: AsyncSession, revision_id: str) -> dict:
        revision = await session.get(DocumentRevision, revision_id)
        if revision is None:
            raise ValueError("document revision not found")
        document = await session.get(Document, revision.document_id)
        if document is None:
            raise ValueError("document not found")
        data = await self.storage.read_bytes(revision.storage_key)
        project = await session.get(Project, document.project_id)
        if revision.status not in {"current", "approved"}:
            await self.search.replace_source(
                session,
                organization_id=document.organization_id,
                project_id=document.project_id,
                source_type="document_revision",
                source_id=revision.id,
                text="",
                metadata={},
                external_ai_allowed=False,
            )
            return {"revision_id": revision.id, "characters": 0, "chunks": 0, "skipped": "not_current"}
        text = extract_text(data, revision.content_type, self.settings, revision.storage_key)
        revision.extracted_text = text
        revision.metadata_json = {**revision.metadata_json, "text_extracted": bool(text), "byte_size": len(data)}
        count = await self.search.replace_source(
            session,
            organization_id=document.organization_id,
            project_id=document.project_id,
            source_type="document_revision",
            source_id=revision.id,
            text=text,
            metadata={
                "document_id": document.id,
                "title": document.title,
                "kind": document.kind,
                "discipline": document.discipline,
                "revision": revision.revision,
                "revision_status": revision.status,
                "sheet_number": revision.sheet_number,
            },
            external_ai_allowed=bool((project.metadata_json if project else {}).get("external_ai_allowed", False)),
        )
        return {"revision_id": revision.id, "characters": len(text), "chunks": count}
