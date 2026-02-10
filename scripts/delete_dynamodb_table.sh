#!/usr/bin/env bash
set -euo pipefail

# DynamoDB table deleter for admin dashboard

TABLE_NAME=${ADMIN_LOANS_TABLE:-admin_loans}
AWS_REGION=${AWS_REGION:-""}
AWS_PROFILE=${AWS_PROFILE:-""}

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

wait_deleted() {
  local name="$1"
  "${aws_cmd[@]}" dynamodb wait table-not-exists --table-name "$name"
  echo "Table $name deleted"
}

main() {
  require_cli

  echo -e "\n--- $TABLE_NAME"

  if ! table_exists "$TABLE_NAME"; then
    echo "Table does not exist; skipping delete"
    return 0
  fi

  echo "Deleting table $TABLE_NAME..."
  "${aws_cmd[@]}" dynamodb delete-table --table-name "$TABLE_NAME" >/dev/null
  wait_deleted "$TABLE_NAME"
  echo -e "\nDone."
}

main "$@"
