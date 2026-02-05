# Loan App POC

Small proof-of-concept demonstrating event-driven loan processing using AWS Kinesis.

**Architecture**
- `loan-api`: submits loan requests to the `loan_submitted` Kinesis stream and publishes status updates to Redis/admin sync.
- `approver`: consumes `loan_submitted`, applies approval logic, and writes results to the `loan_status` Kinesis stream.
- `admin-dashboard`: a lightweight UI that reads `loan_status` (or subscribes to Redis) to display loan decisions.
- Kinesis streams used: `loan_submitted`, `loan_status` (optional `STREAM_SUFFIX` appended by scripts).

**Prerequisites**
- Docker & Docker Compose (for local end-to-end run)
- Python 3.10+ (if running services locally without containers)
- AWS CLI v2 configured and usable: `aws sts get-caller-identity` must succeed
- AWS credentials must have Kinesis permissions to create/delete streams when using the scripts

**Streams**
See `scripts/README.md` for Kinesis stream creation and deletion (create_kinesis_streams.sh / delete_kinesis_streams.sh).

**Environment**
Important environment variables used by services:
- `AWS_REGION` (e.g. `us-east-1`) — required for boto3/Kinesis clients
- `AWS_PROFILE` (optional) — local profile used with AWS CLI/boto3
- `LOAN_SUBMITTED_STREAM` — name of stream for loan submissions (default `loan_submitted`)
- `LOAN_STATUS_STREAM` — name of stream for loan decisions (default `loan_status`)
- `REDIS_URL` — address of Redis used for inter-service notifications (if used)

Run with optional overrides, e.g.: `AWS_REGION=us-east-1 AWS_PROFILE=rishab STREAM_SUFFIX=_dev`.

**Run locally (docker-compose)**
The project provides `docker-compose.yml` configured to launch services. Example:

```bash
# start containers (reads .env in repo root)
docker compose up --build

# stop
docker compose down
```

**Run a service directly (example: loan-api)**

```bash
# from repo root
cd loan-api
# ensure required env vars are set
AWS_REGION=us-east-1 AWS_PROFILE=rishab LOAN_SUBMITTED_STREAM=loan_submitted LOAN_STATUS_STREAM=loan_status python main.py
```

**Kinesis CLI quick tests**
- Put a record (base64/raw option required for newer AWS CLI):

```bash
aws kinesis put-record \
  --stream-name loan_status \
  --partition-key "pk1" \
  --data '"{"id":"abc","status":"approved"}"' \
  --cli-binary-format raw-in-base64-out \
  --profile rishab --region us-east-1
```

- Get shard iterator and read records (example):

```bash
aws kinesis list-shards --stream-name loan_status --profile rishab --region us-east-1
aws kinesis get-shard-iterator --stream-name loan_status --shard-id shardId-000000000000 --shard-iterator-type TRIM_HORIZON --profile rishab --region us-east-1
aws kinesis get-records --shard-iterator <iterator> --profile rishab --region us-east-1
```

**Repository layout**
- `admin-dashboard/` — UI and templates
- `approver/` — approval service
- `loan-api/` — submits and consumes Kinesis records
- `scripts/` — helpers to create/delete Kinesis streams (see scripts/README.md)
- `.env` — local env file (not committed; included in .gitignore)

**Notes & troubleshooting**
- If you see region or credential errors, confirm `AWS_REGION` and `AWS_PROFILE` match the region where streams exist.
- Recent AWS CLI versions require `--cli-binary-format raw-in-base64-out` for directly providing plaintext data.
- This POC uses a single shard by default. Increase `SHARD_COUNT` or switch to on-demand for higher throughput.

**Contributing**
- Open an issue or PR for doc fixes or environment improvements.
- Keep environment variables documented and avoid committing secrets.

**References**
- Scripts for stream lifecycle: `scripts/README.md`

