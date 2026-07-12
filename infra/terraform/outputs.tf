output "api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "api_alb_dns_name" {
  description = "Origin DNS name. Do not publish it; create a proxied Cloudflare CNAME for the canonical API hostname."
  value       = aws_lb.api.dns_name
}

output "object_bucket" {
  value = aws_s3_bucket.objects.id
}

output "access_log_bucket" {
  value = aws_s3_bucket.access_logs.id
}

output "jobs_queue_url" {
  value = aws_sqs_queue.jobs.url
}

output "jobs_dlq_url" {
  value = aws_sqs_queue.dlq.url
}

output "api_secret_arn" {
  value = aws_secretsmanager_secret.api.arn
}

output "database_endpoint" {
  value     = aws_db_instance.postgres.address
  sensitive = true
}

output "operations_topic_arn" {
  description = "Subscribe the production incident-management integration to this topic."
  value       = aws_sns_topic.operations.arn
}

output "migration_task_definition_arn" {
  description = "Run this one-shot task and require exit code 0 before updating API/worker services."
  value       = aws_ecs_task_definition.migration.arn
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "worker_security_group_id" {
  value = aws_security_group.worker.id
}
