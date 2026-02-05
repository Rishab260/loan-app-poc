"""
Create a .env file in parent directory with:

# AWS credentials for local docker compose
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=....
AWS_SECRET_ACCESS_KEY=....

# Kinesis stream names (override if you used suffixes)
LOAN_SUBMITTED_STREAM=loan_submitted
LOAN_STATUS_STREAM=loan_status
"""


import asyncio
import uuid
import json
import os
from contextlib import asynccontextmanager, suppress
from typing import Any, Dict, List, Optional

import boto3
import httpx
from botocore.exceptions import ClientError
from fastapi import FastAPI, Request, Response, Cookie, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, StreamingResponse
from redis_client import redis_client

LOAN_SUBMITTED_STREAM = os.getenv("LOAN_SUBMITTED_STREAM", "loan_submitted")
LOAN_STATUS_STREAM = os.getenv("LOAN_STATUS_STREAM", "loan_status")
AWS_REGION = os.getenv("AWS_REGION")

if not AWS_REGION:
    raise RuntimeError("AWS_REGION is required for Kinesis usage")


def kinesis_client():
    return boto3.client("kinesis", region_name=AWS_REGION)


async def put_record(stream_name: str, payload: Dict[str, Any], partition_key: str) -> None:
    data = json.dumps(payload).encode()
    await asyncio.to_thread(
        kinesis_client().put_record,
        StreamName=stream_name,
        Data=data,
        PartitionKey=partition_key,
    )


async def get_shard_iterators(stream_name: str) -> List[str]:
    client = kinesis_client()
    shards = await asyncio.to_thread(client.list_shards, StreamName=stream_name)
    iterators: List[str] = []
    for shard in shards.get("Shards", []):
        shard_id = shard["ShardId"]
        it_resp = await asyncio.to_thread(
            client.get_shard_iterator,
            StreamName=stream_name,
            ShardId=shard_id,
            ShardIteratorType="TRIM_HORIZON",
        )
        iterator = it_resp.get("ShardIterator")
        if iterator:
            iterators.append(iterator)
    return iterators


async def consume_status_stream(stop_event: asyncio.Event):
    iterators = await get_shard_iterators(LOAN_STATUS_STREAM)
    while not stop_event.is_set():
        if not iterators:
            await asyncio.sleep(2)
            iterators = await get_shard_iterators(LOAN_STATUS_STREAM)
            continue
        next_iterators: List[str] = []
        for iterator in iterators:
            if stop_event.is_set():
                break
            try:
                resp = await asyncio.to_thread(
                    kinesis_client().get_records, ShardIterator=iterator, Limit=25
                )
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code")
                if code in {"ExpiredIteratorException", "ProvisionedThroughputExceededException"}:
                    continue
                print(f"[WARN] Kinesis get_records failed: {e}")
                continue

            for record in resp.get("Records", []):
                try:
                    message = json.loads(record.get("Data", b"{}"))
                except Exception:
                    continue
                await handle_status_message(message)

            next_it = resp.get("NextShardIterator")
            if next_it:
                next_iterators.append(next_it)
        iterators = next_iterators
        await asyncio.sleep(1)


async def handle_status_message(message: Dict[str, Any]) -> None:
    if not isinstance(message, dict) or "id" not in message:
        return
    channel = f"loan_status:{message['id']}"
    await redis_client.publish(channel, json.dumps(message))
    if message.get("status") == "approved":
        try:
            cached = await redis_client.get(f"loan:{message['id']}")
            if cached:
                loan_data = json.loads(cached)
                opted = loan_data.get("loan_type")
                user_id = loan_data.get("user_id") or loan_data.get("UserID")
                name = loan_data.get("name")
                address = loan_data.get("address")
                loan_amount = loan_data.get("amount")
                if opted and user_id:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            "http://admin-dashboard:8000/opt-by-id",
                            data={
                                "user_id": user_id,
                                "opted": opted,
                                "name": name or "",
                                "address": address or "",
                                "loan_amount": loan_amount or 0,
                            },
                            timeout=5.0,
                        )
                        if resp.status_code >= 400:
                            print(f"[WARN] Admin update failed: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[WARN] Failed to sync admin opted status: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    consumer_task: Optional[asyncio.Task] = asyncio.create_task(consume_status_stream(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        if consumer_task:
            consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await consumer_task

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def index():
    return open("templates/index.html").read()


async def get_current_user(session_token: str = Cookie(None)):
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = await redis_client.get(f"session:{session_token}")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    user_raw = await redis_client.get(f"user:{user_id}")
    if not user_raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    user_obj = json.loads(user_raw)
    user_obj.pop("password", None)
    user_obj["user_id"] = user_id
    return user_obj


@app.get("/profile")
async def profile(user: Dict[str, Any] = Depends(get_current_user)):
    return user

@app.post("/submit")
async def submit(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    data: Dict[str, Any] = dict(await request.form())
    print("[DEBUG] Received form data:", data)
    loan_id = str(uuid.uuid4())
    data["id"] = loan_id
    # attach submitter if provided
    if user:
        submitted_by = user.get("user_id")
        if submitted_by is not None:
            data["submitted_by"] = str(submitted_by)
    # ensure user_id flows with the loan
    user_id = user.get("user_id") if user else None
    if "user_id" not in data and user_id is not None:
        data["user_id"] = str(user_id)
    # cache loan details so we can enrich approval updates
    try:
        await redis_client.set(f"loan:{loan_id}", json.dumps(data), ex=86400)
    except Exception as e:
        print(f"[WARN] Failed to cache loan data: {e}")
    try:
        await put_record(LOAN_SUBMITTED_STREAM, data, partition_key=loan_id)
        print(f"[DEBUG] Published to Kinesis: {data}")
    except Exception as e:
        print(f"[ERROR] Failed to publish to Kinesis: {e}")
        return {"error": str(e)}
    return {"id": loan_id}


@app.post("/login")
async def login(response: Response, user_id: str = Form(...), password: str = Form(...)):
    user_key = f"user:{user_id}"
    user = await redis_client.get(user_key)
    if user:
        user_obj = json.loads(user)
        if user_obj.get("password") != password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        # create user (simple demo registration)
        user_obj = {"user_id": user_id, "password": password}
        await redis_client.set(user_key, json.dumps(user_obj))

    token = str(uuid.uuid4())
    session_key = f"session:{token}"
    await redis_client.set(session_key, user_id, ex=3600)
    response.set_cookie("session_token", token, max_age=3600, path="/", httponly=True)
    user_obj.pop("password", None)
    user_obj["user_id"] = user_id
    return user_obj


@app.post("/logout")
async def logout(response: Response, session_token: str = Cookie(None)):
    if session_token:
        await redis_client.delete(f"session:{session_token}")
    response.delete_cookie("session_token", path="/")
    return {"logged_out": True}


@app.get("/events/{loan_id}")
async def events(loan_id: str):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"loan_status:{loan_id}")

    async def event_stream():
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield f"data: {msg['data']}\n\n"
        finally:
            await pubsub.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
