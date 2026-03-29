# ── SNS Topic for Alerts ───────────────────────────────────────────────────────
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"

  tags = { Environment = var.environment }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── EC2 Alarms ─────────────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "ec2_cpu_high" {
  alarm_name          = "${var.project_name}-ec2-cpu-high"
  alarm_description   = "EC2 backend CPU utilisation exceeded 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    InstanceId = var.ec2_instance_id
  }

  alarm_actions             = [aws_sns_topic.alerts.arn]
  ok_actions                = [aws_sns_topic.alerts.arn]
  insufficient_data_actions = []

  tags = { Environment = var.environment }
}

resource "aws_cloudwatch_metric_alarm" "ec2_status_check" {
  alarm_name          = "${var.project_name}-ec2-status-check-failed"
  alarm_description   = "EC2 backend instance status check failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0

  dimensions = {
    InstanceId = var.ec2_instance_id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = { Environment = var.environment }
}

# ── Lambda Alarms ──────────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "ocr_lambda_errors" {
  alarm_name          = "${var.project_name}-ocr-lambda-errors"
  alarm_description   = "OCR Lambda is producing errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.ocr_lambda_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = { Environment = var.environment }
}

resource "aws_cloudwatch_metric_alarm" "ai_lambda_errors" {
  alarm_name          = "${var.project_name}-ai-lambda-errors"
  alarm_description   = "AI analysis Lambda is producing errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.ai_lambda_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = { Environment = var.environment }
}

resource "aws_cloudwatch_metric_alarm" "ocr_lambda_duration" {
  alarm_name          = "${var.project_name}-ocr-lambda-duration"
  alarm_description   = "OCR Lambda duration approaching timeout (> 240s avg)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  threshold           = 240000
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.ocr_lambda_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = { Environment = var.environment }
}

# ── SQS Dead-Letter Queue Alarms (critical — means jobs are failing) ──────────
resource "aws_cloudwatch_metric_alarm" "ocr_dlq_messages" {
  alarm_name          = "${var.project_name}-ocr-dlq-not-empty"
  alarm_description   = "Messages in OCR Dead-Letter Queue — documents failing OCR processing"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = var.ocr_dlq_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = { Environment = var.environment }
}

resource "aws_cloudwatch_metric_alarm" "ai_dlq_messages" {
  alarm_name          = "${var.project_name}-ai-dlq-not-empty"
  alarm_description   = "Messages in AI Dead-Letter Queue — documents failing AI analysis"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = var.ai_dlq_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = { Environment = var.environment }
}

# ── CloudWatch Dashboard ───────────────────────────────────────────────────────
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "EC2 CPU Utilization"
          region  = "us-east-1"
          period  = 60
          stat    = "Average"
          metrics = [["AWS/EC2", "CPUUtilization", "InstanceId", var.ec2_instance_id]]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Lambda Errors"
          region  = "us-east-1"
          period  = 300
          stat    = "Sum"
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", var.ocr_lambda_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.ai_lambda_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "SQS DLQ Depth (Failed Jobs)"
          region  = "us-east-1"
          period  = 60
          stat    = "Sum"
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.ocr_dlq_name],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.ai_dlq_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Lambda Duration (ms)"
          region  = "us-east-1"
          period  = 300
          stat    = "Average"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.ocr_lambda_name],
            ["AWS/Lambda", "Duration", "FunctionName", var.ai_lambda_name]
          ]
        }
      }
    ]
  })
}
