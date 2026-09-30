resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.project_name}-api-${var.environment}"
  description = "High-throughput asynchronous order ingestion API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_request_validator" "validator" {
  name                        = "OrderPayloadValidator"
  rest_api_id                 = aws_api_gateway_rest_api.api.id
  validate_request_body       = true
  validate_request_parameters = false
}

resource "aws_api_gateway_model" "order_model" {
  rest_api_id  = aws_api_gateway_rest_api.api.id
  name         = "OrderModel"
  description  = "Order JSON validation schema"
  content_type = "application/json"

  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    title     = "OrderInput"
    type      = "object"
    required  = ["order_id", "customer_id", "items", "total_amount", "created_at"]
    properties = {
      order_id = {
        type      = "string"
        minLength = 1
      }
      customer_id = {
        type      = "string"
        minLength = 1
      }
      total_amount = {
        type    = "number"
        minimum = 0.01
      }
      currency = {
        type      = "string"
        minLength = 3
        maxLength = 3
      }
      created_at = {
        type      = "string"
        minLength = 10
      }
      items = {
        type     = "array"
        minItems = 1
        items = {
          type     = "object"
          required = ["item_id", "quantity", "unit_price"]
          properties = {
            item_id = {
              type      = "string"
              minLength = 1
            }
            quantity = {
              type    = "integer"
              minimum = 1
            }
            unit_price = {
              type    = "number"
              minimum = 0.01
            }
          }
        }
      }
    }
  })
}

resource "aws_api_gateway_resource" "orders" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "orders"
}

resource "aws_api_gateway_method" "post_orders" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.orders.id
  http_method   = "POST"
  authorization = "NONE"

  request_validator_id = aws_api_gateway_request_validator.validator.id
  request_models = {
    "application/json" = aws_api_gateway_model.order_model.name
  }
}

resource "aws_api_gateway_integration" "sqs_integration" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.orders.id
  http_method             = aws_api_gateway_method.post_orders.http_method
  integration_http_method = "POST"
  type                    = "AWS"
  credentials             = aws_iam_role.apigateway_sqs_role.arn
  uri                     = "arn:aws:apigateway:${var.aws_region}:sqs:path/${aws_sqs_queue.orders_queue.name}"
  passthrough_behavior    = "NEVER"

  request_parameters = {
    "integration.request.header.Content-Type" = "'application/x-www-form-urlencoded'"
  }

  request_templates = {
    "application/json" = "Action=SendMessage&MessageBody=$util.urlEncode($input.body)"
  }

  depends_on = [aws_iam_role_policy_attachment.apigateway_sqs_attach]
}

resource "aws_api_gateway_method_response" "post_orders_202" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.orders.id
  http_method = aws_api_gateway_method.post_orders.http_method
  status_code = "202"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "sqs_integration_response_202" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.orders.id
  http_method = aws_api_gateway_method.post_orders.http_method
  status_code = aws_api_gateway_method_response.post_orders_202.status_code

  selection_pattern = "^2[0-9][0-9]"

  response_templates = {
    "application/json" = jsonencode({
      status  = "QUEUED"
      message = "Order accepted and queued for asynchronous processing"
    })
  }

  depends_on = [aws_api_gateway_integration.sqs_integration]
}

resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.orders.id,
      aws_api_gateway_method.post_orders.id,
      aws_api_gateway_integration.sqs_integration.id,
      aws_api_gateway_model.order_model.schema,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration_response.sqs_integration_response_202]
}

resource "aws_api_gateway_stage" "stage" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = var.environment
}
