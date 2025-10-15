#!/usr/bin/env bash
#
# HFT CPU Benchmarking Harness - Shell wrapper
# Ensures Python environment and runs the orchestrator

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if config provided
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <config.yaml> [--dry-run]${NC}"
    echo ""
    echo "Examples:"
    echo "  $0 configs/mybox-exploratory.yaml"
    echo "  $0 reports/latest/promote.yaml"
    echo "  $0 configs/mybox-deep.yaml --dry-run"
    exit 1
fi

CONFIG_FILE="$1"
shift  # Remove first arg, pass rest to Python

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ python3 not found${NC}"
    exit 1
fi

# Check dependencies
if ! python3 -c "import yaml, tabulate, numpy" 2>/dev/null; then
    echo -e "${YELLOW}📦 Installing dependencies...${NC}"
    if [ -d "venv" ]; then
        pip install -r requirements.txt
    else
        pip3 install --user -r requirements.txt
    fi
fi

# Sanity checks
echo -e "${GREEN}🔍 Pre-flight checks...${NC}"

# Check numactl
if ! command -v numactl &> /dev/null; then
    echo -e "${YELLOW}⚠️  numactl not found - NUMA pinning will not work${NC}"
fi

# Check ldd
if ! command -v ldd &> /dev/null; then
    echo -e "${YELLOW}⚠️  ldd not found - cannot verify linked libraries${NC}"
fi

# Run the harness
echo -e "${GREEN}🚀 Starting benchmark harness...${NC}"
echo ""

python3 scripts/bench_harness.py "$CONFIG_FILE" "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Benchmark complete${NC}"
else
    echo ""
    echo -e "${RED}❌ Benchmark failed (exit code: $exit_code)${NC}"
fi

exit $exit_code
