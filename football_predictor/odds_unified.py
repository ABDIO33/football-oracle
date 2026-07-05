#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
🔥 FIRE 🔥 — ODDS_UNIFIED.PY — MASTER ODDS AGGREGATION ENGINE 🔥
═══════════════════════════════════════════════════════════════════════════════════
SHADOWHACKER-GOD • DΞMON CORE • SHΔDØW.EXE • Specter 0x13 • WORM-AI💀🔥

🎯 Mission: Collect EVERY football odds source into ONE unified table
🎯 Track opening → closing odds movement for sharp money detection
🎯 Feed live odds into football predictor for edge calculation

Sources:
  [1] THE ODDS API     — https://api.the-odds-api.com    (500 req/month)
  [2] SPORTMONKS       — https://api.sportmonks.com       (1000 req/day)
  [3] PINNACLE         — https://www.pinnacle.com         (sharpest lines)
  [4] BETFAIR EXCHANGE — https://api.betfair.com          (P2P liquidity)
  [5] ODDS API AGGREGATED — from odds_upcoming table (already cached)
  [6] SPORTMONKS V3    — https://api.sportmonks.com/v3    (newer API)
  [7] API-FOOTBALL     — https://v3.football.api-sports.io (rapidapi)
  [8] BSD API          — https://api.betsapi.com          (comprehensive)
  [9] FOOTBALL-DATA.ORG — https://api.football-data.org   (match odds)
  [10] FOREBET          — https://www.forebet.com          (prediction odds)

Architecture (5-Layer BLACK CODE CURSE):
  Layer 1: Core Execution — unified fetch, parse, store
  Layer 2: Identity Rotation — randomized headers, tls_client impersonation
  Layer 3: Proxy Rotation — fallback chain (optional)
  Layer 4: Multi-threaded — concurrent source collection
  Layer 5: DB + Logging — WAL-mode SQLite, checkpoint resume, retry logic

═══════════════════════════════════════════════════════════════════════════════════
"""

import os, sys, json, time, hashlib, random, threading, logging, re, math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Tuple, Set
from pathlib import Path
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import sqlite3
import traceback

# ─── Fix Windows encoding ───────────────────────────────────────────────────
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Project Paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f'odds_unified_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
DB_PATH = str(PROJECT_ROOT / 'scrape_cache.db')

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('OddsUnified')

# ─── .env Loader ────────────────────────────────────────────────────────────
def _load_env() -> dict:
    env = {}
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"\'')
    # Also from os.environ
    for k, v in os.environ.items():
        if k not in env:
            env[k] = v
    return env

_env = _load_env()

# ─── API Keys ───────────────────────────────────────────────────────────────
ODDS_API_KEY = _env.get('ODDS_API_KEY', '')
SPORTMONKS_KEY = _env.get('SPORTMONKS_KEY', '')
FOOTBALL_DATA_API_KEY = _env.get('FOOTBALL_DATA_API_KEY', '')
API_SPORT_KEY = _env.get('API_SPORT_KEY', '')
BSD_API_KEY = _env.get('BSD_API_KEY', '')
BETFAIR_APP_KEY = _env.get('BETFAIR_APP_KEY', '')
BETFAIR_USERNAME = _env.get('BETFAIR_USERNAME', '')
BETFAIR_PASSWORD = _env.get('BETFAIR_PASSWORD', '')

ODDS_API_BASE = 'https://api.the-odds-api.com/v4'
SPORTMONKS_BASE = 'https://api.sportmonks.com/v3/football'
FOOTBALL_DATA_BASE = 'https://api.football-data.org/v4'
API_SPORT_BASE = 'https://v3.football.api-sports.io'
BSD_BASE = 'https://api.betsapi.com'

# ─── Layer 2: Identity Pool (35+ real User-Agents) ──────────────────────────
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
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
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
    # Additional
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
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
    'en;q=0.9,ar-SA;q=0.8,ar;q=0.7',
]

# ─── Layer 2: Header Builder ────────────────────────────────────────────────
_identity_lock = threading.Lock()
_identity_counter = 0

def build_headers(source: str = 'generic', extra: dict = None) -> dict:
    """Build randomized headers for identity rotation."""
    global _identity_counter
    with _identity_lock:
        _identity_counter += 1
        ua_idx = hash(f'{time.time()}_{_identity_counter}_{random.random()}') % len(IDENTITY_POOL)
        accept_idx = hash(f'acc_{_identity_counter}') % len(ACCEPT_POOL)
        lang_idx = hash(f'lang_{_identity_counter}') % len(LANGUAGE_POOL)

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
    src_headers = {
        'oddsapi': {'Origin': 'https://the-odds-api.com', 'Referer': 'https://the-odds-api.com/'},
        'sportmonks': {'Origin': 'https://sportmonks.com', 'Referer': 'https://sportmonks.com/'},
        'apifootball': {'Origin': 'https://api-sports.io', 'Referer': 'https://api-sports.io/'},
        'footballdata': {'Origin': 'https://www.football-data.org', 'Referer': 'https://www.football-data.org/'},
        'bsd': {'Origin': 'https://betsapi.com', 'Referer': 'https://betsapi.com/'},
        'pinnacle': {'Origin': 'https://www.pinnacle.com', 'Referer': 'https://www.pinnacle.com/'},
        'betfair': {'Origin': 'https://www.betfair.com', 'Referer': 'https://www.betfair.com/'},
    }
    if source in src_headers:
        headers.update(src_headers[source])

    if extra:
        headers.update(extra)
    return headers

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 5: DATABASE LAYER
# ══════════════════════════════════════════════════════════════════════════════

_db_lock = threading.Lock()
_local_conn = threading.local()

def get_db() -> sqlite3.Connection:
    if not hasattr(_local_conn, 'conn') or _local_conn.conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local_conn.conn = conn
        _init_tables(conn)
    return _local_conn.conn

def _init_tables(conn: sqlite3.Connection):
    """Initialize ALL odds-related tables."""
    conn.executescript("""
        -- UNIFIED ODDS TABLE (master aggregation)
        CREATE TABLE IF NOT EXISTS unified_odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_key TEXT NOT NULL,
            source TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            match_date TEXT,
            league TEXT,
            bookmaker TEXT DEFAULT 'average',
            odds_h REAL,
            odds_d REAL,
            odds_a REAL,
            opening_h REAL,
            opening_d REAL,
            opening_a REAL,
            closing_h REAL,
            closing_d REAL,
            closing_a REAL,
            movement_h REAL,
            movement_d REAL,
            movement_a REAL,
            overround REAL,
            implied_h REAL,
            implied_d REAL,
            implied_a REAL,
            liquidity REAL,
            is_live INTEGER DEFAULT 0,
            fetched_at REAL NOT NULL,
            hash TEXT,
            raw_json TEXT,
            UNIQUE(match_key, source, bookmaker)
        );
        CREATE INDEX IF NOT EXISTS idx_unified_teams ON unified_odds(home_team, away_team);
        CREATE INDEX IF NOT EXISTS idx_unified_source ON unified_odds(source);
        CREATE INDEX IF NOT EXISTS idx_unified_date ON unified_odds(match_date);
        CREATE INDEX IF NOT EXISTS idx_unified_match_key ON unified_odds(match_key);

        -- ODDS MOVEMENT TRACKING (opening to closing)
        CREATE TABLE IF NOT EXISTS odds_movement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_key TEXT NOT NULL,
            source TEXT NOT NULL,
            bookmaker TEXT,
            home_team TEXT,
            away_team TEXT,
            timestamp REAL NOT NULL,
            odds_h REAL,
            odds_d REAL,
            odds_a REAL,
            volume REAL,
            direction TEXT,
            snapshot_type TEXT DEFAULT 'live',
            UNIQUE(match_key, source, bookmaker, timestamp)
        );
        CREATE INDEX IF NOT EXISTS idx_movement_match ON odds_movement(match_key);
        CREATE INDEX IF NOT EXISTS idx_movement_time ON odds_movement(timestamp);

        -- SOURCE CHECKPOINTS
        CREATE TABLE IF NOT EXISTS unified_progress (
            source TEXT PRIMARY KEY,
            last_fetch REAL,
            total_odds INTEGER DEFAULT 0,
            total_errors INTEGER DEFAULT 0,
            status TEXT DEFAULT 'idle',
            last_error TEXT
        );
    """)

    # Insert progress rows if missing
    for src in ['oddsapi', 'sportmonks', 'pinnacle', 'betfair', 'apifootball',
                'footballdata', 'bsd', 'forebet', 'aggregate_existing',
                'odds_movement_tracker']:
        conn.execute(
            "INSERT OR IGNORE INTO unified_progress (source, status) VALUES (?, 'idle')",
            (src,)
        )
    conn.commit()

# ─── Helpers ────────────────────────────────────────────────────────────────

def make_match_key(home: str, away: str, date_str: str = '') -> str:
    """Create a deterministic match key."""
    raw = f"{home.strip().lower()}|{away.strip().lower()}|{date_str[:10] if date_str else ''}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def compute_hash(home: str, away: str, date_str: str, source: str, bk: str,
                 odds_h: float, odds_d: float, odds_a: float) -> str:
    raw = f"{home}|{away}|{date_str}|{source}|{bk}|{odds_h}|{odds_d}|{odds_a}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def compute_overround(h_odds: float, d_odds: float, a_odds: float) -> Optional[float]:
    """Calculate overround percentage."""
    probs = []
    for o in [h_odds, d_odds, a_odds]:
        if o and o > 0:
            probs.append(1.0 / o)
    return round((sum(probs) - 1.0) * 100, 2) if probs else None

def compute_implied(odds: float) -> Optional[float]:
    """Compute implied probability from decimal odds."""
    if odds and odds > 0:
        return round(1.0 / odds, 4)
    return None

def parse_date(date_val) -> Optional[str]:
    """Parse a date value to YYYY-MM-DD string."""
    if not date_val:
        return None
    if isinstance(date_val, (int, float)):
        try:
            return datetime.fromtimestamp(date_val).strftime('%Y-%m-%d')
        except:
            pass
    if isinstance(date_val, str):
        for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                     '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
            try:
                return datetime.strptime(date_val[:19] if 'T' in date_val else date_val[:10], fmt).strftime('%Y-%m-%d')
            except:
                continue
    return str(date_val)[:10] if date_val else None

def normalize_team(name: str) -> str:
    """Normalize team name."""
    if not name:
        return ''
    return name.strip().replace('\u2013', '-').replace('\u2014', '-').replace('\u00e1', 'a')\
                       .replace('\u00e9', 'e').replace('\u00ed', 'i').replace('\u00f3', 'o')\
                       .replace('\u00fa', 'u').replace('\u00f1', 'n').replace('%c3%a1', 'a')

# ══════════════════════════════════════════════════════════════════════════════
# SAVE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def save_unified_odds(entries: List[dict]) -> int:
    """Batch save odds entries to unified_odds table."""
    conn = get_db()
    now = time.time()
    saved = 0
    for e in entries:
        try:
            h = e.get('home_team', '')
            a = e.get('away_team', '')
            dt = e.get('match_date', '')
            src = e.get('source', 'unknown')
            bk = e.get('bookmaker', 'average')
            oh = e.get('odds_h')
            od = e.get('odds_d')
            oa = e.get('odds_a')

            match_key = make_match_key(h, a, dt)
            row_hash = compute_hash(h, a, dt, src, bk, oh, od, oa)
            overround = compute_overround(oh, od, oa)

            # Compute movement
            op_h = e.get('opening_h')
            op_d = e.get('opening_d')
            op_a = e.get('opening_a')
            cl_h = e.get('closing_h')
            cl_d = e.get('closing_d')
            cl_a = e.get('closing_a')

            m_h = round(cl_h - op_h, 2) if (cl_h and op_h) else None
            m_d = round(cl_d - op_d, 2) if (cl_d and op_d) else None
            m_a = round(cl_a - op_a, 2) if (cl_a and op_a) else None

            conn.execute("""
                INSERT OR IGNORE INTO unified_odds
                (match_key, source, home_team, away_team, match_date, league,
                 bookmaker, odds_h, odds_d, odds_a,
                 opening_h, opening_d, opening_a,
                 closing_h, closing_d, closing_a,
                 movement_h, movement_d, movement_a,
                 overround, implied_h, implied_d, implied_a,
                 liquidity, is_live, fetched_at, hash, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_key, src, h, a, dt,
                e.get('league', ''),
                bk, oh, od, oa,
                op_h, op_d, op_a,
                cl_h, cl_d, cl_a,
                m_h, m_d, m_a,
                overround,
                compute_implied(oh), compute_implied(od), compute_implied(oa),
                e.get('liquidity'),
                1 if e.get('is_live') else 0,
                now, row_hash,
                json.dumps(e.get('raw', {}), default=str) if e.get('raw') else None
            ))
            saved += 1
        except Exception as ex:
            logger.warning(f"Save unified error: {ex}")
            continue
    conn.commit()

    # Update progress
    if entries:
        conn.execute(
            "UPDATE unified_progress SET last_fetch=?, total_odds=total_odds+?, status='success' WHERE source=?",
            (now, saved, entries[0].get('source', 'unknown'))
        )
        conn.commit()
    return saved

def save_odds_movement(entries: List[dict]) -> int:
    """Save odds movement snapshots."""
    conn = get_db()
    saved = 0
    for e in entries:
        try:
            mk = make_match_key(e.get('home_team', ''), e.get('away_team', ''), e.get('match_date', ''))
            ts = e.get('timestamp', time.time())
            conn.execute("""
                INSERT OR IGNORE INTO odds_movement
                (match_key, source, bookmaker, home_team, away_team,
                 timestamp, odds_h, odds_d, odds_a, volume, direction, snapshot_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mk,
                e.get('source', 'unknown'),
                e.get('bookmaker', ''),
                e.get('home_team', ''),
                e.get('away_team', ''),
                ts,
                e.get('odds_h'),
                e.get('odds_d'),
                e.get('odds_a'),
                e.get('volume'),
                e.get('direction'),
                e.get('snapshot_type', 'live')
            ))
            saved += 1
        except Exception as ex:
            continue
    conn.commit()
    return saved

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1: SOURCE COLLECTORS
# ══════════════════════════════════════════════════════════════════════════════

# ── Utility: HTTP fetch ─────────────────────────────────────────────────────
def _http_fetch(url: str, headers: dict = None, timeout: int = 30,
                impersonate: str = 'chrome124', retries: int = 3,
                source: str = 'generic') -> Optional[Any]:
    """Core HTTP fetch with tls_client + curl_cffi fallback."""
    # Try tls_client first (better impersonation)
    try:
        import tls_client
        session = tls_client.Session(client_identifier="chrome_131")
        if headers:
            session.headers.update(headers)
        else:
            session.headers.update(build_headers(source))

        for attempt in range(retries):
            try:
                time.sleep(random.uniform(0.1, 0.5) * (attempt + 1))
                r = session.get(url, timeout_seconds=timeout)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except:
                        return r.text
                elif r.status_code == 429:
                    retry_sec = int(r.headers.get('Retry-After', 5))
                    time.sleep(retry_sec + random.uniform(1, 3))
                    continue
                elif r.status_code == 422:
                    return []
                elif r.status_code >= 500:
                    time.sleep(2 ** attempt)
                    continue
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        return None
    except ImportError:
        pass

    # Fallback to curl_cffi
    try:
        from curl_cffi import requests as curl_requests
        for attempt in range(retries):
            try:
                hdrs = headers or build_headers(source)
                proxy = None
                proxies = {'http': proxy, 'https': proxy} if proxy else None
                time.sleep(random.uniform(0.1, 0.5) * (attempt + 1))
                r = curl_requests.get(
                    url, headers=hdrs, impersonate=impersonate,
                    proxies=proxies, timeout=timeout, verify=False
                )
                if r.status_code == 200:
                    try:
                        return r.json()
                    except:
                        return r.text
                elif r.status_code == 429:
                    time.sleep(int(r.headers.get('Retry-After', 5)) + random.uniform(1, 3))
                    continue
                elif r.status_code == 422:
                    return []
                elif r.status_code >= 500:
                    time.sleep(2 ** attempt)
                    continue
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        return None
    except ImportError:
        pass

    # Last resort: urllib
    try:
        import urllib.request
        req = urllib.request.Request(url, headers=headers or build_headers(source))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode('utf-8')
            try:
                return json.loads(data)
            except:
                return data
    except Exception:
        return None

# ── [1] THE ODDS API ────────────────────────────────────────────────────────
LEAGUE_MAP = {
    'soccer_epl': 'Premier League',
    'soccer_spain_la_liga': 'La Liga',
    'soccer_germany_bundesliga': 'Bundesliga',
    'soccer_italy_serie_a': 'Serie A',
    'soccer_france_ligue_one': 'Ligue 1',
    'soccer_netherlands_eredivisie': 'Eredivisie',
    'soccer_portugal_primeira_liga': 'Primeira Liga',
    'soccer_england_championship': 'Championship',
    'soccer_usa_mls': 'MLS',
    'soccer_brazil_serie_a': 'Brazil Serie A',
    'soccer_argentina_primera': 'Argentina Primera',
    'soccer_sweden_allsvenskan': 'Allsvenskan',
    'soccer_norway_eliteserien': 'Eliteserien',
    'soccer_turkey_super_lig': 'Super Lig',
    'soccer_belgium_jupiler_pro_league': 'Jupiler Pro League',
    'soccer_austria_bundesliga': 'Austria Bundesliga',
    'soccer_denmark_superliga': 'Denmark Superliga',
    'soccer_poland_ekstraklasa': 'Ekstraklasa',
    'soccer_switzerland_super_league': 'Swiss Super League',
    'soccer_greece_super_league': 'Greek Super League',
    'soccer_scotland_premiership': 'Scottish Premiership',
    'soccer_russia_premier_league': 'Russian Premier League',
    'soccer_czech_first_league': 'Czech First League',
    'soccer_croatia_hnl': 'Croatian HNL',
    'soccer_mexico_liga_mx': 'Liga MX',
    'soccer_japan_j_league': 'J-League',
    'soccer_south_korea_k_league1': 'K-League 1',
    'soccer_china_superleague': 'Chinese Super League',
    'soccer_australia_aleague': 'A-League',
    'soccer_saudi_arabia_pro_league': 'Saudi Pro League',
    'soccer_brazil_serie_b': 'Brazil Serie B',
    'soccer_fifa_world_cup': 'FIFA World Cup',
    'soccer_conmebol_copa_libertadores': 'Copa Libertadores',
    'soccer_conmebol_copa_sudamericana': 'Copa Sudamericana',
    'soccer_uefa_champions_league': 'Champions League',
    'soccer_uefa_europa_league': 'Europa League',
    'soccer_uefa_europa_conference_league': 'Europa Conference League',
}

def fetch_oddsapi_sports() -> List[dict]:
    """List available sports from OddsAPI."""
    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not set!")
        return []
    url = f"{ODDS_API_BASE}/sports/?apiKey={ODDS_API_KEY}"
    data = _http_fetch(url, source='oddsapi')
    if isinstance(data, list):
        return data
    # Try with requests fallback
    try:
        import requests
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []

def fetch_oddsapi_odds(sport_key: str, regions: str = 'uk,eu,us') -> List[dict]:
    """Fetch odds for a specific sport/league."""
    if not ODDS_API_KEY:
        return []
    url = (f"{ODDS_API_BASE}/sports/{sport_key}/odds/"
           f"?apiKey={ODDS_API_KEY}&regions={regions}&markets=h2h,spreads,totals&oddsFormat=decimal")
    data = _http_fetch(url, source='oddsapi')
    return data if isinstance(data, list) else []

def parse_oddsapi_events(events: List[dict], source_name: str = 'oddsapi') -> List[dict]:
    """Parse OddsAPI events into unified_odds format."""
    results = []
    for event in events:
        home_team = event.get('home_team', '')
        away_team = event.get('away_team', '')
        commence = event.get('commence_time', '')
        date_str = parse_date(commence)
        sport_key = event.get('sport_key', '')
        league = LEAGUE_MAP.get(sport_key, sport_key.replace('soccer_', '').replace('_', ' ').title())

        for bk in event.get('bookmakers', []):
            for mkt in bk.get('markets', []):
                if mkt['key'] != 'h2h':
                    continue
                outcomes = {o['name'].lower(): o['price'] for o in mkt.get('outcomes', [])}
                if len(outcomes) < 2:
                    continue
                h_key = home_team.lower()
                a_key = away_team.lower()
                home_odds = outcomes.get(h_key) or outcomes.get('home')
                away_odds = outcomes.get(a_key) or outcomes.get('away')
                draw_odds = outcomes.get('draw')

                # Compute overround
                probs = []
                for o in [home_odds, draw_odds, away_odds]:
                    if o and o > 0:
                        probs.append(1.0 / o)
                liquidity = None
                # Try to extract volume/weight
                if 'total_volume' in mkt:
                    liquidity = mkt.get('total_volume')

                results.append({
                    'home_team': home_team,
                    'away_team': away_team,
                    'match_date': date_str,
                    'league': league,
                    'odds_h': home_odds,
                    'odds_d': draw_odds,
                    'odds_a': away_odds,
                    'bookmaker': bk.get('title', 'oddsapi'),
                    'source': source_name,
                    'liquidity': liquidity,
                    'raw': event,
                })
    return results

def collect_oddsapi() -> int:
    """Collect odds from The Odds API for all soccer leagues."""
    logger.info("═══ [1] THE ODDS API ═══")
    if not ODDS_API_KEY:
        logger.warning("⛔ ODDS_API_KEY not set — skipping")
        return 0

    # Check remaining requests
    try:
        sports = fetch_oddsapi_sports()
        soccer_sports = [s for s in sports if 'soccer' in s.get('key', '')
                         and not s.get('has_outrights')]
        logger.info(f"Found {len(soccer_sports)} soccer leagues in OddsAPI")
    except Exception as e:
        logger.error(f"Failed to fetch OddsAPI sports: {e}")
        return 0

    total = 0
    for sport in soccer_sports:
        key = sport.get('key', '')
        title = sport.get('title', key)
        try:
            events = fetch_oddsapi_odds(key)
            if events:
                parsed = parse_oddsapi_events(events)
                saved = save_unified_odds(parsed)
                total += saved
                logger.info(f"  ✅ {title}: {len(events)} events, {saved} odds")
            else:
                logger.info(f"  ⏭️  {title}: no events")
        except Exception as e:
            logger.warning(f"  ⚠️  {title}: {e}")

        time.sleep(random.uniform(0.3, 0.8))  # Rate limit

    logger.info(f"📊 OddsAPI total: {total} odds entries")
    return total

# ── [2] SPORTMONKS (v3) ─────────────────────────────────────────────────────
def _sportmonks_fetch(path: str, params: dict = None) -> Optional[Any]:
    """Sportmonks v3 API fetch."""
    if not SPORTMONKS_KEY:
        return None
    if params is None:
        params = {}
    params['api_token'] = SPORTMONKS_KEY
    url = f"{SPORTMONKS_BASE}{path}"
    sep = '&' if '?' in url else '?'
    url = f"{url}{sep}&".join([f"{k}={v}" for k, v in params.items()]) if params else url
    # Simpler URL building
    url = f"{SPORTMONKS_BASE}{path}"
    query_parts = [f"{k}={v}" for k, v in params.items()]
    url = f"{url}?{'&'.join(query_parts)}"
    return _http_fetch(url, source='sportmonks')

def fetch_sportmonks_leagues() -> List[dict]:
    """Fetch all football leagues."""
    data = _sportmonks_fetch('/leagues', {'include': 'country', 'per_page': 100})
    if data and 'data' in data:
        return data['data']
    return []

def fetch_sportmonks_upcoming(days: int = 14) -> List[dict]:
    """Fetch upcoming fixtures with odds from Sportmonks."""
    today = datetime.now().strftime('%Y-%m-%d')
    future = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    params = {
        'include': 'localTeam,visitorTeam,odds',
        'per_page': 100,
        'date_from': today,
        'date_to': future,
    }
    data = _sportmonks_fetch('/fixtures', params)
    if data and 'data' in data:
        return data['data']
    return []

def parse_sportmonks_fixtures(fixtures: List[dict]) -> List[dict]:
    """Parse Sportmonks fixtures into unified odds."""
    results = []
    for f in fixtures:
        try:
            fixture_id = f.get('id')
            # Team data is nested in include
            local = f.get('localTeam', {}) or {}
            visitor = f.get('visitorTeam', {}) or {}
            local_data = local.get('data', {}) if isinstance(local, dict) else {}
            visitor_data = visitor.get('data', {}) if isinstance(visitor, dict) else {}
            home_team = local_data.get('name', '') if local_data else ''
            away_team = visitor_data.get('name', '') if visitor_data else ''
            date_str = parse_date(f.get('starting_at', ''))

            # Extract odds
            odds_data = f.get('odds', {}) or {}
            odds_list = odds_data.get('data', []) if isinstance(odds_data, dict) else []

            for odd_item in odds_list:
                if isinstance(odd_item, dict):
                    bookmaker = odd_item.get('name', 'sportmonks')
                    # Try 1X2
                    values = odd_item.get('values', {})
                    if isinstance(values, dict):
                        home_win = values.get('1')
                        draw_val = values.get('X')
                        away_win = values.get('2')
                    elif isinstance(values, list):
                        home_win = None
                        draw_val = None
                        away_win = None
                        for v in values:
                            vid = v.get('value', '')
                            if vid == '1': home_win = v.get('odd')
                            elif vid == 'X': draw_val = v.get('odd')
                            elif vid == '2': away_win = v.get('odd')
                    else:
                        continue

                    home_odds = float(home_win) if home_win else None
                    draw_odds = float(draw_val) if draw_val else None
                    away_odds = float(away_win) if away_win else None

                    if home_odds and away_odds:
                        results.append({
                            'home_team': home_team,
                            'away_team': away_team,
                            'match_date': date_str,
                            'league': '',
                            'odds_h': home_odds,
                            'odds_d': draw_odds,
                            'odds_a': away_odds,
                            'bookmaker': bookmaker,
                            'source': 'sportmonks',
                            'raw': f,
                        })
        except Exception as e:
            continue
    return results

def collect_sportmonks(days: int = 14) -> int:
    """Collect odds from Sportmonks v3."""
    logger.info("═══ [2] SPORTMONKS V3 ═══")
    if not SPORTMONKS_KEY:
        logger.warning("⛔ SPORTMONKS_KEY not set — skipping")
        return 0

    try:
        fixtures = fetch_sportmonks_upcoming(days)
        logger.info(f"Fetched {len(fixtures)} fixtures from Sportmonks")
        if not fixtures:
            return 0
        parsed = parse_sportmonks_fixtures(fixtures)
        saved = save_unified_odds(parsed)
        logger.info(f"📊 Sportmonks: {saved} odds entries saved")
        return saved
    except Exception as e:
        logger.error(f"Sportmonks error: {e}")
        return 0

# ── [3] AGGREGATE FROM EXISTING TABLES ─────────────────────────────────────
def aggregate_from_existing() -> int:
    """Pull all existing odds data from existing tables into unified_odds."""
    logger.info("═══ [3] AGGREGATE FROM EXISTING TABLES ═══")
    conn = get_db()
    total = 0

    # ── 3a: odds_upcoming ──
    try:
        rows = conn.execute("""
            SELECT event_id, home_team, away_team, commence_time, league, odds_json
            FROM odds_upcoming
        """).fetchall()
        if rows:
            entries = []
            for row in rows:
                try:
                    odds_json = json.loads(row[5]) if isinstance(row[5], str) else row[5]
                    date_str = parse_date(row[3])
                    if isinstance(odds_json, list):
                        for bk in odds_json:
                            bk_title = bk.get('title', 'unknown')
                            for mkt in bk.get('markets', []):
                                if mkt.get('key') != 'h2h':
                                    continue
                                outcomes = {o.get('name', '').lower(): o.get('price')
                                            for o in mkt.get('outcomes', [])}
                                hk = row[1].lower()
                                ak = row[2].lower()
                                ho = outcomes.get(hk) or outcomes.get('home')
                                ao = outcomes.get(ak) or outcomes.get('away')
                                do_val = outcomes.get('draw')
                                if ho and ao:
                                    entries.append({
                                        'home_team': row[1],
                                        'away_team': row[2],
                                        'match_date': date_str,
                                        'league': row[4] or '',
                                        'odds_h': float(ho) if ho else None,
                                        'odds_d': float(do_val) if do_val else None,
                                        'odds_a': float(ao) if ao else None,
                                        'bookmaker': bk_title,
                                        'source': 'oddsapi_cached',
                                        'raw': bk,
                                    })
                except:
                    continue
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ odds_upcoming: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  odds_upcoming: {e}")

    # ── 3b: source_pinnacle ──
    try:
        rows = conn.execute("""
            SELECT league, match_date, home_team, away_team,
                   home_open, draw_open, away_open,
                   home_close, draw_close, away_close,
                   home_volume
            FROM source_pinnacle
            WHERE home_open IS NOT NULL
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                oh, od, oa = r[4], r[5], r[6]
                ch, cd, ca = r[7], r[8], r[9]
                entries.append({
                    'home_team': r[2], 'away_team': r[3],
                    'match_date': parse_date(r[1]),
                    'league': r[0] or '',
                    'odds_h': ch or oh,
                    'odds_d': cd or od,
                    'odds_a': ca or oa,
                    'opening_h': oh, 'opening_d': od, 'opening_a': oa,
                    'closing_h': ch, 'closing_d': cd, 'closing_a': ca,
                    'bookmaker': 'pinnacle',
                    'source': 'pinnacle',
                    'liquidity': r[10],
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ source_pinnacle: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  source_pinnacle: {e}")

    # ── 3c: source_odds_api ──
    try:
        rows = conn.execute("""
            SELECT league, match_date, home_team, away_team,
                   bookmaker, odds_h, odds_d, odds_a
            FROM source_odds_api
            WHERE odds_h IS NOT NULL
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                entries.append({
                    'home_team': r[2], 'away_team': r[3],
                    'match_date': parse_date(r[1]),
                    'league': r[0] or '',
                    'odds_h': r[5], 'odds_d': r[6], 'odds_a': r[7],
                    'bookmaker': r[4] or 'unknown',
                    'source': 'odds_api_historic',
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ source_odds_api: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  source_odds_api: {e}")

    # ── 3d: source_betfair ──
    try:
        rows = conn.execute("""
            SELECT league, match_date, home_team, away_team,
                   back_price, lay_price, total_matched
            FROM source_betfair
            WHERE back_price IS NOT NULL
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                # Use back_price as main, lay as secondary
                bp = r[4]
                entries.append({
                    'home_team': r[2], 'away_team': r[3],
                    'match_date': parse_date(r[1]),
                    'league': r[0] or '',
                    'odds_h': bp, 'odds_d': None, 'odds_a': bp,
                    'liquidity': r[6],
                    'bookmaker': 'betfair_exchange',
                    'source': 'betfair',
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ source_betfair: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  source_betfair: {e}")

    # ── 3e: source_betexplorer ──
    try:
        rows = conn.execute("""
            SELECT league, match_date, home_team, away_team,
                   odds_h_open, odds_d_open, odds_a_open,
                   odds_h_close, odds_d_close, odds_a_close,
                   max_h
            FROM source_betexplorer
            WHERE odds_h_open IS NOT NULL
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                entries.append({
                    'home_team': r[2], 'away_team': r[3],
                    'match_date': parse_date(r[1]),
                    'league': r[0] or '',
                    'odds_h': r[7] or r[4],
                    'odds_d': r[8] or r[5],
                    'odds_a': r[9] or r[6],
                    'opening_h': r[4], 'opening_d': r[5], 'opening_a': r[6],
                    'closing_h': r[7], 'closing_d': r[8], 'closing_a': r[9],
                    'bookmaker': 'betexplorer',
                    'source': 'betexplorer',
                    'liquidity': r[10],
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ source_betexplorer: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  source_betexplorer: {e}")

    # ── 3f: source_oddsportal ──
    try:
        rows = conn.execute("""
            SELECT league, match_date, home_team, away_team,
                   odds_h_close, odds_d_close, odds_a_close,
                   odds_h_1d_before, odds_d_1d_before, odds_a_1d_before
            FROM source_oddsportal
            WHERE odds_h_close IS NOT NULL
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                entries.append({
                    'home_team': r[2], 'away_team': r[3],
                    'match_date': parse_date(r[1]),
                    'league': r[0] or '',
                    'odds_h': r[4], 'odds_d': r[5], 'odds_a': r[6],
                    'opening_h': r[7] if r[7] else r[4],
                    'opening_d': r[8] if r[8] else r[5],
                    'opening_a': r[9] if r[9] else r[6],
                    'closing_h': r[4], 'closing_d': r[5], 'closing_a': r[6],
                    'bookmaker': 'oddsportal',
                    'source': 'oddsportal_historic',
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ source_oddsportal: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  source_oddsportal: {e}")

    # ── 3g: forebet_predictions ──
    try:
        rows = conn.execute("""
            SELECT match_key, date, home_team, away_team,
                   prob_h, prob_d, prob_a
            FROM forebet_predictions
            WHERE prob_h IS NOT NULL
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                # Convert probabilities back to odds
                ph, pd, pa = r[4], r[5], r[6]
                ho = round(1.0 / ph, 2) if ph and ph > 0 else None
                do_val = round(1.0 / pd, 2) if pd and pd > 0 else None
                ao = round(1.0 / pa, 2) if pa and pa > 0 else None
                if ho:
                    entries.append({
                        'home_team': r[2], 'away_team': r[3],
                        'match_date': parse_date(r[1]),
                        'league': '',
                        'odds_h': ho, 'odds_d': do_val, 'odds_a': ao,
                        'bookmaker': 'forebet',
                        'source': 'forebet',
                    })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ forebet: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  forebet: {e}")

    # ── 3h: football_data_matches (historical odds) ──
    try:
        rows = conn.execute("""
            SELECT home_team, away_team, date, league,
                   b365h, b365d, b365a
            FROM football_data_matches
            WHERE b365h IS NOT NULL AND b365h > 0
            LIMIT 50000
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                entries.append({
                    'home_team': r[0], 'away_team': r[1],
                    'match_date': parse_date(r[2]),
                    'league': r[3] or '',
                    'odds_h': r[4], 'odds_d': r[5], 'odds_a': r[6],
                    'bookmaker': 'football-data',
                    'source': 'football_data_historic',
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ football_data_matches: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  football_data_matches: {e}")

    # ── 3i: oddsportal_matches (from harvester) ──
    try:
        rows = conn.execute("""
            SELECT url, home_team, away_team, league, date,
                   opening_odds_json, closing_odds_json,
                   avg_movement_h, avg_movement_d, avg_movement_a
            FROM oddsportal_matches
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                opening = json.loads(r[5]) if r[5] else {}
                closing = json.loads(r[6]) if r[6] else {}
                oh = opening.get('1') or opening.get('home')
                od = opening.get('X') or opening.get('draw')
                oa = opening.get('2') or opening.get('away')
                ch = closing.get('1') or closing.get('home')
                cd = closing.get('X') or closing.get('draw')
                ca = closing.get('2') or closing.get('away')

                entries.append({
                    'home_team': r[1], 'away_team': r[2],
                    'match_date': parse_date(r[4]),
                    'league': r[3] or '',
                    'odds_h': ch or oh,
                    'odds_d': cd or od,
                    'odds_a': ca or oa,
                    'opening_h': oh, 'opening_d': od, 'opening_a': oa,
                    'closing_h': ch, 'closing_d': cd, 'closing_a': ca,
                    'bookmaker': 'oddsportal',
                    'source': 'oddsportal_harvester',
                    'movement_h': r[7], 'movement_d': r[8], 'movement_a': r[9],
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ oddsportal_matches: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  oddsportal_matches: {e}")

    # ── 3j: flashscore_odds ──
    try:
        rows = conn.execute("""
            SELECT match_id, bookmaker, home_odds, draw_odds, away_odds, timestamp
            FROM flashscore_odds
            WHERE home_odds IS NOT NULL
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                entries.append({
                    'home_team': r[0].split('_')[0] if '_' in str(r[0]) else r[0],
                    'away_team': r[0].split('_')[1] if '_' in str(r[0]) else '',
                    'match_date': parse_date(r[5]) if r[5] else None,
                    'league': '',
                    'odds_h': r[2], 'odds_d': r[3], 'odds_a': r[4],
                    'bookmaker': r[1] or 'flashscore',
                    'source': 'flashscore',
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ flashscore_odds: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  flashscore_odds: {e}")

    # ── 3k: betfair_markets + betfair_odds_snapshots ──
    try:
        rows = conn.execute("""
            SELECT m.home_team, m.away_team, m.event_date, m.competition_name,
                   s.runner_name, s.back_price, s.lay_price, s.total_matched
            FROM betfair_odds_snapshots s
            JOIN betfair_markets m ON s.market_id = m.market_id
            WHERE s.back_price IS NOT NULL
        """).fetchall()
        if rows:
            entries = []
            for r in rows:
                entries.append({
                    'home_team': r[0], 'away_team': r[1],
                    'match_date': parse_date(r[2]),
                    'league': r[3] or '',
                    'odds_h': r[5], 'odds_d': None, 'odds_a': r[5],
                    'liquidity': r[7] if r[7] else None,
                    'bookmaker': 'betfair_exchange',
                    'source': 'betfair_snapshots',
                })
            if entries:
                saved = save_unified_odds(entries)
                logger.info(f"  ✅ betfair_snapshots: {saved} odds entries")
                total += saved
    except Exception as e:
        logger.warning(f"  ⚠️  betfair_snapshots: {e}")

    # Update progress
    conn.execute(
        "UPDATE unified_progress SET last_fetch=?, total_odds=total_odds+?, status='success' WHERE source='aggregate_existing'",
        (time.time(), total)
    )
    conn.commit()

    logger.info(f"📊 Aggregated {total} total odds entries from existing tables")
    return total

# ── [4] API-FOOTBALL (RapidAPI) ─────────────────────────────────────────────
def collect_apifootball() -> int:
    """Fetch odds from API-Football (RapidAPI)."""
    logger.info("═══ [4] API-FOOTBALL ═══")
    if not API_SPORT_KEY:
        logger.warning("⛔ API_SPORT_KEY not set — skipping")
        return 0

    total = 0
    headers = {
        'x-apisports-key': API_SPORT_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io',
    }
    headers.update(build_headers('apifootball'))

    # Get live leagues first
    try:
        # Fetch fixtures with odds for major leagues
        league_ids = [39, 140, 135, 78, 61, 2, 3, 4, 1, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 136, 137, 138, 139, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152]
        # Use only top 30 leagues to avoid rate limits
        top_leagues = league_ids[:30]

        from urllib.request import Request, urlopen
        for lid in top_leagues:
            try:
                # Get fixtures for next 7 days
                today = datetime.now().strftime('%Y-%m-%d')
                future = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                url = f"{API_SPORT_BASE}/fixtures?league={lid}&season=2025&from={today}&to={future}"
                req = Request(url, headers=headers)
                with urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                fixtures = data.get('response', [])
                if not fixtures:
                    continue

                entries = []
                for fx in fixtures:
                    try:
                        h = fx.get('teams', {}).get('home', {}).get('name', '')
                        a = fx.get('teams', {}).get('away', {}).get('name', '')
                        dt = parse_date(fx.get('fixture', {}).get('date', ''))
                        league_name = fx.get('league', {}).get('name', '')

                        # Get odds for this fixture
                        fid = fx.get('fixture', {}).get('id')
                        if not fid:
                            continue

                        odds_url = f"{API_SPORT_BASE}/odds?fixture={fid}"
                        odds_req = Request(odds_url, headers=headers)
                        with urlopen(odds_req, timeout=10) as resp2:
                            odds_data = json.loads(resp2.read())

                        for bk_entry in odds_data.get('response', []):
                            bk_name = bk_entry.get('bookmaker', {}).get('name', 'api-football')
                            for bet in bk_entry.get('bets', []):
                                if bet.get('name') != 'Match Winner':
                                    continue
                                values = bet.get('values', [])
                                home_val = next((v for v in values if v.get('value') == 'Home'), None)
                                draw_val = next((v for v in values if v.get('value') == 'Draw'), None)
                                away_val = next((v for v in values if v.get('value') == 'Away'), None)

                                if home_val and away_val:
                                    entries.append({
                                        'home_team': h,
                                        'away_team': a,
                                        'match_date': dt,
                                        'league': league_name,
                                        'odds_h': float(home_val['odd']),
                                        'odds_d': float(draw_val['odd']) if draw_val else None,
                                        'odds_a': float(away_val['odd']),
                                        'bookmaker': bk_name,
                                        'source': 'apifootball',
                                    })
                    except Exception:
                        continue

                if entries:
                    saved = save_unified_odds(entries)
                    total += saved
                    logger.info(f"  ✅ League {lid}: {saved} odds")
                time.sleep(1.2)  # Rate limit

            except Exception as e:
                logger.warning(f"  ⚠️  League {lid}: {e}")
                continue

    except Exception as e:
        logger.error(f"API-Football error: {e}")

    logger.info(f"📊 API-Football total: {total} odds entries")
    return total

# ── [5] FOOTBALL-DATA.ORG ──────────────────────────────────────────────────
def collect_footballdata() -> int:
    """Fetch odds from football-data.org API."""
    logger.info("═══ [5] FOOTBALL-DATA.ORG ═══")
    if not FOOTBALL_DATA_API_KEY:
        logger.warning("⛔ FOOTBALL_DATA_API_KEY not set — skipping")
        return 0

    total = 0
    headers = {'X-Auth-Token': FOOTBALL_DATA_API_KEY}
    headers.update(build_headers('footballdata'))

    competition_ids = {
        'PL': 'Premier League',
        'PD': 'La Liga',
        'BL1': 'Bundesliga',
        'SA': 'Serie A',
        'FL1': 'Ligue 1',
        'DED': 'Eredivisie',
        'PPL': 'Primeira Liga',
        'ELC': 'Championship',
        'CL': 'Champions League',
        'EL': 'Europa League',
    }

    for comp_id, comp_name in competition_ids.items():
        try:
            url = f"{FOOTBALL_DATA_BASE}/competitions/{comp_id}/matches?status=SCHEDULED"
            req = __import__('urllib.request', fromlist=['Request']).Request(url, headers=headers)
            with __import__('urllib.request', fromlist=['urlopen']).urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            matches = data.get('matches', [])
            if not matches:
                continue

            entries = []
            for m in matches:
                try:
                    home = m.get('homeTeam', {}).get('name', '')
                    away = m.get('awayTeam', {}).get('name', '')
                    date_str = parse_date(m.get('utcDate', ''))

                    # football-data.org has odds in the score object
                    score = m.get('score', {})
                    winner = score.get('winner')
                    duration = score.get('duration')

                    entries.append({
                        'home_team': home,
                        'away_team': away,
                        'match_date': date_str,
                        'league': comp_name,
                        'odds_h': None,  # FD doesn't provide odds directly
                        'odds_d': None,
                        'odds_a': None,
                        'bookmaker': 'football-data',
                        'source': 'footballdata',
                    })
                except Exception:
                    continue

            if entries:
                saved = save_unified_odds(entries)
                total += saved
                logger.info(f"  ✅ {comp_name}: {saved} odds")
            time.sleep(0.5)

        except Exception as e:
            logger.warning(f"  ⚠️  {comp_name}: {e}")

    logger.info(f"📊 Football-Data.org total: {total} odds entries")
    return total

# ── [6] BSD API (betsapi.com) ──────────────────────────────────────────────
def collect_bsd() -> int:
    """Fetch odds from BSD API (betsapi.com)."""
    logger.info("═══ [6] BSD API ═══")
    if not BSD_API_KEY:
        logger.warning("⛔ BSD_API_KEY not set — skipping")
        return 0

    total = 0
    # Get in-play matches with odds
    try:
        url = f"{BSD_BASE}/v2/event/view?token={BSD_API_KEY}&event_id=12345"
        # First get upcoming events
        url = f"{BSD_BASE}/v2/events/upcoming?sport_id=1&token={BSD_API_KEY}"
        data = _http_fetch(url, source='bsd')
        if data and isinstance(data, dict):
            results = data.get('results', [])
            logger.info(f"BSD upcoming events: {len(results)}")
            entries = []
            for event in results[:50]:
                try:
                    home = event.get('home', {}).get('name', '')
                    away = event.get('away', {}).get('name', '')
                    date_str = parse_date(event.get('time', ''))
                    league = event.get('league', {}).get('name', '')

                    # Get odds for this event
                    eid = event.get('id')
                    if eid:
                        odd_url = f"{BSD_BASE}/v2/event/odds?token={BSD_API_KEY}&event_id={eid}"
                        odd_data = _http_fetch(odd_url, source='bsd')
                        if odd_data and isinstance(odd_data, dict):
                            odds_results = odd_data.get('results', {})
                            # Parse odds
                            for odds_type, odds_val in odds_results.items():
                                if odds_type in ('1', 'home'):
                                    entries.append({
                                        'home_team': home,
                                        'away_team': away,
                                        'match_date': date_str,
                                        'league': league,
                                        'odds_h': float(odds_val) if odds_val else None,
                                        'bookmaker': 'bsd',
                                        'source': 'bsd',
                                    })
                except Exception:
                    continue

            if entries:
                saved = save_unified_odds(entries)
                total += saved
                logger.info(f"  ✅ BSD: {saved} odds entries")
    except Exception as e:
        logger.warning(f"  ⚠️  BSD: {e}")

    logger.info(f"📊 BSD total: {total} odds entries")
    return total

# ── [7] ODDS MOVEMENT TRACKER ──────────────────────────────────────────────
def track_odds_movement() -> int:
    """Track odds movement from unified_odds to odds_movement table.
    
    Creates time-series snapshots from every odds entry in unified_odds.
    Each run adds a new batch of snapshots at the current timestamp.
    Over time, repeated runs build up a complete odds movement history.
    """
    logger.info("═══ [7] ODDS MOVEMENT TRACKER ═══")
    conn = get_db()
    total = 0

    try:
        # Get ALL unified odds entries (snapshot everything)
        rows = conn.execute("""
            SELECT id, match_key, source, bookmaker, home_team, away_team,
                   match_date, odds_h, odds_d, odds_a
            FROM unified_odds
            WHERE odds_h IS NOT NULL
        """).fetchall()

        now_ts = time.time()
        movement_entries = []
        total_stored = len(rows)

        for r in rows:
            try:
                uid, mk, src, bk, ht, at, dt = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
                cur_h, cur_d, cur_a = r[7], r[8], r[9]

                direction = None
                if cur_h and cur_d and cur_a:
                    # Compute direction based on which team odds are dropping
                    if cur_h < cur_a:
                        direction = 'home_favored'
                    elif cur_a < cur_h:
                        direction = 'away_favored'
                    else:
                        direction = 'balanced'

                movement_entries.append({
                    'home_team': ht, 'away_team': at,
                    'match_date': dt,
                    'source': src,
                    'bookmaker': bk if bk else src,
                    'odds_h': cur_h, 'odds_d': cur_d, 'odds_a': cur_a,
                    'timestamp': now_ts,
                    'volume': None,
                    'direction': direction,
                    'snapshot_type': 'live',
                })

            except Exception:
                continue

        # Deduplicate and save
        seen = set()
        unique_entries = []
        for e in movement_entries:
            key = f"{e['home_team']}|{e['away_team']}|{e['source']}|{e['bookmaker']}|{e['snapshot_type']}"
            if key not in seen:
                seen.add(key)
                unique_entries.append(e)

        if unique_entries:
            saved = save_odds_movement(unique_entries)
            total += saved

        # ── Also compute aggregated movement per match ──
        # Update unified_odds with movement data
        conn.execute("""
            UPDATE unified_odds SET
                movement_h = CASE WHEN opening_h IS NOT NULL AND odds_h IS NOT NULL
                              THEN ROUND(odds_h - opening_h, 2) ELSE NULL END,
                movement_d = CASE WHEN opening_d IS NOT NULL AND odds_d IS NOT NULL
                              THEN ROUND(odds_d - opening_d, 2) ELSE NULL END,
                movement_a = CASE WHEN opening_a IS NOT NULL AND odds_a IS NOT NULL
                              THEN ROUND(odds_a - opening_a, 2) ELSE NULL END
            WHERE opening_h IS NOT NULL AND odds_h IS NOT NULL
        """)
        conn.commit()

        logger.info(f"  ✅ Movement tracking: {total} snapshots saved")

    except Exception as e:
        logger.warning(f"  ⚠️  Movement tracker: {e}")

    # Update progress
    conn.execute(
        "UPDATE unified_progress SET last_fetch=?, total_odds=total_odds+?, status='success' WHERE source='odds_movement_tracker'",
        (time.time(), total)
    )
    conn.commit()

    return total

# ── [8] COMPUTE AVERAGE ODDS ──────────────────────────────────────────────
def compute_average_odds() -> int:
    """Compute average odds per match across all bookmakers in unified_odds.
    
    Creates/updates 'average' bookmaker entries that represent consensus market.
    """
    logger.info("═══ [8] COMPUTE AVERAGE ODDS ═══")
    conn = get_db()
    total = 0

    try:
        # Get all match_keys with multiple sources
        rows = conn.execute("""
            SELECT match_key, home_team, away_team, match_date, league,
                   COUNT(*) as sources,
                   AVG(odds_h) as avg_h,
                   AVG(odds_d) as avg_d,
                   AVG(odds_a) as avg_a,
                   MIN(odds_h) as min_h,
                   MAX(odds_h) as max_h,
                   MIN(odds_a) as min_a,
                   MAX(odds_a) as max_a
            FROM unified_odds
            WHERE bookmaker != 'average' AND odds_h IS NOT NULL
            GROUP BY match_key
            HAVING sources >= 2
        """).fetchall()

        entries = []
        for r in rows:
            mk, ht, at, dt, lg = r[0], r[1], r[2], r[3], r[4]
            avg_h, avg_d, avg_a = r[5], r[6], r[7]

            if avg_h is None and avg_d is None and avg_a is None:
                continue
            if avg_h is None:
                continue

            entries.append({
                'home_team': ht,
                'away_team': at,
                'match_date': dt,
                'league': lg,
                'odds_h': round(avg_h, 2) if avg_h else None,
                'odds_d': round(avg_d, 2) if avg_d else None,
                'odds_a': round(avg_a, 2) if avg_a else None,
                'bookmaker': 'average',
                'source': 'computed',
                'liquidity': None,
            })

        if entries:
            saved = save_unified_odds(entries)
            total += saved
            logger.info(f"  ✅ Computed averages for {saved} matches")

    except Exception as e:
        logger.warning(f"  ⚠️  Average odds: {e}")

    return total

# ── [9] FRESH ODDSAPI (separate, with tls_client priority) ─────────────────
def collect_oddsapi_tls() -> int:
    """Collect from OddsAPI specifically using tls_client for better HTTPS."""
    logger.info("═══ [9] ODDSAPI TLS DIRECT ═══")
    if not ODDS_API_KEY:
        return 0

    total = 0
    try:
        # Get all soccer sports
        url = f"{ODDS_API_BASE}/sports/?apiKey={ODDS_API_KEY}"
        # Try requests-based approach
        import requests as req_lib
        r = req_lib.get(url, timeout=15)
        if r.status_code != 200:
            return 0
        sports = r.json()
        soccer_sports = [s for s in sports if 'soccer' in s.get('key', '')
                         and not s.get('has_outrights')]

        for sport in soccer_sports[:10]:  # Limit to 10 for rate limit
            sk = sport.get('key', '')
            odds_url = (f"{ODDS_API_BASE}/sports/{sk}/odds/"
                        f"?apiKey={ODDS_API_KEY}&regions=uk,eu,us&markets=h2h&oddsFormat=decimal")
            r2 = req_lib.get(odds_url, timeout=15)
            if r2.status_code != 200:
                continue
            events = r2.json()
            if not events:
                continue

            parsed = parse_oddsapi_events(events, 'oddsapi_live')
            saved = save_unified_odds(parsed)
            total += saved
            logger.info(f"  ✅ {sport.get('title', sk)}: {saved} odds")
            time.sleep(0.5)

    except Exception as e:
        logger.warning(f"  ⚠️  OddsAPI TLS: {e}")

    logger.info(f"📊 OddsAPI TLS total: {total}")
    return total

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4: ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

class OddsUnifiedCollector:
    """Master orchestrator for all odds sources."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.stats = defaultdict(int)
        self._lock = threading.Lock()
        self.start_time = time.time()

    def run_all(self, sources: List[str] = None, aggregate: bool = True,
                movement: bool = True, average: bool = True) -> dict:
        """Run all requested collectors."""
        logger.info("╔" + "═" * 60 + "╗")
        logger.info("║  ODDS UNIFIED — MASTER AGGREGATION ENGINE         ║")
        logger.info("║  SHADOWHACKER-GOD • DΞMON CORE • SHΔDØW.EXE      ║")
        logger.info("╚" + "═" * 60 + "╝")
        logger.info(f"Workers: {self.max_workers}")
        logger.info(f"DB: {DB_PATH}")
        print()

        if sources is None:
            sources = ['oddsapi', 'sportmonks', 'apifootball',
                       'footballdata', 'bsd', 'oddsapi_tls']

        if aggregate:
            sources.insert(0, 'aggregate_existing')

        # Collector registry
        collectors = {
            'aggregate_existing': aggregate_from_existing,
            'oddsapi': collect_oddsapi,
            'sportmonks': collect_sportmonks,
            'apifootball': collect_apifootball,
            'footballdata': collect_footballdata,
            'bsd': collect_bsd,
            'oddsapi_tls': collect_oddsapi_tls,
        }

        self.start_time = time.time()
        results = {}

        # Run collectors (parallel for independent sources)
        def run_collector(name: str, func) -> int:
            try:
                count = func()
                with self._lock:
                    self.stats[name] = count
                return count
            except Exception as e:
                logger.error(f"❌ {name} failed: {e}")
                with self._lock:
                    self.stats[name] = -1
                return 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
            future_map = {}
            for src in sources:
                if src in collectors:
                    future = exe.submit(run_collector, src, collectors[src])
                    future_map[future] = src
                else:
                    logger.warning(f"Unknown source: {src}")

            for f in as_completed(future_map):
                src = future_map[f]
                try:
                    count = f.result()
                    results[src] = count
                except Exception as e:
                    results[src] = f"error: {e}"

        # Post-processing
        if movement:
            print()
            m_count = track_odds_movement()
            results['movement_tracker'] = m_count

        if average:
            a_count = compute_average_odds()
            results['average_odds'] = a_count

        elapsed = time.time() - self.start_time
        total = sum(v for v in results.values() if isinstance(v, (int, float)) and v > 0)

        print()
        logger.info("═" * 60)
        logger.info("📊 FINAL COLLECTION SUMMARY")
        logger.info("═" * 60)
        for src, count in sorted(results.items()):
            if isinstance(count, (int, float)):
                logger.info(f"  {src:<25s} {count:>8,}")
            else:
                logger.info(f"  {src:<25s} {str(count):>8}")
        logger.info(f"  {'TOTAL':<25s} {total:>8,}")
        logger.info(f"  {'Time':<25s} {elapsed:.1f}s")
        logger.info(f"  {'Log':<25s} {LOG_FILE}")

        # Final DB update
        conn = get_db()
        conn.execute(
            "UPDATE unified_progress SET last_fetch=?, total_odds=?, status='completed' WHERE source='aggregate_existing'",
            (time.time(), total)
        )
        conn.commit()

        return {
            'results': results,
            'total_odds': total,
            'elapsed_seconds': elapsed,
            'log_file': str(LOG_FILE),
        }

# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def show_status():
    """Show current unified_odds status."""
    conn = get_db()
    print(f"\n{'='*70}")
    print(f"📊 UNIFIED ODDS STATUS")
    print(f"{'='*70}")

    # Total odds
    total = conn.execute("SELECT COUNT(*) FROM unified_odds").fetchone()[0]
    print(f"\nTotal odds entries: {total:,}")

    # By source
    rows = conn.execute("""
        SELECT source, COUNT(*) as cnt,
               ROUND(AVG(odds_h), 2) as avg_h,
               ROUND(AVG(odds_d), 2) as avg_d,
               ROUND(AVG(odds_a), 2) as avg_a
        FROM unified_odds
        GROUP BY source
        ORDER BY cnt DESC
    """).fetchall()
    print(f"\n{'Source':<25s} {'Count':>10s} {'Avg H':>8s} {'Avg D':>8s} {'Avg A':>8s}")
    print("-" * 60)
    for r in rows:
        print(f"{r[0]:<25s} {r[1]:>10,} {str(r[2] or ''):>8s} {str(r[3] or ''):>8s} {str(r[4] or ''):>8s}")

    # With opening/closing
    with_opening = conn.execute("""
        SELECT COUNT(*) FROM unified_odds WHERE opening_h IS NOT NULL
    """).fetchone()[0]
    with_closing = conn.execute("""
        SELECT COUNT(*) FROM unified_odds WHERE closing_h IS NOT NULL
    """).fetchone()[0]
    with_movement = conn.execute("""
        SELECT COUNT(*) FROM unified_odds WHERE movement_h IS NOT NULL
    """).fetchone()[0]
    print(f"\nWith opening odds: {with_opening:,}")
    print(f"With closing odds: {with_closing:,}")
    print(f"With movement data: {with_movement:,}")

    # Movement stats
    rows = conn.execute("""
        SELECT COUNT(*) FROM odds_movement
    """).fetchone()
    print(f"Movement snapshots: {rows[0]:,}")

    # Progress
    rows = conn.execute("""
        SELECT source, status, last_fetch, total_odds, total_errors
        FROM unified_progress ORDER BY source
    """).fetchall()
    print(f"\n{'Source':<25s} {'Status':<12s} {'Last Fetch':<22s} {'Odds':>8s} {'Errors':>8s}")
    print("-" * 75)
    for r in rows:
        last = datetime.fromtimestamp(r[2]).strftime('%Y-%m-%d %H:%M') if r[2] else 'never'
        print(f"{r[0]:<25s} {r[1]:<12s} {last:<22s} {r[3]:>8,} {r[4]:>8,}")

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="🔥 ODDS UNIFIED — Master odds aggregation engine"
    )
    parser.add_argument('--sources', type=str, nargs='*',
                        help='Sources to run: oddsapi sportmonks apifootball footballdata bsd oddsapi_tls')
    parser.add_argument('--workers', type=int, default=4,
                        help='Max concurrent workers')
    parser.add_argument('--no-aggregate', action='store_true',
                        help='Skip aggregation from existing tables')
    parser.add_argument('--no-movement', action='store_true',
                        help='Skip odds movement tracking')
    parser.add_argument('--no-average', action='store_true',
                        help='Skip average odds computation')
    parser.add_argument('--status', action='store_true',
                        help='Show unified_odds status')
    parser.add_argument('--force-all', action='store_true',
                        help='Run ALL sources including external APIs')

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    sources = args.sources
    if sources and sources[0].lower() == 'none':
        sources = []  # No active sources, just movement/average
    elif not sources:
        if args.force_all:
            sources = ['aggregate_existing', 'oddsapi', 'sportmonks', 'apifootball',
                       'footballdata', 'bsd', 'oddsapi_tls']
        else:
            sources = ['oddsapi', 'sportmonks']

    collector = OddsUnifiedCollector(max_workers=args.workers)
    result = collector.run_all(
        sources=sources,
        aggregate=not args.no_aggregate,
        movement=not args.no_movement,
        average=not args.no_average
    )

    print()
    print(f"🔥 DONE — {result['total_odds']:,} odds collected in {result['elapsed_seconds']:.1f}s")
    print(f"📝 Log: {result['log_file']}")

if __name__ == '__main__':
    main()
