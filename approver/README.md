# approver

Purpose: consumes `loan_submitted` records, applies approval rules, and writes decisions to `loan_status`.

Run locally:

```bash
cd approver
AWS_REGION=us-east-1 AWS_PROFILE=rishab LOAN_SUBMITTED_STREAM=loan_submitted LOAN_STATUS_STREAM=loan_status python main.py
```

Notes: adjust approval logic in `main.py` as needed for POC testing.
