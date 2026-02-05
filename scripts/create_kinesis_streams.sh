#!/usr/bin/env bash
set -euo pipefail

# Kinesis stream creator for POC parity with Kafka topics
# Streams: loan_submitted, loan_status (suffix optional)

STREAMS=("loan_submitted" "loan_status")
STREAM_SUFFIX=${STREAM_SUFFIX:-""}
SHARD_COUNT=${SHARD_COUNT:-1}
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

wait_active() {
  local name="$1"
  for _ in {1..20}; do
    local status
    status=$("${aws_cmd[@]}" kinesis describe-stream-summary --stream-name "$name" \
      --query 'StreamDescriptionSummary.StreamStatus' --output text 2>/dev/null || true)
    if [[ "$status" == "ACTIVE" ]]; then
      echo "Stream $name is ACTIVE"
      return 0
    fi
    sleep 3
  done
  echo "Timed out waiting for stream $name to become ACTIVE" >&2
  exit 1
}

create_stream() {
  local base="$1"
  local name
  name=$(full_name "$base")

  echo "\n--- $name"

  if stream_exists "$name"; then
    echo "Stream already exists; skipping create"
    wait_active "$name"
    return 0
  fi

  echo "Creating stream $name with $SHARD_COUNT shard(s)..."
  "${aws_cmd[@]}" kinesis create-stream --stream-name "$name" --shard-count "$SHARD_COUNT"

  echo "Waiting for stream to exist..."
  "${aws_cmd[@]}" kinesis wait stream-exists --stream-name "$name"
  wait_active "$name"
}

main() {
  require_cli
  for stream in "${STREAMS[@]}"; do
    create_stream "$stream"
  done
  echo "\nDone."
}

main "$@"
