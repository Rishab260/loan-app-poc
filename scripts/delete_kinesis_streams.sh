#!/usr/bin/env bash
set -euo pipefail

# Delete the Kinesis streams used in this POC to prevent ongoing billing.
# Streams: loan_submitted, loan_status (suffix optional)

STREAMS=("loan_submitted" "loan_status")
STREAM_SUFFIX=${STREAM_SUFFIX:-""}
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

full_name() {
  local base="$1"
  echo "${base}${STREAM_SUFFIX}"
}

stream_exists() {
  local name="$1"
  "${aws_cmd[@]}" kinesis describe-stream-summary --stream-name "$name" >/dev/null 2>&1
}

delete_stream() {
  local base="$1"
  local name
  name=$(full_name "$base")

  echo "\n--- $name"

  if ! stream_exists "$name"; then
    echo "Stream does not exist; skipping"
    return 0
  fi

  echo "Deleting stream $name..."
  "${aws_cmd[@]}" kinesis delete-stream --stream-name "$name"

  echo "Waiting for stream to be deleted..."
  "${aws_cmd[@]}" kinesis wait stream-not-exists --stream-name "$name"
  echo "Stream $name deleted."
}

main() {
  require_cli
  for stream in "${STREAMS[@]}"; do
    delete_stream "$stream"
  done
  echo "\nDone."
}

main "$@"
