#!/usr/bin/env bash
#
# Helper script to check system is ready for benchmarking

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔍 HFT CPU Benchmark - System Check"
echo ""

errors=0
warnings=0

# Check Python
echo -n "Python 3: "
if command -v python3 &> /dev/null; then
    version=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓${NC} $version"
else
    echo -e "${RED}✗ Not found${NC}"
    ((errors++))
fi

# Check pip packages
echo -n "PyYAML: "
if python3 -c "import yaml" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Not installed${NC}"
    ((errors++))
fi

echo -n "tabulate: "
if python3 -c "import tabulate" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Not installed${NC}"
    ((errors++))
fi

echo -n "numpy: "
if python3 -c "import numpy" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Not installed${NC}"
    ((errors++))
fi

# Check numactl
echo -n "numactl: "
if command -v numactl &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ Not found${NC}"
    ((errors++))
fi

# Check ldd
echo -n "ldd: "
if command -v ldd &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC}  Not found (provenance will be incomplete)"
    ((warnings++))
fi

# Check jq (optional but useful)
echo -n "jq: "
if command -v jq &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC}  Not found (optional, for result analysis)"
    ((warnings++))
fi

echo ""
echo "System Configuration:"
echo ""

# CPU info
echo "CPU:"
if [ -f /proc/cpuinfo ]; then
    model=$(grep "model name" /proc/cpuinfo | head -1 | cut -d':' -f2 | xargs)
    phys=$(grep "physical id" /proc/cpuinfo | sort -u | wc -l)
    cores=$(grep "cpu cores" /proc/cpuinfo | head -1 | cut -d':' -f2 | xargs)
    echo "  Model: $model"
    echo "  Sockets: $phys"
    echo "  Cores per socket: $cores"
    echo "  Total physical cores: $((phys * cores))"
fi

# NUMA and Physical Core Detection
echo ""
echo "NUMA Topology:"
if command -v numactl &> /dev/null; then
    nodes=$(numactl --hardware | grep "available:" | cut -d':' -f2 | xargs)
    echo "  $nodes"
    echo ""
    echo "  Physical cores (use these for --physcpubind):"
    
    # Parse lscpu to show physical cores only
    if command -v lscpu &> /dev/null; then
        physical_cores=$(lscpu --parse=CPU,Core | grep -v '^#' | awk -F',' '!seen[$2]++ {print $1}' | tr '\n' ',' | sed 's/,$//')
        echo "    CPUs: $physical_cores"
        
        # Show per-node breakdown
        echo ""
        echo "  Per-node breakdown:"
        for node in $(seq 0 $((${nodes%% *} - 1))); do
            node_physical=$(lscpu --parse=CPU,Core,Node | grep -v '^#' | awk -F',' -v node=$node '$3==node && !seen[$2]++ {print $1}' | tr '\n' ',' | sed 's/,$//')
            echo "    Node $node physical cores: $node_physical"
        done
        
        echo ""
        echo "  SMT/HT siblings (avoid these):"
        smt_cores=$(lscpu --parse=CPU,Core | grep -v '^#' | awk -F',' 'seen[$2]++ {print $1}' | tr '\n' ',' | sed 's/,$//')
        echo "    CPUs: $smt_cores"
    else
        # Fallback to numactl output
        numactl --hardware | grep "node.*cpus:" | sed 's/^/  /'
    fi
fi

# Governor
echo ""
echo -n "CPU Governor: "
if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
    if [ "$gov" = "performance" ]; then
        echo -e "${GREEN}$gov${NC}"
    else
        echo -e "${YELLOW}$gov${NC} (consider 'performance' for benchmarking)"
        ((warnings++))
    fi
else
    echo "N/A"
fi

# NUMA balancing
echo -n "NUMA Balancing: "
if [ -f /proc/sys/kernel/numa_balancing ]; then
    bal=$(cat /proc/sys/kernel/numa_balancing)
    if [ "$bal" = "0" ]; then
        echo -e "${GREEN}disabled${NC}"
    else
        echo -e "${YELLOW}enabled${NC} (should disable for benchmarking)"
        ((warnings++))
    fi
else
    echo "N/A"
fi

# Check for stray env vars
echo ""
echo -n "Thread env vars: "
thread_vars=$(env | grep -E 'OMP|BLAS|MKL|GOMP|KMP' || true)
if [ -z "$thread_vars" ]; then
    echo -e "${GREEN}clean${NC}"
else
    echo -e "${YELLOW}found:${NC}"
    echo "$thread_vars" | sed 's/^/  /'
    ((warnings++))
fi

# Summary
echo ""
echo "────────────────────────────────"
if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
    echo -e "${GREEN}✓ System ready for benchmarking${NC}"
    exit 0
elif [ $errors -eq 0 ]; then
    echo -e "${YELLOW}⚠ $warnings warnings (system usable but not optimal)${NC}"
    exit 0
else
    echo -e "${RED}✗ $errors errors, $warnings warnings${NC}"
    echo ""
    echo "To fix errors, run:"
    [ $errors -gt 0 ] && echo "  pip3 install --user -r requirements.txt"
    [ $errors -gt 0 ] && command -v numactl &> /dev/null || echo "  sudo apt install numactl  # or yum/dnf"
    exit 1
fi
