#!/usr/bin/env bash
set -euo pipefail

# Package and update Lambda code/handler

FUNCTION_NAME=${FUNCTION_NAME:-loan_handler}
AWS_REGION=${AWS_REGION:-""}
AWS_PROFILE=${AWS_PROFILE:-""}
ZIP_NAME=${ZIP_NAME:-loan_handler.zip}

aws_cmd=(aws)
[[ -n "$AWS_PROFILE" ]] && aws_cmd+=(--profile "$AWS_PROFILE")
[[ -n "$AWS_REGION" ]] && aws_cmd+=(--region "$AWS_REGION")

rm -f "$ZIP_NAME"
zip -r "$ZIP_NAME" loan_status_handler.py requirements.txt >/dev/null

"${aws_cmd[@]}" lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --zip-file "fileb://$ZIP_NAME"

"${aws_cmd[@]}" lambda update-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --handler loan_status_handler.lambda_handler
