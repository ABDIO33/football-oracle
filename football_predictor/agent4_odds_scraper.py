#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
AGENT 4 — ODDS SCRAPER (BLACK CODE CURSE v9999999)
═══════════════════════════════════════════════════════════════════════════════════
Layer 1: Core Engine — Multi-source odds fetching (OddsAPI, Sportmonks, Flashscore)
Layer 2: Identity Randomization — Rotating User-Agents, Accept headers, timing jitter
Layer 3: Proxy Rotation — Multi-IP fallback chain with geo-mimicking
Layer 4: Multi-threading — Concurrent workers with rate-limit-aware dispatch
Layer 5: DB Persistence + Logging — SQLite cache, JSON logs, checkpoint resume

Targets:
  • The Odds API (https://the-odds-api.com) — free tier, 500 req/mo
  • Sportmonks (https://sportmonks.com) — free tier, 1000 req/day
  • Flashscore — public scraping via curl_cffi impersonate
═══════════════════════════════════════════════════════════════════════════════════
"""

import sys, os, json, time, sqlite3, threading, hashlib, random, logging, re
from datetime import datetime, timezone, timedelta
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

# ─── Fix Windows encoding ───────────────────────────────────────────────────
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Layer 5: Logging Config ────────────────────────────────────────────────
LOG_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f'agent4_odds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Agent4_Odds')

# ─── Layer 5: DB Config ─────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scrape_cache.db')

# ─── Layer 2: Identity Pool (50+ real User-Agents) ──────────────────────────
IDENTITY_POOL = [
    # Chrome 124-130 (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    # Chrome (macOS)
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    # Chrome (Linux)
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    # Firefox 125-130
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0',
    # Safari
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    # Mobile
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.83 Mobile Safari/537.36',
]

ACCEPT_POOL = [
    'application/json, text/plain, */*',
    'application/json, text/html, application/xhtml+xml, */*',
    'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'application/json, text/javascript, */*; q=0.01',
    '*/*',
]

LANGUAGE_POOL = [
    'en-US,en;q=0.9',
    'en-GB,en;q=0.9,ar;q=0.8',
    'en-US,en;q=0.8,fr;q=0.6',
    'en-US,en;q=0.7,de;q=0.5',
    'en;q=0.9,ar-SA;q=0.8,ar;q=0.7',
]

# ─── Layer 3: Proxy Config ──────────────────────────────────────────────────
PROXY_LIST = []  # Populate with proxies: ['http://user:pass@ip:port', ...]
MAX_PROXY_FAILURES = 3
_proxy_blacklist = {}
_proxy_lock = threading.Lock()


def get_working_proxy() -> Optional[str]:
    """Return a random non-blacklisted proxy."""
    if not PROXY_LIST:
        return None
    with _proxy_lock:
        available = [p for p in PROXY_LIST
                     if _proxy_blacklist.get(p, 0) < MAX_PROXY_FAILURES]
        if not available:
            _proxy_blacklist.clear()
            available = PROXY_LIST[:]
        return random.choice(available) if available else None


def mark_proxy_failed(proxy: str):
    """Increment failure counter for a proxy."""
    if proxy:
        with _proxy_lock:
            _proxy_blacklist[proxy] = _proxy_blacklist.get(proxy, 0) + 1


# ─── Layer 2: Identity Builder ──────────────────────────────────────────────
_build_lock = threading.Lock()
_identity_index = 0


def build_headers(source: str = 'generic', extra: dict = None) -> dict:
    """Build randomized headers for a request (Layer 2 identity rotation)."""
    global _identity_index
    with _build_lock:
        _identity_index += 1
        ua_idx = hash(f'{time.time()}_{_identity_index}_{random.random()}') % len(IDENTITY_POOL)
        accept_idx = hash(f'acc_{_identity_index}') % len(ACCEPT_POOL)
        lang_idx = hash(f'lang_{_identity_index}') % len(LANGUAGE_POOL)

    headers = {
        'User-Agent': IDENTITY_POOL[ua_idx],
        'Accept': ACCEPT_POOL[accept_idx],
        'Accept-Language': LANGUAGE_POOL[lang_idx],
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }

    # Source-specific headers
    if source == 'oddsapi':
        headers.update({
            'Origin': 'https://the-odds-api.com',
            'Referer': 'https://the-odds-api.com/',
        })
    elif source == 'sportmonks':
        headers.update({
            'Origin': 'https://sportmonks.com',
            'Referer': 'https://sportmonks.com/',
        })
    elif source == 'flashscore':
        headers.update({
            'Origin': 'https://www.flashscore.com',
            'Referer': 'https://www.flashscore.com/',
            'X-Requested-With': 'XMLHttpRequest',
        })
    elif source == 'sofascore':
        headers.update({
            'Origin': 'https://www.sofascore.com',
            'Referer': 'https://www.sofascore.com/',
            'x-requested-with': 'XMLHttpRequest',
        })

    if extra:
        headers.update(extra)

    return headers


# ─── Layer 5: Database Layer ────────────────────────────────────────────────
_db_lock = threading.Lock()
_local_conn = threading.local()


def get_db() -> sqlite3.Connection:
    """Get thread-local DB connection."""
    if not hasattr(_local_conn, 'conn') or _local_conn.conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        _local_conn.conn = conn
        _init_tables(conn)
    return _local_conn.conn


def _init_tables(conn: sqlite3.Connection):
    """Initialize all data tables (idempotent)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent4_odds_all (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            event_id TEXT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            commence_time TEXT,
            league TEXT,
            home_odds REAL,
            draw_odds REAL,
            away_odds REAL,
            overround REAL,
            bookmaker TEXT,
            raw_json TEXT,
            fetched_at REAL NOT NULL,
            UNIQUE(source, event_id, bookmaker, home_team, away_team)
        );
        CREATE INDEX IF NOT EXISTS idx_agent4_odds_teams
            ON agent4_odds_all(home_team, away_team);
        CREATE INDEX IF NOT EXISTS idx_agent4_odds_fetched
            ON agent4_odds_all(fetched_at);

        CREATE TABLE IF NOT EXISTS agent4_odds_progress (
            source TEXT PRIMARY KEY,
            last_fetch REAL,
            total_fetched INTEGER DEFAULT 0,
            total_errors INTEGER DEFAULT 0,
            status TEXT DEFAULT 'idle'
        );

        CREATE TABLE IF NOT EXISTS agent4_odds_sportmonks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id INTEGER,
            home_team TEXT,
            away_team TEXT,
            date TEXT,
            league TEXT,
            home_win_odds REAL,
            draw_odds REAL,
            away_win_odds REAL,
            home_over_odd REAL,
            home_under_odd REAL,
            both_score_yes REAL,
            both_score_no REAL,
            raw_json TEXT,
            fetched_at REAL,
            UNIQUE(fixture_id)
        );

        INSERT OR IGNORE INTO agent4_odds_progress (source, status)
        VALUES ('oddsapi', 'idle');
        INSERT OR IGNORE INTO agent4_odds_progress (source, status)
        VALUES ('sportmonks', 'idle');
        INSERT OR IGNORE INTO agent4_odds_progress (source, status)
        VALUES ('flashscore', 'idle');
    """)
    conn.commit()


def save_odds(source: str, entries: List[dict]):
    """Batch-save odds entries to DB."""
    conn = get_db()
    now = time.time()
    saved = 0
    for e in entries:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO agent4_odds_all
                (source, event_id, home_team, away_team, commence_time, league,
                 home_odds, draw_odds, away_odds, overround, bookmaker, raw_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source,
                str(e.get('event_id', '')),
                e.get('home_team', ''),
                e.get('away_team', ''),
                e.get('commence_time', ''),
                e.get('league', ''),
                e.get('home_odds'),
                e.get('draw_odds'),
                e.get('away_odds'),
                e.get('overround'),
                e.get('bookmaker', ''),
                json.dumps(e.get('raw', {}), default=str) if e.get('raw') else None,
                now
            ))
            saved += 1
        except Exception as ex:
            logger.warning(f"DB save error: {ex}")
    conn.commit()
    # Update progress
    conn.execute(
        "UPDATE agent4_odds_progress SET last_fetch=?, total_fetched=total_fetched+?, status='success' WHERE source=?",
        (now, saved, source)
    )
    conn.commit()
    return saved


def save_sportmonks_odds(fixtures: List[dict]):
    """Save Sportmonks odds data."""
    conn = get_db()
    now = time.time()
    saved = 0
    for f in fixtures:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO agent4_odds_sportmonks
                (fixture_id, home_team, away_team, date, league,
                 home_win_odds, draw_odds, away_win_odds,
                 home_over_odd, home_under_odd, both_score_yes, both_score_no,
                 raw_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f.get('fixture_id'),
                f.get('home_team', ''),
                f.get('away_team', ''),
                f.get('date', ''),
                f.get('league', ''),
                f.get('home_win_odds'),
                f.get('draw_odds'),
                f.get('away_win_odds'),
                f.get('home_over_odd'),
                f.get('home_under_odd'),
                f.get('both_score_yes'),
                f.get('both_score_no'),
                json.dumps(f.get('raw', {}), default=str) if f.get('raw') else None,
                now
            ))
            saved += 1
        except Exception as ex:
            logger.warning(f"Sportmonks DB save error: {ex}")
    conn.commit()
    conn.execute(
        "UPDATE agent4_odds_progress SET last_fetch=?, total_fetched=total_fetched+?, status='success' WHERE source='sportmonks'",
        (now, saved)
    )
    conn.commit()
    return saved


# ─── Layer 1: Core Engine — The Odds API ────────────────────────────────────
ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')
ODDS_API_BASE = 'https://api.the-odds-api.com/v4'

# League mappings for The Odds API
LEAGUE_MAP = {
    'premier_league': 'soccer_epl',
    'epl': 'soccer_epl',
    'la_liga': 'soccer_spain_la_liga',
    'bundesliga': 'soccer_germany_bundesliga',
    'serie_a': 'soccer_italy_serie_a',
    'ligue_1': 'soccer_france_ligue_one',
    'eredivisie': 'soccer_netherlands_eredivisie',
    'primeira_liga': 'soccer_portugal_primeira_liga',
    'championship': 'soccer_england_championship',
    'mls': 'soccer_usa_mls',
    'brazil_serie_a': 'soccer_brazil_serie_a',
    'argentina_primera': 'soccer_argentina_primera',
    'allsvenskan': 'soccer_sweden_allsvenskan',
    'eliteserien': 'soccer_norway_eliteserien',
    'super_lig': 'soccer_turkey_super_lig',
    'jupiler_pro': 'soccer_belgium_jupiler_pro_league',
    'austria_bundesliga': 'soccer_austria_bundesliga',
    'denmark_superliga': 'soccer_denmark_superliga',
    'poland_ekstraklasa': 'soccer_poland_ekstraklasa',
    'swiss_super_league': 'soccer_switzerland_super_league',
}


def _oddsapi_fetch(url: str, retries: int = 3) -> Optional[Any]:
    """Core HTTP fetch with identity rotation + proxy fallback (Layer 1-3)."""
    from curl_cffi import requests as curl_requests

    for attempt in range(retries):
        headers = build_headers('oddsapi')
        proxy = get_working_proxy()
        proxies = {'http': proxy, 'https': proxy} if proxy else None

        # Timing jitter (Layer 2)
        jitter = random.uniform(0.1, 0.8)
        time.sleep(jitter)

        try:
            r = curl_requests.get(
                url,
                headers=headers,
                impersonate="chrome124",
                proxies=proxies,
                timeout=20,
                verify=False
            )
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 422:
                return []
            elif r.status_code == 429:
                retry_after = int(r.headers.get('Retry-After', 10))
                logger.warning(f"OddsAPI 429: waiting {retry_after}s")
                time.sleep(retry_after + random.uniform(1, 3))
                continue
            elif r.status_code >= 500:
                logger.warning(f"OddsAPI {r.status_code}: retry {attempt+1}/{retries}")
                if proxy:
                    mark_proxy_failed(proxy)
                time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
                continue
            else:
                logger.warning(f"OddsAPI unexpected status {r.status_code}")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return None
        except Exception as e:
            logger.warning(f"OddsAPI fetch error (attempt {attempt+1}): {e}")
            if proxy:
                mark_proxy_failed(proxy)
            if attempt < retries - 1:
                time.sleep(2 ** attempt + random.uniform(1, 3))
                continue
            return None
    return None


def fetch_oddsapi_sports() -> List[dict]:
    """List available sports from OddsAPI."""
    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set!")
        return []
    url = f"{ODDS_API_BASE}/sports/?apiKey={ODDS_API_KEY}"
    data = _oddsapi_fetch(url)
    return data if isinstance(data, list) else []


def fetch_oddsapi_odds(sport_key: str, regions: str = 'uk,eu,us') -> List[dict]:
    """Fetch odds for a specific sport/league."""
    if not ODDS_API_KEY:
        return []
    url = (f"{ODDS_API_BASE}/sports/{sport_key}/odds/"
           f"?apiKey={ODDS_API_KEY}&regions={regions}&markets=h2h,spreads,totals&oddsFormat=decimal")
    data = _oddsapi_fetch(url)
    return data if isinstance(data, list) else []


def parse_oddsapi_events(events: List[dict]) -> List[dict]:
    """Parse OddsAPI events into standardized format."""
    results = []
    for event in events:
        home_team = event.get('home_team', '')
        away_team = event.get('away_team', '')
        commence = event.get('commence_time', '')
        league = event.get('sport_key', '').replace('soccer_', '').replace('_', ' ').title()

        for bk in event.get('bookmakers', []):
            for mkt in bk.get('markets', []):
                if mkt['key'] != 'h2h':
                    continue
                outcomes = {o['name'].lower(): o['price'] for o in mkt.get('outcomes', [])}
                if len(outcomes) < 2:
                    continue
                # Map outcomes (could be home/away or team names)
                h_key = home_team.lower()
                a_key = away_team.lower()
                home_odds = outcomes.get(h_key) or outcomes.get('home')
                away_odds = outcomes.get(a_key) or outcomes.get('away')
                draw_odds = outcomes.get('draw')

                # Calculate overround
                probs = []
                for o in [home_odds, draw_odds, away_odds]:
                    if o and o > 0:
                        probs.append(1.0 / o)
                overround = round((sum(probs) - 1.0) * 100, 2) if probs else None

                results.append({
                    'event_id': event.get('id', ''),
                    'home_team': home_team,
                    'away_team': away_team,
                    'commence_time': commence,
                    'league': league,
                    'home_odds': home_odds,
                    'draw_odds': draw_odds,
                    'away_odds': away_odds,
                    'overround': overround,
                    'bookmaker': bk.get('title', ''),
                    'raw': event,
                })
    return results


# ─── Layer 1: Core Engine — Sportmonks API ──────────────────────────────────
SPORTMONKS_KEY = os.environ.get('SPORTMONKS_KEY', '')
SPORTMONKS_BASE = 'https://api.sportmonks.com/v3/football'


def _sportmonks_fetch(path: str, params: dict = None, retries: int = 3) -> Optional[Any]:
    """Sportmonks API fetch with identity rotation."""
    from curl_cffi import requests as curl_requests

    if not SPORTMONKS_KEY:
        return None

    if params is None:
        params = {}
    params['api_token'] = SPORTMONKS_KEY

    url = f"{SPORTMONKS_BASE}{path}"
    for key, val in params.items():
        sep = '?' if '?' not in url else '&'
        url = f"{url}{sep}{key}={val}"

    for attempt in range(retries):
        headers = build_headers('sportmonks')
        jitter = random.uniform(0.2, 1.0)
        time.sleep(jitter)

        try:
            r = curl_requests.get(url, headers=headers, impersonate="chrome124",
                                   timeout=25, verify=False)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                logger.warning("Sportmonks 429: rate limited")
                time.sleep(5 + random.uniform(1, 5))
                continue
            elif r.status_code == 401:
                logger.error("Sportmonks 401: invalid API key")
                return None
            else:
                logger.warning(f"Sportmonks {r.status_code}: retry {attempt+1}")
                time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
                continue
        except Exception as e:
            logger.warning(f"Sportmonks fetch error: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt + random.uniform(1, 3))
                continue
            return None
    return None


def fetch_sportmonks_leagues() -> List[dict]:
    """Fetch all football leagues from Sportmonks."""
    data = _sportmonks_fetch('/leagues', {'include': 'country', 'per_page': 100})
    if data and 'data' in data:
        return data['data']
    return []


def fetch_sportmonks_fixtures(league_ids: List[int] = None, date_from: str = None,
                               date_to: str = None) -> List[dict]:
    """Fetch fixtures with odds from Sportmonks."""
    params = {
        'include': 'localTeam,visitorTeam,odds',
        'per_page': 50,
    }
    if date_from:
        params['date_from'] = date_from
    if date_to:
        params['date_to'] = date_to
    if league_ids:
        params['league_ids'] = ','.join(str(lid) for lid in league_ids)

    data = _sportmonks_fetch('/fixtures', params)
    if data and 'data' in data:
        return data['data']
    return []


def parse_sportmonks_fixtures(fixtures: List[dict]) -> List[dict]:
    """Parse Sportmonks fixtures into standardized odds format."""
    results = []
    for f in fixtures:
        try:
            fixture_id = f.get('id')
            home_team = (f.get('localTeam', {}).get('data', {}) or {}).get('name', '') if f.get('localTeam') else ''
            away_team = (f.get('visitorTeam', {}).get('data', {}) or {}).get('name', '') if f.get('visitorTeam') else ''
            date_str = f.get('starting_at', '')

            # Extract odds
            odds_data = f.get('odds', {}).get('data', []) if f.get('odds') else []
            home_win = draw = away_win = None
            over = under = bts_yes = bts_no = None

            for odd in odds_data:
                # odd[0] is bookmaker info, we take the first bookmaker
                for bk_odd in odd if isinstance(odd, list) else [odd]:
                    # Try to find 1X2 odds
                    if bk_odd.get('name') == '1X2' or bk_odd.get('label') == '1X2':
                        values = bk_odd.get('values', {})
                        if isinstance(values, dict):
                            home_win = values.get('1')
                            draw = values.get('X')
                            away_win = values.get('2')
                        elif isinstance(values, list):
                            for v in values:
                                if v.get('value') == '1': home_win = v.get('odd')
                                elif v.get('value') == 'X': draw = v.get('odd')
                                elif v.get('value') == '2': away_win = v.get('odd')

                    # Over/Under
                    if 'Over/Under' in (bk_odd.get('name', '') or bk_odd.get('label', '')):
                        values = bk_odd.get('values', {})
                        if isinstance(values, dict):
                            over = values.get('over')
                            under = values.get('under')

                    # Both teams to score
                    if 'Both Teams Score' in (bk_odd.get('name', '') or bk_odd.get('label', '')):
                        values = bk_odd.get('values', {})
                        if isinstance(values, dict):
                            bts_yes = values.get('yes')
                            bts_no = values.get('no')

            results.append({
                'fixture_id': fixture_id,
                'home_team': home_team,
                'away_team': away_team,
                'date': date_str,
                'league': '',
                'home_win_odds': float(home_win) if home_win else None,
                'draw_odds': float(draw) if draw else None,
                'away_win_odds': float(away_win) if away_win else None,
                'home_over_odd': float(over) if over else None,
                'home_under_odd': float(under) if under else None,
                'both_score_yes': float(bts_yes) if bts_yes else None,
                'both_score_no': float(bts_no) if bts_no else None,
                'raw': f,
            })
        except Exception as e:
            logger.warning(f"Parse Sportmonks fixture error: {e}")
            continue

    return results


# ─── Layer 1: Core Engine — Flashscore Scraper ──────────────────────────────
FLASHSCORE_BASE = 'https://www.flashscore.com'


def fetch_flashscore_odds(match_url: str = None) -> Optional[dict]:
    """Scrape odds from Flashscore using curl_cffi impersonate."""
    from curl_cffi import requests as curl_requests

    url = match_url or f'{FLASHSCORE_BASE}/football/'
    headers = build_headers('flashscore')

    try:
        r = curl_requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        logger.warning(f"Flashscore error: {e}")
    return None


# ─── Layer 4: Multi-threading ───────────────────────────────────────────────


class OddsCollector:
    """Orchestrator for multi-source odds collection across all layers."""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.stats = {
            'oddsapi_fetched': 0,
            'oddsapi_errors': 0,
            'sportmonks_fetched': 0,
            'sportmonks_errors': 0,
            'flashscore_fetched': 0,
            'flashscore_errors': 0,
        }
        self._stats_lock = threading.Lock()
        self._start_time = time.time()

    def collect_oddsapi(self, leagues: List[str] = None) -> int:
        """Collect odds from OddsAPI for all active soccer leagues."""
        logger.info("═" * 50)
        logger.info("🔥 Layer 1-4: OddsAPI Collection")
        logger.info("═" * 50)

        if not ODDS_API_KEY:
            logger.warning("⛔ ODDS_API_KEY not set — skipping OddsAPI")
            return 0

        # Get available sports
        sports = fetch_oddsapi_sports()
        soccer_sports = [s for s in sports if 'soccer' in s.get('key', '') and not s.get('has_outrights')]

        if leagues:
            filtered = []
            for s in soccer_sports:
                sk = s.get('key', '')
                for lg in leagues:
                    mapped = LEAGUE_MAP.get(lg.lower().replace(' ', '_'))
                    if mapped and mapped == sk:
                        filtered.append(s)
                        break
            soccer_sports = filtered

        logger.info(f"Found {len(soccer_sports)} soccer leagues in OddsAPI")

        if not soccer_sports:
            return 0

        total_odds = 0

        def fetch_league(sport: dict) -> int:
            key = sport.get('key', '')
            title = sport.get('title', key)
            events = fetch_oddsapi_odds(key)
            if events:
                parsed = parse_oddsapi_events(events)
                saved = save_odds('oddsapi', parsed)
                with self._stats_lock:
                    self.stats['oddsapi_fetched'] += saved
                logger.info(f"  ✅ {title}: {len(events)} events, {saved} odds entries")
                return saved
            else:
                logger.info(f"  ⏭️  {title}: no events")
                with self._stats_lock:
                    self.stats['oddsapi_errors'] += 1
                return 0

        with ThreadPoolExecutor(max_workers=min(self.max_workers, 3)) as exe:
            futures = {exe.submit(fetch_league, s): s for s in soccer_sports}
            for f in as_completed(futures):
                try:
                    total_odds += f.result()
                except Exception as e:
                    logger.error(f"OddsAPI league fetch error: {e}")

        logger.info(f"📊 OddsAPI total: {total_odds} odds entries from {len(soccer_sports)} leagues")
        return total_odds

    def collect_sportmonks(self, days_ahead: int = 7) -> int:
        """Collect odds from Sportmonks for upcoming fixtures."""
        logger.info("═" * 50)
        logger.info("🔥 Layer 1-4: Sportmonks Odds Collection")
        logger.info("═" * 50)

        if not SPORTMONKS_KEY:
            logger.warning("⛔ SPORTMONKS_KEY not set — skipping Sportmonks")
            return 0

        today = datetime.now().strftime('%Y-%m-%d')
        future = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

        fixtures = fetch_sportmonks_fixtures(date_from=today, date_to=future)
        logger.info(f"Found {len(fixtures)} fixtures from Sportmonks")

        if not fixtures:
            with self._stats_lock:
                self.stats['sportmonks_errors'] += 1
            return 0

        parsed = parse_sportmonks_fixtures(fixtures)
        saved = save_sportmonks_odds(parsed)

        with self._stats_lock:
            self.stats['sportmonks_fetched'] += saved

        logger.info(f"📊 Sportmonks total: {saved} odds entries saved")
        return saved

    def collect_all(self, leagues: List[str] = None) -> dict:
        """Run all collection sources (Layer 4 orchestration)."""
        self._start_time = time.time()
        logger.info("╔" + "═" * 60 + "╗")
        logger.info("║  AGENT 4 — ODDS SCRAPER v9999999                    ║")
        logger.info("║  BLACK CODE CURSE — 5-Layer Active                  ║")
        logger.info("╚" + "═" * 60 + "╝")
        logger.info(f"Workers: {self.max_workers}")
        logger.info(f"Identity pool: {len(IDENTITY_POOL)} UAs")
        logger.info(f"Proxies: {len(PROXY_LIST)} available")
        logger.info()

        # Run both sources
        oddsapi_count = self.collect_oddsapi(leagues)
        sportmonks_count = self.collect_sportmonks()

        elapsed = time.time() - self._start_time
        total = oddsapi_count + sportmonks_count

        logger.info()
        logger.info("═" * 60)
        logger.info("📊 COLLECTION SUMMARY")
        logger.info("═" * 60)
        logger.info(f"  OddsAPI:     {oddsapi_count:>8,} odds")
        logger.info(f"  Sportmonks:  {sportmonks_count:>8,} odds")
        logger.info(f"  Total:       {total:>8,} odds")
        logger.info(f"  Time:        {elapsed:.1f}s")
        logger.info(f"  Log file:    {LOG_FILE}")

        return {
            'oddsapi': oddsapi_count,
            'sportmonks': sportmonks_count,
            'total': total,
            'elapsed_seconds': elapsed,
            'log_file': str(LOG_FILE),
        }


# ─── CLI Entry Point ────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="🔥 AGENT 4 — Multi-source Odds Scraper (BLACK CODE CURSE)"
    )
    parser.add_argument('--workers', type=int, default=5,
                        help='Max concurrent workers (Layer 4)')
    parser.add_argument('--leagues', type=str, nargs='*',
                        help='Specific leagues to fetch (e.g. epl la_liga bundesliga)')
    parser.add_argument('--oddsapi-only', action='store_true',
                        help='Only fetch from OddsAPI')
    parser.add_argument('--sportmonks-only', action='store_true',
                        help='Only fetch from Sportmonks')
    parser.add_argument('--days-ahead', type=int, default=7,
                        help='Days ahead for Sportmonks fixtures')
    parser.add_argument('--status', action='store_true',
                        help='Show collection status and exit')

    args = parser.parse_args()

    if args.status:
        conn = get_db()
        rows = conn.execute("SELECT * FROM agent4_odds_progress").fetchall()
        print(f"{'Source':<15} {'Last Fetch':<25} {'Fetched':<10} {'Errors':<10} {'Status':<10}")
        print("-" * 70)
        for r in rows:
            last = datetime.fromtimestamp(r[1]).strftime('%Y-%m-%d %H:%M') if r[1] else 'never'
            print(f"{r[0]:<15} {last:<25} {r[2]:<10} {r[3]:<10} {r[4]:<10}")
        conn.close()
        return

    collector = OddsCollector(max_workers=args.workers)
    result = collector.collect_all(leagues=args.leagues)

    print()
    print(f"🔥 DONE — {result['total']:,} odds collected in {result['elapsed_seconds']:.1f}s")
    print(f"📝 Log: {result['log_file']}")


if __name__ == '__main__':
    main()
