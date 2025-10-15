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
- Type: `int` or `object`
- If `int`: Number of repetitions per test
- If `object`: Use `count` (int), `outlier_rejection` (bool), `confidence_interval` (float, optional)

**Recommended:**
- Exploratory: `2`
- Deep: `10`


### `output_dir` (required)
- Type: `string`
- Purpose: Base directory for reports


## Complete Examples

See `configs/example-exploratory.yaml` and `configs/example-deep.yaml` for full templates.

## Workflow

1. **Exploratory:** Broad sweep with `generate_promote: true`
2. Review `reports/latest/promote.yaml` for top performers
3. **Deep:** Run promoted config with 10 repetitions and outlier rejection
4. Select production settings from deep mode results

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
