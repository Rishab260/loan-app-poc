import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI

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


async def consume_requests(stop_event: asyncio.Event):
    iterators = await get_shard_iterators(LOAN_SUBMITTED_STREAM)
    while not stop_event.is_set():
        if not iterators:
            await asyncio.sleep(2)
            iterators = await get_shard_iterators(LOAN_SUBMITTED_STREAM)
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
                await auto_approve(message)

            next_it = resp.get("NextShardIterator")
            if next_it:
                next_iterators.append(next_it)
        iterators = next_iterators
        await asyncio.sleep(1)


async def auto_approve(message: Any):
    try:
        if isinstance(message, dict):
            payload = message
        elif isinstance(message, (str, bytes, bytearray)):
            payload = json.loads(message)
        else:
            return
    except Exception:
        return

    loan_id = payload.get("id")
    if loan_id:
        await put_record(LOAN_STATUS_STREAM, {"id": loan_id, "status": "approved"}, partition_key=str(loan_id))


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    consumer_task: Optional[asyncio.Task] = asyncio.create_task(consume_requests(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        if consumer_task:
            consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await consumer_task


app = FastAPI(lifespan=lifespan)


@app.post("/approve/{loan_id}")
async def approve(loan_id: str):
    await put_record(LOAN_STATUS_STREAM, {"id": loan_id, "status": "approved"}, partition_key=str(loan_id))
    return {"status": "approved"}


@app.post("/deny/{loan_id}")
async def deny(loan_id: str):
    await put_record(LOAN_STATUS_STREAM, {"id": loan_id, "status": "denied"}, partition_key=str(loan_id))
    return {"status": "denied"}
