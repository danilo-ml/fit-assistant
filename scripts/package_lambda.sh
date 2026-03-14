#!/bin/bash
# Lambda Packaging Script for FitAgent
# Packages source code and dependencies for AWS Lambda deployment

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PACKAGE_DIR="build/lambda-package"
OUTPUT_ZIP="build/lambda.zip"
REQUIREMENTS_FILE="requirements.txt"

echo -e "${GREEN}=== FitAgent Lambda Packaging ===${NC}"
echo ""

# Step 1: Clean previous builds
echo -e "${YELLOW}[1/5] Cleaning previous builds...${NC}"
rm -rf build/
mkdir -p "$PACKAGE_DIR"
echo "✓ Build directory cleaned"
echo ""

# Step 2: Install dependencies
echo -e "${YELLOW}[2/5] Installing dependencies...${NC}"
pip install -r "$REQUIREMENTS_FILE" -t "$PACKAGE_DIR" --upgrade --quiet --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all:

# Remove unnecessary files to reduce package size
echo "  Removing unnecessary files..."
find "$PACKAGE_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type f -name "*.pyc" -delete
find "$PACKAGE_DIR" -type f -name "*.pyo" -delete
# Keep opentelemetry dist-info for metadata
find "$PACKAGE_DIR" -type d -name "*.dist-info" ! -name "opentelemetry*" -exec rm -rf {} + 2>/dev/null || true
find "$PACKAGE_DIR" -type d -name "*.egg-info" ! -name "opentelemetry*" -exec rm -rf {} + 2>/dev/null || true

# Remove additional unnecessary files
echo "  Removing additional bloat..."
rm -rf "$PACKAGE_DIR"/boto3* "$PACKAGE_DIR"/botocore* "$PACKAGE_DIR"/s3transfer* 2>/dev/null || true
find "$PACKAGE_DIR" -type f -name "*.so" -exec strip {} \; 2>/dev/null || true
find "$PACKAGE_DIR" -name "*.md" -delete 2>/dev/null || true
find "$PACKAGE_DIR" -name "*.txt" ! -name "requirements.txt" -delete 2>/dev/null || true
find "$PACKAGE_DIR" -name "*.rst" -delete 2>/dev/null || true

echo "✓ Dependencies installed"
echo ""

# Step 3: Copy source code
echo -e "${YELLOW}[3/5] Copying source code...${NC}"
# Copy contents of src folder to package root (flatten structure for Lambda imports)
cp -r src/* "$PACKAGE_DIR/"
echo "✓ Source code copied"
echo ""

# Step 4: Verify Strands SDK inclusion
echo -e "${YELLOW}[4/6] Verifying Strands SDK...${NC}"
if [ -d "$PACKAGE_DIR/strands_agents" ] || [ -d "$PACKAGE_DIR/strands" ]; then
    echo "✓ Strands SDK found in package"
else
    echo -e "${RED}✗ WARNING: Strands SDK not found in package${NC}"
    echo "  This may cause runtime errors. Verify requirements.txt includes strands-agents"
fi
echo ""

# Step 4.5: Fix OpenTelemetry StopIteration bug for Python 3.12
echo -e "${YELLOW}[5/6] Fixing OpenTelemetry Python 3.12 compatibility...${NC}"
OTEL_CONTEXT_FILE="$PACKAGE_DIR/opentelemetry/context/__init__.py"

if [ -f "$OTEL_CONTEXT_FILE" ]; then
    python3 scripts/fix_opentelemetry_context.py "$OTEL_CONTEXT_FILE"
else
    echo "  OpenTelemetry context not found, skipping patch"
fi
echo ""

# Step 5: Create deployment package
echo -e "${YELLOW}[6/6] Creating deployment package...${NC}"
cd "$PACKAGE_DIR"
zip -r "../../$OUTPUT_ZIP" . -q
cd ../..

# Get package size
PACKAGE_SIZE=$(du -h "$OUTPUT_ZIP" | cut -f1)
echo "✓ Deployment package created: $OUTPUT_ZIP ($PACKAGE_SIZE)"
echo ""

# Verify package size (Lambda limit is 50MB zipped, 250MB unzipped)
PACKAGE_SIZE_BYTES=$(stat -f%z "$OUTPUT_ZIP" 2>/dev/null || stat -c%s "$OUTPUT_ZIP" 2>/dev/null)
MAX_SIZE_BYTES=$((50 * 1024 * 1024))  # 50MB

if [ "$PACKAGE_SIZE_BYTES" -gt "$MAX_SIZE_BYTES" ]; then
    echo -e "${RED}✗ ERROR: Package size ($PACKAGE_SIZE) exceeds Lambda limit (50MB)${NC}"
    echo "  Consider:"
    echo "  - Using Lambda Layers for large dependencies"
    echo "  - Removing unused dependencies"
    echo "  - Using smaller model SDKs"
    exit 1
fi

# Summary
echo -e "${GREEN}=== Packaging Complete ===${NC}"
echo "Package location: $OUTPUT_ZIP"
echo "Package size: $PACKAGE_SIZE"
echo ""
echo "Next steps:"
echo "  1. Upload to S3: aws s3 cp $OUTPUT_ZIP s3://your-deployment-bucket/"
echo "  2. Deploy stack: ./scripts/deploy_staging.sh"
echo ""
