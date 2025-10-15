# HFT CPU Benchmarking Kit

A lightweight, config-driven harness for systematic llama.cpp performance testing on multi-core NUMA systems.

## Philosophy

- **YAML-driven:** All test scenarios live in declarative configs
- **Two modes:** Exploratory (fast, broad) → Deep (confirmatory, narrow)
- **Provenance:** Every run captures binary fingerprints, env, NUMA state
- **Reproducible:** Promotes winners from exploratory to deep testing

## Target Platform

Optimized for multi-core NUMA systems, particularly:
- AMD Threadripper (1950X, 2990WX, 3970X, etc.)
- AMD EPYC (dual-socket servers)
- Intel Xeon (multi-socket NUMA configurations)

Key features:
- Handles SMT (hyperthreading) correctly
- Configurable NUMA pinning strategies
- Detects physical core IDs automatically

## Quick Start

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure your test
cp configs/example-exploratory.yaml configs/mytest.yaml
# Edit: model path, llama-bench path

# 3. Run exploratory sweep
./run_bench.sh configs/mytest.yaml

# 4. Check results
cat reports/latest/summary.md

# 5. Promote winners to deep testing
./run_bench.sh reports/latest/promote.yaml
```

## Project Structure

```
hft-cpu-test/
├── configs/                      # Test definitions (YAML)
│   ├── example-exploratory.yaml  # Full exploratory template
│   ├── example-deep.yaml         # Deep testing template
│   └── minimal.yaml              # Quick-start minimal config
├── scripts/
│   ├── bench_harness.py          # Main orchestrator
│   ├── setup_builds.sh           # Optional: build multiple BLAS variants
│   └── check_system.sh           # System readiness checker
├── docs/
│   ├── QUICK_START.md            # Getting started guide
│   ├── CONFIG_SCHEMA.md          # Complete YAML reference
│   ├── PROVENANCE.md             # What's captured per run
│   ├── EXAMPLES.md               # Usage patterns
│   └── INDEX.md                  # Documentation index
├── reports/                      # Auto-generated (timestamped)
├── builds/                       # Optional: built binaries
├── run_bench.sh                  # Main entry point
└── requirements.txt              # Python dependencies
```

## Two-Mode Workflow

### Exploratory (Fast Discovery)
- Test 3-4 builds × 3 NUMA presets × key scenarios
- 2-3 repetitions per configuration
- Generates ranking + `promote.yaml` with top performers

### Deep (Validation)
- Test top 1-2 configurations from exploratory
- 7-10 repetitions with outlier rejection
- Statistical confidence intervals
- Production-ready recommendations

## NUMA Strategies

Example presets (adjust for your CPU topology):

- **vanilla:** No pinning (baseline)
- **all-cores:** All physical cores across NUMA nodes
- **single-node:** Single NUMA node only
- **balanced:** Cores spread evenly across nodes

**Important:** Use `lscpu --parse=CPU,Core,Node` to identify your physical core IDs. On many AMD systems they're sequential (0-15), on some Intel systems they're even-numbered (0,2,4...).

## Documentation

- **[Quick Start](docs/QUICK_START.md)** - Get running in 5 minutes
- **[Configuration Schema](docs/CONFIG_SCHEMA.md)** - Complete YAML reference
- **[Provenance](docs/PROVENANCE.md)** - System state capture details
- **[Examples](docs/EXAMPLES.md)** - Real-world usage patterns
- **[Documentation Index](docs/INDEX.md)** - Complete documentation guide

## System Requirements

- Python 3.7+
- `numactl` (for NUMA pinning)
- At least one `llama-bench` binary from llama.cpp
- Linux with NUMA support

## Adapting for Your CPU

When setting up on a new system:

1. Check your topology: `lscpu --parse=CPU,Core,Node` and `numactl --hardware`
2. Identify physical core IDs (vs SMT/HT siblings)
3. Update `--physcpubind` in config to use physical cores only
4. Test with `--dry-run` before executing
5. Run `./scripts/check_system.sh` to validate configuration

## License

MIT
