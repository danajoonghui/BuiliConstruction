from __future__ import annotations

import re
import secrets
import tempfile
import uuid
from ipaddress import ip_address
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import orjson
import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from .core.config import Settings, get_settings
from .core.errors import AppError, app_error_handler
from .core.logging import configure_logging
from .db import SessionFactory, engine
from .demo import seed_demo
from .deps import current_user, require_project
from .models import Base, Evidence, FixtureAsset, Issue, Project, utcnow
from .routes import router
from .services.ai import AIProvider
from .services.documents import DocumentService
from .services.email import EmailService
from .services.fixture_assets import TripoFixtureAssetService
from .services.issues import analyze_issue
from .services.jobs import JobManager
from .services.reports import ReportService
from .services.rate_limit import InProcessRateLimiter
from .services.scanner import FileScanner
from .services.search import SearchService
from .services.spatial import SpatialService
from .services.storage import ObjectStorage, build_storage
from buili_spatial.router import build_router as build_spatial_runtime_router

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class Services:
    storage: ObjectStorage
    ai: AIProvider
    search: SearchService
    documents: DocumentService
    reports: ReportService
    spatial: SpatialService
    email: EmailService
    scanner: FileScanner
    rate_limiter: InProcessRateLimiter
    jobs: JobManager
    fixture_assets: TripoFixtureAssetService


def _json_dumps(value) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_NON_STR_KEYS)


def _trusted_client_ip(request: Request, settings: Settings) -> str:
    candidate = ""
    if settings.environment == "production":
        # The origin-secret gate below makes this Cloudflare-injected header
        # trustworthy. Using the ALB peer address would rate-limit all users as
        # one client.
        candidate = request.headers.get("cf-connecting-ip", "").strip()
    if not candidate and request.client:
        candidate = request.client.host
    try:
        return str(ip_address(candidate))
    except ValueError:
        return "unknown"


def build_services(settings: Settings) -> Services:
    storage = build_storage(settings)
    ai = AIProvider(settings)
    search = SearchService(ai)
    documents = DocumentService(settings, storage, search)
    reports = ReportService(storage)
    spatial = SpatialService(settings, storage)
    email = EmailService(settings)
    scanner = FileScanner(settings)
    rate_limiter = InProcessRateLimiter()
    jobs = JobManager(settings)
    fixture_assets = TripoFixtureAssetService(settings, storage)
    result = Services(
        storage=storage,
        ai=ai,
        search=search,
        documents=documents,
        reports=reports,
        spatial=spatial,
        email=email,
        scanner=scanner,
        rate_limiter=rate_limiter,
        jobs=jobs,
        fixture_assets=fixture_assets,
    )

    async def document_ingest(session, job):
        return await documents.ingest_revision(session, str(job.input_json["revision_id"]))

    async def evidence_analyze(session, job):
        evidence = await session.get(Evidence, str(job.input_json["evidence_id"]))
        if evidence is None:
            raise ValueError("evidence not found")
        data = await storage.read_bytes(evidence.storage_key) if evidence.storage_key else None
        project = await session.get(Project, evidence.project_id)
        external_ai_allowed = bool(
            (project.metadata_json if project else {}).get("external_ai_allowed", False)
        )
        local_analysis = None
        if data:
            try:
                from buili_spatial.analysis import build_default_analysis_service

                suffix = Path(evidence.storage_key or evidence.title).suffix or (
                    ".mp3" if evidence.kind == "voice_note" else ".jpg"
                )
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                    temporary.write(data)
                    temporary_path = Path(temporary.name)
                try:
                    kind = (
                        "audio"
                        if evidence.kind == "voice_note"
                        else ("image" if evidence.kind in {"photo", "scan"} else "document")
                    )
                    local_analysis = (
                        build_default_analysis_service(allow_external=False)
                        .analyze(temporary_path, kind=kind)
                        .model_dump(mode="json")
                    )
                finally:
                    temporary_path.unlink(missing_ok=True)
            except Exception as exc:
                local_analysis = {
                    "provider": "deterministic_local",
                    "warnings": [{"code": "LOCAL_MEDIA_ANALYSIS_FAILED", "message": str(exc)}],
                    "review_required": True,
                }
        if evidence.kind == "voice_note" and data and not evidence.transcript:
            evidence.transcript = await ai.transcribe(
                evidence.title + ".mp3", data, external_allowed=external_ai_allowed
            )
        analysis, provider = await ai.analyze_evidence(
            title=evidence.title,
            description=evidence.description,
            transcript=evidence.transcript,
            content_type=evidence.content_type,
            data=data,
            external_allowed=external_ai_allowed,
        )
        evidence.analysis_json = {
            "local": local_analysis,
            "semantic": analysis,
            "provider": provider,
        }
        searchable = "\n".join(
            value
            for value in [
                evidence.title,
                evidence.description,
                evidence.transcript,
                analysis.get("summary", ""),
            ]
            if value
        )
        chunks = await search.replace_source(
            session,
            organization_id=evidence.organization_id,
            project_id=evidence.project_id,
            source_type="evidence",
            source_id=evidence.id,
            text=searchable,
            metadata={"kind": evidence.kind, "location": evidence.location_json},
            external_ai_allowed=external_ai_allowed,
        )
        return {
            "evidence_id": evidence.id,
            "provider": provider,
            "chunks": chunks,
            "analysis": analysis,
        }

    async def issue_analyze(session, job):
        issue = await session.get(Issue, str(job.input_json["issue_id"]))
        if issue is None:
            raise ValueError("issue not found")
        return await analyze_issue(session, issue)

    jobs.register("document.ingest", document_ingest)
    jobs.register("evidence.analyze", evidence_analyze)
    jobs.register("issue.analyze", issue_analyze)
    jobs.register("spatial.generate", spatial.generate)

    async def fixture_asset_generate(session, job):
        asset = await session.get(FixtureAsset, str(job.input_json["fixture_asset_id"]))
        if asset is None:
            raise ValueError("fixture asset not found")
        return await fixture_assets.generate(session, asset)

    jobs.register("fixture_asset.generate", fixture_asset_generate)

    async def upload_scan(session, job):
        from .models import Upload

        upload = await session.get(Upload, str(job.input_json["upload_id"]))
        if upload is None:
            raise ValueError("upload not found")
        data = await storage.read_bytes(upload.object_key)
        try:
            result = await scanner.scan(data, upload.content_type, upload.original_filename)
        except AppError as exc:
            upload.scan_status = "infected" if exc.code == "MALWARE_DETECTED" else "error"
            upload.status = "rejected" if exc.code == "MALWARE_DETECTED" else "quarantined"
            upload.scan_result_json = {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
            upload.scanned_at = utcnow()
            if exc.code == "MALWARE_DETECTED":
                return {
                    "upload_id": upload.id,
                    "status": upload.scan_status,
                    "error": upload.scan_result_json,
                }
            # Persist the honest indeterminate verdict, then let SQS retry and
            # eventually move the job to its DLQ rather than silently accepting.
            await session.commit()
            raise
        upload.scan_status = str(result["status"])
        upload.status = "complete" if upload.scan_status == "clean" else "quarantined"
        upload.scan_result_json = result
        upload.scanned_at = utcnow()
        return {"upload_id": upload.id, **result}

    jobs.register("upload.scan", upload_scan)
    return result


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    service_container = build_services(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_create_schema:
            async with engine.begin() as connection:
                if not settings.is_sqlite:
                    await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await connection.run_sync(Base.metadata.create_all)
        await service_container.jobs.start()
        if settings.demo_mode:
            async with SessionFactory() as session:
                await seed_demo(
                    session,
                    settings,
                    service_container.storage,
                    service_container.search,
                    service_container.reports,
                )
        await logger.ainfo(
            "application.started",
            environment=settings.environment,
            storage_backend=settings.storage_backend,
            job_backend=settings.job_backend,
            ai_enabled=service_container.ai.enabled,
        )
        yield
        await service_container.jobs.stop()
        await engine.dispose()

    app = FastAPI(
        title="BUILI API",
        version="0.1.0",
        description="Source-grounded construction verification and issue workflows.",
        lifespan=lifespan,
    )
    app.state.services = service_container
    app.state.json_dumps = _json_dumps
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-CSRF-Token",
        ],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = (
            supplied
            if re.fullmatch(r"[A-Za-z0-9_.:-]{8,64}", supplied)
            else f"req_{uuid.uuid4().hex}"
        )
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, method=request.method, path=request.url.path
        )
        # The production ALB accepts traffic only from Cloudflare, and Cloudflare
        # injects this per-origin secret.  IP allow-listing alone is insufficient
        # because another Cloudflare customer could otherwise proxy to the ALB.
        # Health probes are direct ALB/ECS traffic and intentionally exempt.
        if settings.environment == "production" and request.url.path not in {
            "/health/live",
            "/health/ready",
        }:
            expected_origin = (
                settings.origin_verify_secret.get_secret_value()
                if settings.origin_verify_secret
                else ""
            )
            supplied_origin = request.headers.get("x-buili-origin-verify", "")
            if not supplied_origin or not secrets.compare_digest(supplied_origin, expected_origin):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "ORIGIN_VERIFICATION_FAILED",
                            "message": "Request origin is not trusted",
                            "details": {},
                        },
                        "request_id": request_id,
                    },
                    headers={"X-Request-ID": request_id},
                )
        rate_limited_auth_paths = {
            "/v1/auth/signup",
            "/v1/auth/login",
            "/v1/auth/refresh",
            "/v1/auth/oidc/exchange",
            "/v1/auth/forgot-password",
            "/v1/auth/request-email-verification",
            "/v1/auth/reset-password",
        }
        if request.method == "POST" and request.url.path in rate_limited_auth_paths:
            client_ip = _trusted_client_ip(request, settings)
            allowed = await service_container.rate_limiter.allow(
                f"{client_ip}:{request.url.path}", settings.auth_rate_limit_per_minute
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many authentication requests",
                            "details": {},
                        },
                        "request_id": request_id,
                    },
                    headers={"Retry-After": "60", "X-Request-ID": request_id},
                )
        csrf_exempt = {
            "/v1/auth/signup",
            "/v1/auth/login",
            "/v1/auth/oidc/exchange",
            "/v1/auth/forgot-password",
            "/v1/auth/request-email-verification",
            "/v1/auth/reset-password",
            "/v1/auth/verify-email",
        }
        cookie_auth = not request.headers.get("authorization") and bool(
            request.cookies.get("buili_access") or request.cookies.get("buili_refresh")
        )
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and cookie_auth
            and request.url.path not in csrf_exempt
        ):
            cookie_csrf = request.cookies.get("buili_csrf", "")
            header_csrf = request.headers.get("x-csrf-token", "")
            if (
                not cookie_csrf
                or not header_csrf
                or not secrets.compare_digest(cookie_csrf, header_csrf)
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "CSRF_VALIDATION_FAILED",
                            "message": "CSRF token is missing or invalid",
                            "details": {},
                        },
                        "request_id": request_id,
                    },
                    headers={"X-Request-ID": request_id},
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, AppError):  # pragma: no cover - guarded by Starlette routing
            raise exc
        return await app_error_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic includes the rejected field value in `input`. That can be a
        # password, reset token, OIDC credential, or other secret and must not
        # be reflected into responses/log collectors.
        safe_errors = [
            {
                "type": item.get("type", "validation_error"),
                "loc": item.get("loc", ()),
                "msg": item.get("msg", "Invalid value"),
            }
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"errors": jsonable_encoder(safe_errors)},
                },
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}},
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        await logger.aexception("request.unhandled_error", error=str(exc))
        message = (
            str(exc)
            if settings.environment in {"development", "test"}
            else "An unexpected error occurred"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "INTERNAL_ERROR", "message": message, "details": {}},
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    app.include_router(router)
    app.include_router(
        build_spatial_runtime_router(
            auth_dependency=current_user,
            project_dependency=require_project("spatial:create"),
        )
    )
    return app


app = create_app()
