#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              HARVESTER: OddsPortal — historical odds movement             ▓
▓  Tracks opening vs closing prices, sharp money movement, line movement    ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, re, random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin, quote, urlparse
from bs4 import BeautifulSoup

from curl_cffi import requests as curl_requests
from eternal_harvester_config import (
    ODDSPORTAL_CONFIG,
    LOGS_DIR, DB_PATH, get_rate_limiter, save_checkpoint, load_checkpoint,
    log_event, get_db,
)

# ─── Constants ───────────────────────────────────────────────────────────────
BASE = ODDSPORTAL_CONFIG.base_url
RATE_LIMITER = get_rate_limiter('oddsportal', 8)
LOG_FILE = LOGS_DIR / 'oddsportal.log'
CHECKPOINT_KEY = 'oddsportal'

# Rotating headers
HEADERS_TEMPLATES = [
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.oddsportal.com/',
    },
    {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.9',
        'Referer': 'https://www.oddsportal.com/soccer/',
    },
]

# ─── Logging ─────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [oddsportal] {msg}'
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('oddsportal', level, msg)


def _random_delay(min_s: float = 3.0, max_s: float = 8.0):
    """Random delay for OddsPortal."""
    time.sleep(random.uniform(min_s, max_s))


def _get_headers() -> Dict:
    return random.choice(HEADERS_TEMPLATES)


# ─── Fetching ────────────────────────────────────────────────────────────────
def _fetch(url: str, retries: int = 10) -> Optional[str]:
    """Fetch with extreme care for OddsPortal (very aggressive blocking)."""
    for attempt in range(retries):
        with RATE_LIMITER:
            try:
                r = curl_requests.get(
                    url,
                    headers=_get_headers(),
                    impersonate=random.choice(['chrome124', 'chrome120', 'chrome124']),
                    timeout=(30, ODDSPORTAL_CONFIG.timeout),  # (connect, read) timeout
                )
                if r.status_code == 200:
                    text = r.text
                    # Check for bot detection
                    if len(text) < 500 or 'captcha' in text.lower()[:1000] or 'blocked' in text.lower()[:1000]:
                        wait = (3.0 ** attempt) + random.uniform(5, 20)
                        _log(f'Possible bot block, waiting {wait:.0f}s (attempt {attempt+1})', 'WARN')
                        time.sleep(wait)
                        continue
                    return text
                elif r.status_code == 429:
                    wait = (3.0 ** attempt) + random.uniform(5, 20)
                    _log(f'429 rate limited, waiting {wait:.0f}s', 'WARN')
                    time.sleep(wait)
                    continue
                elif r.status_code == 403:
                    _log(f'403 Forbidden on {url}', 'WARN')
                    time.sleep(30 + random.uniform(0, 30))
                    continue
                elif r.status_code == 404:
                    return None
                else:
                    _log(f'HTTP {r.status_code}', 'WARN')
                    time.sleep(5 + 2 ** attempt)
                    continue
            except Exception as e:
                _log(f'Fetch error (attempt {attempt+1}): {e}', 'WARN')
                time.sleep(ODDSPORTAL_CONFIG.retry_backoff_base ** attempt + 2)
                continue
    _log(f'Failed after {retries} retries: {url}', 'ERROR')
    return None


# ─── DB ─────────────────────────────────────────────────────────────────────
def _ensure_tables():
    """Ensure OddsPortal tables exist."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS oddsportal_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            home_team TEXT,
            away_team TEXT,
            league TEXT,
            date TEXT,
            score TEXT,
            opening_odds_json TEXT,
            closing_odds_json TEXT,
            odds_history_json TEXT,
            avg_movement_h REAL,
            avg_movement_d REAL,
            avg_movement_a REAL,
            fetched_at REAL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS oddsportal_odds_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_url TEXT,
            timestamp TEXT,
            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,
            bookmaker TEXT,
            FOREIGN KEY(match_url) REFERENCES oddsportal_matches(url)
        )
    ''')
    conn.commit()
    conn.close()


# ─── Parsers ─────────────────────────────────────────────────────────────────
def _parse_odds(val_str: str) -> Optional[float]:
    """Parse decimal odds from string."""
    if not val_str or val_str in ('-', ''):
        return None
    try:
        return float(val_str.strip())
    except ValueError:
        return None


def _extract_d_rows(html: str) -> Optional[List[Dict]]:
    """Extract match data from OddsPortal's embedded JSON (React state).

    OddsPortal now uses a React SPA. Match data is embedded in the HTML
    as HTML-escaped JSON in the format:
        &quot;d&quot;:{&quot;total&quot;:N,&quot;rows&quot;:[{...match objects...}]}
    Returns a list of match dicts, or None if extraction fails.
    """
    # Find the embedded data: &quot;d&quot;:{&quot;total&quot;:...,&quot;rows&quot;:[...]}
    idx = html.find('&quot;d&quot;:{&quot;total&quot;')
    if idx < 0:
        # Try without HTML entities (some responses may be different)
        idx = html.find('"d":{"total"')
    if idx < 0:
        return None

    # Find the opening brace of the d value
    open_brace = html.find('{', idx)
    if open_brace < 0:
        return None

    # Find the matching closing brace
    depth = 0
    pos = open_brace
    while pos < len(html):
        if html[pos] == '{':
            depth += 1
        elif html[pos] == '}':
            depth -= 1
            if depth == 0:
                break
        pos += 1

    if depth != 0:
        return None

    # Extract the d value and unescape HTML entities
    d_value = html[open_brace:pos+1]
    # Replace HTML entity quotes with actual quotes
    json_str = d_value.replace('&quot;', '"')
    # Also handle &#x27; (apostrophe)
    json_str = json_str.replace('&#x27;', "'")

    try:
        data = json.loads(json_str)
        rows = data.get('rows', [])
        return rows
    except (json.JSONDecodeError, KeyError) as e:
        _log(f'Failed to parse embedded JSON: {e}', 'WARN')
        return None


def get_league_matches(league_slug: str, max_pages: int = 5) -> List[Dict]:
    """Get all matches for a league from OddsPortal.

    OddsPortal now uses a React SPA. Match data is embedded as
    JSON in the HTML, not in HTML table rows. This function
    extracts the embedded JSON and parses it.

    URL pattern: /soccer/{country}/{league}/results/
    """
    matches = []

    for page in range(1, max_pages + 1):
        if page == 1:
            url = f'{BASE}/soccer/{league_slug}/results/'
        else:
            url = f'{BASE}/soccer/{league_slug}/results/#/page/{page}/'

        _log(f'Fetching league page {page}: {league_slug}')
        _random_delay()

        html = _fetch(url)
        if not html:
            _log(f'No data for {league_slug} page {page}', 'WARN')
            break

        # Extract embedded JSON data (React state)
        rows = _extract_d_rows(html)
        if not rows:
            _log(f'No embedded data found for {league_slug} page {page}', 'WARN')
            break

        for row in rows:
            try:
                home_team = row.get('home-name', '')
                away_team = row.get('away-name', '')
                if not home_team or not away_team:
                    continue

                # Match URL
                match_url_path = row.get('url', '')
                match_url = urljoin(BASE, match_url_path) if match_url_path else ''

                # Score
                home_result = row.get('homeResult', '') or ''
                away_result = row.get('awayResult', '') or ''
                if home_result and away_result:
                    score = f'{home_result}:{away_result}'
                else:
                    score = ''

                # Date
                timestamp = row.get('date-start-timestamp', 0)
                if timestamp:
                    from datetime import datetime
                    date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                else:
                    date = ''

                # Odds are NOT embedded in the initial page.
                # They come from a separate AJAX endpoint.
                # The 'cols' field (e.g. '1|X|2') tells which columns exist.
                odds_h, odds_d, odds_a = None, None, None

                matches.append({
                    'url': match_url,
                    'home_team': home_team,
                    'away_team': away_team,
                    'date': date,
                    'score': score,
                    'odds_h': odds_h,
                    'odds_d': odds_d,
                    'odds_a': odds_a,
                    'league_slug': league_slug,
                    'match_id': row.get('id'),
                    'encode_event_id': row.get('encodeEventId', ''),
                    'status': row.get('event-stage-name', ''),
                })

            except Exception as e:
                _log(f'Error parsing match row: {e}', 'WARN')
                continue

        # Check if no more results
        if len(rows) == 0:
            break

    _log(f'Found {len(matches)} matches for {league_slug}')
    return matches


def get_match_odds_history(match_url: str) -> Optional[Dict]:
    """Get detailed odds history for a single match.

    Includes opening/closing prices and movement data.
    """
    full_url = urljoin(BASE, match_url) if not match_url.startswith('http') else match_url

    _random_delay()
    html = _fetch(full_url + '#odds-history')
    if not html:
        html = _fetch(full_url)

    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    history = {
        'url': full_url,
        'open_h': None, 'open_d': None, 'open_a': None,
        'close_h': None, 'close_d': None, 'close_a': None,
        'movements': [],
    }

    # Look for average odds
    avg_rows = soup.find_all('tr', class_=re.compile(r'avg|average'))
    for row in avg_rows:
        tds = row.find_all('td')
        if len(tds) >= 4:
            history['open_h'] = _parse_odds(tds[0].get_text(strip=True))
            history['open_d'] = _parse_odds(tds[1].get_text(strip=True))
            history['open_a'] = _parse_odds(tds[2].get_text(strip=True))

            # Closing odds might be the last row
            history['close_h'] = _parse_odds(tds[-3].get_text(strip=True)) if len(tds) >= 3 else None
            history['close_d'] = _parse_odds(tds[-2].get_text(strip=True)) if len(tds) >= 2 else None
            history['close_a'] = _parse_odds(tds[-1].get_text(strip=True))

    # Look for odds movement table
    movement_table = soup.find('table', {'class': re.compile(r'movement|odds_movement')})
    if movement_table:
        for tr in movement_table.find_all('tr')[1:]:  # Skip header
            tds = tr.find_all('td')
            if len(tds) >= 5:
                movement = {
                    'time': tds[0].get_text(strip=True),
                    'bookmaker': tds[1].get_text(strip=True) if len(tds) > 1 else '',
                    '1': _parse_odds(tds[2].get_text(strip=True)) if len(tds) > 2 else None,
                    'X': _parse_odds(tds[3].get_text(strip=True)) if len(tds) > 3 else None,
                    '2': _parse_odds(tds[4].get_text(strip=True)) if len(tds) > 4 else None,
                }
                history['movements'].append(movement)

    return history


# ─── OddsPortal League Slugs ────────────────────────────────────────────────
LEAGUE_SLUGS = [
    # England
    'england/premier-league',
    'england/championship',
    'england/league-one',
    'england/league-two',
    # Spain
    'spain/laliga',
    'spain/laliga2',
    # Germany
    'germany/bundesliga',
    'germany/2-bundesliga',
    'germany/3-liga',
    # Italy
    'italy/serie-a',
    'italy/serie-b',
    # France
    'france/ligue-1',
    'france/ligue-2',
    # Netherlands
    'netherlands/eredivisie',
    # Portugal
    'portugal/primeira-liga',
    # Turkey
    'turkey/super-lig',
    # Belgium
    'belgium/jupiler-pro-league',
    # Scotland
    'scotland/premiership',
    # Austria
    'austria/bundesliga',
    # Switzerland
    'switzerland/super-league',
    # Greece
    'greece/super-league',
    # Russia
    'russia/premier-league',
    # Poland
    'poland/ekstraklasa',
    # Croatia
    'croatia/hnl',
    # Denmark
    'denmark/superliga',
    # Sweden
    'sweden/allsvenskan',
    # Norway
    'norway/eliteserien',
    # Brazil
    'brazil/serie-a',
    # Argentina
    'argentina/primera-division',
    # Mexico
    'mexico/liga-mx',
    # USA
    'usa/mls',
    # Japan
    'japan/j1-league',
    # Australia
    'australia/a-league',
    # Saudi Arabia
    'saudi-arabia/pro-league',
]


# ─── Main harvest ──────────────────────────────────────────────────────────
def harvest_all(checkpoint: bool = True, force_refresh: bool = False,
                max_leagues: int = 35) -> Dict:
    """Harvest OddsPortal for all leagues.

    Args:
        checkpoint: Save progress checkpoints
        force_refresh: Re-fetch cached leagues
        max_leagues: Max leagues to process

    Returns:
        Stats dict
    """
    _ensure_tables()

    start_time = time.time()
    total_matches = 0
    total_histories = 0
    total_errors = 0
    leagues_done = 0

    completed = set()
    if not force_refresh:
        cp = load_checkpoint(CHECKPOINT_KEY)
        if cp:
            completed = set(cp['data'].get('completed', []))

    slugs = LEAGUE_SLUGS[:max_leagues]
    _log(f'OddsPortal harvest: {len(slugs)} leagues')

    conn = get_db()

    for slug in slugs:
        if slug in completed and not force_refresh:
            continue

        _log(f'Processing {slug}...')
        # Delay is inside get_league_matches; no extra delay here

        try:
            matches = get_league_matches(slug, max_pages=3)
        except Exception as e:
            _log(f'Error fetching {slug}: {e}', 'ERROR')
            total_errors += 1
            continue

        leagues_done += 1
        inserted = 0

        for match in matches:
            try:
                match_url = match.get('url', '')
                if not match_url:
                    continue

                # Try to get odds history for a sample of matches
                opening_json = None
                closing_json = None
                history_json = None

                # Only fetch history for first 20 matches per league
                if inserted < 20:
                    try:
                        history = get_match_odds_history(match_url)
                        if history:
                            opening_json = json.dumps({
                                '1': history.get('open_h'),
                                'X': history.get('open_d'),
                                '2': history.get('open_a'),
                            })
                            closing_json = json.dumps({
                                '1': history.get('close_h'),
                                'X': history.get('close_d'),
                                '2': history.get('close_a'),
                            })
                            history_json = json.dumps(history.get('movements', []))

                            # Also save individual snapshots
                            for mov in history.get('movements', []):
                                conn.execute('''
                                    INSERT OR REPLACE INTO oddsportal_odds_snapshots
                                        (match_url, timestamp, home_odds, draw_odds,
                                         away_odds, bookmaker)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (
                                    match_url,
                                    mov.get('time', ''),
                                    mov.get('1'),
                                    mov.get('X'),
                                    mov.get('2'),
                                    mov.get('bookmaker', ''),
                                ))
                            total_histories += 1
                    except Exception as e:
                        _log(f'History fetch error: {e}', 'WARN')

                # Calculate average movement
                avg_h = None
                avg_d = None
                avg_a = None
                if opening_json and closing_json:
                    try:
                        op = json.loads(opening_json)
                        cl = json.loads(closing_json)
                        if op.get('1') and cl.get('1'):
                            avg_h = cl['1'] - op['1']
                        if op.get('X') and cl.get('X'):
                            avg_d = cl['X'] - op['X']
                        if op.get('2') and cl.get('2'):
                            avg_a = cl['2'] - op['2']
                    except Exception:
                        pass

                conn.execute('''
                    INSERT OR IGNORE INTO oddsportal_matches
                        (url, home_team, away_team, league, date, score,
                         opening_odds_json, closing_odds_json, odds_history_json,
                         avg_movement_h, avg_movement_d, avg_movement_a, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_url,
                    match.get('home_team', ''),
                    match.get('away_team', ''),
                    slug,
                    match.get('date', ''),
                    match.get('score', ''),
                    opening_json,
                    closing_json,
                    history_json,
                    avg_h, avg_d, avg_a,
                    time.time(),
                ))
                inserted += 1
                total_matches += 1

            except Exception as e:
                _log(f'Error saving match: {e}', 'WARN')
                total_errors += 1

        conn.commit()
        completed.add(slug)
        _log(f'{slug}: {inserted} matches')

        if checkpoint:
            save_checkpoint(CHECKPOINT_KEY, {
                'completed': list(completed),
            }, total_matches, total_errors)

    conn.close()
    duration = time.time() - start_time

    _log(f'OddsPortal complete: {leagues_done} leagues, {total_matches} matches, '
         f'{total_histories} histories, {total_errors} errors, {duration:.1f}s')

    if checkpoint:
        save_checkpoint(CHECKPOINT_KEY, {
            'completed': list(completed),
        }, total_matches, total_errors)

    return {
        'source': 'oddsportal',
        'leagues_processed': leagues_done,
        'matches': total_matches,
        'odds_histories': total_histories,
        'errors': total_errors,
        'duration_seconds': duration,
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='OddsPortal odds movement harvester')
    parser.add_argument('--force', action='store_true', help='Force re-fetch')
    parser.add_argument('--max-leagues', type=int, default=10)
    args = parser.parse_args()

    result = harvest_all(force_refresh=args.force, max_leagues=args.max_leagues)
    print(json.dumps(result, indent=2))
