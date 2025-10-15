# Usage Examples

Real-world benchmarking scenarios for multi-core NUMA systems.

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

## 2. Quick Single Build Test

Create `configs/single-build-test.yaml`:

```yaml
mode: exploratory
model:
  path: /data/models/qwen-q4.gguf
  name: qwen-q4

builds:
  - name: openblas-build
    path: /opt/llama.cpp/build/bin/llama-bench
    provider: OpenBLAS
    env:
      OPENBLAS_NUM_THREADS: "1"
      OMP_NUM_THREADS: "1"

builds_select: [openblas-build]

pinning:
  presets:
    vanilla:
      description: "No pinning (baseline)"
      numactl: null
      llama_numa: null
  select: [vanilla]

scenarios:
  threads: 16  # All 16 physical cores
  batches: [{b: 256, ub: 64}]
  kv_cache: [{type_k: f16, type_v: f16}]
  attention: [{flags: ["-fa"], label: "fa"}]

metrics:
  - {name: pp512, args: "-p 512 -n 0"}
  - {name: tg128, args: "-p 0 -n 128"}

repetitions:
  count: 2
  outlier_rejection: false

output:
  report_dir: reports
  timestamp: true
  generate_promote: false
  top_n: 1
```

Run it:

```bash
./run_bench.sh configs/single-build-test.yaml
```

## 3. Compare NUMA Pinning Strategies

Test vanilla vs pinned performance (example for 16-core system):

```yaml
# Same as example 2, but update pinning section:

pinning:
  presets:
    vanilla:
      description: "No pinning (baseline)"
      numactl: null
      llama_numa: null
    
    all-cores:
      description: "All physical cores (both NUMA nodes)"
      # IMPORTANT: Replace with YOUR physical core IDs from lscpu
      numactl: "-N 0,1 -m 0,1 --physcpubind=<your_physical_cores>"
      llama_numa: null
    
    single-node:
      description: "Single NUMA node only"
      # IMPORTANT: Replace with YOUR node 0 physical cores
      numactl: "-N 0 -m 0 --physcpubind=<your_node0_cores>"
      llama_numa: null
  
  select:
    - vanilla
    - all-cores
    - single-node
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
# Step 1: Run exploratory with 3 builds
./run_bench.sh configs/mybox-exploratory.yaml
# Takes ~20 minutes

# Step 2: Check results
cat reports/latest/summary.md
less reports/latest/raw/results.json

# Step 3: Auto-generated promote file
cat reports/latest/promote.yaml

# Step 4: Run deep test on winners
./run_bench.sh reports/latest/promote.yaml
# Takes ~40 minutes (10 reps × multiple configs)

# Step 5: Final results
cat reports/latest/summary.md
```

## 7. Custom Deep Config (Manual Winner Selection)

After reviewing exploratory results, create `configs/production-deep.yaml`:

```yaml
mode: deep

model:
  path: /data/models/qwen-14b-q4.gguf
  name: qwen-14b-q4

builds:
  - name: blis-omp
    path: /opt/builds/blis-omp/llama-bench
    provider: BLIS-OpenMP
    env:
      OMP_NUM_THREADS: "1"
      BLIS_NUM_THREADS: "1"

builds_select: [blis-omp]  # Winner from exploratory

pinning:
  presets:
    winner:
      description: "Best performer from exploratory"
      # REPLACE with your winning physical core configuration
      numactl: "-N 0,1 -m 0,1 --physcpubind=<your_physical_cores>"
      llama_numa: null
  select: [winner]

scenarios:
  threads: 16  # Adjust to your core count
  batches: [{b: 256, ub: 96}]  # Best from exploratory
  kv_cache: [{type_k: q8_0, type_v: f16}]  # Best from exploratory
  attention: [{flags: ["-mla", "3", "-fa"], label: "mla3-fa"}]  # Best from exploratory

metrics:
  - {name: pp512, args: "-p 512 -n 0"}
  - {name: tg128, args: "-p 0 -n 128"}
  - {name: mixed, args: "-p 256 -n 512"}

repetitions:
  count: 10
  outlier_rejection: true
  confidence_interval: 0.95

output:
  report_dir: reports
  timestamp: true
  generate_promote: false
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
