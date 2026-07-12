from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.postgres


def _required_url(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is required for PostgreSQL RLS integration tests")
    return value


async def test_api_cannot_spoof_worker_and_indirect_tables_are_isolated():
    api_url = _required_url("BUILI_TEST_POSTGRES_API_URL")
    worker_url = _required_url("BUILI_TEST_POSTGRES_WORKER_URL")
    suffix = uuid.uuid4().hex[:12]
    ids = {
        key: f"{prefix}_{suffix}{index}"
        for index, (key, prefix) in enumerate(
            [
                ("user_a", "usr"), ("user_b", "usr"), ("org_a", "org"), ("org_b", "org"),
                ("project_a", "prj"), ("project_b", "prj"), ("document_a", "doc"),
                ("document_b", "doc"), ("revision_a", "rev"), ("revision_b", "rev"),
                ("issue_a", "iss"), ("issue_b", "iss"), ("evidence_a", "evd"),
                ("evidence_b", "evd"), ("source_a", "src"), ("source_b", "src"),
                ("audit_a", "aud"), ("audit_b", "aud"),
            ]
        )
    }
    api = create_async_engine(api_url)
    worker = create_async_engine(worker_url)
    try:
        async with worker.begin() as connection:
            assert (await connection.scalar(text("SELECT current_user"))) == "buili_worker"
            for user in (ids["user_a"], ids["user_b"]):
                await connection.execute(
                    text("INSERT INTO users (id,email,display_name,is_active,email_verified,auth_version,created_at,updated_at) "
                         "VALUES (:id,:email,:id,true,true,0,now(),now())"),
                    {"id": user, "email": f"{user}@rls.test"},
                )
            for label in ("a", "b"):
                await connection.execute(
                    text("INSERT INTO organizations (id,name,slug,created_at,updated_at) VALUES (:id,:name,:slug,now(),now())"),
                    {"id": ids[f"org_{label}"], "name": f"RLS {label}", "slug": f"rls-{suffix}-{label}"},
                )
                await connection.execute(
                    text("INSERT INTO organization_members (id,organization_id,user_id,role,created_at) "
                         "VALUES (:id,:org,:usr,'owner',now())"),
                    {"id": f"mem_{suffix}{label}", "org": ids[f"org_{label}"], "usr": ids[f"user_{label}"]},
                )
                await connection.execute(
                    text("INSERT INTO projects (id,organization_id,name,code,status,project_type,address,timezone,units,metadata_json,created_at,updated_at) "
                         "VALUES (:id,:org,:name,:code,'active','renovation','','UTC','metric','{}',now(),now())"),
                    {"id": ids[f"project_{label}"], "org": ids[f"org_{label}"], "name": f"P {label}", "code": f"RLS-{suffix}-{label}"},
                )
                await connection.execute(
                    text("INSERT INTO project_members (id,project_id,user_id,role,created_at) VALUES (:id,:project,:usr,'manager',now())"),
                    {"id": f"pmem_{suffix}{label}", "project": ids[f"project_{label}"], "usr": ids[f"user_{label}"]},
                )
                await connection.execute(
                    text("INSERT INTO documents (id,organization_id,project_id,title,kind,discipline,created_by,created_at,updated_at) "
                         "VALUES (:id,:org,:project,'RLS drawing','drawing','general',:usr,now(),now())"),
                    {"id": ids[f"document_{label}"], "org": ids[f"org_{label}"], "project": ids[f"project_{label}"], "usr": ids[f"user_{label}"]},
                )
                await connection.execute(
                    text("INSERT INTO document_revisions (id,document_id,revision,status,storage_key,content_type,size,sha256,extracted_text,metadata_json,created_at,updated_at) "
                         "VALUES (:id,:document,'1','approved',:key,'text/plain',1,:sha,'RLS','{}',now(),now())"),
                    {"id": ids[f"revision_{label}"], "document": ids[f"document_{label}"], "key": f"rls/{suffix}/{label}", "sha": label * 64},
                )
                await connection.execute(
                    text("INSERT INTO evidence (id,organization_id,project_id,kind,title,description,location_json,metadata_json,transcript,analysis_json,created_by,created_at,updated_at) "
                         "VALUES (:id,:org,:project,'photo','RLS','','{}','{}','','{}',:usr,now(),now())"),
                    {"id": ids[f"evidence_{label}"], "org": ids[f"org_{label}"], "project": ids[f"project_{label}"], "usr": ids[f"user_{label}"]},
                )
                await connection.execute(
                    text("INSERT INTO issues (id,organization_id,project_id,number,title,description,issue_type,status,priority,observed_condition,expected_condition,difference,classification,recommended_action,evidence_sufficiency,missing_evidence,verification_json,location_json,created_by,created_at,updated_at) "
                         "VALUES (:id,:org,:project,:number,'RLS','','design_question','draft','normal','','','','insufficient_evidence','additional_evidence_required','insufficient','[]','{}','{}',:usr,now(),now())"),
                    {"id": ids[f"issue_{label}"], "org": ids[f"org_{label}"], "project": ids[f"project_{label}"], "number": f"RLS-{label}", "usr": ids[f"user_{label}"]},
                )
                await connection.execute(
                    text("INSERT INTO issue_evidence (issue_id,evidence_id,relationship_type,created_at) VALUES (:issue,:evidence,'supports',now())"),
                    {"issue": ids[f"issue_{label}"], "evidence": ids[f"evidence_{label}"]},
                )
                await connection.execute(
                    text("INSERT INTO issue_sources (id,issue_id,revision_id,bbox_json,quote,relationship_type) VALUES (:id,:issue,:revision,'[]','RLS','requirement')"),
                    {"id": ids[f"source_{label}"], "issue": ids[f"issue_{label}"], "revision": ids[f"revision_{label}"]},
                )
                await connection.execute(
                    text("INSERT INTO audit_logs (id,organization_id,project_id,action,resource_type,details_json,created_at) VALUES (:id,:org,:project,'RLS_TEST','project','{}',now())"),
                    {"id": ids[f"audit_{label}"], "org": ids[f"org_{label}"], "project": ids[f"project_{label}"]},
                )

        async with api.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_user_id', :user_id, true)"),
                {"user_id": ids["user_a"]},
            )
            for table in (
                "projects", "document_revisions", "project_members", "issue_sources",
                "issue_evidence", "audit_logs",
            ):
                assert await connection.scalar(text(f"SELECT count(*) FROM {table}")) == 1  # noqa: S608
            await connection.execute(text("SELECT set_config('app.is_worker', 'true', true)"))
            assert await connection.scalar(text("SELECT count(*) FROM projects")) == 1

        async with worker.connect() as connection:
            assert await connection.scalar(text("SELECT count(*) FROM projects WHERE id LIKE :prefix"), {"prefix": f"prj_{suffix}%"}) == 2
    finally:
        async with worker.begin() as connection:
            for table, keys in (
                ("audit_logs", ["audit_a", "audit_b"]),
                ("issue_sources", ["source_a", "source_b"]),
                ("issue_evidence", []),
                ("issues", ["issue_a", "issue_b"]),
                ("evidence", ["evidence_a", "evidence_b"]),
                ("document_revisions", ["revision_a", "revision_b"]),
                ("documents", ["document_a", "document_b"]),
                ("project_members", []),
                ("projects", ["project_a", "project_b"]),
                ("organization_members", []),
                ("organizations", ["org_a", "org_b"]),
                ("users", ["user_a", "user_b"]),
            ):
                if keys:
                    await connection.execute(
                        text(f"DELETE FROM {table} WHERE id IN (:a,:b)"),  # noqa: S608
                        {"a": ids[keys[0]], "b": ids[keys[1]]},
                    )
                elif table == "issue_evidence":
                    await connection.execute(
                        text("DELETE FROM issue_evidence WHERE issue_id IN (:a,:b)"),
                        {"a": ids["issue_a"], "b": ids["issue_b"]},
                    )
                elif table == "project_members":
                    await connection.execute(text("DELETE FROM project_members WHERE id LIKE :prefix"), {"prefix": f"pmem_{suffix}%"})
                else:
                    await connection.execute(text("DELETE FROM organization_members WHERE id LIKE :prefix"), {"prefix": f"mem_{suffix}%"})
        await api.dispose()
        await worker.dispose()
