#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓                      ETERNAL HARVESTER CONFIG                             ▓
▓  ALL sources, API keys, URLs, rate limits, proxy settings — unified       ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • WORM-AI💀🔥                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, json, time, sqlite3
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# ─── Project Root ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(PROJECT_ROOT / 'scrape_cache.db')
HARVESTERS_DIR = Path(__file__).resolve().parent
LOGS_DIR = HARVESTERS_DIR / 'harvest_logs'
CHECKPOINTS_DIR = HARVESTERS_DIR / 'checkpoints'
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CHECKPOINTS_DIR, exist_ok=True)

# ─── API Keys (loaded from .env with fallbacks) ─────────────────────────────
def _load_env() -> dict:
    """Load .env from project root. Returns dict of all key=value pairs."""
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
    return env

_env = _load_env()

# ─── API Keys Dict ──────────────────────────────────────────────────────────
API_KEYS: Dict[str, str] = {
    # football-data.co.uk (no key needed for CSVs)
    'football_data': '',
    # Understat (no key needed)
    'understat': '',
    # FBref (no key needed, but respect robots.txt)
    'fbref': '',
    # Transfermarkt (no key needed, but respect robots.txt)
    'transfermarkt': '',
    # Betfair API (free tier)
    'betfair': _env.get('BETFAIR_KEY', ''),
    # OddsPortal (no key needed, but heavy scraping protection)
    'oddsportal': '',
    # OpenWeatherMap (1000/day free tier)
    'openweathermap': _env.get('OPENWEATHERMAP_KEY', ''),
    # Flashscore (no key needed)
    'flashscore': '',
    # SportMonks (free tier — 100 req/month)
    'sportmonks': _env.get('SPORTMONKS_KEY', 'fTcgxXfqgyTxJ00ruM5SsGvdCcEPcFwhqXYGrKcpwy8A1IaORjujOxMEDsX0'),
    # Football-Data.org API
    'football_data_org': _env.get('FOOTBALL_DATA_API_KEY', 'c7d5c5c1b80d4ebe821a58b3087b968d'),
    # Odds API (The Odds API — 500 req/month free)
    'odds_api': _env.get('ODDS_API_KEY', '1aa4dd22f7ee80b8d03c654c064c4fce'),
    # API-SPORT (rapidapi)
    'api_sport': _env.get('API_SPORT_KEY', '2064edeecfd82a209e2dca203d5ac9b6'),
    # BSData / BSD API
    'bsd_api': _env.get('BSD_API_KEY', '37728ad7a9b501c47968df4fadc3e2757ab60384'),
}

# ─── Source Configs ─────────────────────────────────────────────────────────
@dataclass
class SourceConfig:
    """Configuration for a single data source."""
    name: str
    enabled: bool = True
    base_url: str = ''
    rate_limit_per_minute: int = 30
    concurrency: int = 3
    timeout: int = 120
    retry_max: int = 5
    retry_backoff_base: float = 2.0
    retry_jitter: float = 1.0
    cache_ttl_minutes: int = 60
    check_interval_hours: float = 6.0
    headers: Dict[str, str] = field(default_factory=lambda: {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/125.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/json,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    })


# ─── Football-Data.co.uk ────────────────────────────────────────────────────
FOOTBALL_DATA_CONFIG = SourceConfig(
    name='football_data_uk',
    base_url='https://www.football-data.co.uk',
    rate_limit_per_minute=60,
    concurrency=5,
    check_interval_hours=12.0,
)

# All leagues + codes for football-data.co.uk
FOOTBALL_DATA_LEAGUES: Dict[str, Dict[str, str]] = {
    'ENG': {
        'name': 'England',
        'leagues': {
            'E0': 'Premier League',
            'E1': 'Championship',
            'E2': 'League 1',
            'E3': 'League 2',
            'EC': 'Conference',
            'EC0': 'National League',
            'EC1': 'National League N/S',
        }
    },
    'SCO': {
        'name': 'Scotland',
        'leagues': {
            'SC0': 'Premiership',
            'SC1': 'Championship',
            'SC2': 'League 1',
            'SC3': 'League 2',
        }
    },
    'GER': {
        'name': 'Germany',
        'leagues': {
            'D1': 'Bundesliga 1',
            'D2': 'Bundesliga 2',
            'D3': 'Liga 3',
        }
    },
    'ITA': {
        'name': 'Italy',
        'leagues': {
            'I1': 'Serie A',
            'I2': 'Serie B',
        }
    },
    'SPA': {
        'name': 'Spain',
        'leagues': {
            'SP1': 'La Liga',
            'SP2': 'La Liga 2',
        }
    },
    'FRA': {
        'name': 'France',
        'leagues': {
            'F1': 'Ligue 1',
            'F2': 'Ligue 2',
        }
    },
    'NED': {
        'name': 'Netherlands',
        'leagues': {
            'N1': 'Eredivisie',
        }
    },
    'BEL': {
        'name': 'Belgium',
        'leagues': {
            'B1': 'Jupiler League',
        }
    },
    'POR': {
        'name': 'Portugal',
        'leagues': {
            'P1': 'Liga Portugal',
        }
    },
    'TUR': {
        'name': 'Turkey',
        'leagues': {
            'T1': 'Super Lig',
        }
    },
    'GRE': {
        'name': 'Greece',
        'leagues': {
            'G1': 'Super League',
        }
    },
    'AUT': {
        'name': 'Austria',
        'leagues': {
            'A1': 'Bundesliga',
        }
    },
    'SWI': {
        'name': 'Switzerland',
        'leagues': {
            'SW1': 'Challenge League',  # Actually Super League uses SWI sometimes
        }
    },
    'DEN': {
        'name': 'Denmark',
        'leagues': {
            'DK1': 'Superliga',
        }
    },
    'SWE': {
        'name': 'Sweden',
        'leagues': {
            'SE1': 'Allsvenskan',
        }
    },
    'NOR': {
        'name': 'Norway',
        'leagues': {
            'NO1': 'Eliteserien',
        }
    },
    'RUS': {
        'name': 'Russia',
        'leagues': {
            'RU1': 'Premier League',
        }
    },
    'POL': {
        'name': 'Poland',
        'leagues': {
            'PO1': 'Ekstraklasa',
        }
    },
    'CRO': {
        'name': 'Croatia',
        'leagues': {
            'CR1': 'HNL',
        }
    },
    'CZE': {
        'name': 'Czech Republic',
        'leagues': {
            'CZ1': 'First League',
        }
    },
    'ROM': {
        'name': 'Romania',
        'leagues': {
            'RO1': 'Liga I',
        }
    },
    'SRB': {
        'name': 'Serbia',
        'leagues': {
            'SB1': 'SuperLiga',
        }
    },
    'ARG': {
        'name': 'Argentina',
        'leagues': {
            'AR1': 'Primera Division',
        }
    },
    'BRA': {
        'name': 'Brazil',
        'leagues': {
            'BR1': 'Serie A',
            'BR2': 'Serie B',
        }
    },
    'MEX': {
        'name': 'Mexico',
        'leagues': {
            'MX1': 'Liga MX',
        }
    },
    'USA': {
        'name': 'USA',
        'leagues': {
            'MLS': 'MLS',
        }
    },
    'JPN': {
        'name': 'Japan',
        'leagues': {
            'J1': 'J-League',
            'J2': 'J2 League',
        }
    },
    'KOR': {
        'name': 'South Korea',
        'leagues': {
            'K1': 'K-League 1',
        }
    },
    'CHN': {
        'name': 'China',
        'leagues': {
            'C1': 'Chinese Super League',
        }
    },
    'AUS': {
        'name': 'Australia',
        'leagues': {
            'AU1': 'A-League',
        }
    },
    'SAU': {
        'name': 'Saudi Arabia',
        'leagues': {
            'SA1': 'Saudi Pro League',
        }
    },
}

FOOTBALL_DATA_SEASONS: List[str] = [
    '2425', '2324', '2223', '2122', '2021',
    '1920', '1819', '1718', '1617', '1516',
    '1415', '1314', '1213', '1112', '1011',
    '0910', '0809', '0708', '0607', '0506',
    '0405', '0304', '0203', '0102', '0001',
    '99100', '9899', '9798', '9697', '9596',
    '9495', '9394', '9293',
]

# ─── Understat ───────────────────────────────────────────────────────────────
UNDERSTAT_CONFIG = SourceConfig(
    name='understat',
    base_url='https://understat.com',
    rate_limit_per_minute=20,
    concurrency=2,
    timeout=90,
    retry_max=8,
)

UNDERSTAT_LEAGUES = {
    'EPL': 'Premier League',
    'La_liga': 'La Liga',
    'Bundesliga': 'Bundesliga',
    'Serie_A': 'Serie A',
    'Ligue_1': 'Ligue 1',
    'RFPL': 'Russian Premier League',
}

# ─── FBref ───────────────────────────────────────────────────────────────────
FBREF_CONFIG = SourceConfig(
    name='fbref',
    base_url='https://fbref.com',
    rate_limit_per_minute=15,  # Be gentle with FBref
    concurrency=1,
    timeout=120,
    retry_max=10,
    retry_backoff_base=4.0,
    check_interval_hours=24.0,
)

FBREF_TOP_LEAGUES = [
    'Premier-League',
    'La-Liga',
    'Bundesliga',
    'Serie-A',
    'Ligue-1',
    'Eredivisie',
    'Primeira-Liga',
    'Super-Lig',
    'Russian-Premier-League',
    'Scottish-Premiership',
    'Jupiler-Pro-League',
    'Raiffeisen-Super-League',
    'Allsvenskan',
    'Eliteserien',
    'Danish-Superliga',
    'Ekstraklasa',
    'Czech-First-League',
    'Liga-I',
    'Hrvatska-NL',
    'Austrian-Bundesliga',
    'Super-League-Greece',
    'Ukrainian-Premier-League',
    'Saudi-Professional-League',
    'Chinese-Super-League',
    'J1-League',
    'K-League-1',
    'A-League',
    'Brasileirao-Serie-A',
    'Primera-Division-Argentina',
    'Primera-Division-Chile',
    'Liga-MX',
    'MLS',
]

# ─── Transfermarkt ──────────────────────────────────────────────────────────
TRANSFERMARKT_CONFIG = SourceConfig(
    name='transfermarkt',
    base_url='https://www.transfermarkt.com',
    rate_limit_per_minute=10,  # Very strict with TM
    concurrency=1,
    timeout=90,
    retry_max=10,
    retry_backoff_base=5.0,
    check_interval_hours=24.0,
)

TRANSFERMARKT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
    'Referer': 'https://www.transfermarkt.com/',
    'DNT': '1',
}

# ─── Betfair ─────────────────────────────────────────────────────────────────
BETFAIR_CONFIG = SourceConfig(
    name='betfair',
    base_url='https://api.betfair.com/exchange/betting/rest/v1.0',
    rate_limit_per_minute=60,
    concurrency=2,
)

BETFAIR_APP_KEY = _env.get('BETFAIR_APP_KEY', '')
BETFAIR_USERNAME = _env.get('BETFAIR_USERNAME', '')
BETFAIR_PASSWORD = _env.get('BETFAIR_PASSWORD', '')

# ⚠ Cert required for Betfair API — store in PROJECT_ROOT/certs/
BETFAIR_CERT_PATH = str(PROJECT_ROOT / 'certs' / 'client-2048.p12')
BETFAIR_CERT_PASSWORD = _env.get('BETFAIR_CERT_PASSWORD', '')

# ─── OddsPortal ──────────────────────────────────────────────────────────────
ODDSPORTAL_CONFIG = SourceConfig(
    name='oddsportal',
    base_url='https://www.oddsportal.com',
    rate_limit_per_minute=8,
    concurrency=1,
    timeout=90,
    retry_max=10,
    retry_backoff_base=3.0,
    check_interval_hours=12.0,
)

# ─── OpenWeatherMap ──────────────────────────────────────────────────────────
OPENWEATHERMAP_CONFIG = SourceConfig(
    name='openweathermap',
    base_url='https://api.openweathermap.org/data/2.5',
    rate_limit_per_minute=60,
    concurrency=3,
    timeout=30,
)

# ─── Flashscore ──────────────────────────────────────────────────────────────
FLASHSCORE_CONFIG = SourceConfig(
    name='flashscore',
    base_url='https://www.flashscore.com',
    rate_limit_per_minute=20,
    concurrency=2,
    timeout=60,
    retry_max=8,
)

# ─── Proxy Configuration ────────────────────────────────────────────────────
PROXY_CONFIG = {
    'enabled': False,  # Set to True to use proxies (disabled for speed)
    'free_proxy_urls': [
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt',
        'https://raw.githubusercontent.com/scriptzteam/Proxy-List/master/http.txt',
        'https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=10000&country=all',
        'https://www.proxy-list.download/api/v1/get?type=http',
    ],
    'test_url': 'https://httpbin.org/ip',
    'test_timeout': 3,
    'min_proxies': 3,
    'max_proxies': 30,
    'rotation_interval_seconds': 300,
    'ban_threshold': 3,  # Ban proxy after this many failures
    'country_whitelist': [],  # Empty = all countries
}

# ─── Database ────────────────────────────────────────────────────────────────
DB_TABLES_META = {
    'harvester_checkpoints': '''
        CREATE TABLE IF NOT EXISTS harvester_checkpoints (
            source TEXT PRIMARY KEY,
            checkpoint_data TEXT,
            last_run REAL,
            status TEXT DEFAULT 'idle',
            records_fetched INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            duration_seconds REAL DEFAULT 0.0
        )
    ''',
    'harvester_log': '''
        CREATE TABLE IF NOT EXISTS harvester_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            level TEXT DEFAULT 'INFO',
            message TEXT,
            details TEXT,
            timestamp REAL DEFAULT (strftime('%s','now'))
        )
    ''',
}


# ─── Rate Limiter ───────────────────────────────────────────────────────────
class RateLimiter:
    """Token-bucket rate limiter per source."""
    def __init__(self, rate_per_minute: int):
        self.rate = rate_per_minute
        self.tokens = rate_per_minute
        self.last_refill = time.time()
        self.max_tokens = rate_per_minute

    def acquire(self) -> float:
        """Wait for a token. Returns wait time in seconds."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * (self.rate / 60.0))
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0

        wait = (1.0 - self.tokens) * (60.0 / self.rate)
        self.tokens = 0.0
        return max(0.0, wait)

    def __enter__(self):
        wait = self.acquire()
        if wait > 0:
            time.sleep(wait)
        return self

    def __exit__(self, *args):
        pass


# ─── Rate limiter instances ─────────────────────────────────────────────────
RATE_LIMITERS: Dict[str, RateLimiter] = {}

def get_rate_limiter(name: str, rate: Optional[int] = None) -> RateLimiter:
    """Get or create a rate limiter for a named source."""
    if name not in RATE_LIMITERS:
        r = rate or globals().get(f'{name.upper()}_CONFIG', SourceConfig(name=name)).rate_limit_per_minute
        RATE_LIMITERS[name] = RateLimiter(r)
    return RATE_LIMITERS[name]


# ─── Source registry ─────────────────────────────────────────────────────────
ALL_SOURCES = {
    'football_data_uk': FOOTBALL_DATA_CONFIG,
    'understat': UNDERSTAT_CONFIG,
    'fbref': FBREF_CONFIG,
    'transfermarkt': TRANSFERMARKT_CONFIG,
    'betfair': BETFAIR_CONFIG,
    'oddsportal': ODDSPORTAL_CONFIG,
    'openweathermap': OPENWEATHERMAP_CONFIG,
    'flashscore': FLASHSCORE_CONFIG,
}


def get_source_config(name: str) -> SourceConfig:
    """Get config for a named source."""
    return ALL_SOURCES.get(name, SourceConfig(name=name))


def get_db() -> sqlite3.Connection:
    """Get a database connection with WAL mode."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def init_checkpoint_tables():
    """Ensure checkpoint tables exist."""
    conn = get_db()
    for table_ddl in DB_TABLES_META.values():
        conn.execute(table_ddl)
    conn.commit()
    conn.close()


def save_checkpoint(source: str, data: dict, records_fetched: int = 0, errors: int = 0):
    """Save a checkpoint for a harvester source."""
    conn = get_db()
    now = time.time()
    conn.execute('''
        INSERT INTO harvester_checkpoints (source, checkpoint_data, last_run, status, records_fetched, errors)
        VALUES (?, ?, ?, 'completed', ?, ?)
        ON CONFLICT(source) DO UPDATE SET
            checkpoint_data = excluded.checkpoint_data,
            last_run = excluded.last_run,
            status = 'completed',
            records_fetched = harvester_checkpoints.records_fetched + excluded.records_fetched,
            errors = harvester_checkpoints.errors + excluded.errors
    ''', (source, json.dumps(data), now, records_fetched, errors))
    conn.commit()
    conn.close()


def load_checkpoint(source: str) -> Optional[dict]:
    """Load a checkpoint for a harvester source."""
    conn = get_db()
    row = conn.execute(
        'SELECT checkpoint_data, last_run FROM harvester_checkpoints WHERE source = ?',
        (source,)
    ).fetchone()
    conn.close()
    if row:
        return {'data': json.loads(row[0]), 'last_run': row[1]}
    return None


def log_event(source: str, level: str, message: str, details: str = ''):
    """Log an event to the harvester_log table."""
    conn = get_db()
    conn.execute(
        'INSERT INTO harvester_log (source, level, message, details) VALUES (?, ?, ?, ?)',
        (source, level, message, details[:1000])
    )
    conn.commit()
    conn.close()


# ─── Init on import ─────────────────────────────────────────────────────────
init_checkpoint_tables()
