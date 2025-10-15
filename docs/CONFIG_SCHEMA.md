# Configuration Schema

Complete reference for benchmark YAML configuration files.

**Target Platforms:** Multi-core NUMA systems (AMD Threadripper, EPYC, Intel Xeon)

## Top-Level Fields

### `mode` (required)
- Type: `string`
- Values: `exploratory` | `deep`
- Purpose: Determines test strategy

### `model` (required)
- Type: `object`
- Fields:
  - `path` (string): Absolute path to GGUF model
  - `name` (string): Display name for reports


### `builds` (required)
- Type: `dict`
- Keys: unique build names
- Values: Build definition objects

#### Build Definition
```yaml
builds:
  my-build:
    binary: /absolute/path/to/llama-bench
    label: OpenBLAS
    env:
      OMP_NUM_THREADS: "1"
      OPENBLAS_NUM_THREADS: "1"
      # Any env vars needed for this build
```


### `builds_select` (required)
- Type: `list[string]` or `"all"`
- Purpose: Which builds to actually run
- Example: `[my-build, openblas-build]`


### `test_matrix` (required)
- Type: `list`
- Items: Test configuration objects

#### Test Matrix Entry
```yaml
test_matrix:
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
```

**CPU Topology Note:** Use `lscpu --parse=CPU,Core,Node` to identify your physical core IDs. Specify only physical cores in `--physcpubind`, not SMT/HT siblings.


### `metrics` (required)
- Type: `list[string]` or `list[dict]`
- Items: Metric names or metric definition objects

#### Metric Definition
```yaml
metrics:
  - pp512
  - tg128
  - mixed
# or
metrics:
  - name: pp512
    args: "-p 512 -n 0"
  - name: tg128
    args: "-p 0 -n 128"
  - name: mixed
    args: "-p 512 -n 128"
```

Common metrics:
- `pp512`: Prompt processing (512 tokens)
- `tg128`: Text generation (128 tokens)
- `mixed`: Combined (`-p 512 -n 128`)


### `repetitions` (required)
- Type: `int`
- Purpose: Number of repetitions per test

**Recommended:**
- Exploratory: `2-3` (fast discovery)
- Deep: `3` (breadth over depth)


### `output_dir` (required)
- Type: `string`
- Purpose: Base directory for reports


### `parameter_sweep` (deep mode only)
- Type: `object`
- Purpose: Define parameter variations for deep mode testing
- Fields:
  - `kv_cache`: List of KV cache type variations
  - `mla_variants`: List of MLA/attention optimization variants
  - `batch_sizes`: List of batch/ubatch size combinations

#### Parameter Sweep Example
```yaml
parameter_sweep:
  kv_cache:
    - name: f16_f16
      args: "-ctk f16 -ctv f16"  # Baseline
    - name: f8_f16
      args: "-ctk f8 -ctv f16"   # Quantized K cache
  
  mla_variants:
    - name: baseline
      args: ""                   # No optimization
    - name: mla2_fa_fmoe
      args: "-mla 2 -fa -fmoe"  # MLA + flash attn + fused MoE
  
  batch_sizes:
    - name: std
      args: "-b 2048 -ub 512"   # Default
    - name: small
      args: "-b 256 -ub 128"    # Lower latency
```

**Deep mode generates cross-product:** builds × test_matrix × metrics × kv_cache × mla_variants × batch_sizes


## Complete Examples

See `configs/example-exploratory.yaml` and `configs/example-deep.yaml` for full templates.

## Workflow

1. **Exploratory:** Test many builds with simple configs (2-3 reps)
2. Review `reports/latest/summary.md` for top 2-3 builds
3. **Deep:** Create parameter sweep config testing winners with variations
4. Run deep config to find optimal KV cache, MLA, batch settings
5. Select production settings from deep mode results

## CPU Topology Detection

Before running, determine your physical core IDs:

```bash
lscpu --parse=CPU,Core,Node
numactl --hardware
```

**Common patterns:**

- **AMD Threadripper/EPYC:** Physical cores are sequential (0,1,2,3...)
- **Intel Xeon (some):** Physical cores are even-numbered (0,2,4,6...)
- **Always check:** Your system may differ!

Update `--physcpubind` in configs with **only** physical core IDs.
