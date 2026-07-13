# Deployment guide

This repository contains no live credentials. Production is an AWS origin
behind Cloudflare; Cloudflare remains authoritative DNS/WAF while AWS runs the
API, workers, database, queues, object storage, and observability.

## Domain layout

```text
builiconstruction.com        Marketing site
www.builiconstruction.com    Redirect to apex
app.builiconstruction.com    Authenticated product
api.builiconstruction.com    Cloudflare-proxied AWS API origin
status.builiconstruction.com Independent status page
```

Never expose database, queue, bucket, or ALB hostnames to end users.

## 1. Environment and Terraform state

Use separate AWS accounts for staging and production. Each environment needs
separate databases, buckets, queues, keys, OAuth applications, and API keys.

Create an encrypted/versioned private S3 bucket for Terraform state outside
this stack. Copy `infra/terraform/backend.hcl.example` to a protected location,
then initialize and validate with Terraform 1.10 or newer:

```powershell
terraform -chdir=infra/terraform init -backend-config=backend.hcl
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -var-file=production.tfvars
```

The backend uses S3 native lock files. Restrict state access to the deployment
role and a break-glass administrator; state can contain infrastructure metadata.

## 2. Origin TLS and Cloudflare

1. Request or import an ACM certificate in the deployment Region for
   `api.builiconstruction.com`. Add certificate-validation DNS records in
   Cloudflare as **DNS only** until ACM reports `Issued`.
2. Supply the certificate ARN to Terraform. There is no plaintext forwarding
   mode: port 80 only redirects, and port 443 always requires ACM TLS.
3. Apply Terraform, then create a proxied Cloudflare CNAME:

   ```text
   CNAME  api  <api_alb_dns_name output>  Proxied
   ```

4. Set Cloudflare SSL/TLS to **Full (strict)**. Enable managed WAF rules and
   rate limits for authentication, uploads, AI analysis, report export, and
   public-share routes.
5. Keep the apex/app deployments separate from the ALB. Redirect preview
   provider hostnames to the canonical production hostname and disable search
   indexing on previews.

The IPv4 ALB security group accepts ports 80/443 only from Cloudflare's
published IPv4 proxy networks. Cloudflare still serves IPv6 visitors at the
edge and connects to this origin over IPv4. The HTTPS listener forwards only the canonical API
Host header; all other hosts receive 404. Also create a Cloudflare origin
request Transform Rule that replaces `X-Buili-Origin-Verify` with the random
`ORIGIN_VERIFY_SECRET` value described below. Production API middleware must
compare that header in constant time and reject missing/incorrect values before
authentication; only ALB health paths may be exempt. This second factor matters
because source-IP filtering alone cannot distinguish BUILI's zone from another
Cloudflare customer. Never expose or log this header value.

Together these controls prevent users from bypassing BUILI's Cloudflare WAF by
calling the ALB DNS name or proxying it through another zone. The ranges in
`variables.tf` must be compared regularly with
`https://www.cloudflare.com/ips/` and updated before Cloudflare publishes a
removal or addition. Do not add `0.0.0.0/0` as a temporary origin rule.

After cutover, verify all four conditions:

- `https://api.builiconstruction.com/health/ready` succeeds through Cloudflare;
- direct access to the ALB from an ordinary client times out or is refused;
- an incorrect Host header never reaches the API target group;
- requests without the private origin verification header are rejected.

## 3. Runtime secrets and identity

Terraform creates one Secrets Manager record but deliberately does not create a
secret value. Populate it from protected CI or the AWS console with JSON keys:

```text
API_DATABASE_URL       postgresql+asyncpg://buili_api:... URL with ssl=require
WORKER_DATABASE_URL    postgresql+asyncpg://buili_worker:... URL with ssl=require
MIGRATION_DATABASE_URL postgresql+asyncpg://buili_migrator:... URL with ssl=require
JWT_SECRET     at least 32 cryptographically random bytes
OIDC_CLIENT_ID Google Web client ID
ORIGIN_VERIFY_SECRET at least 32 random bytes, shared only with Cloudflare
OPENAI_API_KEY only when external_ai_enabled=true
TRIPO_API_KEY only when tripo_enabled=true
```

Create the three roles with `apps/api/scripts/bootstrap_database_roles.sql`,
run migrations only as `buili_migrator`, then apply
`apps/api/scripts/grant_runtime_database_privileges.sql`. The API task receives
only `API_DATABASE_URL`; the worker receives only `WORKER_DATABASE_URL`; the
one-shot migration task receives only `MIGRATION_DATABASE_URL`. RLS bypass is
based on PostgreSQL `current_user = 'buili_worker'`, not a spoofable session
setting, and `buili_api` must never be granted membership in that role. Do not
run any runtime with the RDS master account. Never put secret values in a
`.tfvars`, backend file, shell history, ticket, chat, screenshot, or commit.
Revoke any key that has appeared in one of those locations before deployment.

The Google OAuth application must list the exact production origins described
in `docs/GOOGLE_SIGN_IN.md`. The frontend reads its public client ID from
`GET /v1/auth/capabilities`, so no frontend secret or rebuild is required. No
Google client secret is used by this ID-token exchange flow. Test account
creation, explicit identity linking, revocation, and logout before release.

Production cookies are `Secure`, `SameSite=Lax`, and host-only to
`api.builiconstruction.com`; Terraform intentionally does not set a Cookie
Domain. Credentialed CORS permits `app.builiconstruction.com` only, never the
marketing apex or `www`. Login and refresh responses return `csrf_token`; after
a reload the app recovers it through credentialed `GET /v1/auth/csrf`. The
marketing site therefore cannot read the token or use an authenticated API
session even if it is compromised.

### Mandatory one-shot migration gate

Terraform creates `aws_ecs_task_definition.migration`; it is not a long-lived
service. Before updating API or worker services, CI must run it in the private
subnets and wait for exit code zero. With Terraform outputs loaded into
protected CI variables, the equivalent AWS CLI flow is:

```powershell
$task = aws ecs run-task --cluster $ECS_CLUSTER_ARN `
  --task-definition $MIGRATION_TASK_DEFINITION_ARN --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNET_A,$PRIVATE_SUBNET_B],securityGroups=[$WORKER_SECURITY_GROUP_ID],assignPublicIp=DISABLED}" `
  --query 'tasks[0].taskArn' --output text
aws ecs wait tasks-stopped --cluster $ECS_CLUSTER_ARN --tasks $task
$exit = aws ecs describe-tasks --cluster $ECS_CLUSTER_ARN --tasks $task `
  --query 'tasks[0].containers[?name==`migration`].exitCode | [0]' --output text
if ($exit -ne '0') { throw "Database migration failed with exit code $exit" }
```

After success, run the runtime-grant SQL as the migrator, then deploy services.
Never allow an application task to invoke the migration task or read its URL.

## 4. Transactional email

Verify `builiconstruction.com` in Amazon SES, publish its DKIM/SPF/DMARC records
in Cloudflare, request SES production access, and validate delivery to external
recipients. The API role can send only through that SES identity. Production
enables email verification; signup/reset flows are not release-ready until SES
delivery and bounce/complaint handling have been exercised.

Signup does not issue access or refresh credentials until verification. Access
and refresh paths re-check the user record, so credentials minted under an older
configuration cannot bypass the gate. Treat an SES sandbox account, missing
DKIM, or an untested bounce/complaint path as a release blocker.

### Upload antivirus and parser limits

Production workers run a pinned ClamAV sidecar and use its INSTREAM protocol.
Format/signature validation alone never marks an upload clean. If ClamAV is
unavailable or returns an indeterminate verdict, the object remains quarantined;
malware is rejected. DOCX/XLSX entry count, expanded size and compression ratio,
PDF page count/text extraction, and image pixel count are bounded before parsers
consume content. Vulnerability-scan and refresh the ClamAV image/signatures in
every promotion, and exercise both EICAR rejection and scanner-outage behavior
in staging.

## 5. External AI control

External AI is disabled by default. Enabling it requires both:

- `external_ai_enabled=true` in the reviewed release configuration; and
- a new project-scoped `OPENAI_API_KEY` in Secrets Manager with budgets and
alerts.

Tripo presentation-asset generation has a separate `tripo_enabled` kill switch
and `TRIPO_API_KEY`. The worker submits only approved semantic prompts, validates
provider URLs and GLB bytes, copies accepted files to BUILI storage, and leaves
them `review_required`. Provider URLs are never sent to the browser and generated
objects cannot change PlanGraph coordinates or contractual dimensions.

## 5.1 Repeatable GitHub production deployment

After the initial AWS bootstrap, `.github/workflows/deploy-production-api.yml`
performs the normal release with GitHub OIDC instead of long-lived AWS keys. Set
the GitHub `production` environment to require manual approval and configure:

```text
Secret:   AWS_DEPLOY_ROLE_ARN
Variable: AWS_REGION                 us-west-1
Variable: TF_STATE_BUCKET            private encrypted state bucket
Variable: TF_STATE_KEY               buili/production/terraform.tfstate
Variable: ACM_CERTIFICATE_ARN        issued certificate for api.builiconstruction.com
Variable: ALARM_EMAIL                optional
Variable: EXTERNAL_AI_ENABLED        false until approved
Variable: OPENAI_MODEL               pinned only when enabled
Variable: TRIPO_ENABLED              false until project policy and key are ready
Variable: TRIPO_MODEL_VERSION        P1-20260311
```

The workflow builds an immutable image tagged with the Git commit SHA, pushes it
to ECR, registers but does not yet promote the migration task, requires the
one-shot migration exit code to be zero, applies the reviewed infrastructure
plan, then verifies readiness through Cloudflare. A failed migration therefore
cannot update the long-lived API/worker services.

The first bootstrap remains a deliberate administrator operation because the
RDS roles, initial Secrets Manager JSON value, ACM validation, Cloudflare origin
rule, and GitHub OIDC trust must exist before an unattended deployment can be
safe. Never solve that dependency by committing a database password or AWS key.

The worker receives no key while the switch is off. Keep per-organization and
per-project consent/policy checks in the application, treat uploaded content as
untrusted, preserve model/prompt/source provenance, and retain deterministic
local fallbacks for unsupported or low-confidence inputs.

## 6. Storage immutability and retention

The API and worker roles can read/write only `org/*` project objects. Neither
role has `s3:DeleteObject` or `s3:DeleteObjectVersion`, so uploaded originals
and their versions cannot be removed by an application compromise or bug.
Versioning is enabled and public access is fully blocked. Any legal deletion or
retention purge must use a separately approved break-glass workflow with audit
evidence; never grant delete to the normal ECS roles.

ALB access logs are retained for one year. API and worker CloudWatch logs are
retained for 90 days by default. Confirm these periods against customer
contracts and legal requirements before onboarding real project data.

## 7. Scaling, alarms, and backup recovery

The API keeps at least two tasks and scales on CPU. Workers scale out from the
SQS visible-message backlog and scale in only after both visible and in-flight
jobs remain at zero for ten minutes. The operations SNS topic receives alarms
for:

- non-empty DLQ and excessive oldest-job age;
- sustained worker CPU/memory pressure;
- ECS task OOM stops;
- API target 5xx responses;
- low RDS free storage and sustained RDS CPU.

Subscribe incident management to the `operations_topic_arn` output. If using
`alarm_email`, confirm the SNS email subscription after apply. Route DLQ alerts
to an owned runbook that inspects, redacts, fixes, and explicitly replays jobs;
workers intentionally cannot consume the DLQ.

RDS is private, Multi-AZ, deletion-protected, encrypted, and configured for a
35-day point-in-time recovery window plus a final snapshot. PostgreSQL/upgrade
logs and enhanced monitoring are enabled. Perform a restore into an isolated
environment at least quarterly, validate row counts and tenant isolation, then
destroy the restore. Also test S3 version recovery and a complete queue replay.

## 8. Release gates

Before production promotion, all of the following must pass:

- frontend typecheck, unit tests, production build, and mobile/desktop smoke;
- API lint/typecheck, unit/integration tests, migrations, and readiness probe;
- spatial contract/evaluation tests with representative plans;
- Terraform format, validation, reviewed plan, policy scan, secret scan, and
  dependency/container vulnerability scan;
- Cloudflare-only origin, strict TLS, cookie-domain, CORS, and Google OAuth
  validation;
- upload size/type/checksum/malware-path validation;
- tenant-isolation, permission, report approval, and audit tests;
- alarm delivery, ECS rollback, DLQ handling, backup restore, and object-version
  recovery drills;
- documented application and infrastructure rollback rehearsal.

The normal SQLite suite does not prove PostgreSQL RLS. CI must also run
`tests/integration/test_postgres_rls.py` against a migrated disposable database
with `BUILI_TEST_POSTGRES_API_URL` and `BUILI_TEST_POSTGRES_WORKER_URL`. The test
asserts indirect-table isolation and proves that `buili_api` cannot obtain the
worker bypass by setting `app.is_worker`. Migration inspection must confirm the
`vector_cosine_ops` HNSW index exists before enabling semantic search at scale.

No infrastructure configuration can make model accuracy unconditional. Before
a customer pilot, establish accepted datasets and thresholds for every drawing
class, evidence type, discipline, and revision workflow. Low-confidence or
unsupported inputs must remain review-required instead of being presented as
verified.
