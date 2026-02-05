# loan-api

Purpose: submits loan requests to `LOAN_SUBMITTED_STREAM` and consumes `LOAN_STATUS_STREAM` updates for admin sync.

Run locally:

```bash
cd loan-api
# set envs
AWS_REGION=us-east-1 AWS_PROFILE=rishab LOAN_SUBMITTED_STREAM=loan_submitted LOAN_STATUS_STREAM=loan_status python main.py
```

Important env vars:
- `AWS_REGION` (required)
- `AWS_PROFILE` (optional)
- `LOAN_SUBMITTED_STREAM` (default `loan_submitted`)
- `LOAN_STATUS_STREAM` (default `loan_status`)
- `REDIS_URL` (optional)

Docker: the provided Dockerfile builds the service image used by docker-compose.
