# Deep Mode - Parameter Sweep Explained

## What is Deep Mode?

**Deep mode is NOT "run the same test 10 times"**  
**Deep mode IS "torture-test winners with parameter variations"**

Think of it as a parameter search grid to optimize the winning builds from exploratory.

## The Two-Phase Workflow

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: EXPLORATORY                                    │
├─────────────────────────────────────────────────────────┤
│ • Many builds (6+)                                      │
│ • Simple configs (2-3 NUMA variations)                  │
│ • Default parameters                                    │
│ • Low repetitions (2-3)                                 │
│ • Goal: Find 2-3 winning builds                         │
│ • Time: Fast (~2 hours)                                 │
└─────────────────────────────────────────────────────────┘
                        ↓
         Pick top 2-3 builds manually
                        ↓
┌─────────────────────────────────────────────────────────┐
│ PHASE 2: DEEP (Parameter Sweep)                        │
├─────────────────────────────────────────────────────────┤
│ • Few builds (2-3 winners only)                         │
│ • Winning NUMA config                                   │
│ • MANY parameter variations:                            │
│   - KV cache types (f16/f16, f8/f16, f16/f8, f8/f8)    │
│   - MLA variants (baseline, mla2, mla3, ±fmoe)         │
│   - Batch sizes (various combos)                        │
│ • Same repetitions (3)                                  │
│ • Goal: Find optimal parameter settings                 │
│ • Time: Longer (6-12 hours depending on combinations)   │
└─────────────────────────────────────────────────────────┘
```

## Parameter Sweep Configuration

Deep mode uses the `parameter_sweep` section in YAML:

```yaml
mode: deep
repetitions: 3

parameter_sweep:
  
  # KV Cache Type Variations
  kv_cache:
    - name: "f16_f16"
      args: "-ctk f16 -ctv f16"  # Baseline (default)
    
    - name: "f8_f16"
      args: "-ctk f8 -ctv f16"   # Quantize K cache
    
    - name: "f16_f8"
      args: "-ctk f16 -ctv f8"   # Quantize V cache
    
    - name: "f8_f8"
      args: "-ctk f8 -ctv f8"    # Quantize both (max memory saving)
  
  # MLA (Multi-Layer Attention) Variants
  mla_variants:
    - name: "baseline"
      args: ""  # No optimization flags
    
    - name: "mla2_fa_fmoe"
      args: "-mla 2 -fa -fmoe"  # MLA level 2 + flash attention + fused MoE
    
    - name: "mla3_fa_fmoe"
      args: "-mla 3 -fa -fmoe"  # MLA level 3 (more aggressive)
    
    - name: "mla2_fa"
      args: "-mla 2 -fa"  # Without fused MoE
    
    - name: "mla3_fa"
      args: "-mla 3 -fa"  # Without fused MoE
  
  # Batch/Ubatch Size Variations
  batch_sizes:
    - name: "std_2048_512"
      args: "-b 2048 -ub 512"  # Default
    
    - name: "small_256_32"
      args: "-b 256 -ub 32"    # Small batches (low latency)
    
    - name: "small_256_64"
      args: "-b 256 -ub 64"
    
    - name: "small_256_128"
      args: "-b 256 -ub 128"
    
    - name: "mid_512_128"
      args: "-b 512 -ub 128"
    
    - name: "mid_1024_256"
      args: "-b 1024 -ub 256"
```

## Matrix Size Calculation

**Total tests = builds × NUMA_configs × metrics × kv_variants × mla_variants × batch_variants**

### Example 1: Starter (Reasonable)
```
2 builds × 1 NUMA × 3 metrics × 2 KV × 2 MLA × 3 batch
= 72 tests × 3 reps = 216 runs (~2-3 hours)
```

### Example 2: Comprehensive
```
2 builds × 1 NUMA × 3 metrics × 4 KV × 5 MLA × 7 batch
= 840 tests × 3 reps = 2,520 runs (~10-15 hours)
```

### Example 3: Exhaustive (Don't do this unless you have time!)
```
3 builds × 3 NUMA × 3 metrics × 4 KV × 5 MLA × 7 batch
= 3,780 tests × 3 reps = 11,340 runs (~30-40 hours)
```

## What Gets Tested

For each combination, the harness generates a test like:

```bash
numactl -N 0,1 -m 0,1 --physcpubind=0-15 \
  llama-bench \
    -m model.gguf \
    -t 16 \
    -ctk f8 -ctv f16 \      # ← KV cache variation
    -mla 2 -fa -fmoe \      # ← MLA variation
    -b 512 -ub 256 \        # ← Batch variation
    -pg 512,128 \           # ← Metric
    -o json
```

Every combination gets tested to find the optimal parameters.

## Tips for Running Deep Mode

### Start Small
Don't test all combinations at once! Start with:
- 2 builds (top winners)
- 1 NUMA config (the winning one)
- 2 KV variants (baseline + f8/f16)
- 2 MLA variants (baseline + mla2_fa)
- 3 batch sizes (std, small, mid)

This gives you ~36-72 tests to run first.

### Expand Gradually
Once you see which variations help:
1. Drop the variants that hurt performance
2. Add more granular tests around the winners
3. Test edge cases (very small/large batches)

### Watch the Output
The harness shows progress:
```
[1/72] ik_vanilla / optimal_f16_f16_baseline_std / pp512
  Rep 1: ...
  ✓ 91.23 t/s
```

The config name tells you what's being tested:
- `optimal` = NUMA config
- `f16_f16` = KV cache type
- `baseline` = MLA variant
- `std` = batch size

## Example Configs

See these files for working examples:

- `configs/qb-deep-starter.yaml` - **START HERE** (72 tests, ~2-3 hours)
- `configs/example-1950x-deep.yaml` - Comprehensive (288 tests, ~6-8 hours)
- `configs/example-deep-parameter-sweep.yaml` - Full example with all options

## Summary

| Mode | Purpose | Tests | Time | Output |
|------|---------|-------|------|--------|
| **exploratory** | Find winning builds | ~36 | ~2h | `promote.yaml` (ignore this, pick manually) |
| **deep** | Optimize parameters | ~72-840 | ~3-15h | `summary.md` with best params |

**Deep mode = breadth of parameters, not depth of repetitions!** 🎯
