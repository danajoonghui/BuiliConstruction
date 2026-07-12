# BUILI production architecture

BUILI is a multi-tenant construction-verification product. The 2D-to-3D
pipeline is one source of spatial context; official project records are built
from immutable document revisions, spatial-scene versions, field evidence,
human review, and audit events.

## Runtime boundaries

```text
builiconstruction.com / app.builiconstruction.com
                 │
          Cloudflare DNS/WAF
                 │
        Next.js web application
                 │ HTTPS + secure cookie
                 ▼
      api.builiconstruction.com
           FastAPI API tier
          ┌──────┼─────────┐
          ▼      ▼         ▼
   PostgreSQL   Object     Queue
   + pgvector   storage    workers
                            │
                  ┌─────────┴─────────┐
                  ▼                   ▼
           BUILI spatial        AI provider adapter
           CPU pipeline         (OpenAI now, GPU later)
```

- `apps/web`: marketing site, authenticated product, responsive field capture.
- `apps/api`: identity, tenancy, workflow, search/RAG, jobs, reports, audit.
- `buili_spatial`: deterministic plan/media contracts and local CPU processing.
- `infra`: deployable infrastructure definitions and service configuration.

## Source-of-truth rules

1. Original uploads are immutable and addressed by SHA-256.
2. Drawings, plan graphs, spatial scenes, AI runs, reports, and approvals are
   versioned. A new result supersedes; it never overwrites.
3. An AI candidate cannot become an official issue or exported report without
   an authorized human review event.
4. Every generated statement must retain project, document version, sheet,
   revision, page/region, and evidence references.
5. A spatial result with an error warning or `review_required` confidence is
   blocked from official use.
6. Project permissions are checked in the API and are suitable for database
   row-level-security enforcement in production.

## AI and RAG

BUILI uses provider adapters rather than importing a model SDK into domain
logic. The default hosted adapter uses the OpenAI Responses API with structured
output. Audio transcription uses a separate transcription adapter. Both are
disabled when credentials are absent, leaving deterministic extraction and a
review-required result.

Retrieval order:

1. tenant and project authorization filter;
2. current/approved revision filter;
3. location, discipline, sheet, and object metadata filter;
4. keyword and vector retrieval;
5. reranking;
6. citation-preserving response generation.

This prevents a semantically similar but superseded drawing from silently
becoming the contractual basis for an issue.

## Authentication

- Passwords are hashed server-side; raw passwords are never logged.
- Google sign-in is an OIDC identity flow, not a client-side trust assertion.
- Access sessions are short-lived. Refresh credentials are rotated and stored
  in secure, HTTP-only cookies in production.
- Organization and project membership are separate from identity-provider
  identity.
- Demo access is enabled only with `DEMO_MODE=true` and is never a production
  administrator account.

## Evidence and action routing

Evidence is captured first, localized to a floor/space/object, and then matched
to approved requirements. The action router distinguishes:

- approved field change / model update pending;
- unapproved deviation / field correction or punch;
- existing-condition conflict / RFI and possible change event;
- design inconsistency / RFI;
- planned incomplete work / observation;
- tolerance-level deviation / no action;
- insufficient evidence / targeted recapture request.

The seeded Cooper Residence example intentionally recommends a field
correction for the clearly documented 12-inch versus 18-inch receptacle
elevation, rather than generating an unnecessary RFI.

## Production topology

The recommended first production topology is a modular monolith plus workers:

- two stateless API tasks behind a load balancer;
- PostgreSQL Multi-AZ with PostGIS/pgvector;
- private object storage with signed, short-lived upload/download requests;
- a general job worker and an independently scalable document/spatial worker;
- a dead-letter queue and idempotent job keys;
- centralized JSON logs, traces, errors, and service metrics;
- Cloudflare-managed DNS, TLS edge, WAF, bot protection, and rate limiting.

The future GPU worker consumes the same versioned job contract. Adding it does
not change client APIs or official-review semantics.
