#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              HARVESTER: FBref — advanced stats, progressive passes        ▓
▓  ALL teams in top 30 leagues. Proxy rotation + random delays.              ▓
▓  Stats: progressive passes, passes under pressure, GK stats, possession   ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, re, random, asyncio, sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from curl_cffi import requests as curl_requests
from eternal_harvester_config import (
    FBREF_CONFIG, FBREF_TOP_LEAGUES,
    LOGS_DIR, DB_PATH, get_rate_limiter, save_checkpoint, load_checkpoint,
    log_event, get_db,
)

# ─── Constants ───────────────────────────────────────────────────────────────
BASE = FBREF_CONFIG.base_url
RATE_LIMITER = get_rate_limiter('fbref', 15)
LOG_FILE = LOGS_DIR / 'fbref.log'
CHECKPOINT_KEY = 'fbref'

# Rotating user agents for fingerprint diversity
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
]

# ─── Utils ──────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [fbref] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('fbref', level, msg)


def _random_delay(base_min: float = 2.0, base_max: float = 6.0):
    """Sleep a random amount to avoid detection."""
    delay = random.uniform(base_min, base_max)
    time.sleep(delay)


def _get_headers() -> Dict:
    """Get headers with rotating User-Agent."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': BASE + '/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }


def _fetch(url: str, use_proxy: bool = True, retries: int = 8) -> Optional[str]:
    """Fetch with proxy rotation, random delays, and exponential backoff."""
    last_err = None
    for attempt in range(retries):
        with RATE_LIMITER:
            try:
                proxy = None
                if use_proxy:
                    try:
                        from proxy_rotator import get_proxy
                        proxy = get_proxy()
                    except Exception:
                        pass

                r = curl_requests.get(
                    url,
                    headers=_get_headers(),
                    impersonate=random.choice(['chrome124', 'chrome120', 'chrome124']),
                    timeout=FBREF_CONFIG.timeout,
                    proxy=proxy,
                )
                if r.status_code == 200:
                    return r.text
                elif r.status_code == 429:
                    wait = (FBREF_CONFIG.retry_backoff_base ** attempt) + random.uniform(1, 5)
                    _log(f'429 rate limited, waiting {wait:.0f}s (attempt {attempt+1})', 'WARN')
                    time.sleep(wait)
                    # Rotate user agent harder
                    continue
                elif r.status_code == 403:
                    _log(f'403 Forbidden for {url} (attempt {attempt+1})', 'WARN')
                    wait = 10 + random.uniform(0, 10)
                    time.sleep(wait)
                    continue
                elif r.status_code == 404:
                    return None
                else:
                    _log(f'HTTP {r.status_code} for {url}', 'WARN')
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt + random.uniform(0, 2))
                    continue
            except Exception as e:
                last_err = e
                _log(f'Fetch error (attempt {attempt+1}): {e}', 'WARN')
                if attempt < retries - 1:
                    wait = (FBREF_CONFIG.retry_backoff_base ** attempt) + random.uniform(1, 3)
                    time.sleep(wait)
                continue

    _log(f'Failed after {retries} retries: {url}', 'ERROR')
    return None


# ─── DB ─────────────────────────────────────────────────────────────────────
def _ensure_tables():
    """Ensure FBref tables exist with advanced stats columns."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fbref_team_stats (
            team TEXT,
            season TEXT,
            league TEXT,
            -- General
            mp INTEGER, wins INTEGER, draws INTEGER, losses INTEGER,
            gf REAL, ga REAL, gd REAL,
            -- Possession
            possession REAL, passes_total REAL, passes_completed REAL,
            pass_accuracy REAL, progressive_passes REAL,
            -- Shooting
            shots_total REAL, shots_sot REAL, shots_per90 REAL,
            sot_per90 REAL, goals_per_shot REAL, goals_per_sot REAL,
            xg REAL, npxg REAL, xg_per_shot REAL, g_minus_xg REAL,
            -- Goalkeeping
            gk_ga REAL, gk_ga90 REAL, gk_saves REAL, gk_save_pct REAL,
            gk_psxg REAL, gk_psxg_net REAL, gk_launched REAL,
            gk_passes_att REAL, gk_throws REAL, gk_crosses REAL,
            -- Defensive
            tackles REAL, tackles_won REAL, tackles_def_3rd REAL,
            tackles_mid_3rd REAL, tackles_att_3rd REAL,
            pressures REAL, pressure_success REAL,
            clearances REAL, blocked_shots REAL, interceptions REAL,
            -- Misc
            cards_yellow REAL, cards_red REAL, fouls REAL, fouls_drawn REAL,
            offsides REAL, corners REAL, own_goals REAL,
            updated REAL,
            PRIMARY KEY (team, season)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fbref_player_stats (
            player TEXT,
            team TEXT,
            season TEXT,
            league TEXT,
            position TEXT,
            age REAL,
            mp INTEGER, starts INTEGER, minutes REAL,
            -- Per 90
            goals_per90 REAL, assists_per90, g_plus_a_per90 REAL,
            shots_per90 REAL, sot_per90 REAL,
            passes_completed_per90 REAL, pass_accuracy REAL,
            progressive_passes_per90 REAL,
            progressive_carries_per90 REAL,
            tackles_per90 REAL, interceptions_per90 REAL,
            pressures_per90 REAL,
            xg_per90 REAL, xag_per90 REAL,
            updated REAL,
            PRIMARY KEY (player, team, season)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fbref_cache (
            team TEXT, season TEXT, stat TEXT, value REAL, updated REAL,
            PRIMARY KEY(team, season, stat)
        )
    ''')
    conn.commit()
    conn.close()


# ─── Parse FBref tables ────────────────────────────────────────────────────
def _parse_table_to_rows(html: str, table_id: str) -> List[Dict]:
    """Parse a stats table from FBref HTML by table ID."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', {'id': table_id})
    if not table:
        return []

    rows = []
    for tr in table.find_all('tr'):
        th = tr.find('th', {'data-stat': 'player'}) or tr.find('th', {'data-stat': 'team'})
        if not th:
            continue

        row = {}
        for td in tr.find_all(['td', 'th']):
            stat = td.get('data-stat')
            if stat:
                val = td.get_text(strip=True)
                row[stat] = val

        if row:
            rows.append(row)

    return rows


def _safe_float_fbref(val) -> Optional[float]:
    """Parse FBref value (may have commas, % signs, etc.)."""
    if not val or val == '':
        return None
    cleaned = val.replace(',', '').replace('%', '').replace('+', '').strip()
    if cleaned == '':
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_league_standings(league_slug: str, season: str = '2025-2026') -> Dict:
    """Fetch all team stats for a league from FBref standings page.

    FBref URL pattern: /en/comps/{comp_id}/{season}/{league_slug}-Stats
    """
    _log(f'Fetching {league_slug} {season} standings...')

    # Build URL from league slug
    url = f'{BASE}/en/comps/search/{league_slug}-Stats'

    # Actually we need the comp_id. Let's try a direct approach.
    # FBref uses numeric comp IDs. Let's use known ones.
    comp_ids = {
        'Premier-League': '9',
        'La-Liga': '12',
        'Bundesliga': '20',
        'Serie-A': '11',
        'Ligue-1': '13',
        'Eredivisie': '23',
        'Primeira-Liga': '32',
        'Super-Lig': '26',
        'Russian-Premier-League': '30',
        'Scottish-Premiership': '40',
        'Jupiler-Pro-League': '37',
        'Raiffeisen-Super-League': '102',
        'Allsvenskan': '50',
        'Eliteserien': '51',
        'Danish-Superliga': '52',
        'Ekstraklasa': '36',
        'Czech-First-League': '56',
        'Liga-I': '172',
        'Hrvatska-NL': '67',
        'Austrian-Bundesliga': '43',
        'Super-League-Greece': '27',
        'Ukrainian-Premier-League': '39',
        'Saudi-Professional-League': '93',
        'Chinese-Super-League': '60',
        'J1-League': '74',
        'K-League-1': '76',
        'A-League': '71',
        'Brasileirao-Serie-A': '24',
        'Primera-Division-Argentina': '21',
        'Primera-Division-Chile': '45',
        'Liga-MX': '31',
        'MLS': '22',
    }

    comp_id = comp_ids.get(league_slug)
    if not comp_id:
        _log(f'No comp_id for {league_slug}', 'WARN')
        return {}

    # Stats page URL
    season_url = season.replace('-', '')[:7]  # '2025-2026' -> '2025-2026' or just year
    # FBref uses: /en/comps/9/2025-2026/stats/2025-2026-Premier-League-Stats
    season_part = season
    stats_url = f'{BASE}/en/comps/{comp_id}/{season_part}/stats/{season_part}-{league_slug}-Stats'

    html = _fetch(stats_url)
    if not html:
        _log(f'Failed to fetch {stats_url}', 'ERROR')
        return {}

    # Parse all_stats_standard table for team-level data
    all_tables = {}

    # Standard stats
    standard_rows = _parse_table_to_rows(html, 'stats_standard')
    if standard_rows:
        all_tables['standard'] = standard_rows

    # Possession stats
    possession_rows = _parse_table_to_rows(html, 'stats_possession')
    if possession_rows:
        all_tables['possession'] = possession_rows

    # Shooting stats
    shooting_rows = _parse_table_to_rows(html, 'stats_shooting')
    if shooting_rows:
        all_tables['shooting'] = shooting_rows

    # Goalkeeping
    gk_rows = _parse_table_to_rows(html, 'stats_keeper')
    if gk_rows:
        all_tables['goalkeeping'] = gk_rows

    # Defensive
    defensive_rows = _parse_table_to_rows(html, 'stats_defense')
    if defensive_rows:
        all_tables['defense'] = defensive_rows

    # Passing
    passing_rows = _parse_table_to_rows(html, 'stats_passing')
    if passing_rows:
        all_tables['passing'] = passing_rows

    # Misc
    misc_rows = _parse_table_to_rows(html, 'stats_misc')
    if misc_rows:
        all_tables['misc'] = misc_rows

    # Also try player stats
    all_tables['player_standard'] = _parse_table_to_rows(html, 'stats_standard_9')

    return all_tables


def save_team_stats(tables: Dict, league_slug: str, season: str):
    """Save FBref team and player stats to database."""
    conn = get_db()
    now = time.time()
    cached = 0

    conn.execute('BEGIN TRANSACTION')

    # Process team standard stats → fbref_team_stats
    if 'standard' in tables:
        for row in tables['standard']:
            team_name_el = row.get('team', '')
            # Extract team name from the <a> tag if present
            team = team_name_el

            if not team:
                continue

            # Build stat row
            stats = {
                'team': team,
                'season': season,
                'league': league_slug,
                'mp': _safe_float_fbref(row.get('games')),
                'wins': _safe_float_fbref(row.get('wins')),
                'draws': _safe_float_fbref(row.get('draws')),
                'losses': _safe_float_fbref(row.get('losses')),
                'gf': _safe_float_fbref(row.get('goals_for')),
                'ga': _safe_float_fbref(row.get('goals_against')),
                'xg': _safe_float_fbref(row.get('xg')),
                'npxg': _safe_float_fbref(row.get('npxg')),
                'xg_per_shot': _safe_float_fbref(row.get('xg_per_shot')),
                'g_minus_xg': _safe_float_fbref(row.get('g_minus_xg')),
                'updated': now,
            }
            if not any(v is not None for v in stats.values()):
                continue

            conn.execute('''
                INSERT OR REPLACE INTO fbref_team_stats
                    (team, season, league, mp, wins, draws, losses,
                     gf, ga, xg, npxg, xg_per_shot, g_minus_xg, updated)
                VALUES (:team, :season, :league, :mp, :wins, :draws, :losses,
                        :gf, :ga, :xg, :npxg, :xg_per_shot, :g_minus_xg, :updated)
            ''', stats)
            cached += 1

            # Also add to simple cache
            for stat_key, stat_val in stats.items():
                if stat_val is not None and stat_key in ('mp', 'wins', 'gf', 'ga', 'xg', 'xg_per_shot', 'g_minus_xg'):
                    try:
                        conn.execute('''
                            INSERT OR REPLACE INTO fbref_cache (team, season, stat, value, updated)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (team, season, stat_key, float(stat_val), now))
                    except Exception:
                        pass

    # Process possession stats
    if 'possession' in tables:
        for row in tables['possession']:
            team = row.get('team', '')
            if not team:
                continue

            conn.execute('''
                UPDATE fbref_team_stats SET
                    possession = ?, passes_total = ?, passes_completed = ?,
                    pass_accuracy = ?, progressive_passes = ?, updated = ?
                WHERE team = ? AND season = ?
            ''', (
                _safe_float_fbref(row.get('possession')),
                _safe_float_fbref(row.get('passes')),
                _safe_float_fbref(row.get('passes_completed')),
                _safe_float_fbref(row.get('pass_accuracy')),
                _safe_float_fbref(row.get('progressive_passes')),
                now,
                team, season,
            ))

    # Process shooting stats
    if 'shooting' in tables:
        for row in tables['shooting']:
            team = row.get('team', '')
            if not team:
                continue

            conn.execute('''
                UPDATE fbref_team_stats SET
                    shots_total = ?, shots_sot = ?, shots_per90 = ?,
                    sot_per90 = ?, goals_per_shot = ?, goals_per_sot = ?,
                    updated = ?
                WHERE team = ? AND season = ?
            ''', (
                _safe_float_fbref(row.get('shots_total')),
                _safe_float_fbref(row.get('shots_on_target')),
                _safe_float_fbref(row.get('shots_per90')),
                _safe_float_fbref(row.get('shots_on_target_per90')),
                _safe_float_fbref(row.get('goals_per_shot')),
                _safe_float_fbref(row.get('goals_per_shot_on_target')),
                now,
                team, season,
            ))

    # Process goalkeeper stats
    if 'goalkeeping' in tables:
        for row in tables['goalkeeping']:
            team = row.get('team', '')
            if not team:
                continue

            conn.execute('''
                UPDATE fbref_team_stats SET
                    gk_ga = ?, gk_ga90 = ?, gk_saves = ?, gk_save_pct = ?,
                    gk_psxg = ?, gk_psxg_net = ?, updated = ?
                WHERE team = ? AND season = ?
            ''', (
                _safe_float_fbref(row.get('goals_against')),
                _safe_float_fbref(row.get('goals_against_per90')),
                _safe_float_fbref(row.get('saves')),
                _safe_float_fbref(row.get('save_pct')),
                _safe_float_fbref(row.get('psxg')),
                _safe_float_fbref(row.get('psxg_net')),
                now,
                team, season,
            ))

    # Process player stats
    if 'player_standard' in tables:
        for row in tables['player_standard']:
            player = row.get('player', '')
            team_el = row.get('team', '')
            if not player or not team_el:
                continue
            team = team_el

            conn.execute('''
                INSERT OR REPLACE INTO fbref_player_stats
                    (player, team, season, league, position, age,
                     mp, starts, minutes, goals_per90, assists_per90,
                     g_plus_a_per90, shots_per90, sot_per90,
                     passes_completed_per90, pass_accuracy,
                     progressive_passes_per90, progressive_carries_per90,
                     tackles_per90, interceptions_per90, pressures_per90,
                     xg_per90, xag_per90, updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player, team, season, league_slug,
                row.get('position'), _safe_float_fbref(row.get('age')),
                _safe_float_fbref(row.get('games')),
                _safe_float_fbref(row.get('games_starts')),
                _safe_float_fbref(row.get('minutes')),
                _safe_float_fbref(row.get('goals_per90')),
                _safe_float_fbref(row.get('assists_per90')),
                _safe_float_fbref(row.get('goals_assists_per90')),
                _safe_float_fbref(row.get('shots_per90')),
                _safe_float_fbref(row.get('shots_on_target_per90')),
                _safe_float_fbref(row.get('passes_completed_per90')),
                _safe_float_fbref(row.get('pass_accuracy')),
                _safe_float_fbref(row.get('progressive_passes_per90')),
                _safe_float_fbref(row.get('progressive_carries_per90')),
                _safe_float_fbref(row.get('tackles_per90')),
                _safe_float_fbref(row.get('interceptions_per90')),
                _safe_float_fbref(row.get('pressures_per90')),
                _safe_float_fbref(row.get('xg_per90')),
                _safe_float_fbref(row.get('xag_per90')),
                now,
            ))

    conn.commit()
    _log(f'Saved {cached} teams + player stats for {league_slug} {season}')

    conn.close()
    return cached


# ─── Main harvest ──────────────────────────────────────────────────────────
def harvest_all(
    checkpoint: bool = True,
    force_refresh: bool = False,
    max_leagues: int = 30,
    seasons: List[str] = None,
) -> Dict:
    """Harvest FBref for all leagues.

    Args:
        checkpoint: Save progress checkpoints
        force_refresh: Re-fetch cached leagues
        max_leagues: Max leagues to process
        seasons: List of seasons to process (default: current + last)

    Returns:
        Stats dict
    """
    _ensure_tables()

    if seasons is None:
        current = datetime.now().year
        seasons = [f'{current-1}-{current}', f'{current}-{current+1}']

    start_time = time.time()
    total_teams = 0
    total_errors = 0
    total_leagues = 0

    completed = set()
    if not force_refresh:
        cp = load_checkpoint(CHECKPOINT_KEY)
        if cp:
            completed = set(cp['data'].get('completed', []))

    _log(f'FBref harvest start. {min(max_leagues, len(FBREF_TOP_LEAGUES))} leagues')

    for league_slug in FBREF_TOP_LEAGUES[:max_leagues]:
        for season in seasons:
            job_key = f'{league_slug}/{season}'
            if job_key in completed and not force_refresh:
                continue

            _log(f'Harvesting {league_slug} {season}...')

            _random_delay(3, 8)  # Be extra respectful to FBref

            try:
                tables = fetch_league_standings(league_slug, season)
                if not tables:
                    _log(f'No data for {league_slug} {season}', 'WARN')
                    total_errors += 1
                    continue

                teams = save_team_stats(tables, league_slug, season)
                total_teams += teams
                total_leagues += 1
                completed.add(job_key)

                _log(f'{league_slug} {season}: {teams} teams cached')

                # Save checkpoint periodically
                if total_leagues % 3 == 0 and checkpoint:
                    save_checkpoint(CHECKPOINT_KEY, {
                        'completed': list(completed),
                    }, total_teams, total_errors)

            except Exception as e:
                _log(f'Error harvesting {league_slug} {season}: {e}', 'ERROR')
                total_errors += 1

            # Extra delay between seasons
            _random_delay(5, 10)

    duration = time.time() - start_time
    _log(f'FBref complete: {total_leagues} leagues, {total_teams} teams, '
         f'{total_errors} errors, {duration:.1f}s')

    if checkpoint:
        save_checkpoint(CHECKPOINT_KEY, {
            'completed': list(completed),
        }, total_teams, total_errors)

    return {
        'source': 'fbref',
        'leagues_processed': total_leagues,
        'teams_cached': total_teams,
        'errors': total_errors,
        'duration_seconds': duration,
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='FBref advanced stats harvester')
    parser.add_argument('--force', action='store_true', help='Force re-fetch')
    parser.add_argument('--leagues', type=int, default=10,
                        help='Number of leagues to process')
    parser.add_argument('--league', type=str, default=None,
                        help='Single league slug (e.g., Premier-League)')
    args = parser.parse_args()

    if args.league:
        _ensure_tables()
        tables = fetch_league_standings(args.league)
        if tables:
            teams = save_team_stats(tables, args.league, '2025-2026')
            print(json.dumps({'teams': teams}, indent=2))
        else:
            print(json.dumps({'error': 'No data'}, indent=2))
    else:
        result = harvest_all(force_refresh=args.force, max_leagues=args.leagues)
        print(json.dumps(result, indent=2))
