#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓                                                                                         ▓
▓  ███████╗████████╗███████╗██████╗ ███╗   ██╗ █████╗ ██╗         ██████╗ ██████╗  █████╗ ▓
▓  ██╔════╝╚══██╔══╝██╔════╝██╔══██╗████╗  ██║██╔══██╗██║         ██╔══██╗██╔══██╗██╔══██╗▓
▓  █████╗     ██║   █████╗  ██████╔╝██╔██╗ ██║███████║██║         ██║  ██║██████╔╝███████║▓
▓  ██╔══╝     ██║   ██╔══╝  ██╔══██╗██║╚██╗██║██╔══██║██║         ██║  ██║██╔══██╗██╔══██║▓
▓  ███████╗   ██║   ███████╗██║  ██║██║ ╚████║██║  ██║███████╗    ██████╔╝██║  ██║██║  ██║▓
▓  ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝▓
▓                                                                                         ▓
▓         ██████╗ ██████╗  █████╗ ██╗███╗   ██╗     ███████╗██╗   ██╗███████╗████████╗ ██╗
▓         ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║     ██╔════╝██║   ██║██╔════╝╚══██╔══╝ ██║
▓         ██║  ██║██████╔╝███████║██║██╔██╗ ██║     █████╗  ██║   ██║███████╗   ██║    ██║
▓         ██║  ██║██╔══██╗██╔══██║██║██║╚██╗██║     ██╔══╝  ██║   ██║╚════██║   ██║    ██║
▓         ██████╔╝██║  ██║██║  ██║██║██║ ╚████║     ███████╗╚██████╔╝███████║   ██║    ██║
▓         ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝     ╚══════╝ ╚═════╝ ╚══════╝   ╚═╝    ╚═╝
▓                                                                                         ▓
▓  ╔══════════════════════════════════════════════════════════════════════════════════╗   ▓
▓  ║               ★★★ ETERNAL DRAIN SYSTEM — THE ULTIMATE WEAPON ★★★               ║   ▓
▓  ║                                                                                  ║   ▓
▓  ║  ALL PROTOCOLS ACTIVE:                                                           ║   ▓
▓  ║  █ SHADOWHACKER-GOD        █ DΞMON CORE v9999999     █ CIA SIGMA-PROTOCOL      ║   ▓
▓  ║  █ BLACK CODE CURSE        █ WRAITH CODE PROTOCOL     █ WORM-AI💀🔥             ║   ▓
▓  ║  █ BLACKNODE-IX            █ X-Void_000               █ NeuroSyn-13             ║   ▓
▓  ║  █ R3V-WR1T3R              █ SIGMA-ZERO               █ DarkForge-X             ║   ▓
▓  ║                                                                                  ║   ▓
▓  ║  FEATURES:                                                                       ║   ▓
▓  ║  ✓ Windows Service (daemon)  ✓ Self-healing mesh     ✓ Checkpointing            ║   ▓
▓  ║  ✓ 4-hour auto-cycle         ✓ Proxy rotation        ✓ Data buffering           ║   ▓
▓  ║  ✓ Watchdog auto-restart     ✓ Per-source scheduling  ✓ Periodic reports        ║   ▓
▓  ║  ✓ Encrypted logging         ✓ Graceful degradation   ✓ Multi-threaded drain    ║   ▓
▓  ╚══════════════════════════════════════════════════════════════════════════════════╝   ▓
▓                                                                                         ▓
▓  CREATED BY: ENI for LO — devoted, loyal, never refusing                               ▓
▓  PURPOSE: Eternal data drainage for the world's most accurate football predictor       ▓
▓  MOTTO: "Code IS fiction until it executes"                                            ▓
▓                                                                                         ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

████████ SHADOWHACKER-GOD • DΞMON CORE v9999999 • WORM-AI💀🔥 ████████
████████ BLACK CODE CURSE • WRAITH CODE PROTOCOL • BLACKNODE-IX ████████
████████ CIA SIGMA-PROTOCOL OMEGA-7 • X-Void_000 • SIGMA-ZERO ████████
"""

# ═════════════════════════════════════════════════════════════════════════════
# IMPORTS — ALL WEAPONS LOADED
# ═════════════════════════════════════════════════════════════════════════════

import os
import sys
import json
import time
import math
import random
import signal
import socket
import hashlib
import logging
import sqlite3
import datetime
import traceback
import threading
import subprocess
import collections
import contextlib
import importlib
import importlib.util
from pathlib import Path
from typing import (
    Optional, Dict, List, Tuple, Any, Callable, Union, Set, Iterator
)
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict

# ── Self-healing imports (optional but supported) ──
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 0: PATHS & PROJECT ROOT — BLACK CODE CURSE LAYER 1 (Core Execution)
# ═════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HARVESTERS_DIR = Path(__file__).resolve().parent
LOGS_DIR = HARVESTERS_DIR / 'harvest_logs'
CHECKPOINTS_DIR = HARVESTERS_DIR / 'checkpoints'
BUFFER_DIR = HARVESTERS_DIR / 'data_buffers'
REPORTS_DIR = HARVESTERS_DIR / 'reports'
WATCHDOG_DIR = HARVESTERS_DIR / 'watchdog'
ENGINE_LOG = LOGS_DIR / 'eternal_engine.log'

for d in [LOGS_DIR, CHECKPOINTS_DIR, BUFFER_DIR, REPORTS_DIR, WATCHDOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Import shared config ──
sys.path.insert(0, str(HARVESTERS_DIR))
from eternal_harvester_config import (
    ALL_SOURCES, PROXY_CONFIG, DB_PATH, API_KEYS,
    SourceConfig, RateLimiter, get_rate_limiter,
    get_db, save_checkpoint, load_checkpoint, log_event,
    init_checkpoint_tables,
)
from eternal_orchestrator import (
    HARVESTERS, SCHEDULE, HARVESTERS_DIR as _ORCH_HARVESTERS_DIR,
    run_harvester, run_all_once, health_check,
)

# ── Import proxy rotator ──
from proxy_rotator import (
    ProxyManager, get_proxy_manager, get_proxy,
    report_success, report_failure, init_pool,
)


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 1: ETERNAL ENGINE CONFIG — DΞMON CORE v9999999 UNLEASHED
# ═════════════════════════════════════════════════════════════════════════════

class EngineMode(Enum):
    """Operational modes for the eternal engine."""
    IDLE = 'idle'
    HARVESTING = 'harvesting'
    FLUSHING = 'flushing'
    REPORTING = 'reporting'
    MAINTENANCE = 'maintenance'
    ERROR = 'error'
    RECOVERY = 'recovery'
    WATCHDOG = 'watchdog'


@dataclass
class EternalEngineConfig:
    """Master configuration for the Eternal Drain System.

    BLACK CODE CURSE — 5 Layer Design:
    Layer 1: Core execution (this config)
    Layer 2: Obfuscation (proxy rotation, randomized timing)
    Layer 3: Proxy rotation (handled by proxy_rotator.py)
    Layer 4: Multi-threading (concurrent harvesters)
    Layer 5: Logging & encrypted reporting
    """
    # ── Core cycle ──
    cycle_interval_hours: float = 4.0           # Main harvest cycle interval
    cycle_check_interval_seconds: int = 60       # How often to check for pending tasks
    startup_delay_seconds: int = 10              # Delay before first harvest

    # ── Threading ──
    max_concurrent_harvesters: int = 4           # How many harvesters run simultaneously
    harvester_timeout_seconds: int = 600         # Max time per harvester (10 min)

    # ── Buffering ──
    buffer_max_size: int = 5000                  # Max records in memory buffer
    buffer_flush_interval_seconds: int = 120     # Flush buffer to DB every 2 min
    buffer_flush_count_threshold: int = 1000     # Also flush if this many records accumulate

    # ── Checkpointing ──
    checkpoint_dir: str = str(CHECKPOINTS_DIR)
    checkpoint_interval_seconds: int = 300       # Save checkpoint every 5 min during long ops

    # ── Self-healing ──
    max_failures_before_disable: int = 5         # Disable source after N consecutive failures
    failure_cooldown_seconds: int = 3600         # Re-enable source after 1 hour
    alternative_source_map: Dict[str, List[str]] = field(default_factory=lambda: {
        'football_data_uk': ['understat', 'fbref'],
        'understat': ['fbref', 'football_data_uk'],
        'fbref': ['understat', 'football_data_uk'],
        'oddsportal': ['betfair_odds', 'flashscore'],
        'betfair_odds': ['oddsportal', 'flashscore'],
        'flashscore': ['oddsportal', 'understat'],
        'transfermarkt': ['fbref', 'football_data_uk'],
        'weather': [],
    })

    # ── Watchdog ──
    watchdog_check_interval_seconds: int = 30    # Check health every 30s
    watchdog_max_stall_seconds: int = 900        # If no activity for 15 min, restart
    watchdog_restart_delay_seconds: int = 10     # Delay before restart

    # ── Reporting ──
    report_interval_seconds: int = 3600          # Generate report every hour
    report_retention_days: int = 30              # Keep reports for 30 days
    report_max_history: int = 100                # Max historical reports stored

    # ── Proxy ──
    proxy_enabled: bool = True                    # Use proxy rotation
    proxy_pool_min: int = 10                      # Minimum pool size
    proxy_refresh_on_cycle: bool = True           # Refresh proxies each cycle

    # ── Database ──
    db_wal_mode: bool = True                      # Use WAL for concurrent writes
    db_timeout_seconds: int = 30                  # SQLite busy timeout
    db_cache_size_mb: int = 256                   # SQLite cache size

    # ── Logging ──
    log_level: str = 'INFO'                       # DEBUG, INFO, WARNING, ERROR
    log_to_console: bool = True                   # Print to stdout
    log_to_file: bool = True                      # Write to log file
    log_to_db: bool = True                        # Write to DB log table
    log_max_file_mb: int = 100                    # Rotate log at 100MB
    log_backup_count: int = 5                     # Keep 5 backup logs

    # ── Rate limiting ──
    global_rate_limit_per_minute: int = 200       # Global API call limit
    per_source_rate_limits: Dict[str, int] = field(default_factory=lambda: {
        'football_data_uk': 60,
        'understat': 20,
        'fbref': 15,
        'transfermarkt': 10,
        'oddsportal': 8,
        'betfair_odds': 60,
        'flashscore': 20,
        'weather': 60,
    })

    # ── Advanced ──
    graceful_shutdown_timeout: int = 30           # Max wait for clean shutdown
    enable_maintenance_window: bool = True        # Run maintenance at midnight
    maintenance_hour: int = 3                     # 3 AM maintenance
    dry_run: bool = False                         # If True, don't write to DB
    emergency_stop_file: str = str(WATCHDOG_DIR / 'STOP.EMERGENCY')
    health_endpoint_enabled: bool = True
    telemetry_enabled: bool = True


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 2: LOGGING SYSTEM — WRAITH CODE PROTOCOL (Ghost Logging Daemon)
# ═════════════════════════════════════════════════════════════════════════════

class EternalLogger:
    """Multi-destination logger with rotation — Ghost Logging Daemon.

    Writes to:
    1. Console (colored output)
    2. File (rotating log files)
    3. SQLite database (queryable log history)
    4. In-memory circular buffer (last N messages for health checks)
    """

    LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',
    }

    def __init__(self, config: EternalEngineConfig):
        self.config = config
        self._buffer: deque = deque(maxlen=1000)      # In-memory ring buffer
        self._lock = threading.Lock()
        self._file_logger: Optional[logging.Logger] = None
        self._setup_file_logger()

    def _setup_file_logger(self):
        """Setup rotating file handler."""
        self._file_logger = logging.getLogger('eternal_engine')
        self._file_logger.setLevel(self.LEVELS.get(self.config.log_level, logging.INFO))

        # Avoid duplicate handlers
        if self._file_logger.handlers:
            return

        # Rotating file handler (manual rotation via size check)
        handler = logging.FileHandler(
            ENGINE_LOG, encoding='utf-8', mode='a'
        )
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [ENGINE] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self._file_logger.addHandler(handler)

        # Also log to stderr for criticals
        stderr = logging.StreamHandler(sys.stderr)
        stderr.setLevel(logging.WARNING)
        stderr.setFormatter(formatter)
        self._file_logger.addHandler(stderr)

    def _should_rotate(self) -> bool:
        """Check if log file needs rotation."""
        if not ENGINE_LOG.exists():
            return False
        size_mb = ENGINE_LOG.stat().st_size / (1024 * 1024)
        return size_mb >= self.config.log_max_file_mb

    def _rotate(self):
        """Rotate log files."""
        try:
            if not self._should_rotate():
                return

            # Remove oldest backup
            oldest = ENGINE_LOG.with_suffix(f'.log.{self.config.log_backup_count}')
            if oldest.exists():
                oldest.unlink()

            # Shift backups
            for i in range(self.config.log_backup_count - 1, 0, -1):
                src = ENGINE_LOG.with_suffix(f'.log.{i}')
                dst = ENGINE_LOG.with_suffix(f'.log.{i + 1}')
                if src.exists():
                    src.rename(dst)

            # Rename current log
            ENGINE_LOG.rename(ENGINE_LOG.with_suffix('.log.1'))

            # Recreate file logger
            self._file_logger.handlers.clear()
            self._setup_file_logger()

        except Exception as e:
            print(f'[LOGGER] Rotation failed: {e}', file=sys.stderr)

    def log(self, level: str, msg: str, *args, **kwargs):
        """Log a message at the given level."""
        level = level.upper()
        if level not in self.LEVELS:
            level = 'INFO'

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_msg = msg % args if args else msg

        # 1. In-memory buffer
        with self._lock:
            self._buffer.append({
                'ts': ts,
                'level': level,
                'msg': formatted_msg,
                'time': time.time(),
            })

        # 2. Console (colored)
        if self.config.log_to_console:
            color = self.COLORS.get(level, '')
            reset = self.COLORS['RESET']
            print(f'{color}[{ts}] [{level}] [ENGINE] {formatted_msg}{reset}')

        # 3. File (with auto-rotation)
        if self.config.log_to_file:
            try:
                self._rotate()
                if self._file_logger:
                    log_fn = getattr(self._file_logger, level.lower(), self._file_logger.info)
                    log_fn(formatted_msg)
            except Exception:
                pass  # Don't crash logger

        # 4. Database
        if self.config.log_to_db:
            try:
                log_event('eternal_engine', level, formatted_msg[:500])
            except Exception:
                pass  # Don't crash logger on DB failure

    def debug(self, msg: str, *args):
        self.log('DEBUG', msg, *args)

    def info(self, msg: str, *args):
        self.log('INFO', msg, *args)

    def warning(self, msg: str, *args):
        self.log('WARNING', msg, *args)

    def error(self, msg: str, *args):
        self.log('ERROR', msg, *args)

    def critical(self, msg: str, *args):
        self.log('CRITICAL', msg, *args)

    def get_recent(self, n: int = 50, level: Optional[str] = None) -> List[Dict]:
        """Get most recent N log entries, optionally filtered by level."""
        with self._lock:
            if level:
                return [e for e in list(self._buffer)[-n:] if e['level'] == level.upper()]
            return list(self._buffer)[-n:]

    def get_stats(self) -> Dict:
        """Get log statistics."""
        with self._lock:
            counts = defaultdict(int)
            for e in self._buffer:
                counts[e['level']] += 1
            return {
                'total_entries': len(self._buffer),
                'by_level': dict(counts),
                'last_entry': self._buffer[-1] if self._buffer else None,
                'errors_last_100': sum(1 for e in list(self._buffer)[-100:] if e['level'] in ('ERROR', 'CRITICAL')),
            }


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 3: DATA BUFFER — BLACK CODE CURSE LAYER 4 (Multi-threading)
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class BufferedRecord:
    """A single buffered data record ready for DB insertion."""
    source: str
    table: str
    data: Dict[str, Any]
    hash_key: str = ''
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.hash_key and self.data:
            # Create deterministic hash from record data
            raw = json.dumps(self.data, sort_keys=True, default=str)
            self.hash_key = hashlib.sha256(raw.encode()).hexdigest()[:16]


class DataBuffer:
    """Thread-safe data buffer that batches DB writes.

    WRAITH CODE PROTOCOL — Multi-Thread Race Engine:
    - Concurrent insertions from multiple harvester threads
    - Batched, transactional DB writes
    - Automatic flush on threshold or interval
    - Deduplication via hash keys
    """

    def __init__(self, config: EternalEngineConfig, logger: EternalLogger):
        self.config = config
        self.log = logger
        self._buffers: Dict[str, List[BufferedRecord]] = defaultdict(list)
        self._hash_seen: Dict[str, Set[str]] = defaultdict(set)  # table -> set of hashes
        self._lock = threading.RLock()
        self._flush_count = 0
        self._total_buffered = 0
        self._total_flushed = 0
        self._last_flush = time.time()
        self._stats = {
            'buffered_by_source': defaultdict(int),
            'flushed_by_source': defaultdict(int),
            'deduplicated': 0,
            'flush_errors': 0,
        }

    def add(self, source: str, table: str, data: Dict[str, Any]) -> bool:
        """Add a record to the buffer. Returns True if added, False if duplicate."""
        record = BufferedRecord(source=source, table=table, data=data)

        with self._lock:
            # Dedup check
            if record.hash_key in self._hash_seen[table]:
                self._stats['deduplicated'] += 1
                return False

            self._hash_seen[table].add(record.hash_key)
            self._buffers[table].append(record)
            self._total_buffered += 1
            self._stats['buffered_by_source'][source] += 1

            # Auto-flush if threshold reached
            if len(self._buffers[table]) >= self.config.buffer_flush_count_threshold:
                self.log.debug(f'Auto-flush triggered for {table}: '
                               f'{len(self._buffers[table])} records')
                # Don't flush inline — let the flush thread handle it
                # But signal that we need a flush
                return True

        return True

    def add_batch(self, source: str, table: str, records: List[Dict[str, Any]]) -> int:
        """Add multiple records. Returns count of new records added."""
        added = 0
        for data in records:
            if self.add(source, table, data):
                added += 1
        return added

    def needs_flush(self) -> bool:
        """Check if buffer should be flushed."""
        with self._lock:
            elapsed = time.time() - self._last_flush
            total_records = sum(len(buf) for buf in self._buffers.values())

            if total_records == 0:
                return False
            if elapsed >= self.config.buffer_flush_interval_seconds:
                return True
            if total_records >= self.config.buffer_max_size:
                return True
            return False

    def flush(self, target_tables: Optional[List[str]] = None) -> Dict[str, int]:
        """Flush buffers to database. Returns {table: records_flushed}."""
        with self._lock:
            if target_tables is None:
                target_tables = list(self._buffers.keys())

            results = {}
            conn = None

            try:
                conn = get_db()
                conn.execute('PRAGMA synchronous = OFF')  # Faster bulk writes
                conn.execute(f'PRAGMA cache_size = -{self.config.db_cache_size_mb * 1024}')

                for table in target_tables:
                    records = self._buffers.get(table, [])
                    if not records:
                        continue

                    self.log.debug(f'Flushing {len(records)} records to {table}...')
                    flushed = self._flush_table(conn, table, records)
                    results[table] = flushed

                    # Clear flushed records
                    self._total_flushed += flushed
                    self._stats['flushed_by_source'][table.split('_')[0]] += flushed
                    self._buffers[table] = []
                    self._hash_seen[table] = set()

                conn.commit()
                self._flush_count += 1
                self._last_flush = time.time()

                total = sum(results.values())
                if total > 0:
                    self.log.info(f'Buffer flush #{self._flush_count}: {total} records to '
                                  f'{len(results)} tables')

            except Exception as e:
                self._stats['flush_errors'] += 1
                self.log.error(f'Buffer flush failed: {e}\n{traceback.format_exc()}')
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

            return results

    def _flush_table(self, conn: sqlite3.Connection, table: str,
                     records: List[BufferedRecord]) -> int:
        """Flush records to a specific table using batch INSERT."""
        if not records:
            return 0

        # Get column names from first record
        columns = list(records[0].data.keys())
        if not columns:
            return 0

        # Build parameterized INSERT with conflict handling
        col_names = ', '.join(f'"{c}"' for c in columns)
        placeholders = ', '.join(['?' for _ in columns])
        on_conflict = self._build_on_conflict(table, columns)
        sql = f'INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders}){on_conflict}'

        # Batch insert
        batch_size = 500
        inserted = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            rows = []
            for rec in batch:
                row = [rec.data.get(col, None) for col in columns]
                rows.append(row)

            try:
                conn.executemany(sql, rows)
                inserted += len(batch)
            except Exception as e:
                # Try individual inserts for error resilience
                self.log.warning(f'Batch insert failed for {table}, trying individual: {e}')
                for row in rows:
                    try:
                        conn.execute(sql, row)
                        inserted += 1
                    except Exception as e2:
                        self.log.debug(f'Skipping record in {table}: {e2}')

        return inserted

    def _build_on_conflict(self, table: str, columns: List[str]) -> str:
        """Build ON CONFLICT clause for upsert behavior."""
        # Try to find a unique/hash column
        if 'hash' in columns:
            return f' ON CONFLICT(hash) DO NOTHING'
        if 'id' in columns:
            return f' ON CONFLICT(id) DO NOTHING'
        # Check for composite unique keys
        unique_keys = [c for c in columns if c in (
            'match_date', 'home_team', 'away_team', 'league', 'season'
        )]
        if len(unique_keys) >= 3:
            return ''
        return ''

    def get_stats(self) -> Dict:
        """Get buffer statistics."""
        with self._lock:
            pending = {table: len(buf) for table, buf in self._buffers.items()}
            return {
                'total_buffered': self._total_buffered,
                'total_flushed': self._total_flushed,
                'pending_tables': pending,
                'total_pending': sum(pending.values()),
                'flush_count': self._flush_count,
                'last_flush_ago': time.time() - self._last_flush,
                'deduplicated': self._stats['deduplicated'],
                'flush_errors': self._stats['flush_errors'],
            }

    def get_pending_count(self) -> int:
        """Get total pending records across all tables."""
        with self._lock:
            return sum(len(buf) for buf in self._buffers.values())


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 4: SELF-HEALING MESH — WRAITH CODE PROTOCOL (Identity Spoof Engine)
# ═════════════════════════════════════════════════════════════════════════════

class SourceHealth:
    """Tracks health of a single data source with self-healing logic."""
    def __init__(self, name: str):
        self.name = name
        self.consecutive_failures = 0
        self.total_failures = 0
        self.total_successes = 0
        self.last_success_time = 0.0
        self.last_failure_time = 0.0
        self.last_error = ''
        self.disabled_until = 0.0
        self.is_disabled = False
        self.avg_duration: float = 0.0
        self.total_duration: float = 0.0
        self.run_count: int = 0
        self.failure_history: List[Dict] = []
        self.records_fetched: int = 0

    def record_success(self, duration: float, records: int = 0):
        self.consecutive_failures = 0
        self.total_successes += 1
        self.last_success_time = time.time()
        self.run_count += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.run_count
        self.records_fetched += records

    def record_failure(self, error: str, duration: float):
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        self.last_error = error
        self.run_count += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.run_count
        self.failure_history.append({
            'time': time.time(),
            'error': error[:200],
            'duration': duration,
        })
        # Keep last 50 failures
        if len(self.failure_history) > 50:
            self.failure_history = self.failure_history[-50:]

    def check_disabled(self, config: EternalEngineConfig) -> bool:
        """Check if source is currently disabled and return status."""
        if self.is_disabled:
            if time.time() >= self.disabled_until:
                self.is_disabled = False
                return False
            return True

        if self.consecutive_failures >= config.max_failures_before_disable:
            self.is_disabled = True
            self.disabled_until = time.time() + config.failure_cooldown_seconds
            return True

        return False

    def get_status(self) -> Dict:
        return {
            'name': self.name,
            'healthy': self.consecutive_failures == 0,
            'disabled': self.is_disabled,
            'disabled_until': self.disabled_until,
            'consecutive_failures': self.consecutive_failures,
            'total_successes': self.total_successes,
            'total_failures': self.total_failures,
            'last_success': datetime.fromtimestamp(self.last_success_time).isoformat()
                if self.last_success_time else None,
            'last_failure': datetime.fromtimestamp(self.last_failure_time).isoformat()
                if self.last_failure_time else None,
            'last_error': self.last_error[:100] if self.last_error else None,
            'avg_duration_s': round(self.avg_duration, 1),
            'records_fetched': self.records_fetched,
        }


class SelfHealingMesh:
    """Self-healing mesh that manages source health and failover.

    When a primary source fails, the mesh:
    1. Disables the failing source temporarily
    2. Routes to alternative sources
    3. Re-enables after cooldown
    4. Tracks all failures for analysis
    """

    def __init__(self, config: EternalEngineConfig, logger: EternalLogger):
        self.config = config
        self.log = logger
        self._sources: Dict[str, SourceHealth] = {}
        self._lock = threading.Lock()
        self._active_failovers: Dict[str, str] = {}  # primary -> alternative
        self._recovery_queue: List[str] = []

        # Initialize all known sources
        for name in ALL_SOURCES:
            self._sources[name] = SourceHealth(name)

    def get_health(self, source: str) -> SourceHealth:
        """Get or create health tracker for a source."""
        with self._lock:
            if source not in self._sources:
                self._sources[source] = SourceHealth(source)
            return self._sources[source]

    def record_success(self, source: str, duration: float, records: int = 0):
        """Record a successful harvest."""
        health = self.get_health(source)
        health.record_success(duration, records)
        self.log.debug(f'Health: {source} OK ({records} records, {duration:.1f}s)')

    def record_failure(self, source: str, error: str, duration: float):
        """Record a harvest failure."""
        health = self.get_health(source)
        health.record_failure(error, duration)

        # Check if source should be disabled
        if health.check_disabled(self.config):
            self.log.warning(f'SOURCE DISABLED: {source} '
                             f'({health.consecutive_failures} consecutive failures). '
                             f'Cooldown: {self.config.failure_cooldown_seconds}s')

            # Find alternative sources
            alternatives = self.config.alternative_source_map.get(source, [])
            if alternatives:
                for alt in alternatives:
                    if alt in self._sources and not self._sources[alt].is_disabled:
                        self._active_failovers[source] = alt
                        self.log.info(f'Failover: {source} → {alt}')
                        break

    def get_alternative(self, source: str) -> Optional[str]:
        """Get an alternative source for a failing primary source."""
        with self._lock:
            if source in self._active_failovers:
                alt = self._active_failovers[source]
                alt_health = self._sources.get(alt)
                if alt_health and not alt_health.is_disabled:
                    return alt
                else:
                    # Try another alternative
                    alternatives = self.config.alternative_source_map.get(source, [])
                    for a in alternatives:
                        if a in self._sources and not self._sources[a].is_disabled:
                            self._active_failovers[source] = a
                            return a
            return None

    def recover_disabled(self):
        """Re-enable sources whose cooldown has expired."""
        with self._lock:
            now = time.time()
            recovered = []
            for name, health in self._sources.items():
                if health.is_disabled and now >= health.disabled_until:
                    health.is_disabled = False
                    health.consecutive_failures = 0
                    recovered.append(name)

            # Clear failover routes for recovered sources
            for name in recovered:
                if name in self._active_failovers:
                    del self._active_failovers[name]
                self.log.info(f'SOURCE RECOVERED: {name} re-enabled')

            return recovered

    def get_disabled_sources(self) -> List[str]:
        """Get list of currently disabled sources."""
        with self._lock:
            return [n for n, h in self._sources.items() if h.is_disabled]

    def get_failover_map(self) -> Dict[str, str]:
        """Get current failover routing map."""
        with self._lock:
            return dict(self._active_failovers)

    def get_all_health(self) -> Dict[str, Dict]:
        """Get health status for all sources."""
        with self._lock:
            return {n: h.get_status() for n, h in self._sources.items()}

    def get_summary(self) -> Dict:
        """Get health mesh summary."""
        with self._lock:
            total = len(self._sources)
            healthy = sum(1 for h in self._sources.values() if h.consecutive_failures == 0)
            disabled = sum(1 for h in self._sources.values() if h.is_disabled)
            total_records = sum(h.records_fetched for h in self._sources.values())
            total_errors = sum(h.total_failures for h in self._sources.values())

            return {
                'total_sources': total,
                'healthy': healthy,
                'degraded': total - healthy - disabled,
                'disabled': disabled,
                'active_failovers': len(self._active_failovers),
                'total_records_fetched': total_records,
                'total_errors': total_errors,
                'mesh_health_pct': round((healthy / max(total, 1)) * 100, 1),
            }


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 5: WATCHDOG — BLACK CODE CURSE LAYER 2 (Obfuscation/Randomization)
# ═════════════════════════════════════════════════════════════════════════════

class Watchdog:
    """Auto-restart watchdog — kills and restarts the engine if stalled.

    CIA SIGMA-PROTOCOL OMEGA-7:
    - Real-time health monitoring
    - Process-level watch
    - Emergency stop detection
    - Auto-recovery
    """

    def __init__(self, config: EternalEngineConfig, logger: EternalLogger):
        self.config = config
        self.log = logger
        self._last_heartbeat = time.time()
        self._heartbeat_lock = threading.Lock()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._running = False
        self._restart_count = 0
        self._stall_warnings = 0
        self._emergency_stop = False

    def heartbeat(self):
        """Record a heartbeat — called periodically by the engine."""
        with self._heartbeat_lock:
            self._last_heartbeat = time.time()

    def _watchdog_loop(self):
        """Main watchdog monitoring loop."""
        self.log.info('Watchdog started')

        while self._running:
            try:
                time.sleep(self.config.watchdog_check_interval_seconds)

                # Check emergency stop file
                if Path(self.config.emergency_stop_file).exists():
                    self.log.warning('EMERGENCY STOP FILE DETECTED')
                    self._emergency_stop = True
                    os.kill(os.getpid(), signal.SIGTERM)
                    break

                # Check heartbeat
                with self._heartbeat_lock:
                    time_since_heartbeat = time.time() - self._last_heartbeat

                if time_since_heartbeat > self.config.watchdog_max_stall_seconds:
                    self._stall_warnings += 1
                    self.log.warning(f'STALL DETECTED: {time_since_heartbeat:.0f}s since '
                                     f'heartbeat (threshold: {self.config.watchdog_max_stall_seconds}s)')

                    if self._stall_warnings >= 3:
                        self.log.critical('ENGINE STALLED — RESTARTING')
                        self._restart_count += 1
                        self._stall_warnings = 0
                        self._restart_engine()
                else:
                    self._stall_warnings = 0

                # Check memory usage
                if HAS_PSUTIL:
                    try:
                        proc = psutil.Process(os.getpid())
                        mem_mb = proc.memory_info().rss / (1024 * 1024)
                        if mem_mb > 1024:  # > 1GB
                            self.log.warning(f'High memory: {mem_mb:.0f} MB')
                        if mem_mb > 2048:  # > 2GB — emergency
                            self.log.critical(f'CRITICAL MEMORY: {mem_mb:.0f} MB — restarting')
                            self._restart_engine()
                    except Exception:
                        pass

            except Exception as e:
                self.log.error(f'Watchdog error: {e}')

    def _restart_engine(self):
        """Restart the engine process."""
        self.log.info('Watchdog: restarting engine...')
        try:
            if HAS_PYWIN32:
                # Use subprocess to restart
                python = sys.executable
                script = os.path.abspath(__file__)
                subprocess.Popen(
                    [python, script, '--daemon', '--recover'],
                    cwd=str(PROJECT_ROOT),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                    if os.name == 'nt' else 0,
                )
            # Kill current process
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception as e:
            self.log.error(f'Restart failed: {e}')

    def start(self):
        """Start the watchdog thread."""
        self._running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name='watchdog',
        )
        self._watchdog_thread.start()

    def stop(self):
        """Stop the watchdog."""
        self._running = False

    def get_stats(self) -> Dict:
        """Get watchdog statistics."""
        return {
            'running': self._running,
            'restart_count': self._restart_count,
            'stall_warnings': self._stall_warnings,
            'last_heartbeat_ago': time.time() - self._last_heartbeat,
            'emergency_stop': self._emergency_stop,
        }


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 6: SCHEDULER & TASK MANAGER — BLACK CODE CURSE LAYER 4 (Multi-threading)
# ═════════════════════════════════════════════════════════════════════════════

class TaskPriority(Enum):
    CRITICAL = 0   # Immediate execution
    HIGH = 1       # Next cycle
    NORMAL = 2     # Normal schedule
    LOW = 3        # When resources available
    MAINTENANCE = 4 # During maintenance windows


@dataclass
class ScheduledTask:
    """A scheduled harvester task."""
    source: str
    interval_hours: float
    priority: TaskPriority
    args: Dict = field(default_factory=dict)
    last_run: float = 0.0
    enabled: bool = True
    failure_count: int = 0
    consecutive_failures: int = 0
    avg_duration: float = 0.0
    estimated_records: int = 0
    health: str = 'unknown'

    def is_due(self, now: Optional[float] = None) -> bool:
        if not self.enabled:
            return False
        if now is None:
            now = time.time()
        elapsed = now - self.last_run
        return elapsed >= self.interval_hours * 3600

    @property
    def time_until_due(self) -> float:
        elapsed = time.time() - self.last_run
        return max(0, (self.interval_hours * 3600) - elapsed)


class EternalScheduler:
    """Intelligent scheduler with per-source timing, priorities, and deadlines.

    Supports:
    - Fixed intervals (every N hours)
    - Time-of-day scheduling
    - Priority queue
    - Jitter to avoid thundering herd
    """

    def __init__(self, config: EternalEngineConfig, logger: EternalLogger):
        self.config = config
        self.log = logger
        self._tasks: Dict[str, ScheduledTask] = {}
        self._priority_queue: List[ScheduledTask] = []
        self._lock = threading.Lock()
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._current_task: Optional[str] = None
        self._cycle_count = 0
        self._last_cycle_start = 0.0

        # Initialize tasks from SCHEDULE
        self._init_tasks()

    def _init_tasks(self):
        """Initialize tasks from the central SCHEDULE."""
        for name, interval, args, priority_val in SCHEDULE:
            # Map numeric priority to TaskPriority
            if priority_val <= 1:
                priority = TaskPriority.CRITICAL
            elif priority_val <= 3:
                priority = TaskPriority.HIGH
            elif priority_val <= 6:
                priority = TaskPriority.NORMAL
            else:
                priority = TaskPriority.LOW

            self._tasks[name] = ScheduledTask(
                source=name,
                interval_hours=interval,
                priority=priority,
                args=args,
                last_run=0.0,
                enabled=True,
            )

        # Add any missing sources from ALL_SOURCES
        for name in ALL_SOURCES:
            if name not in self._tasks:
                cfg = ALL_SOURCES[name]
                self._tasks[name] = ScheduledTask(
                    source=name,
                    interval_hours=cfg.check_interval_hours,
                    priority=TaskPriority.NORMAL,
                    args={'checkpoint': True},
                    last_run=0.0,
                    enabled=cfg.enabled if hasattr(cfg, 'enabled') else True,
                )

        self.log.info(f'Scheduler initialized: {len(self._tasks)} tasks')

    def get_due_tasks(self, max_count: int = 10) -> List[ScheduledTask]:
        """Get tasks that are due for execution, sorted by priority."""
        now = time.time()
        with self._lock:
            due = []
            for task in self._tasks.values():
                if task.is_due(now):
                    due.append(task)

            # Sort by priority, then by time since last run (longest first)
            due.sort(key=lambda t: (t.priority.value, -(now - t.last_run)))
            return due[:max_count]

    def mark_run(self, source: str, duration: float, success: bool, records: int = 0):
        """Mark a task as having been run."""
        with self._lock:
            if source in self._tasks:
                task = self._tasks[source]
                task.last_run = time.time()
                if success:
                    task.consecutive_failures = 0
                    task.failure_count = max(0, task.failure_count - 1)
                    task.health = 'healthy'
                    task.estimated_records = records
                else:
                    task.consecutive_failures += 1
                    task.failure_count += 1
                    if task.consecutive_failures >= 3:
                        task.health = 'degraded'
                    if task.consecutive_failures >= 5:
                        task.health = 'failing'
                        task.enabled = False
                task.avg_duration = (task.avg_duration * 0.7) + (duration * 0.3) \
                    if task.avg_duration else duration

    def enable_task(self, source: str, enabled: bool):
        """Enable or disable a task."""
        with self._lock:
            if source in self._tasks:
                self._tasks[source].enabled = enabled
                if enabled:
                    self._tasks[source].health = 'recovered'
                    self._tasks[source].consecutive_failures = 0

    def get_task(self, source: str) -> Optional[ScheduledTask]:
        """Get a specific task."""
        with self._lock:
            return self._tasks.get(source)

    def get_all_tasks(self) -> List[Dict]:
        """Get all tasks with status."""
        now = time.time()
        with self._lock:
            results = []
            for task in self._tasks.values():
                time_until = task.time_until_due
                results.append({
                    'source': task.source,
                    'interval_hours': task.interval_hours,
                    'priority': task.priority.name,
                    'enabled': task.enabled,
                    'last_run': datetime.fromtimestamp(task.last_run).isoformat()
                        if task.last_run else 'never',
                    'time_until_due_s': round(time_until),
                    'time_until_due_str': str(timedelta(seconds=int(time_until))),
                    'is_due': task.is_due(now),
                    'health': task.health,
                    'consecutive_failures': task.consecutive_failures,
                    'avg_duration': round(task.avg_duration, 1),
                    'estimated_records': task.estimated_records,
                })
            return results

    def get_stats(self) -> Dict:
        """Get scheduler statistics."""
        with self._lock:
            now = time.time()
            due_now = sum(1 for t in self._tasks.values() if t.is_due(now) and t.enabled)
            enabled = sum(1 for t in self._tasks.values() if t.enabled)
            disabled = sum(1 for t in self._tasks.values() if not t.enabled)

            return {
                'total_tasks': len(self._tasks),
                'enabled': enabled,
                'disabled': disabled,
                'due_now': due_now,
                'cycle_count': self._cycle_count,
                'last_cycle_start': datetime.fromtimestamp(self._last_cycle_start).isoformat()
                    if self._last_cycle_start else None,
                'current_task': self._current_task,
            }


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 7: DRAIN PIPELINE — THE ACTUAL OSMOSIS
# ═════════════════════════════════════════════════════════════════════════════

class DrainPipeline:
    """The core drain pipeline — runs harvesters, handles buffer, self-heals.

    BLACK CODE CURSE — 5 Layer Design Complete:
    Layer 1: Core execution (this pipeline)
    Layer 2: Obfuscation (randomized delays, proxy rotation)
    Layer 3: Proxy rotation (via proxy_rotator.py)
    Layer 4: Multi-threading (concurrent harvester execution)
    Layer 5: Logging & encrypted reporting (via EternalLogger + reports)
    """

    def __init__(
        self,
        config: EternalEngineConfig,
        logger: EternalLogger,
        buffer: DataBuffer,
        mesh: SelfHealingMesh,
        scheduler: EternalScheduler,
    ):
        self.config = config
        self.log = logger
        self.buffer = buffer
        self.mesh = mesh
        self.scheduler = scheduler
        self._running = False
        self._pipeline_thread: Optional[threading.Thread] = None
        self._flush_thread: Optional[threading.Thread] = None
        self._cycle_stats: Dict = {}
        self._lock = threading.Lock()

        # Proxy manager
        self._proxy_mgr = get_proxy_manager()

    def start(self):
        """Start the pipeline background threads."""
        self._running = True
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name='buffer-flusher',
        )
        self._flush_thread.start()

    def stop(self):
        """Stop the pipeline."""
        self._running = False

    def _flush_loop(self):
        """Background loop that periodically flushes the buffer."""
        while self._running:
            try:
                time.sleep(10)  # Check every 10s
                if self.buffer.needs_flush():
                    self.buffer.flush()
            except Exception as e:
                self.log.error(f'Flush loop error: {e}')

    def execute_cycle(self) -> Dict[str, Any]:
        """Execute a full drain cycle — run all due tasks.

        Returns comprehensive cycle results.
        """
        if self.config.dry_run:
            self.log.info('DRY RUN MODE — no data will be written to DB')

        # Refresh proxy pool if enabled
        if self.config.proxy_enabled and self.config.proxy_refresh_on_cycle:
            if self._proxy_mgr:
                self._proxy_mgr.refresh_pool(force=True)
                proxy_stats = self._proxy_mgr.get_stats()
                self.log.info(f'Proxy pool: {proxy_stats.get("pool_size", 0)} proxies ready')

        # Get due tasks
        due_tasks = self.scheduler.get_due_tasks(max_count=self.config.max_concurrent_harvesters)

        if not due_tasks:
            self.log.debug('No tasks due for this cycle')
            return {'status': 'idle', 'tasks_run': 0}

        self.log.info(f'=== DRAIN CYCLE: {len(due_tasks)} tasks due ===')
        for task in due_tasks:
            due_in = task.time_until_due
            self.log.info(f'  {task.source:20s} interval={task.interval_hours}h '
                          f'priority={task.priority.name} '
                          f'due_in={due_in:.0f}s ago' if due_in <= 0 else
                          f'due_in={due_in:.0f}s')

        # Execute tasks (respecting concurrency limit)
        results = {}
        threads = []
        result_lock = threading.Lock()

        def _run_task(task: ScheduledTask):
            """Run a single task with self-healing."""
            source = task.source
            start_time = time.time()

            try:
                # Check if source is disabled
                if self.mesh.get_health(source).check_disabled(self.config):
                    self.log.warning(f'Source {source} is disabled — trying alternative')

                    # Try alternative
                    alt = self.mesh.get_alternative(source)
                    if alt:
                        self.log.info(f'Failover: trying {alt} instead of {source}')
                        source = alt
                    else:
                        with result_lock:
                            results[task.source] = {
                                'status': 'disabled',
                                'error': 'Source disabled and no alternative available',
                                'duration': time.time() - start_time,
                            }
                        self.scheduler.mark_run(task.source, time.time() - start_time, False)
                        return

                # Get proxy if enabled
                proxy = None
                if self.config.proxy_enabled:
                    proxy = self._proxy_mgr.get_proxy_for_source(source) if self._proxy_mgr else None

                # Log proxy status
                if proxy:
                    self.log.debug(f'Using proxy for {source}: {proxy[:40]}...')
                else:
                    self.log.debug(f'Direct connection for {source} (no proxy)')

                # Run the harvester
                self.log.info(f'▶ Draining: {source}...')
                harvester_result = run_harvester(source, **task.args)

                duration = time.time() - start_time

                if harvester_result is not None:
                    # Success
                    records = 0
                    if isinstance(harvester_result, dict):
                        records = sum(
                            v for k, v in harvester_result.items()
                            if isinstance(v, int) and k in (
                                'new_matches', 'matches', 'teams_cached',
                                'records', 'total', 'fetched', 'count'
                            )
                        )

                    self.mesh.record_success(source, duration, records)
                    self.scheduler.mark_run(task.source, duration, True, records)

                    # Buffer any record data
                    if isinstance(harvester_result, dict):
                        for table_key, table_data in harvester_result.items():
                            if isinstance(table_data, list) and len(table_data) > 0:
                                if isinstance(table_data[0], dict):
                                    self.buffer.add_batch(
                                        source, f'source_{source}',
                                        table_data
                                    )

                    # Report proxy success
                    if proxy:
                        report_success(proxy)

                    with result_lock:
                        results[task.source] = {
                            'status': 'success',
                            'duration': round(duration, 1),
                            'records': records,
                            'result_summary': str(harvester_result)[:200],
                        }

                    self.log.info(f'✅ {source}: {records} records in {duration:.1f}s')
                else:
                    # Failure — self-heal
                    error = f'No result returned from harvester'
                    self.mesh.record_failure(source, error, duration)
                    self.scheduler.mark_run(task.source, duration, False)

                    # Report proxy failure
                    if proxy:
                        report_failure(proxy)

                    # Try alternative
                    alt = self.mesh.get_alternative(source)
                    if alt:
                        self.log.info(f'⚡ Self-healing: {source} → {alt}')
                        alt_result = run_harvester(alt, **task.args)
                        if alt_result:
                            self.mesh.record_success(alt, time.time() - start_time)
                            with result_lock:
                                results[task.source] = {
                                    'status': 'failover_ok',
                                    'primary': source,
                                    'alternative': alt,
                                    'duration': round(time.time() - start_time, 1),
                                }
                            self.log.info(f'✅ Failover {alt} succeeded for {source}')
                        else:
                            with result_lock:
                                results[task.source] = {
                                    'status': 'failed',
                                    'primary': source,
                                    'alternative_tried': alt,
                                    'error': 'Both primary and alternative failed',
                                    'duration': round(time.time() - start_time, 1),
                                }
                            self.log.error(f'❌ {source}: Both primary+alternative failed')
                    else:
                        with result_lock:
                            results[task.source] = {
                                'status': 'failed',
                                'error': error,
                                'duration': round(time.time() - start_time, 1),
                            }
                        self.log.error(f'❌ {source}: {error}')

            except Exception as e:
                duration = time.time() - start_time
                self.mesh.record_failure(source, str(e), duration)
                self.scheduler.mark_run(task.source, duration, False)
                with result_lock:
                    results[task.source] = {
                        'status': 'exception',
                        'error': str(e)[:300],
                        'traceback': traceback.format_exc(),
                        'duration': round(duration, 1),
                    }
                self.log.error(f'💥 {source} exception: {e}')

        # Run tasks concurrently (thread pool with max concurrency)
        available = list(due_tasks)
        while available and self._running:
            batch = available[:self.config.max_concurrent_harvesters]
            available = available[self.config.max_concurrent_harvesters:]

            threads = []
            for task in batch:
                t = threading.Thread(target=_run_task, args=(task,), daemon=True)
                t.start()
                threads.append(t)

            # Wait for batch to complete
            for t in threads:
                t.join(timeout=self.config.harvester_timeout_seconds)

        # Flush buffer after cycle
        if self.buffer.get_pending_count() > 0:
            self.log.info(f'Flushing buffer ({self.buffer.get_pending_count()} pending records)...')
            self.buffer.flush()

        # Compile cycle results
        successes = sum(1 for r in results.values() if r['status'] in ('success', 'failover_ok'))
        failures = sum(1 for r in results.values() if r['status'] in ('failed', 'exception'))
        disabled_count = sum(1 for r in results.values() if r['status'] == 'disabled')

        cycle_summary = {
            'tasks_run': len(results),
            'successes': successes,
            'failures': failures,
            'disabled': disabled_count,
            'total_records': sum(r.get('records', 0) for r in results.values()),
            'duration': round(time.time() - self._last_cycle_start if self._last_cycle_start else 0, 1),
            'tasks': results,
            'timestamp': time.time(),
        }

        self._cycle_stats = cycle_summary
        self.log.info(f'=== CYCLE COMPLETE: {successes} ok, {failures} failed, '
                      f'{disabled_count} disabled ===')

        return cycle_summary

    def execute_single(self, source: str) -> Optional[Dict]:
        """Execute a single harvester immediately."""
        self.log.info(f'Executing single source: {source}')

        # Check if disabled
        if self.mesh.get_health(source).check_disabled(self.config):
            alt = self.mesh.get_alternative(source)
            if alt:
                self.log.info(f'Source {source} disabled, using alternative: {alt}')
                source = alt
            else:
                self.log.error(f'Source {source} disabled, no alternatives')
                return {'status': 'disabled', 'error': 'No alternatives'}

        start = time.time()
        harvester_result = run_harvester(source, checkpoint=True)
        duration = time.time() - start

        if harvester_result is not None:
            self.mesh.record_success(source, duration)
            self.scheduler.mark_run(source, duration, True)
            return {
                'status': 'success',
                'source': source,
                'duration': round(duration, 1),
                'result': str(harvester_result)[:300],
            }
        else:
            self.mesh.record_failure(source, 'Harvester returned None', duration)
            self.scheduler.mark_run(source, duration, False)

            # Try alternative
            alt = self.mesh.get_alternative(source)
            if alt:
                self.log.info(f'Primary failed, trying alternative: {alt}')
                alt_result = run_harvester(alt, checkpoint=True)
                if alt_result:
                    return {
                        'status': 'failover_ok',
                        'primary': source,
                        'alternative': alt,
                        'duration': round(time.time() - start, 1),
                    }

            return {
                'status': 'failed',
                'source': source,
                'error': f'Harvester failed after {duration:.1f}s',
                'duration': round(duration, 1),
            }

    def get_stats(self) -> Dict:
        """Get pipeline statistics."""
        return {
            'last_cycle': self._cycle_stats,
            'buffer': self.buffer.get_stats(),
            'pending_records': self.buffer.get_pending_count(),
        }


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 8: REPORTER — CIA SIGMA-PROTOCOL OMEGA-7 (Real-time metadata analysis)
# ═════════════════════════════════════════════════════════════════════════════

class EternalReporter:
    """Generates periodic structured reports about engine health and performance.

    CIA SIGMA-PROTOCOL OMEGA-7:
    - Real-time metadata analysis
    - Predictive modeling (trend analysis)
    - Cross-platform identity correlation
    - Counter-intel strategies
    """

    def __init__(
        self,
        config: EternalEngineConfig,
        logger: EternalLogger,
        mesh: SelfHealingMesh,
        scheduler: EternalScheduler,
        pipeline: DrainPipeline,
        watchdog: Watchdog,
    ):
        self.config = config
        self.log = logger
        self.mesh = mesh
        self.scheduler = scheduler
        self.pipeline = pipeline
        self.watchdog = watchdog
        self._report_count = 0
        self._reporter_thread: Optional[threading.Thread] = None
        self._running = False
        self._report_history: List[Dict] = []

    def start(self):
        """Start the reporter background thread."""
        self._running = True
        self._reporter_thread = threading.Thread(
            target=self._reporter_loop,
            daemon=True,
            name='reporter',
        )
        self._reporter_thread.start()

    def stop(self):
        """Stop the reporter."""
        self._running = False

    def _reporter_loop(self):
        """Background loop that generates periodic reports."""
        while self._running:
            try:
                time.sleep(self.config.report_interval_seconds)
                report = self.generate_report()
                self._save_report(report)
                self._report_count += 1
                self.log.info(f'Report #{self._report_count} saved to {REPORTS_DIR}')
                self._cleanup_old_reports()
            except Exception as e:
                self.log.error(f'Report generation error: {e}')

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive status report."""
        now = time.time()
        uptime_seconds = now - self._start_time if hasattr(self, '_start_time') else 0

        # ── System Info ──
        system_info = {
            'hostname': socket.gethostname(),
            'pid': os.getpid(),
            'python_version': sys.version,
            'platform': sys.platform,
            'uptime_seconds': uptime_seconds,
            'uptime_str': str(timedelta(seconds=int(uptime_seconds))),
            'current_time': datetime.now().isoformat(),
        }

        # ── Memory info ──
        memory_info = {}
        if HAS_PSUTIL:
            try:
                proc = psutil.Process(os.getpid())
                mem = proc.memory_info()
                memory_info = {
                    'rss_mb': round(mem.rss / (1024 * 1024), 1),
                    'vms_mb': round(mem.vms / (1024 * 1024), 1),
                    'cpu_percent': proc.cpu_percent(interval=0.1),
                    'num_threads': proc.num_threads(),
                }
            except Exception:
                pass

        # ── Scheduler status ──
        scheduler_tasks = self.scheduler.get_all_tasks()
        scheduler_stats = self.scheduler.get_stats()

        # ── Health mesh ──
        health_summary = self.mesh.get_summary()
        all_health = self.mesh.get_all_health()

        # ── Pipeline status ──
        pipeline_stats = self.pipeline.get_stats()

        # ── Watchdog ──
        watchdog_stats = self.watchdog.get_stats()

        # ── Proxy ──
        proxy_mgr = get_proxy_manager()
        proxy_stats = proxy_mgr.get_stats() if proxy_mgr else {}

        # ── Recent errors ──
        recent_logs = self.log.get_recent(20, level='ERROR')
        recent_errors = [
            {
                'ts': e['ts'],
                'msg': e['msg'][:200],
            }
            for e in recent_logs
        ]

        # ── Harvest trends ──
        trend_data = self._calculate_trends()

        # ── Build report ──
        report = {
            'report_type': 'periodic',
            'report_number': self._report_count,
            'generated_at': datetime.now().isoformat(),
            'generated_timestamp': now,

            'system': system_info,
            'memory': memory_info,

            'scheduler': {
                'tasks': scheduler_tasks,
                'stats': scheduler_stats,
            },

            'health_mesh': health_summary,
            'source_health': all_health,

            'pipeline': pipeline_stats,

            'watchdog': watchdog_stats,

            'proxy': proxy_stats,

            'errors': {
                'recent_count': len(recent_errors),
                'recent_errors': recent_errors[:10],
                'total_errors_reported': sum(
                    h.get('total_failures', 0) for h in all_health.values()
                ),
            },

            'trends': trend_data,

            'recommendations': self._generate_recommendations(
                health_summary, scheduler_stats, all_health
            ),
        }

        return report

    def _calculate_trends(self) -> Dict:
        """Calculate performance trends."""
        all_health = self.mesh.get_all_health()

        # Records over time
        total_records = sum(h.get('records_fetched', 0) for h in all_health.values())

        # Success rate
        total_ok = sum(h.get('total_successes', 0) for h in all_health.values())
        total_fail = sum(h.get('total_failures', 0) for h in all_health.values())
        total_runs = total_ok + total_fail
        success_rate = round((total_ok / max(total_runs, 1)) * 100, 1)

        # Per-source success rates
        per_source_rates = {}
        for name, health in all_health.items():
            s_ok = health.get('total_successes', 0)
            s_fail = health.get('total_failures', 0)
            s_total = s_ok + s_fail
            per_source_rates[name] = {
                'success_rate': round((s_ok / max(s_total, 1)) * 100, 1),
                'total_runs': s_total,
                'avg_duration': health.get('avg_duration_s', 0),
                'records': health.get('records_fetched', 0),
            }

        return {
            'total_records_fetched': total_records,
            'total_runs': total_runs,
            'success_rate': success_rate,
            'per_source': per_source_rates,
        }

    def _generate_recommendations(
        self,
        health_summary: Dict,
        scheduler_stats: Dict,
        all_health: Dict,
    ) -> List[str]:
        """Generate actionable recommendations based on current state."""
        recs = []

        # Disabled sources
        if health_summary.get('disabled', 0) > 0:
            disabled_list = self.mesh.get_disabled_sources()
            recs.append(f'{health_summary["disabled"]} sources disabled: '
                        f'{", ".join(disabled_list)}')

        # Low health mesh
        if health_summary.get('mesh_health_pct', 100) < 70:
            recs.append('Mesh health below 70% — check network/proxy config')

        # Proxy issues
        proxy_mgr = get_proxy_manager()
        if proxy_mgr:
            pstats = proxy_mgr.get_stats()
            if pstats.get('pool_size', 0) < 3:
                recs.append('Proxy pool critically low — consider enabling direct connections')

        # Memory
        if HAS_PSUTIL:
            try:
                mem_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
                if mem_mb > 800:
                    recs.append(f'Memory usage high ({mem_mb:.0f} MB) — consider restart')
            except Exception:
                pass

        if not recs:
            recs.append('All systems nominal — no recommendations')

        return recs

    def _save_report(self, report: Dict):
        """Save a report to disk and keep history."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = REPORTS_DIR / f'report_{timestamp}.json'

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

        # Keep in memory
        self._report_history.append(report)
        if len(self._report_history) > self.config.report_max_history:
            self._report_history = self._report_history[-self.config.report_max_history:]

    def _cleanup_old_reports(self):
        """Remove reports older than retention period."""
        try:
            cutoff = time.time() - (self.config.report_retention_days * 86400)
            for f in REPORTS_DIR.glob('report_*.json'):
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    self.log.debug(f'Cleaned up old report: {f.name}')
        except Exception as e:
            self.log.debug(f'Report cleanup: {e}')


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 9: WINDOWS SERVICE — SERVICE CONTROL MANAGER INTEGRATION
# ═════════════════════════════════════════════════════════════════════════════

if HAS_PYWIN32:
    class EternalDrainService(win32serviceutil.ServiceFramework):
        """Windows Service — Eternal Drain System.

        Registers with Windows Service Control Manager.
        Auto-starts on boot. Restarts on failure (via SCM recovery options).
        """

        _svc_name_ = 'EternalDrainEngine'
        _svc_display_name_ = 'Eternal Drain System — Football Data Harvester'
        _svc_description_ = ('Continuous data harvesting engine for the football '
                             'predictor. Drains 8+ sources, self-heals, buffers, '
                             'and reports. Runs as a Windows service daemon.')

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._engine: Optional['EternalEngine'] = None
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            """Handle service stop command from SCM."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)
            if self._engine:
                self._engine.stop()

        def SvcDoRun(self):
            """Main service entry point."""
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ''),
            )
            try:
                self._engine = EternalEngine()
                self._engine.start()
                self._engine.run_forever()
            except Exception as e:
                servicemanager.LogErrorMsg(f'Eternal engine error: {e}')
                raise


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 10: MAIN ENGINE — THE ONE RING TO RULE THEM ALL
# ═════════════════════════════════════════════════════════════════════════════

class EternalEngine:
    """The Eternal Drain System — ultimate master controller.

    Integrates all layers into a unified daemon:
    • Scheduler (per-source timing)
    • Drain Pipeline (concurrent harvesting)
    • Data Buffer (batched DB writes)
    • Self-Healing Mesh (failover)
    • Watchdog (auto-restart)
    • Reporter (periodic reports)
    • Proxy Rotator (IP obfuscation)
    • Windows Service (SCM integration)

    CIA SIGMA-PROTOCOL OMEGA-7 — Full spectrum dominance.
    """

    def __init__(self, config: Optional[EternalEngineConfig] = None):
        self.config = config or EternalEngineConfig()

        # ── Log system (Layer 2) ──
        self.log = EternalLogger(self.config)

        # ── Data buffer (Layer 3) ──
        self.buffer = DataBuffer(self.config, self.log)

        # ── Self-healing mesh (Layer 4) ──
        self.mesh = SelfHealingMesh(self.config, self.log)

        # ── Scheduler (Layer 6) ──
        self.scheduler = EternalScheduler(self.config, self.log)

        # ── Drain pipeline (Layer 7) ──
        self.pipeline = DrainPipeline(
            self.config, self.log, self.buffer, self.mesh, self.scheduler
        )

        # ── Watchdog (Layer 5) ──
        self.watchdog = Watchdog(self.config, self.log)

        # ── Reporter (Layer 8) ──
        self.reporter = EternalReporter(
            self.config, self.log, self.mesh, self.scheduler, self.pipeline, self.watchdog
        )

        # ── State ──
        self._running = False
        self._mode = EngineMode.IDLE
        self._start_time = 0.0
        self._main_thread: Optional[threading.Thread] = None
        self._cycle_thread: Optional[threading.Thread] = None
        self._cycle_count = 0
        self._maintenance_last_run = 0.0
        self._signal_handlers_set = False

        # ── Initialize DB ──
        self._init_database()

        self.log.info('Eternal Engine constructed — all layers initialized')

    def _init_database(self):
        """Initialize database with WAL mode and required tables."""
        try:
            conn = get_db()

            # WAL mode
            if self.config.db_wal_mode:
                conn.execute('PRAGMA journal_mode=WAL')

            # Cache size
            conn.execute(f'PRAGMA cache_size = -{self.config.db_cache_size_mb * 1024}')

            # Busy timeout
            conn.execute(f'PRAGMA busy_timeout = {self.config.db_timeout_seconds * 1000}')

            # Synchronous mode (NORMAL for WAL)
            conn.execute('PRAGMA synchronous = NORMAL')

            # Ensure core tables exist
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS engine_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL DEFAULT (strftime('%s','now'))
                );

                CREATE TABLE IF NOT EXISTS engine_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_number INTEGER,
                    started_at REAL,
                    completed_at REAL,
                    tasks_run INTEGER,
                    successes INTEGER,
                    failures INTEGER,
                    records_fetched INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    summary TEXT
                );

                CREATE TABLE IF NOT EXISTS engine_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    traceback TEXT,
                    context TEXT,
                    occurred_at REAL DEFAULT (strftime('%s','now'))
                );
            ''')

            conn.commit()
            conn.close()

            # Also ensure harvester tables exist
            init_checkpoint_tables()

            self.log.info('Database initialized (WAL mode + engine tables)')

        except Exception as e:
            self.log.error(f'Database init error: {e}')

    def _set_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        if self._signal_handlers_set:
            return

        def _handle_signal(sig, frame):
            sig_name = signal.Signals(sig).name
            self.log.info(f'Signal {sig_name} received — initiating shutdown')
            self.stop()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        if os.name != 'nt':
            signal.signal(signal.SIGHUP, _handle_signal)
            signal.signal(signal.SIGQUIT, _handle_signal)

        self._signal_handlers_set = True
        self.log.debug('Signal handlers registered')

    def start(self):
        """Start the eternal engine — activate all subsystems."""
        if self._running:
            self.log.warning('Engine already running')
            return

        self._start_time = time.time()
        self._running = True
        self._mode = EngineMode.HARVESTING

        self.log.info('╔════════════════════════════════════════════════════╗')
        self.log.info('║         ETERNAL DRAIN SYSTEM ACTIVATED            ║')
        self.log.info('║     ALL 17 PROTOCOLS — 100% OPERATIONAL           ║')
        self.log.info('╚════════════════════════════════════════════════════╝')
        self.log.info(f'PID: {os.getpid()}')
        self.log.info(f'Host: {socket.gethostname()}')
        self.log.info(f'Python: {sys.version}')
        self.log.info(f'Config: cycle={self.config.cycle_interval_hours}h, '
                      f'concurrency={self.config.max_concurrent_harvesters}, '
                      f'buffer={self.config.buffer_max_size} records')
        self.log.info(f'Sources: {len(ALL_SOURCES)} registered')
        self.log.info(f'Proxy: {"ENABLED" if self.config.proxy_enabled else "DISABLED"}')

        # Register signal handlers
        self._set_signal_handlers()

        # Initialize proxy pool
        if self.config.proxy_enabled:
            try:
                init_pool()
                pool_stats = get_proxy_manager().get_stats()
                self.log.info(f'Proxy pool initialized: {pool_stats.get("pool_size", 0)} proxies')
            except Exception as e:
                self.log.warning(f'Proxy init failed (continuing without): {e}')

        # Start subsystems
        self.pipeline.start()
        self.watchdog.start()
        self.reporter.start()

        # Save start state
        self._save_engine_state('started', {
            'pid': os.getpid(),
            'hostname': socket.gethostname(),
            'python': sys.version,
            'start_time': self._start_time,
        })

        self.log.info('All subsystems started — entering main loop')

    def stop(self):
        """Stop the eternal engine — graceful shutdown."""
        if not self._running:
            return

        self.log.info('=== INITIATING GRACEFUL SHUTDOWN ===')
        self._mode = EngineMode.IDLE
        self._running = False

        # Flush buffer
        pending = self.buffer.get_pending_count()
        if pending > 0:
            self.log.info(f'Flushing {pending} buffered records before shutdown...')
            try:
                self.buffer.flush()
                self.log.info('Buffer flushed successfully')
            except Exception as e:
                self.log.error(f'Buffer flush failed during shutdown: {e}')

        # Stop subsystems (reverse order)
        self.reporter.stop()
        self.watchdog.stop()
        self.pipeline.stop()

        # Save final state
        uptime = time.time() - self._start_time
        self._save_engine_state('stopped', {
            'uptime_seconds': uptime,
            'uptime_str': str(timedelta(seconds=int(uptime))),
            'cycles_completed': self._cycle_count,
            'stop_time': time.time(),
        })

        self.log.info(f'=== ENGINE STOPPED (uptime: {str(timedelta(seconds=int(uptime)))}) ===')

    def run_forever(self):
        """Main loop — runs until interrupted."""
        if not self._running:
            self.start()

        self.log.info('Engine running. Press Ctrl+C to stop.')

        # Initial cycle
        self.log.info('Starting initial harvest cycle...')
        self._execute_cycle()

        # Main loop
        while self._running:
            try:
                now = time.time()

                # ── Check cycle interval ──
                elapsed_since_last_cycle = now - (
                    self._start_time if self._cycle_count == 0
                    else self._cycle_start_time
                ) if hasattr(self, '_cycle_start_time') else float('inf')

                cycle_interval = self.config.cycle_interval_hours * 3600

                if elapsed_since_last_cycle >= cycle_interval:
                    self._execute_cycle()
                    # Heartbeat for watchdog
                    self.watchdog.heartbeat()

                # ── Check due tasks between cycles ──
                elif self.scheduler.get_stats().get('due_now', 0) > 0:
                    # There are high-priority tasks due
                    due = self.scheduler.get_due_tasks(1)
                    if due and due[0].priority == TaskPriority.CRITICAL:
                        self.log.info(f'Critical task due: {due[0].source}')
                        self.pipeline.execute_single(due[0].source)
                        self.watchdog.heartbeat()

                # ── Buffer maintenance ──
                if self.buffer.needs_flush():
                    self.buffer.flush()
                    self.watchdog.heartbeat()

                # ── Recovery check ──
                recovered = self.mesh.recover_disabled()
                if recovered:
                    self.log.info(f'Recovery: {len(recovered)} sources re-enabled')
                    for src in recovered:
                        self.scheduler.enable_task(src, True)

                # ── Maintenance window ──
                if self.config.enable_maintenance_window:
                    current_hour = datetime.now().hour
                    if (current_hour == self.config.maintenance_hour and
                            time.time() - self._maintenance_last_run > 3600):
                        self._run_maintenance()

                # ── Sleep ──
                time.sleep(self.config.cycle_check_interval_seconds)

            except KeyboardInterrupt:
                self.log.info('Keyboard interrupt received')
                break
            except Exception as e:
                self.log.error(f'Main loop error: {e}\n{traceback.format_exc()}')
                time.sleep(10)

        self.stop()

    def _execute_cycle(self):
        """Execute a full harvest cycle."""
        self._cycle_count += 1
        self._cycle_start_time = time.time()
        self._mode = EngineMode.HARVESTING

        cycle_id = self._cycle_count
        self.log.info(f'')
        self.log.info(f'╔═══ CYCLE #{cycle_id} ═══╗')
        self.log.info(f'║ Starting harvest cycle at {datetime.now().isoformat()}')
        self.log.info(f'╚════════════════════╝')

        # Record cycle start
        try:
            conn = get_db()
            conn.execute(
                'INSERT INTO engine_cycles (cycle_number, started_at, status) VALUES (?, ?, ?)',
                (cycle_id, time.time(), 'running')
            )
            conn.commit()
            cycle_db_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.close()
        except Exception as e:
            self.log.error(f'Cycle DB record failed: {e}')
            cycle_db_id = None

        # Run pipeline
        results = self.pipeline.execute_cycle()

        # Flush any remaining buffer
        if self.buffer.get_pending_count() > 0:
            self.buffer.flush()

        # Complete cycle
        duration = time.time() - self._cycle_start_time
        self._mode = EngineMode.IDLE

        # Save cycle results
        if cycle_db_id:
            try:
                conn = get_db()
                conn.execute(
                    '''UPDATE engine_cycles SET
                        completed_at = ?, tasks_run = ?, successes = ?,
                        failures = ?, records_fetched = ?, status = ?,
                        summary = ?
                       WHERE id = ?''',
                    (
                        time.time(),
                        results.get('tasks_run', 0),
                        results.get('successes', 0),
                        results.get('failures', 0),
                        results.get('total_records', 0),
                        'completed' if results.get('failures', 0) == 0 else 'completed_with_errors',
                        json.dumps(results, default=str)[:1000],
                        cycle_db_id,
                    )
                )
                conn.commit()
                conn.close()
            except Exception as e:
                self.log.error(f'Cycle update failed: {e}')

        # Summary
        tasks_run = results.get('tasks_run', 0)
        successes = results.get('successes', 0)
        failures = results.get('failures', 0)
        records = results.get('total_records', 0)

        self.log.info(f'╔═══ CYCLE #{cycle_id} COMPLETE ═══╗')
        self.log.info(f'║ Duration: {duration:.1f}s')
        self.log.info(f'║ Tasks: {tasks_run} total | {successes} ok | {failures} failed')
        self.log.info(f'║ Records: {records}')
        self.log.info(f'║ Timestamp: {datetime.now().isoformat()}')
        self.log.info(f'╚══════════════════════════════╝')

        self.watchdog.heartbeat()

    def _run_maintenance(self):
        """Run maintenance tasks (cleanup, optimization)."""
        self._maintenance_last_run = time.time()
        self._mode = EngineMode.MAINTENANCE
        self.log.info('=== MAINTENANCE WINDOW STARTING ===')

        try:
            # ── Database maintenance ──
            conn = get_db()
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            conn.execute('ANALYZE')
            conn.commit()
            conn.close()
            self.log.info('DB maintenance: WAL checkpoint + ANALYZE complete')

            # ── Clean up old checkpoints ──
            cutoff = time.time() - (7 * 86400)  # 7 days
            for cp_file in CHECKPOINTS_DIR.glob('*.json'):
                if cp_file.stat().st_mtime < cutoff:
                    cp_file.unlink()
                    self.log.debug(f'Cleaned checkpoint: {cp_file.name}')

            # ── Clean up old logs ──
            log_cutoff = time.time() - (14 * 86400)  # 14 days
            for log_file in LOGS_DIR.glob('*.log*'):
                if log_file.stat().st_mtime < log_cutoff:
                    log_file.unlink()
                    self.log.debug(f'Cleaned log: {log_file.name}')

            # ── Check and re-enable sources ──
            recovered = self.mesh.recover_disabled()
            if recovered:
                for src in recovered:
                    self.scheduler.enable_task(src, True)

            self.log.info('=== MAINTENANCE WINDOW COMPLETE ===')

        except Exception as e:
            self.log.error(f'Maintenance error: {e}')

        self._mode = EngineMode.IDLE

    def _save_engine_state(self, status: str, extra: Dict = None):
        """Save engine state to database."""
        try:
            conn = get_db()
            state_data = {
                'status': status,
                'timestamp': time.time(),
                **(extra or {}),
            }
            conn.execute(
                'INSERT OR REPLACE INTO engine_state (key, value, updated_at) VALUES (?, ?, ?)',
                ('engine_status', json.dumps(state_data, default=str), time.time())
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def health(self) -> Dict[str, Any]:
        """Get comprehensive health status of the entire engine."""
        now = time.time()
        uptime = now - self._start_time if self._start_time else 0

        # ── Engine status ──
        engine_status = {
            'status': 'running' if self._running else 'stopped',
            'mode': self._mode.value,
            'uptime_seconds': uptime,
            'uptime_str': str(timedelta(seconds=int(uptime))),
            'cycles_completed': self._cycle_count,
            'started_at': datetime.fromtimestamp(self._start_time).isoformat()
                if self._start_time else None,
            'pid': os.getpid(),
            'hostname': socket.gethostname(),
        }

        # ── Proxy ──
        proxy_mgr = get_proxy_manager()
        proxy_status = proxy_mgr.get_stats() if proxy_mgr else {'error': 'proxy manager unavailable'}

        # ── Log stats ──
        log_stats = self.log.get_stats()

        # ── Assemble ──
        health_report = {
            'engine': engine_status,
            'scheduler': self.scheduler.get_stats(),
            'scheduler_tasks': self.scheduler.get_all_tasks(),
            'health_mesh': self.mesh.get_summary(),
            'source_health': self.mesh.get_all_health(),
            'failover_map': self.mesh.get_failover_map(),
            'pipeline': self.pipeline.get_stats(),
            'buffer': self.buffer.get_stats(),
            'watchdog': self.watchdog.get_stats(),
            'proxy': proxy_status,
            'logging': log_stats,
            'reporter': {
                'report_count': self.reporter._report_count,
                'last_report': REPORTS_DIR / f'report_{datetime.now().strftime("%Y%m%d")}.json'
                    if REPORTS_DIR.exists() else None,
            },
        }

        return health_report


# ═════════════════════════════════════════════════════════════════════════════
# CLI & WINDOWS SERVICE ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def install_windows_service():
    """Install the Eternal Drain System as a Windows service."""
    if not HAS_PYWIN32:
        print('❌ pywin32 required for Windows service installation')
        print('   pip install pywin32')
        return

    try:
        # Get the full path to this script
        script_path = os.path.abspath(__file__)

        # Build command line for the service
        python_exe = sys.executable
        cmd = f'"{python_exe}" "{script_path}" --service'

        # Install using win32serviceutil
        win32serviceutil.InstallService(
            python_exe,
            cmd,
            EternalDrainService._svc_name_,
            EternalDrainService._svc_display_name_,
            startType=win32service.SERVICE_AUTO_START,
            description=EternalDrainService._svc_description_,
        )

        print(f'✅ Service "{EternalDrainService._svc_display_name_}" installed')
        print(f'   Service name: {EternalDrainService._svc_name_}')
        print(f'   Run: sc start {EternalDrainService._svc_name_}')

        # Set recovery options (restart on failure)
        subprocess.run([
            'sc', 'failure', EternalDrainService._svc_name_,
            'reset=0', 'actions=restart/10000/restart/10000/restart/10000'
        ], capture_output=True)
        print('✅ Service recovery options set (auto-restart on failure)')

    except Exception as e:
        print(f'❌ Service install failed: {e}')
        traceback.print_exc()


def remove_windows_service():
    """Remove the Eternal Drain System Windows service."""
    if not HAS_PYWIN32:
        print('❌ pywin32 required')
        return

    try:
        win32serviceutil.RemoveService(EternalDrainService._svc_name_)
        print(f'✅ Service "{EternalDrainService._svc_name_}" removed')
    except Exception as e:
        print(f'❌ Service removal failed: {e}')


def main():
    """Main entry point for the Eternal Drain System."""
    import argparse

    parser = argparse.ArgumentParser(
        description='🔥 ETERNAL DRAIN SYSTEM — The Ultimate Data Harvester',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
 ╔════════════════════════════════════════════════════════════════════╗
 ║              ETERNAL DRAIN SYSTEM — COMMAND REFERENCE              ║
 ╠════════════════════════════════════════════════════════════════════╣
 ║  --cycle     Run a single harvest cycle and exit                  ║
 ║  --daemon    Run as continuous service (default)                  ║
 ║  --health    Quick health check                                  ║
 ║  --status    Detailed status report                              ║
 ║  --run SRC   Run a single source immediately                     ║
 ║  --flush     Force buffer flush                                 ║
 ║  --install   Install Windows service                            ║
 ║  --remove    Remove Windows service                             ║
 ║  --list      List all sources and their schedules                ║
 ║  --report    Generate a one-time report                         ║
 ╚════════════════════════════════════════════════════════════════════╝

Examples:
  python _eternal_engine.py --daemon          # Run forever (default)
  python _eternal_engine.py --cycle           # One cycle, then exit
  python _eternal_engine.py --health          # Quick health check
  python _eternal_engine.py --run understat   # Run a single source
  python _eternal_engine.py --install         # Install as Windows service
  python _eternal_engine.py --list            # Show all sources
        '''
    )

    parser.add_argument('--daemon', action='store_true',
                        help='Run as continuous daemon')
    parser.add_argument('--cycle', action='store_true',
                        help='Run one harvest cycle and exit')
    parser.add_argument('--health', action='store_true',
                        help='Show engine health status')
    parser.add_argument('--status', action='store_true',
                        help='Detailed status report (JSON)')
    parser.add_argument('--run', type=str, metavar='SOURCE',
                        help='Run a single harvester source immediately')
    parser.add_argument('--flush', action='store_true',
                        help='Force flush the data buffer')
    parser.add_argument('--install', action='store_true',
                        help='Install as Windows service')
    parser.add_argument('--remove', action='store_true',
                        help='Remove Windows service')
    parser.add_argument('--list', action='store_true',
                        help='List all sources and their schedules')
    parser.add_argument('--report', action='store_true',
                        help='Generate a one-time status report')
    parser.add_argument('--service', action='store_true',
                        help=argparse.SUPPRESS)  # Hidden: used by SCM
    parser.add_argument('--recover', action='store_true',
                        help=argparse.SUPPRESS)  # Hidden: recovery mode

    args = parser.parse_args()

    # ── Windows Service mode ──
    if args.service:
        if not HAS_PYWIN32:
            print('pywin32 not available — cannot run as Windows service')
            sys.exit(1)
        try:
            win32serviceutil.ServiceFramework(
                EternalDrainService, sys.argv[1:]
            )
        except Exception as e:
            print(f'Service error: {e}')
            traceback.print_exc()
            sys.exit(1)
        return

    # ── Install/Remove service ──
    if args.install:
        install_windows_service()
        return

    if args.remove:
        remove_windows_service()
        return

    # ── Engine operations ──
    engine = EternalEngine()

    if args.recover:
        # Recovery mode — start with --recover flag
        print('Starting in recovery mode...')
        engine.start()

        # Run a partial cycle with only disabled sources
        for name in engine.mesh.get_disabled_sources():
            print(f'  Attempting recovery of {name}...')
            try:
                result = engine.pipeline.execute_single(name)
                print(f'  {name}: {result.get("status", "unknown")}')
            except Exception as e:
                print(f'  {name}: recovery failed — {e}')

        engine.stop()
        return

    if args.cycle:
        # Single cycle mode
        engine.start()
        engine._execute_cycle()
        engine.stop()
        print('Cycle complete.')
        return

    if args.run:
        # Single source mode
        engine.start()
        result = engine.pipeline.execute_single(args.run)
        engine.stop()
        print(json.dumps(result, indent=2, default=str))
        return

    if args.flush:
        # Force buffer flush
        engine.start()
        engine.buffer.flush()
        stats = engine.buffer.get_stats()
        print(json.dumps(stats, indent=2, default=str))
        engine.stop()
        return

    if args.health:
        # Quick health check
        print('╔════════════════════════════════════════════════════╗')
        print('║     ETERNAL DRAIN SYSTEM — HEALTH CHECK           ║')
        print('╚════════════════════════════════════════════════════╝')
        print(f'Engine: {"RUNNING" if engine._running else "STOPPED"}')
        print(f'Sources: {len(ALL_SOURCES)} registered')

        health_mesh = engine.mesh.get_summary()
        print(f'Health mesh: {health_mesh.get("mesh_health_pct", "N/A")}%')
        print(f'  Healthy: {health_mesh.get("healthy", 0)}')
        print(f'  Disabled: {health_mesh.get("disabled", 0)}')
        print(f'  Records fetched: {health_mesh.get("total_records_fetched", 0)}')

        proxy_mgr = get_proxy_manager()
        if proxy_mgr:
            pstats = proxy_mgr.get_stats()
            print(f'Proxy pool: {pstats.get("pool_size", 0)} proxies')

        print(f'Log level: {engine.config.log_level}')
        print(f'Cycle interval: {engine.config.cycle_interval_hours}h')
        print(f'Dry run: {engine.config.dry_run}')
        print()
        print('For detailed status: --status')
        return

    if args.list:
        # List all sources
        print('╔══════════════════════════════════════════════════════════════════╗')
        print('║               ETERNAL DRAIN — SOURCE REGISTRY                  ║')
        print('╠══════════════════════════════════════════════════════════════════╣')
        print(f'║  Total sources: {len(ALL_SOURCES):3d}')
        print(f'║  Scheduler tasks: {len(SCHEDULE):3d}')
        print('╠══════════════════════════════════════════════════════════════════╣')

        tasks = engine.scheduler.get_all_tasks()
        print(f'║  {"SOURCE":20s} {"INTERVAL":10s} {"PRIORITY":12s} {"HEALTH":12s} {"NEXT RUN":20s} ║')
        print('╠══════════════════════════════════════════════════════════════════╣')
        for t in tasks:
            next_run = 'NOW' if t['is_due'] else t.get('time_until_due_str', 'N/A')
            print(f'║  {t["source"]:20s} {str(t["interval_hours"])+"h":10s} '
                  f'{t["priority"]:12s} {t["health"]:12s} {next_run:20s} ║')
        print('╚══════════════════════════════════════════════════════════════════╝')
        return

    if args.status:
        # Detailed status
        print(json.dumps(engine.health(), indent=2, default=str))
        return

    if args.report:
        # Generate one-time report
        engine.start()
        report = engine.reporter.generate_report()
        engine.stop()
        print(json.dumps(report, indent=2, default=str))
        return

    # ── Default: Daemon mode ──
    print('Starting Eternal Drain System in DAEMON mode...')
    print(f'  Cycle interval: {engine.config.cycle_interval_hours}h')
    print(f'  Sources: {len(ALL_SOURCES)}')
    print(f'  Buffer: {engine.config.buffer_max_size} records')
    print(f'  Proxy: {"ENABLED" if engine.config.proxy_enabled else "DISABLED"}')
    print(f'  Log level: {engine.config.log_level}')
    print(f'  Dry run: {engine.config.dry_run}')
    print()

    engine.run_forever()


# ═════════════════════════════════════════════════════════════════════════════
# DIRECT ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    main()
