import json
import os
import sys
from decimal import Decimal
import pytest
import boto3
from moto import mock_aws

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from handler import lambda_handler  # noqa: E402


@pytest.fixture(autouse=True)
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
    os.environ["ORDERS_TABLE_NAME"] = "OrdersTableTest"


@pytest.fixture
def dynamodb_table(aws_credentials):
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
        test_table = dynamodb.create_table(
            TableName="OrdersTableTest",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        import handler
        handler._table = test_table
        yield test_table


def test_lambda_handler_single_order_success(dynamodb_table):
    order_payload = {
        "order_id": "ord-101",
        "customer_id": "cust-202",
        "items": [
            {"item_id": "item-A", "quantity": 1, "unit_price": 49.99}
        ],
        "total_amount": 49.99,
        "currency": "eur",
        "created_at": "2026-09-30T10:00:00Z",
    }

    event = {
        "Records": [
            {
                "messageId": "msg-001",
                "body": json.dumps(order_payload),
            }
        ]
    }

    response = lambda_handler(event, None)
    assert response == {"batchItemFailures": []}

    item = dynamodb_table.get_item(
        Key={"PK": "CUSTOMER#cust-202", "SK": "ORDER#ord-101"}
    ).get("Item")

    assert item is not None
    assert item["order_id"] == "ord-101"
    assert item["customer_id"] == "cust-202"
    assert item["total_amount"] == Decimal("49.99")
    assert item["currency"] == "EUR"
    assert item["status"] == "CONFIRMED"


def test_lambda_handler_partial_batch_failures(dynamodb_table):
    valid_payload = {
        "order_id": "ord-201",
        "customer_id": "cust-303",
        "items": [{"item_id": "item-B", "quantity": 2, "unit_price": 10.0}],
        "total_amount": 20.0,
        "created_at": "2026-09-30T10:00:00Z",
    }

    invalid_schema_payload = {
        "order_id": "ord-202",
        "total_amount": -5.0,
    }

    event = {
        "Records": [
            {"messageId": "msg-valid", "body": json.dumps(valid_payload)},
            {"messageId": "msg-bad-json", "body": "{not-valid-json"},
            {"messageId": "msg-bad-schema", "body": json.dumps(invalid_schema_payload)},
        ]
    }

    response = lambda_handler(event, None)

    assert "batchItemFailures" in response
    failed_ids = {f["itemIdentifier"] for f in response["batchItemFailures"]}
    assert failed_ids == {"msg-bad-json", "msg-bad-schema"}

    saved_item = dynamodb_table.get_item(
        Key={"PK": "CUSTOMER#cust-303", "SK": "ORDER#ord-201"}
    ).get("Item")
    assert saved_item is not None


def test_lambda_handler_idempotent_duplicate_order(dynamodb_table):
    order_payload = {
        "order_id": "ord-dup",
        "customer_id": "cust-dup",
        "items": [{"item_id": "item-C", "quantity": 1, "unit_price": 15.0}],
        "total_amount": 15.0,
        "created_at": "2026-09-30T10:00:00Z",
    }

    event = {
        "Records": [
            {"messageId": "msg-dup-1", "body": json.dumps(order_payload)},
            {"messageId": "msg-dup-2", "body": json.dumps(order_payload)},
        ]
    }

    response = lambda_handler(event, None)
    assert response == {"batchItemFailures": []}
