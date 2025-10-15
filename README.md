# HFT CPU Benchmarking Kit

A lightweight, config-driven harness for systematic llama.cpp performance testing on multi-core NUMA systems.

## Philosophy

- **YAML-driven:** All test scenarios live in declarative configs
- **Two modes:** Exploratory (fast, broad) → Deep (confirmatory, narrow)
- **Provenance:** Every run captures binary fingerprints, env, NUMA state
- **Reproducible:** Promotes winners from exploratory to deep testing

## Target Platform

Optimized for multi-core NUMA systems, including:
- AMD Threadripper (all models)
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
# Option A: Start from 1950X example (if you have one)
cp configs/example-1950x-exploratory.yaml configs/mytest.yaml

# Option B: Start from generic template
cp configs/example-exploratory.yaml configs/mytest.yaml
# Then: Edit model path, llama-bench path, CPU topology

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
├── configs/                           # Test definitions (YAML)
│   ├── minimal.yaml                   # Quick-start template
│   ├── example-exploratory.yaml       # Generic exploratory template
│   ├── example-deep.yaml              # Generic deep template
│   ├── example-1950x-exploratory.yaml # Real 1950X exploratory config
│   └── example-1950x-deep.yaml        # Real 1950X deep config
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
- Test many builds (4-6) with simple configurations
- Default parameters, basic NUMA strategies
- 2-3 repetitions per configuration
- Goal: Identify 2-3 winning builds
- Generates ranking in `summary.md`

### Deep (Parameter Sweep)
- Test top 2-3 builds from exploratory with parameter variations
- KV cache types (f16/f16, f8/f16, f16/f8, f8/f8)
- MLA variants (mla 2/3, flash attention, fused MoE)
- Batch/ubatch size combinations
- 3 repetitions (breadth over depth)
- Goal: Find optimal parameter settings for production

## NUMA Strategies

Example presets (adjust for your CPU topology):

- **vanilla:** No pinning (baseline)
- **all-cores:** All physical cores across NUMA nodes
- **single-node:** Single NUMA node only
- **balanced:** Cores spread evenly across nodes

**Important:** Use `lscpu --parse=CPU,Core,Node` to identify your physical core IDs. On many AMD systems they're sequential (0-15), on some Intel systems they're even-numbered (0,2,4...).

## Example Configurations

**Generic templates** (adapt to your CPU):
- `configs/minimal.yaml` - Quick start template
- `configs/example-exploratory.yaml` - Full exploratory template
- `configs/example-deep.yaml` - Deep validation template

**Real working examples** (AMD Threadripper 1950X):
- `configs/example-1950x-exploratory.yaml` - Complete exploratory config
- `configs/example-1950x-deep.yaml` - Deep validation config

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

## License & Credits

- Generated by Claude Sonnet 4.5 🤖
- Check-out the blog with experiments: https://nikro.me/
- Get in touch with us: https://humanfacetech.com/
