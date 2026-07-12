variable "aws_region" {
  description = "AWS Region for the production stack."
  type        = string
  default     = "us-west-1"
}

variable "name" {
  description = "Resource name prefix."
  type        = string
  default     = "buili-prod"
}

variable "image_tag" {
  description = "Immutable API/worker image tag (prefer a Git SHA, not latest)."
  type        = string
  default     = "replace-with-git-sha"

  validation {
    condition     = var.image_tag != "latest" && length(trimspace(var.image_tag)) >= 7
    error_message = "image_tag must be an immutable release identifier (for example, a Git SHA), not latest."
  }
}

variable "certificate_arn" {
  description = "ACM certificate ARN for api.builiconstruction.com. Production is TLS-only and this value is required."
  type        = string

  validation {
    condition     = startswith(var.certificate_arn, "arn:aws:acm:")
    error_message = "certificate_arn must be a non-empty ACM certificate ARN."
  }
}

variable "api_hostname" {
  description = "Canonical API hostname proxied through Cloudflare."
  type        = string
  default     = "api.builiconstruction.com"
}

variable "public_api_url" {
  description = "Canonical public API URL."
  type        = string
  default     = "https://api.builiconstruction.com"

  validation {
    condition     = startswith(var.public_api_url, "https://")
    error_message = "public_api_url must use HTTPS."
  }
}

variable "frontend_url" {
  description = "Canonical authenticated application URL."
  type        = string
  default     = "https://app.builiconstruction.com"

  validation {
    condition     = startswith(var.frontend_url, "https://")
    error_message = "frontend_url must use HTTPS."
  }
}

variable "email_domain" {
  description = "Pre-verified Amazon SES sending domain. DNS verification records remain managed in Cloudflare."
  type        = string
  default     = "builiconstruction.com"
}

variable "allowed_origins" {
  description = "Comma-separated CORS origins passed to the API and applied to direct S3 uploads."
  type        = string
  default     = "https://app.builiconstruction.com"

  validation {
    condition = alltrue([
      for origin in split(",", var.allowed_origins) :
      startswith(trimspace(origin), "https://") &&
      !contains(["https://builiconstruction.com", "https://www.builiconstruction.com"], trimspace(origin))
    ])
    error_message = "Every production CORS origin must use HTTPS; marketing apex/www origins are forbidden."
  }
}

variable "clamav_image" {
  description = "Pinned ClamAV daemon image used by the worker sidecar. Review and vulnerability-scan before promotion."
  type        = string
  default     = "clamav/clamav:1.4"
}

variable "cookie_samesite" {
  description = "Authentication cookie SameSite policy."
  type        = string
  default     = "lax"

  validation {
    condition     = contains(["lax", "strict", "none"], var.cookie_samesite)
    error_message = "cookie_samesite must be lax, strict, or none."
  }
}

variable "external_ai_enabled" {
  description = "Explicit production kill switch for external AI processing. A key is injected only when enabled."
  type        = bool
  default     = false
}

variable "openai_model" {
  description = "Pinned model identifier used by the API when external AI is enabled."
  type        = string
  default     = "gpt-5.6-terra"
}

variable "openai_transcribe_model" {
  description = "Pinned speech-to-text model identifier."
  type        = string
  default     = "gpt-4o-transcribe"
}

variable "openai_embedding_model" {
  description = "Pinned embedding model identifier."
  type        = string
  default     = "text-embedding-3-small"
}

variable "cloudflare_ipv4_cidrs" {
  description = "Cloudflare proxy IPv4 ranges allowed to reach the public ALB. Keep synchronized with https://www.cloudflare.com/ips/."
  type        = list(string)
  default = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
  ]

  validation {
    condition     = length(var.cloudflare_ipv4_cidrs) > 0
    error_message = "At least one Cloudflare IPv4 range is required; an empty list would expose or disable the origin."
  }
}

variable "alb_deletion_protection" {
  description = "Protect the production load balancer from accidental deletion."
  type        = bool
  default     = true
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.small"
}

variable "db_deletion_protection" {
  type    = bool
  default = true
}

variable "db_backup_retention_days" {
  description = "Point-in-time recovery window for RDS."
  type        = number
  default     = 35

  validation {
    condition     = var.db_backup_retention_days >= 7 && var.db_backup_retention_days <= 35
    error_message = "db_backup_retention_days must be between 7 and 35."
  }
}

variable "api_cpu" {
  type    = number
  default = 1024
}

variable "api_memory" {
  type    = number
  default = 2048
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "api_max_count" {
  type    = number
  default = 10
}

variable "worker_cpu" {
  type    = number
  default = 2048
}

variable "worker_memory" {
  type    = number
  default = 8192
}

variable "worker_min_count" {
  type    = number
  default = 1
}

variable "worker_max_count" {
  type    = number
  default = 10
}

variable "worker_target_queue_depth" {
  description = "Target visible SQS messages used by worker target-tracking autoscaling."
  type        = number
  default     = 5
}

variable "queue_oldest_message_alarm_seconds" {
  description = "Alarm when the oldest queued job exceeds this age."
  type        = number
  default     = 600
}

variable "log_retention_days" {
  description = "CloudWatch application and task-event log retention."
  type        = number
  default     = 90
}

variable "alarm_email" {
  description = "Optional operations email. AWS requires subscription confirmation."
  type        = string
  default     = ""
}

variable "additional_alarm_topic_arns" {
  description = "Additional SNS topic ARNs for production alarms."
  type        = list(string)
  default     = []
}
