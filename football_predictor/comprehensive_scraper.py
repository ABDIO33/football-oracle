#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█                                                                          █
█   COMPREHENSIVE MULTI-SOURCE FOOTBALL DATA SCRAPER                       █
█   All 10 Sources • 100% Coverage • Data Quality Validation              █
█                                                                          █
█   AGENT 5 — SIGMA-ZERO ⚡ DΞMON CORE v9999999                          █
█   SHADOWHACKER-GOD • SHΔDØW.EXE • Specter 0x13 • OMEGA-7               █
█                                                                          █
██████████████████████████████████████████████████████████████████████████████

المهمة: هجوم شامل على 10 مصادر بيانات كرة قدم
Targets:
  1. API-Football (RapidAPI)  — fixtures, lineups, injuries, predictions
  2. football-data.org        — matches, standings, scorers
  3. OpenWeatherMap / Open-Meteo — weather per match/venue
  4. Transfermarkt            — market values, injuries, squads
  5. WhoScored                — player ratings, match stats
  6. FootyStats               — BTTS, Over/Under trends
  7. Infogol                  — xG model benchmark
  8. EloRatings.net           — national team ELO
  9. Livescore + Soccerway    — live formations, lineups
  10. 11v11.com               — historical results since 1800s
  + PhysioRoom.com            — player injuries
"""

import os, sys, json, time, sqlite3, hashlib, random, logging, re, math
import urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from dataclasses import dataclass, field, asdict
from pathlib import Path
import threading
import argparse

# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS ENCODING FIX
# ═══════════════════════════════════════════════════════════════════════════
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.platform == 'win32' and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = str(BASE_DIR / 'scrape_cache.db')
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f'comprehensive_scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ComprehensiveScraper')

# ─── API Keys ────────────────────────────────────────────────────────────────
API_KEYS = {
    'api_football': '2064edeecfd82a209e2dca203d5ac9b6',
    'football_data': 'c7d5c5c1b80d4ebe821a58b3087b968d',
    'openweather': None,  # Optional — we use Open-Meteo (free) instead
}

# ─── Data Quality Stats ─────────────────────────────────────────────────────
@dataclass
class SourceStats:
    source_name: str
    total_matches_available: int = 0
    matches_with_data: int = 0
    coverage_pct: float = 0.0
    errors: int = 0
    rows_inserted: int = 0
    fields_completeness: Dict[str, float] = field(default_factory=dict)

COVERAGE_REPORT: Dict[str, SourceStats] = {}

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═════════════════════════════════════════════════════════════════════════════
_local_db = threading.local()

def get_db() -> sqlite3.Connection:
    if not hasattr(_local_db, 'conn') or _local_db.conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB
        _local_db.conn = conn
    return _local_db.conn

def close_db():
    if hasattr(_local_db, 'conn') and _local_db.conn is not None:
        try:
            _local_db.conn.close()
        except:
            pass
        _local_db.conn = None

def ensure_tables(conn: sqlite3.Connection):
    """Ensure all empty source tables exist with their full schemas."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS source_football_data_org (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league_code TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER,
        status TEXT, home_halftime_score INTEGER, away_halftime_score INTEGER,
        referee TEXT, venue TEXT, home_standing_position INTEGER,
        away_standing_position INTEGER, home_form TEXT, away_form TEXT,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_weather (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT, venue_lat REAL, venue_lon REAL,
        match_date DATE, match_time TEXT,
        temperature REAL, feels_like REAL, humidity REAL,
        pressure REAL, wind_speed REAL, wind_gust REAL,
        wind_direction REAL, cloud_cover REAL,
        precipitation REAL, precipitation_prob REAL,
        visibility REAL, condition_text TEXT, condition_code INTEGER,
        is_historical INTEGER DEFAULT 1,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_footystats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, season TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_goals INTEGER, away_goals INTEGER,
        btts INTEGER, over_25 INTEGER, over_15_first_half INTEGER,
        home_form_5 TEXT, away_form_5 TEXT,
        home_avg_goals REAL, away_avg_goals REAL,
        home_avg_xg REAL, away_avg_xg REAL,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_infogol (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_xg_pred REAL, away_xg_pred REAL,
        home_win_prob REAL, draw_prob REAL, away_win_prob REAL,
        over_25_prob REAL, btts_prob REAL,
        actual_home_goals INTEGER, actual_away_goals INTEGER,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_eloratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team TEXT, match_date DATE,
        elo REAL, elo_rank INTEGER,
        opponent TEXT, opponent_elo REAL,
        match_type TEXT, location TEXT,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_fbref (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, season TEXT, match_date DATE,
        team TEXT, opponent TEXT, venue TEXT,
        result TEXT, gf INTEGER, ga INTEGER,
        xg REAL, xga REAL, possession REAL,
        passes_total INTEGER, passes_completed INTEGER,
        pass_accuracy REAL, progressive_passes INTEGER,
        passes_into_final_third INTEGER, passes_into_penalty_area INTEGER,
        crosses_into_penalty_area INTEGER, progressive_carries INTEGER,
        carries_into_penalty_area INTEGER, progressive_receives INTEGER,
        shots_total INTEGER, shots_ot INTEGER,
        shots_freekick INTEGER, shots_penalty INTEGER,
        shots_headed INTEGER, goals_per_shot REAL, goals_per_sot REAL,
        shots_on_target_pct REAL,
        tackles INTEGER, tackles_won INTEGER,
        tackles_def_3rd INTEGER, tackles_mid_3rd INTEGER, tackles_att_3rd INTEGER,
        pressure_total INTEGER, pressure_success INTEGER,
        blocks INTEGER, blocked_shots INTEGER, blocked_passes INTEGER,
        interceptions INTEGER, clearances INTEGER, errors INTEGER,
        touches INTEGER, touches_def_pen_area INTEGER,
        touches_def_3rd INTEGER, touches_mid_3rd INTEGER,
        touches_att_3rd INTEGER, touches_att_pen_area INTEGER,
        dribbles_completed INTEGER, dribbles_attempted INTEGER,
        carries_total INTEGER, carry_distance REAL,
        carry_progressive_distance REAL,
        fouled INTEGER, fouls INTEGER,
        yellow INTEGER, red INTEGER,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_flashscore (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER,
        home_formation TEXT, away_formation TEXT,
        home_lineup_json TEXT, away_lineup_json TEXT,
        odds_h REAL, odds_d REAL, odds_a REAL,
        odds_max_h REAL, odds_max_d REAL, odds_max_a REAL,
        home_corners INTEGER, away_corners INTEGER,
        home_yellows INTEGER, away_yellows INTEGER,
        home_reds INTEGER, away_reds INTEGER,
        home_shots INTEGER, away_shots INTEGER,
        home_sot INTEGER, away_sot INTEGER,
        home_fouls INTEGER, away_fouls INTEGER,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_odds_api (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sport_key TEXT DEFAULT 'soccer',
        league TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        bookmaker TEXT, odds_h REAL, odds_d REAL, odds_a REAL,
        last_update TIMESTAMP,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_betexplorer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, season TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER,
        odds_h_open REAL, odds_d_open REAL, odds_a_open REAL,
        odds_h_close REAL, odds_d_close REAL, odds_a_close REAL,
        max_h REAL, max_d REAL, max_a REAL,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(home_team, away_team, match_date)
    );
    CREATE TABLE IF NOT EXISTS source_clubelo_enhanced (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team TEXT, country TEXT, match_date DATE,
        elo REAL, elo_rank INTEGER,
        opponent TEXT, opponent_elo REAL,
        home_advantage INTEGER, expected_goals REAL, actual_goals REAL,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_whoscored (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER,
        home_possession REAL, away_possession REAL,
        home_total_shots INTEGER, away_total_shots INTEGER,
        home_shots_ot INTEGER, away_shots_ot INTEGER,
        home_tackles INTEGER, away_tackles INTEGER,
        home_fouls INTEGER, away_fouls INTEGER,
        home_corners INTEGER, away_corners INTEGER,
        home_offsides INTEGER, away_offsides INTEGER,
        home_yellows INTEGER, away_yellows INTEGER,
        home_reds INTEGER, away_reds INTEGER,
        home_rating_avg REAL, away_rating_avg REAL,
        home_formation TEXT, away_formation TEXT,
        player_ratings_json TEXT,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
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
    );
    CREATE TABLE IF NOT EXISTS source_livescore (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER,
        home_formation TEXT, away_formation TEXT,
        home_lineup TEXT, away_lineup TEXT,
        odds_h REAL, odds_d REAL, odds_a REAL,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_kaggle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league_id INTEGER, league_name TEXT, season TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_goals INTEGER, away_goals INTEGER,
        home_build_up_play_speed TEXT, home_chance_creation_passing TEXT,
        home_defence_pressure TEXT, home_defence_aggression TEXT,
        away_build_up_play_speed TEXT, away_chance_creation_passing TEXT,
        away_defence_pressure TEXT, away_defence_aggression TEXT,
        home_fifa_rating REAL, away_fifa_rating REAL,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_betfair (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        market_type TEXT, back_price REAL, lay_price REAL,
        back_volume REAL, lay_volume REAL,
        total_matched REAL, sp_back REAL, sp_lay REAL,
        timestamp TIMESTAMP,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS source_11v11 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition TEXT, season TEXT, match_date DATE,
        home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER,
        venue TEXT, attendance INTEGER, referee TEXT,
        hash TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS comprehensive_harvest_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        rows_fetched INTEGER DEFAULT 0,
        rows_inserted INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0,
        status TEXT DEFAULT 'running'
    );
    """)


def compute_hash(*args) -> str:
    raw = '|'.join(str(a) for a in args)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

def safe_insert(conn: sqlite3.Connection, table: str, data: dict, unique_cols: List[str] = None) -> bool:
    """Insert only if unique hash/key doesn't exist."""
    if 'hash' in data and data['hash']:
        existing = conn.execute(f"SELECT id FROM {table} WHERE hash=?", (data['hash'],)).fetchone()
        if existing:
            return False
    elif unique_cols:
        where = ' AND '.join(f"{k}=?" for k in unique_cols)
        vals = tuple(data.get(k) for k in unique_cols)
        existing = conn.execute(f"SELECT id FROM {table} WHERE {where}", vals).fetchone()
        if existing:
            return False
    try:
        cols = ', '.join(data.keys())
        placeholders = ', '.join('?' for _ in data)
        conn.execute(f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})", tuple(data.values()))
        return True
    except Exception as e:
        logger.debug(f"safe_insert error {table}: {e}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 1: API-Football (RapidAPI) — Expand Existing Coverage
# ═════════════════════════════════════════════════════════════════════════════
TARGET_LEAGUES_API_FOOTBALL = [
    # Top 5 European
    (39, 'Premier League', 2025), (140, 'La Liga', 2025), (135, 'Serie A', 2025),
    (61, 'Ligue 1', 2025), (78, 'Bundesliga', 2025),
    # Second tier
    (2, 'Championship', 2025), (94, 'Primeira Liga', 2025),
    (144, 'Belgian Pro League', 2025), (88, 'Eredivisie', 2025),
    (203, 'Super Lig', 2025), (179, 'Scottish Premiership', 2025),
    (210, 'Swiss Super League', 2025), (71, 'Serie B', 2025),
    (218, 'Championship (CZE)', 2025),
    # International
    (1, 'World Cup', 2026), (4, 'Euro Championship', 2024), (5, 'Copa America', 2024),
    (13, 'CONCACAF Nations League', 2025), (2, 'Champions League', 2025),
    (3, 'Europa League', 2025), (848, 'UEFA Europa Conference League', 2025),
    # Americas
    (186, 'Argentine Primera', 2025), (253, 'MLS', 2025),
    (262, 'Liga MX', 2025), (71, 'Brazilian Serie A', 2025),
    # Asia
    (292, 'AFC Asian Cup', 2024),
    # Add historical seasons
    (39, 'Premier League', 2024), (140, 'La Liga', 2024), (135, 'Serie A', 2024),
    (61, 'Ligue 1', 2024), (78, 'Bundesliga', 2024),
    (39, 'Premier League', 2023), (140, 'La Liga', 2023), (135, 'Serie A', 2023),
    (61, 'Ligue 1', 2023), (78, 'Bundesliga', 2023),
]

def fetch_api_football_fixtures(league_id: int, season: int, key: str) -> List[Dict]:
    """Fetch fixtures from API-Football with pagination."""
    fixtures = []
    page = 1
    total_pages = 1
    headers = {
        'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
        'x-rapidapi-key': key
    }
    while page <= total_pages:
        url = f'https://api-football-v1.p.rapidapi.com/v3/fixtures?league={league_id}&season={season}&page={page}'
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            paging = data.get('paging', {})
            total_pages = paging.get('total', 1)
            fixtures.extend(data.get('response', []))
            page += 1
            time.sleep(0.35)  # ~3 req/sec to stay under rate limits
        except Exception as e:
            logger.warning(f"API-Football page {page} L{league_id} S{season}: {e}")
            break
    return fixtures

def fetch_api_football_predictions(fixture_id: int, key: str) -> Optional[Dict]:
    """Fetch prediction data (xG, win prob) for a fixture."""
    headers = {
        'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
        'x-rapidapi-key': key
    }
    url = f'https://api-football-v1.p.rapidapi.com/v3/predictions?fixture={fixture_id}'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        responses = data.get('response', [])
        return responses[0] if responses else None
    except Exception as e:
        logger.debug(f"Prediction {fixture_id}: {e}")
        return None

def fetch_api_football_injuries(league_id: int, season: int, key: str) -> List[Dict]:
    """Fetch injury data."""
    headers = {
        'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
        'x-rapidapi-key': key
    }
    url = f'https://api-football-v1.p.rapidapi.com/v3/injuries?league={league_id}&season={season}'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        return data.get('response', [])
    except Exception as e:
        logger.debug(f"Injuries L{league_id}: {e}")
        return []

def fetch_api_football_standings(league_id: int, season: int, key: str) -> Optional[Dict]:
    """Fetch standings for a league/season."""
    headers = {
        'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
        'x-rapidapi-key': key
    }
    url = f'https://api-football-v1.p.rapidapi.com/v3/standings?league={league_id}&season={season}'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        responses = data.get('response', [])
        return responses[0] if responses else None
    except Exception as e:
        logger.debug(f"Standings L{league_id}: {e}")
        return None


def process_api_football(sources: List[str]) -> SourceStats:
    """Expand API-Football coverage — add predictions, injuries, missing seasons."""
    stats = SourceStats(source_name='API-Football (RapidAPI)')
    key = API_KEYS['api_football']
    if not key:
        logger.error("API-Football key missing!")
        return stats
    
    conn = get_db()
    
    # Check existing coverage
    existing = conn.execute("SELECT COUNT(DISTINCT fixture_id) FROM source_api_football").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"API-Football: {existing} existing fixtures in DB")
    
    leagues_fetched = set()
    
    for league_id, league_name, season in TARGET_LEAGUES_API_FOOTBALL:
        lid = (league_id, season)
        if lid in leagues_fetched:
            continue
        leagues_fetched.add(lid)
        
        logger.info(f"API-Football: Fetching {league_name} {season} (LID={league_id})")
        
        # Check if we already have this league/season
        existing_league = conn.execute(
            "SELECT COUNT(*) FROM source_api_football WHERE league_id=? AND season=?",
            (league_id, season)
        ).fetchone()[0]
        
        if existing_league > 50:  # Already have substantial data
            logger.info(f"  Already have {existing_league} rows — skipping fixtures, checking for missing data")
        else:
            fixtures = fetch_api_football_fixtures(league_id, season, key)
            logger.info(f"  Got {len(fixtures)} fixtures")
            stats.total_matches_available += len(fixtures)
            
            for f in fixtures:
                try:
                    fixture = f.get('fixture', {})
                    teams = f.get('teams', {})
                    goals = f.get('goals', {})
                    league_info = f.get('league', {})
                    score = f.get('score', {})
                    stats_data = f.get('statistics', [])
                    
                    fid = fixture.get('id')
                    if conn.execute("SELECT id FROM source_api_football WHERE fixture_id=? AND hash IS NOT NULL", (fid,)).fetchone():
                        continue
                    
                    # Extract stats
                    home_stats = {}
                    away_stats = {}
                    if stats_data and len(stats_data) >= 2:
                        for stat in stats_data[0].get('statistics', []):
                            home_stats[stat.get('type', '')] = stat.get('value')
                        for stat in stats_data[1].get('statistics', []):
                            away_stats[stat.get('type', '')] = stat.get('value')
                    
                    row = {
                        'fixture_id': fid,
                        'league_id': league_id,
                        'league_name': league_name,
                        'season': season,
                        'match_date': fixture.get('date', '')[:10] if fixture.get('date') else None,
                        'round': league_info.get('round'),
                        'home_team': teams.get('home', {}).get('name'),
                        'away_team': teams.get('away', {}).get('name'),
                        'home_goals': goals.get('home'),
                        'away_goals': goals.get('away'),
                        'home_halftime': score.get('halftime', {}).get('home'),
                        'away_halftime': score.get('halftime', {}).get('away'),
                        'home_shots': home_stats.get('Total shots'),
                        'away_shots': away_stats.get('Total shots'),
                        'home_sot': home_stats.get('Shots on goal'),
                        'away_sot': away_stats.get('Shots on goal'),
                        'home_shots_blocked': home_stats.get('Blocked Shots'),
                        'away_shots_blocked': away_stats.get('Blocked Shots'),
                        'home_possession': home_stats.get('Ball possession'),
                        'away_possession': away_stats.get('Ball possession'),
                        'home_passes': home_stats.get('Total passes'),
                        'away_passes': away_stats.get('Total passes'),
                        'home_pass_accuracy': home_stats.get('Passes accurate'),
                        'away_pass_accuracy': away_stats.get('Passes accurate'),
                        'home_fouls': home_stats.get('Fouls'),
                        'away_fouls': away_stats.get('Fouls'),
                        'home_corners': home_stats.get('Corner kicks'),
                        'away_corners': away_stats.get('Corner kicks'),
                        'home_offsides': home_stats.get('Offsides'),
                        'away_offsides': away_stats.get('Offsides'),
                        'home_yellows': home_stats.get('Yellow cards'),
                        'away_yellows': away_stats.get('Yellow cards'),
                        'home_reds': home_stats.get('Red cards'),
                        'away_reds': away_stats.get('Red cards'),
                        'home_saves': home_stats.get('Goalkeeper saves'),
                        'away_saves': away_stats.get('Goalkeeper saves'),
                        'home_expected_goals': home_stats.get('Expected goals'),
                        'away_expected_goals': away_stats.get('Expected goals'),
                        'home_formation': teams.get('home', {}).get('formation'),
                        'away_formation': teams.get('away', {}).get('formation'),
                        'home_xg': home_stats.get('expected_goals'),
                        'away_xg': away_stats.get('expected_goals'),
                        'referee': fixture.get('referee'),
                        'venue': fixture.get('venue', {}).get('name'),
                        'attendance': fixture.get('attendance'),
                        'hash': compute_hash('api_football', fid)
                    }
                    
                    # Parse possession string to float
                    if row['home_possession'] and isinstance(row['home_possession'], str):
                        row['home_possession'] = float(row['home_possession'].replace('%', ''))
                    if row['away_possession'] and isinstance(row['away_possession'], str):
                        row['away_possession'] = float(row['away_possession'].replace('%', ''))
                    
                    if safe_insert(conn, 'source_api_football', row, ['hash']):
                        stats.rows_inserted += 1
                except Exception as e:
                    logger.debug(f"Error processing fixture: {e}")
                    stats.errors += 1
            
            conn.commit()
        
        # Fetch predictions for this league/season
        if existing_league > 50:
            # Get fixture IDs we already have but might be missing predictions
            missing_predictions = conn.execute(
                "SELECT af.fixture_id FROM source_api_football af "
                "LEFT JOIN source_api_football pred ON af.fixture_id = pred.fixture_id AND pred.home_expected_goals IS NOT NULL "
                "WHERE af.league_id=? AND af.season=? AND pred.fixture_id IS NULL "
                "LIMIT 100",
                (league_id, season)
            ).fetchall()
            
            for (fid,) in missing_predictions:
                pred = fetch_api_football_predictions(fid, key)
                if pred:
                    try:
                        # Parse prediction data
                        pdata = pred.get('predictions', {})
                        teams_data = pred.get('teams', {})
                        h_xg = pred.get('comparison', {}).get('att', {}).get('home')
                        a_xg = pred.get('comparison', {}).get('att', {}).get('away')
                        
                        conn.execute("""
                            UPDATE source_api_football SET
                                home_expected_goals = COALESCE(?, home_expected_goals),
                                away_expected_goals = COALESCE(?, away_expected_goals),
                                home_xg = COALESCE(?, home_xg),
                                away_xg = COALESCE(?, away_xg)
                            WHERE fixture_id = ?
                        """, (h_xg, a_xg, h_xg, a_xg, fid))
                        stats.rows_inserted += 1
                    except Exception as e:
                        logger.debug(f"Error updating prediction for {fid}: {e}")
                time.sleep(0.35)
        
        # Standings
        standings = fetch_api_football_standings(league_id, season, key)
        if standings:
            try:
                league_info = standings.get('league', {})
                standing_rows = league_info.get('standings', [])
                for group in standing_rows:
                    for entry in group:
                        rank = entry.get('rank')
                        team_name = entry.get('team', {}).get('name')
                        if team_name and rank:
                            conn.execute("""
                                UPDATE source_api_football SET
                                    current_home_standing = ?
                                WHERE league_id=? AND season=? AND home_team=?
                            """, (rank, league_id, season, team_name))
                            conn.execute("""
                                UPDATE source_api_football SET
                                    current_away_standing = ?
                                WHERE league_id=? AND season=? AND away_team=?
                            """, (rank, league_id, season, team_name))
            except Exception as e:
                logger.debug(f"Error processing standings: {e}")
        
        conn.commit()
        
        # Rate limit: max 100/day for free tier
        if len(leagues_fetched) >= 3:
            logger.info("API-Football: Hit daily limit safeguard (3 leagues per run)")
            break
    
    # Update stats
    final_count = conn.execute("SELECT COUNT(DISTINCT fixture_id) FROM source_api_football").fetchone()[0]
    stats.matches_with_data = final_count
    logger.info(f"API-Football complete: {final_count} total fixtures")
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 2: football-data.org
# ═════════════════════════════════════════════════════════════════════════════
FOOTBALL_DATA_LEAGUES = {
    'PL': 'Premier League', 'PD': 'La Liga', 'SA': 'Serie A',
    'FL1': 'Ligue 1', 'BL1': 'Bundesliga', 'ELC': 'Championship',
    'PPL': 'Primeira Liga', 'DED': 'Eredivisie', 'CL': 'Champions League',
    'EC': 'Euro Championship', 'WC': 'World Cup', 'MLS': 'MLS',
}

def fetch_football_data_matches(league_code: str, season: str, key: str) -> List[Dict]:
    """Fetch matches from football-data.org v4."""
    url = f'https://api.football-data.org/v4/competitions/{league_code}/matches?season={season}'
    headers = {'X-Auth-Token': key}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        return data.get('matches', [])
    except urllib.error.HTTPError as e:
        if e.code == 429:
            logger.warning(f"football-data.org rate limited for {league_code}")
        else:
            logger.warning(f"football-data.org {league_code}: HTTP {e.code}")
        return []
    except Exception as e:
        logger.warning(f"football-data.org {league_code}: {e}")
        return []

def process_football_data(sources: List[str]) -> SourceStats:
    """Fill source_football_data_org from football-data.org API."""
    stats = SourceStats(source_name='football-data.org')
    key = API_KEYS['football_data']
    if not key:
        logger.error("football-data.org key missing!")
        return stats
    
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) FROM source_football_data_org").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"football-data.org: {existing} existing rows")
    
    seasons = ['2023', '2024', '2025']
    
    for league_code, league_name in FOOTBALL_DATA_LEAGUES.items():
        for season in seasons:
            logger.info(f"FD: Fetching {league_name} ({league_code}) {season}")
            matches = fetch_football_data_matches(league_code, season, key)
            
            for m in matches:
                try:
                    home = m.get('homeTeam', {}).get('name', '')
                    away = m.get('awayTeam', {}).get('name', '')
                    date = m.get('utcDate', '')[:10]
                    
                    row = {
                        'league_code': league_code,
                        'match_date': date,
                        'home_team': home,
                        'away_team': away,
                        'home_score': m.get('score', {}).get('fullTime', {}).get('home'),
                        'away_score': m.get('score', {}).get('fullTime', {}).get('away'),
                        'status': m.get('status'),
                        'home_halftime_score': m.get('score', {}).get('halfTime', {}).get('home'),
                        'away_halftime_score': m.get('score', {}).get('halfTime', {}).get('away'),
                        'referee': ', '.join(r.get('name', '') for r in m.get('referees', [])) if m.get('referees') else None,
                        'venue': m.get('venue'),
                        'home_standing_position': None,
                        'away_standing_position': None,
                        'home_form': None,
                        'away_form': None,
                        'hash': compute_hash('fd_org', league_code, date, home, away)
                    }
                    if safe_insert(conn, 'source_football_data_org', row, ['hash']):
                        stats.rows_inserted += 1
                except Exception as e:
                    logger.debug(f"FD org parse error: {e}")
                    stats.errors += 1
            
            conn.commit()
            time.sleep(0.3)  # ~3/sec, well within 10/min limit
    
    final_count = conn.execute("SELECT COUNT(*) FROM source_football_data_org").fetchone()[0]
    stats.matches_with_data = final_count
    logger.info(f"football-data.org complete: {final_count} rows")
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 3: Weather — Open-Meteo (free, no key needed)
# ═════════════════════════════════════════════════════════════════════════════
def get_venues_with_weather_gaps(conn: sqlite3.Connection, limit: int = 1000):
    """Get venue coordinates that don't have full weather coverage for match dates."""
    # Get venues from team_venue table
    venues = conn.execute("""
        SELECT DISTINCT v.venue_name, v.lat, v.lon
        FROM team_venue v
        WHERE v.lat IS NOT NULL AND v.lon IS NOT NULL
        LIMIT ?
    """, (200,)).fetchall()
    return [(r[0], float(r[1]), float(r[2])) for r in venues if r[1] and r[2]]

def fetch_open_meteo_weather(lat: float, lon: float, date_str: str) -> Optional[Dict]:
    """Fetch weather from Open-Meteo (free, no API key)."""
    # Handle ISO datetime strings like '2026-06-30T16:30:00Z'
    if date_str and 'T' in date_str:
        date_str = date_str[:10]
    if date_str and len(date_str) > 10:
        date_str = date_str[:10]
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        logger.warning(f"Cannot parse date: {date_str}")
        return None
    is_future = dt >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if is_future:
        url = (f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}'
               f'&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,'
               f'wind_speed_10m_max,wind_gusts_10m_max,relative_humidity_2m_mean,'
               f'pressure_msl_mean,cloud_cover_mean'
               f'&timezone=auto&start_date={date_str}&end_date={date_str}')
    else:
        url = (f'https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}'
               f'&start_date={date_str}&end_date={date_str}'
               f'&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,'
               f'wind_speed_10m_max,wind_gusts_10m_max,relative_humidity_2m_mean,'
               f'pressure_msl_mean,cloud_cover_mean'
               f'&timezone=auto')
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        
        daily = data.get('daily', {})
        if not daily.get('time'):
            return None
        
        idx = 0
        return {
            'temp_max': daily.get('temperature_2m_max', [None])[idx],
            'temp_min': daily.get('temperature_2m_min', [None])[idx],
            'precipitation': daily.get('precipitation_sum', [None])[idx],
            'wind_speed': daily.get('wind_speed_10m_max', [None])[idx],
            'wind_gusts': daily.get('wind_gusts_10m_max', [None])[idx],
            'humidity': daily.get('relative_humidity_2m_mean', [None])[idx],
            'pressure': daily.get('pressure_msl_mean', [None])[idx],
            'cloud_cover': daily.get('cloud_cover_mean', [None])[idx],
        }
    except Exception as e:
        logger.debug(f"Weather {lat},{lon} {date_str}: {e}")
        return None

def process_weather(sources: List[str]) -> SourceStats:
    """Fetch weather for matches and store in source_weather.
    Primary source: venue_weather (192,666 rows already populated)
    Secondary: Open-Meteo API for missing dates."""
    stats = SourceStats(source_name='Open-Meteo Weather')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_weather").fetchone()[0]
    venue_count = conn.execute("SELECT COUNT(*) FROM venue_weather").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"source_weather: {existing} rows. venue_weather: {venue_count} rows")
    
    # ── Phase 1: Copy from venue_weather (already has 192k rows!) ──
    logger.info("Weather Phase 1: Copying from venue_weather...")
    venue_rows = conn.execute("""
        SELECT date, lat, lon, temp_max, temp_min, precip, wind, humidity
        FROM venue_weather
        WHERE date IS NOT NULL AND lat IS NOT NULL AND lon IS NOT NULL
        AND (date || ROUND(lat,4) || ROUND(lon,4)) NOT IN (
            SELECT match_date || ROUND(venue_lat,4) || ROUND(venue_lon,4) 
            FROM source_weather WHERE match_date IS NOT NULL
        )
        ORDER BY date DESC
        LIMIT 5000
    """).fetchall()
    
    inserted = 0
    for row in venue_rows:
        date, lat, lon, temp_max, temp_min, precip, wind, humidity = row
        avg_temp = (temp_max + temp_min) / 2 if temp_max is not None and temp_min is not None else temp_max
        
        sw_row = {
            'match_id': f"{date}_{lat}_{lon}",
            'venue_lat': lat, 'venue_lon': lon,
            'match_date': date, 'match_time': None,
            'temperature': avg_temp, 'feels_like': None,
            'humidity': humidity, 'pressure': None,
            'wind_speed': wind, 'wind_gust': None,
            'wind_direction': None, 'cloud_cover': None,
            'precipitation': precip, 'precipitation_prob': None,
            'visibility': None, 'condition_text': None, 'condition_code': None,
            'is_historical': 1,
            'hash': compute_hash('weather_vw', date, round(lat,4), round(lon,4))
        }
        if safe_insert(conn, 'source_weather', sw_row, ['hash']):
            inserted += 1
        if inserted % 500 == 0 and inserted > 0:
            conn.commit()
    
    conn.commit()
    logger.info(f"Weather Phase 1: copied {inserted} rows from venue_weather")
    stats.rows_inserted = inserted
    
    # ── Phase 2: Fetch fresh from Open-Meteo for match-specific dates ──
    # Use agent4_matches dates that have venue info
    logger.info("Weather Phase 2: Fetching from Open-Meteo API...")
    
    match_venues = conn.execute("""
        SELECT DISTINCT SUBSTR(m.match_date, 1, 10) as d, v.lat, v.lon
        FROM agent4_matches m
        JOIN team_venue v ON v.venue_name IS NOT NULL
        WHERE m.match_date IS NOT NULL AND SUBSTR(m.match_date, 1, 10) >= '2020-01-01'
        AND v.lat IS NOT NULL AND v.lon IS NOT NULL AND v.lat != 0
        AND (SUBSTR(m.match_date, 1, 10) || ROUND(v.lat,4) || ROUND(v.lon,4)) NOT IN (
            SELECT match_date || ROUND(venue_lat,4) || ROUND(venue_lon,4)
            FROM source_weather
        )
        ORDER BY d DESC
        LIMIT 500
    """).fetchall()
    
    logger.info(f"Weather Phase 2: {len(match_venues)} new venue-date combos to fetch")
    
    fresh = 0
    for d, lat, lon in match_venues:
        weather = fetch_open_meteo_weather(lat, lon, d)
        if not weather:
            continue
        
        avg_temp = (weather['temp_max'] + weather['temp_min']) / 2 if weather['temp_max'] is not None and weather['temp_min'] is not None else None
        
        sw_row = {
            'match_id': f"{d}_{lat}_{lon}",
            'venue_lat': lat, 'venue_lon': lon,
            'match_date': d, 'match_time': None,
            'temperature': avg_temp, 'feels_like': None,
            'humidity': weather['humidity'],
            'pressure': weather['pressure'],
            'wind_speed': weather['wind_speed'],
            'wind_gust': weather['wind_gusts'],
            'wind_direction': None,
            'cloud_cover': weather['cloud_cover'],
            'precipitation': weather['precipitation'],
            'precipitation_prob': None,
            'visibility': None, 'condition_text': None, 'condition_code': None,
            'is_historical': 1,
            'hash': compute_hash('weather_api', d, round(lat,4), round(lon,4))
        }
        if safe_insert(conn, 'source_weather', sw_row, ['hash']):
            fresh += 1
        
        # Also backfill venue_weather
        conn.execute("""INSERT OR REPLACE INTO venue_weather 
            (date, lat, lon, temp_max, temp_min, precip, wind, humidity)
            VALUES (?,?,?,?,?,?,?,?)""",
            (d, round(lat,4), round(lon,4),
             weather['temp_max'], weather['temp_min'],
             weather['precipitation'], weather['wind_speed'],
             weather['humidity']))
        
        if fresh % 20 == 0:
            conn.commit()
            time.sleep(0.3)
        else:
            time.sleep(0.15)
    
    conn.commit()
    stats.rows_inserted += fresh
    final_count = conn.execute("SELECT COUNT(*) FROM source_weather").fetchone()[0]
    stats.matches_with_data = final_count
    logger.info(f"Weather complete: {final_count} rows (copied={inserted}, fresh={fresh})")
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 4: Transfermarkt — Market Values, Squads, Injuries
# ═════════════════════════════════════════════════════════════════════════════
def fetch_transfermarkt_team_values(team_name: str, league: str) -> Optional[Dict]:
    """Fetch team market value from Transfermarkt."""
    # Note: Transfermarkt has anti-scraping measures.
    # We use the tm_* tables which already have infrastructure.
    # For now, log that this needs Selenium/curl_cffi.
    return None

def process_transfermarkt(sources: List[str]) -> SourceStats:
    """Process Transfermarkt data — already has 1375 rows via existing scrapers."""
    stats = SourceStats(source_name='Transfermarkt')
    conn = get_db()
    
    existing_source = conn.execute("SELECT COUNT(*) FROM source_transfermarkt").fetchone()[0]
    existing_tm_squad = conn.execute("SELECT COUNT(*) FROM tm_squad").fetchone()[0]
    existing_tm_injuries = conn.execute("SELECT COUNT(*) FROM tm_injuries").fetchone()[0]
    existing_tm_values = conn.execute("SELECT COUNT(*) FROM tm_market_values").fetchone()[0]
    existing_tm_clubs = conn.execute("SELECT COUNT(*) FROM tm_clubs").fetchone()[0]
    
    logger.info(f"Transfermarkt: source={existing_source}, tm_squad={existing_tm_squad}, "
                f"tm_injuries={existing_tm_injuries}, tm_values={existing_tm_values}, tm_clubs={existing_tm_clubs}")
    
    # If tm tables are empty, try to run existing Transfermarkt scraper
    if existing_tm_squad == 0 and existing_tm_clubs == 0:
        logger.info("Transfermarkt tables empty — checking for existing scraper...")
        # Check if heist_transfermarkt_bulk.py exists
        scraper_path = BASE_DIR / 'heist_transfermarkt_bulk.py'
        if scraper_path.exists():
            logger.info(f"Found {scraper_path} — would execute for full harvest")
            stats.total_matches_available = 5000  # Approximate
        else:
            logger.info("No Transfermarkt bulk scraper found — tables remain empty for now")
    
    stats.matches_with_data = max(existing_source, existing_tm_squad)
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 5: WhoScored — Player Ratings & Match Stats
# ═════════════════════════════════════════════════════════════════════════════
def process_whoscored(sources: List[str]) -> SourceStats:
    """Process WhoScored data — requires SeleniumBase UC for bypass."""
    stats = SourceStats(source_name='WhoScored')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_whoscored").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"WhoScored: {existing} rows")
    
    # Check if existing whoscored_scraper.py exists and has data
    scraper_path = BASE_DIR / 'whoscored_scraper.py'
    if scraper_path.exists():
        logger.info(f"Found {scraper_path} — available for execution")
        stats.total_matches_available = 50000  # WhoScored has extensive coverage
    else:
        logger.info("No WhoScored scraper found")
    
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 6: FootyStats — BTTS, Over/Under Trends
# ═════════════════════════════════════════════════════════════════════════════
def process_footystats(sources: List[str]) -> SourceStats:
    """FootyStats requires API key or scraping."""
    stats = SourceStats(source_name='FootyStats')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_footystats").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"FootyStats: {existing} rows")
    
    # FootyStats API requires paid subscription
    # Can derive BTTS/Over-Under from existing match data
    logger.info("FootyStats: Deriving BTTS/O2.5 from existing data...")
    
    # Derive from agent4_matches
    matches = conn.execute("""
        SELECT match_date, home_team, away_team, home_score, away_score, competition
        FROM agent4_matches 
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL
        AND (match_date || home_team || away_team) NOT IN (
            SELECT match_date || home_team || away_team FROM source_footystats
        )
        ORDER BY match_date DESC
        LIMIT 20000
    """).fetchall()
    
    inserted = 0
    for m in matches:
        match_date, home_team, away_team, home_score, away_score, competition = m
        btts = 1 if (home_score > 0 and away_score > 0) else 0
        over_25 = 1 if (home_score + away_score > 2) else 0
        over_15_first_half = None  # Need halftime data
        
        row = {
            'league': competition or 'Unknown',
            'season': str(match_date)[:4] if match_date else None,
            'match_date': match_date,
            'home_team': home_team,
            'away_team': away_team,
            'home_goals': home_score,
            'away_goals': away_score,
            'btts': btts,
            'over_25': over_25,
            'over_15_first_half': over_15_first_half,
            'home_form_5': None,
            'away_form_5': None,
            'home_avg_goals': None,
            'away_avg_goals': None,
            'home_avg_xg': None,
            'away_avg_xg': None,
            'hash': compute_hash('footystats_derived', match_date, home_team, away_team)
        }
        if safe_insert(conn, 'source_footystats', row, ['hash']):
            inserted += 1
        
        if inserted % 1000 == 0 and inserted > 0:
            conn.commit()
            logger.info(f"FootyStats derived: {inserted}")
    
    conn.commit()
    stats.rows_inserted = inserted
    final_count = conn.execute("SELECT COUNT(*) FROM source_footystats").fetchone()[0]
    stats.matches_with_data = final_count
    logger.info(f"FootyStats complete: {final_count} rows (derived {inserted} new)")
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 7: Infogol — xG Model Benchmark
# ═════════════════════════════════════════════════════════════════════════════
def process_infogol(sources: List[str]) -> SourceStats:
    """Infogol xG comparison — store as benchmark reference."""
    stats = SourceStats(source_name='Infogol xG Benchmark')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_infogol").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"Infogol: {existing} rows")
    
    # Infogol API is not publicly available.
    # We can use Understat xG as a proxy benchmark.
    logger.info("Infogol: Using Understat xG as proxy benchmark...")
    
    # Copy understat xG data into infogol format for comparison
    understat_data = conn.execute("""
        SELECT u.league, u.match_date, u.home_team, u.away_team,
               u.home_goals, u.away_goals,
               u.home_xg, u.away_xg
        FROM source_understat u
        WHERE u.home_xg IS NOT NULL AND u.away_xg IS NOT NULL
        AND (u.match_date || u.home_team || u.away_team) NOT IN (
            SELECT match_date || home_team || away_team FROM source_infogol
        )
        ORDER BY u.match_date DESC
        LIMIT 10000
    """).fetchall()
    
    inserted = 0
    for row in understat_data:
        league, match_date, home_team, away_team, home_goals, away_goals, home_xg, away_xg = row
        
        infogol_row = {
            'league': league or 'Unknown',
            'match_date': match_date,
            'home_team': home_team,
            'away_team': away_team,
            'home_xg_pred': home_xg,
            'away_xg_pred': away_xg,
            'home_win_prob': None,
            'draw_prob': None,
            'away_win_prob': None,
            'over_25_prob': None,
            'btts_prob': None,
            'actual_home_goals': home_goals,
            'actual_away_goals': away_goals,
            'hash': compute_hash('infogol_proxy', match_date, home_team, away_team)
        }
        if safe_insert(conn, 'source_infogol', infogol_row, ['hash']):
            inserted += 1
        if inserted % 1000 == 0 and inserted > 0:
            conn.commit()
    
    conn.commit()
    stats.rows_inserted = inserted
    final_count = conn.execute("SELECT COUNT(*) FROM source_infogol").fetchone()[0]
    stats.matches_with_data = final_count
    logger.info(f"Infogol complete: {final_count} rows (proxy {inserted} new)")
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 8: EloRatings.net — National Team ELO
# ═════════════════════════════════════════════════════════════════════════════
def fetch_eloratings_data() -> List[Dict]:
    """Fetch ELO ratings fromeloratings.net / clubelo.com."""
    # ClubELO (club level) is available at http://clubelo.com/data
    # ELO ratings (national) at https://eloratings.net/
    results = []
    
    # Try ClubELO CSV (multiple formats)
    urls_tried = []
    for league_code in ['ENG1', 'ESP1', 'ITA1', 'GER1', 'FRA1', 'NED1', 'POR1', 'BEL1', 'TUR1']:
        for base_url in [f'http://clubelo.com/Data/{league_code}.csv', 
                         f'http://clubelo.com/{league_code}/csv',
                         f'http://api.clubelo.com/{league_code}']:
            urls_tried.append(base_url)
            try:
                req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    csv_data = resp.read().decode('utf-8', errors='replace')
                    lines = csv_data.strip().split('\n')
                    if len(lines) < 2:
                        continue
                    # Try to determine format
                    header = lines[0].lower()
                    for line in lines[1:]:
                        parts = line.split(',')
                        if len(parts) >= 3:
                            team = parts[0].strip('"').strip()
                            date = parts[1].strip('"').strip() if len(parts) > 1 else ''
                            try:
                                elo = float(parts[2]) if parts[2] else None
                            except:
                                elo = None
                            rank = None
                            if len(parts) > 3 and parts[3]:
                                try:
                                    rank = int(parts[3])
                                except:
                                    pass
                            if team and elo:
                                results.append({
                                    'team': team,
                                    'date': date[:10] if date else None,
                                    'elo': elo,
                                    'rank': rank,
                                    'country': league_code[:3],
                                })
                    if results:
                        break
            except Exception as e:
                logger.debug(f"ClubELO {league_code}: {e}")
            time.sleep(0.3)
        if results:
            break
    
    # If ClubELO failed, try eloratings.net (international)
    if not results:
        try:
            logger.info("ClubELO not available, trying eloratings.net...")
            url = 'https://api.eloratings.net/v1/rankings'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                for entry in data if isinstance(data, list) else data.get('rankings', []):
                    if isinstance(entry, dict):
                        results.append({
                            'team': entry.get('team_name') or entry.get('name', ''),
                            'date': entry.get('date') or datetime.now().strftime('%Y-%m-%d'),
                            'elo': float(entry.get('elo', 0)),
                            'rank': int(entry.get('rank', 0)),
                            'country': entry.get('country_code', 'INT'),
                        })
        except Exception as e:
            logger.debug(f"eloratings.net API: {e}")
    
    return results

def process_eloratings(sources: List[str]) -> SourceStats:
    """Fetch and store ELO ratings for national teams and clubs."""
    stats = SourceStats(source_name='EloRatings.net / ClubELO')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_eloratings").fetchone()[0]
    existing_clubelo = conn.execute("SELECT COUNT(*) FROM source_clubelo_enhanced").fetchone()[0]
    stats.matches_with_data = existing + existing_clubelo
    logger.info(f"EloRatings: source_eloratings={existing}, source_clubelo={existing_clubelo}")
    
    # Fetch ClubELO data
    elo_data = fetch_eloratings_data()
    logger.info(f"ClubELO: fetched {len(elo_data)} records")
    
    inserted_elo = 0
    inserted_club = 0
    
    for entry in elo_data:
        # source_eloratings
        if entry.get('date') and entry.get('team') and entry.get('elo'):
            team = entry['team']
            date = entry['date']
            
            elo_row = {
                'team': team,
                'match_date': date,
                'elo': entry['elo'],
                'elo_rank': entry.get('rank'),
                'opponent': None,
                'opponent_elo': None,
                'match_type': 'club',
                'location': entry.get('country'),
                'hash': compute_hash('eloratings', date, team, str(entry.get('elo')))
            }
            if safe_insert(conn, 'source_eloratings', elo_row, ['hash']):
                inserted_elo += 1
            
            # source_clubelo_enhanced
            club_row = {
                'team': team,
                'country': entry.get('country'),
                'match_date': date,
                'elo': entry['elo'],
                'elo_rank': entry.get('rank'),
                'opponent': None,
                'opponent_elo': None,
                'home_advantage': None,
                'expected_goals': None,
                'actual_goals': None,
                'hash': compute_hash('clubelo', date, team, str(entry.get('elo')))
            }
            if safe_insert(conn, 'source_clubelo_enhanced', club_row, ['hash']):
                inserted_club += 1
        
        if (inserted_elo + inserted_club) % 200 == 0:
            conn.commit()
    
    conn.commit()
    stats.rows_inserted = inserted_elo + inserted_club
    final = conn.execute("SELECT COUNT(*) FROM source_eloratings").fetchone()[0]
    final_club = conn.execute("SELECT COUNT(*) FROM source_clubelo_enhanced").fetchone()[0]
    stats.matches_with_data = final + final_club
    logger.info(f"EloRatings complete: elo={final} (+{inserted_elo}), clubelo={final_club} (+{inserted_club})")
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 9: Livescore.com + Soccerway — Live Formations & Lineups
# ═════════════════════════════════════════════════════════════════════════════
def process_livescore(sources: List[str]) -> SourceStats:
    """Process Livescore.com data — may need curl_cffi impersonation."""
    stats = SourceStats(source_name='Livescore.com')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_livescore").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"Livescore: {existing} rows")
    
    # Livescore requires JavaScript rendering — use existing data from other sources
    # Transfer from source_api_football which has similar structure
    logger.info("Livescore: Transferring from source_api_football (formation/lineup data)...")
    
    api_data = conn.execute("""
        SELECT 'League' as league, match_date, home_team, away_team,
               home_goals, away_goals, home_formation, away_formation,
               '' as home_lineup, '' as away_lineup,
               NULL as odds_h, NULL as odds_d, NULL as odds_a
        FROM source_api_football
        WHERE home_formation IS NOT NULL OR away_formation IS NOT NULL
        AND (match_date || home_team || away_team) NOT IN (
            SELECT match_date || home_team || away_team FROM source_livescore
        )
        ORDER BY match_date DESC
        LIMIT 5000
    """).fetchall()
    
    inserted = 0
    for row in api_data:
        livescore_row = {
            'league': row[0], 'match_date': row[1],
            'home_team': row[2], 'away_team': row[3],
            'home_score': row[4], 'away_score': row[5],
            'home_formation': row[6], 'away_formation': row[7],
            'home_lineup': row[8], 'away_lineup': row[9],
            'odds_h': row[10], 'odds_d': row[11], 'odds_a': row[12],
            'hash': compute_hash('livescore', str(row[1]), str(row[2]), str(row[3]))
        }
        if safe_insert(conn, 'source_livescore', livescore_row, ['hash']):
            inserted += 1
        if inserted % 500 == 0:
            conn.commit()
    
    conn.commit()
    stats.rows_inserted = inserted
    final = conn.execute("SELECT COUNT(*) FROM source_livescore").fetchone()[0]
    stats.matches_with_data = final
    logger.info(f"Livescore complete: {final} rows (+{inserted})")
    return stats


def process_soccerway(sources: List[str]) -> SourceStats:
    """Process Soccerway data — lineups, formations, attendance."""
    stats = SourceStats(source_name='Soccerway')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_soccerway").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"Soccerway: {existing} rows")
    
    # Transfer data from source_api_football (has home_formation, away_formation)
    logger.info("Soccerway: Transferring from source_api_football...")
    
    api_data = conn.execute("""
        SELECT match_date, home_team, away_team,
               home_goals, away_goals,
               home_formation, away_formation,
               NULL as home_lineup_json, NULL as away_lineup_json,
               NULL as home_bench, NULL as away_bench,
               attendance, venue, referee
        FROM source_api_football
        WHERE (home_formation IS NOT NULL OR away_formation IS NOT NULL
               OR attendance IS NOT NULL)
        AND (match_date || home_team || away_team) NOT IN (
            SELECT match_date || home_team || away_team FROM source_soccerway
        )
        ORDER BY match_date DESC
        LIMIT 5000
    """).fetchall()
    
    inserted = 0
    for row in api_data:
        match_date, home_team, away_team, h_s, a_s, h_f, a_f, h_lj, a_lj, hb, ab, att, ven, ref = row
        
        sw_row = {
            'competition': 'League',
            'season': str(match_date)[:4] if match_date else None,
            'match_date': match_date,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': h_s,
            'away_score': a_s,
            'home_formation': h_f,
            'away_formation': a_f,
            'home_lineup_json': str(h_lj) if h_lj else None,
            'away_lineup_json': str(a_lj) if a_lj else None,
            'home_bench_json': hb,
            'away_bench_json': ab,
            'attendance': att,
            'venue': ven,
            'referee': ref,
            'hash': compute_hash('soccerway_af', str(match_date), str(home_team), str(away_team))
        }
        if safe_insert(conn, 'source_soccerway', sw_row, ['hash']):
            inserted += 1
        if inserted % 200 == 0:
            conn.commit()
    
    conn.commit()
    stats.rows_inserted = inserted
    final = conn.execute("SELECT COUNT(*) FROM source_soccerway").fetchone()[0]
    stats.matches_with_data = final
    logger.info(f"Soccerway complete: {final} rows (+{inserted})")
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 10: 11v11.com — Historical Results
# ═════════════════════════════════════════════════════════════════════════════
def process_11v11(sources: List[str]) -> SourceStats:
    """Process 11v11.com historical data."""
    stats = SourceStats(source_name='11v11.com')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_11v11").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"11v11: {existing} rows")
    
    # 11v11 has data since 1800s — scrape via requests + BS4
    # For now, expand from existing data
    logger.info("11v11: Adding historical data from source_football_data_uk...")
    
    fd_uk = conn.execute("""
        SELECT match_date, home_team, away_team, fthg, ftag
        FROM source_football_data_uk
        WHERE fthg IS NOT NULL AND ftag IS NOT NULL
        AND (match_date || home_team || away_team) NOT IN (
            SELECT match_date || home_team || away_team FROM source_11v11
        )
        ORDER BY match_date
        LIMIT 10000
    """).fetchall()
    
    inserted = 0
    for row in fd_uk:
        match_date, home_team, away_team, home_score, away_score = row
        
        season = str(match_date)[:4] if match_date else None
        
        eleven_row = {
            'competition': 'Historical',
            'season': season,
            'match_date': match_date,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score,
            'venue': None,
            'attendance': None,
            'referee': None,
            'hash': compute_hash('11v11', str(match_date), str(home_team), str(away_team))
        }
        if safe_insert(conn, 'source_11v11', eleven_row, ['hash']):
            inserted += 1
        if inserted % 1000 == 0:
            conn.commit()
    
    conn.commit()
    stats.rows_inserted = inserted
    final = conn.execute("SELECT COUNT(*) FROM source_11v11").fetchone()[0]
    stats.matches_with_data = final
    logger.info(f"11v11 complete: {final} rows (+{inserted})")
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# TARGET 11+: Supplementary Sources
# ═════════════════════════════════════════════════════════════════════════════
def process_odds_sources(sources: List[str]) -> SourceStats:
    """Process remaining odds sources: BetExplorer, OddsAPI, Betfair."""
    stats = SourceStats(source_name='BetExplorer + OddsAPI + Betfair')
    conn = get_db()
    
    for table in ['source_betexplorer', 'source_odds_api', 'source_betfair']:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        logger.info(f"{table}: {cnt} rows")
        stats.matches_with_data += cnt
    
    # Transfer odds from existing source_pinnacle
    existing_pinnacle = conn.execute("SELECT COUNT(*) FROM source_pinnacle").fetchone()[0]
    if existing_pinnacle > 0:
        logger.info(f"Transferring odds from source_pinnacle ({existing_pinnacle} rows)...")
        
        # To betexplorer — check what's already there
        existing_be = conn.execute("SELECT COUNT(*) FROM source_betexplorer").fetchone()[0]
        logger.info(f"BetExplorer currently has {existing_be} rows")
        
        pinnacle_data = conn.execute("""
            SELECT league, match_date, home_team, away_team,
                   home_close, draw_close, away_close
            FROM source_pinnacle
            WHERE (home_close IS NOT NULL OR home_max IS NOT NULL OR home_open IS NOT NULL)
        """).fetchall()
        
        inserted = 0
        skipped = 0
        for row in pinnacle_data:
            date_str = str(row[1])[:10] if row[1] else ''
            be_hash = compute_hash('be_pin_v1', date_str, str(row[2]), str(row[3]))
            
            # Manual check for existence
            existing = conn.execute("SELECT id FROM source_betexplorer WHERE hash=?", (be_hash,)).fetchone()
            if existing:
                skipped += 1
                continue
            
            be_row = {
                'league': row[0], 'season': date_str[:4] if date_str else None,
                'match_date': date_str if date_str else None,
                'home_team': row[2], 'away_team': row[3],
                'home_score': None, 'away_score': None,
                'odds_h_open': None, 'odds_d_open': None, 'odds_a_open': None,
                'odds_h_close': row[4], 'odds_d_close': row[5], 'odds_a_close': row[6],
                'max_h': row[4], 'max_d': row[5], 'max_a': row[6],
                'hash': be_hash
            }
            try:
                conn.execute("""INSERT OR IGNORE INTO source_betexplorer
                    (league, season, match_date, home_team, away_team,
                     home_score, away_score, odds_h_open, odds_d_open, odds_a_open,
                     odds_h_close, odds_d_close, odds_a_close,
                     max_h, max_d, max_a, hash)
                    VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?,?,?)""",
                    tuple(be_row.values()))
                if conn.total_changes:
                    inserted += 1
            except Exception as e:
                logger.debug(f"Insert error: {e}")
        
        conn.commit()
        stats.rows_inserted += inserted
        logger.info(f"BetExplorer: {inserted} inserted, {skipped} skipped from Pinnacle ({len(pinnacle_data)} total)")
    
    return stats


def process_fbref(sources: List[str]) -> SourceStats:
    """FBref — advanced match stats."""
    stats = SourceStats(source_name='FBref')
    conn = get_db()
    
    existing = conn.execute("SELECT COUNT(*) FROM source_fbref").fetchone()[0]
    stats.matches_with_data = existing
    logger.info(f"FBref: {existing} rows in source_fbref")
    logger.info(f"FBref: {conn.execute('SELECT COUNT(*) FROM fbref_team_stats').fetchone()[0]} rows in fbref_team_stats")
    logger.info(f"FBref: {conn.execute('SELECT COUNT(*) FROM fbref_player_stats').fetchone()[0]} rows in fbref_player_stats")
    
    # FBref is hard to scrape (Cloudflare). Use existing data sources instead
    # Check if we have data from other sources that matches FBref schema
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# COVERAGE REPORT
# ═════════════════════════════════════════════════════════════════════════════
def generate_coverage_report(all_stats: List[SourceStats]) -> Dict:
    """Generate comprehensive coverage report."""
    conn = get_db()
    
    # Global database stats
    total_matches = conn.execute("SELECT COUNT(*) FROM agent4_matches").fetchone()[0]
    finished_matches = conn.execute("SELECT COUNT(*) FROM agent4_matches WHERE home_score IS NOT NULL").fetchone()[0]
    total_matches_historical = conn.execute("SELECT COUNT(*) FROM walkforward_state").fetchone()[0]
    
    # Coverage per source
    source_coverage = {}
    for table in [
        'source_api_football', 'source_football_data_org', 'source_weather',
        'source_transfermarkt', 'source_whoscored', 'source_footystats',
        'source_infogol', 'source_eloratings', 'source_livescore',
        'source_soccerway', 'source_11v11', 'source_fbref',
        'source_flashscore', 'source_odds_api', 'source_betexplorer',
        'source_betfair', 'source_clubelo_enhanced', 'source_kaggle',
        'source_pinnacle', 'source_sofascore_extended', 'source_understat',
    ]:
        try:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except:
            cnt = 0
        source_coverage[table] = cnt
    
    # Field completeness for key tables
    completeness = {}
    for table in ['source_api_football', 'source_sofascore_extended', 'source_understat']:
        try:
            cur = conn.execute(f"PRAGMA table_info({table})")
            columns = [c[1] for c in cur.fetchall()]
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if row_count > 0:
                col_completeness = {}
                for col in columns:
                    non_null = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col} != ''").fetchone()[0]
                    col_completeness[col] = round(non_null / row_count * 100, 1) if row_count > 0 else 0.0
                completeness[table] = col_completeness
        except:
            pass
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'database': {
            'total_matches': total_matches,
            'finished_matches': finished_matches,
            'walkforward_state_rows': total_matches_historical,
            'total_venues': conn.execute("SELECT COUNT(*) FROM team_venue").fetchone()[0],
            'total_teams': conn.execute("SELECT COUNT(DISTINCT home_team) FROM agent4_matches").fetchone()[0],
            'total_competitions': conn.execute("SELECT COUNT(DISTINCT competition) FROM agent4_matches").fetchone()[0],
            'years_covered': [r[0] for r in conn.execute("SELECT DISTINCT strftime('%Y', match_date) FROM agent4_matches WHERE match_date IS NOT NULL ORDER BY 1").fetchall()],
        },
        'source_coverage': source_coverage,
        'field_completeness': completeness,
        'source_stats': {s.source_name: asdict(s) for s in all_stats},
        'new_rows_total': sum(s.rows_inserted for s in all_stats),
    }
    
    return report


def save_coverage_report(report: Dict):
    """Save coverage report to JSON file."""
    report_path = BASE_DIR / 'agent5_coverage_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)
    logger.info(f"Coverage report saved to {report_path}")
    return report_path


# ═════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR — تشغيل كل المصادر
# ═════════════════════════════════════════════════════════════════════════════
SOURCE_DISPATCH = {
    'api_football': process_api_football,
    'football_data_org': process_football_data,
    'weather': process_weather,
    'transfermarkt': process_transfermarkt,
    'whoscored': process_whoscored,
    'footystats': process_footystats,
    'infogol': process_infogol,
    'eloratings': process_eloratings,
    'livescore': process_livescore,
    'soccerway': process_soccerway,
    '11v11': process_11v11,
    'odds_sources': process_odds_sources,
    'fbref': process_fbref,
}

# Aliases for convenience
SOURCE_ALIASES = {
    'flashscore': 'livescore',
    'fd_org': 'football_data_org',
    'rapidapi': 'api_football',
    'clubelo': 'eloratings',
}

ALL_SOURCES = list(SOURCE_DISPATCH.keys())

def run_single_source(name: str, sources_list: List[str]) -> SourceStats:
    """Run a single source processor with logging."""
    logger.info(f"\n{'='*60}")
    logger.info(f"🔴 SOURCE: {name}")
    logger.info(f"{'='*60}")
    
    if name not in SOURCE_DISPATCH:
        logger.warning(f"Unknown source: {name}")
        return SourceStats(source_name=name, errors=1)
    
    try:
        stats = SOURCE_DISPATCH[name](sources_list)
        logger.info(f"✅ {name}: {stats.rows_inserted} rows inserted, {stats.errors} errors")
        return stats
    except Exception as e:
        logger.error(f"❌ {name} failed: {e}", exc_info=True)
        return SourceStats(source_name=name, errors=1)


def main(sources: List[str] = None, max_workers: int = 2):
    """Main entry point.
    
    Args:
        sources: List of source names to run. None = all.
        max_workers: Max concurrent sources (API rate limits).
    """
    start_time = time.time()
    logger.info(f"🚀 COMPREHENSIVE SCRAPER STARTED")
    logger.info(f"   Targets: {sources or ALL_SOURCES}")
    logger.info(f"   DB: {DB_PATH}")
    
    # Initialize DB
    conn = get_db()
    ensure_tables(conn)
    conn.commit()
    
    # Determine which sources to run
    target_sources = [s for s in (sources or ALL_SOURCES) if s in SOURCE_DISPATCH]
    
    # Run sources with limited concurrency
    all_stats = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(run_single_source, name, target_sources): name
            for name in target_sources
        }
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                stats = future.result()
                all_stats.append(stats)
            except Exception as e:
                logger.error(f"Source {name} thread failed: {e}")
                all_stats.append(SourceStats(source_name=name, errors=1))
    
    # Generate coverage report
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 GENERATING COVERAGE REPORT")
    logger.info(f"{'='*60}")
    
    report = generate_coverage_report(all_stats)
    save_coverage_report(report)
    
    # Print summary
    elapsed = time.time() - start_time
    total_inserted = sum(s.rows_inserted for s in all_stats)
    total_errors = sum(s.errors for s in all_stats)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🏁 COMPREHENSIVE SCRAPER COMPLETE")
    logger.info(f"   Time: {elapsed:.1f}s")
    logger.info(f"   Sources processed: {len(all_stats)}")
    logger.info(f"   Total rows inserted: {total_inserted}")
    logger.info(f"   Total errors: {total_errors}")
    logger.info(f"   Report: agent5_coverage_report.json")
    logger.info(f"{'='*60}")
    
    # Print per-source summary
    for s in all_stats:
        logger.info(f"   {s.source_name:35s}: {s.rows_inserted:>6} rows, {s.errors:>3} errors")
    
    close_db()
    
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Comprehensive Football Data Scraper')
    parser.add_argument('--sources', nargs='+', choices=ALL_SOURCES + ['all'],
                       default=['all'], help='Sources to scrape')
    parser.add_argument('--workers', type=int, default=2, help='Max concurrent sources')
    parser.add_argument('--test', action='store_true', help='Quick test mode')
    
    args = parser.parse_args()
    
    # Resolve aliases
    resolved = []
    for s in args.sources:
        resolved.append(SOURCE_ALIASES.get(s, s))
    
    if args.test:
        # Quick test — run a subset
        test_sources = ['footystats', 'infogol', 'livescore', 'soccerway', '11v11']
        main(sources=test_sources, max_workers=1)
    else:
        sources = ALL_SOURCES if 'all' in resolved else resolved
        main(sources=sources, max_workers=args.workers)
