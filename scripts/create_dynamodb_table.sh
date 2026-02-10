#!/usr/bin/env bash
set -euo pipefail

# DynamoDB table creator for admin dashboard
# Table: admin_loans (default)

TABLE_NAME=${ADMIN_LOANS_TABLE:-admin_loans}
AWS_REGION=${AWS_REGION:-""}
AWS_PROFILE=${AWS_PROFILE:-""}
BILLING_MODE=${BILLING_MODE:-PAY_PER_REQUEST}
READ_CAPACITY=${READ_CAPACITY:-5}
WRITE_CAPACITY=${WRITE_CAPACITY:-5}

aws_cmd=(aws)
[[ -n "$AWS_PROFILE" ]] && aws_cmd+=(--profile "$AWS_PROFILE")
[[ -n "$AWS_REGION" ]] && aws_cmd+=(--region "$AWS_REGION")

require_cli() {
  if ! command -v aws >/dev/null 2>&1; then
    echo "aws CLI not found. Install AWS CLI v2 and configure credentials." >&2
    exit 1
  fi
}

table_exists() {
  local name="$1"
  "${aws_cmd[@]}" dynamodb describe-table --table-name "$name" >/dev/null 2>&1
}

wait_active() {
  local name="$1"
  "${aws_cmd[@]}" dynamodb wait table-exists --table-name "$name"
  local status
  status=$("${aws_cmd[@]}" dynamodb describe-table --table-name "$name" --query 'Table.TableStatus' --output text 2>/dev/null || true)
  if [[ "$status" == "ACTIVE" ]]; then
    echo "Table $name is ACTIVE"
    return 0
  fi
  echo "Table $name is not ACTIVE (status=$status)" >&2
  exit 1
}

create_table() {
  local name="$1"

  echo -e "\n--- $name"

  if table_exists "$name"; then
    echo "Table already exists; skipping create"
    wait_active "$name"
    return 0
  fi

  echo "Creating table $name (partition key: UserID)..."
  if [[ "$BILLING_MODE" == "PAY_PER_REQUEST" ]]; then
    "${aws_cmd[@]}" dynamodb create-table \
      --table-name "$name" \
      --attribute-definitions AttributeName=UserID,AttributeType=N \
      --key-schema AttributeName=UserID,KeyType=HASH \
      --billing-mode PAY_PER_REQUEST
  else
    "${aws_cmd[@]}" dynamodb create-table \
      --table-name "$name" \
      --attribute-definitions AttributeName=UserID,AttributeType=N \
      --key-schema AttributeName=UserID,KeyType=HASH \
      --provisioned-throughput ReadCapacityUnits="$READ_CAPACITY",WriteCapacityUnits="$WRITE_CAPACITY"
  fi

  wait_active "$name"
}

main() {
  require_cli
  create_table "$TABLE_NAME"
  echo -e "\nDone."
}

main "$@"
