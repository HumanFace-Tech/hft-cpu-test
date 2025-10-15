# Provenance Capture

Every benchmark run captures a complete snapshot of the execution environment to ensure reproducibility and explain anomalies.

**Purpose:** Debug performance variations, validate configurations, and enable cross-system comparisons on multi-core NUMA systems.

## What's Captured

### Binary Fingerprint
- **SHA256 hash** of the llama-bench executable
- Ensures you know exactly which binary produced results
- Detects accidental use of wrong build

### Linked Libraries
- Output of `ldd <binary>` filtered for BLAS/threading libs:
  - `libblis`
  - `libopenblas`
  - `libmkl_rt`
  - `libgomp` (GNU OpenMP)
  - `libiomp` (Intel OpenMP)
- Confirms which BLAS is actually loaded at runtime
- Catches LD_LIBRARY_PATH issues

### Environment Variables
- All threading control vars:
  - `OMP_NUM_THREADS`
  - `OPENBLAS_NUM_THREADS`
  - `BLIS_NUM_THREADS`
  - `MKL_NUM_THREADS`
  - `GOMP_CPU_AFFINITY`
  - `KMP_AFFINITY`
- Build-specific overrides from YAML config
- Detects unwanted inherited env vars

### NUMA Status
- Output of `numactl --show`
- Shows:
  - Available NUMA nodes
  - Current memory policy
  - CPU affinity mask
- Confirms pinning is applied correctly

### CPU Information
- Model name from `/proc/cpuinfo`
- Physical core count
- Helps explain performance on different machines

### Kernel Settings
- `kernel.numa_balancing` (0=off, 1=on)
  - **Should be OFF** for reproducible benchmarks
- `scaling_governor` (performance, powersave, etc.)
  - **Should be "performance"** for max throughput

## JSON Structure

Provenance is saved per test case in `reports/<timestamp>/raw/results.json`:

```json
{
  "test": { /* test definition */ },
  "provenance": {
    "timestamp": "2025-10-15T14:30:00",
    "binary": {
      "path": "/path/to/llama-bench",
      "sha256": "abc123...",
      "linked_libs": [
        "libblis.so.4 => /usr/lib/x86_64-linux-gnu/libblis.so.4",
        "libgomp.so.1 => /usr/lib/x86_64-linux-gnu/libgomp.so.1"
      ]
    },
    "environment": {
      "OMP_NUM_THREADS": "1",
      "BLIS_NUM_THREADS": "1"
    },
    "numa": {
      "available": true,
      "config": "policy: default\npreferred node: current\nphyscpubind: 0 2 4 6..."
    },
    "cpu": {
      "model": "AMD EPYC 7443P 24-Core Processor",
      "physical_cores": 24
    },
    "kernel": {
      "numa_balancing": "0",
      "cpu_governor": "performance"
    }
  },
  "runs": [ /* repetition results */ ]
}
```

## Why This Matters

### Debugging Performance Dips

**Scenario:** Performance dropped from 45 t/s to 38 t/s with identical configuration.

**Check provenance:**

1. Binary SHA256 different? → Wrong build
2. Governor changed to "powersave"? → System config drift
3. Different linked libs? → LD_LIBRARY_PATH changed
4. NUMA balancing enabled? → Kernel interfering with pinning

### Validating Runs

Before trusting benchmark results, verify:

- ✅ Linked libs match expected BLAS provider
- ✅ Thread env vars match configuration (OMP_NUM_THREADS=1, etc.)
- ✅ NUMA pinning applied correctly (check physcpubind shows your physical cores)
- ✅ Governor is "performance" (not powersave or ondemand)
- ✅ numa_balancing is "0" (disabled)

### Cross-System Comparison

Provenance enables understanding performance differences across systems:

- CPU model variations (Threadripper vs EPYC vs Xeon)
- Kernel version differences (5.x vs 6.x)
- BLAS library versions (OpenBLAS 0.3.20 vs 0.3.27)
- NUMA topology differences (2-node vs 4-node vs 8-node)

## Quick Check Script

```bash
# Extract provenance from latest run
jq '.[] | select(.test.build.name == "blis-omp-znver1") | .provenance' \
  reports/latest/raw/results.json | head -50
```

## Best Practices for NUMA Systems

### Pre-Benchmark System Configuration

1. **Disable NUMA balancing** (prevents kernel from moving memory):

   ```bash
   echo 0 | sudo tee /proc/sys/kernel/numa_balancing
   ```

2. **Set performance governor** (max CPU frequency):

   ```bash
   echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
   ```

3. **Verify clean environment** (no inherited thread vars):

   ```bash
   env | grep -E 'OMP|BLAS|MKL|GOMP|KMP'
   # Should be empty or only show your intended settings
   ```

4. **Verify NUMA topology:**

   ```bash
   numactl --hardware
   # Confirm your NUMA nodes and core distribution
   ```

5. **Optional - CPU isolation** (for dedicated systems):

   ```bash
   # Add to kernel command line: isolcpus=<your_physical_cores>
   cat /proc/cmdline | grep isolcpus
   ```
