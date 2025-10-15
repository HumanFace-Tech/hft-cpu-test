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
- Type: `list`
- Items: Build definition objects

#### Build Definition
```yaml
- name: unique-build-id
  path: /absolute/path/to/llama-bench
  provider: BLIS-OpenMP | OpenBLAS | MKL | none
  env:
    OMP_NUM_THREADS: "1"
    OPENBLAS_NUM_THREADS: "1"
    # Any env vars needed for this build
```

### `builds_select` (required)
- Type: `list[string]` or `"all"`
- Purpose: Which builds to actually run
- Example: `[blis-omp-znver1, openblas-znver1]`

### `pinning` (required)
- Type: `object`
- Fields:
  - `presets`: Dict of named pinning strategies
  - `select`: List of preset names to run

#### Pinning Preset

```yaml
preset-name:
  description: Human-readable explanation
  numactl: "numactl args" or null
  llama_numa: "numactl" or null  # Enables --numa flag
```

**Important:** Use EITHER `numactl` (process-level) OR `llama_numa` (app-level), not both.

**CPU Topology Note:** Use `lscpu --parse=CPU,Core,Node` to identify your physical core IDs. Specify only physical cores in `--physcpubind`, not SMT/HT siblings.

### `scenarios` (required)
- Type: `object`
- Fields:
  - `threads` (int): Fixed thread count
  - `batches` (list): Batch/ubatch combinations
  - `kv_cache` (list): KV cache type combinations
  - `attention` (list): Attention flag variants

#### Batch Definition
```yaml
- b: 256    # Batch size
  ub: 64    # Ubatch size
```

#### KV Cache Definition
```yaml
- type_k: f16 | q8_0 | q4_0
  type_v: f16 | q8_0
```

#### Attention Definition
```yaml
- flags: ["-mla", "2", "-fa", "-fmoe"]
  label: mla2-fa-fmoe  # For reports
```

### `metrics` (required)
- Type: `list`
- Items: Metric definition objects

#### Metric Definition
```yaml
- name: pp512           # Display name
  args: "-p 512 -n 0"   # llama-bench args
```

Common metrics:
- `pp512`: Prompt processing (512 tokens)
- `tg128`: Text generation (128 tokens)
- `mixed`: Combined (`-p 256 -n 512`)

### `repetitions` (required)
- Type: `object`
- Fields:
  - `count` (int): Number of repetitions per test
  - `outlier_rejection` (bool): Drop min/max (deep mode)
  - `confidence_interval` (float, optional): For CI calculation

**Recommended:**
- Exploratory: `count: 2`, `outlier_rejection: false`
- Deep: `count: 10`, `outlier_rejection: true`

### `output` (required)
- Type: `object`
- Fields:
  - `report_dir` (string): Base directory for reports
  - `timestamp` (bool): Create timestamped subdirs
  - `generate_promote` (bool): Create promote.yaml
  - `top_n` (int): How many to promote per metric

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
