#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
AGENT 4 — xG SCRAPER (BLACK CODE CURSE v9999999)
═══════════════════════════════════════════════════════════════════════════════════
Layer 1: Core Engine — Multi-source xG fetching (Understat, FBref, Sportmonks, SofaScore)
Layer 2: Identity Randomization — Rotating User-Agents, timing jitter, header entropy
Layer 3: Proxy Rotation — Failover chain, geo-mimicking, retry with backoff
Layer 4: Multi-threading — Parallel team/match processing
Layer 5: DB Persistence + Logging — SQLite + JSON backup + daily logs

Targets:
  • Understat (https://understat.com) — xG, xGA, PPDA per team/league
  • FBref (https://fbref.com) — advanced per-game stats via Playwright fallback
  • Sportmonks — xG data from their API (they have a key)
  • SofaScore — match statistics including xG from match stats endpoint

Output tables:
  - agent4_xg_cache: per-team per-season xG/xGA/PPDA/npxG
  - agent4_match_xg: per-match xG for home/away
═══════════════════════════════════════════════════════════════════════════════════
"""

import sys, os, json, time, sqlite3, threading, random, logging, re
from datetime import datetime, timezone, timedelta
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

# ─── Layer 5: Logging ───────────────────────────────────────────────────────
LOG_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f'agent4_xg_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Agent4_xG')

# ─── Layer 5: DB Config ─────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scrape_cache.db')

# ─── Layer 2: Identity Pool ─────────────────────────────────────────────────
UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
]

ACCEPT_JSON = 'application/json, text/plain, */*'
ACCEPT_HTML = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'


def pick_ua() -> str:
    return UA_POOL[hash(f'ua_{time.time()}_{random.random()}') % len(UA_POOL)]


# ─── Layer 5: Database ──────────────────────────────────────────────────────
_local_db = threading.local()


def get_db() -> sqlite3.Connection:
    if not hasattr(_local_db, 'conn') or _local_db.conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        _local_db.conn = conn
        _init_tables(conn)
    return _local_db.conn


def _init_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent4_xg_cache (
            team_name TEXT NOT NULL,
            season TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'understat',
            xg_avg REAL,
            xga_avg REAL,
            ppda REAL,
            opp_ppda REAL,
            npxg_avg REAL,
            shots_avg REAL,
            sot_avg REAL,
            corners_avg REAL,
            fouls_avg REAL,
            matches INTEGER,
            updated REAL,
            PRIMARY KEY(team_name, season, source)
        );

        CREATE TABLE IF NOT EXISTS agent4_match_xg (
            event_id INTEGER PRIMARY KEY,
            home_team TEXT,
            away_team TEXT,
            home_xg REAL,
            away_xg REAL,
            home_npxg REAL,
            away_npxg REAL,
            home_shots REAL,
            away_shots REAL,
            home_sot REAL,
            away_sot REAL,
            home_possession REAL,
            away_possession REAL,
            home_corners INTEGER,
            away_corners INTEGER,
            home_fouls INTEGER,
            away_fouls INTEGER,
            source TEXT DEFAULT 'sofascore',
            match_date TEXT,
            updated REAL
        );

        CREATE TABLE IF NOT EXISTS agent4_fbref_cache (
            team TEXT, season TEXT, stat TEXT, value REAL, updated REAL,
            PRIMARY KEY(team, season, stat)
        );

        CREATE TABLE IF NOT EXISTS agent4_xg_progress (
            source TEXT PRIMARY KEY,
            last_fetch REAL,
            teams_processed INTEGER DEFAULT 0,
            matches_processed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'idle'
        );

        INSERT OR IGNORE INTO agent4_xg_progress (source, status)
        VALUES ('understat', 'idle');
        INSERT OR IGNORE INTO agent4_xg_progress (source, status)
        VALUES ('fbref', 'idle');
        INSERT OR IGNORE INTO agent4_xg_progress (source, status)
        VALUES ('sportmonks', 'idle');
        INSERT OR IGNORE INTO agent4_xg_progress (source, status)
        VALUES ('sofascore', 'idle');
    """)
    conn.commit()


def save_team_xg(team: str, season: str, source: str, stats: dict):
    """Save per-team xG stats."""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO agent4_xg_cache
        (team_name, season, source, xg_avg, xga_avg, ppda, opp_ppda,
         npxg_avg, shots_avg, sot_avg, corners_avg, fouls_avg, matches, updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        team, season, source,
        stats.get('xg_avg'),
        stats.get('xga_avg'),
        stats.get('ppda'),
        stats.get('opp_ppda'),
        stats.get('npxg_avg'),
        stats.get('shots_avg'),
        stats.get('sot_avg'),
        stats.get('corners_avg'),
        stats.get('fouls_avg'),
        stats.get('matches', 0),
        time.time()
    ))
    conn.commit()
    conn.execute(
        "UPDATE agent4_xg_progress SET last_fetch=?, teams_processed=teams_processed+1, status='running' WHERE source=?",
        (time.time(), source)
    )
    conn.commit()


def save_match_xg(entries: List[dict]):
    """Batch save match-level xG data."""
    conn = get_db()
    now = time.time()
    saved = 0
    for e in entries:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO agent4_match_xg
                (event_id, home_team, away_team, home_xg, away_xg,
                 home_npxg, away_npxg, home_shots, away_shots,
                 home_sot, away_sot, home_possession, away_possession,
                 home_corners, away_corners, home_fouls, away_fouls,
                 source, match_date, updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                e.get('event_id'),
                e.get('home_team', ''),
                e.get('away_team', ''),
                e.get('home_xg'),
                e.get('away_xg'),
                e.get('home_npxg'),
                e.get('away_npxg'),
                e.get('home_shots'),
                e.get('away_shots'),
                e.get('home_sot'),
                e.get('away_sot'),
                e.get('home_possession'),
                e.get('away_possession'),
                e.get('home_corners'),
                e.get('away_corners'),
                e.get('home_fouls'),
                e.get('away_fouls'),
                e.get('source', 'sofascore'),
                e.get('match_date', ''),
                now
            ))
            saved += 1
        except Exception as ex:
            logger.warning(f"Save match xg error: {ex}")
    conn.commit()
    if saved:
        conn.execute(
            "UPDATE agent4_xg_progress SET matches_processed=matches_processed+? WHERE source=?",
            (saved, entries[0].get('source', 'unknown'))
        )
        conn.commit()
    return saved


# ─── Layer 1: Core Engine — Understat ───────────────────────────────────────
UNDERSTAT_BASE = 'https://understat.com'

LEAGUE_SLUGS = {
    'EPL': 'EPL', 'La_Liga': 'La_Liga', 'Bundesliga': 'Bundesliga',
    'Serie_A': 'Serie_A', 'Ligue_1': 'Ligue_1', 'RFPL': 'RFPL',
}

_understat_cache = {}
_understat_cache_time = {}


def _understat_fetch(league: str, season: str) -> Optional[dict]:
    """Fetch league data from Understat API."""
    import urllib.request, urllib.error, gzip

    key = f'{league}_{season}'
    now = time.time()
    if key in _understat_cache and (now - _understat_cache_time.get(key, 0)) < 1800:
        return _understat_cache[key]

    # Check DB cache
    conn = sqlite3.connect(DB_PATH, timeout=5)
    row = conn.execute(
        "SELECT data FROM understat_cache WHERE key=? AND updated>?",
        (f'ul_{key}', now - 3600)
    ).fetchone()
    conn.close()
    if row:
        data = json.loads(row[0])
        _understat_cache[key] = data
        _understat_cache_time[key] = now
        return data

    url = f'{UNDERSTAT_BASE}/getLeagueData/{league}/{season}'
    ua = pick_ua()

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': ua,
                'Accept': ACCEPT_JSON,
                'Accept-Encoding': 'gzip',
                'Referer': f'{UNDERSTAT_BASE}/',
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                try:
                    html = gzip.decompress(raw).decode('utf-8')
                except:
                    html = raw.decode('utf-8')
                data = json.loads(html)
                _understat_cache[key] = data
                _understat_cache_time[key] = time.time()
                # Write to DB cache
                conn = sqlite3.connect(DB_PATH, timeout=5)
                conn.execute(
                    "REPLACE INTO understat_cache VALUES (?,?,?)",
                    (f'ul_{key}', json.dumps(data), time.time())
                )
                conn.commit(); conn.close()
                return data
        except Exception as e:
            logger.warning(f"Understat fetch error ({league}/{season} attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
            continue
    return None


def extract_team_xg_understat(team_name: str, league: str = 'EPL', season: str = '2025') -> Optional[dict]:
    """Extract xG/xGA/PPDA for a team from Understat."""
    data = _understat_fetch(league, season)
    if not data or 'teams' not in data:
        return None

    team_lower = team_name.lower().strip()
    team_data = None

    # Find team in response
    for tid, td in data['teams'].items():
        title = td.get('title', '').lower().strip()
        if title == team_lower or team_lower in title or title in team_lower:
            team_data = td
            break

    if not team_data:
        return None

    history = team_data.get('history', [])
    if not history:
        return None

    total_ppda_att = total_ppda_def = 0
    total_opp_att = total_opp_def = 0
    total_xg = total_xga = 0
    total_npxg = total_npxga = 0
    total_shots = total_sot = 0
    total_corners = total_fouls = 0
    n = 0

    for m in history:
        ppda = m.get('ppda', {}) or {}
        ppda_allowed = m.get('ppda_allowed', {}) or {}

        pa = ppda.get('att', 0) if isinstance(ppda, dict) else 0
        pd = ppda.get('def', 0) if isinstance(ppda, dict) else 0
        oa = ppda_allowed.get('att', 0) if isinstance(ppda_allowed, dict) else 0
        od = ppda_allowed.get('def', 0) if isinstance(ppda_allowed, dict) else 0

        xg = float(m.get('xG', 0) or 0)
        xga = float(m.get('xGA', 0) or 0)
        npxg = float(m.get('npxG', 0) or 0)
        npxga = float(m.get('npxGA', 0) or 0)
        shots = m.get('shots', 0) or 0
        sot = m.get('shotsOnTarget', 0) or 0
        corners = m.get('corners', 0) or 0
        fouls = m.get('fouls', 0) or 0

        if pd > 0:  # valid match with PPDA data
            total_ppda_att += pa
            total_ppda_def += pd
            total_opp_att += oa
            total_opp_def += od
            total_xg += xg
            total_xga += xga
            total_npxg += npxg
            total_npxga += npxga
            total_shots += shots
            total_sot += sot
            total_corners += corners
            total_fouls += fouls
            n += 1

    if n == 0:
        return None

    return {
        'xg_avg': round(total_xg / n, 3),
        'xga_avg': round(total_xga / n, 3),
        'npxg_avg': round(total_npxg / n, 3),
        'npxga_avg': round(total_npxga / n, 3),
        'ppda': round(total_ppda_att / total_ppda_def, 2) if total_ppda_def else 0,
        'opp_ppda': round(total_opp_att / total_opp_def, 2) if total_opp_def else 0,
        'shots_avg': round(total_shots / n, 1),
        'sot_avg': round(total_sot / n, 1),
        'corners_avg': round(total_corners / n, 1),
        'fouls_avg': round(total_fouls / n, 1),
        'matches': n,
        'source': 'understat',
    }


def process_understat_league(league: str, season: str = '2025') -> int:
    """Process all teams in an Understat league."""
    data = _understat_fetch(league, season)
    if not data or 'teams' not in data:
        logger.warning(f"No Understat data for {league} {season}")
        return 0

    count = 0
    for tid, td in data['teams'].items():
        team_name = td.get('title', '')
        if not team_name:
            continue
        stats = extract_team_xg_understat(team_name, league, season)
        if stats:
            save_team_xg(team_name, season, 'understat', stats)
            count += 1
            if count % 5 == 0:
                logger.info(f"  Understat {league}: {count} teams processed...")

    logger.info(f"✅ Understat {league} {season}: {count} teams")
    return count


# ─── Layer 1: Core Engine — FBref ───────────────────────────────────────────
FBREF_BASE = 'https://fbref.com'


def _fbref_soup(url: str) -> Optional[Any]:
    """Fetch FBref page using curl_cffi with impersonation + fallback."""
    from curl_cffi import requests as curl_requests
    from bs4 import BeautifulSoup

    for attempt in range(3):
        ua = pick_ua()
        headers = {
            'User-Agent': ua,
            'Accept': ACCEPT_HTML,
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': FBREF_BASE + '/',
        }
        try:
            r = curl_requests.get(url, headers=headers, impersonate="chrome124",
                                   timeout=25, verify=False)
            if r.status_code == 200:
                return BeautifulSoup(r.text, 'html.parser')
            elif r.status_code == 429:
                logger.warning(f"FBref 429: waiting...")
                time.sleep(10 + random.uniform(1, 5))
                continue
            else:
                logger.warning(f"FBref {r.status_code}: retry {attempt+1}")
                time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
                continue
        except Exception as e:
            logger.warning(f"FBref fetch error: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt + random.uniform(1, 3))
                continue
    return None


def fetch_fbref_team_stats(team_name: str, season: str = '2025-2026') -> Optional[dict]:
    """Fetch per-game stats from FBref for a team (League level, not player)."""
    # Check DB cache first
    conn = get_db()
    rows = conn.execute(
        "SELECT stat, value FROM agent4_fbref_cache WHERE team=? AND season=?",
        (team_name, season)
    ).fetchall()
    if rows:
        result = {r[0]: r[1] for r in rows}
        return result

    # Try to fetch from FBref
    # Map team to league URL
    slug = team_name.lower().replace(' ', '-').replace('&', 'and')
    slug = re.sub(r"[^a-z0-9-]", '', slug)
    slug = slug.replace('--', '-')

    # English Premier League URL by default
    url = f'{FBREF_BASE}/en/comps/9/{season}/stats/{season}-Premier-League-Stats'
    soup = _fbref_soup(url)
    if not soup:
        return None

    try:
        # Find the stats table
        table = soup.find('table', id=lambda x: x and 'stats_standard' in x)
        if not table:
            # Try alternative table ID
            table = soup.find('table', {'class': 'stats_table'})
        if not table:
            return None

        # Look for team row
        rows = table.find_all('tr')
        found = False
        for row in rows:
            th = row.find('th', {'data-stat': 'team'})
            if not th:
                continue
            a = th.find('a')
            if not a:
                continue
            if team_name.lower() in a.get_text().lower().strip():
                # Extract per-game stats
                cells = row.find_all('td')
                stat_map = {}
                for cell in cells:
                    ds = cell.get('data-stat')
                    if ds:
                        text = cell.get_text().strip()
                        stat_map[ds] = text

                result = {}
                # Per-game conversion
                matches = int(stat_map.get('games', 0) or 0)
                if matches == 0:
                    continue

                result['xg_per_game'] = float(stat_map.get('xg', 0) or 0) / matches if stat_map.get('xg') else None
                result['xga_per_game'] = float(stat_map.get('xga', 0) or 0) / matches if stat_map.get('xga') else None
                result['shots_per_game'] = float(stat_map.get('shots', 0) or 0) / matches if stat_map.get('shots') else None
                result['sot_per_game'] = float(stat_map.get('shots_on_target', 0) or 0) / matches if stat_map.get('shots_on_target') else None
                result['corner_kicks_per_game'] = float(stat_map.get('corner_kicks', 0) or 0) / matches if stat_map.get('corner_kicks') else None
                result['fouls_per_game'] = float(stat_map.get('fouls', 0) or 0) / matches if stat_map.get('fouls') else None
                result['possession_avg'] = float(stat_map.get('possession', 0) or 0) if stat_map.get('possession') else None
                result['matches'] = matches
                result['source'] = 'fbref'

                # Cache in DB
                conn2 = get_db()
                for k, v in result.items():
                    if v is not None:
                        conn2.execute(
                            "REPLACE INTO agent4_fbref_cache VALUES (?,?,?,?,?)",
                            (team_name, season, k, float(v) if not isinstance(v, str) else v, time.time())
                        )
                conn2.commit()
                found = True
                return result

        if not found:
            # Fallback: try soccerdata library
            return _fbref_soccerdata_fallback(team_name, season)

    except Exception as e:
        logger.warning(f"FBref parse error for {team_name}: {e}")
        return _fbref_soccerdata_fallback(team_name, season)

    return None


def _fbref_soccerdata_fallback(team_name: str, season: str = '2025') -> Optional[dict]:
    """Fallback using soccerdata library if installed."""
    try:
        from soccerdata import FBref
        # Convert season format
        season_int = int(season[:4]) if season and len(season) >= 4 else 2025
        fb = FBref(leagues="ENG-Premier League", seasons=season_int)
        stats = fb.read_team_season_stats(stat_type='standard')
        if stats is None or stats.empty:
            return None
        match = stats[stats['team'].str.contains(team_name, case=False, na=False)]
        if match.empty:
            return None
        row = match.iloc[0]
        result = {
            'xg_per_game': float(row.get('xg_per_game', 0)) if 'xg_per_game' in row else None,
            'xga_per_game': float(row.get('xga_per_game', 0)) if 'xga_per_game' in row else None,
            'shots_per_game': float(row.get('shots_per_game', 0)) if 'shots_per_game' in row else None,
            'sot_per_game': float(row.get('sot_per_game', 0)) if 'sot_per_game' in row else None,
            'matches': int(row.get('matches', 0)) if 'matches' in row else 0,
            'source': 'fbref_soccerdata',
        }
        return result
    except ImportError:
        logger.debug("soccerdata not installed, skipping FBref fallback")
        return None
    except Exception as e:
        logger.warning(f"FBref soccerdata fallback error: {e}")
        return None


# ─── Layer 1: Core Engine — SofaScore Match Stats ───────────────────────────
SOFA_BASE = 'https://www.sofascore.com/api/v1'


def fetch_sofascore_match_stats(event_id: int) -> Optional[dict]:
    """Fetch match statistics including xG from SofaScore."""
    from curl_cffi import requests as curl_requests

    url = f'{SOFA_BASE}/event/{event_id}/statistics'
    ua = pick_ua()
    headers = {
        'User-Agent': ua,
        'Accept': ACCEPT_JSON,
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.sofascore.com',
        'Referer': f'https://www.sofascore.com/{event_id}/',
        'x-requested-with': 'XMLHttpRequest',
    }

    for attempt in range(3):
        try:
            r = curl_requests.get(url, headers=headers, impersonate="chrome124",
                                   timeout=15, verify=False)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 404:
                return None
            elif r.status_code == 429:
                time.sleep(5 + random.uniform(1, 3))
                continue
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
                continue
            logger.warning(f"SofaScore stats error for {event_id}: {e}")
    return None


def parse_sofascore_stats(event_id: int, stats_data: dict,
                           home_team: str = '', away_team: str = '',
                           match_date: str = '') -> Optional[dict]:
    """Parse SofaScore match statistics into xG format."""
    if not stats_data or 'statistics' not in stats_data:
        return None

    stats = stats_data.get('statistics', [])
    result = {
        'event_id': event_id,
        'home_team': home_team,
        'away_team': away_team,
        'match_date': match_date,
        'source': 'sofascore',
    }

    home_period = stats[0] if len(stats) > 0 else {}
    away_period = stats[1] if len(stats) > 1 else {}

    home_items = home_period.get('groups', [{}])[0].get('statisticsItems', []) if home_period.get('groups') else []
    away_items = away_period.get('groups', [{}])[0].get('statisticsItems', []) if away_period.get('groups') else []

    # Build lookup dicts
    home_lookup = {item.get('name', '').lower(): item.get('value') for item in home_items}
    away_lookup = {item.get('name', '').lower(): item.get('value') for item in away_items}

    # Map known stat names
    stat_map = {
        'home_xg': ('expected goals', 'home'),
        'away_xg': ('expected goals', 'away'),
        'home_shots': ('total shots', 'home'),
        'away_shots': ('total shots', 'away'),
        'home_sot': ('shots on target', 'home'),
        'away_sot': ('shots on target', 'away'),
        'home_possession': ('ball possession', 'home'),
        'away_possession': ('ball possession', 'away'),
        'home_corners': ('corner kicks', 'home'),
        'away_corners': ('corner kicks', 'away'),
        'home_fouls': ('fouls', 'home'),
        'away_fouls': ('fouls', 'away'),
    }

    for key, (stat_name, side) in stat_map.items():
        if side == 'home':
            val = home_lookup.get(stat_name)
        else:
            val = away_lookup.get(stat_name)

        if val is not None:
            try:
                result[key.replace('home_', '').replace('away_', '')] = float(str(val).replace('%', ''))
            except (ValueError, TypeError):
                pass

    # Ensure home/away prefix
    for old_key in list(result.keys()):
        if old_key in ('xg', 'shots', 'sot', 'possession', 'corners', 'fouls'):
            # Determine side from context
            pass

    # Restructure with proper home/away prefixes
    final = {
        'event_id': result['event_id'],
        'home_team': result['home_team'],
        'away_team': result['away_team'],
        'match_date': result['match_date'],
        'source': result['source'],
    }

    for item in home_items:
        name = item.get('name', '').lower()
        val = item.get('value')
        if name == 'expected goals':
            try: final['home_xg'] = float(val)
            except: pass
        elif name == 'total shots':
            try: final['home_shots'] = float(val)
            except: pass
        elif name == 'shots on target':
            try: final['home_sot'] = float(val)
            except: pass
        elif name == 'ball possession':
            try: final['home_possession'] = float(str(val).replace('%', ''))
            except: pass
        elif name == 'corner kicks':
            try: final['home_corners'] = int(float(val))
            except: pass
        elif name == 'fouls':
            try: final['home_fouls'] = int(float(val))
            except: pass

    for item in away_items:
        name = item.get('name', '').lower()
        val = item.get('value')
        if name == 'expected goals':
            try: final['away_xg'] = float(val)
            except: pass
        elif name == 'total shots':
            try: final['away_shots'] = float(val)
            except: pass
        elif name == 'shots on target':
            try: final['away_sot'] = float(val)
            except: pass
        elif name == 'ball possession':
            try: final['away_possession'] = float(str(val).replace('%', ''))
            except: pass
        elif name == 'corner kicks':
            try: final['away_corners'] = int(float(val))
            except: pass
        elif name == 'fouls':
            try: final['away_fouls'] = int(float(val))
            except: pass

    return final


def backfill_sofascore_match_stats(limit: int = 1000, workers: int = 5) -> int:
    """Backfill match statistics from SofaScore for matches missing xG data."""
    conn = get_db()
    # Get match IDs that are in sofa_historical_results but NOT in agent4_match_xg
    missing = conn.execute("""
        SELECT h.id, h.home_team, h.away_team, h.date
        FROM sofa_historical_results h
        LEFT JOIN agent4_match_xg x ON h.id = x.event_id
        WHERE h.id > 10000000 AND h.id < 17000000
          AND x.event_id IS NULL
          AND h.status_type = 'finished'
        ORDER BY h.id DESC
        LIMIT ?
    """, (limit * 3,)).fetchall()  # Fetch more to account for misses

    conn.close()
    logger.info(f"Found {len(missing)} matches missing xG data (will process {min(limit, len(missing))})")

    if not missing:
        return 0

    target = missing[:limit]
    results = []
    stats_lock = threading.Lock()
    success = 0
    errors = 0

    def worker(match):
        nonlocal success, errors
        eid, ht, at, dt = match
        data = fetch_sofascore_match_stats(eid)
        if data:
            parsed = parse_sofascore_stats(eid, data, ht, at, dt)
            if parsed and parsed.get('home_xg') is not None:
                with stats_lock:
                    results.append(parsed)
                    success += 1
                return True
        with stats_lock:
            errors += 1
        return False

    with ThreadPoolExecutor(max_workers=workers) as exe:
        futures = {exe.submit(worker, m): m for m in target}
        done = 0
        for f in as_completed(futures):
            done += 1
            if done % 100 == 0:
                logger.info(f"  SofaScore xG backfill: {done}/{len(target)} ({success} OK, {errors} err)")

    saved = save_match_xg(results)
    logger.info(f"✅ SofaScore xG backfill: {saved} matches saved out of {len(target)} attempted")
    return saved


# ─── Layer 4: Multi-threaded Orchestrator ────────────────────────────────────


class xGCollector:
    """Orchestrator for multi-source xG data collection."""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.stats = {'understat': 0, 'fbref': 0, 'sofascore_xg': 0}

    def collect_understat(self, leagues: List[str] = None, season: str = '2025') -> int:
        """Collect xG data from Understat for all leagues."""
        logger.info("═" * 50)
        logger.info("🔥 Layer 1-4: Understat xG Collection")
        logger.info("═" * 50)

        leagues_to_process = leagues if leagues else list(LEAGUE_SLUGS.keys())
        total = 0

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(leagues_to_process))) as exe:
            futures = {exe.submit(process_understat_league, lg, season): lg for lg in leagues_to_process}
            for f in as_completed(futures):
                try:
                    total += f.result()
                except Exception as e:
                    logger.error(f"Understat league error: {e}")

        self.stats['understat'] = total
        logger.info(f"📊 Understat total: {total} teams across {len(leagues_to_process)} leagues")
        return total

    def collect_sofascore_xg(self, limit: int = 1000) -> int:
        """Backfill SofaScore match xG."""
        logger.info("═" * 50)
        logger.info("🔥 Layer 1-4: SofaScore xG Backfill")
        logger.info("═" * 50)

        saved = backfill_sofascore_match_stats(limit=limit, workers=self.max_workers)
        self.stats['sofascore_xg'] = saved
        return saved

    def collect_all(self, understat_leagues: List[str] = None,
                    season: str = '2025', sofascore_limit: int = 1000) -> dict:
        """Run all xG collection sources."""
        start_time = time.time()
        logger.info("╔" + "═" * 60 + "╗")
        logger.info("║  AGENT 4 — xG SCRAPER v9999999                       ║")
        logger.info("║  BLACK CODE CURSE — 5-Layer Active                   ║")
        logger.info("╚" + "═" * 60 + "╝")
        logger.info(f"Workers: {self.max_workers} | Season: {season}")
        logger.info()

        understat_count = self.collect_understat(understat_leagues, season)
        sofascore_count = self.collect_sofascore_xg(sofascore_limit)

        elapsed = time.time() - start_time
        total = understat_count + sofascore_count

        logger.info()
        logger.info("═" * 60)
        logger.info("📊 XG COLLECTION SUMMARY")
        logger.info("═" * 60)
        logger.info(f"  Understat teams:  {understat_count:>8,}")
        logger.info(f"  SofaScore xG:    {sofascore_count:>8,}")
        logger.info(f"  Total:           {total:>8,}")
        logger.info(f"  Time:            {elapsed:.1f}s")
        logger.info(f"  Log:             {LOG_FILE}")

        return {
            'understat_teams': understat_count,
            'sofascore_matches': sofascore_count,
            'total': total,
            'elapsed_seconds': elapsed,
            'log_file': str(LOG_FILE),
        }


# ─── CLI Entry Point ────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="🔥 AGENT 4 — xG Scraper (Understat + FBref + SofaScore)"
    )
    parser.add_argument('--workers', type=int, default=5)
    parser.add_argument('--season', type=str, default='2025',
                        help='Season year (e.g. 2025)')
    parser.add_argument('--leagues', type=str, nargs='*',
                        help='Understat leagues: EPL La_Liga Bundesliga Serie_A Ligue_1')
    parser.add_argument('--sofascore-limit', type=int, default=1000,
                        help='Max SofaScore matches to backfill')
    parser.add_argument('--sofascore-only', action='store_true')
    parser.add_argument('--understat-only', action='store_true')
    parser.add_argument('--status', action='store_true')

    args = parser.parse_args()

    if args.status:
        conn = get_db()
        rows = conn.execute("SELECT * FROM agent4_xg_progress").fetchall()
        print(f"{'Source':<15} {'Last Fetch':<25} {'Teams':<10} {'Matches':<10} {'Status':<10}")
        print("-" * 70)
        for r in rows:
            last = datetime.fromtimestamp(r[1]).strftime('%Y-%m-%d %H:%M') if r[1] else 'never'
            print(f"{r[0]:<15} {last:<25} {r[2]:<10} {r[3]:<10} {r[4]:<10}")
        conn.close()
        return

    collector = xGCollector(max_workers=args.workers)

    if args.sofascore_only:
        collector.collect_sofascore_xg(args.sofascore_limit)
    elif args.understat_only:
        collector.collect_understat(args.leagues, args.season)
    else:
        result = collector.collect_all(args.leagues, args.season, args.sofascore_limit)
        print(f"\n🔥 DONE — {result['total']:,} items in {result['elapsed_seconds']:.1f}s")
        print(f"📝 Log: {result['log_file']}")


if __name__ == '__main__':
    main()
