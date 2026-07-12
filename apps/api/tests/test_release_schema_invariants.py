from __future__ import annotations

from sqlalchemy import UniqueConstraint

from buili_api.models import DocumentRevision, PlanGraph, SearchChunk, SpatialScene


def test_active_revision_spatial_versions_and_vector_index_are_database_enforced():
    document_indexes = {index.name: index for index in DocumentRevision.__table__.indexes}
    assert document_indexes["uq_document_one_active_revision"].unique is True

    scene_constraints = {
        constraint.name
        for constraint in SpatialScene.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert "uq_spatial_scene_version" in scene_constraints
    assert any(index.name == "uq_spatial_scene_approved_source" and index.unique for index in SpatialScene.__table__.indexes)
    assert any(index.name == "uq_plan_graph_approved_source" and index.unique for index in PlanGraph.__table__.indexes)

    hnsw = next(index for index in SearchChunk.__table__.indexes if index.name == "ix_search_chunks_embedding_hnsw")
    assert hnsw.dialect_options["postgresql"]["using"] == "hnsw"
    assert hnsw.dialect_options["postgresql"]["ops"] == {"embedding": "vector_cosine_ops"}
