# Documentation Index

Complete documentation for the HFT CPU Benchmarking Kit.

**Target Platforms:** Multi-core NUMA systems (AMD Threadripper, EPYC, Intel Xeon)

## Configuration Files

**Generic templates** (adapt to your CPU topology):
- `configs/minimal.yaml` - Quick start
- `configs/example-exploratory.yaml` - Full exploratory template
- `configs/example-deep.yaml` - Deep validation template

**Real working examples** (AMD Threadripper 1950X):
- `configs/example-1950x-exploratory.yaml` - Complete exploratory setup
- `configs/example-1950x-deep.yaml` - Deep validation setup

## Getting Started

1. **[Quick Start Guide](QUICK_START.md)** ⭐ START HERE
   - 5-minute setup for NUMA systems
   - CPU topology detection
   - System preparation steps
   - First benchmark run

2. **[Usage Examples](EXAMPLES.md)**
   - Real-world benchmarking scenarios
   - Single build tests
   - NUMA comparison strategies
   - Complete exploratory → deep workflow

## Reference

3. **[Configuration Schema](CONFIG_SCHEMA.md)**
   - Complete YAML reference
   - All configuration options
   - CPU topology detection guide

4. **[Provenance Capture](PROVENANCE.md)**
   - What's captured per run
   - Debugging performance issues
   - System validation checklist
   - Best practices for NUMA systems

## Quick Reference

### Essential Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# System check
./scripts/check_system.sh

# Run benchmark
./run_bench.sh configs/mytest.yaml

# Check results
cat reports/latest/summary.md
```

### Determining Physical Core IDs

Every CPU is different! Use these commands:

```bash
# See core mapping
lscpu --parse=CPU,Core,Node

# See NUMA layout
numactl --hardware
```

**Common patterns:**
- **AMD Threadripper/EPYC:** Sequential (0,1,2,3...)
- **Intel Xeon (some):** Even-numbered (0,2,4,6...)

### Example NUMA Bindings

```bash
# AMD Threadripper pattern (sequential 16 cores)
--physcpubind=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15

# Intel Xeon pattern (even-numbered 16 cores)
--physcpubind=0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30

# Always verify YOUR system first!
```

## Files by Purpose

### For First-Time Users

- `QUICK_START.md` - Get running fast
- `EXAMPLES.md` - Copy-paste configurations

### For Configuration

- `CONFIG_SCHEMA.md` - All YAML options
- CPU topology detection (in QUICK_START.md and EXAMPLES.md)

### For Debugging

- `PROVENANCE.md` - Understanding captured data
- `EXAMPLES.md` - System preparation section

## External Resources

- [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp)
- [numactl Documentation](https://linux.die.net/man/8/numactl)
- [AMD Threadripper Architecture](https://www.amd.com/en/products/processors/ryzen-threadripper)

## Adapting for Your System

When setting up on a new CPU:

1. Run `lscpu --parse=CPU,Core,Node` to understand your topology
2. Identify physical core IDs (vs SMT/HT siblings)
3. Update NUMA bindings in configs with your physical cores
4. Test thoroughly with `--dry-run` before executing
5. Run `./scripts/check_system.sh` to validate

## Support

For issues specific to:

- **CPU topology:** See topology detection in `QUICK_START.md`
- **NUMA pinning:** See `EXAMPLES.md` section 8
- **Configuration:** See `CONFIG_SCHEMA.md`
- **Performance issues:** See `PROVENANCE.md` best practices
- **Usage patterns:** See `EXAMPLES.md`
