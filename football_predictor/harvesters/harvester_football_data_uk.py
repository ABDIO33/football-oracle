#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              HARVESTER: football-data.co.uk — ALL leagues, ALL seasons    ▓
▓  Downloads every CSV, parses into DB, auto-detects new files              ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, csv, io, json, time, asyncio, aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin
import sqlite3

from curl_cffi import requests as curl_requests
from eternal_harvester_config import (
    FOOTBALL_DATA_CONFIG, FOOTBALL_DATA_LEAGUES, FOOTBALL_DATA_SEASONS,
    LOGS_DIR, DB_PATH, get_rate_limiter, save_checkpoint, load_checkpoint,
    log_event, get_db,
)

# ─── Constants ───────────────────────────────────────────────────────────────
BASE = FOOTBALL_DATA_CONFIG.base_url
RATE_LIMITER = get_rate_limiter('football_data_uk')
LOG_FILE = LOGS_DIR / 'football_data_uk.log'
CHECKPOINT_KEY = 'football_data_uk'

headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/csv,application/*,*/*',
    'Referer': BASE + '/',
}

# ─── Utils ──────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [football-data] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('football_data_uk', level, msg)


def _fetch_csv(url: str, retries: int = 5) -> Optional[str]:
    """Fetch a CSV file with curl_cffi impersonation + retry."""
    last_err = None
    for attempt in range(retries):
        with RATE_LIMITER:
            try:
                r = curl_requests.get(
                    url,
                    headers=headers,
                    impersonate='chrome124',
                    timeout=FOOTBALL_DATA_CONFIG.timeout,
                )
                if r.status_code == 200:
                    text = r.text
                    if len(text) > 50 and ('HomeTeam' in text[:200] or 'Div' in text[:200]):
                        return text
                    # Might be a 404 redirect page or empty
                    _log(f'Empty/invalid CSV from {url} ({len(text)} bytes)', 'WARN')
                    return None
                elif r.status_code == 404:
                    return None
                elif r.status_code == 429:
                    wait = (2 ** attempt) * 5
                    _log(f'Rate limited (429), waiting {wait}s (attempt {attempt+1})', 'WARN')
                    time.sleep(wait)
                    continue
                else:
                    _log(f'HTTP {r.status_code} for {url}', 'WARN')
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                last_err = e
                _log(f'Fetch error (attempt {attempt+1}): {e}', 'WARN')
                if attempt < retries - 1:
                    time.sleep(2 ** attempt + 1)
    _log(f'Failed after {retries} retries: {url}', 'ERROR')
    return None


def _parse_value(v: str) -> float:
    """Parse a CSV value to float, returning None if invalid."""
    if not v or v.strip() == '':
        return None
    try:
        return float(v.strip())
    except ValueError:
        return None


def _parse_csv_to_rows(text: str) -> List[Dict]:
    """Parse CSV text to list of dicts."""
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _ensure_table():
    """Ensure the football_data_matches table exists."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS football_data_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_code TEXT,
            country TEXT,
            league TEXT,
            date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_goals REAL,
            away_goals REAL,
            result TEXT,
            home_shots REAL,
            away_shots REAL,
            home_sot REAL,
            away_sot REAL,
            home_fouls REAL,
            away_fouls REAL,
            home_corners REAL,
            away_corners REAL,
            home_yellow REAL,
            away_yellow REAL,
            home_red REAL,
            away_red REAL,
            b365h REAL,
            b365d REAL,
            b365a REAL,
            avgh REAL,
            avgd REAL,
            avga REAL,
            maxh REAL,
            maxd REAL,
            maxa REAL,
            UNIQUE(league_code, date, home_team, away_team)
        )
    ''')
    conn.commit()
    conn.close()


# ─── Column mapping: CSV header → DB column ─────────────────────────────────
COLUMN_MAP = {
    'B365H': 'b365h', 'B365D': 'b365d', 'B365A': 'b365a',
    'B365CH': 'b365h', 'B365CD': 'b365d', 'B365CA': 'b365a',  # closing odds
    'PSH': 'b365h', 'PSD': 'b365d', 'PSA': 'b365a',
    'BSH': 'b365h', 'BSD': 'b365d', 'BSA': 'b365a',
    'AvgH': 'avgh', 'AvgD': 'avgd', 'AvgA': 'avga',
    'AvgCH': 'avgh', 'AvgCD': 'avgd', 'AvgCA': 'avga',
    'MaxH': 'maxh', 'MaxD': 'maxd', 'MaxA': 'maxa',
    'MaxCH': 'maxh', 'MaxCD': 'maxd', 'MaxCA': 'maxa',
    'HTHG': 'home_goals', 'HTAG': 'away_goals',
    'FTHG': 'home_goals', 'FTAG': 'away_goals',
    'HS': 'home_shots', 'AS': 'away_shots',
    'HST': 'home_sot', 'AST': 'away_sot',
    'HF': 'home_fouls', 'AF': 'away_fouls',
    'HC': 'home_corners', 'AC': 'away_corners',
    'HY': 'home_yellow', 'AY': 'away_yellow',
    'HR': 'home_red', 'AR': 'away_red',
}

# Column priority for conflicting mappings (higher = preferred)
COL_PRIORITY = {
    'home_goals': {'FTHG': 10, 'HTHG': 5},
    'away_goals': {'FTAG': 10, 'HTAG': 5},
    'b365h': {'B365H': 10, 'B365CH': 9, 'PSH': 5, 'BSH': 5},
    'b365d': {'B365D': 10, 'B365CD': 9, 'PSD': 5, 'BSD': 5},
    'b365a': {'B365A': 10, 'B365CA': 9, 'PSA': 5, 'BSA': 5},
    'avgh': {'AvgH': 10, 'AvgCH': 9},
    'avgd': {'AvgD': 10, 'AvgCD': 9},
    'avga': {'AvgA': 10, 'AvgCA': 9},
    'maxh': {'MaxH': 10, 'MaxCH': 9},
    'maxd': {'MaxD': 10, 'MaxCD': 9},
    'maxa': {'MaxA': 10, 'MaxCA': 9},
}


def _extract_row(csv_row: Dict, league_code: str, country: str, league: str) -> Optional[Dict]:
    """Extract a single CSV row into DB format with column priority resolution."""
    row = {
        'league_code': league_code,
        'country': country,
        'league': league,
        'date': csv_row.get('Date', '').strip(),
        'home_team': csv_row.get('HomeTeam', '').strip(),
        'away_team': csv_row.get('AwayTeam', '').strip(),
        'result': csv_row.get('FTR', csv_row.get('HTR', '')).strip(),
    }

    if not row['home_team'] or not row['away_team']:
        return None

    # Resolve columns by priority
    resolved = {}
    for db_col, sources in COL_PRIORITY.items():
        best_val = None
        best_priority = -1
        for csv_col, priority in sorted(sources.items(), key=lambda x: -x[1]):
            if csv_col in csv_row:
                v = _parse_value(csv_row[csv_col])
                if v is not None:
                    best_val = v
                    break
        if best_val is not None:
            resolved[db_col] = best_val

    # Also try direct mapping for stats columns
    for csv_col, db_col in COLUMN_MAP.items():
        if db_col not in resolved or resolved[db_col] is None:
            v = _parse_value(csv_row.get(csv_col, ''))
            if v is not None:
                resolved[db_col] = v

    row.update(resolved)
    return row


def _get_seen_matches(conn: sqlite3.Connection) -> set:
    """Get set of (league_code, date, home_team, away_team) already in DB."""
    seen = set()
    try:
        cur = conn.execute(
            'SELECT league_code, date, home_team, away_team FROM football_data_matches'
        )
        for r in cur.fetchall():
            seen.add((r[0], r[1], r[2], r[3]))
    except Exception:
        pass
    return seen


# ─── Main harvester ─────────────────────────────────────────────────────────
def _process_league_file(
    conn: sqlite3.Connection,
    league_code: str,
    country: str,
    league: str,
    season: str,
    seen_matches: set,
    all_csv_paths: List[str],
) -> Tuple[int, int]:
    """Process a single league+season CSV file. Returns (inserted, errors)."""
    # Try multiple possible URLs
    urls_tried = []
    inserted = 0
    errors = 0

    for path_tmpl in all_csv_paths:
        url = urljoin(BASE + '/', path_tmpl)
        urls_tried.append(url)

    for url in urls_tried[:3]:  # Try up to 3 URL patterns
        csv_text = _fetch_csv(url)
        if csv_text is None:
            continue

        # Parse
        rows = _parse_csv_to_rows(csv_text)
        if not rows:
            continue

        _log(f'Processing {league_code}/{season}: {len(rows)} rows from {url}')

        batch = []
        for csv_row in rows:
            extracted = _extract_row(csv_row, league_code, country, league)
            if extracted is None:
                continue

            key = (extracted['league_code'], extracted['date'],
                   extracted['home_team'], extracted['away_team'])
            if key in seen_matches:
                continue

            batch.append(extracted)

        if not batch:
            _log(f'{league_code}/{season}: No new matches')
            return 0, 0

        # Bulk insert
        try:
            conn.executemany('''
                INSERT OR IGNORE INTO football_data_matches
                    (league_code, country, league, date, home_team, away_team,
                     home_goals, away_goals, result,
                     home_shots, away_shots, home_sot, away_sot,
                     home_fouls, away_fouls, home_corners, away_corners,
                     home_yellow, away_yellow, home_red, away_red,
                     b365h, b365d, b365a, avgh, avgd, avga, maxh, maxd, maxa)
                VALUES
                    (:league_code, :country, :league, :date, :home_team, :away_team,
                     :home_goals, :away_goals, :result,
                     :home_shots, :away_shots, :home_sot, :away_sot,
                     :home_fouls, :away_fouls, :home_corners, :away_corners,
                     :home_yellow, :away_yellow, :home_red, :away_red,
                     :b365h, :b365d, :b365a, :avgh, :avgd, :avga, :maxh, :maxd, :maxa)
            ''', batch)
            conn.commit()
            inserted += len(batch)
            # Update seen set
            for b in batch:
                seen_matches.add((b['league_code'], b['date'], b['home_team'], b['away_team']))
        except Exception as e:
            conn.rollback()
            _log(f'Insert error for {league_code}/{season}: {e}', 'ERROR')
            errors += len(batch)

        return inserted, errors

    _log(f'{league_code}/{season}: No CSV found after {len(urls_tried)} URLs')
    return 0, errors


def _get_csv_paths(league_code: str, season: str) -> List[str]:
    """Generate possible CSV file paths for a league+season.

    football-data.co.uk has multiple naming patterns:
    - Standard: mmzSEAS.csv (e.g., E02425.csv)
    - Old format: mmmSEAS.csv (e.g., E02425.csv)
    - Also: https://www.football-data.co.uk/mmz4281/2425/E0.csv
    """
    paths = []

    # Season code extraction
    if len(season) == 4:
        # Format: 2425 -> first two are end year? Actually 2425 means 2024-2025
        # The actual filename convention uses 2-digit years
        yr1 = season[:2]
        yr2 = season[2:]
    elif len(season) == 5:
        # Format: 99100 for 1999-2000
        yr1 = season[:2]
        yr2 = season[2:]
    else:
        yr1 = season[:2]
        yr2 = season[2:4]

    # Pattern 1: /data/MMMSEAS.CSV (old format)
    # e.g., /data/E02425.csv
    paths.append(f"data/{league_code}{season}.csv")

    # Pattern 2: /mmz4281/SEAS/LEAGUE.csv
    # The archive number changes over time
    archive_nums = ['4281', '4481', '5281', '6081', '7081', '8081', '9081']
    for an in archive_nums:
        # Try both 4-char season and 2-digit + 2-digit
        if len(season) == 4:
            paths.append(f"mmz{an}/{season[:2]}{season[2:]}/{league_code}.csv")
        paths.append(f"mmz{an}/{season}/{league_code}.csv")

    # Pattern 3: modern format /mmz4281/2425/E0.csv
    # Actually these go under /mmz4281/2425/E0.csv
    for an in archive_nums:
        if len(season) == 4:
            paths.append(f"mmz{an}/{season}/{league_code}.csv")

    return paths


async def harvest_all(checkpoint: bool = True, force_refresh: bool = False) -> Dict:
    """Harvest all leagues and seasons from football-data.co.uk.

    Returns dict with stats.
    """
    _ensure_table()

    start_time = time.time()
    total_inserted = 0
    total_errors = 0
    total_files = 0
    total_skipped = 0

    conn = get_db()
    seen_matches = _get_seen_matches(conn)

    # Check which seasons/leagues already downloaded
    completed = set()
    if not force_refresh:
        cp = load_checkpoint(CHECKPOINT_KEY)
        if cp:
            completed = set(cp['data'].get('completed_files', []))

    _log(f'Starting harvest. Already in DB: {len(seen_matches)} matches. '
         f'Completed files: {len(completed)}')

    for country_code, country_data in FOOTBALL_DATA_LEAGUES.items():
        country = country_data['name']
        for league_code, league in country_data['leagues'].items():
            for season in FOOTBALL_DATA_SEASONS:
                file_key = f'{league_code}/{season}'
                if file_key in completed and not force_refresh:
                    total_skipped += 1
                    continue

                csv_paths = _get_csv_paths(league_code, season)

                inserted, errors = _process_league_file(
                    conn, league_code, country, league,
                    season, seen_matches, csv_paths
                )

                total_inserted += inserted
                total_errors += errors
                total_files += 1
                completed.add(file_key)

                if inserted > 0 or errors > 0:
                    _log(f'{file_key}: +{inserted} new, {errors} errors')

                # Save checkpoint periodically
                if total_files % 10 == 0 and checkpoint:
                    save_checkpoint(CHECKPOINT_KEY, {
                        'completed_files': list(completed),
                        'last_season': season,
                        'last_league': league_code,
                        'country': country_code,
                    }, total_inserted, total_errors)

    conn.close()

    duration = time.time() - start_time
    _log(f'Harvest complete. Files: {total_files} (+{total_skipped} skipped), '
         f'New matches: {total_inserted}, Errors: {total_errors}, '
         f'Duration: {duration:.1f}s')

    # Final checkpoint
    save_checkpoint(CHECKPOINT_KEY, {
        'completed_files': list(completed),
        'total_runs': 1,
    }, total_inserted, total_errors)

    return {
        'source': 'football_data_uk',
        'files_processed': total_files,
        'files_skipped': total_skipped,
        'new_matches': total_inserted,
        'errors': total_errors,
        'duration_seconds': duration,
    }


# ─── Auto-update: only recent seasons ──────────────────────────────────────
def harvest_recent_seasons(years_back: int = 5) -> Dict:
    """Only harvest recent seasons for quick updates."""
    global FOOTBALL_DATA_SEASONS
    recent_seasons = [s for s in FOOTBALL_DATA_SEASONS
                      if s >= f'{(datetime.now().year - years_back) % 100:02d}{datetime.now().year % 100:02d}'
                      or '20' in s[:2]]
    _log(f'Harvesting recent seasons only: {recent_seasons[:3]}...{recent_seasons[-1]}')

    # Override global seasons list temporarily
    old_seasons = FOOTBALL_DATA_SEASONS
    FOOTBALL_DATA_SEASONS = recent_seasons
    try:
        result = asyncio.run(harvest_all(checkpoint=True))
        return result
    finally:
        FOOTBALL_DATA_SEASONS = old_seasons


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='football-data.co.uk harvester')
    parser.add_argument('--recent', action='store_true', help='Recent seasons only')
    parser.add_argument('--force', action='store_true', help='Force re-download')
    args = parser.parse_args()

    if args.recent:
        result = harvest_recent_seasons()
    else:
        result = asyncio.run(harvest_all(force_refresh=args.force))

    print(json.dumps(result, indent=2))
