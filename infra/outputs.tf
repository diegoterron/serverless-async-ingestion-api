output "api_endpoint" {
  description = "Base URL for the API Gateway stage"
  value       = "${aws_api_gateway_stage.stage.invoke_url}/orders"
}

output "sqs_queue_url" {
  description = "URL of the primary SQS queue"
  value       = aws_sqs_queue.orders_queue.id
}

output "sqs_queue_arn" {
  description = "ARN of the primary SQS queue"
  value       = aws_sqs_queue.orders_queue.arn
}

output "sqs_dlq_url" {
  description = "URL of the Dead-Letter Queue"
  value       = aws_sqs_queue.orders_dlq.id
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.orders.name
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.order_processor.function_name
}
