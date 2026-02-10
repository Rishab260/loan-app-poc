#!/usr/bin/env bash
set -euo pipefail

# Deploy Lambda via CloudFormation using template.yaml

STACK_NAME=${STACK_NAME:-loan-status-lambda}
ADMIN_LOANS_TABLE=${ADMIN_LOANS_TABLE:-admin_loans}
LOAN_STATUS_STREAM_ARN=${LOAN_STATUS_STREAM_ARN:-""}
S3_BUCKET=${S3_BUCKET:-""}
AWS_REGION=${AWS_REGION:-""}
AWS_PROFILE=${AWS_PROFILE:-""}

if [[ -z "$LOAN_STATUS_STREAM_ARN" ]]; then
  echo "LOAN_STATUS_STREAM_ARN is required" >&2
  exit 1
fi

if [[ -z "$S3_BUCKET" ]]; then
  echo "S3_BUCKET is required (bucket for packaged Lambda artifacts)" >&2
  exit 1
fi

aws_cmd=(aws)
[[ -n "$AWS_PROFILE" ]] && aws_cmd+=(--profile "$AWS_PROFILE")
[[ -n "$AWS_REGION" ]] && aws_cmd+=(--region "$AWS_REGION")

cleanup() {
  rm -f packaged.yaml
}

trap cleanup EXIT

if ! "${aws_cmd[@]}" s3api head-bucket --bucket "$S3_BUCKET" >/dev/null 2>&1; then
  echo "Creating S3 bucket $S3_BUCKET"
  if [[ "$AWS_REGION" == "us-east-1" || -z "$AWS_REGION" ]]; then
    "${aws_cmd[@]}" s3api create-bucket --bucket "$S3_BUCKET" >/dev/null
  else
    "${aws_cmd[@]}" s3api create-bucket \
      --bucket "$S3_BUCKET" \
      --create-bucket-configuration LocationConstraint="$AWS_REGION" >/dev/null
  fi
fi

"${aws_cmd[@]}" cloudformation package \
  --template-file template.yaml \
  --s3-bucket "$S3_BUCKET" \
  --output-template-file packaged.yaml

"${aws_cmd[@]}" cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file packaged.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    AdminLoansTable="$ADMIN_LOANS_TABLE" \
    LoanStatusStreamArn="$LOAN_STATUS_STREAM_ARN"
