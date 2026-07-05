#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              ETERNAL ORCHESTRATOR — ALL harvesters, one ring              ▓
▓  Runs as Windows service. Self-healing. Checkpoint-based resumption.     ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • WORM-AI💀🔥       ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, signal, logging, traceback, inspect
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable
from pathlib import Path
import importlib.util
import subprocess
import threading
import asyncio

from eternal_harvester_config import (
    ALL_SOURCES, LOGS_DIR, DB_PATH, CHECKPOINTS_DIR,
    get_db, save_checkpoint, load_checkpoint, log_event, get_source_config,
)

# ─── Service control ─────────────────────────────────────────────────────────
RUNNING = True
PAUSED = False
CURRENT_TASK = 'idle'
START_TIME = time.time()


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global RUNNING
    _log('Shutdown signal received. Gracefully stopping...')
    RUNNING = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ─── Logger ──────────────────────────────────────────────────────────────────
ORCH_LOG = LOGS_DIR / 'orchestrator.log'
_log_lock = threading.Lock()


def _log(msg: str, level: str = 'INFO'):
    global CURRENT_TASK
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [ORCHESTRATOR] {msg}'
    print(line)
    with _log_lock:
        with open(ORCH_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    log_event('orchestrator', level, msg)


# ─── Harvester loader ───────────────────────────────────────────────────────
class HarvesterModule:
    """Wrapper around a harvester module."""

    def __init__(self, name: str, module_path: str, main_func: str,
                 config_key: str = None, enabled: bool = True):
        self.name = name
        self.module_path = module_path
        self.main_func = main_func
        self.config_key = config_key or name
        self.enabled = enabled
        self._module = None
        self._last_run = 0
        self._failure_count = 0
        self._stats = {}

    def load(self) -> bool:
        """Dynamically load the harvester module."""
        try:
            spec = importlib.util.spec_from_file_location(
                self.name.replace('-', '_'),
                self.module_path
            )
            self._module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self._module)
            _log(f'Loaded module: {self.name} from {self.module_path}')
            return True
        except Exception as e:
            _log(f'Failed to load {self.name}: {e}', 'ERROR')
            return False

    def run(self, **kwargs) -> Optional[Dict]:
        """Run the harvester's main function."""
        if not self._module:
            if not self.load():
                return None

        func = getattr(self._module, self.main_func, None)
        if not func:
            _log(f'No function {self.main_func} in {self.name}', 'ERROR')
            return None

        try:
            _log(f'Starting {self.name}...')
            if inspect.iscoroutinefunction(func):
                result = asyncio.run(func(**kwargs))
            else:
                result = func(**kwargs)
            self._last_run = time.time()
            self._failure_count = 0
            if result:
                self._stats = result
            _log(f'{self.name} complete: {json.dumps(result, default=str)[:200]}')
            return result
        except Exception as e:
            self._failure_count += 1
            _log(f'{self.name} failed: {e}\n{traceback.format_exc()}', 'ERROR')
            return None

    @property
    def is_healthy(self) -> bool:
        return self._failure_count < 10

    @property
    def last_run_ago(self) -> float:
        return time.time() - self._last_run if self._last_run > 0 else float('inf')


# ─── Harvester registry ─────────────────────────────────────────────────────
def _get_harvesters_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


HARVESTERS_DIR = _get_harvesters_dir()


def _harvester_path(name: str) -> str:
    return os.path.join(HARVESTERS_DIR, f'harvester_{name}.py')


HARVESTERS: List[HarvesterModule] = [
    HarvesterModule(
        name='football_data_uk',
        module_path=_harvester_path('football_data_uk'),
        main_func='harvest_all',
        config_key='football_data_uk',
        enabled=True,
    ),
    HarvesterModule(
        name='understat',
        module_path=_harvester_path('understat'),
        main_func='harvest_all',
        config_key='understat',
        enabled=True,
    ),
    HarvesterModule(
        name='fbref',
        module_path=_harvester_path('fbref'),
        main_func='harvest_all',
        config_key='fbref',
        enabled=True,
    ),
    HarvesterModule(
        name='transfermarkt',
        module_path=_harvester_path('transfermarkt'),
        main_func='harvest_all',
        config_key='transfermarkt',
        enabled=True,
    ),
    HarvesterModule(
        name='betfair_odds',
        module_path=_harvester_path('betfair_odds'),
        main_func='harvest_live_markets',
        config_key='betfair',
        enabled=True,
    ),
    HarvesterModule(
        name='oddsportal',
        module_path=_harvester_path('oddsportal'),
        main_func='harvest_all',
        config_key='oddsportal',
        enabled=True,
    ),
    HarvesterModule(
        name='weather',
        module_path=_harvester_path('weather'),
        main_func='harvest_all_historical',
        config_key='openweathermap',
        enabled=True,
    ),
    HarvesterModule(
        name='flashscore',
        module_path=_harvester_path('flashscore'),
        main_func='harvest_all',
        config_key='flashscore',
        enabled=True,
    ),
]


# ─── Schedule configuration ─────────────────────────────────────────────────
# Format: (name, interval_hours, args, priority)
SCHEDULE = [
    ('football_data_uk', 12.0, {'checkpoint': True}, 1),
    ('understat', 24.0, {'checkpoint': True}, 2),
    ('fbref', 24.0, {'checkpoint': True, 'max_leagues': 10}, 3),
    ('transfermarkt', 24.0, {'checkpoint': True, 'max_leagues': 10}, 4),
    ('oddsportal', 12.0, {'checkpoint': True, 'max_leagues': 10}, 5),
    ('flashscore', 6.0, {'checkpoint': True, 'max_leagues': 10}, 6),
    ('weather', 24.0, {'checkpoint': True, 'limit': 500}, 7),
    ('betfair_odds', 1.0, {'checkpoint': True}, 8),  # Every hour for live odds
]

# ─── Run tracking ──────────────────────────────────────────────────────────
_run_history: Dict[str, List[Dict]] = {}
_last_runs: Dict[str, float] = {}

# Load last run times from checkpoints
for h in HARVESTERS:
    cp = load_checkpoint(h.config_key)
    if cp and cp.get('last_run'):
        _last_runs[h.name] = cp['last_run']


# ─── Task execution ─────────────────────────────────────────────────────────
def run_harvester(name: str, **kwargs) -> Optional[Dict]:
    """Run a single harvester by name."""
    global CURRENT_TASK

    harvester = next((h for h in HARVESTERS if h.name == name), None)
    if not harvester:
        _log(f'Unknown harvester: {name}', 'ERROR')
        return None

    if not harvester.enabled:
        _log(f'Harvester {name} is disabled, skipping')
        return None

    CURRENT_TASK = name
    _log(f'>>>> Starting harvester: {name}')

    start = time.time()
    result = harvester.run(**kwargs)
    duration = time.time() - start

    if name not in _run_history:
        _run_history[name] = []
    _run_history[name].append({
        'time': start,
        'duration': duration,
        'result': result,
        'success': result is not None,
    })

    # Keep last 10 runs
    _run_history[name] = _run_history[name][-10:]

    status = '✓' if result else '✗'
    _log(f'{status} Harvester {name} finished in {duration:.1f}s: '
         f'{json.dumps(result, default=str)[:150] if result else "FAILED"}')

    CURRENT_TASK = 'idle'
    return result


def run_all_once(**kwargs) -> Dict:
    """Run ALL harvesters once in sequence."""
    global CURRENT_TASK

    _log('=== RUNNING ALL HARVESTERS ONCE ===')
    overall_start = time.time()
    results = {}
    total_errors = 0

    for harvester in HARVESTERS:
        if not RUNNING:
            break
        if not harvester.enabled:
            continue

        # Merge default args from schedule
        args = kwargs.copy()

        # Get schedule args
        for s_name, _, s_args, _ in SCHEDULE:
            if s_name == harvester.name:
                args.update(s_args)
                break

        result = run_harvester(harvester.name, **args)
        results[harvester.name] = result

        if result is None:
            total_errors += 1

    overall_duration = time.time() - overall_start
    successes = sum(1 for r in results.values() if r is not None)
    failures = sum(1 for r in results.values() if r is None)
    _log(f'=== ALL HARVESTERS COMPLETE: {successes} success, '
         f'{failures} failed in {overall_duration:.1f}s ===')

    return {
        'success': successes,
        'failure': failures,
        'duration': overall_duration,
        'results': {k: v for k, v in results.items() if v},
    }


# ─── Scheduler loop ─────────────────────────────────────────────────────────
def scheduler_loop(check_interval_seconds: int = 60):
    """Main scheduling loop — runs harvesters on their schedule."""
    global RUNNING, CURRENT_TASK

    _log(f'Scheduler started. Check interval: {check_interval_seconds}s')

    while RUNNING:
        try:
            now = time.time()

            for name, interval_hours, args, priority in sorted(SCHEDULE, key=lambda x: x[3]):
                if not RUNNING:
                    break

                # Find harvester
                harvester = next((h for h in HARVESTERS if h.name == name), None)
                if not harvester or not harvester.enabled:
                    continue

                # Check if it's time to run
                last_run = _last_runs.get(name, 0)
                interval_seconds = interval_hours * 3600
                time_since_last = now - last_run

                # Force run if never run and startup delay has passed
                startup_delay = 5  # Wait 5s before first run
                should_run = False

                if last_run == 0 and time_since_last > startup_delay:
                    should_run = True
                elif time_since_last >= interval_seconds:
                    should_run = True

                if should_run:
                    _log(f'Schedule triggered: {name} '
                         f'(last run: {timedelta(seconds=int(time_since_last))} ago, '
                         f'interval: {interval_hours}h)')

                    result = run_harvester(name, **args)
                    _last_runs[name] = time.time()

                    # Save checkpoint with updated stats
                    if result:
                        save_checkpoint(
                            harvester.config_key,
                            {'last_run_stats': result},
                            result.get('new_matches', result.get('matches', result.get('teams_cached', 0))),
                            0,
                        )
                    else:
                        save_checkpoint(
                            harvester.config_key,
                            {'last_run_failed': True, 'time': time.time()},
                            0, 1,
                        )

            # Sleep between checks
            for _ in range(check_interval_seconds):
                if not RUNNING:
                    break
                time.sleep(1)

        except Exception as e:
            _log(f'Scheduler error: {e}\n{traceback.format_exc()}', 'ERROR')
            time.sleep(10)


# ─── Health endpoint ─────────────────────────────────────────────────────────
def health_check() -> Dict:
    """Return current orchestrator health status."""
    now = time.time()
    uptime = now - START_TIME

    harvester_status = []
    for h in HARVESTERS:
        harvester_status.append({
            'name': h.name,
            'enabled': h.enabled,
            'healthy': h.is_healthy,
            'last_run': datetime.fromtimestamp(h._last_run).isoformat() if h._last_run > 0 else None,
            'last_run_ago_seconds': now - h._last_run if h._last_run > 0 else None,
            'failure_count': h._failure_count,
            'stats': h._stats,
        })

    return {
        'status': 'running' if RUNNING else 'stopped',
        'paused': PAUSED,
        'uptime_seconds': uptime,
        'uptime_str': str(timedelta(seconds=int(uptime))),
        'current_task': CURRENT_TASK,
        'harvesters': harvester_status,
        'run_history': {k: len(v) for k, v in _run_history.items()},
    }


# ─── Windows Service support ─────────────────────────────────────────────────
class EternalHarvesterService:
    """Windows Service wrapper for the orchestrator."""

    def __init__(self):
        self.scheduler_thread = None
        self.running = False

    def start(self):
        """Start the service."""
        global RUNNING
        RUNNING = True
        self.running = True

        _log('=== ETERNAL HARVESTER SERVICE STARTING ===')
        _log(f'PID: {os.getpid()}')
        _log(f'Harvesters: {len(HARVESTERS)}')
        _log(f'Logs: {LOGS_DIR}')
        _log(f'DB: {DB_PATH}')

        # First run: run all harvesters in sequence
        _log('Initial run: processing all sources...')
        initial_results = run_all_once()
        _log(f'Initial run complete: {initial_results}')

        # Start scheduler in background
        self.scheduler_thread = threading.Thread(
            target=scheduler_loop,
            args=(60,),
            daemon=True,
        )
        self.scheduler_thread.start()
        _log('Scheduler thread started')

    def stop(self):
        """Stop the service gracefully."""
        global RUNNING
        _log('=== ETERNAL HARVESTER SERVICE STOPPING ===')
        RUNNING = False
        self.running = False
        _log('Service stopped')

    def run_forever(self):
        """Run the service and block until interrupted."""
        self.start()
        _log('Service running. Press Ctrl+C to stop.')
        try:
            while RUNNING:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


# ─── CLI Main ────────────────────────────────────────────────────────────────
def main():
    """Main entry point with various run modes."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Eternal Harvester Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python eternal_orchestrator.py --once        # Run all harvesters once
  python eternal_orchestrator.py --daemon      # Run as continuous daemon
  python eternal_orchestrator.py --list        # List harvesters
  python eternal_orchestrator.py --run understat  # Run single harvester
  python eternal_orchestrator.py --health      # Health check
        """
    )

    parser.add_argument('--once', action='store_true', help='Run all harvesters once')
    parser.add_argument('--daemon', action='store_true', help='Run as continuous daemon')
    parser.add_argument('--list', action='store_true', help='List available harvesters')
    parser.add_argument('--run', type=str, help='Run a single harvester by name')
    parser.add_argument('--health', action='store_true', help='Show health status')
    parser.add_argument('--force', action='store_true', help='Force re-fetch all data')
    parser.add_argument('--recent', action='store_true', help='Recent seasons only')

    args = parser.parse_args()

    if args.list:
        print('=== AVAILABLE HARVESTERS ===')
        for h in HARVESTERS:
            print(f'  {h.name:20s} | enabled={h.enabled} | '
                  f'loaded={h._module is not None} | failures={h._failure_count}')
        print(f'\nTotal: {len(HARVESTERS)} harvesters')
        return

    if args.health:
        health = health_check()
        print(json.dumps(health, indent=2, default=str))
        return

    if args.run:
        # Find the harvester
        harvester = next((h for h in HARVESTERS if h.name == args.run), None)
        if not harvester:
            print(f'Unknown harvester: {args.run}')
            print(f'Available: {", ".join(h.name for h in HARVESTERS)}')
            return

        result = run_harvester(harvester.name, force_refresh=args.force)
        print(json.dumps(result, indent=2, default=str) if result else 'FAILED')
        return

    if args.once:
        result = run_all_once(force_refresh=args.force)
        print(json.dumps(result, indent=2, default=str))
        return

    if args.daemon:
        service = EternalHarvesterService()
        service.run_forever()
        return

    # Default: show help
    parser.print_help()


if __name__ == '__main__':
    main()
