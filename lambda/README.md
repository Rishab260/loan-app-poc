# Loan Status Lambda

Triggered by the `loan_status` Kinesis stream. When a record has `status=approved`, the function upserts a DynamoDB item in the admin loans table so the admin dashboard updates without a page reload.

## Environment

- `AWS_REGION` (required)
- `ADMIN_LOANS_TABLE` (default: `admin_loans`)

## Deploy with AWS SAM

```bash
cd lambda

LOAN_STATUS_STREAM_ARN=arn:aws:kinesis:us-east-1:123456789012:stream/loan_status \
ADMIN_LOANS_TABLE=admin_loans \
AWS_REGION=us-east-1 \
bash deploy.sh
```

## Lambda-Kinesis event source mapping

The mapping connects the `loan_status` stream to the Lambda so records invoke the handler. The SAM deploy creates this mapping using the provided `LOAN_STATUS_STREAM_ARN`.

To create or verify it manually with the CLI:

```bash
aws lambda create-event-source-mapping \
  --function-name loan_handler \
  --event-source-arn arn:aws:kinesis:us-east-1:123456789012:stream/loan_status \
  --starting-position TRIM_HORIZON

aws lambda list-event-source-mappings --function-name loan_handler
```

## Update existing Lambda (CLI)

```bash
cd lambda
AWS_PROFILE=rishab AWS_REGION=us-east-1 FUNCTION_NAME=loan_handler bash update_lambda.sh
```

## Expected Kinesis record payload

```json
{
  "id": "<loan_id>",
  "status": "approved",
  "user_id": 123,
  "loan_type": "refinance",
  "name": "Alex Johnson",
  "address": "123 Maple St",
  "amount": 250000
}
```

## DynamoDB item shape

- `UserID` (partition key, Number)
- `LoanId` (String)
- `Name` (String)
- `Address` (String)
- `LoanAmount` (Number)
- `Opted` (String)
- `Status` (String)
- `UpdatedAt` (String, ISO-8601)
