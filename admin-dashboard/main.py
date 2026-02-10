import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

AWS_REGION = os.getenv("AWS_REGION")
ADMIN_LOANS_TABLE = os.getenv("ADMIN_LOANS_TABLE", "admin_loans")
ADMIN_SEED = os.getenv("ADMIN_SEED", "true").lower() not in {"0", "false", "no"}

if not AWS_REGION:
    raise RuntimeError("AWS_REGION is required for DynamoDB usage")


def dynamodb_table():
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(ADMIN_LOANS_TABLE)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decimal_to_number(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "UserID": int(item.get("UserID")),
        "Name": item.get("Name", ""),
        "Address": item.get("Address", ""),
        "LoanAmount": float(decimal_to_number(item.get("LoanAmount", 0))),
        "Opted": item.get("Opted"),
        "Status": item.get("Status", "pending"),
        "UpdatedAt": item.get("UpdatedAt"),
    }


def scan_loans() -> List[Dict[str, Any]]:
    table = dynamodb_table()
    items: List[Dict[str, Any]] = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    normalized = [normalize_item(item) for item in items]
    normalized.sort(key=lambda row: row.get("UserID", 0))
    return normalized


def seed_data() -> None:
    if not ADMIN_SEED:
        return
    table = dynamodb_table()
    resp = table.scan(Limit=1)
    if resp.get("Items"):
        return
    now = now_iso()
    table.put_item(
        Item={
            "UserID": 1,
            "Name": "Alex Johnson",
            "Address": "123 Maple St",
            "LoanAmount": Decimal("250000"),
            "Status": "pending",
            "UpdatedAt": now,
        }
    )
    table.put_item(
        Item={
            "UserID": 2,
            "Name": "Jamie Smith",
            "Address": "456 Oak Ave",
            "LoanAmount": Decimal("310000"),
            "Status": "pending",
            "UpdatedAt": now,
        }
    )


def build_item(
    user_id: int,
    name: str,
    address: str,
    loan_amount: float,
    opted: Optional[str],
    status: str,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "UserID": int(user_id),
        "Name": name,
        "Address": address,
        "LoanAmount": Decimal(str(loan_amount)),
        "Status": status,
        "UpdatedAt": now_iso(),
    }
    if opted:
        item["Opted"] = opted
    return item


def token_from_loans(loans: List[Dict[str, Any]]) -> str:
    parts = [
        f"{row.get('UserID')}|{row.get('Opted')}|{row.get('Status')}|{row.get('UpdatedAt')}"
        for row in loans
    ]
    digest = hashlib.sha1(";".join(parts).encode()).hexdigest()
    return digest


templates = Jinja2Templates(directory="templates")
app = FastAPI(title="Admin Dashboard")


@app.on_event("startup")
def on_startup() -> None:
    seed_data()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    loans = scan_loans()
    return templates.TemplateResponse("admin.html", {"request": request, "loans": loans})


@app.get("/api/loans")
def list_loans():
    return scan_loans()


@app.get("/events")
async def events():
    async def event_stream():
        last_token = ""
        last_keepalive = time.monotonic()
        while True:
            loans = await asyncio.to_thread(scan_loans)
            token = token_from_loans(loans)
            if token != last_token:
                last_token = token
                payload = json.dumps({"type": "loans_updated"})
                yield f"data: {payload}\n\n"
            now = time.monotonic()
            if now - last_keepalive > 15:
                yield ": keepalive\n\n"
                last_keepalive = now
            await asyncio.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/opt/{user_id}")
def set_opted(user_id: int, opted: str = Form(...)):
    if opted not in {"pay-mortgage", "refinance"}:
        raise HTTPException(status_code=400, detail="Invalid option")

    table = dynamodb_table()
    try:
        resp = table.get_item(Key={"UserID": int(user_id)})
    except ClientError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Loan not found")

    item["Opted"] = opted
    item["Status"] = item.get("Status", "pending")
    item["UpdatedAt"] = now_iso()
    table.put_item(Item=item)
    return RedirectResponse(url="/", status_code=303)


@app.post("/reset/{user_id}")
def reset_opted(user_id: int):
    table = dynamodb_table()
    try:
        resp = table.get_item(Key={"UserID": int(user_id)})
    except ClientError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Loan not found")

    item.pop("Opted", None)
    item["Status"] = "pending"
    item["UpdatedAt"] = now_iso()
    table.put_item(Item=item)
    return RedirectResponse(url="/", status_code=303)


@app.post("/opt-by-id")
def set_opted_by_id(
    user_id: int = Form(...),
    opted: str = Form(...),
    name: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    loan_amount: Optional[str] = Form(None),
):
    if opted not in {"pay-mortgage", "refinance"}:
        raise HTTPException(status_code=400, detail="Invalid option")

    try:
        amount_val = float(loan_amount) if loan_amount is not None else 0.0
    except ValueError:
        amount_val = 0.0

    item = build_item(
        user_id=user_id,
        name=name or f"User {user_id}",
        address=address or "Unknown",
        loan_amount=amount_val,
        opted=opted,
        status="approved",
    )
    dynamodb_table().put_item(Item=item)
    return {"updated": int(user_id), "opted": opted}
