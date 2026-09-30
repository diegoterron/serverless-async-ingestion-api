resource "aws_sqs_queue" "orders_dlq" {
  name                      = "${var.project_name}-orders-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days
}

resource "aws_sqs_queue" "orders_queue" {
  name                       = "${var.project_name}-orders-queue-${var.environment}"
  visibility_timeout_seconds = 60 # 6x lambda timeout of 10s
  message_retention_seconds  = 345600 # 4 days

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orders_dlq.arn
    maxReceiveCount     = 3
  })
}
