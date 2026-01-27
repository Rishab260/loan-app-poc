
import asyncio
import uuid
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from faststream.kafka import KafkaBroker
from faststream import FastStream
from redis_client import redis_client

broker = KafkaBroker("redpanda:9092")

@asynccontextmanager
async def lifespan(app: FastAPI):
    for _ in range(10):
        try:
            await broker.start()
            break
        except Exception:
            await asyncio.sleep(2)
    yield
    await broker.close()

app = FastAPI(lifespan=lifespan)
stream = FastStream(broker)

@app.get("/", response_class=HTMLResponse)
async def index():
    return open("templates/index.html").read()

@app.post("/submit")
async def submit(request: Request):
    data = dict(await request.form())
    print("[DEBUG] Received form data:", data)
    loan_id = str(uuid.uuid4())
    data["id"] = loan_id
    try:
        result = await broker.publish(json.dumps(data), topic="loan.requests")
        print(f"[DEBUG] Published to Kafka: {data}, result: {result}")
    except Exception as e:
        print(f"[ERROR] Failed to publish to Kafka: {e}")
        return {"error": str(e)}
    return {"id": loan_id}

@broker.subscriber("loan.status")
async def status_consumer(message: dict):
    channel = f"loan_status:{message['id']}"
    await redis_client.publish(channel, json.dumps(message))

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
