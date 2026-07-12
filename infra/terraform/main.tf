data "aws_availability_zones" "available" { state = "available" }
data "aws_caller_identity" "current" {}

locals {
  azs          = slice(data.aws_availability_zones.available.names, 0, 2)
  tags         = { Application = "BUILI", Environment = "production", ManagedBy = "Terraform" }
  cors_origins = [for origin in split(",", var.allowed_origins) : trimspace(origin)]

  api_runtime_environment = [
    { name = "BUILI_ENVIRONMENT", value = "production" },
    { name = "BUILI_LOG_LEVEL", value = "INFO" },
    { name = "BUILI_AUTO_CREATE_SCHEMA", value = "false" },
    { name = "BUILI_DEMO_MODE", value = "false" },
    { name = "BUILI_PUBLIC_API_URL", value = var.public_api_url },
    { name = "BUILI_FRONTEND_URL", value = var.frontend_url },
    { name = "BUILI_CORS_ORIGINS", value = var.allowed_origins },
    { name = "BUILI_COOKIE_SECURE", value = "true" },
    { name = "BUILI_COOKIE_SAMESITE", value = var.cookie_samesite },
    { name = "BUILI_EMAIL_BACKEND", value = "ses" },
    { name = "BUILI_REQUIRE_EMAIL_VERIFICATION", value = "true" },
    { name = "BUILI_JWT_ISSUER", value = var.public_api_url },
    { name = "BUILI_JWT_AUDIENCE", value = "buili-web" },
    { name = "BUILI_OIDC_ISSUER", value = "https://accounts.google.com" },
    { name = "BUILI_STORAGE_BACKEND", value = "s3" },
    { name = "BUILI_S3_BUCKET", value = aws_s3_bucket.objects.id },
    { name = "BUILI_S3_REGION", value = var.aws_region },
    { name = "BUILI_JOB_BACKEND", value = "sqs" },
    { name = "BUILI_SQS_QUEUE_URL", value = aws_sqs_queue.jobs.url },
    { name = "BUILI_MALWARE_SCANNER_BACKEND", value = "clamav" },
    { name = "BUILI_CLAMAV_HOST", value = "127.0.0.1" },
    { name = "BUILI_CLAMAV_PORT", value = "3310" },
    { name = "BUILI_EXTERNAL_AI_ENABLED", value = tostring(var.external_ai_enabled) },
    { name = "OPENAI_MODEL", value = var.openai_model },
    { name = "OPENAI_TRANSCRIBE_MODEL", value = var.openai_transcribe_model },
    { name = "OPENAI_EMBEDDING_MODEL", value = var.openai_embedding_model },
  ]

  common_runtime_secrets = concat(
    [
      { name = "BUILI_JWT_SECRET", valueFrom = "${aws_secretsmanager_secret.api.arn}:JWT_SECRET::" },
      { name = "BUILI_OIDC_CLIENT_ID", valueFrom = "${aws_secretsmanager_secret.api.arn}:OIDC_CLIENT_ID::" },
      { name = "BUILI_ORIGIN_VERIFY_SECRET", valueFrom = "${aws_secretsmanager_secret.api.arn}:ORIGIN_VERIFY_SECRET::" },
    ],
    var.external_ai_enabled ? [
      { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.api.arn}:OPENAI_API_KEY::" },
    ] : [],
  )

  api_runtime_secrets = concat(local.common_runtime_secrets, [
    { name = "BUILI_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.api.arn}:API_DATABASE_URL::" },
  ])

  worker_runtime_secrets = concat(local.common_runtime_secrets, [
    { name = "BUILI_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.api.arn}:WORKER_DATABASE_URL::" },
    { name = "BUILI_WORKER_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.api.arn}:WORKER_DATABASE_URL::" },
  ])

  migration_runtime_secrets = concat(local.common_runtime_secrets, [
    { name = "BUILI_DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.api.arn}:MIGRATION_DATABASE_URL::" },
  ])

  alarm_actions = concat([aws_sns_topic.operations.arn], var.additional_alarm_topic_arns)
}

resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = var.name })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = local.tags
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${var.name}-public-${count.index + 1}" })
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 10)
  tags              = merge(local.tags, { Name = "${var.name}-private-${count.index + 1}" })
}

resource "aws_eip" "nat" {
  count  = 2
  domain = "vpc"
  tags   = merge(local.tags, { Name = "${var.name}-nat-${count.index + 1}" })
}

resource "aws_nat_gateway" "main" {
  count         = 2
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  depends_on    = [aws_internet_gateway.main]
  tags          = merge(local.tags, { Name = "${var.name}-nat-${count.index + 1}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = local.tags
}
resource "aws_route_table" "private" {
  count  = 2
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }
  tags = merge(local.tags, { Name = "${var.name}-private-${count.index + 1}" })
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_s3_bucket" "objects" {
  bucket_prefix = "buili-prod-objects-"
  tags          = local.tags

  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "objects" {
  bucket                  = aws_s3_bucket.objects.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "objects" {
  bucket = aws_s3_bucket.objects.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "objects" {
  bucket = aws_s3_bucket.objects.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_cors_configuration" "objects" {
  bucket = aws_s3_bucket.objects.id
  cors_rule {
    allowed_headers = ["content-type", "x-amz-checksum-sha256", "x-amz-date", "authorization"]
    allowed_methods = ["PUT"]
    allowed_origins = local.cors_origins
    expose_headers  = ["ETag", "x-amz-checksum-sha256", "x-amz-version-id"]
    max_age_seconds = 900
  }
}
resource "aws_s3_bucket_lifecycle_configuration" "objects" {
  bucket = aws_s3_bucket.objects.id
  rule {
    id     = "abort-incomplete"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

resource "aws_s3_bucket_policy" "objects" {
  bucket = aws_s3_bucket.objects.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.objects.arn, "${aws_s3_bucket.objects.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_s3_bucket" "access_logs" {
  bucket_prefix = "buili-prod-access-logs-"
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule { object_ownership = "BucketOwnerPreferred" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    id     = "retain-production-access-logs"
    status = "Enabled"
    filter {}
    expiration { days = 365 }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
  depends_on = [aws_s3_bucket_versioning.access_logs]
}

resource "aws_s3_bucket_versioning" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_policy" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowALBLogDelivery"
        Effect    = "Allow"
        Principal = { Service = "logdelivery.elasticloadbalancing.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.access_logs.arn}/alb/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = { StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" } }
      },
      {
        Sid       = "AllowALBLogDeliveryAclCheck"
        Effect    = "Allow"
        Principal = { Service = "logdelivery.elasticloadbalancing.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.access_logs.arn
      },
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [aws_s3_bucket.access_logs.arn, "${aws_s3_bucket.access_logs.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
    ]
  })
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-jobs-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = local.tags
}
resource "aws_sqs_queue" "jobs" {
  name                       = "${var.name}-jobs"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy             = jsonencode({ deadLetterTargetArn = aws_sqs_queue.dlq.arn, maxReceiveCount = 4 })
  tags                       = local.tags
}

resource "aws_ecr_repository" "api" {
  name                 = "buili/api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = local.tags
}
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy     = jsonencode({ rules = [{ rulePriority = 1, description = "Keep 30 images", selection = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 30 }, action = { type = "expire" } }] })
}

resource "aws_secretsmanager_secret" "api" {
  name                    = "${var.name}/api"
  recovery_window_in_days = 30
  tags                    = local.tags
}

resource "aws_db_subnet_group" "main" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
  tags       = local.tags
}
resource "aws_security_group" "db" {
  name   = "${var.name}-db"
  vpc_id = aws_vpc.main.id
  tags   = local.tags
}

resource "aws_iam_role" "rds_monitoring" {
  name = "${var.name}-rds-monitoring"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_db_parameter_group" "postgres" {
  name   = "${var.name}-postgres16"
  family = "postgres16"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  parameter {
    name  = "log_connections"
    value = "1"
  }
  parameter {
    name  = "log_disconnections"
    value = "1"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }
  tags = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier                      = replace(var.name, "_", "-")
  engine                          = "postgres"
  engine_version                  = "16.4"
  instance_class                  = var.db_instance_class
  allocated_storage               = 30
  max_allocated_storage           = 200
  storage_encrypted               = true
  db_name                         = "buili"
  username                        = "buili_admin"
  manage_master_user_password     = true
  db_subnet_group_name            = aws_db_subnet_group.main.name
  parameter_group_name            = aws_db_parameter_group.postgres.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  multi_az                        = true
  publicly_accessible             = false
  backup_retention_period         = var.db_backup_retention_days
  backup_window                   = "09:00-10:00"
  maintenance_window              = "sun:10:00-sun:11:00"
  deletion_protection             = var.db_deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.name}-final"
  performance_insights_enabled    = true
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  copy_tags_to_snapshot           = true
  delete_automated_backups        = false
  auto_minor_version_upgrade      = true
  tags                            = local.tags
}

resource "aws_security_group" "alb" {
  name        = "${var.name}-alb"
  description = "Cloudflare-only ingress to the BUILI API origin"
  vpc_id      = aws_vpc.main.id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "alb_http_cloudflare_ipv4" {
  for_each          = toset(var.cloudflare_ipv4_cidrs)
  security_group_id = aws_security_group.alb.id
  description       = "Cloudflare HTTP redirect"
  cidr_ipv4         = each.value
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "alb_https_cloudflare_ipv4" {
  for_each          = toset(var.cloudflare_ipv4_cidrs)
  security_group_id = aws_security_group.alb.id
  description       = "Cloudflare HTTPS origin traffic"
  cidr_ipv4         = each.value
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_api" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward requests only to API tasks"
  referenced_security_group_id = aws_security_group.api.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_security_group" "api" {
  name        = "${var.name}-api"
  description = "Private ECS API and worker tasks"
  vpc_id      = aws_vpc.main.id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "api_from_alb" {
  security_group_id            = aws_security_group.api.id
  description                  = "API listener from the ALB only"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "api_egress" {
  security_group_id = aws_security_group.api.id
  description       = "HTTPS, database, and managed-service egress through private routes"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "worker" {
  name        = "${var.name}-worker"
  description = "Private background workers with no inbound listeners"
  vpc_id      = aws_vpc.main.id
  tags        = local.tags
}

resource "aws_vpc_security_group_egress_rule" "worker_egress" {
  security_group_id = aws_security_group.worker.id
  description       = "Database and managed-service egress through private routes"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group_rule" "db_from_api" {
  type                     = "ingress"
  security_group_id        = aws_security_group.db.id
  source_security_group_id = aws_security_group.api.id
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "db_from_worker" {
  type                     = "ingress"
  security_group_id        = aws_security_group.db.id
  source_security_group_id = aws_security_group.worker.id
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
}

resource "aws_lb" "api" {
  name                       = substr(replace(var.name, "_", "-"), 0, 32)
  load_balancer_type         = "application"
  subnets                    = aws_subnet.public[*].id
  security_groups            = [aws_security_group.alb.id]
  drop_invalid_header_fields = true
  enable_deletion_protection = var.alb_deletion_protection

  access_logs {
    bucket  = aws_s3_bucket.access_logs.id
    prefix  = "alb"
    enabled = true
  }

  depends_on = [aws_s3_bucket_policy.access_logs, aws_s3_bucket_ownership_controls.access_logs]
  tags       = local.tags
}

resource "aws_lb_target_group" "api" {
  name        = substr("${replace(var.name, "_", "-")}-api", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health/ready"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }

  deregistration_delay = 30
  tags                 = local.tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = "{\"error\":\"not_found\"}"
      status_code  = "404"
    }
  }
}

resource "aws_lb_listener_rule" "canonical_api_host" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    host_header { values = [var.api_hostname] }
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name}/api"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.name}/worker"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_ecs_cluster" "main" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = local.tags
}

resource "aws_iam_role" "execution" {
  name = "${var.name}-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = aws_secretsmanager_secret.api.arn
    }]
  })
}

resource "aws_iam_role" "api_task" {
  name = "${var.name}-api-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "api_task" {
  role = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ProjectObjectReadWrite"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.objects.arn}/org/*"
      },
      {
        Sid      = "ProjectObjectList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.objects.arn
        Condition = {
          StringLike = { "s3:prefix" = ["org/*"] }
        }
      },
      {
        Sid      = "EnqueueJobs"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.jobs.arn
      },
      {
        Sid      = "SendTransactionalEmail"
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/${var.email_domain}"
      },
    ]
  })
}

resource "aws_iam_role" "worker_task" {
  name = "${var.name}-worker-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "worker_task" {
  role = aws_iam_role.worker_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ProjectObjectReadWrite"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.objects.arn}/org/*"
      },
      {
        Sid      = "ProjectObjectList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.objects.arn
        Condition = {
          StringLike = { "s3:prefix" = ["org/*"] }
        }
      },
      {
        Sid    = "ConsumeJobs"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes",
        ]
        Resource = aws_sqs_queue.jobs.arn
      },
    ]
  })
}

# Migrations need database credentials only.  They must not inherit the
# worker's S3/SQS permissions, even though they use the same application image.
resource "aws_iam_role" "migration_task" {
  name = "${var.name}-migration-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    environment = local.api_runtime_environment
    secrets     = local.api_runtime_secrets
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
    stopTimeout = 30
    linuxParameters = {
      initProcessEnabled = true
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])
  tags = local.tags
}

resource "aws_ecs_service" "api" {
  name                               = "api"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.api_desired_count
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 90
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  propagate_tags                     = "SERVICE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener_rule.canonical_api_host]
  tags       = local.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn

  container_definitions = jsonencode([{
    name        = "worker"
    image       = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential   = true
    command     = ["python", "-m", "buili_api.worker"]
    environment = local.api_runtime_environment
    secrets     = local.worker_runtime_secrets
    dependsOn = [{
      containerName = "clamav"
      condition     = "HEALTHY"
    }]
    stopTimeout = 120
    linuxParameters = {
      initProcessEnabled = true
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }, {
    name              = "clamav"
    image             = var.clamav_image
    essential         = true
    cpu               = 512
    memoryReservation = 3072
    portMappings = [{
      containerPort = 3310
      protocol      = "tcp"
    }]
    healthCheck = {
      command     = ["CMD-SHELL", "echo PING | nc 127.0.0.1 3310 | grep PONG"]
      interval    = 30
      timeout     = 10
      retries     = 5
      startPeriod = 120
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "clamav"
      }
    }
  }])
  tags = local.tags
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${var.name}-migration"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.migration_task.arn

  container_definitions = jsonencode([{
    name        = "migration"
    image       = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential   = true
    command     = ["alembic", "upgrade", "head"]
    environment = local.api_runtime_environment
    secrets     = local.migration_runtime_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "migration"
      }
    }
  }])
  tags = local.tags
}

resource "aws_ecs_service" "worker" {
  name                               = "worker"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.worker.arn
  desired_count                      = var.worker_min_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  propagate_tags                     = "SERVICE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = false
  }

  tags = local.tags
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_max_count
  min_capacity       = max(2, var.api_desired_count)
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 60
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

resource "aws_appautoscaling_target" "worker" {
  max_capacity       = var.worker_max_count
  min_capacity       = var.worker_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "worker_scale_out" {
  name               = "${var.name}-worker-scale-out"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_lower_bound = 0
      metric_interval_upper_bound = 20
      scaling_adjustment          = 1
    }

    step_adjustment {
      metric_interval_lower_bound = 20
      scaling_adjustment          = 3
    }
  }
}

resource "aws_appautoscaling_policy" "worker_scale_in" {
  name               = "${var.name}-worker-scale-in"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 300
    metric_aggregation_type = "Average"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = -1
    }
  }
}
