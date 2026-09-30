import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from models import Order

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_table = None


def get_table():
    global _table
    if _table is None:
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-1"))
        table_name = os.environ.get("ORDERS_TABLE_NAME", "OrdersTable")
        dynamodb = boto3.resource("dynamodb", region_name=region)
        _table = dynamodb.Table(table_name)
    return _table


def process_order(record: Dict[str, Any]) -> None:
    message_id = record["messageId"]
    raw_body = record.get("body", "{}")

    data = json.loads(raw_body)
    order = Order(**data)

    items_payload = [
        {
            "item_id": item.item_id,
            "quantity": item.quantity,
            "unit_price": Decimal(str(item.unit_price)),
        }
        for item in order.items
    ]

    db_item = {
        "PK": f"CUSTOMER#{order.customer_id}",
        "SK": f"ORDER#{order.order_id}",
        "GSI1PK": f"ORDER#{order.order_id}",
        "GSI1SK": "METADATA",
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "items": items_payload,
        "total_amount": Decimal(str(order.total_amount)),
        "currency": order.currency,
        "status": "CONFIRMED",
        "created_at": order.created_at,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    get_table().put_item(
        Item=db_item,
        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
    )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = event.get("Records", [])
    batch_item_failures: List[Dict[str, str]] = []

    for record in records:
        message_id = record["messageId"]
        try:
            process_order(record)
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.error(f"Invalid order payload in message {message_id}: {exc}")
            batch_item_failures.append({"itemIdentifier": message_id})
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code == "ConditionalCheckFailedException":
                # Order already processed, safe to acknowledge
                logger.info(f"Duplicate order in message {message_id}, skipping")
                continue

            logger.error(f"DynamoDB error processing message {message_id}: {exc}")
            batch_item_failures.append({"itemIdentifier": message_id})
        except Exception as exc:
            logger.error(f"Unexpected error processing message {message_id}: {exc}")
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}
