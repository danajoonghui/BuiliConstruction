resource "aws_sns_topic" "operations" {
  name              = "${var.name}-operations"
  kms_master_key_id = "alias/aws/sns"
  tags              = local.tags
}

resource "aws_sns_topic_subscription" "operations_email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.operations.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "jobs_dlq_visible" {
  alarm_name          = "${var.name}-jobs-dlq-not-empty"
  alarm_description   = "At least one background job exhausted retries and entered the DLQ."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { QueueName = aws_sqs_queue.dlq.name }
  tags                = local.tags
}

resource "aws_cloudwatch_metric_alarm" "jobs_oldest_age" {
  alarm_name          = "${var.name}-jobs-oldest-message"
  alarm_description   = "Background processing latency exceeded the production objective."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.queue_oldest_message_alarm_seconds
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { QueueName = aws_sqs_queue.jobs.name }
  tags                = local.tags
}

resource "aws_cloudwatch_metric_alarm" "worker_backlog_scale_out" {
  alarm_name          = "${var.name}-worker-backlog-scale-out"
  alarm_description   = "Scale workers out as visible queue depth grows."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = var.worker_target_queue_depth
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_appautoscaling_policy.worker_scale_out.arn]
  dimensions          = { QueueName = aws_sqs_queue.jobs.name }
  tags                = local.tags
}

resource "aws_cloudwatch_metric_alarm" "worker_idle_scale_in" {
  alarm_name          = "${var.name}-worker-idle-scale-in"
  alarm_description   = "Scale down only after both visible and in-flight jobs remain at zero."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  evaluation_periods  = 10
  datapoints_to_alarm = 10
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_appautoscaling_policy.worker_scale_in.arn]

  metric_query {
    id          = "visible"
    return_data = false
    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesVisible"
      period      = 60
      stat        = "Maximum"
      dimensions  = { QueueName = aws_sqs_queue.jobs.name }
    }
  }

  metric_query {
    id          = "inflight"
    return_data = false
    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesNotVisible"
      period      = 60
      stat        = "Maximum"
      dimensions  = { QueueName = aws_sqs_queue.jobs.name }
    }
  }

  metric_query {
    id          = "idle"
    label       = "Queue idle"
    expression  = "IF((visible + inflight) == 0, 1, 0)"
    return_data = true
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "worker_memory_high" {
  alarm_name          = "${var.name}-worker-memory-high"
  alarm_description   = "Worker memory is close to its Fargate limit; investigate large documents or leaks before an OOM stop."
  namespace           = "AWS/ECS"
  metric_name         = "MemoryUtilization"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = 85
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.worker.name
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "worker_cpu_high" {
  alarm_name          = "${var.name}-worker-cpu-high"
  alarm_description   = "Worker CPU remained saturated after queue-depth scaling."
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 10
  datapoints_to_alarm = 8
  comparison_operator = "GreaterThanThreshold"
  threshold           = 90
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.worker.name
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "api_target_5xx" {
  alarm_name          = "${var.name}-api-target-5xx"
  alarm_description   = "The API returned five or more 5xx responses in five minutes."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 2
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }
  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "${var.name}-rds-free-storage-low"
  alarm_description   = "RDS free storage dropped below 5 GiB."
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  comparison_operator = "LessThanThreshold"
  threshold           = 5368709120
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { DBInstanceIdentifier = aws_db_instance.postgres.id }
  tags                = local.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${var.name}-rds-cpu-high"
  alarm_description   = "RDS CPU remained above 85 percent for fifteen minutes."
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = 85
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
  dimensions          = { DBInstanceIdentifier = aws_db_instance.postgres.id }
  tags                = local.tags
}

resource "aws_cloudwatch_event_rule" "ecs_oom" {
  name        = "${var.name}-ecs-oom"
  description = "Capture ECS tasks stopped because a container exceeded memory."
  event_pattern = jsonencode({
    source        = ["aws.ecs"]
    "detail-type" = ["ECS Task State Change"]
    detail = {
      clusterArn = [aws_ecs_cluster.main.arn]
      lastStatus = ["STOPPED"]
      containers = {
        reason = [{ prefix = "OutOfMemory" }]
      }
    }
  })
  tags = local.tags
}

data "aws_iam_policy_document" "operations_topic" {
  statement {
    sid       = "AccountAdministration"
    effect    = "Allow"
    actions   = ["SNS:*", ]
    resources = [aws_sns_topic.operations.arn]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  statement {
    sid       = "CloudWatchAlarmPublish"
    effect    = "Allow"
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.operations.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid       = "EventBridgePublish"
    effect    = "Allow"
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.operations.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudwatch_event_rule.ecs_oom.arn]
    }
  }
}

resource "aws_sns_topic_policy" "operations" {
  arn    = aws_sns_topic.operations.arn
  policy = data.aws_iam_policy_document.operations_topic.json
}

resource "aws_cloudwatch_event_target" "ecs_oom_operations" {
  rule       = aws_cloudwatch_event_rule.ecs_oom.name
  target_id  = "operations-sns"
  arn        = aws_sns_topic.operations.arn
  depends_on = [aws_sns_topic_policy.operations]
}
