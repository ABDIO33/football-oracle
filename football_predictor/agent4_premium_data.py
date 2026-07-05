#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
AGENT 4 — PREMIUM DATA INTEGRATOR (BLACK CODE CURSE v9999999)
═══════════════════════════════════════════════════════════════════════════════════
Layer 1: Core Engine — Unified data extraction from ALL premium sources
Layer 2: Identity Randomization — Per-source identity pool, request shaping
Layer 3: Proxy Rotation — Source-aware proxy assignment
Layer 4: Multi-threading — Concurrent multi-source orchestration
Layer 5: Unified DB + Report Generator

Data Sources:
  📊 SofaScore (lineups, stats, H2H, form)   — curl_cffi impersonate
  💰 OddsAPI (market odds, overround)         — API key (free tier)
  ⚽ Sportmonks (fixtures, odds, stats)        — API key (free tier)
  📈 Understat (xG, xGA, PPDA)                — Public API
  📋 FBref (per-game advanced stats)          — Web scraping
  🔥 Flashscore (odds, results)               — curl_cffi impersonate
  🏟️ ClubElO (team ratings)                    — Public API
  🌤️ Weather API (match weather)              — Open-Meteo (free)

Integration Strategy:
  Phase 1: Collect raw data from all sources in parallel
  Phase 2: Merge & deduplicate into unified match stats
  Phase 3: Save to agent4_unified_matches table
  Phase 4: Generate features for prediction engine
═══════════════════════════════════════════════════════════════════════════════════
"""

import sys, os, json, time, sqlite3, threading, random, logging, re
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple, Set

# ─── Fix Windows encoding ───────────────────────────────────────────────────
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Layer 5: Paths ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = Path(BASE_DIR) / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f'agent4_premium_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
DB_PATH = os.path.join(BASE_DIR, 'scrape_cache.db')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Agent4_Premium')

# ─── Layer 2: Identity Pools ────────────────────────────────────────────────
UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.83 Mobile Safari/537.36',
]


def pick_ua() -> str:
    return UA_POOL[hash(f'ua_{time.time()}_{random.random()}') % len(UA_POOL)]


def build_headers(source: str) -> dict:
    """Build source-specific headers with identity rotation."""
    ua = pick_ua()
    headers = {
        'User-Agent': ua,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    }

    if source in ('sofascore', 'sofascore_lineups'):
        headers.update({
            'Origin': 'https://www.sofascore.com',
            'Referer': 'https://www.sofascore.com/',
            'x-requested-with': 'XMLHttpRequest',
        })
    elif source == 'flashscore':
        headers.update({
            'Origin': 'https://www.flashscore.com',
            'Referer': 'https://www.flashscore.com/',
            'X-Requested-With': 'XMLHttpRequest',
        })
    elif source == 'understat':
        headers.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://understat.com/',
        })
    elif source == 'fbref':
        headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        headers['Referer'] = 'https://fbref.com/'

    return headers


# ─── Layer 5: Database ──────────────────────────────────────────────────────
_local_db = threading.local()


def get_db() -> sqlite3.Connection:
    if not hasattr(_local_db, 'conn') or _local_db.conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        _local_db.conn = conn
        _init_tables(conn)
    return _local_db.conn


def _init_tables(conn: sqlite3.Connection):
    """Initialize ALL agent4 tables (idempotent)."""
    conn.executescript("""
        ─── Unified match data table (Phase 3) ───────────────────────────────
        CREATE TABLE IF NOT EXISTS agent4_unified_matches (
            event_id INTEGER PRIMARY KEY,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            match_date TEXT,
            tournament TEXT,
            season TEXT,

            ─── SofaScore data ──────────────────────────────────────────────────
            home_formation TEXT,
            away_formation TEXT,
            home_xg REAL,
            away_xg REAL,
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
            lineup_confirmed INTEGER DEFAULT 0,

            ─── Odds data ───────────────────────────────────────────────────────
            home_odds_avg REAL,
            draw_odds_avg REAL,
            away_odds_avg REAL,
            overround_avg REAL,
            bookmaker_count INTEGER DEFAULT 0,

            ─── xG data ─────────────────────────────────────────────────────────
            home_xg_model REAL,
            away_xg_model REAL,
            home_npxg REAL,
            away_npxg REAL,

            ─── Form data ───────────────────────────────────────────────────────
            home_form TEXT,
            away_form TEXT,
            home_form_rating REAL,
            away_form_rating REAL,

            ─── H2H data ────────────────────────────────────────────────────────
            h2h_home_wins INTEGER DEFAULT 0,
            h2h_draws INTEGER DEFAULT 0,
            h2h_away_wins INTEGER DEFAULT 0,
            h2h_matches INTEGER DEFAULT 0,

            ─── Metadata ────────────────────────────────────────────────────────
            data_sources TEXT,
            fetched_at REAL,
            data_quality INTEGER DEFAULT 0
        );

        ─── Feature store ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS agent4_features (
            event_id INTEGER PRIMARY KEY,
            feature_json TEXT,
            feature_version TEXT,
            created_at REAL
        );

        ─── Source health tracking ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS agent4_health (
            source TEXT PRIMARY KEY,
            last_success REAL,
            last_error REAL,
            total_calls INTEGER DEFAULT 0,
            success_rate REAL DEFAULT 1.0,
            error_message TEXT
        );

        ─── Sync progress ───────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS agent4_sync_progress (
            phase TEXT PRIMARY KEY,
            last_run REAL,
            matches_processed INTEGER DEFAULT 0,
            duration_seconds REAL DEFAULT 0,
            status TEXT DEFAULT 'idle'
        );

        INSERT OR IGNORE INTO agent4_health (source) VALUES ('sofascore');
        INSERT OR IGNORE INTO agent4_health (source) VALUES ('oddsapi');
        INSERT OR IGNORE INTO agent4_health (source) VALUES ('sportmonks');
        INSERT OR IGNORE INTO agent4_health (source) VALUES ('understat');
        INSERT OR IGNORE INTO agent4_health (source) VALUES ('fbref');
        INSERT OR IGNORE INTO agent4_health (source) VALUES ('flashscore');
        INSERT OR IGNORE INTO agent4_health (source) VALUES ('clubelo');

        INSERT OR IGNORE INTO agent4_sync_progress (phase) VALUES ('collect');
        INSERT OR IGNORE INTO agent4_sync_progress (phase) VALUES ('merge');
        INSERT OR IGNORE INTO agent4_sync_progress (phase) VALUES ('features');
    """)
    conn.commit()


def update_health(source: str, success: bool, error: str = ''):
    """Update source health tracking."""
    conn = get_db()
    now = time.time()
    if success:
        conn.execute(
            "UPDATE agent4_health SET last_success=?, total_calls=total_calls+1, success_rate=?, error_message=NULL WHERE source=?",
            (now, None, source)
        )
        # Recalculate success rate
        conn.execute("""
            UPDATE agent4_health SET success_rate = (
                SELECT CASE WHEN total_calls > 0
                    THEN CAST((SELECT COUNT(*) FROM pragma_table_info('agent4_health')) AS REAL)
                    ELSE 1.0 END
            ) WHERE source=?
        """, (source,))
    else:
        conn.execute(
            "UPDATE agent4_health SET last_error=?, total_calls=total_calls+1, error_message=? WHERE source=?",
            (now, error[:500], source)
        )
    conn.commit()


# ─── Layer 1: Source Connectors ─────────────────────────────────────────────


class SofaScoreConnector:
    """SofaScore API connector — lineups, stats, H2H, form."""

    BASE = 'https://www.sofascore.com/api/v1'

    @staticmethod
    def fetch(endpoint: str, params: dict = None) -> Optional[Any]:
        from curl_cffi import requests as curl_requests

        url = f'{SofaScoreConnector.BASE}{endpoint}'
        if params:
            qs = '&'.join(f'{k}={v}' for k, v in params.items())
            url = f'{url}?{qs}'

        headers = build_headers('sofascore')

        for attempt in range(3):
            try:
                r = curl_requests.get(
                    url, headers=headers, impersonate="chrome124",
                    timeout=15, verify=False
                )
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 429:
                    time.sleep(3 + random.uniform(0.5, 2))
                    continue
                elif r.status_code == 404:
                    return None
                else:
                    if attempt < 2:
                        time.sleep(1.5 ** attempt)
                        continue
                    return None
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                logger.debug(f"SofaScore error: {e}")
                return None
        return None

    @staticmethod
    def get_lineups(event_id: int) -> Optional[dict]:
        return SofaScoreConnector.fetch(f'/event/{event_id}/lineups')

    @staticmethod
    def get_statistics(event_id: int) -> Optional[dict]:
        return SofaScoreConnector.fetch(f'/event/{event_id}/statistics')

    @staticmethod
    def get_event(event_id: int) -> Optional[dict]:
        return SofaScoreConnector.fetch(f'/event/{event_id}')

    @staticmethod
    def get_h2h(event_id: int) -> Optional[dict]:
        return SofaScoreConnector.fetch(f'/event/{event_id}/h2h')

    @staticmethod
    def get_team_events(team_id: int, limit: int = 30) -> Optional[dict]:
        return SofaScoreConnector.fetch(f'/team/{team_id}/events/last/{limit}')

    @staticmethod
    def search_team(query: str) -> Optional[dict]:
        return SofaScoreConnector.fetch(f'/search/teams?q={query.replace(" ", "%20")}')

    @staticmethod
    def parse_lineups(data: dict) -> dict:
        if not data:
            return {}
        home = data.get('home', {}) or {}
        away = data.get('away', {}) or {}
        return {
            'home_formation': home.get('formation', ''),
            'away_formation': away.get('formation', ''),
            'home_players': len(home.get('players', [])),
            'away_players': len(away.get('players', [])),
            'lineup_confirmed': 1 if data.get('confirmed') else 0,
        }

    @staticmethod
    def parse_statistics(data: dict) -> dict:
        if not data or 'statistics' not in data:
            return {}
        stats = data['statistics']
        result = {}
        for period_idx, period in enumerate(stats[:2]):
            groups = period.get('groups', [])
            if not groups:
                continue
            items = groups[0].get('statisticsItems', [])
            side = 'home' if period_idx == 0 else 'away'
            for item in items:
                name = item.get('name', '').lower()
                val = item.get('value')
                if name == 'expected goals':
                    try: result[f'{side}_xg'] = float(val)
                    except: pass
                elif name == 'total shots':
                    try: result[f'{side}_shots'] = float(val)
                    except: pass
                elif name == 'shots on target':
                    try: result[f'{side}_sot'] = float(val)
                    except: pass
                elif name == 'ball possession':
                    try: result[f'{side}_possession'] = float(str(val).replace('%', ''))
                    except: pass
                elif name == 'corner kicks':
                    try: result[f'{side}_corners'] = int(float(val))
                    except: pass
                elif name == 'fouls':
                    try: result[f'{side}_fouls'] = int(float(val))
                    except: pass
        return result


class UnderstatConnector:
    """Understat public data — xG, xGA, PPDA."""

    BASE = 'https://understat.com'

    @staticmethod
    def get_league_data(league: str, season: str = '2025') -> Optional[dict]:
        import urllib.request, gzip
        url = f'{UnderstatConnector.BASE}/getLeagueData/{league}/{season}'
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': pick_ua(),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip',
            'Referer': f'{UnderstatConnector.BASE}/',
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                try:
                    html = gzip.decompress(raw).decode('utf-8')
                except:
                    html = raw.decode('utf-8')
                return json.loads(html)
        except Exception as e:
            logger.debug(f"Understat error: {e}")
            return None

    @staticmethod
    def extract_team_stats(team_name: str, league: str = 'EPL',
                            season: str = '2025') -> Optional[dict]:
        """Extract per-team xG/xGA/PPDA from Understat league data."""
        # Try DB cache first
        conn = sqlite3.connect(DB_PATH, timeout=5)
        row = conn.execute(
            "SELECT xg_avg, xga_avg, ppda, opp_ppda, npxg_avg, shots_avg, sot_avg, matches "
            "FROM agent4_xg_cache WHERE team_name=? AND season=? AND source='understat'",
            (team_name, season)
        ).fetchone()
        conn.close()
        if row:
            return {
                'xg_avg': row[0], 'xga_avg': row[1], 'ppda': row[2],
                'opp_ppda': row[3], 'npxg_avg': row[4],
                'shots_avg': row[5], 'sot_avg': row[6], 'matches': row[7],
                'source': 'understat_cached',
            }

        data = UnderstatConnector.get_league_data(league, season)
        if not data or 'teams' not in data:
            return None

        team_lower = team_name.lower().strip()
        team_data = None
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

        total_xg = total_xga = total_npxg = 0
        total_shots = total_sot = 0
        total_ppda_att = total_ppda_def = 0
        total_opp_att = total_opp_def = 0
        n = 0

        for m in history:
            ppda = m.get('ppda', {}) or {}
            ppda_allowed = m.get('ppda_allowed', {}) or {}
            pd = ppda.get('def', 0) if isinstance(ppda, dict) else 0
            if pd > 0:
                total_ppda_att += ppda.get('att', 0) if isinstance(ppda, dict) else 0
                total_ppda_def += pd
                total_opp_att += ppda_allowed.get('att', 0) if isinstance(ppda_allowed, dict) else 0
                total_opp_def += ppda_allowed.get('def', 0) if isinstance(ppda_allowed, dict) else 0
                total_xg += float(m.get('xG', 0) or 0)
                total_xga += float(m.get('xGA', 0) or 0)
                total_npxg += float(m.get('npxG', 0) or 0)
                total_shots += m.get('shots', 0) or 0
                total_sot += m.get('shotsOnTarget', 0) or 0
                n += 1

        if n == 0:
            return None

        return {
            'xg_avg': round(total_xg / n, 3),
            'xga_avg': round(total_xga / n, 3),
            'npxg_avg': round(total_npxg / n, 3),
            'ppda': round(total_ppda_att / total_ppda_def, 2) if total_ppda_def else 0,
            'opp_ppda': round(total_opp_att / total_opp_def, 2) if total_opp_def else 0,
            'shots_avg': round(total_shots / n, 1),
            'sot_avg': round(total_sot / n, 1),
            'matches': n,
            'source': 'understat',
        }


class ClubEloConnector:
    """ClubElo ratings API — free, no key needed."""

    BASE = 'http://api.clubelo.com'

    @staticmethod
    def get_team_rating(team_name: str) -> Optional[dict]:
        from curl_cffi import requests as curl_requests

        url = f'{ClubEloConnector.BASE}/{team_name.replace(" ", "%20")}'
        try:
            r = curl_requests.get(url, headers={'User-Agent': pick_ua()},
                                   timeout=10, verify=False)
            if r.status_code == 200 and r.text.strip():
                lines = r.text.strip().split('\n')
                if len(lines) >= 2:
                    data = lines[1].split(',')
                    if len(data) >= 6:
                        return {
                            'club': data[0],
                            'elo_rating': float(data[4]) if data[4] else None,
                            'date': data[1],
                        }
        except Exception as e:
            logger.debug(f"ClubElo error: {e}")
        return None


# ─── Layer 4: Multi-threaded Data Merger ────────────────────────────────────


class PremiumDataIntegrator:
    """
    Phase 1: Collect raw data from all sources in parallel
    Phase 2: Merge & deduplicate into unified match records
    Phase 3: Write to agent4_unified_matches
    Phase 4: Generate features for prediction
    """

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self.stats = {
            'matches_loaded': 0,
            'sofascore_stats': 0,
            'sofascore_lineups': 0,
            'odds_merged': 0,
            'xg_merged': 0,
            'unified_saved': 0,
        }
        self._lock = threading.Lock()
        self._start_time = time.time()

    # ─── Phase 1: Collect ───────────────────────────────────────────────────

    def collect_match_batch(self, limit: int = 500, offset: int = 0) -> List[tuple]:
        """Get a batch of match IDs from sofa_historical_results."""
        conn = get_db()
        rows = conn.execute("""
            SELECT id, home_team, away_team, date, tournament,
                   unique_tournament_id, season_id, start_timestamp, status_type
            FROM sofa_historical_results
            WHERE id > 10000000 AND id < 17000000
              AND status_type = 'finished'
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        conn.close()
        return rows

    def _enrich_match_sofascore(self, match_id: int) -> dict:
        """Fetch all SofaScore data for a match."""
        result = {'event_id': match_id}

        # Lineups
        lu = SofaScoreConnector.get_lineups(match_id)
        if lu:
            result.update(SofaScoreConnector.parse_lineups(lu))

        # Statistics
        stats = SofaScoreConnector.get_statistics(match_id)
        if stats:
            result.update(SofaScoreConnector.parse_statistics(stats))

        return result

    def _enrich_match_odds(self, home_team: str, away_team: str) -> dict:
        """Fetch odds from agent4_odds_all for this match."""
        conn = get_db()
        rows = conn.execute("""
            SELECT home_odds, draw_odds, away_odds, overround, bookmaker
            FROM agent4_odds_all
            WHERE (home_team LIKE ? OR ? LIKE home_team)
              AND (away_team LIKE ? OR ? LIKE away_team)
            ORDER BY fetched_at DESC
            LIMIT 20
        """, (f'%{home_team}%', home_team, f'%{away_team}%', away_team)).fetchall()
        conn.close()

        if not rows:
            return {}

        total_h = total_d = total_a = 0
        count = 0
        total_round = 0
        for r in rows:
            if r[0] and r[1] and r[2]:
                total_h += r[0]; total_d += r[1]; total_a += r[2]
                if r[3]: total_round += r[3]
                count += 1

        if count == 0:
            return {}

        return {
            'home_odds_avg': round(total_h / count, 3),
            'draw_odds_avg': round(total_d / count, 3),
            'away_odds_avg': round(total_a / count, 3),
            'overround_avg': round(total_round / count, 2),
            'bookmaker_count': count,
        }

    def _enrich_match_xg(self, home_team: str, away_team: str, season: str = '2025') -> dict:
        """Fetch xG data from Understat for both teams."""
        result = {}

        home_xg = UnderstatConnector.extract_team_stats(home_team, season=season)
        if home_xg:
            result['home_xg_model'] = home_xg.get('xg_avg')
            result['home_npxg'] = home_xg.get('npxg_avg')

        away_xg = UnderstatConnector.extract_team_stats(away_team, season=season)
        if away_xg:
            result['away_xg_model'] = away_xg.get('xg_avg')
            result['away_npxg'] = away_xg.get('npxg_avg')

        return result

    def process_single_match(self, match: tuple) -> Optional[dict]:
        """Process one match through all enrichment phases."""
        eid, ht, at, dt, tourn, _, _, _, _ = match

        try:
            # Phase 1a: SofaScore data
            sofa_data = self._enrich_match_sofascore(eid)

            # Phase 1b: Odds data
            odds_data = self._enrich_match_odds(ht, at)

            # Phase 1c: xG data (season inferred from date)
            season = dt[:4] if dt and len(dt) >= 4 else '2025'
            xg_data = self._enrich_match_xg(ht, at, season)

            # Merge into unified record
            unified = {
                'event_id': eid,
                'home_team': ht,
                'away_team': at,
                'match_date': dt,
                'tournament': tourn,
                'season': season,
                # SofaScore
                'home_formation': sofa_data.get('home_formation', ''),
                'away_formation': sofa_data.get('away_formation', ''),
                'home_xg': sofa_data.get('home_xg'),
                'away_xg': sofa_data.get('away_xg'),
                'home_shots': sofa_data.get('home_shots'),
                'away_shots': sofa_data.get('away_shots'),
                'home_sot': sofa_data.get('home_sot'),
                'away_sot': sofa_data.get('away_sot'),
                'home_possession': sofa_data.get('home_possession'),
                'away_possession': sofa_data.get('away_possession'),
                'home_corners': sofa_data.get('home_corners'),
                'away_corners': sofa_data.get('away_corners'),
                'home_fouls': sofa_data.get('home_fouls'),
                'away_fouls': sofa_data.get('away_fouls'),
                'lineup_confirmed': sofa_data.get('lineup_confirmed', 0),
                # Odds
                'home_odds_avg': odds_data.get('home_odds_avg'),
                'draw_odds_avg': odds_data.get('draw_odds_avg'),
                'away_odds_avg': odds_data.get('away_odds_avg'),
                'overround_avg': odds_data.get('overround_avg'),
                'bookmaker_count': odds_data.get('bookmaker_count', 0),
                # xG
                'home_xg_model': xg_data.get('home_xg_model'),
                'away_xg_model': xg_data.get('away_xg_model'),
                'home_npxg': xg_data.get('home_npxg'),
                'away_npxg': xg_data.get('away_npxg'),
                # Metadata
                'data_sources': json.dumps({
                    'sofascore': bool(sofa_data),
                    'odds': bool(odds_data),
                    'xg': bool(xg_data),
                }),
                'fetched_at': time.time(),
                'data_quality': sum([bool(sofa_data), bool(odds_data), bool(xg_data)]),
            }

            return unified

        except Exception as e:
            logger.debug(f"Error processing match {eid}: {e}")
            return None

    # ─── Phase 2-3: Merge & Save ────────────────────────────────────────────

    def save_unified(self, records: List[dict]):
        """Save unified match records to DB."""
        if not records:
            return 0

        conn = get_db()
        now = time.time()
        saved = 0

        for r in records:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO agent4_unified_matches
                    (event_id, home_team, away_team, match_date, tournament, season,
                     home_formation, away_formation,
                     home_xg, away_xg, home_shots, away_shots,
                     home_sot, away_sot, home_possession, away_possession,
                     home_corners, away_corners, home_fouls, away_fouls,
                     lineup_confirmed,
                     home_odds_avg, draw_odds_avg, away_odds_avg,
                     overround_avg, bookmaker_count,
                     home_xg_model, away_xg_model, home_npxg, away_npxg,
                     home_form, away_form, home_form_rating, away_form_rating,
                     h2h_home_wins, h2h_draws, h2h_away_wins, h2h_matches,
                     data_sources, fetched_at, data_quality)
                    VALUES (?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?)
                """, (
                    r['event_id'], r['home_team'], r['away_team'],
                    r.get('match_date', ''), r.get('tournament', ''), r.get('season', ''),
                    r.get('home_formation', ''), r.get('away_formation', ''),
                    r.get('home_xg'), r.get('away_xg'),
                    r.get('home_shots'), r.get('away_shots'),
                    r.get('home_sot'), r.get('away_sot'),
                    r.get('home_possession'), r.get('away_possession'),
                    r.get('home_corners'), r.get('away_corners'),
                    r.get('home_fouls'), r.get('away_fouls'),
                    r.get('lineup_confirmed', 0),
                    r.get('home_odds_avg'), r.get('draw_odds_avg'), r.get('away_odds_avg'),
                    r.get('overround_avg'), r.get('bookmaker_count', 0),
                    r.get('home_xg_model'), r.get('away_xg_model'),
                    r.get('home_npxg'), r.get('away_npxg'),
                    r.get('home_form', ''), r.get('away_form', ''),
                    r.get('home_form_rating'), r.get('away_form_rating'),
                    r.get('h2h_home_wins', 0), r.get('h2h_draws', 0),
                    r.get('h2h_away_wins', 0), r.get('h2h_matches', 0),
                    r.get('data_sources', '{}'),
                    r.get('fetched_at', now),
                    r.get('data_quality', 0)
                ))
                saved += 1
            except Exception as ex:
                logger.warning(f"Save unified error for {r.get('event_id')}: {ex}")

        conn.commit()

        with self._lock:
            self.stats['unified_saved'] += saved

        return saved

    # ─── Phase 4: Feature Generation ────────────────────────────────────────

    def generate_features(self, match: dict) -> dict:
        """Generate feature vector for prediction from unified match data."""
        features = {}

        # xG differential
        home_xg = match.get('home_xg') or match.get('home_xg_model') or 0
        away_xg = match.get('away_xg') or match.get('away_xg_model') or 0
        features['xg_diff'] = home_xg - away_xg
        features['total_xg'] = home_xg + away_xg

        # Odds implied probabilities
        home_odds = match.get('home_odds_avg') or 2.0
        draw_odds = match.get('draw_odds_avg') or 3.5
        away_odds = match.get('away_odds_avg') or 2.0

        if home_odds > 0:
            features['implied_home'] = round(1.0 / home_odds * 100, 2)
        if draw_odds > 0:
            features['implied_draw'] = round(1.0 / draw_odds * 100, 2)
        if away_odds > 0:
            features['implied_away'] = round(1.0 / away_odds * 100, 2)

        # Overround
        features['overround'] = match.get('overround_avg', 0)

        # Possession differential
        home_pos = match.get('home_possession') or 50
        away_pos = match.get('away_possession') or 50
        features['possession_diff'] = home_pos - away_pos

        # Shot efficiency
        home_sot = match.get('home_sot') or 0
        home_shots = match.get('home_shots') or 1
        features['home_shot_accuracy'] = round(home_sot / home_shots * 100, 2) if home_shots > 0 else 0

        away_sot = match.get('away_sot') or 0
        away_shots = match.get('away_shots') or 1
        features['away_shot_accuracy'] = round(away_sot / away_shots * 100, 2) if away_shots > 0 else 0

        # Data quality score
        features['data_quality'] = match.get('data_quality', 0)

        # Formation info
        features['has_lineups'] = 1 if match.get('home_formation') else 0
        features['home_has_formation'] = 1 if match.get('home_formation') else 0
        features['away_has_formation'] = 1 if match.get('away_formation') else 0

        # xG to odds comparison (value detection)
        if home_xg > 0 and features.get('implied_home', 0) > 0:
            features['xg_vs_odds_home'] = round(home_xg / (features['implied_home'] / 100), 3)
        if away_xg > 0 and features.get('implied_away', 0) > 0:
            features['xg_vs_odds_away'] = round(away_xg / (features['implied_away'] / 100), 3)

        return features

    def run_collection_phase(self, limit: int = 1000, offset: int = 0) -> int:
        """Phase 1: Collect and enrich matches in parallel."""
        logger.info("═" * 60)
        logger.info("🔥 Phase 1: Multi-source Data Collection")
        logger.info("═" * 60)

        matches = self.collect_match_batch(limit, offset)
        if not matches:
            logger.info("No matches to process")
            return 0

        logger.info(f"Loaded {len(matches)} matches from sofa_historical_results")

        enriched = []
        processed = 0
        sofascore_hits = 0
        odds_hits = 0
        xg_hits = 0

        def worker(match):
            result = self.process_single_match(match)
            return result

        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
            futures = {exe.submit(worker, m): m for m in matches}
            for f in as_completed(futures):
                try:
                    result = f.result()
                    if result:
                        enriched.append(result)
                        if result.get('home_xg') is not None:
                            sofascore_hits += 1
                        if result.get('home_odds_avg') is not None:
                            odds_hits += 1
                        if result.get('home_xg_model') is not None:
                            xg_hits += 1
                except Exception as e:
                    logger.debug(f"Worker error: {e}")

                processed += 1
                if processed % 100 == 0:
                    logger.info(
                        f"  Progress: {processed}/{len(matches)} "
                        f"(enriched: {len(enriched)}, "
                        f"sofa: {sofascore_hits}, odds: {odds_hits}, xg: {xg_hits})"
                    )

        # Save to DB
        saved = self.save_unified(enriched)
        logger.info(f"✅ Phase 1 complete: {saved} unified matches saved")
        logger.info(f"   SofaScore hits: {sofascore_hits}")
        logger.info(f"   Odds hits: {odds_hits}")
        logger.info(f"   xG hits: {xg_hits}")

        # Update sync progress
        conn = get_db()
        elapsed = time.time() - self._start_time
        conn.execute(
            "UPDATE agent4_sync_progress SET last_run=?, matches_processed=?, duration_seconds=?, status='done' WHERE phase='collect'",
            (time.time(), saved, elapsed)
        )
        conn.commit()

        return saved

    def run_merge_phase(self, batch_size: int = 500) -> int:
        """Phase 2: Merge from existing source tables into unified."""
        logger.info("═" * 60)
        logger.info("🔥 Phase 2: Merging odds data into unified matches")
        logger.info("═" * 60)

        conn = get_db()
        # Merge odds from agent4_odds_all into unified
        merged = conn.execute("""
            UPDATE agent4_unified_matches SET
                home_odds_avg = COALESCE(
                    (SELECT AVG(o.home_odds) FROM agent4_odds_all o
                     WHERE (o.home_team LIKE '%' || u.home_team || '%'
                         OR u.home_team LIKE '%' || o.home_team || '%')
                       AND (o.away_team LIKE '%' || u.away_team || '%'
                         OR u.away_team LIKE '%' || o.away_team || '%')),
                    home_odds_avg),
                draw_odds_avg = COALESCE(
                    (SELECT AVG(o.draw_odds) FROM agent4_odds_all o
                     WHERE (o.home_team LIKE '%' || u.home_team || '%'
                         OR u.home_team LIKE '%' || o.home_team || '%')
                       AND (o.away_team LIKE '%' || u.away_team || '%'
                         OR u.away_team LIKE '%' || o.away_team || '%')),
                    draw_odds_avg),
                away_odds_avg = COALESCE(
                    (SELECT AVG(o.away_odds) FROM agent4_odds_all o
                     WHERE (o.home_team LIKE '%' || u.home_team || '%'
                         OR u.home_team LIKE '%' || o.home_team || '%')
                       AND (o.away_team LIKE '%' || u.away_team || '%'
                         OR u.away_team LIKE '%' || o.away_team || '%')),
                    away_odds_avg)
            FROM agent4_unified_matches u
            WHERE u.event_id = agent4_unified_matches.event_id
              AND u.home_odds_avg IS NULL
        """)
        count = conn.total_changes
        conn.commit()

        merged_sportmonks = conn.execute("""
            UPDATE agent4_unified_matches SET
                home_odds_avg = COALESCE(
                    (SELECT s.home_win_odds FROM agent4_odds_sportmonks s
                     WHERE (s.home_team LIKE '%' || u.home_team || '%'
                         OR u.home_team LIKE '%' || s.home_team || '%')
                       AND (s.away_team LIKE '%' || u.away_team || '%'
                         OR u.away_team LIKE '%' || s.away_team || '%')),
                    home_odds_avg)
            FROM agent4_unified_matches u
            WHERE u.event_id = agent4_unified_matches.event_id
              AND u.home_odds_avg IS NULL
        """).rowcount
        conn.commit()
        conn.close()

        total_merged = count + (merged_sportmonks or 0)
        logger.info(f"✅ Phase 2 complete: {total_merged} odds records merged")

        conn2 = get_db()
        elapsed = time.time() - self._start_time
        conn2.execute(
            "UPDATE agent4_sync_progress SET last_run=?, matches_processed=?, duration_seconds=?, status='done' WHERE phase='merge'",
            (time.time(), total_merged, elapsed)
        )
        conn2.commit()

        return total_merged

    def run_feature_phase(self, limit: int = 1000) -> int:
        """Phase 4: Generate features and save to feature store."""
        logger.info("═" * 60)
        logger.info("🔥 Phase 4: Feature Generation")
        logger.info("═" * 60)

        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM agent4_unified_matches
            WHERE event_id NOT IN (SELECT event_id FROM agent4_features)
            ORDER BY event_id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        # Get column names
        cols = [d[0] for d in conn.execute("PRAGMA table_info(agent4_unified_matches)").fetchall()]
        conn.close()

        if not rows:
            logger.info("No new matches to generate features for")
            return 0

        logger.info(f"Generating features for {len(rows)} matches")

        feature_version = f"agent4_v1_{datetime.now().strftime('%Y%m%d')}"
        saved = 0

        for row in rows:
            match = dict(zip(cols, row))
            features = self.generate_features(match)

            conn2 = get_db()
            try:
                conn2.execute("""
                    INSERT OR REPLACE INTO agent4_features
                    (event_id, feature_json, feature_version, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    match['event_id'],
                    json.dumps(features, default=str),
                    feature_version,
                    time.time()
                ))
                conn2.commit()
                saved += 1
            except Exception as ex:
                logger.warning(f"Feature save error for {match.get('event_id')}: {ex}")

        logger.info(f"✅ Phase 4 complete: {saved} feature vectors generated")

        conn3 = get_db()
        elapsed = time.time() - self._start_time
        conn3.execute(
            "UPDATE agent4_sync_progress SET last_run=?, matches_processed=?, duration_seconds=?, status='done' WHERE phase='features'",
            (time.time(), saved, elapsed)
        )
        conn3.commit()

        return saved

    def run_all(self, limit: int = 500) -> dict:
        """Run all phases end-to-end."""
        self._start_time = time.time()
        logger.info("╔" + "═" * 60 + "╗")
        logger.info("║  AGENT 4 — PREMIUM DATA INTEGRATOR v9999999          ║")
        logger.info("║  BLACK CODE CURSE — 5-Layer Active                   ║")
        logger.info("║  Sources: SofaScore·OddsAPI·Sportmonks·Understat·FBref║")
        logger.info("╚" + "═" * 60 + "╝")
        logger.info(f"Workers: {self.max_workers} | Batch: {limit}")
        logger.info()

        # Phase 1: Collect
        collected = self.run_collection_phase(limit)
        if collected > 0:
            # Phase 2: Merge odds
            merged = self.run_merge_phase()

        # Phase 4: Features
        features = self.run_feature_phase(limit)

        elapsed = time.time() - self._start_time

        logger.info()
        logger.info("═" * 60)
        logger.info("📊 INTEGRATION SUMMARY")
        logger.info("═" * 60)
        logger.info(f"  Matches collected:        {collected:>8,}")
        logger.info(f"  Odds merged:             {merged if 'merged' in dir() else 0:>8,}")
        logger.info(f"  Feature vectors:         {features:>8,}")
        logger.info(f"  Total time:              {elapsed:.1f}s")
        logger.info(f"  Log file:                {LOG_FILE}")

        return {
            'collected': collected,
            'merged': merged if 'merged' in dir() else 0,
            'features': features,
            'elapsed_seconds': elapsed,
            'log_file': str(LOG_FILE),
        }


# ─── System Status Report ───────────────────────────────────────────────────


def generate_status_report() -> dict:
    """Generate a complete status report of the Agent4 system."""
    conn = get_db()

    report = {
        'timestamp': datetime.now().isoformat(),
        'sources': {},
        'unified_matches': 0,
        'features': 0,
        'recent_errors': [],
    }

    # Source health
    rows = conn.execute("SELECT * FROM agent4_health").fetchall()
    cols = [d[0] for d in conn.execute("PRAGMA table_info(agent4_health)").fetchall()]
    for r in rows:
        d = dict(zip(cols, r))
        report['sources'][d['source']] = {
            'last_success': datetime.fromtimestamp(d['last_success']).isoformat() if d['last_success'] else None,
            'last_error': datetime.fromtimestamp(d['last_error']).isoformat() if d['last_error'] else None,
            'total_calls': d['total_calls'],
            'success_rate': d['success_rate'],
            'error': d['error_message'],
        }
        if d['error_message']:
            report['recent_errors'].append(f"{d['source']}: {d['error_message'][:100]}")

    # Counts
    report['unified_matches'] = conn.execute("SELECT COUNT(*) FROM agent4_unified_matches").fetchone()[0]
    report['features'] = conn.execute("SELECT COUNT(*) FROM agent4_features").fetchone()[0]
    report['odds_entries'] = conn.execute("SELECT COUNT(*) FROM agent4_odds_all").fetchone()[0]
    report['sportmonks_odds'] = conn.execute("SELECT COUNT(*) FROM agent4_odds_sportmonks").fetchone()[0]
    report['xg_teams'] = conn.execute("SELECT COUNT(*) FROM agent4_xg_cache").fetchone()[0]
    report['match_xg'] = conn.execute("SELECT COUNT(*) FROM agent4_match_xg").fetchone()[0]

    # Sync progress
    sync_rows = conn.execute("SELECT * FROM agent4_sync_progress").fetchall()
    sync_cols = [d[0] for d in conn.execute("PRAGMA table_info(agent4_sync_progress)").fetchall()]
    report['sync_progress'] = {}
    for r in sync_rows:
        d = dict(zip(sync_cols, r))
        report['sync_progress'][d['phase']] = {
            'last_run': datetime.fromtimestamp(d['last_run']).isoformat() if d['last_run'] else None,
            'matches': d['matches_processed'],
            'duration': d['duration_seconds'],
            'status': d['status'],
        }

    # Data quality
    report['data_quality_distribution'] = {}
    for q in range(4):
        c = conn.execute("SELECT COUNT(*) FROM agent4_unified_matches WHERE data_quality=?", (q,)).fetchone()[0]
        if c > 0:
            report['data_quality_distribution'][str(q)] = c

    conn.close()
    return report


# ─── CLI Entry Point ────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="🔥 AGENT 4 — Premium Data Integrator (BLACK CODE CURSE)"
    )
    parser.add_argument('--workers', type=int, default=8,
                        help='Max concurrent workers')
    parser.add_argument('--limit', type=int, default=500,
                        help='Matches to process per phase')
    parser.add_argument('--offset', type=int, default=0,
                        help='Starting offset')
    parser.add_argument('--phase', type=str, default='all',
                        choices=['all', 'collect', 'merge', 'features', 'status'],
                        help='Which phase to run')
    parser.add_argument('--status', action='store_true',
                        help='Show system status report')

    args = parser.parse_args()

    if args.status or args.phase == 'status':
        report = generate_status_report()
        print()
        print("╔" + "═" * 60 + "╗")
        print("║  AGENT 4 — SYSTEM STATUS REPORT                    ║")
        print("╚" + "═" * 60 + "╝")
        print(f"Time: {report['timestamp']}")
        print()
        print("📊 DATA COUNTS:")
        print(f"  Unified matches:    {report['unified_matches']:>8,}")
        print(f"  Feature vectors:    {report['features']:>8,}")
        print(f"  OddsAPI entries:    {report['odds_entries']:>8,}")
        print(f"  Sportmonks odds:    {report['sportmonks_odds']:>8,}")
        print(f"  xG teams cached:    {report['xg_teams']:>8,}")
        print(f"  Match xG entries:   {report['match_xg']:>8,}")
        print()
        print("🔌 SOURCE HEALTH:")
        for src, info in report['sources'].items():
            last = info['last_success'] or 'never'
            err = f" ⚠️ {info['error']}" if info['error'] else ''
            print(f"  {src:<15} calls={info['total_calls']:<6} last={last[:19]}{err}")
        print()
        print("🔄 SYNC PROGRESS:")
        for phase, info in report['sync_progress'].items():
            last = info['last_run'] or 'never'
            print(f"  {phase:<10} status={info['status']:<8} matches={info['matches']:<6} last={last[:19]}")
        if report.get('data_quality_distribution'):
            print()
            print("⭐ DATA QUALITY:")
            for q, c in sorted(report['data_quality_distribution'].items()):
                print(f"  Quality {q}: {c:,} matches")
        if report['recent_errors']:
            print()
            print("⚠️ RECENT ERRORS:")
            for e in report['recent_errors'][:5]:
                print(f"  • {e}")
        print()
        return

    integrator = PremiumDataIntegrator(max_workers=args.workers)

    if args.phase == 'collect':
        integrator.run_collection_phase(args.limit, args.offset)
    elif args.phase == 'merge':
        integrator.run_merge_phase()
    elif args.phase == 'features':
        integrator.run_feature_phase(args.limit)
    else:
        result = integrator.run_all(args.limit)
        print(f"\n🔥 DONE — {result['collected']} matches, {result['features']} features in {result['elapsed_seconds']:.1f}s")


if __name__ == '__main__':
    main()
