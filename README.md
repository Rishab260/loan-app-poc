# Loan App POC

Small proof-of-concept demonstrating event-driven loan processing using AWS Kinesis.

**Architecture**
- `loan-api`: submits loan requests to the `loan_submitted` Kinesis stream and publishes status updates to Redis/admin sync.
- `approver`: consumes `loan_submitted`, applies approval logic, and writes results to the `loan_status` Kinesis stream.
- `admin-dashboard`: a lightweight UI that reads DynamoDB and updates via SSE without page reloads.
- `lambda/loan_status_handler.py`: processes `loan_status` Kinesis records and updates DynamoDB when approved.
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
- `ADMIN_LOANS_TABLE` — DynamoDB table for admin dashboard (default `admin_loans`)
- `ADMIN_SEED` — seed demo data in admin dashboard (`true`/`false`)

Run with optional overrides, e.g.: `AWS_REGION=us-east-1 AWS_PROFILE=rishab STREAM_SUFFIX=_dev`.

**Run locally (docker-compose)**
The project provides `docker-compose.yml` configured to launch services. Example:

```bash
# start containers (reads .env in repo root)
docker compose up --build

# stop
docker compose down
```

**End-to-end workflow**

1. Create AWS resources.

```bash
bash scripts/create_kinesis_streams.sh
bash scripts/create_dynamodb_table.sh
```

2. Deploy or update the Lambda and ensure the Kinesis mapping exists.

```bash
cd lambda
LOAN_STATUS_STREAM_ARN=arn:aws:kinesis:us-east-1:123456789012:stream/loan_status \
ADMIN_LOANS_TABLE=admin_loans \
AWS_REGION=us-east-1 \
bash deploy.sh

aws lambda list-event-source-mappings --function-name loan_handler
```

3. Start the local services.

```bash
docker compose up --build
```

4. Submit a loan request.

- The `loan-api` service publishes to the `loan_submitted` stream.
- The `approver` service reads `loan_submitted` and writes decisions to `loan_status`.
- The Lambda reads `loan_status` and upserts items in DynamoDB.
- The admin dashboard reads DynamoDB and refreshes via SSE.

5. Verify the flow.

- Check the admin dashboard UI for updated rows.
- Tail the Lambda logs if needed: `aws logs tail /aws/lambda/loan_handler --since 5m`.

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

