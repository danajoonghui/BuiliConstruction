# BUILI

BUILI is a construction-verification workspace that connects field evidence to the
current drawing, model, RFI, submittal, and requirement, then routes the result to a
human-reviewed punch item, RFI, change event, or model-update request.

This repository contains three deployable parts:

- `apps/web` — Next.js marketing site, authenticated workspace, and mobile capture UI.
- `apps/api` — FastAPI multi-tenant API, background jobs, storage, search, reports, and auth.
- `buili_spatial` — deterministic 2D-plan parsing and lightweight spatial-index pipeline.

The sample assets in `buili_demo_evidence` are one coherent, synthetic workspace for
Jordan Cho at Northstar Builders. They are safe to use for product demos and automated
tests; they must not be presented as a real customer project.

## Local development

### API

```powershell
cd apps/api
py -3.13 -m pip install -e ".[dev]"
Copy-Item .env.example .env
$env:BUILI_DEMO_MODE = "true"
$env:BUILI_DEMO_EVIDENCE_PATH = "../../buili_demo_evidence"
alembic upgrade head
uvicorn buili_api.main:app --reload
```

### Web

```powershell
cd apps/web
npm ci
Copy-Item .env.example .env.local
$env:NEXT_PUBLIC_DEMO_MODE = "true"
npm run dev
```

Open `http://localhost:3000`. The API OpenAPI document is at
`http://localhost:8000/docs`.

For a containerized integration environment, run:

```powershell
docker compose -f infra/compose.yml up --build
```

## Verification

```powershell
py -3.13 -m pytest buili_spatial/tests -q
py -3.13 -m pytest apps/api/tests -q
cd apps/web
npm run typecheck
npm test
npm run build
```

## Production

The public web application is deployed on Cloudflare Workers at
[builiconstruction.com](https://builiconstruction.com). The API infrastructure is
production-ready in code but must be provisioned separately before live authentication,
uploads, and customer workflows are enabled.

No live credential is committed. Set secrets through a cloud secret manager and keep
external AI disabled until an organization/project explicitly opts in. Low-confidence
spatial or AI output is always review-required; only an approved version may be exported
as an official construction record.

See `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `SECURITY.md`, and `infra/README.md`
before provisioning. The intended public layout is:

```text
builiconstruction.com       marketing
app.builiconstruction.com   product
api.builiconstruction.com   API
```

The Cloudflare Worker deploys the public web application. The API origin, database,
queue, object store, OAuth application, email provider, ClamAV service, backups, and
monitoring still need environment-specific provisioning and release approval.
