# BUILI infrastructure

`compose.yml` is the local integration stack: PostgreSQL + pgvector, private
MinIO object storage, an SQS-compatible queue, and the API.

```powershell
docker compose -f infra/compose.yml up --build
```

`terraform/` is the production AWS foundation:

- two-AZ VPC, private ECS/Fargate API and worker services, and one NAT gateway
  per Availability Zone;
- a public ALB whose security group accepts only the published Cloudflare proxy
  networks, with mandatory ACM TLS and a canonical-host listener rule;
- private Multi-AZ RDS PostgreSQL with forced TLS, 35-day point-in-time recovery,
  enhanced monitoring, performance insights, and exported PostgreSQL logs;
- encrypted/versioned private S3, immutable-from-runtime project objects, and
  one-year ALB access logs;
- SQS with a DLQ, queue-depth worker autoscaling, CloudWatch alarms, ECS OOM
  event alerts, and an encrypted operations SNS topic;
- separate least-privilege API and worker task roles, ECR immutable tags, and
  Secrets Manager runtime injection.
- separate PostgreSQL URLs/principals for API, worker and migrations; the API
  never receives the worker RLS-bypass principal;
- a one-shot ECS migration task that must succeed before service rollout, plus
  a ClamAV worker sidecar whose positive verdict is required to leave quarantine.

Terraform state uses an encrypted S3 backend with an S3 lock file. Bootstrap
that state bucket separately, copy `backend.hcl.example` outside source control,
and initialize with:

```powershell
terraform -chdir=infra/terraform init -backend-config=backend.hcl
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -var-file=production.tfvars
```

No credential or secret value belongs in Terraform variables/state. Populate
the created Secrets Manager record through a protected CI job or the AWS
console. See `docs/DEPLOYMENT.md` for the required keys, Cloudflare cutover,
SES/Google setup, alarm subscriptions, and release gates.
