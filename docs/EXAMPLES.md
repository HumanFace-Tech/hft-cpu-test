# Usage Examples

Real-world benchmarking scenarios for multi-core NUMA systems.

**Note:** For complete working examples specific to AMD Threadripper 1950X, see:
- `configs/example-1950x-exploratory.yaml` - Full exploratory configuration
- `configs/example-1950x-deep.yaml` - Deep validation configuration

These examples below use generic placeholders. Adapt them to your CPU topology.

## 1. First Time Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy minimal config template
cp configs/minimal.yaml configs/mytest.yaml

# Edit paths and CPU topology
nano configs/mytest.yaml

# Test the config without running
./run_bench.sh configs/mytest.yaml --dry-run
```

builds:
builds_select: [openblas-build]
pinning:

## 2. Quick Single Build Test

Create `configs/single-build-test.yaml`:

```yaml
mode: exploratory
model_path: /data/models/qwen-q4.gguf
model_info: qwen-q4
builds:
  openblas-build:
    binary: /opt/llama.cpp/build/bin/llama-bench
    label: OpenBLAS
    env:
      OPENBLAS_NUM_THREADS: "1"
      OMP_NUM_THREADS: "1"

  - openblas-build
test_matrix:
  - name: all_cores
    numactl: "--physcpubind=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15"
    env:
      OMP_NUM_THREADS: "16"
    extra_args: "-t 16"
metrics:
  - pp512
  - tg128
  - mixed
output_dir: ./reports
repetitions: 2
```

Run it:

```bash
./run_bench.sh configs/single-build-test.yaml
```
pinning:

## 3. Compare NUMA Pinning Strategies

Test vanilla vs pinned performance (example for 16-core system):

```yaml
mode: exploratory
model_path: /data/models/qwen-q4.gguf
model_info: qwen-q4
builds:
  openblas-build:
    binary: /opt/llama.cpp/build/bin/llama-bench
    label: OpenBLAS
    env:
      OPENBLAS_NUM_THREADS: "1"
      OMP_NUM_THREADS: "1"
builds_select:
  - openblas-build
test_matrix:
  - name: vanilla
    numactl: null
    env:
      OMP_NUM_THREADS: "16"
    extra_args: "-t 16"
  - name: all_cores
    numactl: "--physcpubind=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15"
    env:
      OMP_NUM_THREADS: "16"
    extra_args: "-t 16"
  - name: single_node
    numactl: "--physcpubind=0,1,2,3,4,5,6,7"
    env:
      OMP_NUM_THREADS: "8"
    extra_args: "-t 8"
metrics:
  - pp512
  - tg128
  - mixed
output_dir: ./reports
repetitions: 2
```

**Note:** Use `lscpu --parse=CPU,Core,Node` to find your physical core IDs first!

## 4. Test Multiple Batch Sizes

```yaml
scenarios:
  threads: 16
  batches:
    - {b: 256, ub: 32}
    - {b: 256, ub: 64}
    - {b: 256, ub: 96}
    - {b: 512, ub: 128}
  # ... rest same
```

## 5. KV Cache Comparison

```yaml
scenarios:
  threads: 16
  batches: [{b: 256, ub: 64}]
  kv_cache:
    - {type_k: f16, type_v: f16}    # Baseline
    - {type_k: q8_0, type_v: f16}   # Quantized key
    - {type_k: q8_0, type_v: q8_0}  # Both quantized
  attention: [{flags: ["-fa"], label: "fa"}]
```

## 6. Full Exploratory → Deep Workflow

```bash
# Step 1: Run exploratory with multiple builds
./run_bench.sh configs/mybox-exploratory.yaml
# Takes ~20 minutes, tests many builds with simple configs

# Step 2: Check results and identify top 2-3 builds
cat reports/latest/summary.md

# Step 3: Create deep config for parameter sweep
cp configs/example-deep.yaml configs/mybox-deep.yaml
nano configs/mybox-deep.yaml
# - Set builds_select to your top 2-3 winners
# - Configure parameter_sweep (KV cache, MLA, batch sizes)

# Step 4: Run deep parameter sweep
./run_bench.sh configs/mybox-deep.yaml
# Takes ~3-8 hours depending on parameter combinations

# Step 5: Final results with optimal parameters
cat reports/latest/summary.md
```

## 7. Deep Mode - Parameter Sweep

After reviewing exploratory results, create `configs/production-deep.yaml`:

```yaml
mode: deep
repetitions: 3  # Breadth over depth

model_path: /data/models/qwen-14b-q4.gguf
model_info: qwen-14b-q4

builds:
  blis-omp:
    binary: /opt/builds/blis-omp/llama-bench
    label: BLIS-OpenMP
    env:
      OMP_NUM_THREADS: "1"
      BLIS_NUM_THREADS: "1"

builds_select: [blis-omp]  # Winner from exploratory

test_matrix:
  - name: optimal
    numactl: "-N 0,1 -m 0,1 --physcpubind=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15"
    env:
      OMP_NUM_THREADS: "16"
    extra_args: "-t 16"

metrics:
  - pp512
  - tg128
  - mixed

output_dir: ./reports

# Parameter sweep - test combinations
parameter_sweep:
  kv_cache:
    - name: f16_f16
      args: "-ctk f16 -ctv f16"  # Baseline
    - name: f8_f16
      args: "-ctk f8 -ctv f16"   # Quantized K
  
  mla_variants:
    - name: baseline
      args: ""
    - name: mla2_fa
      args: "-mla 2 -fa"
    - name: mla3_fa_fmoe
      args: "-mla 3 -fa -fmoe"
  
  batch_sizes:
    - name: std
      args: "-b 2048 -ub 512"
    - name: small
      args: "-b 256 -ub 128"
    - name: mid
      args: "-b 512 -ub 256"

# This generates: 1 build × 1 NUMA × 3 metrics × 2 KV × 3 MLA × 3 batch
#                = 54 tests × 3 reps = 162 runs
```

## 8. Understanding Your CPU Topology

```bash
# See your CPU layout
lscpu --parse=CPU,Core,Node

# Look for the pattern in the output:
# - Each unique Core number = physical core (use these)
# - Duplicate Core numbers = SMT/HT siblings (skip these)

# Detailed NUMA info
numactl --hardware

# Example AMD Threadripper pattern:
# node 0 cpus: 0 1 2 3 4 5 6 7 16 17 18 19 20 21 22 23
# node 1 cpus: 8 9 10 11 12 13 14 15 24 25 26 27 28 29 30 31
# Physical cores: 0-15 (sequential)
# SMT siblings: 16-31

# Example Intel Xeon pattern (some models):
# node 0 cpus: 0 2 4 6 8 10 12 14 1 3 5 7 9 11 13 15
# Physical cores: 0,2,4,6,8,10,12,14 (even numbers)
# SMT siblings: 1,3,5,7,9,11,13,15 (odd numbers)

# Your pattern will depend on your specific CPU!
```

## 9. System Preparation (Required Before Benchmarking)

```bash
# 1. Set performance mode
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 2. Disable NUMA balancing
echo 0 | sudo tee /proc/sys/kernel/numa_balancing

# 3. Verify settings
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor  # Should show: performance
cat /proc/sys/kernel/numa_balancing  # Should show: 0

# 4. Clean environment (check for stray thread variables)
env | grep -E 'OMP|BLAS|MKL|GOMP|KMP'
# Should be empty unless you've explicitly set them

# 5. Use the system checker
./scripts/check_system.sh
```

## 10. Analyzing Results

```bash
# Quick summary
cat reports/latest/summary.md

# Full JSON data
jq '.' reports/latest/raw/results.json | less

# Extract specific build's provenance
jq '.[] | select(.test.build.name == "blis-omp") | .provenance' \
  reports/latest/raw/results.json

# Find top performer for pp512
jq -r '.[] | 
  select(.test.metric.name == "pp512") | 
  [.test.build.name, .test.pinning[0], (.runs | map(.performance.tokens_per_sec) | add / length)] | 
  @tsv' reports/latest/raw/results.json | sort -k3 -nr | head -5

# Compare two runs
diff -u reports/2025-10-15-140000-exploratory/summary.md \
        reports/2025-10-15-153000-deep/summary.md
```

## 11. Building Multiple Variants (Optional)

```bash
# Use the setup script
cd /var/www/hft-cpu-test
./scripts/setup_builds.sh

# This creates:
# builds/cpu-only-znver1/llama-bench
# builds/openblas-znver1/llama-bench
# builds/blis-omp-znver1/llama-bench
# (etc.)

# Then reference them in your config:
# builds:
#   - name: blis-omp
#     path: /var/www/hft-cpu-test/builds/blis-omp-znver1/llama-bench
#     ...
```
