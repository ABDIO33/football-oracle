#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              HARVESTER: Understat — xG, per-shot data, shot maps          ▓
▓  Top 6 leagues: EPL, La Liga, Bundesliga, Serie A, Ligue 1, RPL           ▓
▓  Uses asyncio + aiohttp with curl_cffi impersonation                      ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, asyncio, aiohttp, re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import urljoin

from curl_cffi import requests as curl_requests
from eternal_harvester_config import (
    UNDERSTAT_CONFIG, UNDERSTAT_LEAGUES,
    LOGS_DIR, DB_PATH, get_rate_limiter, save_checkpoint, load_checkpoint,
    log_event, get_db,
)

# ─── Constants ───────────────────────────────────────────────────────────────
BASE = UNDERSTAT_CONFIG.base_url
RATE_LIMITER = get_rate_limiter('understat')
LOG_FILE = LOGS_DIR / 'understat.log'
CHECKPOINT_KEY = 'understat'

headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'X-Requested-With': 'XMLHttpRequest',
}

# ─── Utils ──────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [understat] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('understat', level, msg)


def _extract_json_var(html: str, var_name: str) -> Optional[Any]:
    """Extract a JavaScript variable from Understat HTML."""
    # Pattern: var varName = [{...}];
    patterns = [
        rf'var\s+{var_name}\s*=\s*({{\s*"data".*?}});',
        rf'var\s+{var_name}\s*=\s*(\[.*?\]);',
        rf'var\s+{var_name}\s*=\s*({{.*?}});',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                # Try cleaning trailing commas
                cleaned = re.sub(r',\s*}', '}', match.group(1))
                cleaned = re.sub(r',\s*]', ']', cleaned)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
    return None


def _fetch_sync(url: str, retries: int = 5) -> Optional[str]:
    """Synchronous fetch with rate limiting and curl_cffi."""
    for attempt in range(retries):
        with RATE_LIMITER:
            try:
                r = curl_requests.get(
                    url, headers=headers,
                    impersonate='chrome124',
                    timeout=UNDERSTAT_CONFIG.timeout,
                )
                if r.status_code == 200:
                    return r.text
                elif r.status_code == 429:
                    wait = (2 ** attempt) * 3
                    _log(f'Rate limited (429), waiting {wait}s', 'WARN')
                    time.sleep(wait)
                    continue
                else:
                    _log(f'HTTP {r.status_code} for {url}', 'WARN')
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                _log(f'Fetch error (attempt {attempt+1}): {e}', 'WARN')
                if attempt < retries - 1:
                    time.sleep(2 ** attempt + 1)
    return None


async def _fetch_async(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Async fetch with rate limiting."""
    with RATE_LIMITER:
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(
                total=UNDERSTAT_CONFIG.timeout)) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    _log(f'HTTP {resp.status} for {url}', 'WARN')
                    return None
        except Exception as e:
            _log(f'Async fetch error: {e}', 'WARN')
            return None


# ─── Helper to extract team/matches from JSON scripts ─────────────────────
def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ─── Ensure DB tables ───────────────────────────────────────────────────────
def _ensure_tables():
    """Ensure Understat tables exist."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS understat_matches (
            id INTEGER PRIMARY KEY,
            league TEXT,
            season TEXT,
            date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_goals INTEGER,
            away_goals INTEGER,
            home_xg REAL,
            away_xg REAL,
            is_result INTEGER,
            FOREIGN KEY(id) REFERENCES understat_shotmap(match_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS understat_shotmap (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            minute INTEGER,
            team TEXT,
            player TEXT,
            xg REAL,
            season TEXT,
            league TEXT,
            situation TEXT,
            shot_type TEXT,
            last_action TEXT,
            x REAL,
            y REAL,
            result TEXT,
            h_a TEXT,
            FOREIGN KEY(match_id) REFERENCES understat_matches(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS understat_ppda (
            team TEXT,
            season TEXT,
            league TEXT,
            ppda_att INTEGER,
            ppda_def INTEGER,
            ppda_ratio REAL,
            FOREIGN KEY(season) REFERENCES understat_matches(season)
        )
    ''')
    conn.commit()
    conn.close()


# ─── League page: get all matches ──────────────────────────────────────────
def fetch_league_matches(league: str, season: str = '2025') -> List[Dict]:
    """Fetch all matches for a league+season from Understat."""
    url = f'{BASE}/league/{league}/{season}'
    html = _fetch_sync(url)
    if not html:
        return []

    # The match data is in var datesData
    data = _extract_json_var(html, 'datesData')
    if not data:
        # Try different var name
        data = _extract_json_var(html, 'teamsData')
        if not data:
            _log(f'Could not extract data from {url}', 'ERROR')
            return []

    return data if isinstance(data, list) else []


def process_league(league: str, season: str = '2025') -> Tuple[int, int, int]:
    """Process a single league+season. Returns (matches, shots, errors)."""
    matches_data = fetch_league_matches(league, season)
    if not matches_data:
        return 0, 0, 0

    _log(f'Processing {league} {season}: {len(matches_data)} matches')

    conn = get_db()
    matches_inserted = 0
    shots_inserted = 0
    errors = 0

    for match in matches_data:
        try:
            match_id = _safe_int(match.get('id'))
            if not match_id:
                continue

            # Extract match data
            home_team = match.get('h', {}).get('title', '')
            away_team = match.get('a', {}).get('title', '')
            date = match.get('datetime', match.get('date', ''))[:10]
            home_goals = _safe_int(match.get('goals', {}).get('h'))
            away_goals = _safe_int(match.get('goals', {}).get('a'))
            home_xg = _safe_float(match.get('xG', {}).get('h'))
            away_xg = _safe_float(match.get('xG', {}).get('a'))
            is_result = 1 if match.get('isResult') else 0

            # Get shot data
            shot_data = match.get('shotData', {})
            home_shots = shot_data.get('h', []) if isinstance(shot_data, dict) else []
            away_shots = shot_data.get('a', []) if isinstance(shot_data, dict) else []

            if not home_team or not away_team:
                continue

            # Insert match
            conn.execute('''
                INSERT OR REPLACE INTO understat_matches
                    (id, league, season, date, home_team, away_team,
                     home_goals, away_goals, home_xg, away_xg, is_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (match_id, league, season, date, home_team, away_team,
                  home_goals, away_goals, home_xg, away_xg, is_result))
            matches_inserted += 1

            # Insert shots
            for shot in home_shots + away_shots:
                if not isinstance(shot, dict):
                    continue
                h_a = 'h' if shot in home_shots else 'a'
                conn.execute('''
                    INSERT OR IGNORE INTO understat_shotmap
                        (match_id, minute, team, player, xg, season, league,
                         situation, shot_type, last_action, x, y, result, h_a)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id,
                    _safe_int(shot.get('minute')),
                    shot.get('team', home_team if h_a == 'h' else away_team),
                    shot.get('player', ''),
                    _safe_float(shot.get('xG')),
                    season, league,
                    shot.get('situation', ''),
                    shot.get('shotType', ''),
                    shot.get('lastAction', ''),
                    _safe_float(shot.get('X')),
                    _safe_float(shot.get('Y')),
                    shot.get('result', ''),
                    h_a,
                ))
                shots_inserted += 1

            conn.commit()

        except Exception as e:
            conn.rollback()
            _log(f'Error processing match {match.get("id")}: {e}', 'ERROR')
            errors += 1
            continue

    conn.close()
    return matches_inserted, shots_inserted, errors


def fetch_ppda_data(league: str, season: str = '2025') -> int:
    """Fetch PPDA (passes per defensive action) data."""
    url = f'{BASE}/league/{league}/{season}'
    html = _fetch_sync(url)
    if not html:
        return 0

    teams_data = _extract_json_var(html, 'teamsData')
    if not teams_data:
        return 0

    conn = get_db()
    inserted = 0

    for team_id, team_info in teams_data.items():
        if not isinstance(team_info, dict):
            continue
        team_name = team_info.get('title', '')
        history = team_info.get('history', [])
        if not history or not team_name:
            continue

        # Aggregate PPDA from history
        total_att = 0
        total_def = 0
        for h in history:
            if isinstance(h, dict):
                ppda = h.get('ppda', {})
                if isinstance(ppda, dict):
                    total_att += _safe_int(ppda.get('att')) or 0
                    total_def += _safe_int(ppda.get('def')) or 0

        ratio = total_def / total_att if total_att > 0 else None

        try:
            conn.execute('''
                INSERT OR REPLACE INTO understat_ppda
                    (team, season, league, ppda_att, ppda_def, ppda_ratio)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (team_name, season, league, total_att, total_def, ratio))
            inserted += 1
        except Exception as e:
            _log(f'PPDA insert error for {team_name}: {e}', 'ERROR')

    conn.commit()
    conn.close()
    return inserted


# ─── Main harvest function ─────────────────────────────────────────────────
def harvest_all(checkpoint: bool = True, force_refresh: bool = False,
                max_seasons_per_league: int = 5) -> Dict:
    """Harvest all Understat leagues and seasons.

    Args:
        checkpoint: Save checkpoint to DB
        force_refresh: Re-fetch already completed seasons
        max_seasons_per_league: Number of recent seasons to fetch

    Returns:
        Stats dict
    """
    _ensure_tables()

    start_time = time.time()
    total_matches = 0
    total_shots = 0
    total_errors = 0
    total_ppda = 0

    # Determine seasons to scan
    current_year = datetime.now().year
    seasons = [str(current_year), str(current_year - 1), str(current_year - 2),
               str(current_year - 3), str(current_year - 4)]

    completed = set()
    if not force_refresh:
        cp = load_checkpoint(CHECKPOINT_KEY)
        if cp:
            completed = set(cp['data'].get('completed', []))

    _log(f'Understat harvest start. {len(UNDERSTAT_LEAGUES)} leagues, '
         f'{len(seasons)} seasons each')

    for league_key, league_name in UNDERSTAT_LEAGUES.items():
        for season in seasons[:max_seasons_per_league]:
            job_key = f'{league_key}/{season}'
            if job_key in completed and not force_refresh:
                continue

            _log(f'Harvesting {league_name} ({league_key}) {season}...')

            matches, shots, errors = process_league(league_key, season)
            total_matches += matches
            total_shots += shots
            total_errors += errors

            # PPDA data
            ppda = fetch_ppda_data(league_key, season)
            total_ppda += ppda

            _log(f'{job_key}: {matches} matches, {shots} shots, {ppda} PPDA, {errors} errors')
            completed.add(job_key)

    duration = time.time() - start_time
    _log(f'Understat complete: {total_matches} matches, {total_shots} shots, '
         f'{total_ppda} PPDA entries, {total_errors} errors, {duration:.1f}s')

    if checkpoint:
        save_checkpoint(CHECKPOINT_KEY, {
            'completed': list(completed),
        }, total_matches + total_shots + total_ppda, total_errors)

    return {
        'source': 'understat',
        'matches': total_matches,
        'shots': total_shots,
        'ppda': total_ppda,
        'errors': total_errors,
        'duration_seconds': duration,
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Understat xG harvester')
    parser.add_argument('--force', action='store_true', help='Force re-fetch')
    parser.add_argument('--league', type=str, default=None,
                        help='Single league (EPL, La_liga, etc.)')
    parser.add_argument('--season', type=str, default=None,
                        help='Single season (2025, 2024, etc.)')
    args = parser.parse_args()

    if args.league and args.season:
        _ensure_tables()
        matches, shots, errors = process_league(args.league, args.season)
        ppda = fetch_ppda_data(args.league, args.season)
        print(json.dumps({
            'matches': matches, 'shots': shots,
            'ppda': ppda, 'errors': errors,
        }, indent=2))
    else:
        result = harvest_all(force_refresh=args.force)
        print(json.dumps(result, indent=2))
