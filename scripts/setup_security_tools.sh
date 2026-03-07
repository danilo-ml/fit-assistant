#!/bin/bash

# Setup Security Tools
# This script installs and configures security tools to prevent future incidents

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║              Security Tools Setup                            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo ""
echo "This script will install and configure security tools:"
echo "  - pre-commit hooks"
echo "  - detect-secrets"
echo "  - bandit (Python security linter)"
echo ""
read -p "Press Enter to continue or Ctrl+C to exit..."

# Check if Python is installed
echo ""
echo -e "${BLUE}[1/5] Checking prerequisites...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}✗ pip3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ pip3 found${NC}"

# Install pre-commit
echo ""
echo -e "${BLUE}[2/5] Installing pre-commit...${NC}"

if command -v pre-commit &> /dev/null; then
    echo -e "${GREEN}✓ pre-commit already installed${NC}"
else
    pip3 install pre-commit
    echo -e "${GREEN}✓ pre-commit installed${NC}"
fi

# Install detect-secrets
echo ""
echo -e "${BLUE}[3/5] Installing detect-secrets...${NC}"

pip3 install detect-secrets
echo -e "${GREEN}✓ detect-secrets installed${NC}"

# Install bandit
echo ""
echo -e "${BLUE}[4/5] Installing bandit...${NC}"

pip3 install bandit[toml]
echo -e "${GREEN}✓ bandit installed${NC}"

# Setup pre-commit hooks
echo ""
echo -e "${BLUE}[5/5] Setting up pre-commit hooks...${NC}"

# Create secrets baseline
if [ ! -f .secrets.baseline ]; then
    echo "Creating secrets baseline..."
    detect-secrets scan > .secrets.baseline
    echo -e "${GREEN}✓ Secrets baseline created${NC}"
else
    echo -e "${GREEN}✓ Secrets baseline already exists${NC}"
fi

# Install pre-commit hooks
pre-commit install
echo -e "${GREEN}✓ Pre-commit hooks installed${NC}"

# Run pre-commit on all files (optional)
echo ""
read -p "Run pre-commit checks on all files now? (yes/no): " RUN_ALL

if [ "$RUN_ALL" = "yes" ]; then
    echo ""
    echo "Running pre-commit on all files..."
    pre-commit run --all-files || true
fi

# Summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║              Security Tools Setup Complete!                  ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Installed tools:"
echo -e "${GREEN}✓${NC} pre-commit - Runs checks before each commit"
echo -e "${GREEN}✓${NC} detect-secrets - Scans for secrets in code"
echo -e "${GREEN}✓${NC} bandit - Python security linter"
echo ""
echo "Pre-commit hooks will now run automatically on every commit."
echo ""
echo "To manually run checks:"
echo "  pre-commit run --all-files"
echo ""
echo "To scan for secrets:"
echo "  detect-secrets scan"
echo ""
echo "To run security linter:"
echo "  bandit -r src/"
echo ""
