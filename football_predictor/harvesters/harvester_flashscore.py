#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              HARVESTER: Flashscore → SofaScore bridge                     ▓
▓  Flashscore SPA cannot be scraped (all data via WebSocket).               ▓
▓  This harvester uses SofaScore API as the data source instead.            ▓
▓  Same DB schema, same function signatures.                                ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, re, random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin, quote

from curl_cffi import requests as curl_requests
from eternal_harvester_config import (
    FLASHSCORE_CONFIG,
    LOGS_DIR, DB_PATH, get_rate_limiter, save_checkpoint, load_checkpoint,
    log_event, get_db,
)

# ─── Constants ───────────────────────────────────────────────────────────────
# Using SofaScore API instead of Flashscore (Flashscore uses SPA/WebSocket only)
SOFA_BASE = 'https://www.sofascore.com/api/v1'
SOFA_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/',
}

RATE_LIMITER = get_rate_limiter('flashscore', 20)
LOG_FILE = LOGS_DIR / 'flashscore.log'
CHECKPOINT_KEY = 'flashscore'

# Rate limiting for SofaScore
_sofa_last_req = 0

# ─── SofaScore tournament ID map ──────────────────────────────────────────
# Searched via GET /api/v1/search/unique-tournaments?q={name}
SOFASCORE_TOURNAMENT_IDS = {
    'england/premier-league': 17,
    'england/championship': 18,
    'england/league-one': 24,
    'england/league-two': 25,
    'spain/laliga': 8,
    'spain/laliga2': 54,
    'germany/bundesliga': 35,
    'germany/2-bundesliga': 44,
    'germany/3-liga': 491,
    'italy/serie-a': 23,
    'italy/serie-b': 26,  # Serie B
    'france/ligue-1': 34,
    'france/ligue-2': 182,
    'netherlands/eredivisie': 37,
    'portugal/primeira-liga': 238,  # Liga Portugal Betclic
    'turkey/super-lig': 52,  # Super Lig
    'belgium/jupiler-pro-league': 38,  # Pro League
    'scotland/premiership': 36,
    'austria/bundesliga': 45,  # Austrian Bundesliga
    'switzerland/super-league': 215,  # Swiss Super League
    'greece/super-league': 185,  # Stoiximan Super League
    'russia/premier-league': 203,  # Russian Premier League
    'poland/ekstraklasa': 202,
    'croatia/hnl': 170,  # HNL
    'denmark/superliga': 39,
    'sweden/allsvenskan': 40,
    'norway/eliteserien': 20,
    'brazil/serie-a': 13,  # Brasileirao Serie A
    'argentina/primera-division': 15,  # Argentine Primera Division
    'mexico/liga-mx': 11621,  # Liga MX (Apertura — current half-season)
    'usa/mls': 242,
    'japan/j1-league': 196,
    'australia/a-league': 136,
    'saudi-arabia/pro-league': 955,
}

# League name mapping for display
LEAGUE_NAMES = {
    'england/premier-league': 'England Premier League',
    'england/championship': 'England Championship',
    'england/league-one': 'England League One',
    'england/league-two': 'England League Two',
    'spain/laliga': 'Spain La Liga',
    'spain/laliga2': 'Spain La Liga 2',
    'germany/bundesliga': 'Germany Bundesliga',
    'germany/2-bundesliga': 'Germany 2. Bundesliga',
    'germany/3-liga': 'Germany 3. Liga',
    'italy/serie-a': 'Italy Serie A',
    'italy/serie-b': 'Italy Serie B',
    'france/ligue-1': 'France Ligue 1',
    'france/ligue-2': 'France Ligue 2',
    'netherlands/eredivisie': 'Netherlands Eredivisie',
    'portugal/primeira-liga': 'Portugal Liga Portugal',
    'turkey/super-lig': 'Turkey Super Lig',
    'belgium/jupiler-pro-league': 'Belgium Pro League',
    'scotland/premiership': 'Scotland Premiership',
    'austria/bundesliga': 'Austria Bundesliga',
    'switzerland/super-league': 'Switzerland Super League',
    'greece/super-league': 'Greece Super League',
    'russia/premier-league': 'Russia Premier League',
    'poland/ekstraklasa': 'Poland Ekstraklasa',
    'croatia/hnl': 'Croatia HNL',
    'denmark/superliga': 'Denmark Superliga',
    'sweden/allsvenskan': 'Sweden Allsvenskan',
    'norway/eliteserien': 'Norway Eliteserien',
    'brazil/serie-a': 'Brazil Serie A',
    'argentina/primera-division': 'Argentina Primera Division',
    'mexico/liga-mx': 'Mexico Liga MX',
    'usa/mls': 'USA MLS',
    'japan/j1-league': 'Japan J1 League',
    'australia/a-league': 'Australia A-League',
    'saudi-arabia/pro-league': 'Saudi Pro League',
}


# ─── Logging ─────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [flashscore] {msg}'
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    try:
        log_event('flashscore', level, msg)
    except Exception:
        pass  # DB might be locked


def _random_delay():
    time.sleep(random.uniform(0.5, 2.0))


# ─── SofaScore API client ───────────────────────────────────────────────────
def _sofa_get(path: str, params: dict = None, retries: int = 3) -> Optional[dict]:
    """Make a SofaScore API request with rate limiting."""
    global _sofa_last_req

    url = f'{SOFA_BASE}{path}'
    if params:
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        url = f'{url}?{qs}'

    for attempt in range(retries):
        # Rate limit: max 3 requests/sec
        now = time.time()
        since_last = now - _sofa_last_req
        if since_last < 0.35:
            time.sleep(0.35 - since_last)

        with RATE_LIMITER:
            try:
                r = curl_requests.get(
                    url,
                    headers=SOFA_HEADERS,
                    impersonate='chrome124',
                    timeout=(15, 60),
                )
                _sofa_last_req = time.time()

                if r.status_code == 200:
                    return json.loads(r.text)
                elif r.status_code == 429:
                    _log(f'SofaScore 429 rate limited, waiting', 'WARN')
                    time.sleep(5 + 2 ** attempt)
                    continue
                elif r.status_code == 404:
                    return None
                else:
                    _log(f'SofaScore HTTP {r.status_code} for {path}', 'WARN')
                    if attempt < retries - 1:
                        time.sleep(1 + attempt)
                    continue
            except Exception as e:
                _log(f'SofaScore fetch error ({path}): {e}', 'WARN')
                if attempt < retries - 1:
                    time.sleep(1 + 2 ** attempt)
                continue

    return None


def _resolve_tournament_id(slug: str) -> Optional[int]:
    """Resolve a league slug to a SofaScore unique tournament ID."""
    if slug in SOFASCORE_TOURNAMENT_IDS:
        return SOFASCORE_TOURNAMENT_IDS[slug]

    # Fallback: search SofaScore for this tournament
    # Extract league name from slug (e.g., 'england/premier-league' -> 'premier league')
    parts = slug.split('/')
    search_term = parts[-1].replace('-', '+') if parts else slug.replace('-', '+')

    _log(f'Searching SofaScore for tournament: {search_term}', 'INFO')
    data = _sofa_get(f'/search/unique-tournaments?q={search_term}')
    if data and 'results' in data:
        for result in data['results']:
            entity = result.get('entity', {})
            eid = entity.get('id')
            if eid:
                return eid

    return None


def _get_current_season(tournament_id: int) -> Optional[int]:
    """Get the current (latest) season ID for a tournament."""
    data = _sofa_get(f'/unique-tournament/{tournament_id}/seasons')
    if not data:
        return None

    seasons = data.get('seasons', [])
    if not seasons:
        return None

    # First season in the list is typically the current one
    return seasons[0].get('id')


def _get_rounds(tournament_id: int, season_id: int) -> List[int]:
    """Get all round numbers for a tournament season."""
    data = _sofa_get(f'/unique-tournament/{tournament_id}/season/{season_id}/rounds')
    if not data:
        return []

    rounds = []
    for rnd in data.get('rounds', []):
        rnum = rnd.get('round')
        if rnum is not None:
            rounds.append(rnum)
    return sorted(rounds)


def _get_events_for_round(tournament_id: int, season_id: int, round_num: int) -> List[Dict]:
    """Get all events (matches) for a specific round."""
    data = _sofa_get(
        f'/unique-tournament/{tournament_id}/season/{season_id}/events/round/{round_num}'
    )
    if not data:
        return []

    return data.get('events', [])


def _parse_event(event: Dict, competition: str) -> Dict:
    """Parse a SofaScore event into our standard match format."""
    home_team = event.get('homeTeam', {}) or {}
    away_team = event.get('awayTeam', {}) or {}
    home_score = event.get('homeScore', {}) or {}
    away_score = event.get('awayScore', {}) or {}
    status = event.get('status', {}) or {}

    match_id = str(event.get('id', ''))
    ts = event.get('startTimestamp', 0)
    if ts:
        dt = datetime.fromtimestamp(ts)
        ts_str = dt.strftime('%Y-%m-%d %H:%M')
    else:
        ts_str = ''

    match = {
        'match_id': match_id,
        'home_team': home_team.get('name', ''),
        'away_team': away_team.get('name', ''),
        'home_score': str(home_score.get('current', '')) if home_score.get('current') is not None else '',
        'away_score': str(away_score.get('current', '')) if away_score.get('current') is not None else '',
        'competition': competition,
        'ts': ts_str,
        'status': status.get('type', ''),
    }
    return match


# ─── DB ─────────────────────────────────────────────────────────────────────
def _ensure_tables():
    """Ensure Flashscore tables exist."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS flashscore_matches (
            match_id TEXT PRIMARY KEY,
            home_team TEXT,
            away_team TEXT,
            home_score TEXT,
            away_score TEXT,
            competition TEXT,
            ts TEXT,
            stats_json TEXT,
            fetched_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS flashscore_lineups (
            match_id TEXT PRIMARY KEY,
            home_formation TEXT,
            away_formation TEXT,
            home_players TEXT,
            away_players TEXT,
            fetched_at TEXT,
            FOREIGN KEY(match_id) REFERENCES flashscore_matches(match_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS flashscore_h2h (
            match_id TEXT,
            opponent TEXT,
            played TEXT,
            home_wins INTEGER,
            away_wins INTEGER,
            draws INTEGER,
            home_goals INTEGER,
            away_goals INTEGER,
            last_matches TEXT,
            PRIMARY KEY (match_id, opponent)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS flashscore_odds (
            match_id TEXT,
            bookmaker TEXT,
            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,
            timestamp TEXT,
            PRIMARY KEY (match_id, bookmaker, timestamp)
        )
    ''')
    conn.commit()
    conn.close()


# ─── Match detail from SofaScore ────────────────────────────────────────────
def _fetch_match_detail(event_id: int) -> Optional[Dict]:
    """Fetch match details including statistics from SofaScore."""
    data = _sofa_get(f'/event/{event_id}')
    if not data:
        return None

    event = data.get('event', {})
    detail = {
        'match_id': str(event_id),
        'event': event,
    }

    # Extract statistics
    stats_data = _sofa_get(f'/event/{event_id}/statistics')
    if stats_data:
        detail['statistics'] = stats_data.get('statistics', [])

    # Extract lineups
    lineup_data = _sofa_get(f'/event/{event_id}/lineups')
    if lineup_data:
        detail['lineups'] = {
            'home': lineup_data.get('home', {}),
            'away': lineup_data.get('away', {}),
        }

    return detail


def _fetch_h2h(event_id: int) -> Optional[List[Dict]]:
    """Fetch H2H data for a match from SofaScore."""
    data = _sofa_get(f'/event/{event_id}/h2h')
    if not data:
        return None

    h2h_matches = []
    for h2h_event in data.get('events', []):
        ht = h2h_event.get('homeTeam', {}) or {}
        at = h2h_event.get('awayTeam', {}) or {}
        hs = h2h_event.get('homeScore', {}) or {}
        aws = h2h_event.get('awayScore', {}) or {}
        ts = h2h_event.get('startTimestamp', 0)

        date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts else ''
        score = f"{hs.get('current', '?')}-{aws.get('current', '?')}"

        h2h_matches.append({
            'date': date_str,
            'home_team': ht.get('name', ''),
            'away_team': at.get('name', ''),
            'score': score,
            'home_score': hs.get('current'),
            'away_score': aws.get('current'),
        })

    return h2h_matches if h2h_matches else None


def parse_h2h(match_id: str) -> Optional[List[Dict]]:
    """Public API: parse H2H for a match (via SofaScore API)."""
    try:
        return _fetch_h2h(int(match_id))
    except ValueError:
        return None


def parse_match_detail(match_id: str) -> Optional[Dict]:
    """Public API: parse match detail (via SofaScore API)."""
    try:
        return _fetch_match_detail(int(match_id))
    except ValueError:
        return None


# ─── Main harvest ──────────────────────────────────────────────────────────
def harvest_league_matches(league_slug: str, league_name: str) -> Dict:
    """Harvest all matches for a league from SofaScore API.

    Gets: match list (all rounds) → details → lineups → H2H
    """
    # Resolve SofaScore tournament ID
    tournament_id = _resolve_tournament_id(league_slug)
    if tournament_id is None:
        _log(f'No SofaScore tournament ID for {league_slug}', 'ERROR')
        return {'matches': 0, 'errors': 1}

    # Get current season
    season_id = _get_current_season(tournament_id)
    if season_id is None:
        _log(f'No season found for tournament {tournament_id}', 'ERROR')
        return {'matches': 0, 'errors': 1}

    _log(f'{league_name}: SofaScore tournament={tournament_id} season={season_id}')

    # Get all rounds
    rounds = _get_rounds(tournament_id, season_id)
    if not rounds:
        _log(f'No rounds found for tournament {tournament_id}', 'WARN')
        return {'matches': 0, 'errors': 0}

    _log(f'{league_name}: {len(rounds)} rounds')

    conn = get_db()
    conn.execute('BEGIN TRANSACTION')
    now = datetime.now().isoformat()

    saved = 0
    detail_saved = 0
    h2h_saved = 0
    errors = 0

    for round_num in rounds:
        _random_delay()

        events = _get_events_for_round(tournament_id, season_id, round_num)
        if not events:
            conn.commit()
            continue

        for event in events:
            match = _parse_event(event, league_name)
            match_id = match.get('match_id')
            if not match_id:
                continue

            try:
                # Save match
                conn.execute('''
                    INSERT OR REPLACE INTO flashscore_matches
                        (match_id, home_team, away_team, home_score, away_score,
                         competition, ts, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id, match['home_team'], match['away_team'],
                    match['home_score'], match['away_score'],
                    match['competition'], match['ts'], now,
                ))
                saved += 1

                # Fetch details for first 10 matches only
                if saved <= 10:
                    _random_delay()
                    detail = _fetch_match_detail(int(match_id))
                    if detail:
                        # Save statistics as JSON
                        if 'statistics' in detail and detail['statistics']:
                            stats_json = json.dumps(detail['statistics'])
                            conn.execute('''
                                UPDATE flashscore_matches SET stats_json = ? WHERE match_id = ?
                            ''', (stats_json, match_id))
                            detail_saved += 1

                        # Save lineups
                        if 'lineups' in detail and detail['lineups']:
                            lineups = detail['lineups']
                            home = lineups.get('home', {})
                            away = lineups.get('away', {})

                            # Extract formation
                            home_formation = ''
                            away_formation = ''
                            home_players = []
                            away_players = []

                            if home:
                                home_formation = home.get('formation', '')
                                for player in home.get('players', []):
                                    pname = player.get('name', '')
                                    if pname:
                                        home_players.append(pname)

                            if away:
                                away_formation = away.get('formation', '')
                                for player in away.get('players', []):
                                    pname = player.get('name', '')
                                    if pname:
                                        away_players.append(pname)

                            conn.execute('''
                                INSERT OR REPLACE INTO flashscore_lineups
                                    (match_id, home_formation, away_formation,
                                     home_players, away_players, fetched_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                match_id,
                                home_formation,
                                away_formation,
                                json.dumps(home_players),
                                json.dumps(away_players),
                                now,
                            ))

                    # Fetch H2H
                    _random_delay()
                    h2h = _fetch_h2h(int(match_id))
                    if h2h:
                        for h in h2h[:10]:  # Last 10 H2H matches
                            # Determine opponent
                            if h.get('home_team') == match['home_team']:
                                opponent = h.get('away_team', '')
                                home_goals = h.get('home_score')
                                away_goals = h.get('away_score')
                            else:
                                opponent = h.get('home_team', match['away_team'])
                                home_goals = h.get('away_score')
                                away_goals = h.get('home_score')

                            if opponent:
                                hg = int(home_goals) if home_goals is not None else None
                                ag = int(away_goals) if away_goals is not None else None
                                conn.execute('''
                                    INSERT OR REPLACE INTO flashscore_h2h
                                        (match_id, opponent, played, home_wins, away_wins,
                                         draws, home_goals, away_goals, timestamp)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    match_id, opponent, h.get('date', ''),
                                    1 if hg is not None and ag is not None and hg > ag else 0,
                                    1 if hg is not None and ag is not None and ag > hg else 0,
                                    1 if hg is not None and ag is not None and hg == ag else 0,
                                    hg, ag, now,
                                ))
                                h2h_saved += 1

            except Exception as e:
                _log(f'Error saving match {match_id}: {e}', 'WARN')
                errors += 1
                continue

    conn.commit()
    conn.close()

    _log(f'{league_name}: {saved} matches, {detail_saved} details, {h2h_saved} H2H, {errors} errors')

    return {
        'matches': saved,
        'details': detail_saved,
        'h2h': h2h_saved,
        'errors': errors,
    }


def _extract_score(score_str: str, index: int) -> Optional[int]:
    """Extract home (0) or away (1) score from '3-1' format."""
    if ':' in score_str:
        parts = score_str.split(':')
    elif '-' in score_str:
        parts = score_str.split('-')
    else:
        return None
    try:
        return int(parts[index].strip())
    except (ValueError, IndexError):
        return None


def harvest_all(checkpoint: bool = True, force_refresh: bool = False,
                max_leagues: int = 40) -> Dict:
    """Harvest all leagues via SofaScore API.

    Args:
        checkpoint: Save progress
        force_refresh: Re-fetch
        max_leagues: Max leagues

    Returns:
        Stats dict
    """
    _ensure_tables()

    start_time = time.time()
    total_matches = 0
    total_details = 0
    total_h2h = 0
    total_errors = 0
    leagues_done = 0

    completed = set()
    if not force_refresh:
        cp = load_checkpoint(CHECKPOINT_KEY)
        if cp:
            completed = set(cp['data'].get('completed', []))

    # Use all slugs available
    all_slugs = list(LEAGUE_NAMES.keys())[:max_leagues]

    for slug in all_slugs:
        if slug in completed and not force_refresh:
            continue

        name = LEAGUE_NAMES.get(slug, slug)
        _log(f'Harvesting {name}...')
        _random_delay()

        result = harvest_league_matches(slug, name)
        total_matches += result.get('matches', 0)
        total_details += result.get('details', 0)
        total_h2h += result.get('h2h', 0)
        total_errors += result.get('errors', 0)
        leagues_done += 1
        completed.add(slug)

        if leagues_done % 5 == 0 and checkpoint:
            save_checkpoint(CHECKPOINT_KEY, {
                'completed': list(completed),
            }, total_matches + total_details, total_errors)

    duration = time.time() - start_time
    _log(f'Flashscore complete: {leagues_done} leagues, {total_matches} matches, '
         f'{total_details} details, {total_h2h} H2H, {total_errors} errors, '
         f'{duration:.1f}s')

    if checkpoint:
        save_checkpoint(CHECKPOINT_KEY, {
            'completed': list(completed),
        }, total_matches + total_details + total_h2h, total_errors)

    return {
        'source': 'flashscore',
        'leagues_processed': leagues_done,
        'matches': total_matches,
        'match_details': total_details,
        'h2h_records': total_h2h,
        'errors': total_errors,
        'duration_seconds': duration,
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Flashscore data harvester (SofaScore bridge)')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--max-leagues', type=int, default=10)
    parser.add_argument('--single', type=str, help='Single league slug')
    args = parser.parse_args()

    if args.single:
        name = LEAGUE_NAMES.get(args.single, args.single)
        result = harvest_league_matches(args.single, name)
        print(json.dumps(result, indent=2))
    else:
        result = harvest_all(force_refresh=args.force, max_leagues=args.max_leagues)
        print(json.dumps(result, indent=2))
