# BUILI API

Production-oriented FastAPI backend for multi-tenant construction verification. It runs with
SQLite, local object storage, and an in-process queue for local development; PostgreSQL, S3,
SQS, Google OIDC, and OpenAI are enabled through environment variables without code changes.

## Local run

```powershell
cd apps/api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
$env:PYTHONPATH = (Resolve-Path ../..).Path
alembic upgrade head
uvicorn buili_api.main:app --reload
```

For upload testing, run the Compose-provided ClamAV service and set
`BUILI_MALWARE_SCANNER_BACKEND=clamav`. A disabled scanner is fail-closed: uploads stay
quarantined and cannot become document or evidence sources.

OpenAPI is at `http://localhost:8000/docs`. Health endpoints are `/health/live` and
`/health/ready`.

## Browser authentication

Browser auth defaults to cookie transport. Signup, login, refresh, and Google/OIDC exchange set
short-lived `buili_access` and rotating `buili_refresh` HttpOnly cookies plus a readable
`buili_csrf` cookie. Production cookies are host-only to the API; the product obtains the CSRF
value from the login response or `GET /v1/auth/csrf`, then sends it as `X-CSRF-Token` for unsafe
cookie-authenticated requests. Native/CLI clients may append `?transport=body` and use the
returned bearer/refresh tokens. Refresh-token reuse revokes its entire token family and access
generation. Required email verification issues no signup credentials, and access/refresh both
re-check the verified user record. Google Identity Services obtains the ID token in the browser;
`POST /v1/auth/oidc/exchange` verifies OIDC discovery/JWKS/audience. Existing password accounts
are never auto-linked by email; authenticated users explicitly link through `/v1/auth/oidc/link`.

Password reset is non-enumerating and uses hashed, expiring, single-use tokens. Check
`GET /v1/auth/capabilities`: reset and verification delivery are honestly reported disabled
until `BUILI_EMAIL_BACKEND=log` (local only) or `ses` is configured.

## Demo persona

Set `BUILI_DEMO_MODE=true` only in local/staging. On startup an idempotent seed creates:

- Jordan Cho, Project Manager at Northstar Builders (login persona)
- Mike Alvarez, Field Foreman (evidence author)
- Cooper Residence Renovation
- the exact assets in `buili_demo_evidence`
- issue `BUI-1042`: a garage GFCI centerline at 12 in AFF against E1.1 Note 3's
  18 in minimum, routed to field correction/punch with an optional clarification RFI draft

Authenticate with `POST /v1/auth/login` using `BUILI_DEMO_EMAIL` and
`BUILI_DEMO_PASSWORD`. Demo mode is rejected when `BUILI_ENVIRONMENT=production`.

## Production requirements

- Set independent random values of at least 32 characters for `BUILI_JWT_SECRET` and
  `BUILI_ORIGIN_VERIFY_SECRET`, plus PostgreSQL `BUILI_DATABASE_URL`, a private S3 bucket,
  and SQS. Production startup rejects HTTP public/frontend URLs and non-HTTPS CORS origins.
- Use separate `buili_api`, `buili_worker`, and `buili_migrator` database URLs. Never inject
  `BUILI_WORKER_DATABASE_URL` into the API task; worker RLS bypass depends on PostgreSQL
  `current_user`, not a caller-controlled session setting.
- Configure `BUILI_OIDC_CLIENT_ID` for Google sign-in.
- Put secrets in a cloud secret manager, never in images or source control.
- Set `BUILI_ORIGIN_VERIFY_SECRET` from Secrets Manager and configure a Cloudflare request
  header transform to inject the same value as `X-Buili-Origin-Verify`. Production rejects
  every non-health request without a constant-time match; the value must never be exposed to
  browser code or logs.
- OpenAI is optional. Without `OPENAI_API_KEY`, extraction/search/report flows remain usable
  and AI endpoints return deterministic grounded fallbacks with `provider=disabled`.
- A key alone never enables external processing. `BUILI_EXTERNAL_AI_ENABLED=true` and the
  project's `metadata_json.external_ai_allowed=true` are both required before any customer text,
  image, or audio is sent. Size limits, untrusted-context instructions, timeouts, provenance,
  and safe local fallbacks are enforced.
- Run migrations as a separate release task: `alembic upgrade head`.

Uploads use safe basenames, signed checksums, expiry/replay checks, quarantine, bounded
PDF/archive/image validation, and a real ClamAV INSTREAM verdict. Signature checks or an
unavailable scanner never mark a file clean. Objects become available to document/evidence
workflows only after `scan_status` is `clean`. S3 downloads are forced to attachment; local
downloads add `nosniff` and sandbox CSP.
For S3 uploads, `POST /v1/uploads/{id}/complete` returns `meta.scan_job_id`; poll that job or
`GET /v1/uploads/{id}` and create evidence/revisions only after the upload reports
`status=complete` and `scan_status=clean`.

Spatial jobs invoke `buili_spatial.pipeline.parse_pdf_to_plan_graph`, persist the full immutable
`buili.plan-graph.v2` contract, and version both PlanGraph and SpatialScene against the exact
document revision/hash. Blocking parser errors cannot be approved. Low-confidence outputs can
only advance through `/v1/spatial-scenes/{id}/review`, which creates a new attested/locked version
instead of mutating generated geometry.

Report exports use the original `buili.project-record.v3` template family and create immutable
PDF, DOCX, and JSON manifest artifacts under one report version. Punch, RFI, change-event,
daily-report, and evidence-package outputs each enforce their own operational fields without
repeating the same narrative under multiple headings. Each artifact has a SHA-256 digest and a
tenant-scoped storage record; the report includes an exact source index.
Drafts require an issue that is ready for review. Approval creates a new version and is
blocked unless the issue itself is approved, evidence is sufficient, and its approved
source hashes still match the latest verification run.

See `infra/README.md` and `infra/compose.yml` for local and deployment scaffolding.
