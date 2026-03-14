#!/bin/bash
# Automated fix and test loop for Lambda deployment

set -e

AWS_PROFILE=danilosousa
FUNCTION_NAME="fitagent-message-processor-production"
S3_BUCKET="fitagent-lambda-deployments-429649512384"
S3_KEY="production/lambda-latest.zip"
REGION="us-east-1"
MAX_ITERATIONS=5

echo "=== Lambda Fix and Test Loop ==="
echo "Function: $FUNCTION_NAME"
echo "Max iterations: $MAX_ITERATIONS"
echo ""

for i in $(seq 1 $MAX_ITERATIONS); do
    echo "=========================================="
    echo "Iteration $i of $MAX_ITERATIONS"
    echo "=========================================="
    
    # Step 1: Package Lambda
    echo "[1/5] Packaging Lambda..."
    bash scripts/package_lambda.sh > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "✗ Packaging failed"
        exit 1
    fi
    echo "✓ Package created"
    
    # Step 2: Upload to S3
    echo "[2/5] Uploading to S3..."
    aws s3 cp build/lambda.zip s3://$S3_BUCKET/$S3_KEY --region $REGION --profile $AWS_PROFILE > /dev/null 2>&1
    echo "✓ Uploaded"
    
    # Step 3: Update Lambda function
    echo "[3/5] Updating Lambda function..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --s3-bucket $S3_BUCKET \
        --s3-key $S3_KEY \
        --region $REGION \
        --profile $AWS_PROFILE \
        --no-cli-pager > /dev/null 2>&1
    
    # Wait for update to complete
    aws lambda wait function-updated \
        --function-name $FUNCTION_NAME \
        --region $REGION \
        --profile $AWS_PROFILE
    echo "✓ Lambda updated"
    
    # Step 4: Trigger a test (check if there are messages in queue)
    echo "[4/5] Checking SQS queue..."
    QUEUE_URL="https://sqs.us-east-1.amazonaws.com/429649512384/fitagent-messages-production.fifo"
    MSG_COUNT=$(aws sqs get-queue-attributes \
        --queue-url $QUEUE_URL \
        --attribute-names ApproximateNumberOfMessages \
        --region $REGION \
        --profile $AWS_PROFILE \
        --query 'Attributes.ApproximateNumberOfMessages' \
        --output text)
    
    if [ "$MSG_COUNT" -gt 0 ]; then
        echo "  Messages in queue: $MSG_COUNT"
        echo "  Waiting 10 seconds for processing..."
        sleep 10
    else
        echo "  No messages in queue - send a WhatsApp message to test"
        echo "  Waiting 15 seconds..."
        sleep 15
    fi
    
    # Step 5: Check for errors
    echo "[5/5] Checking for errors..."
    ERROR_LOG=$(aws logs tail /aws/lambda/$FUNCTION_NAME \
        --region $REGION \
        --profile $AWS_PROFILE \
        --since 1m \
        --format short 2>/dev/null | grep -i "ERROR\|ImportModuleError\|ValueError" | head -5)
    
    if [ -z "$ERROR_LOG" ]; then
        echo "✓ No errors found!"
        echo ""
        echo "=========================================="
        echo "SUCCESS! Lambda is working correctly"
        echo "=========================================="
        exit 0
    else
        echo "✗ Errors found:"
        echo "$ERROR_LOG" | head -3
        echo ""
        
        # Analyze error and suggest fix
        if echo "$ERROR_LOG" | grep -q "Propagator.*not found"; then
            echo "→ Missing OpenTelemetry propagator"
            echo "  Add to requirements.txt and retry"
        elif echo "$ERROR_LOG" | grep -q "No module named"; then
            MODULE=$(echo "$ERROR_LOG" | grep -oP "No module named '\K[^']+")
            echo "→ Missing module: $MODULE"
            echo "  Add to requirements.txt and retry"
        elif echo "$ERROR_LOG" | grep -q "ImportModuleError"; then
            echo "→ Import error detected"
        fi
        
        if [ $i -eq $MAX_ITERATIONS ]; then
            echo ""
            echo "=========================================="
            echo "FAILED after $MAX_ITERATIONS iterations"
            echo "=========================================="
            echo "Last error:"
            echo "$ERROR_LOG"
            exit 1
        fi
        
        echo ""
        echo "Continuing to next iteration..."
        sleep 2
    fi
done
