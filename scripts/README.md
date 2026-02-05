# Kinesis POC Setup

Create Kinesis data streams that mirror the existing Kafka topics used by this app.

## Streams created
- loan_submitted
- loan_status

An optional `STREAM_SUFFIX` is appended to each (e.g., `_dev` → `loan_submitted_dev`).

## Prerequisites
- AWS CLI v2 installed (`aws --version`).
- Credentials configured (`aws sts get-caller-identity` should succeed).
- Permissions: `kinesis:CreateStream`, `kinesis:DescribeStreamSummary`, `kinesis:Wait`, `kinesis:ListStreams`, `kinesis:DeleteStream`.

## Create streams
Run with bash (no execute bit required):

```bash
bash scripts/create_kinesis_streams.sh
```

Optional overrides:

```bash
AWS_REGION=us-west-2 \
AWS_PROFILE=your-profile \
STREAM_SUFFIX=_dev \
SHARD_COUNT=1 \
bash scripts/create_kinesis_streams.sh
```

## Delete streams (stop billing)
Deletes the same streams (with optional suffix) and waits for removal:

```bash
AWS_REGION=us-west-2 \
AWS_PROFILE=your-profile \
STREAM_SUFFIX=_dev \
bash scripts/delete_kinesis_streams.sh
```

## Notes
- Default shard count is 1 for POC; scale shards or switch to on-demand later as throughput grows.
- No server-side encryption or IAM scaffolding is included (by design for POC scope).
- The script is idempotent: existing streams are left intact and waited on until `ACTIVE`.
 - The delete script skips missing streams and waits until they are fully removed.
