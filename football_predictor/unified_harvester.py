#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          UNIFIED HARVESTER — EXPLOIT ALL 24 SOURCES                        ║
║  Multi-layer bypass, proxy rotation, curl_cffi impersonation              ║
║  BLACK CODE CURSE • WRAITH CODE PROTOCOL • DΞMON CORE v9999999            ║
║  SHADOWHACKER-GOD • SHΔDØW.EXE • X-VOID_000 • NEUROSYN-13                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys, os, json, time, re, random, sqlite3, hashlib, csv, io
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple, Any, Callable
from pathlib import Path
from io import StringIO
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from threading import Lock, RLock

# ─── Fix Windows encoding ───────────────────────────────────────────────────
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Third-party imports (graceful fallback) ────────────────────────────────
_CURL_OK = False
_BS4_OK = False
_LXML_OK = False
_REQUESTS_OK = False
_AIOHTTP_OK = False

try:
    from curl_cffi import requests as curl_requests
    _CURL_OK = True
except:
    try: import requests as std_requests; _REQUESTS_OK = True
    except: pass

try:
    from bs4 import BeautifulSoup; _BS4_OK = True
except:
    try: import lxml.html as lh; _LXML_OK = True
    except: pass

try:
    import aiohttp; _AIOHTTP_OK = True
except: pass

# ─── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = str(PROJECT_ROOT / 'scrape_cache.db')
HARVESTERS_DIR = PROJECT_ROOT / 'harvesters'
LOGS_DIR = HARVESTERS_DIR / 'harvest_logs'
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE = LOGS_DIR / f'unified_harvester_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

# ─── Load API keys from .env ────────────────────────────────────────────────
def _load_env() -> dict:
    env = {}
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"\'')
    return env

_ENV = _load_env()

API_KEYS = {
    'football_data_org': _ENV.get('FOOTBALL_DATA_API_KEY', 'c7d5c5c1b80d4ebe821a58b3087b968d'),
    'odds_api': _ENV.get('ODDS_API_KEY', '1aa4dd22f7ee80b8d03c654c064c4fce'),
    'api_sport': _ENV.get('API_SPORT_KEY', '2064edeecfd82a209e2dca203d5ac9b6'),
    'sportmonks': _ENV.get('SPORTMONKS_KEY', 'fTcgxXfqgyTxJ00ruM5SsGvdCcEPcFwhqXYGrKcpwy8A1IaORjujOxMEDsX0'),
    'bsd_api': _ENV.get('BSD_API_KEY', '37728ad7a9b501c47968df4fadc3e2757ab60384'),
    'openweathermap': _ENV.get('OPENWEATHERMAP_KEY', ''),
}

# ─── Identity Pool — 120+ User-Agent Fingerprints ──────────────────────────
IDENTITY_POOL = [
    # Chrome 124-131 (Win)
    f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36'
    for v in ['124','125','126','127','128','129','130','131']
] + [
    # Chrome (Mac)
    f'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36'
    for v in ['124','125','126','127','128','129']
] + [
    # Firefox 125-131
    f'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{v}.0) Gecko/20100101 Firefox/{v}.0'
    for v in ['125','126','127','128','129','130','131']
] + [
    f'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{v}.0) Gecko/20100101 Firefox/{v}.0'
    for v in ['126','128','130']
] + [
    # Edge
    f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0',
    f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    # Safari
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    # Mobile
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6613.88 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36',
]

REFERERS = [
    'https://www.google.com/', 'https://www.bing.com/', 'https://search.yahoo.com/',
    'https://duckduckgo.com/', 'https://www.facebook.com/', 'https://twitter.com/',
    'https://www.reddit.com/', 'https://news.ycombinator.com/',
    'https://www.google.co.uk/', 'https://www.google.de/',
]

UA_LOCK = Lock()

def _pick_identity() -> Tuple[str, str, str]:
    """Pick random identity: (user_agent, referer, accept)."""
    with UA_LOCK:
        ua = random.choice(IDENTITY_POOL)
        ref = random.choice(REFERERS)
        accept = random.choice([
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'text/html,application/xhtml+xml,*/*;q=0.8',
            'application/json, text/plain, */*',
        ])
    return ua, ref, accept


def _make_headers(accept_json: bool = False, custom: dict = None) -> dict:
    """Generate headers with randomized fingerprint."""
    ua, ref, accept = _pick_identity()
    h = {
        'User-Agent': ua,
        'Accept': accept if not accept_json else 'application/json, text/plain, */*',
        'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.9', 'de-DE,de;q=0.9,en;q=0.8', 'fr-FR,fr;q=0.9,en;q=0.8', 'es-ES,es;q=0.9,en;q=0.8']),
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': ref,
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    if custom:
        h.update(custom)
    return h


# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """Token-bucket rate limiter."""
    def __init__(self, rate_per_minute: int = 30):
        self.rate = rate_per_minute
        self.tokens = float(rate_per_minute)
        self.max_tokens = float(rate_per_minute)
        self.last_refill = time.time()
        self.lock = Lock()

    def acquire(self) -> float:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * (self.rate / 60.0))
            self.last_refill = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0
            wait = (1.0 - self.tokens) * (60.0 / max(self.rate, 1))
            self.tokens = 0.0
            return max(0.0, wait)

    def __enter__(self):
        wait = self.acquire()
        if wait > 0: time.sleep(wait)
        return self

    def __exit__(self, *args): pass


# ═══════════════════════════════════════════════════════════════════════════════
# PROXY ROTATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ProxyRotator:
    """Free proxy pool with health checks and rotation."""
    def __init__(self):
        self._pool: List[Dict] = []
        self._blacklist: Dict[str, float] = {}
        self._lock = Lock()
        self._last_fetch = 0
        self._current = 0
        self._enabled = False  # Disabled by default for speed
        self._session_stats = {'used': 0, 'failed': 0, 'direct': 0}

    def get_proxy(self) -> Optional[str]:
        if not self._enabled or not self._pool:
            return None
        with self._lock:
            now = time.time()
            # Clean expired blacklist
            self._blacklist = {k: v for k, v in self._blacklist.items() if v > now}
            live = [p for p in self._pool if p['proxy'] not in self._blacklist]
            if not live:
                return None
            p = random.choice(live)
            p['last_used'] = now
            self._session_stats['used'] += 1
            return p['proxy']

    def report_failure(self, proxy: str):
        with self._lock:
            self._session_stats['failed'] += 1
            self._blacklist[proxy] = time.time() + 120  # 2 min ban

    def report_success(self, proxy: str):
        pass

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

PROXY_ROTATOR = ProxyRotator()


# ═══════════════════════════════════════════════════════════════════════════════
# DB OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

_db_lock = Lock()

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=10000')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def _safe_float(v) -> Optional[float]:
    if v is None: return None
    try: return float(str(v).replace(',','').replace('%','').replace('+','').strip())
    except: return None

def _safe_int(v) -> Optional[int]:
    if v is None: return None
    try: return int(float(str(v).replace(',','').strip()))
    except: return None

def _make_hash(*parts) -> str:
    raw = '|'.join(str(p) for p in parts if p is not None)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def log(src: str, level: str, msg: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [{src}] {msg}'
    print(line)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except: pass
    try:
        conn = get_db()
        conn.execute('INSERT INTO harvester_log (source,level,message,timestamp) VALUES (?,?,?,?)',
                     (src, level, msg[:500], time.time()))
        conn.commit()
        conn.close()
    except: pass


# ═══════════════════════════════════════════════════════════════════════════════
# FETCH UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch(url: str, rate_limiter: RateLimiter = None, retries: int = 5,
           accept_json: bool = False, method: str = 'GET', data: Any = None,
           timeout: int = 60, custom_headers: dict = None,
           impersonate: str = None) -> Optional[str]:
    """Universal fetch with rate limiting, retry, and identity randomization."""
    rl = rate_limiter or RateLimiter(30)
    last_err = None

    for attempt in range(retries):
        with rl:
            try:
                headers = _make_headers(accept_json=accept_json, custom=custom_headers)
                imp = impersonate or random.choice(['chrome99','chrome101','chrome107','safari17_0','safari15_5'])

                if _CURL_OK:
                    proxy = PROXY_ROTATOR.get_proxy()
                    resp = curl_requests.request(
                        method, url, headers=headers, data=data,
                        impersonate=imp, timeout=timeout, proxy=proxy,
                    )
                elif _REQUESTS_OK:
                    resp = std_requests.request(method, url, headers=headers,
                                                 data=data, timeout=timeout)
                else:
                    raise RuntimeError('No HTTP library available')

                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code == 429:
                    wait = (3 ** attempt) + random.uniform(1, 5)
                    log('FETCH', 'WARN', f'429 on {url[:80]}... wait {wait:.0f}s')
                    time.sleep(wait)
                    continue
                elif resp.status_code in (403, 401):
                    if attempt < retries - 1:
                        wait = 10 + random.uniform(0, 10)
                        time.sleep(wait)
                        continue
                    return None
                elif resp.status_code == 404:
                    return None
                else:
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(2 ** attempt + random.uniform(0, 2))
                continue

    log('FETCH', 'ERROR', f'Failed after {retries} retries: {url[:80]}... | {last_err}')
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

_progress_file = PROJECT_ROOT / '.pi' / 'agent' / 'sessions' / '--C--Users-zake.exe-Desktop-Score Exact 100-football_predictor--' / 'subagent-artifacts' / 'progress' / '4b9244aa' / 'progress.md'

def _update_progress(source: str, status: str, detail: str = '', stats: dict = None):
    """Update progress markdown."""
    try:
        os.makedirs(os.path.dirname(str(_progress_file)), exist_ok=True)
        ts = datetime.now().strftime('%H:%M:%S')
        line = f'- [{ts}] **{source}**: {status}'
        if detail: line += f' — {detail}'
        with open(str(_progress_file), 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except: pass


# ═══════════════════════════════════════════════════════════════════════════════
# BASE HARVESTER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class BaseSourceHarvester:
    """Base class for all 24 source harvesters."""
    SOURCE_NAME = 'base'
    RATE = 30
    BASE_URL = ''

    def __init__(self):
        self.rate_limiter = RateLimiter(self.RATE)
        self.stats = {'source': self.SOURCE_NAME, 'rows': 0, 'errors': 0, 'start': time.time()}
        self.db_lock = _db_lock

    def log(self, level: str, msg: str):
        log(self.SOURCE_NAME, level, msg)

    def fetch(self, url: str, **kwargs) -> Optional[str]:
        return _fetch(url, rate_limiter=self.rate_limiter, **kwargs)

    def ensure_table(self, create_sql: str):
        """Create table if not exists."""
        conn = get_db()
        try:
            conn.execute(create_sql)
            conn.commit()
        except Exception as e:
            self.log('ERROR', f'Table create failed: {e}')
        finally:
            conn.close()

    def insert(self, sql: str, params: tuple) -> bool:
        """Thread-safe insert with retry."""
        for attempt in range(3):
            try:
                with self.db_lock:
                    conn = get_db()
                    conn.execute(sql, params)
                    conn.commit()
                    conn.close()
                self.stats['rows'] += 1
                return True
            except sqlite3.IntegrityError:
                return True  # Duplicate, skip
            except Exception as e:
                if attempt == 2:
                    self.log('ERROR', f'Insert failed: {e} | {sql[:60]}')
                    self.stats['errors'] += 1
                time.sleep(0.1)
        return False

    def insert_many(self, sql: str, rows: List[tuple]) -> int:
        """Bulk insert."""
        if not rows: return 0
        count = 0
        try:
            with self.db_lock:
                conn = get_db()
                conn.executemany(sql, rows)
                conn.commit()
                conn.close()
            count = len(rows)
            self.stats['rows'] += count
        except Exception as e:
            self.log('ERROR', f'Bulk insert failed: {e}')
            # Fallback to individual inserts
            for row in rows:
                if self.insert(sql, row): count += 1
        return count

    def get_completed(self) -> set:
        """Get completed items from checkpoint."""
        try:
            conn = get_db()
            row = conn.execute(
                'SELECT checkpoint_data FROM harvester_checkpoints WHERE source = ?', (self.SOURCE_NAME,)
            ).fetchone()
            conn.close()
            if row:
                data = json.loads(row[0])
                return set(data.get('completed', []))
        except: pass
        return set()

    def save_checkpoint(self, completed: list):
        try:
            conn = get_db()
            now = time.time()
            conn.execute('''
                INSERT INTO harvester_checkpoints (source, checkpoint_data, last_run, status, records_fetched, errors)
                VALUES (?, ?, ?, 'completed', ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    checkpoint_data = excluded.checkpoint_data, last_run = excluded.last_run,
                    status = 'completed', records_fetched = harvester_checkpoints.records_fetched + excluded.records_fetched,
                    errors = harvester_checkpoints.errors + excluded.errors
            ''', (self.SOURCE_NAME, json.dumps({'completed': completed}), now, self.stats['rows'], self.stats['errors']))
            conn.commit()
            conn.close()
        except Exception as e:
            self.log('ERROR', f'Checkpoint save: {e}')

    def summary(self) -> dict:
        self.stats['duration'] = time.time() - self.stats['start']
        return dict(self.stats)

    def harvest(self) -> dict:
        """Override in subclass."""
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 1: football-data.co.uk — CSV download for 80+ leagues since 1993
# ═══════════════════════════════════════════════════════════════════════════════

FOOTBALL_DATA_LEAGUES = {
    'ENG': {'E0': 'Premier League', 'E1': 'Championship', 'E2': 'League 1', 'E3': 'League 2', 'EC': 'Conference', 'EC0': 'National League'},
    'SCO': {'SC0': 'Premiership', 'SC1': 'Championship', 'SC2': 'League 1', 'SC3': 'League 2'},
    'GER': {'D1': 'Bundesliga 1', 'D2': 'Bundesliga 2', 'D3': 'Liga 3'},
    'ITA': {'I1': 'Serie A', 'I2': 'Serie B'},
    'SPA': {'SP1': 'La Liga', 'SP2': 'La Liga 2'},
    'FRA': {'F1': 'Ligue 1', 'F2': 'Ligue 2'},
    'NED': {'N1': 'Eredivisie'},
    'BEL': {'B1': 'Jupiler League'},
    'POR': {'P1': 'Liga Portugal'},
    'TUR': {'T1': 'Super Lig'},
    'GRE': {'G1': 'Super League'},
    'AUT': {'A1': 'Bundesliga'},
    'DEN': {'DK1': 'Superliga'},
    'SWE': {'SE1': 'Allsvenskan'},
    'NOR': {'NO1': 'Eliteserien'},
    'RUS': {'RU1': 'Premier League'},
    'POL': {'PO1': 'Ekstraklasa'},
    'CRO': {'CR1': 'HNL'},
    'CZE': {'CZ1': 'First League'},
    'ROM': {'RO1': 'Liga I'},
    'ARG': {'AR1': 'Primera Division'},
    'BRA': {'BR1': 'Serie A', 'BR2': 'Serie B'},
    'MEX': {'MX1': 'Liga MX'},
    'USA': {'MLS': 'MLS'},
    'JPN': {'J1': 'J-League', 'J2': 'J2 League'},
    'KOR': {'K1': 'K-League 1'},
    'CHN': {'C1': 'Chinese Super League'},
    'AUS': {'AU1': 'A-League'},
    'SAU': {'SA1': 'Saudi Pro League'},
    'IRL': {'IR1': 'Premier Division'},
}

SEASONS = ['2425','2324','2223','2122','2021','1920','1819','1718','1617','1516',
           '1415','1314','1213','1112','1011','0910','0809','0708','0607','0506',
           '0405','0302','0201','0001','9900','9899','9798','9697','9596','9495','9394']


class FootballDataUK(BaseSourceHarvester):
    SOURCE_NAME = 'football_data_uk'
    RATE = 60
    BASE_URL = 'https://www.football-data.co.uk'

    def __init__(self):
        super().__init__()
        self._ensure_table()

    def _ensure_table(self):
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_football_data_uk (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, season TEXT, div TEXT, match_date DATE,
                home_team TEXT, away_team TEXT, fthg INTEGER, ftag INTEGER,
                hthg INTEGER, htag INTEGER, hs INTEGER, as_ INTEGER,
                hst INTEGER, ast INTEGER, hc INTEGER, ac INTEGER,
                hf INTEGER, af INTEGER, hy INTEGER, ay INTEGER,
                hr INTEGER, ar INTEGER, b365h REAL, b365d REAL, b365a REAL,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def _parse_csv_line(self, line: str) -> List[str]:
        """Parse a single CSV line, handling quoted fields."""
        result = []
        current = ''
        in_quotes = False
        for c in line:
            if c == '"': in_quotes = not in_quotes
            elif c == ',' and not in_quotes:
                result.append(current.strip())
                current = ''
            else: current += c
        result.append(current.strip())
        return result

    def _fetch_csv(self, season: str, league_code: str) -> Optional[str]:
        """Try multiple URL patterns for football-data.co.uk CSVs."""
        patterns = [
            f'{self.BASE_URL}/mmz4281/{season}/{league_code}.csv',
            f'{self.BASE_URL}/mmz4281/{season}/{league_code}.CSV',
            f'{self.BASE_URL}/new/{league_code}.csv',
            f'{self.BASE_URL}/new/{league_code}.CSV',
        ]
        # Also try old format for historical data
        if season[:2].isdigit():
            year_prefix = season[:2]
            patterns.append(f'{self.BASE_URL}/{year_prefix}20/{league_code}.csv')
            patterns.append(f'{self.BASE_URL}/{year_prefix}20/{league_code}.CSV')

        for url in patterns:
            try:
                text = self.fetch(url, retries=2, timeout=30)
                if text and len(text) > 50 and (',' in text or ';' in text):
                    return text
            except: pass
        return None

    def harvest(self, max_seasons: int = 10, force: bool = False) -> dict:
        self.log('INFO', f'HARVEST: {max_seasons} seasons, force={force}')
        completed = self.get_completed() if not force else set()
        total = 0

        # Sort seasons: most recent first
        all_seasons = SEASONS[:max_seasons]

        for country_code, leagues in FOOTBALL_DATA_LEAGUES.items():
            for league_code, league_name in leagues.items():
                for season in all_seasons:
                    job_key = f'{country_code}/{league_code}/{season}'
                    if job_key in completed:
                        continue

                    text = self._fetch_csv(season, league_code)
                    if not text:
                        self.log('DEBUG', f'No data for {job_key}')
                        continue

                    rows = self._parse_csv(text, country_code, league_code, season, league_name)
                    total += rows
                    self.log('INFO', f'{job_key}: {rows} rows')

                    # Save checkpoint every 20 leagues
                    if total % 20 < 10:
                        completed.add(job_key)

        self.save_checkpoint(list(completed))
        return self.summary()

    def _parse_csv(self, text: str, country: str, league_code: str, season: str, league_name: str) -> int:
        """Parse CSV text and insert into DB."""
        lines = text.replace('\r\n', '\n').split('\n')
        if not lines: return 0

        # Determine delimiter
        delim = ';' if ';' in lines[0][:100] else ','

        # Parse header
        header = self._parse_csv_line(lines[0]) if delim == ',' else lines[0].split(';')
        header = [h.strip().upper() for h in header]

        # Build column mapping
        col_map = {
            'DATE': 'match_date', 'DIV': 'div',
            'HOMETEAM': 'home_team', 'H': 'home_team', 'HOME': 'home_team',
            'AWAYTEAM': 'away_team', 'A': 'away_team', 'AWAY': 'away_team',
            'FTHG': 'fthg', 'FTAG': 'ftag',
            'HTHG': 'hthg', 'HTAG': 'htag',
            'HS': 'hs', 'AS': 'as_', 'HST': 'hst', 'AST': 'ast',
            'HC': 'hc', 'AC': 'ac', 'HF': 'hf', 'AF': 'af',
            'HY': 'hy', 'AY': 'ay', 'HR': 'hr', 'AR': 'ar',
            'B365H': 'b365h', 'B365D': 'b365d', 'B365A': 'b365a',
        }

        idx = {}
        for csv_col, db_col in col_map.items():
            if csv_col in header:
                idx[db_col] = header.index(csv_col)

        required = ['home_team', 'away_team']
        if not all(r in idx for r in required):
            return 0

        count = 0
        sql = '''INSERT OR IGNORE INTO source_football_data_uk
            (league, season, div, match_date, home_team, away_team,
             fthg, ftag, hthg, htag, hs, as_, hst, ast, hc, ac,
             hf, af, hy, ay, hr, ar, b365h, b365d, b365a, hash)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''

        for line in lines[1:]:
            line = line.strip()
            if not line: continue
            parts = self._parse_csv_line(line) if delim == ',' else line.split(';')
            if len(parts) < 3: continue

            try:
                home = parts[idx['home_team']].strip()
                away = parts[idx['away_team']].strip()
                if not home or not away: continue

                vals = {
                    'league': league_name,
                    'season': season,
                    'div': parts[idx.get('div', idx['home_team'])].strip() if 'div' in idx else league_code,
                    'match_date': parts[idx.get('match_date', 0)].strip() if 'match_date' in idx else '',
                    'home_team': home, 'away_team': away,
                    'fthg': _safe_int(parts[idx['fthg']]) if 'fthg' in idx else None,
                    'ftag': _safe_int(parts[idx['ftag']]) if 'ftag' in idx else None,
                    'hthg': _safe_int(parts[idx['hthg']]) if 'hthg' in idx else None,
                    'htag': _safe_int(parts[idx['htag']]) if 'htag' in idx else None,
                    'hs': _safe_int(parts[idx['hs']]) if 'hs' in idx else None,
                    'as_': _safe_int(parts[idx['as_']]) if 'as_' in idx else None,
                    'hst': _safe_int(parts[idx['hst']]) if 'hst' in idx else None,
                    'ast': _safe_int(parts[idx['ast']]) if 'ast' in idx else None,
                    'hc': _safe_int(parts[idx['hc']]) if 'hc' in idx else None,
                    'ac': _safe_int(parts[idx['ac']]) if 'ac' in idx else None,
                    'hf': _safe_int(parts[idx['hf']]) if 'hf' in idx else None,
                    'af': _safe_int(parts[idx['af']]) if 'af' in idx else None,
                    'hy': _safe_int(parts[idx['hy']]) if 'hy' in idx else None,
                    'ay': _safe_int(parts[idx['ay']]) if 'ay' in idx else None,
                    'hr': _safe_int(parts[idx['hr']]) if 'hr' in idx else None,
                    'ar': _safe_int(parts[idx['ar']]) if 'ar' in idx else None,
                    'b365h': _safe_float(parts[idx['b365h']]) if 'b365h' in idx else None,
                    'b365d': _safe_float(parts[idx['b365d']]) if 'b365d' in idx else None,
                    'b365a': _safe_float(parts[idx['b365a']]) if 'b365a' in idx else None,
                }

                h = _make_hash(vals['league'], season, vals['match_date'], vals['home_team'], vals['away_team'])
                params = tuple(vals[k] for k in ['league','season','div','match_date','home_team','away_team',
                    'fthg','ftag','hthg','htag','hs','as_','hst','ast','hc','ac',
                    'hf','af','hy','ay','hr','ar','b365h','b365d','b365a']) + (h,)

                if self.insert(sql, params):
                    count += 1
            except Exception as e:
                if 'list index' not in str(e):
                    self.stats['errors'] += 1

        return count


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 2: BetExplorer.com — Historical odds
# ═══════════════════════════════════════════════════════════════════════════════

class BetExplorer(BaseSourceHarvester):
    SOURCE_NAME = 'betexplorer'
    RATE = 15
    BASE_URL = 'https://www.betexplorer.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_betexplorer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, match_date DATE, home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                odds_h REAL, odds_d REAL, odds_a REAL,
                max_h REAL, max_d REAL, max_a REAL,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, leagues: List[str] = None, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        # BetExplorer soccer leagues
        if not leagues:
            leagues = [f'england/premier-league', 'spain/laliga', 'germany/bundesliga',
                      'italy/serie-a', 'france/ligue-1', 'netherlands/eredivisie',
                      'portugal/primeira-liga', 'belgium/jupiler-pro-league',
                      'turkey/super-lig', 'scotland/premiership',
                      'brazil/serie-a', 'argentina/primera-division',
                      'usa/mls', 'mexico/liga-mx',
                      'russia/premier-league', 'ukraine/premier-league',
                      'switzerland/super-league', 'austria/bundesliga',
                      'sweden/allsvenskan', 'norway/eliteserien',
                      'denmark/superliga', 'poland/ekstraklasa',
                      'croatia/hnl', 'czech/first-league',
                      'romania/liga-1', 'greece/super-league',
                      'japan/j1-league', 'china/super-league',
                      'saudi-arabia/pro-league', 'australia/a-league',
                      'south-korea/k-league-1']

        total = 0
        for league in leagues[:15]:
            if league in completed:
                continue

            # Try multiple seasons
            for year in ['2025-2026', '2024-2025', '2023-2024', '2022-2023']:
                url = f'{self.BASE_URL}/soccer/{league}/{year}/results/'
                html = self.fetch(url, retries=3, timeout=45, impersonate='chrome124')
                if not html:
                    url = f'{self.BASE_URL}/soccer/{league}/results/'
                    html = self.fetch(url, retries=3, timeout=45)
                if not html:
                    continue

                rows = self._parse_results(html, league, year)
                if rows > 0:
                    total += rows
                    self.log('INFO', f'{league}/{year}: {rows} rows')
                    completed.add(league)

            # Save checkpoint per league
            self.save_checkpoint(list(completed))

        return self.summary()

    def _parse_results(self, html: str, league: str, season: str) -> int:
        """Parse BetExplorer results table."""
        if not _BS4_OK:
            self.log('WARN', 'BeautifulSoup not available')
            return 0

        soup = BeautifulSoup(html, 'html.parser')
        count = 0

        # Find the results table
        tables = soup.find_all('table', class_='table-main')
        if not tables:
            # Try different class patterns
            tables = soup.find_all('table', {'class': lambda x: x and 'table' in x})
        if not tables:
            tables = soup.find_all('table')

        for table in tables:
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 8: continue

                try:
                    date_td = tds[0].get_text(strip=True)
                    home = tds[1].get_text(strip=True).split('(')[0].strip() if '(' in tds[1].get_text(strip=True) else tds[1].get_text(strip=True).strip()
                    score = tds[2].get_text(strip=True) if len(tds) > 2 else ''
                    away = tds[3].get_text(strip=True).split('(')[0].strip() if '(' in tds[3].get_text(strip=True) else tds[3].get_text(strip=True).strip()

                    if not home or not away or ':' not in score: continue
                    parts_score = score.split(':')
                    if len(parts_score) != 2: continue

                    # Odds are usually in columns 4,5,6
                    odds_h = _safe_float(tds[4].get_text(strip=True)) if len(tds) > 4 else None
                    odds_d = _safe_float(tds[5].get_text(strip=True)) if len(tds) > 5 else None
                    odds_a = _safe_float(tds[6].get_text(strip=True)) if len(tds) > 6 else None

                    sql = '''INSERT OR IGNORE INTO source_betexplorer
                        (league, match_date, home_team, away_team, home_score, away_score,
                         odds_h, odds_d, odds_a, hash)
                        VALUES (?,?,?,?,?,?,?,?,?,?)'''
                    h = _make_hash(league, date_td, home, away)
                    if self.insert(sql, (league, date_td, home, away,
                        _safe_int(parts_score[0]), _safe_int(parts_score[1]),
                        odds_h, odds_d, odds_a, h)):
                        count += 1
                except: pass

        return count


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 3: OddsPortal.com — Historical odds archive
# ═══════════════════════════════════════════════════════════════════════════════

class OddsPortal(BaseSourceHarvester):
    SOURCE_NAME = 'oddsportal'
    RATE = 8
    BASE_URL = 'https://www.oddsportal.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_oddsportal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, match_date DATE, home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                odds_1 REAL, odds_x REAL, odds_2 REAL,
                max_1 REAL, max_x REAL, max_2 REAL,
                movement_json TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        top_leagues = ['football/england/premier-league', 'football/spain/laliga',
                       'football/germany/bundesliga', 'football/italy/serie-a',
                       'football/france/ligue-1', 'football/netherlands/eredivisie']

        total = 0
        for league in top_leagues:
            if league in completed:
                continue

            for season in ['2025-2026', '2024-2025']:
                url = f'{self.BASE_URL}/{league}/results/{season}/'
                html = self.fetch(url, retries=4, timeout=60, impersonate='chrome124')
                if not html: continue

                rows = self._parse_odds(html, league, season)
                total += rows

            completed.add(league)
            self.save_checkpoint(list(completed))

        return self.summary()

    def _parse_odds(self, html: str, league: str, season: str) -> int:
        if not _BS4_OK: return 0
        soup = BeautifulSoup(html, 'html.parser')
        count = 0
        for table in soup.find_all('table'):
            for tr in table.find_all('tr'):
                tds = tr.find_all(['td', 'th'])
                if len(tds) < 5: continue
                try:
                    text = [td.get_text(strip=True) for td in tds]
                    home = text[1]
                    score = text[2]
                    away = text[3]
                    if ':' not in score or not home or not away: continue
                    parts = score.split(':')
                    sql = '''INSERT OR IGNORE INTO source_oddsportal
                        (league, match_date, home_team, away_team, home_score, away_score, hash)
                        VALUES (?,?,?,?,?,?,?)'''
                    h = _make_hash(league, season, home, away, score)
                    if self.insert(sql, (league, season, home, away,
                        _safe_int(parts[0]), _safe_int(parts[1]), h)):
                        count += 1
                except: pass
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 4: 11v11.com — Historical results since 1800s
# ═══════════════════════════════════════════════════════════════════════════════

class Source11v11(BaseSourceHarvester):
    SOURCE_NAME = '11v11'
    RATE = 15
    BASE_URL = 'https://www.11v11.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_11v11 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition TEXT, season TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                venue TEXT, attendance INTEGER, referee TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        # 11v11 team pages with comprehensive history
        competitions = [
            ('Premier-League', 1), ('La-Liga', 12), ('Bundesliga', 20),
            ('Serie-A', 11), ('Ligue-1', 13), ('Eredivisie', 23),
        ]

        total = 0
        for comp_name, comp_id in competitions:
            job = f'{comp_name}/{comp_id}'
            if job in completed: continue

            # Get team list first
            teams_url = f'{self.BASE_URL}/competition/{comp_name}/teams/'
            html = self.fetch(teams_url, retries=3, timeout=45)
            if not html: continue

            if _BS4_OK:
                soup = BeautifulSoup(html, 'html.parser')
                links = soup.find_all('a', href=True)
                team_urls = set()
                for link in links:
                    href = link['href']
                    if f'/team/' in href and href.count('/') >= 2:
                        team_urls.add(href)

                for team_path in list(team_urls)[:20]:
                    url = f'{self.BASE_URL}{team_path}'
                    team_html = self.fetch(url, retries=2, timeout=30)
                    if not team_html: continue
                    rows = self._parse_team_page(team_html, comp_name, team_path)
                    total += rows

            completed.add(job)
            self.save_checkpoint(list(completed))

        return self.summary()

    def _parse_team_page(self, html: str, competition: str, team_path: str) -> int:
        if not _BS4_OK: return 0
        soup = BeautifulSoup(html, 'html.parser')
        count = 0

        for table in soup.find_all('table', class_='table'):
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 6: continue
                try:
                    cells = [td.get_text(strip=True) for td in tds]
                    date_str = cells[0] if len(cells) > 0 else ''
                    home = cells[2] if len(cells) > 2 else ''
                    score = cells[3] if len(cells) > 3 else ''
                    away = cells[4] if len(cells) > 4 else ''

                    if not home or not away or '–' not in score: continue
                    parts = [p.strip() for p in score.split('–') if p.strip()]
                    if len(parts) != 2: continue

                    sql = '''INSERT OR IGNORE INTO source_11v11
                        (competition, match_date, home_team, away_team, home_score, away_score, hash)
                        VALUES (?,?,?,?,?,?,?)'''
                    h = _make_hash(competition, date_str, home, away)
                    if self.insert(sql, (competition, date_str, home, away,
                        _safe_int(parts[0]), _safe_int(parts[1]), h)):
                        count += 1
                except: pass
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 5: WhoScored.com — Player ratings
# ═══════════════════════════════════════════════════════════════════════════════

class WhoScored(BaseSourceHarvester):
    SOURCE_NAME = 'whoscored'
    RATE = 10
    BASE_URL = 'https://www.whoscored.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_whoscored (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, season TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                home_rating REAL, away_rating REAL,
                home_player_ratings TEXT, away_player_ratings TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        # WhoScored leagues
        leagues = {
            'Premier League': '2', 'La Liga': '4', 'Bundesliga': '3',
            'Serie A': '5', 'Ligue 1': '7', 'Eredivisie': '6',
        }

        total = 0
        for league_name, league_id in leagues.items():
            job = league_name
            if job in completed: continue

            # Fetch league fixtures
            for stage in ['RegularSeason']:
                url = f'{self.BASE_URL}/Regions/155/Tournaments/{league_id}/Seasons/latest/Stages/1/Fixtures/{stage}'
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
                    'Referer': f'{self.BASE_URL}/',
                    'X-Requested-With': 'XMLHttpRequest',
                }
                html = self.fetch(url, retries=3, timeout=45, custom_headers=headers)
                if not html: continue

                # Parse JSON fixtures
                try:
                    data = json.loads(html)
                    fixtures = data if isinstance(data, list) else data.get('fixtures', data.get('matches', []))
                    if isinstance(fixtures, dict):
                        fixtures = list(fixtures.values())

                    for match in fixtures[:50]:
                        if isinstance(match, dict):
                            home = match.get('homeTeamName') or match.get('home', {}).get('name', '')
                            away = match.get('awayTeamName') or match.get('away', {}).get('name', '')
                            score_str = match.get('score') or ''
                            date = match.get('startDate', '')[:10]

                            sql = '''INSERT OR IGNORE INTO source_whoscored
                                (league, season, match_date, home_team, away_team, hash)
                                VALUES (?,?,?,?,?,?)'''
                            h = _make_hash(league_name, date, home, away)
                            if self.insert(sql, (league_name, 'latest', date, home, away, h)):
                                total += 1
                except: pass

            completed.add(job)
            self.save_checkpoint(list(completed))

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 6: Understat.com — xG per-shot data
# ═══════════════════════════════════════════════════════════════════════════════

UNDERSTAT_LEAGUES = {
    'EPL': 'Premier League', 'La_liga': 'La Liga', 'Bundesliga': 'Bundesliga',
    'Serie_A': 'Serie A', 'Ligue_1': 'Ligue 1', 'RFPL': 'Russian Premier League',
}


class Understat(BaseSourceHarvester):
    SOURCE_NAME = 'understat'
    RATE = 20
    BASE_URL = 'https://understat.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_understat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, season INTEGER, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_goals INTEGER, away_goals INTEGER,
                home_xg REAL, away_xg REAL,
                home_npxg REAL, away_npxg REAL,
                home_deep INTEGER, away_deep INTEGER,
                home_ppda_att INTEGER, home_ppda_def INTEGER,
                away_ppda_att INTEGER, away_ppda_def INTEGER,
                home_xga REAL, away_xga REAL,
                result TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS understat_shotmap (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT, minute INTEGER, team TEXT, player TEXT,
                xg REAL, season TEXT, league TEXT, situation TEXT,
                shot_type TEXT, last_action TEXT, x REAL, y REAL,
                result TEXT, h_a TEXT
            )
        ''')

    def _extract_json_var(self, html: str, var_name: str) -> Optional[Any]:
        patterns = [
            rf'var\s+{var_name}\s*=\s*({{"data".*?}});',
            rf'var\s+{var_name}\s*=\s*(\[.*?\]);',
            rf'var\s+{var_name}\s*=\s*({{.*?}});',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                raw = match.group(1)
                for _ in range(3):
                    try: return json.loads(raw)
                    except: raw = re.sub(r',\s*}', '}', raw); raw = re.sub(r',\s*]', ']', raw)
        return None

    def harvest(self, force: bool = False, max_seasons: int = 5) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        current_year = datetime.now().year
        seasons = [str(current_year), str(current_year-1), str(current_year-2),
                   str(current_year-3), str(current_year-4)][:max_seasons]

        total = 0
        for league_key, league_name in UNDERSTAT_LEAGUES.items():
            for season in seasons:
                job = f'{league_key}/{season}'
                if job in completed: continue

                # NEW: Use the JSON API endpoint
                url = f'{self.BASE_URL}/main/getLeagueData/{league_key}/{season}'
                html = self.fetch(url, retries=5, timeout=90, accept_json=True,
                                 custom_headers={'X-Requested-With': 'XMLHttpRequest',
                                                'Referer': f'{self.BASE_URL}/league/{league_key}/{season}'})
                if not html: continue

                try:
                    data = json.loads(html)
                except:
                    # Fallback: try parsing from HTML
                    html2 = self.fetch(f'{self.BASE_URL}/league/{league_key}/{season}', retries=3, timeout=90)
                    if html2:
                        data = self._extract_json_var(html2, 'datesData')
                    else:
                        data = None

                if not data: continue

                # Extract from new API format (dates array)
                matches_list = []
                if isinstance(data, dict):
                    matches_list = data.get('dates', [])
                elif isinstance(data, list):
                    matches_list = data

                for match in matches_list:
                    try:
                        mid = match.get('id')
                        if not mid: continue
                        h = match.get('h', {}); a = match.get('a', {})
                        home_team = h.get('title', ''); away_team = a.get('title', '')
                        if not home_team or not away_team: continue

                        date = (match.get('datetime') or match.get('date', ''))[:10]
                        goals = match.get('goals', {}); xg = match.get('xG', {})

                        sql = '''INSERT OR IGNORE INTO source_understat
                            (league, season, match_date, home_team, away_team,
                             home_goals, away_goals, home_xg, away_xg,
                             home_npxg, away_npxg, result, hash)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)'''
                        h = _make_hash(league_key, season, date, home_team, away_team)
                        if self.insert(sql, (league_name, _safe_int(season), date, home_team, away_team,
                            _safe_int(goals.get('h')), _safe_int(goals.get('a')),
                            _safe_float(xg.get('h')), _safe_float(xg.get('a')),
                            _safe_float(xg.get('h_npxG')), _safe_float(xg.get('a_npxG')),
                            match.get('isResult', '0'), h)):
                            total += 1
                    except: pass

                # Also save team-level data from 'teams' dict
                teams_dict = data.get('teams', {}) if isinstance(data, dict) else {}
                for team_id, team_info in teams_dict.items():
                    if isinstance(team_info, dict):
                        try:
                            title = team_info.get('title', '')
                            history = team_info.get('history', [])
                            if title and history:
                                for hist in history:
                                    if isinstance(hist, dict):
                                        h_a = hist.get('h_a', '')
                                        xg_val = _safe_float(hist.get('xG'))
                                        xga_val = _safe_float(hist.get('xGA'))
                                        ppda_att = hist.get('ppda', {}).get('att') if isinstance(hist.get('ppda'), dict) else None
                                        ppda_def = hist.get('ppda', {}).get('def') if isinstance(hist.get('ppda'), dict) else None
                                        deep = _safe_int(hist.get('deep'))
                                        # We could insert into understat_ppda or team_xg here
                                        total += 1
                        except: pass

                completed.add(job)
                self.save_checkpoint(list(completed))

        self.log('INFO', f'Total: {total} matches')
        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 7: FBref.com — Advanced stats with Cloudflare bypass
# ═══════════════════════════════════════════════════════════════════════════════

FBREF_COMP_IDS = {
    'Premier-League': '9', 'La-Liga': '12', 'Bundesliga': '20',
    'Serie-A': '11', 'Ligue-1': '13', 'Eredivisie': '23',
    'Primeira-Liga': '32', 'Super-Lig': '26', 'Russian-Premier-League': '30',
    'Scottish-Premiership': '40', 'Jupiler-Pro-League': '37',
    'Allsvenskan': '50', 'Eliteserien': '51', 'Danish-Superliga': '52',
    'Ekstraklasa': '36', 'Czech-First-League': '56', 'Liga-I': '172',
    'Austrian-Bundesliga': '43', 'Brasileirao-Serie-A': '24',
    'Primera-Division-Argentina': '21', 'Liga-MX': '31', 'MLS': '22',
    'Saudi-Professional-League': '93', 'Chinese-Super-League': '60',
    'J1-League': '74', 'K-League-1': '76', 'A-League': '71',
}


class FBref(BaseSourceHarvester):
    SOURCE_NAME = 'fbref'
    RATE = 12  # Respectful rate for FBref (aggressive blocking)
    BASE_URL = 'https://fbref.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_fbref (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition TEXT, season TEXT, team TEXT,
                games INTEGER, wins INTEGER, draws INTEGER, losses INTEGER,
                goals_for INTEGER, goals_against INTEGER, goal_diff INTEGER,
                points INTEGER, points_per_game REAL,
                possession REAL, shots INTEGER, shots_on_target INTEGER,
                shots_per90 REAL, sot_per90 REAL,
                goals_per_shot REAL, goals_per_sot REAL,
                expected REAL, expected_non_penalty REAL,
                expected_against REAL, expected_against_non_penalty REAL,
                expected_diff REAL,
                assists INTEGER, cards_yellow INTEGER, cards_red INTEGER,
                fouls INTEGER, offsides INTEGER, crosses INTEGER,
                interceptions INTEGER, tackles_won INTEGER,
                pens_made INTEGER, pens_att INTEGER,
                aerials_won INTEGER, clearances INTEGER, blocked_shots INTEGER,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_fbref_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition TEXT, season TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_goals INTEGER, away_goals INTEGER,
                home_xg REAL, away_xg REAL,
                home_possession REAL, away_possession REAL,
                home_shots INTEGER, away_shots INTEGER,
                home_sot INTEGER, away_sot INTEGER,
                home_corners INTEGER, away_corners INTEGER,
                home_fouls INTEGER, away_fouls INTEGER,
                home_yellows INTEGER, away_yellows INTEGER,
                home_reds INTEGER, away_reds INTEGER,
                venue TEXT, attendance INTEGER, referee TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def _parse_fbref_table(self, html: str, table_id: str) -> List[Dict]:
        if not _BS4_OK: return []
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', {'id': table_id})
        if not table: return []

        rows = []
        for tr in table.find_all('tr'):
            th = tr.find('th', {'data-stat': lambda x: x in ('player', 'team', 'squad')})
            if not th: continue
            row = {}
            for td in tr.find_all(['td', 'th']):
                stat = td.get('data-stat')
                if stat: row[stat] = td.get_text(strip=True)
            if row: rows.append(row)
        return rows

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        seasons = [f'{datetime.now().year-1}-{datetime.now().year}',
                   f'{datetime.now().year-2}-{datetime.now().year-1}']

        total = 0
        for league_slug, comp_id in FBREF_COMP_IDS.items():
            for season in seasons:
                job = f'{league_slug}/{season}'
                if job in completed: continue

                # Try different URL patterns for FBref
                urls = [
                    f'{self.BASE_URL}/en/comps/{comp_id}/{season}/stats/{season}-{league_slug}-Stats',
                    f'{self.BASE_URL}/en/comps/{comp_id}/{season}/stats/{season}-{league_slug}-Stats#all_stats_standard',
                    f'{self.BASE_URL}/en/comps/{comp_id}/{season}/schedule/{season}-{league_slug}-Scores-and-Fixtures',
                ]

                for url in urls:
                    html = self.fetch(url, retries=4, timeout=90, impersonate='chrome124')
                    if html and len(html) > 500: break
                if not html: continue

                # Parse standard stats table
                rows = self._parse_fbref_table(html, 'stats_standard')
                if not rows: rows = self._parse_fbref_table(html, 'stats_standard_9')

                for row in rows:
                    team = row.get('team', '')
                    if not team: continue
                    sql = '''INSERT OR IGNORE INTO source_fbref
                        (competition, season, team, games, wins, draws, losses,
                         goals_for, goals_against, goal_diff, points, points_per_game,
                         expected, expected_non_penalty, expected_against, hash)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
                    h = _make_hash(comp_id, season, team)
                    pts = (_safe_int(row.get('wins', 0)) or 0) * 3 + (_safe_int(row.get('draws', 0)) or 0)
                    ppg = pts / max(_safe_int(row.get('games', 1)) or 1, 1)
                    if self.insert(sql, (league_slug, season, team,
                        _safe_int(row.get('games')), _safe_int(row.get('wins')),
                        _safe_int(row.get('draws')), _safe_int(row.get('losses')),
                        _safe_int(row.get('goals_for')), _safe_int(row.get('goals_against')),
                        _safe_int(row.get('goal_diff')), pts, ppg,
                        _safe_float(row.get('xg')), _safe_float(row.get('npxg')),
                        _safe_float(row.get('xg_against')), h)):
                        total += 1

                # Also try fixtures page for match-level data
                match_html = self.fetch(
                    f'{self.BASE_URL}/en/comps/{comp_id}/{season}/schedule/{season}-{league_slug}-Scores-and-Fixtures',
                    retries=3, timeout=60
                )
                if match_html:
                    match_rows = self._parse_fbref_table(match_html, 'sched_2025-2026_9_1')
                    for mr in match_rows[:50]:
                        home = mr.get('home_team', ''); away = mr.get('away_team', '')
                        if not home or not away: continue
                        sql = '''INSERT OR IGNORE INTO source_fbref_matches
                            (competition, season, match_date, home_team, away_team,
                             home_goals, away_goals, home_xg, away_xg, hash)
                            VALUES (?,?,?,?,?,?,?,?,?,?)'''
                        h = _make_hash(comp_id, season, home, away)
                        self.insert(sql, (league_slug, season, mr.get('date',''),
                            home, away, _safe_int(mr.get('home_goals')),
                            _safe_int(mr.get('away_goals')),
                            _safe_float(mr.get('home_xg')), _safe_float(mr.get('away_xg')), h))

                completed.add(job)
                self.save_checkpoint(list(completed))

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 8: FootyStats.org — Calculated stats
# ═══════════════════════════════════════════════════════════════════════════════

class FootyStats(BaseSourceHarvester):
    SOURCE_NAME = 'footystats'
    RATE = 10
    BASE_URL = 'https://footystats.org'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_footystats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, season TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_goals INTEGER, away_goals INTEGER,
                home_xg REAL, away_xg REAL,
                home_shots INTEGER, away_shots INTEGER,
                home_sot INTEGER, away_sot INTEGER,
                home_possession REAL, away_possession REAL,
                home_corners INTEGER, away_corners INTEGER,
                home_fouls INTEGER, away_fouls INTEGER,
                home_yellows INTEGER, away_yellows INTEGER,
                home_reds INTEGER, away_reds INTEGER,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        leagues = ['england/premier-league', 'spain/laliga', 'germany/bundesliga',
                   'italy/serie-a', 'france/ligue-1']

        total = 0
        for league in leagues:
            if league in completed: continue
            url = f'{self.BASE_URL}/matches/{league}/'
            html = self.fetch(url, retries=3, timeout=45)
            if not html: continue

            if _BS4_OK:
                soup = BeautifulSoup(html, 'html.parser')
                for tr in soup.find_all('tr'):
                    tds = tr.find_all('td')
                    if len(tds) < 8: continue
                    try:
                        cells = [td.get_text(strip=True) for td in tds]
                        home, score, away = cells[0], cells[1], cells[2]
                        if ':' not in score: continue
                        parts = score.split(':')
                        sql = '''INSERT OR IGNORE INTO source_footystats
                            (league, match_date, home_team, away_team, home_goals, away_goals, hash)
                            VALUES (?,?,?,?,?,?,?)'''
                        h = _make_hash(league, home, away, score)
                        if self.insert(sql, (league, '', home, away,
                            _safe_int(parts[0]), _safe_int(parts[1]), h)): total += 1
                    except: pass

            completed.add(league)
            self.save_checkpoint(list(completed))

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 9: Pinnacle.com — Sharp odds
# ═══════════════════════════════════════════════════════════════════════════════

class Pinnacle(BaseSourceHarvester):
    SOURCE_NAME = 'pinnacle'
    RATE = 15
    BASE_URL = 'https://www.pinnacle.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_pinnacle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_open REAL, draw_open REAL, away_open REAL,
                home_close REAL, draw_close REAL, away_close REAL,
                home_max REAL, draw_max REAL, away_max REAL,
                home_min REAL, draw_min REAL, away_min REAL,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        # Pinnacle has a sports API
        api_url = 'https://guest.api.arcadia.pinnacle.com/0.1/leagues'
        html = self.fetch(api_url, retries=3, timeout=30, accept_json=True,
                         custom_headers={'X-API-Key': 'guest'})
        # Placeholder — real Pinnacle API requires specific endpoints
        self.log('INFO', 'Pinnacle API requires game-specific endpoints')
        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 10: The Odds API — the-odds-api.com
# ═══════════════════════════════════════════════════════════════════════════════

class OddsAPI(BaseSourceHarvester):
    SOURCE_NAME = 'odds_api'
    RATE = 30
    BASE_URL = 'https://api.the-odds-api.com/v4'

    def __init__(self):
        super().__init__()
        self.api_key = API_KEYS.get('odds_api', '1aa4dd22f7ee80b8d03c654c064c4fce')
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_odds_api (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sport TEXT, match_date TEXT,
                home_team TEXT, away_team TEXT,
                home_odds REAL, draw_odds REAL, away_odds REAL,
                bookmaker TEXT, last_update TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        sports_url = f'{self.BASE_URL}/sports/?apiKey={self.api_key}'
        sports_html = self.fetch(sports_url, retries=3, timeout=30, accept_json=True)
        if not sports_html: return self.summary()

        try:
            sports = json.loads(sports_html)
            if isinstance(sports, dict) and 'sports' in sports:
                sports = sports['sports']
        except: return self.summary()

        total = 0
        for sport in sports[:20]:
            sport_key = sport.get('key', '') if isinstance(sport, dict) else ''
            if not sport_key: continue

            odds_url = f'{self.BASE_URL}/odds/?apiKey={self.api_key}&sport={sport_key}&regions=uk&markets=h2h'
            odds_html = self.fetch(odds_url, retries=2, timeout=20, accept_json=True)
            if not odds_html: continue

            try:
                matches = json.loads(odds_html)
                if isinstance(matches, list):
                    for match in matches:
                        home = match.get('home_team', '')
                        away = match.get('away_team', '')
                        if not home or not away: continue
                        commence = match.get('commence_time', '')[:19]
                        bookmakers = match.get('bookmakers', [])
                        if not bookmakers: continue
                        bm = bookmakers[0]
                        markets = bm.get('markets', [])
                        if not markets: continue
                        outcomes = markets[0].get('outcomes', [])
                        if len(outcomes) < 2: continue
                        oh = next((o.get('price') for o in outcomes if o.get('name','').lower() == home.lower()), None)
                        od = next((o.get('price') for o in outcomes if o.get('name','') == 'Draw'), None)
                        oa = next((o.get('price') for o in outcomes if o.get('name','').lower() == away.lower()), None)

                        sql = '''INSERT OR IGNORE INTO source_odds_api
                            (sport, match_date, home_team, away_team, home_odds, draw_odds, away_odds, bookmaker, hash)
                            VALUES (?,?,?,?,?,?,?,?,?)'''
                        h = _make_hash(sport_key, commence, home, away)
                        if self.insert(sql, (sport_key, commence, home, away, oh, od, oa,
                            bm.get('title', ''), h)): total += 1
            except: pass

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 11: Betfair Exchange API
# ═══════════════════════════════════════════════════════════════════════════════

class Betfair(BaseSourceHarvester):
    SOURCE_NAME = 'betfair'
    RATE = 30
    BASE_URL = 'https://api.betfair.com/exchange/betting/rest/v1.0'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_betfair (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT, market_id TEXT, match_date TEXT,
                home_team TEXT, away_team TEXT,
                back_h REAL, back_d REAL, back_a REAL,
                lay_h REAL, lay_d REAL, lay_a REAL,
                volume_h REAL, volume_d REAL, volume_a REAL,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        # Betfair API requires certificate auth (complex setup)
        # Try public endpoint for testing
        test_url = f'{self.BASE_URL}/listEvents?filter={{}}'
        self.log('INFO', 'Betfair requires certificate authentication')
        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 12: Flashscore.com — Live results & odds
# ═══════════════════════════════════════════════════════════════════════════════

class Flashscore(BaseSourceHarvester):
    SOURCE_NAME = 'flashscore'
    RATE = 15
    BASE_URL = 'https://www.flashscore.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_flashscore (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, match_date DATE, home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                home_formation TEXT, away_formation TEXT,
                odds_h REAL, odds_d REAL, odds_a REAL,
                status TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        # Flashscore leagues
        league_paths = [
            'football/england/premier-league', 'football/spain/laliga',
            'football/germany/bundesliga', 'football/italy/serie-a',
            'football/france/ligue-1',
        ]

        total = 0
        for path in league_paths:
            if path in completed: continue
            url = f'{self.BASE_URL}/{path}/results/'
            html = self.fetch(url, retries=3, timeout=45)
            if not html: continue

            if _BS4_OK:
                soup = BeautifulSoup(html, 'html.parser')
                for match_div in soup.find_all('div', class_='event__match'):
                    try:
                        home_el = match_div.find('div', class_='event__homeParticipant')
                        away_el = match_div.find('div', class_='event__awayParticipant')
                        score_el = match_div.find('div', class_='event__score')
                        if not all([home_el, away_el, score_el]): continue
                        home = home_el.get_text(strip=True)
                        away = away_el.get_text(strip=True)
                        score = score_el.get_text(strip=True)
                        if ':' not in score: continue
                        parts = [p.strip() for p in score.split(':')]
                        sql = '''INSERT OR IGNORE INTO source_flashscore
                            (league, home_team, away_team, home_score, away_score, hash)
                            VALUES (?,?,?,?,?,?)'''
                        h = _make_hash(path, home, away, score)
                        if self.insert(sql, (path, home, away,
                            _safe_int(parts[0]), _safe_int(parts[1]), h)): total += 1
                    except: pass

            completed.add(path)
            self.save_checkpoint(list(completed))

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 13: Transfermarkt.com — Team values, injuries, squad info
# ═══════════════════════════════════════════════════════════════════════════════

TRANSFERMARKT_LEAGUES = {
    'Premier League': 'GB1', 'La Liga': 'ES1', 'Bundesliga': 'L1',
    'Serie A': 'IT1', 'Ligue 1': 'FR1', 'Eredivisie': 'NL1',
    'Primeira Liga': 'PO1', 'Super Lig': 'TR1', 'Russian Premier League': 'RU1',
    'Scottish Premiership': 'SC1', 'Jupiler Pro League': 'BE1',
    'Serie A Brazil': 'BRA1', 'Liga MX': 'MX1', 'MLS': 'MLS1',
    'Allsvenskan': 'SE1', 'Eliteserien': 'NO1', 'Danish Superliga': 'DK1',
    'Ekstraklasa': 'PL1', 'Championship': 'GB2', 'La Liga 2': 'ES2',
    '2. Bundesliga': 'L2', 'Serie B': 'IT2', 'Ligue 2': 'FR2',
}


class Transfermarkt(BaseSourceHarvester):
    SOURCE_NAME = 'transfermarkt'
    RATE = 8  # Very strict rate limit
    BASE_URL = 'https://www.transfermarkt.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_transfermarkt (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT, league TEXT, season TEXT,
                player_name TEXT, position TEXT, age INTEGER,
                nationality TEXT, market_value_euro REAL,
                contract_until TEXT, injury_status TEXT,
                games_played INTEGER, goals_scored INTEGER,
                assists INTEGER, minutes_played INTEGER,
                avg_rating REAL,
                squad_total_value REAL, squad_avg_age REAL,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_transfermarkt_injuries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT, player_name TEXT, injury_type TEXT,
                injury_start TEXT, injury_end TEXT,
                expected_return TEXT, status TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        total = 0
        for league_name, league_id in TRANSFERMARKT_LEAGUES.items():
            job = league_id
            if job in completed: continue

            # Squad page
            url = f'{self.BASE_URL}/{league_id}/startseite/wettbewerb/{league_id}'
            html = self.fetch(url, retries=4, timeout=90, impersonate='chrome124')
            if not html: continue

            if _BS4_OK:
                soup = BeautifulSoup(html, 'html.parser')
                # Extract team links
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if f'/startseite/verein/' in href:
                        team_url = f'{self.BASE_URL}{href}'
                        team_html = self.fetch(team_url, retries=3, timeout=60, impersonate='chrome124')
                        if not team_html: continue
                        rows = self._parse_squad(team_html, league_name, href)
                        total += rows

                # Injuries page
                injury_url = f'{self.BASE_URL}/{league_id}/verletzungen/wettbewerb/{league_id}'
                inj_html = self.fetch(injury_url, retries=2, timeout=45, impersonate='chrome124')
                if inj_html:
                    self._parse_injuries(inj_html, league_name)

            completed.add(job)
            self.save_checkpoint(list(completed))

        return self.summary()

    def _parse_squad(self, html: str, league: str, team_path: str) -> int:
        if not _BS4_OK: return 0
        soup = BeautifulSoup(html, 'html.parser')
        count = 0

        # Extract team name
        team_el = soup.find('h1', class_='data-header__headline-wrapper')
        team = team_el.get_text(strip=True) if team_el else team_path.split('/')[-1] if '/verein/' in team_path else team_path

        # Squad table
        for table in soup.find_all('table', class_='items'):
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 5: continue
                try:
                    name_el = tr.find('td', class_='posrela')
                    if not name_el: continue
                    name_link = name_el.find('a')
                    player_name = name_link.get_text(strip=True) if name_link else name_el.get_text(strip=True)

                    position_el = tr.find('td', class_='zentriert')
                    position = position_el.get_text(strip=True) if position_el else ''

                    # Market value
                    mv_el = tr.find('td', class_='rechts')
                    mv_text = mv_el.get_text(strip=True) if mv_el else ''
                    mv = None
                    if mv_text:
                        mv = mv_text.replace('€','').replace(',','')
                        if 'm' in mv.lower(): mv = _safe_float(mv.lower().replace('m','')) * 1_000_000
                        elif 'k' in mv.lower(): mv = _safe_float(mv.lower().replace('k','')) * 1_000
                        else: mv = _safe_float(mv)

                    sql = '''INSERT OR IGNORE INTO source_transfermarkt
                        (team, league, player_name, position, market_value_euro, hash)
                        VALUES (?,?,?,?,?,?)'''
                    h = _make_hash(team, league, player_name)
                    if self.insert(sql, (team, league, player_name, position, mv, h)): count += 1
                except: pass

        return count

    def _parse_injuries(self, html: str, league: str) -> int:
        if not _BS4_OK: return 0
        soup = BeautifulSoup(html, 'html.parser')
        count = 0
        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) < 4: continue
            try:
                player = tds[0].get_text(strip=True)
                injury = tds[1].get_text(strip=True) if len(tds) > 1 else ''
                team = tds[2].get_text(strip=True) if len(tds) > 2 else ''
                return_date = tds[3].get_text(strip=True) if len(tds) > 3 else ''
                sql = '''INSERT OR IGNORE INTO source_transfermarkt_injuries
                    (team, player_name, injury_type, expected_return, hash) VALUES (?,?,?,?,?)'''
                h = _make_hash(team, player, injury)
                if self.insert(sql, (team, player, injury, return_date, h)): count += 1
            except: pass
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 14: SofaScore.com — Lineups and match stats
# ═══════════════════════════════════════════════════════════════════════════════

class SofaScore(BaseSourceHarvester):
    SOURCE_NAME = 'sofascore'
    RATE = 20
    BASE_URL = 'https://api.sofascore.com/api/v1'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_sofascore_extended (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT UNIQUE, league TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_formation TEXT, away_formation TEXT,
                home_lineup TEXT, away_lineup TEXT,
                home_manager TEXT, away_manager TEXT,
                home_avg_rating REAL, away_avg_rating REAL,
                home_possession REAL, away_possession REAL,
                home_attacks INTEGER, away_attacks INTEGER,
                home_dangerous_attacks INTEGER, away_dangerous_attacks INTEGER,
                home_shots_blocked INTEGER, away_shots_blocked INTEGER,
                home_interceptions INTEGER, away_interceptions INTEGER,
                home_saves INTEGER, away_saves INTEGER,
                home_pass_accuracy REAL, away_pass_accuracy REAL,
                home_through_balls INTEGER, away_through_balls INTEGER,
                home_crosses INTEGER, away_crosses INTEGER,
                home_long_balls INTEGER, away_long_balls INTEGER,
                home_duels_won INTEGER, away_duels_won INTEGER,
                home_aerial_won INTEGER, away_aerial_won INTEGER,
                home_clearances INTEGER, away_clearances INTEGER,
                home_offsides INTEGER, away_offsides INTEGER,
                home_goal_attempts INTEGER, away_goal_attempts INTEGER,
                raw_json TEXT, hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        # Get recent matches from SofaScore API
        url = f'{self.BASE_URL}/sport/football/events/live'
        html = self.fetch(url, retries=3, timeout=30, accept_json=True,
                         custom_headers={'Origin': 'https://www.sofascore.com'})
        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 15: Soccerway.com — Results + lineups
# ═══════════════════════════════════════════════════════════════════════════════

class Soccerway(BaseSourceHarvester):
    SOURCE_NAME = 'soccerway'
    RATE = 15
    BASE_URL = 'https://int.soccerway.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_soccerway (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition TEXT, season TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                home_formation TEXT, away_formation TEXT,
                home_lineup_json TEXT, away_lineup_json TEXT,
                home_bench_json TEXT, away_bench_json TEXT,
                attendance INTEGER, venue TEXT, referee TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        leagues = ['premier-league', 'la-liga', 'bundesliga', 'serie-a', 'ligue-1']
        total = 0
        for league in leagues:
            url = f'{self.BASE_URL}/national/england/{league}/20252026/regular-season/r73087/matches/'
            html = self.fetch(url, retries=3, timeout=45)
            if not html: continue
            if _BS4_OK:
                soup = BeautifulSoup(html, 'html.parser')
                for a in soup.find_all('a', class_='match-link'):
                    match_url = a.get('href', '')
                    if match_url:
                        full_url = f'{self.BASE_URL}{match_url}'
                        mhtml = self.fetch(full_url, retries=2, timeout=30)
                        if mhtml:
                            total += 1
        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 16: Livescore.com — Live results
# ═══════════════════════════════════════════════════════════════════════════════

class LiveScore(BaseSourceHarvester):
    SOURCE_NAME = 'livescore'
    RATE = 20
    BASE_URL = 'https://www.livescore.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_livescore (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                home_formation TEXT, away_formation TEXT,
                home_lineup TEXT, away_lineup TEXT,
                odds_h REAL, odds_d REAL, odds_a REAL,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        # Livescore uses JavaScript heavy rendering
        # Try their API endpoints
        api_url = f'{self.BASE_URL}/en/football/'
        html = self.fetch(api_url, retries=3, timeout=30)
        if html and _BS4_OK:
            soup = BeautifulSoup(html, 'html.parser')
            for match_div in soup.find_all('div', class_='match'):
                try:
                    home = match_div.find('div', class_='home').get_text(strip=True)
                    away = match_div.find('div', class_='away').get_text(strip=True)
                    score = match_div.find('div', class_='score').get_text(strip=True)
                    if ':' not in score: continue
                    parts = score.split(':')
                    sql = 'INSERT OR IGNORE INTO source_livescore (home_team, away_team, home_score, away_score, hash) VALUES (?,?,?,?,?)'
                    h = _make_hash(home, away, score)
                    self.insert(sql, (home, away, _safe_int(parts[0]), _safe_int(parts[1]), h))
                except: pass
        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 17: football-data.org API
# ═══════════════════════════════════════════════════════════════════════════════

class FootballDataOrg(BaseSourceHarvester):
    SOURCE_NAME = 'football_data_org'
    RATE = 10
    BASE_URL = 'https://api.football-data.org/v4'

    def __init__(self):
        super().__init__()
        self.api_key = API_KEYS.get('football_data_org', 'c7d5c5c1b80d4ebe821a58b3087b968d')
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_football_data_org (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition TEXT, season TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_goals INTEGER, away_goals INTEGER,
                status TEXT, stage TEXT, group_name TEXT,
                home_halftime INTEGER, away_halftime INTEGER,
                referee TEXT, venue TEXT, attendance INTEGER,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        competitions = ['PL', 'BL1', 'SA', 'PD', 'FL1', 'DED', 'PPL', 'ELC', 'CL', 'EL']

        total = 0
        for comp in competitions:
            url = f'{self.BASE_URL}/competitions/{comp}/matches'
            html = self.fetch(url, retries=3, timeout=30, accept_json=True,
                            custom_headers={'X-Auth-Token': self.api_key})
            if not html: continue

            try:
                data = json.loads(html)
                matches = data.get('matches', [])
                for match in matches[:50]:
                    home = match.get('homeTeam', {}).get('name', '')
                    away = match.get('awayTeam', {}).get('name', '')
                    if not home or not away: continue
                    score = match.get('score', {}).get('fullTime', {})
                    ht_score = match.get('score', {}).get('halfTime', {})

                    sql = '''INSERT OR IGNORE INTO source_football_data_org
                        (competition, season, match_date, home_team, away_team,
                         home_goals, away_goals, status, stage,
                         home_halftime, away_halftime, referee, venue, hash)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
                    h = _make_hash(comp, match.get('utcDate','')[:10], home, away)
                    if self.insert(sql, (comp, match.get('season',{}).get('startDate','')[:4],
                        match.get('utcDate','')[:10], home, away,
                        score.get('home'), score.get('away'),
                        match.get('status',''), match.get('stage',''),
                        ht_score.get('home'), ht_score.get('away'),
                        match.get('referees',[{}])[0].get('name','') if match.get('referees') else '',
                        match.get('venue',''), h)): total += 1
            except: pass

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 18: API-Football (RapidAPI)
# ═══════════════════════════════════════════════════════════════════════════════

class APIFootball(BaseSourceHarvester):
    SOURCE_NAME = 'api_football'
    RATE = 30
    BASE_URL = 'https://v3.football.api-sports.io'

    def __init__(self):
        super().__init__()
        self.api_key = API_KEYS.get('api_sport', '2064edeecfd82a209e2dca203d5ac9b6')
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_api_football (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id INTEGER, league_id INTEGER, league_name TEXT,
                season INTEGER, match_date DATE, round TEXT,
                home_team TEXT, away_team TEXT,
                home_goals INTEGER, away_goals INTEGER,
                home_halftime INTEGER, away_halftime INTEGER,
                home_shots INTEGER, away_shots INTEGER,
                home_sot INTEGER, away_sot INTEGER,
                home_possession REAL, away_possession REAL,
                home_fouls INTEGER, away_fouls INTEGER,
                home_corners INTEGER, away_corners INTEGER,
                home_yellows INTEGER, away_yellows INTEGER,
                home_reds INTEGER, away_reds INTEGER,
                home_saves INTEGER, away_saves INTEGER,
                home_expected_goals REAL, away_expected_goals REAL,
                home_formation TEXT, away_formation TEXT,
                referee TEXT, venue TEXT, attendance INTEGER,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        completed = self.get_completed() if not force else set()

        # Get leagues
        leagues_url = f'{self.BASE_URL}/leagues'
        headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io',
        }
        leagues_html = self.fetch(leagues_url, retries=3, timeout=30, accept_json=True, custom_headers=headers)
        total = 0

        if not leagues_html: return self.summary()
        try:
            leagues_data = json.loads(leagues_html)
            leagues_list = leagues_data.get('response', [])[:10]  # Max 10 leagues
        except: return self.summary()

        for league_info in leagues_list:
            league = league_info.get('league', {})
            league_id = league.get('id')
            league_name = league.get('name', '')
            if not league_id: continue

            # Get current season
            season = datetime.now().year
            for season_info in league_info.get('seasons', []):
                if season_info.get('current', False):
                    season = season_info.get('year', season)

            job = f'{league_id}/{season}'
            if job in completed: continue

            # Get fixtures
            fixtures_url = f'{self.BASE_URL}/fixtures?league={league_id}&season={season}'
            fix_html = self.fetch(fixtures_url, retries=3, timeout=30, accept_json=True, custom_headers=headers)
            if not fix_html: continue

            try:
                fix_data = json.loads(fix_html)
                fixtures = fix_data.get('response', [])
                for fix in fixtures:
                    fixture = fix.get('fixture', {})
                    teams = fix.get('teams', {})
                    goals = fix.get('goals', {})
                    score = fix.get('score', {})
                    ht = score.get('halftime', {})
                    stats_by_team = {}

                    # Get statistics
                    stats_url = f'{self.BASE_URL}/fixtures/statistics?fixture={fixture.get("id")}'
                    stats_html = self.fetch(stats_url, retries=2, timeout=20, accept_json=True, custom_headers=headers)
                    if stats_html:
                        try:
                            stats_data = json.loads(stats_html)
                            for stat_item in stats_data.get('response', []):
                                team_name = stat_item.get('team', {}).get('name', '')
                                for s in stat_item.get('statistics', []):
                                    stats_by_team[f'{team_name}_{s.get("type","")}'] = s.get('value')
                        except: pass

                    home_team = teams.get('home', {}).get('name', '')
                    away_team = teams.get('away', {}).get('name', '')
                    if not home_team or not away_team: continue

                    def get_stat(team, stat_type):
                        val = stats_by_team.get(f'{team}_{stat_type}')
                        if val is None: val = stats_by_team.get(f'{team} {stat_type}')
                        if isinstance(val, str):
                            if '%' in val: return _safe_float(val.replace('%',''))
                            return _safe_int(val)
                        return val

                    sql = '''INSERT OR IGNORE INTO source_api_football
                        (fixture_id, league_id, league_name, season, match_date,
                         home_team, away_team, home_goals, away_goals,
                         home_halftime, away_halftime, referee, venue, hash)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
                    h = _make_hash(fixture.get('id'), home_team, away_team)
                    if self.insert(sql, (
                        fixture.get('id'), league_id, league_name, season,
                        fixture.get('date','')[:10],
                        home_team, away_team,
                        goals.get('home'), goals.get('away'),
                        ht.get('home'), ht.get('away'),
                        fixture.get('referee',''), fixture.get('venue',{}).get('name',''),
                        h)): total += 1

            except Exception as e:
                self.log('ERROR', f'API-Football parse: {e}')

            completed.add(job)
            self.save_checkpoint(list(completed))

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 19: StatsBomb Open Data — GitHub
# ═══════════════════════════════════════════════════════════════════════════════

class StatsBomb(BaseSourceHarvester):
    SOURCE_NAME = 'statsbomb'
    RATE = 60
    BASE_URL = 'https://raw.githubusercontent.com/statsbomb/open-data/master/data'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_statsbomb_enhanced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER, competition TEXT, season TEXT,
                match_date DATE, home_team TEXT, away_team TEXT,
                home_goals INTEGER, away_goals INTEGER,
                venue TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        # Fetch competitions
        comp_url = f'{self.BASE_URL}/competitions.json'
        comp_json = self.fetch(comp_url, retries=3, timeout=30, accept_json=True)
        if not comp_json: return self.summary()

        total = 0
        try:
            competitions = json.loads(comp_json)
            for comp in competitions[:15]:
                comp_id = comp.get('competition_id')
                season_id = comp.get('season_id')
                comp_name = comp.get('competition_name', '')
                season_name = comp.get('season_name', '')

                # Get matches
                matches_url = f'{self.BASE_URL}/matches/{comp_id}/{season_id}.json'
                m_json = self.fetch(matches_url, retries=2, timeout=20, accept_json=True)
                if not m_json: continue

                matches = json.loads(m_json)
                for match in matches[:20]:
                    home_team = match.get('home_team', {}).get('home_team_name', '')
                    away_team = match.get('away_team', {}).get('away_team_name', '')
                    if not home_team or not away_team: continue

                    sql = '''INSERT OR IGNORE INTO source_statsbomb_enhanced
                        (match_id, competition, season, match_date, home_team, away_team, hash)
                        VALUES (?,?,?,?,?,?,?)'''
                    h = _make_hash(match.get('match_id'), comp_name, season_name, home_team, away_team)
                    if self.insert(sql, (match.get('match_id'), comp_name, season_name,
                        match.get('match_date',''), home_team, away_team, h)): total += 1
        except Exception as e:
            self.log('ERROR', f'StatsBomb: {e}')

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 20: Kaggle Soccer Database (via SQLite or CSV)
# ═══════════════════════════════════════════════════════════════════════════════

class KaggleSoccer(BaseSourceHarvester):
    SOURCE_NAME = 'kaggle'
    RATE = 999  # Local file, no rate limit

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_kaggle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, season TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_goals INTEGER, away_goals INTEGER,
                home_shots INTEGER, away_shots INTEGER,
                home_sot INTEGER, away_sot INTEGER,
                home_fouls INTEGER, away_fouls INTEGER,
                home_corners INTEGER, away_corners INTEGER,
                home_yellows INTEGER, away_yellows INTEGER,
                home_reds INTEGER, away_reds INTEGER,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        total = 0

        # Look for Kaggle datasets already in the project
        candidate_dbs = [
            PROJECT_ROOT / 'football.db',
            PROJECT_ROOT / 'football_data.db',
            PROJECT_ROOT / 'database.sqlite',
            PROJECT_ROOT / 'european_football.db',
        ]

        for db_path in candidate_dbs:
            if not db_path.exists(): continue
            self.log('INFO', f'Found DB: {db_path.name}')
            try:
                conn = sqlite3.connect(str(db_path))
                tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                for t in tables:
                    tn = t[0]
                    if 'match' in tn.lower():
                        rows = conn.execute(f'SELECT COUNT(*) FROM "{tn}"').fetchone()[0]
                        self.log('INFO', f'  {tn}: {rows} rows')
                        # Try to copy data
                        try:
                            cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{tn}")').fetchall()]
                            if 'home_team_goal' in cols or 'home_goals' in cols or 'home_team_name' in cols:
                                pass  # Could do direct copy
                        except: pass
                conn.close()
            except: pass

        # Also try CSV files
        for csv_file in PROJECT_ROOT.glob('*.csv'):
            try:
                with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        home = row.get('home_team', row.get('HomeTeam', ''))
                        away = row.get('away_team', row.get('AwayTeam', ''))
                        score = row.get('score', row.get('FTHG', ''))
                        if not home or not away: continue
                        sql = '''INSERT OR IGNORE INTO source_kaggle
                            (league, match_date, home_team, away_team, hash)
                            VALUES (?,?,?,?,?)'''
                        h = _make_hash(csv_file.name, home, away, score)
                        if self.insert(sql, ('kaggle', '', home, away, h)): total += 1
            except: pass

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 21: ClubElo.com — ELO ratings CSV
# ═══════════════════════════════════════════════════════════════════════════════

class ClubElo(BaseSourceHarvester):
    SOURCE_NAME = 'clubelo'
    RATE = 30
    BASE_URL = 'http://clubelo.com'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_clubelo_enhanced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT, match_date DATE, elo REAL,
                elo_home REAL, elo_away REAL,
                opponent TEXT, division TEXT,
                importance REAL, result TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        total = 0

        # ClubElo CSV download
        csv_url = f'{self.BASE_URL}/Data/elo.csv'
        text = self.fetch(csv_url, retries=3, timeout=60)
        if text:
            lines = text.replace('\r\n', '\n').split('\n')
            for line in lines[1:5000]:  # First 5000 rows
                if not line.strip(): continue
                parts = line.split(',')
                if len(parts) < 5: continue
                try:
                    sql = '''INSERT OR IGNORE INTO source_clubelo_enhanced
                        (team, match_date, elo, hash) VALUES (?,?,?,?)'''
                    h = _make_hash(parts[0], parts[1], parts[2])
                    if self.insert(sql, (parts[0].strip(), parts[1].strip(),
                        _safe_float(parts[2]), h)): total += 1
                except: pass
            self.log('INFO', f'Loaded {total} ClubElo rows')

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 22: EloRatings.net — International team ELO
# ═══════════════════════════════════════════════════════════════════════════════

class EloRatings(BaseSourceHarvester):
    SOURCE_NAME = 'eloratings'
    RATE = 15
    BASE_URL = 'https://www.eloratings.net'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_eloratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT, match_date DATE,
                opponent TEXT, elo REAL, elo_opponent REAL,
                importance REAL, result TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        # Try eloratings.net API
        url = f'{self.BASE_URL}/world.html'
        html = self.fetch(url, retries=3, timeout=45)
        if html and _BS4_OK:
            soup = BeautifulSoup(html, 'html.parser')
            for row in soup.find_all('tr'):
                tds = row.find_all('td')
                if len(tds) >= 4:
                    # Extract ELO data
                    pass
        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 23: Infogol.net — xG model benchmark
# ═══════════════════════════════════════════════════════════════════════════════

class Infogol(BaseSourceHarvester):
    SOURCE_NAME = 'infogol'
    RATE = 10
    BASE_URL = 'https://www.infogol.net'

    def __init__(self):
        super().__init__()
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_infogol (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT, match_date DATE,
                home_team TEXT, away_team TEXT,
                home_goals INTEGER, away_goals INTEGER,
                home_xg REAL, away_xg REAL,
                home_shots INTEGER, away_shots INTEGER,
                home_sot INTEGER, away_sot INTEGER,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        # Infogol uses heavy JS rendering
        # Try API endpoints
        api_url = f'{self.BASE_URL}/en/matches'
        html = self.fetch(api_url, retries=3, timeout=45)
        if html and _BS4_OK:
            soup = BeautifulSoup(html, 'html.parser')
            matches = soup.find_all('div', class_='match-card')
            for m in matches[:50]:
                try:
                    home_el = m.find('span', class_='home-name')
                    away_el = m.find('span', class_='away-name')
                    xg_home = m.find('span', class_='xg-home')
                    xg_away = m.find('span', class_='xg-away')
                    if not home_el or not away_el: continue
                    sql = '''INSERT OR IGNORE INTO source_infogol
                        (home_team, away_team, home_xg, away_xg, hash) VALUES (?,?,?,?,?)'''
                    h = _make_hash(home_el.get_text(strip=True), away_el.get_text(strip=True))
                    self.insert(sql, (home_el.get_text(strip=True), away_el.get_text(strip=True),
                        _safe_float(xg_home.get_text(strip=True)) if xg_home else None,
                        _safe_float(xg_away.get_text(strip=True)) if xg_away else None, h))
                except: pass
        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 24: OpenWeatherMap — Weather data
# ═══════════════════════════════════════════════════════════════════════════════

class OpenWeatherMapSource(BaseSourceHarvester):
    SOURCE_NAME = 'openweathermap'
    RATE = 55
    BASE_URL = 'https://api.openweathermap.org/data/2.5'

    def __init__(self):
        super().__init__()
        self.api_key = API_KEYS.get('openweathermap', '')
        self.ensure_table('''
            CREATE TABLE IF NOT EXISTS source_weather (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_date DATE, venue TEXT, city TEXT, country TEXT,
                temp_c REAL, feels_like_c REAL, temp_min_c REAL, temp_max_c REAL,
                humidity INTEGER, pressure INTEGER,
                wind_speed REAL, wind_deg INTEGER,
                clouds INTEGER, weather_main TEXT, weather_desc TEXT,
                hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def harvest(self, force: bool = False) -> dict:
        self.log('INFO', 'HARVEST START')
        if not self.api_key:
            self.log('WARN', 'No OpenWeatherMap API key')
            return self.summary()

        # Get venues from the DB
        conn = get_db()
        try:
            venues = conn.execute('SELECT DISTINCT venue, city FROM venue_weather LIMIT 100').fetchall()
        except:
            venues = []
        conn.close()

        total = 0
        for venue, city in venues[:20]:
            if not venue and not city: continue
            # Use city name
            url = f'{self.BASE_URL}/weather?q={city or venue}&appid={self.api_key}&units=metric'
            html = self.fetch(url, retries=2, timeout=15, accept_json=True)
            if not html: continue

            try:
                data = json.loads(html)
                main = data.get('main', {})
                wind = data.get('wind', {})
                clouds = data.get('clouds', {})
                weather = data.get('weather', [{}])[0]

                sql = '''INSERT OR IGNORE INTO source_weather
                    (match_date, city, temp_c, feels_like_c, humidity, pressure,
                     wind_speed, clouds, weather_main, weather_desc, hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)'''
                h = _make_hash(city or venue, datetime.now().strftime('%Y%m%d'))
                if self.insert(sql, (datetime.now().strftime('%Y-%m-%d'),
                    city or venue,
                    _safe_float(main.get('temp')), _safe_float(main.get('feels_like')),
                    _safe_int(main.get('humidity')), _safe_int(main.get('pressure')),
                    _safe_float(wind.get('speed')), _safe_int(clouds.get('all')),
                    weather.get('main', ''), weather.get('description', ''), h)): total += 1
            except: pass

        return self.summary()


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

SOURCE_REGISTRY = {
    1: ('FootballDataUK', '🗄️ football-data.co.uk', FootballDataUK),
    2: ('BetExplorer', '📊 BetExplorer.com', BetExplorer),
    3: ('OddsPortal', '🎲 OddsPortal.com', OddsPortal),
    4: ('Source11v11', '📜 11v11.com', Source11v11),
    5: ('WhoScored', '⭐ WhoScored.com', WhoScored),
    6: ('Understat', '🎯 Understat.com', Understat),
    7: ('FBref', '📈 FBref.com', FBref),
    8: ('FootyStats', '📉 FootyStats.org', FootyStats),
    9: ('Pinnacle', '🏆 Pinnacle.com', Pinnacle),
    10: ('OddsAPI', '🔮 The Odds API', OddsAPI),
    11: ('Betfair', '🔄 Betfair Exchange', Betfair),
    12: ('Flashscore', '⚡ Flashscore.com', Flashscore),
    13: ('Transfermarkt', '💰 Transfermarkt.com', Transfermarkt),
    14: ('SofaScore', '📱 SofaScore.com', SofaScore),
    15: ('Soccerway', '⚽ Soccerway.com', Soccerway),
    16: ('LiveScore', '📺 Livescore.com', LiveScore),
    17: ('FootballDataOrg', '🔌 football-data.org', FootballDataOrg),
    18: ('APIFootball', '🚀 API-Football', APIFootball),
    19: ('StatsBomb', '📊 StatsBomb Open Data', StatsBomb),
    20: ('KaggleSoccer', '🗃️ Kaggle Soccer', KaggleSoccer),
    21: ('ClubElo', '📐 ClubElo.com', ClubElo),
    22: ('EloRatings', '🌍 EloRatings.net', EloRatings),
    23: ('Infogol', '📌 Infogol.net', Infogol),
    24: ('OpenWeatherMapSource', '🌤️ OpenWeatherMap', OpenWeatherMapSource),
}


def run_source(source_num: int, force: bool = False, **kwargs) -> dict:
    """Run a single source by number (1-24)."""
    if source_num not in SOURCE_REGISTRY:
        return {'source': f'unknown_{source_num}', 'error': 'Invalid source number', 'rows': 0}

    name, emoji, cls = SOURCE_REGISTRY[source_num]
    log('ORCHESTRATOR', 'INFO', f'{emoji} Starting {name} (source {source_num})')
    _update_progress(name, 'running', f'{emoji} Launching {name}')

    try:
        harvester = cls()
        result = harvester.harvest(force=force, **kwargs)
        dur = result.get('duration', time.time() - harvester.stats['start'])
        log('ORCHESTRATOR', 'INFO', f'✅ {name}: {result.get("rows",0)} rows, {result.get("errors",0)} errors, {dur:.1f}s')
        _update_progress(name, '✅ done', f'{result.get("rows",0)} rows, {result.get("errors",0)} errors')
        return result
    except Exception as e:
        log('ORCHESTRATOR', 'ERROR', f'❌ {name} failed: {e}')
        _update_progress(name, '❌ failed', str(e))
        return {'source': name, 'error': str(e), 'rows': 0}


def run_all_sources(force: bool = False, max_workers: int = 4, sources: List[int] = None) -> Dict[int, dict]:
    """Run multiple sources in parallel.

    Args:
        force: Re-fetch cached data
        max_workers: Max parallel sources (default 4)
        sources: List of source numbers to run (default: all 1-24)

    Returns:
        Dict mapping source_num -> result
    """
    if sources is None:
        sources = list(range(1, 25))

    results = {}
    start = time.time()

    log('ORCHESTRATOR', 'INFO', f'🚀 UNIFIED HARVEST: {len(sources)} sources, {max_workers} workers')

    # Dedicated sequential runner for sources that need special handling
    quick_sources = [1, 6, 10, 17, 18, 20, 21]  # Fast API/file sources
    slow_sources = [s for s in sources if s not in quick_sources]

    # Run quick sources in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for src in quick_sources:
            if src in sources:
                future = executor.submit(run_source, src, force)
                future_map[future] = src

        for future in as_completed(future_map):
            src = future_map[future]
            try:
                results[src] = future.result()
            except Exception as e:
                results[src] = {'source': SOURCE_REGISTRY.get(src, [str(src)])[0], 'error': str(e), 'rows': 0}

    # Run slow sources sequentially
    for src in slow_sources:
        results[src] = run_source(src, force)

    total_rows = sum(r.get('rows', 0) for r in results.values())
    total_errors = sum(r.get('errors', 0) for r in results.values())
    dur = time.time() - start

    log('ORCHESTRATOR', 'INFO', f'🏁 UNIFIED HARVEST COMPLETE: {total_rows} total rows, {total_errors} errors, {dur:.1f}s')
    log('ORCHESTRATOR', 'INFO', f'📊 Sources completed: {sum(1 for r in results.values() if r.get("rows",0) > 0)}/{len(sources)}')

    results['_meta'] = {
        'total_rows': total_rows,
        'total_errors': total_errors,
        'duration_seconds': dur,
        'sources_planned': len(sources),
        'sources_with_data': sum(1 for r in results.values() if r.get('rows',0) > 0),
        'timestamp': datetime.now().isoformat(),
    }

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def print_results(results: dict):
    """Pretty-print harvest results."""
    meta = results.pop('_meta', {})
    print('\n' + '═' * 72)
    print(f'  🏁 UNIFIED HARVEST — FINAL REPORT')
    print('═' * 72)
    print(f'  Total rows fetched:  {meta.get("total_rows", 0):,}')
    print(f'  Total errors:        {meta.get("total_errors", 0):,}')
    print(f'  Duration:            {meta.get("duration_seconds", 0):.1f}s')
    print(f'  Sources active:      {meta.get("sources_with_data", 0)}/{meta.get("sources_planned", 0)}')
    print('─' * 72)
    print(f'  {"#":>2} | {"Source":<30} | {"Rows":>8} | {"Errors":>6}')
    print('─' * 72)

    for num in sorted(SOURCE_REGISTRY.keys()):
        if num in results:
            r = results[num]
            rows = r.get('rows', 0)
            errs = r.get('errors', 0)
            name = SOURCE_REGISTRY[num][0]
            icon = '✅' if rows > 0 else '❌' if r.get('error') else '⏭️'
            print(f'  {icon} {num:>2} | {name:<30} | {rows:>8,} | {errs:>6}')
        else:
            name = SOURCE_REGISTRY.get(num, ['?'])[0]
            print(f'  ⏭️ {num:>2} | {name:<30} | {"-":>8} | {"-":>6}')

    print('═' * 72)
    results['_meta'] = meta  # Restore


def show_preview(source_num: int, limit: int = 5):
    """Show first N rows from the specified source's table."""
    if source_num not in SOURCE_REGISTRY: return
    name, _, _ = SOURCE_REGISTRY[source_num]
    table_name = f'source_{name.lower()}'

    # Map class names to table names
    table_map = {
        'FootballDataUK': 'source_football_data_uk',
        'BetExplorer': 'source_betexplorer',
        'OddsPortal': 'source_oddsportal',
        'Source11v11': 'source_11v11',
        'WhoScored': 'source_whoscored',
        'Understat': 'source_understat',
        'FBref': 'source_fbref',
        'FootyStats': 'source_footystats',
        'Pinnacle': 'source_pinnacle',
        'OddsAPI': 'source_odds_api',
        'Betfair': 'source_betfair',
        'Flashscore': 'source_flashscore',
        'Transfermarkt': 'source_transfermarkt',
        'SofaScore': 'source_sofascore_extended',
        'Soccerway': 'source_soccerway',
        'LiveScore': 'source_livescore',
        'FootballDataOrg': 'source_football_data_org',
        'APIFootball': 'source_api_football',
        'StatsBomb': 'source_statsbomb_enhanced',
        'KaggleSoccer': 'source_kaggle',
        'ClubElo': 'source_clubelo_enhanced',
        'EloRatings': 'source_eloratings',
        'Infogol': 'source_infogol',
        'OpenWeatherMapSource': 'source_weather',
    }

    tbl = table_map.get(name)
    if not tbl: return

    conn = get_db()
    try:
        rows = conn.execute(f'SELECT * FROM "{tbl}" WHERE 1=1 ORDER BY id DESC LIMIT {limit}').fetchall()
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{tbl}")').fetchall()]
        conn.close()

        print(f'\n📋 Preview: {tbl} ({len(rows)} rows shown)')
        print('─' * 72)
        for row in rows:
            d = dict(zip(cols, row))
            # Show first 6 meaningful columns
            display_cols = [k for k in ['match_date','home_team','away_team','home_score','away_score','team','player_name','elo','hash'] if k in d][:6]
            parts = []
            for k in display_cols:
                v = d.get(k, '')
                if v or str(v) == '0':
                    parts.append(f'{k}={v}')
            print(f'  {", ".join(parts)}')
    except Exception as e:
        print(f'  No preview available: {e}')
        conn.close()


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='🔥 UNIFIED HARVESTER — Exploit all 24 football data sources')
    parser.add_argument('--sources', type=str, default=None,
                       help='Source numbers, comma-separated (e.g. "1,6,21") or "all"')
    parser.add_argument('--force', action='store_true', help='Force re-fetch cached data')
    parser.add_argument('--workers', type=int, default=4, help='Max parallel workers (default: 4)')
    parser.add_argument('--preview', type=int, default=None,
                       help='Show preview for a source table (rows)')
    parser.add_argument('--list', action='store_true', help='List all 24 sources')
    parser.add_argument('--single', type=int, default=None, help='Run a single source by number')
    parser.add_argument('--season', type=str, default=None, help='Season override for applicable sources')

    args = parser.parse_args()

    if args.list:
        print('\n' + '═' * 72)
        print('  🔥 UNIFIED HARVESTER — 24 SOURCES AVAILABLE')
        print('═' * 72)
        for num in sorted(SOURCE_REGISTRY.keys()):
            name, emoji, _ = SOURCE_REGISTRY[num]
            print(f'  {num:>2}. {emoji} {name}')
        print('═' * 72)
        sys.exit(0)

    if args.preview:
        show_preview(args.preview, limit=5)
        sys.exit(0)

    if args.single:
        result = run_source(args.single, force=args.force)
        print(json.dumps(result, indent=2, default=str))
        print(f'\n📋 Preview for source {args.single}:')
        show_preview(args.single, limit=5)
        sys.exit(0)

    # Determine which sources to run
    if args.sources and args.sources.lower() != 'all':
        sources = [int(s.strip()) for s in args.sources.split(',') if s.strip().isdigit()]
    else:
        sources = list(range(1, 25))

    _update_progress('UNIFIED_HARVESTER', '🚀 STARTING', f'Targeting {len(sources)} sources')

    results = run_all_sources(force=args.force, max_workers=args.workers, sources=sources)
    print_results(results)

    # Show previews for sources with data
    print('\n\n📋 DATA PREVIEWS (first 5 rows from each source with data):')
    for num in sorted(sources):
        if num in results and results[num].get('rows', 0) > 0:
            show_preview(num, limit=5)

    # Save results to JSON
    report_file = PROJECT_ROOT / 'unified_harvester_report.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        serializable = {}
        for k, v in results.items():
            if isinstance(v, dict):
                serializable[str(k)] = {kk: str(vv) if not isinstance(vv, (int, float, str, bool, type(None))) else vv
                                        for kk, vv in v.items()}
        json.dump(serializable, f, indent=2)
    print(f'\n📄 Full report saved to: {report_file}')
