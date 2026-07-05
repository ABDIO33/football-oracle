#!/usr/bin/env python3
"""
Agent 5 ? Phase 5: CENTRALIZED AGENT MONITOR
==============================================
Monitors all agent processes, collects reports, displays progress dashboard.
Updates every 5 minutes (configurable).

Protocols: SHADOW-DOMINION, BLACK CODE CURSE, D?MON CORE
"""

import os
import sys
import json
import time
import glob
import signal
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('agent_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('AgentMonitor')

# Configuration
PROJECT_DIR = Path(__file__).parent
REPORT_INTERVAL = 300  # 5 minutes in seconds (configurable)
MONITORED_PATTERNS = [
    'agent*.py',
    'agent5_*.py',
    'agent4_*.py',
    'agent_heist_*.py',
    'heist_*.py',
    'run_phase*.py',
    '_*.py',
    'train_*.py',
    'ultimate_*.py',
    'build_*.py',
]

# Log file patterns to check
LOG_PATTERNS = [
    '*.log',
    '*_log.txt',
    '*_err.txt',
    '*_out.txt',
]

MONITOR_REPORT = PROJECT_DIR / 'agent_monitor_report.json'
RUNNING_FILE = PROJECT_DIR / '.monitor_running'


class AgentMonitor:
    """Centralized agent monitoring system."""

    def __init__(self, interval: int = REPORT_INTERVAL):
        self.interval = interval
        self.running = False
        self._thread = None
        self.reports = []
        self.start_time = datetime.now()
        self._lock = threading.Lock()

    def discover_agent_scripts(self) -> Dict[str, Path]:
        """Discover all agent scripts in the project directory."""
        scripts = {}
        for pattern in MONITORED_PATTERNS:
            for path in glob.glob(str(PROJECT_DIR / pattern)):
                name = Path(path).stem
                scripts[name] = Path(path)
        return scripts

    def find_log_files(self) -> Dict[str, Path]:
        """Find all log files in the project."""
        log_files = {}
        for pattern in LOG_PATTERNS:
            for path in glob.glob(str(PROJECT_DIR / pattern)):
                name = Path(path).name
                log_files[name] = Path(path)
        return log_files

    def check_script_status(self, script_path: Path) -> Dict[str, Any]:
        """Check if an agent script is running or has run."""
        status = {
            'name': script_path.stem,
            'path': str(script_path),
            'exists': script_path.exists(),
            'size': script_path.stat().st_size if script_path.exists() else 0,
            'modified': datetime.fromtimestamp(
                script_path.stat().st_mtime
            ).isoformat() if script_path.exists() else None,
            'is_running': False,
            'last_log': None,
        }

        # Check if running via process list
        try:
            if os.name == 'nt':  # Windows
                result = subprocess.run(
                    f'wmic process where "name=\'python.exe\'" get CommandLine /format:csv',
                    capture_output=True, text=True, shell=True, timeout=5
                )
                if script_path.stem in result.stdout:
                    status['is_running'] = True
            else:  # Linux/Mac
                result = subprocess.run(
                    ['ps', 'aux'], capture_output=True, text=True, timeout=5
                )
                if script_path.stem in result.stdout:
                    status['is_running'] = True
        except:
            pass

        # Check log files with matching name
        log_base = script_path.stem.replace('agent5_', '').replace('agent_', '')
        for log_name, log_path in self.find_log_files().items():
            if log_base in log_name or script_path.stem in log_name:
                try:
                    with open(log_path, 'r', errors='ignore') as f:
                        lines = f.readlines()
                        status['last_log'] = {
                            'file': log_name,
                            'size': log_path.stat().st_size,
                            'modified': datetime.fromtimestamp(
                                log_path.stat().st_mtime
                            ).isoformat(),
                            'last_10_lines': [l.strip() for l in lines[-10:]],
                            'total_lines': len(lines),
                        }
                except:
                    pass

        return status

    def get_system_stats(self) -> Dict[str, Any]:
        """Get system resource statistics."""
        stats = {
            'cpu_percent': None,
            'memory': {},
            'disk': {},
            'python_processes': 0,
            'gpu_available': False,
            'gpu_memory': None,
        }

        # CPU
        try:
            import psutil
            stats['cpu_percent'] = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            stats['memory'] = {
                'total': mem.total,
                'available': mem.available,
                'used': mem.used,
                'percent': mem.percent,
            }
            disk = psutil.disk_usage(str(PROJECT_DIR))
            stats['disk'] = {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent,
            }
            # Count python processes
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        stats['python_processes'] += 1
                except:
                    pass
        except ImportError:
            # Fallback without psutil
            try:
                if os.name == 'nt':
                    result = subprocess.run(
                        'wmic cpu get loadpercentage',
                        capture_output=True, text=True, shell=True, timeout=5
                    )
                    for line in result.stdout.split('\n'):
                        if line.strip().isdigit():
                            stats['cpu_percent'] = int(line.strip())
                            break
                else:
                    result = subprocess.run(
                        ['top', '-bn1'], capture_output=True, text=True, timeout=5
                    )
                    for line in result.stdout.split('\n'):
                        if '%Cpu(s)' in line:
                            parts = line.split()
                            for i, p in enumerate(parts):
                                if 'id' in p:
                                    stats['cpu_percent'] = 100 - float(parts[i-1])
                                    break
            except:
                pass

            # Memory fallback
            try:
                if os.name == 'nt':
                    result = subprocess.run(
                        'wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /format:csv',
                        capture_output=True, text=True, shell=True, timeout=5
                    )
                    lines = result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        parts = lines[1].split(',')
                        if len(parts) >= 2:
                            stats['memory'] = {
                                'total': int(parts[-2]) * 1024,
                                'free': int(parts[-1]) * 1024,
                                'used': (int(parts[-2]) - int(parts[-1])) * 1024,
                            }
                else:
                    result = subprocess.run(
                        'free -b', capture_output=True, text=True, shell=True, timeout=5
                    )
                    for line in result.stdout.split('\n'):
                        if line.startswith('Mem:'):
                            parts = line.split()
                            stats['memory'] = {
                                'total': int(parts[1]),
                                'used': int(parts[2]),
                                'available': int(parts[-1]),
                            }
            except:
                pass

            # Disk fallback
            try:
                if os.name == 'nt':
                    result = subprocess.run(
                        f'wmic logicaldisk where "DeviceID=\'{PROJECT_DIR.drive}\'" get Size,FreeSpace /format:csv',
                        capture_output=True, text=True, shell=True, timeout=5
                    )
                    for line in result.stdout.split('\n')[1:]:
                        if line.strip():
                            parts = line.split(',')
                            if len(parts) >= 2:
                                total = int(parts[1])
                                free = int(parts[0])
                                stats['disk'] = {
                                    'total': total,
                                    'used': total - free,
                                    'free': free,
                                }
                else:
                    stat = os.statvfs(str(PROJECT_DIR))
                    total = stat.f_frsize * stat.f_blocks
                    free = stat.f_frsize * stat.f_bavail
                    stats['disk'] = {
                        'total': total,
                        'used': total - free,
                        'free': free,
                    }
            except:
                pass

        # GPU check
        try:
            if os.name == 'nt':
                result = subprocess.run(
                    'nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv,noheader,nounits',
                    capture_output=True, text=True, shell=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    stats['gpu_available'] = True
                    parts = result.stdout.strip().split(',')
                    if len(parts) >= 3:
                        stats['gpu_memory'] = {
                            'total': int(parts[0].strip()),
                            'used': int(parts[1].strip()),
                            'free': int(parts[2].strip()),
                        }
            else:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=memory.total,memory.used,memory.free',
                     '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    stats['gpu_available'] = True
                    parts = result.stdout.strip().split(',')
                    if len(parts) >= 3:
                        stats['gpu_memory'] = {
                            'total': int(parts[0].strip()),
                            'used': int(parts[1].strip()),
                            'free': int(parts[2].strip()),
                        }
        except:
            pass

        return stats

    def get_model_stats(self) -> Dict[str, Any]:
        """Get model training statistics from models directory."""
        model_dir = PROJECT_DIR / 'models'
        if not model_dir.exists():
            return {}

        stats = {
            'total_models': 0,
            'total_size': 0,
            'models_by_type': defaultdict(int),
            'largest_models': [],
            'recently_modified': [],
        }

        model_extensions = ['.pkl', '.json', '.ubj', '.pt', '.npy', '.npz']
        models = []

        for ext in model_extensions:
            for path in glob.glob(str(model_dir / f'*{ext}')):
                size = path.stat().st_size
                mtime = path.stat().st_mtime
                ext_type = ext[1:] if ext.startswith('.') else ext

                # Classify model type
                mtype = 'unknown'
                name = path.stem.lower()
                if 'xgboost' in name or 'xgb' in name:
                    mtype = 'xgboost'
                elif 'lgbm' in name:
                    mtype = 'lightgbm'
                elif 'mlp' in name or 'deep' in name or 'nn' in name or '_v' in name:
                    mtype = 'deepnn'
                elif 'ensemble' in name or 'blend' in name or 'hybrid' in name:
                    mtype = 'ensemble'
                elif 'champion' in name or 'ultimate' in name or 'world_record' in name:
                    mtype = 'champion'

                models.append({
                    'name': path.name,
                    'size': size,
                    'size_mb': size / (1024 * 1024),
                    'type': mtype,
                    'modified': datetime.fromtimestamp(mtime).isoformat(),
                    'path': str(path),
                })
                stats['models_by_type'][mtype] += 1
                stats['total_size'] += size

        stats['total_models'] = len(models)
        stats['total_size_gb'] = stats['total_size'] / (1024 ** 3)
        stats['largest_models'] = sorted(models, key=lambda x: -x['size'])[:5]
        stats['recently_modified'] = sorted(
            models, key=lambda x: x['modified'], reverse=True
        )[:10]

        return stats

    def collect_report(self) -> Dict[str, Any]:
        """Collect comprehensive report from all sources."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
            'scripts': [],
            'system': {},
            'models': {},
            'log_files': [],
            'recent_errors': [],
        }

        # Check all scripts
        for name, path in sorted(self.discover_agent_scripts().items()):
            status = self.check_script_status(path)
            report['scripts'].append(status)

        # Check log files
        for name, path in sorted(self.find_log_files().items()):
            try:
                report['log_files'].append({
                    'name': name,
                    'size': path.stat().st_size,
                    'modified': datetime.fromtimestamp(
                        path.stat().st_mtime
                    ).isoformat(),
                })

                # Check for errors in log files
                if path.stat().st_size < 10 * 1024 * 1024:  # < 10MB
                    with open(path, 'r', errors='ignore') as f:
                        content = f.read()
                        error_lines = []
                        for line in content.split('\n')[-200:]:
                            if any(err in line.lower() for err in
                                   ['error', 'exception', 'traceback', 'failed', '[X]']):
                                error_lines.append(line.strip())
                        if error_lines:
                            report['recent_errors'].extend(
                                [f'{name}: {e}' for e in error_lines[-5:]]
                            )
            except:
                pass

        # System stats
        report['system'] = self.get_system_stats()

        # Model stats
        report['models'] = self.get_model_stats()

        return report

    def print_dashboard(self, report: Dict[str, Any]):
        """Print formatted dashboard to terminal."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        uptime = timedelta(seconds=int(report['uptime_seconds']))
        uptime_str = str(uptime).split('.')[0]

        # Clear screen and print dashboard
        os.system('cls' if os.name == 'nt' else 'clear')

        print("?" + "?" * 78 + "?")
        print(f"?  ? AGENT 5 ? CENTRALIZED MONITOR DASHBOARD{' ' * 35}?")
        print(f"?  Time: {now} ? Uptime: {uptime_str}{' ' * 18}?")
        print("?" + "?" * 78 + "?")

        # System stats
        sys = report['system']
        print("?  ? SYSTEM STATS")
        cpu = sys.get('cpu_percent', 'N/A')
        print(f"?     CPU: {cpu}%" if cpu else "?     CPU: N/A")
        mem = sys.get('memory', {})
        if mem:
            mem_pct = mem.get('percent', mem.get('used', 0) / max(mem.get('total', 1), 1) * 100)
            mem_gb = f"{mem.get('used', 0) / (1024**3):.1f}GB / {mem.get('total', 0) / (1024**3):.1f}GB"
            print(f"?     RAM: {mem_gb} ({mem_pct:.0f}%)")
        disk = sys.get('disk', {})
        if disk:
            disk_gb = f"{disk.get('used', 0) / (1024**3):.1f}GB / {disk.get('total', 0) / (1024**3):.1f}GB"
            disk_pct = disk.get('percent', disk.get('used', 0) / max(disk.get('total', 1), 1) * 100)
            print(f"?     DISK: {disk_gb} ({disk_pct:.0f}%)")
        gpu = sys.get('gpu_memory')
        if sys.get('gpu_available') and gpu:
            print(f"?     GPU: {gpu.get('used', 0)}MB / {gpu.get('total', 0)}MB")
        print(f"?     Python processes: {sys.get('python_processes', 'N/A')}")

        print("?" + "?" * 78 + "?")

        # Agent scripts
        print("?  ? AGENT SCRIPTS")
        running_count = sum(1 for s in report['scripts'] if s.get('is_running'))
        print(f"?     Total: {len(report['scripts'])} | Running: {running_count}")
        for script in report['scripts'][:20]:
            name = script['name']
            is_running = script.get('is_running', False)
            size_kb = script.get('size', 0) / 1024
            modified = script.get('modified', '')[:19] if script.get('modified') else ''
            status_icon = '[GRN]' if is_running else '?'
            status_icon = '[RED]' if not script.get('exists') else status_icon
            print(f"?     {status_icon} {name:<30s} {size_kb:>7.1f}KB  {modified}")

        print("?" + "?" * 78 + "?")

        # Models
        mdl = report.get('models', {})
        total = mdl.get('total_models', 0)
        total_gb = mdl.get('total_size_gb', 0)
        print(f"?  ? MODELS: {total} total ({total_gb:.2f} GB)")
        for mtype, count in sorted(mdl.get('models_by_type', {}).items()):
            print(f"?     {mtype}: {count}")
        if mdl.get('largest_models'):
            print(f"?     Largest:")
            for m in mdl['largest_models'][:3]:
                print(f"?       {m['name']:<40s} {m['size_mb']:>7.1f}MB")
        if mdl.get('recently_modified'):
            print(f"?     Recently modified:")
            for m in mdl['recently_modified'][:3]:
                print(f"?       {m['name']} ({m['modified'][:19]})")

        print("?" + "?" * 78 + "?")

        # Recent errors
        errors = report.get('recent_errors', [])
        print(f"?  [X] RECENT ERRORS: {len(errors)}")
        for err in errors[-5:]:
            print(f"?     {err[:100]}")

        print("?" + "?" * 78 + "?")

        # Log files
        logs = report.get('log_files', [])
        total_log_size = sum(l.get('size', 0) for l in logs) / (1024**2)
        print(f"?  ? LOG FILES: {len(logs)} ({total_log_size:.1f} MB)")
        for log in logs[-5:]:
            size_kb = log.get('size', 0) / 1024
            print(f"?     {log['name']:<40s} {size_kb:>8.1f}KB  {log.get('modified', '')[:19]}")

        print("?" + "?" * 78 + "?")
        print(f"  Next update in {self.interval}s ? Press Ctrl+C to stop")

    def save_report(self, report: Dict[str, Any]):
        """Save comprehensive report to JSON file."""
        try:
            # Keep last N reports
            with self._lock:
                self.reports.append(report)
                if len(self.reports) > 100:
                    self.reports = self.reports[-100:]

            with open(MONITOR_REPORT, 'w') as f:
                json.dump(report, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

    def monitor_loop(self):
        """Main monitoring loop."""
        RUNNING_FILE.touch()

        while self.running:
            try:
                # Collect and save report
                report = self.collect_report()
                self.save_report(report)
                self.print_dashboard(report)

                # Save all historical reports
                history_file = PROJECT_DIR / 'agent_monitor_history.json'
                try:
                    with open(history_file, 'w') as f:
                        json.dump(self.reports[-50:], f, indent=2, default=str)
                except:
                    pass

                # Wait for next interval
                for _ in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(10)

        # Cleanup
        if RUNNING_FILE.exists():
            RUNNING_FILE.unlink()

    def start(self):
        """Start the monitor in a background thread."""
        if self.running:
            logger.warning("Monitor already running")
            return

        self.running = True
        self._thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"[OK] Agent Monitor started (interval: {self.interval}s)")

        # Register signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def stop(self):
        """Stop the monitor."""
        self.running = False
        logger.info("? Agent Monitor stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\n\nShutting down Agent Monitor...")
        self.stop()
        sys.exit(0)

    def run_once(self):
        """Run a single check and exit."""
        report = self.collect_report()
        self.save_report(report)
        self.print_dashboard(report)
        return report

    def wait(self):
        """Wait for monitor thread to complete."""
        if self._thread:
            self._thread.join()


def main():
    """Main execution."""
    print("\n" + "#" * 70)
    print("  AGENT 5 ? PHASE 5: CENTRALIZED MONITOR")
    print("  SHADOW-DOMINION | BLACK CODE CURSE | D?MON CORE")
    print("#" * 70)

    import argparse
    parser = argparse.ArgumentParser(description='Agent5 Central Monitor')
    parser.add_argument('--interval', type=int, default=REPORT_INTERVAL,
                        help=f'Report interval in seconds (default: {REPORT_INTERVAL})')
    parser.add_argument('--once', action='store_true',
                        help='Run a single check and exit')
    parser.add_argument('--daemon', action='store_true',
                        help='Run as continuous daemon')
    args = parser.parse_args()

    monitor = AgentMonitor(interval=args.interval)

    if args.once:
        monitor.run_once()
    elif args.daemon:
        print(f"\n  Starting monitor daemon (interval: {args.interval}s)")
        print(f"  Dashboard updates every {args.interval} seconds")
        print(f"  Reports saved to: {MONITOR_REPORT}")
        print(f"  Press Ctrl+C to stop\n")
        monitor.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop()
    else:
        # Interactive mode with initial report
        print("\n  [1/2] Running initial system scan...")
        monitor.run_once()

        print(f"\n  [2/2] Starting continuous monitoring ({args.interval}s interval)...")
        print(f"  Dashboard auto-refreshes. Press Ctrl+C to stop.\n")
        time.sleep(3)
        monitor.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
