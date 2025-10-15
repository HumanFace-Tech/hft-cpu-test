# Quick Start Guide

Get benchmarking in 5 minutes on multi-core NUMA systems.

## Prerequisites

- Python 3.7+
- `numactl` (for NUMA pinning)
- At least one llama.cpp build with `llama-bench` binary
- Multi-core CPU with NUMA (AMD Threadripper, EPYC, Intel Xeon, etc.)

## Step 1: Install Dependencies

```bash
cd /var/www/hft-cpu-test
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Create Your Config

Start with the minimal template:

```bash
cp configs/minimal.yaml configs/mytest.yaml
```

Edit `configs/mytest.yaml`:

1. **Set model path:**
   ```yaml
   model:
     path: /data/models/Qwen2.5-14B-Q4_K_M.gguf
     name: Qwen2.5-14B-Q4_K_M
   ```

2. **Set build path:**
   ```yaml
   builds:
     - name: my-build
       path: /opt/llama.cpp/build/bin/llama-bench
       provider: OpenBLAS  # or BLIS-OpenMP, MKL, none
       env:
         OPENBLAS_NUM_THREADS: "1"
         OMP_NUM_THREADS: "1"
   
   builds_select:
     - my-build
   ```

3. **NUMA pinning (adjust for your CPU):**
   
   First, check your CPU topology:
   ```bash
   lscpu --parse=CPU,Core,Node
   numactl --hardware
   ```
   
   Then update the `physcpubind` values with your **physical core IDs** (not SMT/HT siblings):
   ```yaml
   pinning:
     presets:
       all-cores:
         numactl: "-N 0,1 -m 0,1 --physcpubind=<your_physical_core_ids>"
   ```

## Step 3: Verify System Configuration

Check your system is ready:

```bash
./scripts/check_system.sh
```

Ensure CPU governor is set to "performance":

```bash
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

Disable NUMA balancing for reproducible results:

```bash
echo 0 | sudo tee /proc/sys/kernel/numa_balancing
```

## Step 4: Dry Run

Test your config without executing benchmarks:

```bash
./run_bench.sh configs/mytest.yaml --dry-run
```

This shows the test matrix that will be executed.

## Step 5: Run Exploratory

```bash
./run_bench.sh configs/mytest.yaml
```

Results:
- Runs all test combinations (2-3 reps each)
- Takes ~10-30 minutes depending on matrix size
- Outputs to `reports/<timestamp>-exploratory/`

## Step 6: Review Results

```bash
cat reports/latest/summary.md
```

Look for:
- Top performers per metric (pp512, tg128, mixed)
- Consistency across repetitions
- Any obvious outliers or anomalies

## Step 7: Run Deep Testing

Use the auto-generated promote file with winners:

```bash
./run_bench.sh reports/latest/promote.yaml
```

Deep testing provides:
- 10 repetitions (vs 2 in exploratory)
- Outlier rejection (drop min/max)
- Statistical confidence intervals
- Production-ready recommendations

## Step 8: Select Production Settings

From `reports/latest/summary.md`, identify the winning configuration:

```text
Winner: blis-omp-znver1 / all-16-cores / b=256,ub=96 / kv=q8_0 / mla3-fa
  - pp512: 145.3 t/s ±2.1
  - tg128: 47.8 t/s ±0.8
  - mixed: 52.1 t/s ±1.2
```

## Troubleshooting

### "numactl: command not found"
```bash
sudo apt-get install numactl  # Debian/Ubuntu
sudo yum install numactl      # RHEL/CentOS
```

### "Could not parse output"
llama-bench output format may have changed. Check:
```bash
/path/to/llama-bench --help
/path/to/llama-bench -m model.gguf -p 10 -n 0  # Quick test
```

### Low performance across all tests
Check:
```bash
# CPU governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# Should be "performance"

# NUMA balancing
cat /proc/sys/kernel/numa_balancing
# Should be "0"

# Verify binary is optimized
file /path/to/llama-bench
ldd /path/to/llama-bench | grep -E 'blas|omp'
```

## Next Steps

- Read `docs/CONFIG_SCHEMA.md` for full YAML reference
- Read `docs/PROVENANCE.md` to understand captured data
- Customize scenarios for your workload
- Use `scripts/setup_builds.sh` to create multiple builds

## Complete Workflow Example

```bash
# 1. One-time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. System prep
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
echo 0 | sudo tee /proc/sys/kernel/numa_balancing

# 3. Create config
cp configs/minimal.yaml configs/prod-test.yaml
nano configs/prod-test.yaml  # Edit model/build paths and CPU bindings

# 4. Verify setup
./scripts/check_system.sh
./run_bench.sh configs/prod-test.yaml --dry-run

# 5. Exploratory (fast sweep)
./run_bench.sh configs/prod-test.yaml
# ~15-20 minutes

# 6. Review winners
cat reports/latest/summary.md
cat reports/latest/promote.yaml

# 7. Deep test winners
./run_bench.sh reports/latest/promote.yaml
# ~30-40 minutes

# 8. Final decision
cat reports/latest/summary.md
# Apply winning config to production!
```

## Determining Your CPU Topology

Every CPU is different. Here's how to configure correctly:

### Step 1: Check Topology

```bash
lscpu --parse=CPU,Core,Node
```

Look for the pattern:
- **Physical cores:** Unique "Core" numbers (use these!)
- **SMT/HT siblings:** Duplicate "Core" numbers (skip these)

### Step 2: Common Patterns

**AMD Threadripper/EPYC (sequential):**
- Physical cores: 0, 1, 2, 3, ... N
- SMT siblings: N+1, N+2, ... 2N
- Use: `--physcpubind=0,1,2,3,...,N`

**Some Intel Xeon (even-numbered):**
- Physical cores: 0, 2, 4, 6, ... 2N
- SMT siblings: 1, 3, 5, 7, ... 2N+1
- Use: `--physcpubind=0,2,4,6,...,2N`

### Step 3: Update Config

Replace the `--physcpubind` values in your YAML with your physical core IDs.
