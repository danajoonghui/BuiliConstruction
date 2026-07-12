from __future__ import annotations

import math
import re
from collections import Counter

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SearchChunk
from ..schemas import SearchHit
from .ai import AIProvider

TOKEN_RE = re.compile(r"[a-zA-Z0-9_.-]+")


def chunk_text(text: str, size: int = 1200, overlap: int = 180) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        if end < len(normalized):
            split = normalized.rfind(" ", start, end)
            if split > start + size // 2:
                end = split
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value)]


def lexical_score(query: str, text: str) -> float:
    query_counts = Counter(_tokens(query))
    text_counts = Counter(_tokens(text))
    if not query_counts or not text_counts:
        return 0.0
    overlap = sum(min(count, text_counts[token]) for token, count in query_counts.items())
    phrase = 1.0 if query.lower() in text.lower() else 0.0
    return min(1.0, overlap / sum(query_counts.values()) * 0.85 + phrase * 0.15)


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / denominator if denominator else 0.0


class SearchService:
    def __init__(self, ai: AIProvider):
        self.ai = ai

    async def replace_source(
        self,
        session: AsyncSession,
        *,
        organization_id: str,
        project_id: str,
        source_type: str,
        source_id: str,
        text: str,
        metadata: dict,
        external_ai_allowed: bool = False,
    ) -> int:
        await session.execute(
            delete(SearchChunk).where(
                SearchChunk.organization_id == organization_id,
                SearchChunk.project_id == project_id,
                SearchChunk.source_type == source_type,
                SearchChunk.source_id == source_id,
            )
        )
        values = chunk_text(text)
        embeddings = await self.ai.embeddings(values, external_allowed=external_ai_allowed) if values else None
        for index, value in enumerate(values):
            session.add(
                SearchChunk(
                    organization_id=organization_id,
                    project_id=project_id,
                    source_type=source_type,
                    source_id=source_id,
                    content=value,
                    metadata_json={**metadata, "chunk_index": index},
                    embedding=embeddings[index] if embeddings else None,
                )
            )
        await session.flush()
        return len(values)

    async def search(
        self,
        session: AsyncSession,
        *,
        project_id: str,
        query: str,
        limit: int,
        source_types: list[str] | None = None,
        organization_id: str | None = None,
        external_ai_allowed: bool = False,
    ) -> tuple[list[SearchHit], str]:
        statement = select(SearchChunk).where(SearchChunk.project_id == project_id)
        if organization_id:
            statement = statement.where(SearchChunk.organization_id == organization_id)
        if source_types:
            statement = statement.where(SearchChunk.source_type.in_(source_types))
        statement = statement.where(
            or_(
                SearchChunk.source_type != "document_revision",
                SearchChunk.metadata_json["revision_status"].as_string().in_(["current", "approved"]),
                SearchChunk.metadata_json["revision_status"].as_string().is_(None),
            )
        )
        query_embeddings = await self.ai.embeddings([query], external_allowed=external_ai_allowed) if self.ai.enabled else None
        query_vector = query_embeddings[0] if query_embeddings else None
        if session.get_bind().dialect.name == "postgresql" and query_vector:
            distance = SearchChunk.embedding.cosine_distance(query_vector)
            semantic = list(
                (
                    await session.scalars(
                        statement.where(SearchChunk.embedding.is_not(None))
                        .order_by(distance)
                        .limit(max(limit * 10, 100))
                    )
                ).all()
            )
            terms = _tokens(query)[:8]
            lexical_statement = statement
            if terms:
                lexical_statement = lexical_statement.where(
                    or_(*(SearchChunk.content.ilike(f"%{term}%") for term in terms))
                )
            lexical = list((await session.scalars(lexical_statement.limit(250))).all())
            chunks = list({item.id: item for item in [*semantic, *lexical]}.values())
        else:
            chunks = list((await session.scalars(statement.limit(5000))).all())
        scored: list[tuple[float, SearchChunk]] = []
        for chunk in chunks:
            lexical = lexical_score(query, chunk.content)
            semantic = cosine(query_vector, list(chunk.embedding)) if query_vector and chunk.embedding else 0.0
            score = lexical if query_vector is None else semantic * 0.7 + lexical * 0.3
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits = [
            SearchHit(
                chunk_id=chunk.id,
                source_type=chunk.source_type,
                source_id=chunk.source_id,
                content=chunk.content,
                score=round(score, 4),
                page=chunk.page,
                metadata=chunk.metadata_json,
            )
            for score, chunk in scored[:limit]
        ]
        return hits, "hybrid" if query_vector else "lexical"
