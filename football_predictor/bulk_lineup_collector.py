#!/usr/bin/env python3
"""
bulk_lineup_collector.py — Massive-scale SofaScore lineup collector.

Fetches lineups from SofaScore API for ALL historical matches that have
positive event IDs (real SofaScore match IDs) and are missing from sofa_lineups.

Target: 208,843 missing lineups → 50%+ coverage (currently 8.9%)

Strategy:
  - Focus on IDs >= 10,000,000 (recent matches most likely to have data)
  - Use threaded workers with rate limiting
  - Resume from last checkpoint
  - Store lineups incrementally in sofa_lineups table

Usage:
    python bulk_lineup_collector.py               # Run full collection
    python bulk_lineup_collector.py --quick        # Only 2025-2026 matches
    python bulk_lineup_collector.py --dry-run      # Count only, no fetch
    python bulk_lineup_collector.py --workers 5    # Custom worker count
    python bulk_lineup_collector.py --limit 1000   # Max matches to fetch
"""

import sys
import os
import json
import time
import sqlite3
import threading
import argparse
from datetime import datetime, timezone
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows console encoding
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add parent to path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Configuration ───────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scrape_cache.db')
PROGRESS_TABLE = 'lineup_backfill_progress'  # Tracks which IDs we've processed

# SofaScore rate limiting
MIN_DELAY_BETWEEN_REQUESTS = 0.6  # seconds
MAX_WORKERS = 3  # concurrent fetchers

# Target data
MIN_TARGET_ID = 10_000_000  # Only process IDs >= this (real SofaScore IDs)
MAX_TARGET_ID = 17_000_000  # Upper bound
MIN_TARGET_YEAR = 2021  # Only process matches from this year onwards

# Progress checkpoint
CHECKPOINT_INTERVAL = 100  # Save progress every N matches

# ─── Progress Tracking ───────────────────────────────────────────────────────

_progress_lock = threading.Lock()


def _init_progress_table(conn):
    """Create the progress tracking table if it doesn't exist."""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {PROGRESS_TABLE} (
            event_id INTEGER PRIMARY KEY,
            fetched_at TEXT,
            status TEXT DEFAULT 'done'
        )
    """)
    conn.commit()


def _get_processed_ids(conn):
    """Return set of event_ids already processed."""
    try:
        rows = conn.execute(f"SELECT event_id FROM {PROGRESS_TABLE} WHERE status='done'").fetchall()
        return {r[0] for r in rows}
    except sqlite3.OperationalError:
        _init_progress_table(conn)
        return set()


def _mark_processed(conn, event_id, status='done'):
    """Record a processed event ID."""
    conn.execute(
        f"INSERT OR REPLACE INTO {PROGRESS_TABLE} (event_id, fetched_at, status) VALUES (?, ?, ?)",
        (event_id, datetime.now(timezone.utc).isoformat(), status)
    )


# ─── Database helpers ────────────────────────────────────────────────────────

def get_db_connection():
    """Get a thread-safe connection to the database."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_missing_lineup_ids(conn, min_id=MIN_TARGET_ID, max_id=MAX_TARGET_ID,
                           min_date=None, limit=None, exclude_ids=None):
    """
    Get all positive event IDs from sofa_historical_results that are NOT yet
    in sofa_lineups and NOT in the progress table.
    """
    if exclude_ids is None:
        exclude_ids = set()

    conditions = ["h.id >= ?", "h.id <= ?", "h.id > 0"]
    params = [min_id, max_id]

    if min_date:
        conditions.append("h.date >= ?")
        params.append(min_date)
    else:
        # Default: skip very old matches with wrong ID mappings
        conditions.append("h.date >= ?")
        params.append(f"{MIN_TARGET_YEAR}-01-01")

    # Exclude already-processed from progress table
    # We handle this in Python for flexibility

    query = f"""
        SELECT h.id, h.home_team, h.away_team, h.date, h.tournament
        FROM sofa_historical_results h
        LEFT JOIN sofa_lineups l ON h.id = l.event_id
        WHERE {' AND '.join(conditions)}
          AND l.event_id IS NULL
        ORDER BY h.id ASC
    """

    if limit:
        query += f" LIMIT {limit}"

    rows = conn.execute(query, params).fetchall()

    # Filter out already-processed IDs
    result = []
    for r in rows:
        if r[0] in exclude_ids:
            continue
        # Also exclude negative IDs (shouldn't happen with our WHERE but safety)
        if r[0] <= 0:
            continue
        result.append(r)

    return result


def store_lineup(conn, event_id, lineup_data):
    """
    Store lineup data in sofa_lineups table.
    Returns True if stored successfully, False if no usable data.
    """
    home = lineup_data.get('home', {})
    away = lineup_data.get('away', {})

    home_formation = home.get('formation', '')
    away_formation = away.get('formation', '')
    home_players = home.get('players', [])
    away_players = away.get('players', [])
    confirmed = 1 if lineup_data.get('confirmed') else 0

    # Skip if no formation data at all
    if not home_formation and not away_formation:
        return False

    conn.execute("""
        INSERT OR REPLACE INTO sofa_lineups
        (event_id, home_formation, away_formation,
         home_players_json, away_players_json, confirmed)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        event_id,
        home_formation,
        away_formation,
        json.dumps(home_players, default=str) if home_players else None,
        json.dumps(away_players, default=str) if away_players else None,
        confirmed
    ))
    return True


# ─── Fetch Worker ────────────────────────────────────────────────────────────

class RateLimiter:
    """Simple rate limiter that ensures minimum delay between requests."""

    def __init__(self, min_interval):
        self.min_interval = min_interval
        self._last_time = 0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_time = time.time()


def fetch_and_store(event_id, home_team, away_team, match_date, tournament,
                    rate_limiter, stats_counter, max_retries=2):
    """
    Fetch lineups for a single match and store them.
    Retries up to max_retries times on transient errors.
    Returns (event_id, success, message).
    """
    from sofascore_scraper import get_match_lineups
    import time

    for attempt in range(1 + max_retries):
        rate_limiter.wait()

        try:
            lu = get_match_lineups(event_id)
            if not lu:
                if attempt < max_retries:
                    time.sleep(1.0)  # Wait a bit before retry
                    continue
                stats_counter['miss_no_data'] += 1
                return (event_id, False, 'no_data')

            if not lu.get('home', {}).get('formation') and not lu.get('away', {}).get('formation'):
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                stats_counter['miss_no_formation'] += 1
                return (event_id, False, 'no_formation')

            conn = get_db_connection()
            try:
                stored = store_lineup(conn, event_id, lu)
                conn.commit()
                if stored:
                    stats_counter['success'] += 1
                    home_f = lu.get('home', {}).get('formation', '?')
                    away_f = lu.get('away', {}).get('formation', '?')
                    hp = len(lu.get('home', {}).get('players', []))
                    ap = len(lu.get('away', {}).get('players', []))
                    return (event_id, True,
                            f'{home_f} vs {away_f} ({hp}/{ap} players)')
                else:
                    stats_counter['miss_empty'] += 1
                    return (event_id, False, 'empty_lineup')
            finally:
                conn.close()

        except Exception as e:
            if attempt < max_retries:
                time.sleep(2.0)
                continue
            stats_counter['error'] += 1
            return (event_id, False, f'error: {str(e)[:100]}')

    return (event_id, False, 'max_retries_exceeded')


# ─── Main Collection Loop ────────────────────────────────────────────────────

def collect_lineups(workers=MAX_WORKERS, limit=None, quick=False, dry_run=False,
                    min_id=MIN_TARGET_ID):
    """Main lineup collection function."""
    print("=" * 65)
    print("      BULK LINEUP COLLECTOR — SofaScore Lineup Backfill")
    print("=" * 65)
    print()

    # ── Analyze database ────────────────────────────────────────────────
    conn = get_db_connection()
    try:
        total_hist = conn.execute(
            "SELECT COUNT(*) FROM sofa_historical_results WHERE id > 0"
        ).fetchone()[0]
        total_lineups = conn.execute(
            "SELECT COUNT(*) FROM sofa_lineups"
        ).fetchone()[0]
        with_players = conn.execute(
            "SELECT COUNT(*) FROM sofa_lineups WHERE home_players_json IS NOT NULL"
        ).fetchone()[0]

        print(f"📊 Database Status:")
        print(f"   Historical matches (positive IDs): {total_hist:>8,}")
        print(f"   Existing lineups (sofa_lineups):   {total_lineups:>8,}")
        print(f"   Lineups with player data:          {with_players:>8,}")
        print(f"   Coverage:                          {total_lineups/total_hist*100:>5.1f}%")
        print()

        # ── Initialize progress tracking ────────────────────────────────
        _init_progress_table(conn)
        processed_ids = _get_processed_ids(conn)
        print(f"📝 Already processed (from progress table): {len(processed_ids):,}")
        print()

        # ── Get missing IDs ─────────────────────────────────────────────
        min_date = '2025-01-01' if quick else None  # default filter in get_missing_lineup_ids
        missing = get_missing_lineup_ids(
            conn,
            min_id=min_id,
            min_date=min_date,
            limit=limit,
            exclude_ids=processed_ids
        )
        print(f"🎯 Target matches to fetch: {len(missing):,}")
        if quick:
            print(f"   (Quick mode: 2025-2026 matches only)")
        print()

        # Show breakdown by year
        year_counts = {}
        for r in missing:
            yr = r[3][:4] if r[3] else 'unknown'
            year_counts[yr] = year_counts.get(yr, 0) + 1
        if year_counts:
            print("   Breakdown by year:")
            for yr in sorted(year_counts.keys()):
                print(f"     {yr}: {year_counts[yr]:,}")
        print()

        if dry_run or len(missing) == 0:
            if len(missing) == 0:
                print("✅ No matches to fetch! All caught up.")
            else:
                print(f"🔍 Dry-run complete. Would fetch {len(missing):,} matches.")
            return

        # ── Confirm ─────────────────────────────────────────────────────
        estimated_time = (len(missing) * MIN_DELAY_BETWEEN_REQUESTS) / workers / 60
        print(f"⏱️  Estimated time: {estimated_time:.0f} minutes "
              f"({estimated_time/60:.1f} hours) with {workers} workers")
        print(f"⚡ Rate limit: {MIN_DELAY_BETWEEN_REQUESTS}s between requests")
        print()

        # ── Run Collection ──────────────────────────────────────────────
        stats = {'success': 0, 'miss_no_data': 0, 'miss_no_formation': 0,
                 'miss_empty': 0, 'error': 0, 'skipped': 0}
        stats_lock = threading.Lock()

        def safe_stats_inc(key):
            with stats_lock:
                stats[key] = stats.get(key, 0) + 1

        rate_limiter = RateLimiter(MIN_DELAY_BETWEEN_REQUESTS)
        local_processed = set()

        def worker_callback(future):
            """Callback when a fetch completes."""
            try:
                event_id, success, message = future.result()
                # Stats are already counted inside fetch_and_store
                # Just store progress
                conn2 = get_db_connection()
                try:
                    _mark_processed(conn2, event_id,
                                    'done' if success else 'skipped')
                    conn2.commit()
                    local_processed.add(event_id)
                finally:
                    conn2.close()
            except Exception as e:
                pass

        start_time = time.time()
        batch_submitted = 0
        last_report = start_time
        completed_count = 0
        completed_lock = threading.Lock()

        def track_completion(future):
            with completed_lock:
                nonlocal completed_count
                completed_count += 1
            worker_callback(future)

        print("🚀 Starting collection...")
        print()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []

            for match in missing:
                event_id, home_team, away_team, match_date, tournament = match

                future = executor.submit(
                    fetch_and_store,
                    event_id, home_team, away_team, match_date, tournament,
                    rate_limiter, stats
                )
                future.add_done_callback(track_completion)
                futures.append(future)

                batch_submitted += 1

                # Progress report (based on completed count)
                now = time.time()
                if (now - last_report) >= 15 or batch_submitted == len(missing):
                    with completed_lock:
                        done = completed_count
                    elapsed = now - start_time
                    rate = done / elapsed if elapsed > 0 else 0
                    remaining = len(missing) - done
                    eta = remaining / rate if rate > 0 else 0
                    with stats_lock:
                        print(
                            f"  [{done:>6,}/{len(missing):>6,}] "
                            f"✅ {stats['success']:,} | "
                            f"❌ {stats['error']:,} | "
                            f"⏭️ {stats['miss_no_data']+stats['miss_no_formation']+stats['miss_empty']:,} | "
                            f"⏱️ {elapsed/60:.0f}m, "
                            f"ETA: {eta/60:.0f}m"
                        )
                    last_report = now

                # Stop if we've hit our limit
                if limit and batch_submitted >= limit:
                    print(f"\n⏹️  Reached limit of {limit} matches. Stopping.")
                    break

        # ── Final Report ────────────────────────────────────────────────
        total_time = time.time() - start_time
        total_attempted = batch_submitted

        print()
        print("═" * 60)
        print("📊 COLLECTION COMPLETE")
        print("═" * 60)
        print(f"   Total attempted:     {total_attempted:>8,}")
        print(f"   Successful:          {stats['success']:>8,}")
        print(f"   Errors:              {stats['error']:>8,}")
        print(f"   No data available:   {stats['miss_no_data']:>8,}")
        print(f"   No formation data:   {stats['miss_no_formation']:>8,}")
        print(f"   Empty lineups:       {stats['miss_empty']:>8,}")
        print(f"   Time elapsed:        {total_time/60:.1f} minutes")
        if total_attempted > 0:
            print(f"   Throughput:          {total_attempted/total_time:.1f} matches/s")
        print(f"   Hit rate:            {stats['success']/(max(total_attempted-stats['error'],1))*100:.0f}%")
        print()

        # Final database stats
        new_total = conn.execute("SELECT COUNT(*) FROM sofa_lineups").fetchone()[0]
        new_with_players = conn.execute(
            "SELECT COUNT(*) FROM sofa_lineups WHERE home_players_json IS NOT NULL"
        ).fetchone()[0]
        print(f"📈 New coverage: {new_total:,}/{total_hist:,} "
              f"({new_total/total_hist*100:.1f}%)")
        print(f"   Lineups with player data: {new_with_players:,}")

    finally:
        conn.close()


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Bulk lineup collector from SofaScore API"
    )
    parser.add_argument('--quick', action='store_true',
                        help='Only fetch 2025-2026 matches')
    parser.add_argument('--dry-run', action='store_true',
                        help='Count matches without fetching')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS,
                        help=f'Number of concurrent workers (default: {MAX_WORKERS})')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum number of matches to fetch')
    parser.add_argument('--min-id', type=int, default=MIN_TARGET_ID,
                        help=f'Minimum event ID to process (default: {MIN_TARGET_ID})')
    parser.add_argument('--reset-progress', action='store_true',
                        help='Reset the progress tracking table')

    args = parser.parse_args()

    # Reset progress if requested
    if args.reset_progress:
        conn = get_db_connection()
        try:
            conn.execute(f"DROP TABLE IF EXISTS {PROGRESS_TABLE}")
            conn.commit()
            print(f"✅ Progress table '{PROGRESS_TABLE}' reset.")
        finally:
            conn.close()
        return

    collect_lineups(
        workers=args.workers,
        limit=args.limit,
        quick=args.quick,
        dry_run=args.dry_run,
        min_id=args.min_id
    )


if __name__ == '__main__':
    main()
