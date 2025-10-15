#!/usr/bin/env python3
"""
HFT CPU Benchmarking Harness

Orchestrates llama.cpp benchmarks with:
- YAML-driven configuration
- Exploratory → Deep workflow
- Full provenance capture
- NUMA/threading control
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from tabulate import tabulate


class ProvenanceCollector:
    """Captures system state and binary fingerprints."""
    
    @staticmethod
    def binary_sha256(path: str) -> str:
        """Compute SHA256 of binary."""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    @staticmethod
    def linked_blas(path: str) -> List[str]:
        """Extract BLAS/threading libraries from ldd output."""
        try:
            result = subprocess.run(
                ['ldd', path],
                capture_output=True,
                text=True,
                check=True
            )
            libs = []
            patterns = ['blis', 'openblas', 'mkl', 'gomp', 'iomp']
            for line in result.stdout.splitlines():
                if any(p in line.lower() for p in patterns):
                    libs.append(line.strip())
            return libs
        except Exception as e:
            return [f"Error getting ldd: {e}"]
    
    @staticmethod
    def numa_status() -> Dict[str, Any]:
        """Capture NUMA configuration."""
        try:
            result = subprocess.run(
                ['numactl', '--show'],
                capture_output=True,
                text=True,
                check=True
            )
            return {
                'available': True,
                'config': result.stdout.strip()
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }
    
    @staticmethod
    def cpu_info() -> Dict[str, str]:
        """Extract CPU model and core count."""
        info = {}
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read()
                model_match = re.search(r'model name\s*:\s*(.+)', content)
                if model_match:
                    info['model'] = model_match.group(1).strip()
                
                # Count physical cores
                phys_ids = set(re.findall(r'physical id\s*:\s*(\d+)', content))
                cores_per_pkg = set(re.findall(r'cpu cores\s*:\s*(\d+)', content))
                if phys_ids and cores_per_pkg:
                    info['physical_cores'] = len(phys_ids) * int(list(cores_per_pkg)[0])
        except Exception as e:
            info['error'] = str(e)
        return info
    
    @staticmethod
    def kernel_settings() -> Dict[str, str]:
        """Check relevant kernel tunables."""
        settings = {}
        paths = {
            'numa_balancing': '/proc/sys/kernel/numa_balancing',
            'cpu_governor': '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'
        }
        for name, path in paths.items():
            try:
                with open(path, 'r') as f:
                    settings[name] = f.read().strip()
            except Exception:
                settings[name] = 'N/A'
        return settings
    
    @classmethod
    def collect_all(cls, binary_path: str, env: Dict[str, str]) -> Dict[str, Any]:
        """Gather complete provenance snapshot."""
        return {
            'timestamp': datetime.now().isoformat(),
            'binary': {
                'path': binary_path,
                'sha256': cls.binary_sha256(binary_path),
                'linked_libs': cls.linked_blas(binary_path)
            },
            'environment': env,
            'numa': cls.numa_status(),
            'cpu': cls.cpu_info(),
            'kernel': cls.kernel_settings()
        }


class BenchmarkRunner:
    """Executes individual benchmark runs with full control."""
    
    def __init__(self, config: Dict[str, Any], report_dir: Path):
        self.config = config
        self.report_dir = report_dir
        self.raw_dir = report_dir / 'raw'
        self.raw_dir.mkdir(parents=True, exist_ok=True)
    
    def build_command(
        self,
        binary: str,
        model: str,
        metric_args: str,
        pinning: Dict[str, Any]
    ) -> Tuple[List[str], Dict[str, str]]:
        """Construct the benchmark command."""
        
        # Base command with metric args + JSON output format
        cmd_parts = [binary, '-m', model] + metric_args.split()
        
        # Force JSON output for reliable parsing
        if '-o' not in metric_args and '--output' not in metric_args:
            cmd_parts.extend(['-o', 'json'])
        
        # Add llama-bench internal repetitions if configured
        # Default is 5 in llama-bench, but user can override
        if 'llama_bench_reps' in self.config:
            cmd_parts.extend(['-r', str(self.config['llama_bench_reps'])])
        
        # NUMA handling
        env = os.environ.copy()
        if pinning.get('numactl'):
            # Prepend numactl command
            cmd_parts = ['numactl'] + pinning['numactl'].split() + cmd_parts
        elif pinning.get('llama_numa'):
            # Use llama.cpp's --numa flag
            cmd_parts.extend(['--numa', pinning['llama_numa']])
        
        return cmd_parts, env
    
    def run_single(
        self,
        build: Dict[str, Any],
        pinning: Dict[str, Any],
        metric: Dict[str, str],
        rep: int,
        extra_env: Optional[Dict[str, str]] = None,
        extra_args: str = ''
    ) -> Optional[Dict[str, Any]]:
        """Execute a single benchmark iteration."""
        
        # Get model path - handle both 'model.path' and 'model_path'
        if 'model' in self.config and isinstance(self.config['model'], dict):
            model_path = self.config['model']['path']
        else:
            model_path = self.config.get('model_path', '')
        
        cmd, env = self.build_command(
            build.get('binary') or build.get('path', ''),
            model_path,
            metric['args'],
            pinning
        )
        
        # Add extra args if provided (e.g., -t 16)
        if extra_args:
            cmd.extend(extra_args.split())
        
        # Apply test-specific env vars (e.g., OMP_NUM_THREADS)
        if extra_env:
            env.update(extra_env)
        
        # Apply build-specific env overrides
        if 'env' in build:
            env.update(build['env'])
        
        print(f"  Rep {rep}: {' '.join(cmd)}")
        
        try:
            start_time = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
                env=env
            )
            elapsed = time.time() - start_time
            
            if result.returncode != 0:
                print(f"    ❌ Failed (exit {result.returncode})")
                print(f"    stderr: {result.stderr[:200]}")
                return None
            
            # Parse output (llama-bench produces specific format)
            perf = self.parse_bench_output(result.stdout)
            if not perf:
                print(f"    ⚠️  Could not parse output")
                return None
            
            print(f"    ✓ {perf.get('tokens_per_sec', 'N/A')} t/s")
            
            return {
                'success': True,
                'elapsed': elapsed,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'performance': perf
            }
            
        except subprocess.TimeoutExpired:
            print(f"    ⏱️  Timeout")
            return None
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            return None
    
    @staticmethod
    def parse_bench_output(output: str) -> Optional[Dict[str, float]]:
        """Extract performance metrics from llama-bench JSON output.
        
        Handles IK llama.cpp fork's banner pollution which appears as:
        [
        ======================================= HAVE_FANCY_SIMD is NOT defined
          {
            ...
          }
        ]
        """
        try:
            # IK fork prints banner BETWEEN '[' and '{', so we need to clean it out
            # Strategy: Find '[', then find first '{', then reconstruct as '[ {' + rest
            
            bracket_start = output.find('[')
            if bracket_start == -1:
                # Try standalone object
                brace_start = output.find('{')
                if brace_start != -1:
                    output = output[brace_start:]
                else:
                    return None
            else:
                # Found '[', now find the first '{'
                brace_start = output.find('{', bracket_start)
                if brace_start == -1:
                    return None
                
                # Find the matching ']' at the end
                bracket_end = output.rfind(']')
                if bracket_end == -1:
                    return None
                
                # Reconstruct clean JSON: [ + content from { to ] (inclusive)
                output = '[' + output[brace_start:bracket_end+1]
            
            # Parse the cleaned JSON
            data = json.loads(output)
            
            # Could be a single result or array of results
            if isinstance(data, list):
                result = data[0] if data else {}
            else:
                result = data
            
            if not result:
                return None
            
            perf = {}
            
            # Extract throughput (tokens per second)
            if 'avg_ts' in result:
                perf['tokens_per_sec'] = result['avg_ts']
            
            # Extract test type info
            test_type = result.get('test', '')
            if 'pp' in test_type:
                perf['pp_tokens_per_sec'] = result.get('avg_ts', 0)
            elif 'tg' in test_type:
                perf['tg_tokens_per_sec'] = result.get('avg_ts', 0)
            
            # Store additional useful metrics
            perf['avg_ns'] = result.get('avg_ns', 0)
            perf['stddev_ts'] = result.get('stddev_ts', 0)
            perf['n_prompt'] = result.get('n_prompt', 0)
            perf['n_gen'] = result.get('n_gen', 0)
            
            return perf if perf else None
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # If JSON parsing fails, return None (caller will handle)
            return None


class BenchmarkOrchestrator:
    """Main orchestrator for the benchmark suite."""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.mode = self.config['mode']
        self.results = []
        
        # Setup report directory
        timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
        report_name = f"{timestamp}-{self.mode}"
        
        # Handle both 'output_dir' (top-level) and 'output.report_dir' (nested) formats
        if 'output_dir' in self.config:
            report_base = Path(self.config['output_dir'])
        elif 'output' in self.config:
            report_base = Path(self.config['output']['report_dir'])
        else:
            report_base = Path('./reports')  # Default fallback
            
        self.report_dir = report_base / report_name
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        # Create symlink to latest
        latest_link = report_base / 'latest'
        if latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(report_name)
        
        print(f"📊 Report directory: {self.report_dir}")
    
    def get_selected_builds(self) -> List[Dict[str, Any]]:
        """Filter builds based on selection criteria."""
        all_builds = self.config['builds']
        selected = self.config.get('builds_select', [])
        
        # Handle dict format (key: {binary: ..., label: ...})
        if isinstance(all_builds, dict):
            builds_list = [
                {'name': name, **details} 
                for name, details in all_builds.items()
            ]
            
            if selected == 'all' or selected == ['all']:
                return builds_list
            
            return [b for b in builds_list if b['name'] in selected]
        
        # Handle list format ([{name: ..., binary: ..., label: ...}])
        if selected == 'all' or selected == ['all']:
            return all_builds
        
        return [b for b in all_builds if b['name'] in selected]
    
    def generate_test_matrix(self) -> List[Dict[str, Any]]:
        """Create the full test matrix from test_matrix config section."""
        matrix = []
        builds = self.get_selected_builds()
        
        if 'test_matrix' not in self.config:
            raise ValueError("Config must have 'test_matrix' section")
        
        test_configs = self.config['test_matrix']
        metrics = self.config.get('metrics', ['pp512', 'tg128', 'mixed'])
        
        # Parse metrics into dict format if they're strings
        parsed_metrics = []
        for m in metrics:
            if isinstance(m, str):
                # Convert "pp512" to proper metric dict
                if m == 'pp512':
                    parsed_metrics.append({'name': 'pp512', 'args': '-p 512 -n 0'})
                elif m == 'tg128':
                    parsed_metrics.append({'name': 'tg128', 'args': '-p 0 -n 128'})
                elif m == 'mixed':
                    # Use -pg for true mixed workload (prompt + generation together)
                    parsed_metrics.append({'name': 'mixed', 'args': '-pg 512,128'})
            else:
                parsed_metrics.append(m)
        
        for build in builds:
            for test_config in test_configs:
                # Convert test_config to pinning format
                pinning = {
                    'numactl': test_config.get('numactl'),
                    'llama_numa': test_config.get('llama_numa')
                }
                
                for metric in parsed_metrics:
                    test_case = {
                        'build': build,
                        'pinning': (test_config['name'], pinning),
                        'metric': metric,
                        'env': test_config.get('env', {}),
                        'extra_args': test_config.get('extra_args', '')
                    }
                    matrix.append(test_case)
        
        return matrix
    
    def run_all(self):
        """Execute the full benchmark suite."""
        print(f"\n🚀 Starting {self.mode.upper()} benchmark run\n")
        
        matrix = self.generate_test_matrix()
        total_tests = len(matrix)
        
        # Handle both 'repetitions' as int or dict
        if isinstance(self.config.get('repetitions'), int):
            reps = self.config['repetitions']
        else:
            reps = self.config.get('repetitions', {}).get('count', 3)
        
        print(f"📋 Test matrix: {total_tests} unique configs × {reps} reps = {total_tests * reps} runs\n")
        
        runner = BenchmarkRunner(self.config, self.report_dir)
        
        for idx, test in enumerate(matrix, 1):
            print(f"\n[{idx}/{total_tests}] {test['build']['name']} / {test['pinning'][0]} / {test['metric']['name']}")
            
            # Collect provenance once per build/pinning combo
            provenance = ProvenanceCollector.collect_all(
                test['build']['binary'],
                test.get('env', {})
            )
            
            # Run repetitions
            run_results = []
            for rep in range(1, reps + 1):
                result = runner.run_single(
                    test['build'],
                    test['pinning'][1],
                    test['metric'],
                    rep,
                    extra_env=test.get('env', {}),
                    extra_args=test.get('extra_args', '')
                )
                if result:
                    run_results.append(result)
            
            if run_results:
                self.results.append({
                    'test': test,
                    'provenance': provenance,
                    'runs': run_results
                })
                
                # Save incrementally after each test
                self._save_incremental_results()
        
        print(f"\n✅ Completed {len(self.results)}/{total_tests} test cases")
    
    def _save_incremental_results(self):
        """Save current results to disk after each test completes."""
        raw_json = self.report_dir / 'raw' / 'results.json'
        with open(raw_json, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Also regenerate summary markdown incrementally
        self.generate_summary_markdown()
    
    def generate_reports(self):
        """Generate summary reports and promote file."""
        print(f"\n📝 Generating reports...")
        
        # Save raw results as JSON
        raw_json = self.report_dir / 'raw' / 'results.json'
        with open(raw_json, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Generate markdown summary
        self.generate_summary_markdown()
        
        # Generate promote file if exploratory
        # Handle both 'output' dict and simple top-level configs
        generate_promote = True
        if 'output' in self.config and isinstance(self.config['output'], dict):
            generate_promote = self.config['output'].get('generate_promote', True)
        
        if self.mode == 'exploratory' and generate_promote:
            self.generate_promote_config()
        
        print(f"✓ Reports in: {self.report_dir}")
    
    def generate_summary_markdown(self):
        """Create human-readable summary."""
        summary_path = self.report_dir / 'summary.md'
        
        with open(summary_path, 'w') as f:
            f.write(f"# Benchmark Summary - {self.mode.title()}\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Config:** {self.config_path}\n")
            
            # Handle both model_path and model dict formats
            if 'model_path' in self.config:
                model_name = self.config.get('model_info', Path(self.config['model_path']).stem)
                f.write(f"**Model:** {model_name}\n\n")
            elif 'model' in self.config and isinstance(self.config['model'], dict):
                f.write(f"**Model:** {self.config['model'].get('name', 'N/A')}\n\n")
            else:
                f.write(f"**Model:** N/A\n\n")
            
            # Group results by metric
            by_metric = {}
            for result in self.results:
                metric_name = result['test']['metric']['name']
                if metric_name not in by_metric:
                    by_metric[metric_name] = []
                by_metric[metric_name].append(result)
            
            for metric_name, results in by_metric.items():
                f.write(f"## {metric_name.upper()}\n\n")
                
                # Build table
                rows = []
                for r in results:
                    test = r['test']
                    runs = r['runs']
                    
                    if not runs:
                        continue
                    
                    # Calculate stats across our repetitions
                    perfs = [run['performance'].get('tokens_per_sec', 0) for run in runs]
                    avg_perf = sum(perfs) / len(perfs) if perfs else 0
                    stddev_perf = (sum((p - avg_perf) ** 2 for p in perfs) / len(perfs)) ** 0.5 if len(perfs) > 1 else 0
                    
                    # Also get llama-bench's internal variance (average across our reps)
                    internal_stddevs = [run['performance'].get('stddev_ts', 0) for run in runs]
                    avg_internal_stddev = sum(internal_stddevs) / len(internal_stddevs) if internal_stddevs else 0
                    
                    row = [
                        test['build']['name'],
                        test['pinning'][0],
                        f"{avg_perf:.2f} ± {stddev_perf:.2f}",
                        f"±{avg_internal_stddev:.2f}",
                        len(runs)
                    ]
                    rows.append(row)
                
                # Sort by performance (extract first number from "X.XX ± Y.YY")
                rows.sort(key=lambda x: float(x[2].split()[0]), reverse=True)
                
                headers = ['Build', 'Config', 't/s (our reps)', 'llama-bench σ', 'Reps']
                f.write(tabulate(rows, headers=headers, tablefmt='pipe'))
                f.write("\n\n")
                f.write("*Note: 't/s (our reps)' shows variance across our repetitions. 'llama-bench σ' shows llama-bench's internal variance (default 5 reps each).*\n\n")
            
            f.write("---\n\n")
            f.write("*Generated by HFT CPU Test - https://www.humanfacetech.com/ *\n")
        
        print(f"  ✓ {summary_path}")
    
    def generate_promote_config(self):
        """Create promote.yaml with top performers for deep testing."""
        # Handle both 'output' dict and simple top-level config
        if 'output' in self.config and isinstance(self.config['output'], dict):
            top_n = self.config['output'].get('top_n', 2)
        else:
            top_n = 2  # Default
        
        # Find top performers per metric
        by_metric = {}
        for result in self.results:
            metric_name = result['test']['metric']['name']
            if metric_name not in by_metric:
                by_metric[metric_name] = []
            
            runs = result['runs']
            if runs:
                perfs = [run['performance'].get('tokens_per_sec', 0) for run in runs]
                avg_perf = sum(perfs) / len(perfs) if perfs else 0
                by_metric[metric_name].append((avg_perf, result))
        
        # Get top N per metric
        winners = []
        for metric_name, results in by_metric.items():
            results.sort(reverse=True, key=lambda x: x[0])
            winners.extend([r[1] for r in results[:top_n]])
        
        # Build promote config for deep testing
        promote_path = self.report_dir / 'promote.yaml'
        
        # Start with base config structure
        promote_config = {
            'mode': 'deep',
            'repetitions': 10,  # More reps for deep testing
            'metrics': self.config.get('metrics', ['pp512', 'tg128', 'mixed']),
            'output_dir': self.config.get('output_dir', './reports'),
            'builds': {},
            'builds_select': [],
            'test_matrix': []
        }
        
        # Handle model - support both formats
        if 'model_path' in self.config:
            promote_config['model_path'] = self.config['model_path']
            if 'model_info' in self.config:
                promote_config['model_info'] = self.config['model_info']
        elif 'model' in self.config:
            promote_config['model'] = self.config['model']
        
        # Add llama_bench_reps if configured
        if 'llama_bench_reps' in self.config:
            promote_config['llama_bench_reps'] = self.config['llama_bench_reps']
        
        # Collect unique winners
        seen_builds = set()
        seen_configs = set()
        
        for winner in winners:
            test = winner['test']
            
            # Add build if not seen
            build_name = test['build']['name']
            if build_name not in seen_builds:
                promote_config['builds'][build_name] = {
                    'binary': test['build']['binary'],
                    'label': test['build'].get('label', build_name)
                }
                promote_config['builds_select'].append(build_name)
                seen_builds.add(build_name)
            
            # Add test config if not seen
            config_name = test['pinning'][0]
            if config_name not in seen_configs:
                # Find the original test_matrix entry to preserve all details
                original_matrix = self.config.get('test_matrix', [])
                matching_config = next((cfg for cfg in original_matrix if cfg['name'] == config_name), None)
                
                if matching_config:
                    promote_config['test_matrix'].append(matching_config)
                    seen_configs.add(config_name)
        
        with open(promote_path, 'w') as f:
            yaml.dump(promote_config, f, default_flow_style=False, sort_keys=False)
        
        print(f"  ✓ {promote_path} (top {top_n} per metric)")


def main():
    parser = argparse.ArgumentParser(
        description='HFT CPU Benchmarking Harness',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'config',
        type=Path,
        help='Path to YAML config file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show test matrix without running'
    )
    
    args = parser.parse_args()
    
    if not args.config.exists():
        print(f"❌ Config file not found: {args.config}")
        sys.exit(1)
    
    orchestrator = BenchmarkOrchestrator(args.config)
    
    if args.dry_run:
        matrix = orchestrator.generate_test_matrix()
        print(f"\n📋 Test Matrix ({len(matrix)} configs):\n")
        for idx, test in enumerate(matrix, 1):
            print(f"{idx}. {test['build']['name']} / {test['pinning'][0]} / {test['metric']['name']}")
        sys.exit(0)
    
    orchestrator.run_all()
    orchestrator.generate_reports()
    
    print(f"\n🎉 All done! Check {orchestrator.report_dir}/summary.md")


if __name__ == '__main__':
    main()
