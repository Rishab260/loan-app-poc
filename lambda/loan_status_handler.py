import base64
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict

import boto3

AWS_REGION = os.getenv("AWS_REGION")
ADMIN_LOANS_TABLE = os.getenv("ADMIN_LOANS_TABLE", "admin_loans")

if not AWS_REGION:
    raise RuntimeError("AWS_REGION is required for DynamoDB usage")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dynamodb_table():
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(ADMIN_LOANS_TABLE)


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def handle_record(payload: Dict[str, Any]) -> None:
    if payload.get("status") != "approved":
        return

    user_id = payload.get("user_id")
    if user_id is None:
        return

    item = {
        "UserID": int(user_id),
        "LoanId": payload.get("id"),
        "Name": payload.get("name") or f"User {user_id}",
        "Address": payload.get("address") or "Unknown",
        "LoanAmount": to_decimal(payload.get("amount", 0)),
        "Opted": payload.get("loan_type"),
        "Status": payload.get("status", "approved"),
        "UpdatedAt": now_iso(),
    }

    dynamodb_table().put_item(Item=item)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    records = event.get("Records", [])
    for record in records:
        try:
            encoded = record.get("kinesis", {}).get("data")
            if not encoded:
                continue
            decoded = base64.b64decode(encoded).decode("utf-8")
            payload = json.loads(decoded)
        except Exception:
            continue
        handle_record(payload)

    return {"statusCode": 200, "processed": len(records)}
