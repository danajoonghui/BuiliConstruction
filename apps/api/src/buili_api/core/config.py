from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "BUILI API"
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development", validation_alias=AliasChoices("BUILI_ENVIRONMENT", "ENVIRONMENT")
    )
    log_level: str = Field(default="INFO", validation_alias="BUILI_LOG_LEVEL")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./.data/buili.db",
        validation_alias=AliasChoices("BUILI_DATABASE_URL", "DATABASE_URL"),
    )
    worker_database_url: str | None = Field(default=None, validation_alias="BUILI_WORKER_DATABASE_URL")
    auto_create_schema: bool = Field(default=True, validation_alias="BUILI_AUTO_CREATE_SCHEMA")
    public_api_url: str = Field(default="http://localhost:8000", validation_alias="BUILI_PUBLIC_API_URL")
    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias="BUILI_CORS_ORIGINS",
    )

    jwt_secret: SecretStr = Field(default=SecretStr("local-dev-secret-change-me-32chars"), validation_alias="BUILI_JWT_SECRET")
    jwt_issuer: str = Field(default="https://api.builiconstruction.com", validation_alias="BUILI_JWT_ISSUER")
    jwt_audience: str = Field(default="buili-web", validation_alias="BUILI_JWT_AUDIENCE")
    access_token_minutes: int = Field(default=30, validation_alias="BUILI_ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(default=30, validation_alias="BUILI_REFRESH_TOKEN_DAYS")
    cookie_domain: str | None = Field(default=None, validation_alias="BUILI_COOKIE_DOMAIN")
    cookie_secure: bool = Field(default=False, validation_alias="BUILI_COOKIE_SECURE")
    cookie_samesite: Literal["lax", "strict", "none"] = Field(default="lax", validation_alias="BUILI_COOKIE_SAMESITE")
    origin_verify_secret: SecretStr | None = Field(default=None, validation_alias="BUILI_ORIGIN_VERIFY_SECRET")
    frontend_url: str = Field(default="http://localhost:3000", validation_alias="BUILI_FRONTEND_URL")
    email_backend: Literal["disabled", "log", "ses"] = Field(default="disabled", validation_alias="BUILI_EMAIL_BACKEND")
    require_email_verification: bool = Field(default=False, validation_alias="BUILI_REQUIRE_EMAIL_VERIFICATION")
    auth_token_minutes: int = Field(default=30, validation_alias="BUILI_AUTH_TOKEN_MINUTES")
    auth_rate_limit_per_minute: int = Field(default=12, validation_alias="BUILI_AUTH_RATE_LIMIT_PER_MINUTE")

    oidc_issuer: str = Field(default="https://accounts.google.com", validation_alias="BUILI_OIDC_ISSUER")
    oidc_client_id: str | None = Field(default=None, validation_alias="BUILI_OIDC_CLIENT_ID")

    storage_backend: Literal["local", "s3"] = Field(default="local", validation_alias="BUILI_STORAGE_BACKEND")
    storage_root: Path = Field(default=Path(".data/storage"), validation_alias="BUILI_STORAGE_ROOT")
    s3_bucket: str | None = Field(default=None, validation_alias="BUILI_S3_BUCKET")
    s3_region: str = Field(default="us-west-1", validation_alias="BUILI_S3_REGION")
    s3_endpoint_url: str | None = Field(default=None, validation_alias="BUILI_S3_ENDPOINT_URL")
    upload_url_expiry_seconds: int = 900
    # Kept below the standard ClamAV INSTREAM ceiling; larger assets require a
    # reviewed multipart/offline scanning design rather than bypassing AV.
    max_upload_bytes: int = Field(default=95 * 1024 * 1024, validation_alias="BUILI_MAX_UPLOAD_BYTES")
    malware_scanner_backend: Literal["disabled", "clamav", "test"] = Field(
        default="disabled", validation_alias="BUILI_MALWARE_SCANNER_BACKEND"
    )
    clamav_host: str = Field(default="127.0.0.1", validation_alias="BUILI_CLAMAV_HOST")
    clamav_port: int = Field(default=3310, validation_alias="BUILI_CLAMAV_PORT")
    clamav_timeout_seconds: int = Field(default=60, validation_alias="BUILI_CLAMAV_TIMEOUT_SECONDS")
    max_archive_entries: int = Field(default=10_000, validation_alias="BUILI_MAX_ARCHIVE_ENTRIES")
    max_archive_uncompressed_bytes: int = Field(
        default=512 * 1024 * 1024, validation_alias="BUILI_MAX_ARCHIVE_UNCOMPRESSED_BYTES"
    )
    max_archive_compression_ratio: int = Field(default=100, validation_alias="BUILI_MAX_ARCHIVE_COMPRESSION_RATIO")
    max_pdf_pages: int = Field(default=500, validation_alias="BUILI_MAX_PDF_PAGES")
    max_extracted_text_chars: int = Field(default=5_000_000, validation_alias="BUILI_MAX_EXTRACTED_TEXT_CHARS")
    max_image_pixels: int = Field(default=100_000_000, validation_alias="BUILI_MAX_IMAGE_PIXELS")

    job_backend: Literal["local", "sqs"] = Field(default="local", validation_alias="BUILI_JOB_BACKEND")
    sqs_queue_url: str | None = Field(default=None, validation_alias="BUILI_SQS_QUEUE_URL")
    sqs_endpoint_url: str | None = Field(default=None, validation_alias="BUILI_SQS_ENDPOINT_URL")
    worker_concurrency: int = Field(default=2, validation_alias="BUILI_WORKER_CONCURRENCY")
    job_visibility_timeout_seconds: int = Field(default=900, validation_alias="BUILI_JOB_VISIBILITY_TIMEOUT_SECONDS")
    job_heartbeat_seconds: int = Field(default=300, validation_alias="BUILI_JOB_HEARTBEAT_SECONDS")

    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "BUILI_OPENAI_API_KEY")
    )
    # Model IDs are deliberately deployment-supplied. A made-up or stale
    # library default must never silently reach a production provider call.
    openai_model: str = Field(default="", validation_alias="OPENAI_MODEL")
    openai_transcribe_model: str = Field(default="gpt-4o-transcribe", validation_alias="OPENAI_TRANSCRIBE_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", validation_alias="OPENAI_EMBEDDING_MODEL")
    external_ai_enabled: bool = Field(default=False, validation_alias="BUILI_EXTERNAL_AI_ENABLED")
    openai_timeout_seconds: float = Field(default=30.0, validation_alias="BUILI_OPENAI_TIMEOUT_SECONDS")
    ai_max_image_bytes: int = 20 * 1024 * 1024
    ai_max_audio_bytes: int = 25 * 1024 * 1024
    ai_max_context_characters: int = 120_000
    spatial_processor_url: str | None = Field(default=None, validation_alias="BUILI_SPATIAL_PROCESSOR_URL")

    demo_mode: bool = Field(default=False, validation_alias="BUILI_DEMO_MODE")
    demo_email: str = Field(default="jordan@demo.builiconstruction.com", validation_alias="BUILI_DEMO_EMAIL")
    demo_password: SecretStr = Field(default=SecretStr("ChangeMe-Demo-2026!"), validation_alias="BUILI_DEMO_PASSWORD")
    demo_evidence_path: Path = Field(default=Path("../../buili_demo_evidence"), validation_alias="BUILI_DEMO_EVIDENCE_PATH")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @model_validator(mode="after")
    def validate_secure_runtime(self) -> "Settings":
        if self.environment == "production":
            jwt_secret = self.jwt_secret.get_secret_value()
            normalized_secret = jwt_secret.lower()
            placeholder_markers = ("local-dev", "replace-with", "change-me", "changeme", "example")
            if len(jwt_secret) < 32 or any(marker in normalized_secret for marker in placeholder_markers):
                raise ValueError("BUILI_JWT_SECRET must be an independent secret of at least 32 characters")
            if self.demo_mode:
                raise ValueError("BUILI_DEMO_MODE is forbidden in production")
            if self.auto_create_schema:
                raise ValueError("Run Alembic migrations and disable AUTO_CREATE_SCHEMA in production")
            if not self.cookie_secure:
                raise ValueError("BUILI_COOKIE_SECURE must be true in production")
            if self.email_backend == "log":
                raise ValueError("Log email backend is forbidden in production")
            if self.require_email_verification and self.email_backend == "disabled":
                raise ValueError("Verified production accounts require an enabled email backend")
            origin_secret = (
                self.origin_verify_secret.get_secret_value() if self.origin_verify_secret else ""
            )
            if len(origin_secret) < 32:
                raise ValueError(
                    "BUILI_ORIGIN_VERIFY_SECRET must be an independent secret of at least 32 characters"
                )
            if not self.public_api_url.startswith("https://") or not self.frontend_url.startswith(
                "https://"
            ):
                raise ValueError("Production public API and frontend URLs must use HTTPS")
            if any(not origin.startswith("https://") for origin in self.cors_origin_list):
                raise ValueError("Production CORS origins must use HTTPS")
            if self.malware_scanner_backend != "clamav":
                raise ValueError("Production uploads require BUILI_MALWARE_SCANNER_BACKEND=clamav")
            if self.cookie_domain:
                raise ValueError("Production auth cookies must be host-only; do not set BUILI_COOKIE_DOMAIN")
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires PostgreSQL through a postgresql+asyncpg DATABASE_URL")
            if self.storage_backend != "s3":
                raise ValueError("Production requires BUILI_STORAGE_BACKEND=s3")
            if self.job_backend != "sqs":
                raise ValueError("Production requires BUILI_JOB_BACKEND=sqs")
            forbidden_origins = {"https://builiconstruction.com", "https://www.builiconstruction.com"}
            if forbidden_origins & set(self.cors_origin_list):
                raise ValueError("Marketing apex/www origins cannot receive credentialed API CORS")
        if self.malware_scanner_backend == "test" and self.environment != "test":
            raise ValueError("The deterministic test scanner is available only in test environments")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("BUILI_S3_BUCKET is required for S3 storage")
        if self.job_backend == "sqs" and not self.sqs_queue_url:
            raise ValueError("BUILI_SQS_QUEUE_URL is required for SQS jobs")
        if self.external_ai_enabled:
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when BUILI_EXTERNAL_AI_ENABLED=true")
            if not self.openai_model.strip():
                raise ValueError("OPENAI_MODEL must be explicitly pinned when external AI is enabled")
            if not self.openai_transcribe_model.strip() or not self.openai_embedding_model.strip():
                raise ValueError("OpenAI transcription and embedding model IDs must be explicitly pinned")
        if not 5 <= self.job_heartbeat_seconds < self.job_visibility_timeout_seconds:
            raise ValueError("Job heartbeat must be at least 5 seconds and lower than the visibility timeout")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
