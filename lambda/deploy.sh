#!/usr/bin/env bash
set -euo pipefail

# Deploy the loan status Lambda with AWS SAM

STACK_NAME=${STACK_NAME:-loan-status-lambda}
ADMIN_LOANS_TABLE=${ADMIN_LOANS_TABLE:-admin_loans}
LOAN_STATUS_STREAM_ARN=${LOAN_STATUS_STREAM_ARN:-""}
AWS_REGION=${AWS_REGION:-""}
AWS_PROFILE=${AWS_PROFILE:-""}

if [[ -z "$LOAN_STATUS_STREAM_ARN" ]]; then
  echo "LOAN_STATUS_STREAM_ARN is required" >&2
  exit 1
fi

sam_cmd=(sam)

AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" "${sam_cmd[@]}" build

AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" "${sam_cmd[@]}" deploy \
  --resolve-s3 \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    AdminLoansTable="$ADMIN_LOANS_TABLE" \
    LoanStatusStreamArn="$LOAN_STATUS_STREAM_ARN"
