#!/bin/bash
set -e

STACK_NAME="${1}"
AWS_PROFILE_ARG=""

if [ -z "${STACK_NAME}" ]; then
  echo "Error: CloudFormation stack name is required." >&2
  echo "Usage: $0 <stack-name> [--profile <aws-profile>]" >&2
  exit 1
fi

shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      AWS_PROFILE_ARG="--profile $2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

echo "Querying CloudFormation stack '${STACK_NAME}' for outputs..."

STACK_OUTPUT=$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --query "Stacks[0].Outputs" --output json ${AWS_PROFILE_ARG} 2>&1) || {
  echo "Error: Failed to describe stack '${STACK_NAME}'. Ensure the stack exists and AWS credentials are configured." >&2
  exit 1
}

BUCKET_NAME=$(echo "${STACK_OUTPUT}" | python3 -c "
import sys, json
outputs = json.load(sys.stdin)
for o in outputs:
    if o['OutputKey'] == 'StaticWebsiteBucketName':
        print(o['OutputValue'])
        sys.exit(0)
print('', file=sys.stderr)
sys.exit(1)
") || {
  echo "Error: Could not find 'StaticWebsiteBucketName' output in stack '${STACK_NAME}'." >&2
  exit 1
}

DISTRIBUTION_ID=$(echo "${STACK_OUTPUT}" | python3 -c "
import sys, json
outputs = json.load(sys.stdin)
for o in outputs:
    if o['OutputKey'] == 'StaticWebsiteDistributionId':
        print(o['OutputValue'])
        sys.exit(0)
print('', file=sys.stderr)
sys.exit(1)
") || {
  echo "Error: Could not find 'StaticWebsiteDistributionId' output in stack '${STACK_NAME}'." >&2
  exit 1
}

echo "Bucket: ${BUCKET_NAME}"
echo "Distribution: ${DISTRIBUTION_ID}"

HTML_FILES=$(find static-website/ -name "*.html" -type f)

if [ -z "${HTML_FILES}" ]; then
  echo "Error: No .html files found in static-website/ directory." >&2
  exit 1
fi

echo "Uploading HTML files to S3..."
for file in ${HTML_FILES}; do
  filename=$(basename "${file}")
  echo "  Uploading ${filename}..."
  aws s3 cp "${file}" "s3://${BUCKET_NAME}/${filename}" --content-type "text/html" ${AWS_PROFILE_ARG} || {
    echo "Error: Failed to upload '${filename}' to s3://${BUCKET_NAME}/." >&2
    exit 1
  }
done

echo "Creating CloudFront invalidation..."
aws cloudfront create-invalidation --distribution-id "${DISTRIBUTION_ID}" --paths "/*" ${AWS_PROFILE_ARG} || {
  echo "Error: Failed to create CloudFront invalidation for distribution '${DISTRIBUTION_ID}'." >&2
  exit 1
}

echo "Deploy complete."
