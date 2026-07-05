#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              DB MERGER — unify ALL scraped data into main DB              ▓
▓  Handles deduplication, normalization, cross-referencing, team mapping    ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, re, sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Set
from pathlib import Path

from eternal_harvester_config import DB_PATH, LOGS_DIR, get_db, log_event

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_FILE = LOGS_DIR / 'db_merger.log'


def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [DB-MERGER] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('db_merger', level, msg)


# ─── Team name normalization ────────────────────────────────────────────────
TEAM_ALIASES: Dict[str, str] = {
    # English league common variations
    'Man City': 'Manchester City', 'Manchester City FC': 'Manchester City',
    'Man United': 'Manchester United', 'Manchester Utd': 'Manchester United',
    'Manchester United FC': 'Manchester United',
    "Nott'm Forest": 'Nottingham Forest',
    'Nottingham Forest FC': 'Nottingham Forest',
    'Newcastle Utd': 'Newcastle United', 'Newcastle United FC': 'Newcastle United',
    'Sheffield Utd': 'Sheffield United', 'Sheffield United FC': 'Sheffield United',
    'Sheffield Wed': 'Sheffield Wednesday',
    'West Ham': 'West Ham United', 'West Ham United FC': 'West Ham United',
    'Wolverhampton': 'Wolves', 'Wolverhampton Wanderers': 'Wolves',
    'Brighton': 'Brighton & Hove Albion', 'Brighton & Hove Albion FC': 'Brighton & Hove Albion',
    'Leicester City FC': 'Leicester City',
    'Tottenham': 'Tottenham Hotspur', 'Tottenham Hotspur FC': 'Tottenham Hotspur',
    'AFC Bournemouth': 'Bournemouth',
    'Ipswich Town FC': 'Ipswich Town',
    'Brentford FC': 'Brentford',
    'Crystal Palace FC': 'Crystal Palace',
    'Everton FC': 'Everton',
    'Fulham FC': 'Fulham',
    'Liverpool FC': 'Liverpool',
    'Southampton FC': 'Southampton',
    'Wolves': 'Wolverhampton Wanderers',
    # Spanish
    'FC Barcelona': 'Barcelona', 'Barcelona FC': 'Barcelona',
    'Real Madrid CF': 'Real Madrid',
    'Atlético Madrid': 'Atletico Madrid', 'Club Atlético de Madrid': 'Atletico Madrid',
    'Athletic Club': 'Athletic Bilbao', 'Athletic Bilbao': 'Athletic Club',
    'Valencia CF': 'Valencia',
    'Sevilla FC': 'Sevilla',
    'Real Betis Balompié': 'Real Betis',
    'Villarreal CF': 'Villarreal',
    # German
    'FC Bayern München': 'Bayern Munich', 'Bayern München': 'Bayern Munich',
    'Borussia Dortmund': 'Borussia Dortmund',
    'RB Leipzig': 'RB Leipzig',
    'Bayer 04 Leverkusen': 'Bayer Leverkusen',
    'Eintracht Frankfurt': 'Eintracht Frankfurt',
    'VfB Stuttgart': 'VfB Stuttgart',
    'Borussia Mönchengladbach': 'Borussia Monchengladbach',
    # Italian
    'AC Milan': 'AC Milan', 'Milan': 'AC Milan',
    'FC Internazionale Milano': 'Inter Milan', 'Inter': 'Inter Milan',
    'Juventus FC': 'Juventus',
    'AS Roma': 'Roma', 'Roma': 'Roma',
    'SSC Napoli': 'Napoli',
    'ACF Fiorentina': 'Fiorentina',
    # French
    'Paris Saint Germain': 'Paris Saint-Germain',
    'Olympique de Marseille': 'Marseille', 'OM': 'Marseille',
    'Olympique Lyonnais': 'Lyon',
    'AS Monaco FC': 'Monaco',
    'Stade Rennais FC': 'Rennes',
    'FC Nantes': 'Nantes',
    # Dutch
    'AFC Ajax': 'Ajax',
    'Feyenoord Rotterdam': 'Feyenoord',
    'PSV Eindhoven': 'PSV',
    # Portuguese
    'SL Benfica': 'Benfica',
    'FC Porto': 'Porto',
    'Sporting CP': 'Sporting Lisbon',
    # Turkish
    'Galatasaray AŞ': 'Galatasaray',
    'Fenerbahçe AŞ': 'Fenerbahce',
    'Beşiktaş AŞ': 'Besiktas',
    # Brazilian/Argentine
    'CR Flamengo': 'Flamengo',
    'SC Corinthians': 'Corinthians',
    'São Paulo FC': 'Sao Paulo',
    'CA Boca Juniors': 'Boca Juniors',
    'CA River Plate': 'River Plate',
    # Remove FC/SC suffixes
    'FC': '',
    'SC': '',
    'AFC': '',
    'CF': '',
}

# Cross-source team mapping table
def build_team_mapping() -> int:
    """Build and update the team_name_mapping table across all sources.

    Uses football-data.co.uk names as canonical (most consistent).
    Maps: sofa_name, fbref_name, transfermarkt_name, etc.
    """
    conn = get_db()
    mapped = 0

    # Get all team names from football-data.co.uk (canonical)
    fd_teams = set()
    try:
        cur = conn.execute(
            'SELECT DISTINCT home_team FROM football_data_matches '
            'UNION SELECT DISTINCT away_team FROM football_data_matches'
        )
        fd_teams = set(r[0] for r in cur.fetchall() if r[0])
    except Exception:
        pass

    _log(f'Canonical (football-data.co.uk) teams: {len(fd_teams)}')

    # Get all SofaScore team names
    sofa_teams = set()
    try:
        cur = conn.execute(
            'SELECT DISTINCT home_team FROM sofa_historical_results '
            'UNION SELECT DISTINCT away_team FROM sofa_historical_results'
        )
        sofa_teams = set(r[0] for r in cur.fetchall() if r[0])
    except Exception:
        pass

    _log(f'SofaScore teams: {len(sofa_teams)}')

    # Get Understat teams
    understat_teams = set()
    try:
        cur = conn.execute(
            'SELECT DISTINCT home_team FROM understat_matches '
            'UNION SELECT DISTINCT away_team FROM understat_matches'
        )
        understat_teams = set(r[0] for r in cur.fetchall() if r[0])
    except Exception:
        pass

    # Get FBref teams
    fbref_teams = set()
    try:
        cur = conn.execute('SELECT DISTINCT team FROM fbref_team_stats')
        fbref_teams = set(r[0] for r in cur.fetchall() if r[0])
    except Exception:
        pass

    # Get Transfermarkt teams
    tm_teams = set()
    try:
        cur = conn.execute('SELECT DISTINCT club_name FROM tm_clubs')
        tm_teams = set(r[0] for r in cur.fetchall() if r[0])
    except Exception:
        pass

    # Get Flashscore teams
    fs_teams = set()
    try:
        cur = conn.execute(
            'SELECT DISTINCT home_team FROM flashscore_matches '
            'UNION SELECT DISTINCT away_team FROM flashscore_matches'
        )
        fs_teams = set(r[0] for r in cur.fetchall() if r[0])
    except Exception:
        pass

    # Get OddsPortal teams
    op_teams = set()
    try:
        cur = conn.execute(
            'SELECT DISTINCT home_team FROM oddsportal_matches '
            'UNION SELECT DISTINCT away_team FROM oddsportal_matches'
        )
        op_teams = set(r[0] for r in cur.fetchall() if r[0])
    except Exception:
        pass

    all_insource_teams = set()
    all_insource_teams.update(sofa_teams)
    all_insource_teams.update(understat_teams)
    all_insource_teams.update(fbref_teams)
    all_insource_teams.update(tm_teams)
    all_insource_teams.update(fs_teams)
    all_insource_teams.update(op_teams)

    # For each SofaScore team, try to map to canonical football-data name
    for sofa_team in all_insource_teams:
        if not sofa_team:
            continue

        # Normalize
        clean = _normalize_team_name(sofa_team)
        if not clean:
            continue

        # Check if it matches any canonical team
        best_match = None
        best_score = 0

        for fd_team in fd_teams:
            fd_clean = _normalize_team_name(fd_team)
            if not fd_clean:
                continue

            # Exact match
            if clean.lower() == fd_clean.lower():
                best_match = fd_team
                best_score = 1.0
                break

            # Partial match
            score = _team_similarity(clean, fd_clean)
            if score > best_score and score > 0.7:
                best_score = score
                best_match = fd_team

        # Use alias dictionary
        if not best_match:
            for alias, canonical in TEAM_ALIASES.items():
                if clean.lower() == alias.lower() or sofa_team.lower() == alias.lower():
                    best_match = canonical
                    best_score = 0.95
                    break

        # Use cleaned name as fallback
        if not best_match:
            best_match = clean
            best_score = 0.5

        # Save to mapping table
        if best_match:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO team_name_mapping
                        (fd_name, sofa_name, confidence)
                    VALUES (?, ?, ?)
                ''', (best_match, sofa_team, best_score))
                mapped += 1
            except Exception:
                pass

    conn.commit()

    # Also generate reverse mapping (fd_name for queries)
    _log(f'Team mapping entries: {mapped}')

    conn.close()
    return mapped


def _normalize_team_name(name: str) -> str:
    """Normalize team name for comparison."""
    if not name:
        return ''
    name = name.strip()
    # Remove common suffixes
    name = re.sub(r'\s*(FC|AFC|CF|SC|AS|AC|SS|EC|CR|CA|CD|SD|UD|AD|AE|AA|AO|SE|GE)\s*$', '', name)
    name = re.sub(r'\s*(FC|AFC|CF|SC|AS|AC|SS|EC|CR|CA|CD|SD|UD|AD|AE|AA|AO|SE|GE)\s', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^\w\s\-]', '', name)
    return name.strip()


def _team_similarity(a: str, b: str) -> float:
    """Compute similarity between two team names (0-1)."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()

    if a_lower == b_lower:
        return 1.0

    # Check if one contains the other
    if len(a_lower) >= 4 and a_lower in b_lower:
        return 0.85
    if len(b_lower) >= 4 and b_lower in a_lower:
        return 0.85

    # Token-based
    a_tokens = set(a_lower.split())
    b_tokens = set(b_lower.split())
    if not a_tokens or not b_tokens:
        return 0.0

    intersection = a_tokens & b_tokens
    union = a_tokens | b_tokens
    jaccard = len(intersection) / len(union) if union else 0.0

    return jaccard


# ─── Football-data.co.uk → sofa_historical_results merger ──────────────────
def merge_football_data_to_sofa() -> int:
    """Merge football_data_matches into sofa_historical_results.

    This cross-references via the team_name_mapping table.
    """
    conn = get_db()
    merged = 0
    skipped = 0
    errors = 0

    # Get all football-data matches not yet merged
    rows = conn.execute('''
        SELECT fd.id, fd.date, fd.home_team, fd.away_team, 
               fd.home_goals, fd.away_goals
        FROM football_data_matches fd
        WHERE fd.home_goals IS NOT NULL AND fd.away_goals IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM sofa_historical_results s
              WHERE s.home_score = fd.home_goals
                AND s.away_score = fd.away_goals
                AND s.date = fd.date
                AND (
                    s.home_team = fd.home_team 
                    OR EXISTS (SELECT 1 FROM team_name_mapping tm 
                               WHERE tm.sofa_name = s.home_team AND tm.fd_name = fd.home_team)
                )
          )
    ''').fetchall()

    _log(f'Football-data matches to merge: {len(rows)}')

    for row in rows:
        try:
            _, date, home_team, away_team, home_goals, away_goals = row
            if not all([date, home_team, away_team]):
                skipped += 1
                continue

            # Check if this match already exists in sofa_historical_results
            # by date and team name (try canonical mapping first)
            mapped_home = conn.execute(
                'SELECT sofa_name FROM team_name_mapping WHERE fd_name = ?',
                (home_team,)
            ).fetchone()
            mapped_away = conn.execute(
                'SELECT sofa_name FROM team_name_mapping WHERE fd_name = ?',
                (away_team,)
            ).fetchone()

            sofa_home = mapped_home[0] if mapped_home else home_team
            sofa_away = mapped_away[0] if mapped_away else away_team

            # Insert into sofa_historical_results with a negative ID to avoid conflict
            max_id = conn.execute('SELECT COALESCE(MAX(id), 0) FROM sofa_historical_results').fetchone()[0]
            new_id = - (max_id + merged + 1)

            conn.execute('''
                INSERT OR IGNORE INTO sofa_historical_results
                    (id, home_team, away_team, home_score, away_score,
                     date, status_type, start_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, 'finished', ?)
            ''', (new_id, sofa_home, sofa_away, home_goals, away_goals,
                  date, int(datetime.strptime(date, '%Y-%m-%d').timestamp()) if '-' in date else 0))
            merged += 1

        except Exception as e:
            _log(f'Merge error: {e}', 'ERROR')
            errors += 1

    conn.commit()
    _log(f'Football-data → Sofa: {merged} merged, {skipped} skipped, {errors} errors')
    conn.close()
    return merged


# ─── Understat → sofa_match_stats merger ────────────────────────────────────
def merge_understat_stats() -> int:
    """Merge Understat xG data into sofa_match_stats."""
    conn = get_db()
    merged = 0

    rows = conn.execute('''
        SELECT um.id, um.home_team, um.away_team, um.date, 
               um.home_xg, um.away_xg, um.home_goals, um.away_goals
        FROM understat_matches um
        WHERE NOT EXISTS (
            SELECT 1 FROM sofa_historical_results s
            WHERE s.home_score = um.home_goals 
              AND s.away_score = um.away_goals
              AND s.date = um.date
              AND s.id NOT IN (SELECT event_id FROM sofa_match_stats WHERE home_xg IS NOT NULL)
        )
    ''').fetchall()

    for row in rows:
        try:
            understat_id, home_team, away_team, date, home_xg, away_xg, hg, ag = row
            # Find matching sofa match
            sofa_match = conn.execute('''
                SELECT id FROM sofa_historical_results
                WHERE home_score = ? AND away_score = ? AND date = ?
                  AND (home_team = ? OR home_team = ?)
                  AND (away_team = ? OR away_team = ?)
                LIMIT 1
            ''', (hg, ag, date, home_team, home_team, away_team, away_team)).fetchone()

            if sofa_match:
                event_id = sofa_match[0]
                conn.execute('''
                    INSERT OR REPLACE INTO sofa_match_stats
                        (event_id, home_xg, away_xg)
                    VALUES (?, ?, ?)
                ''', (event_id, home_xg, away_xg))
                merged += 1

        except Exception as e:
            _log(f'Understat merge error: {e}', 'WARN')

    conn.commit()
    _log(f'Understat xG merged into {merged} sofa matches')
    conn.close()
    return merged


# ─── FBref → fbref_cache merger ────────────────────────────────────────────
def merge_fbref_stats() -> int:
    """Ensure FBref team stats are normalized into fbref_cache for quick lookup."""
    conn = get_db()
    merged = 0
    now = time.time()

    rows = conn.execute('''
        SELECT team, season, xg, npxg, possession, progressive_passes,
               shots_total, shots_sot, gk_save_pct, mp
        FROM fbref_team_stats
    ''').fetchall()

    for row in rows:
        team, season, xg, npxg, poss, prog_passes, shots, sot, gk_save, mp = row
        stats_to_cache = {
            'xg': xg, 'npxg': npxg, 'possession': poss,
            'progressive_passes': prog_passes, 'shots_total': shots,
            'shots_sot': sot, 'gk_save_pct': gk_save, 'mp': mp,
        }

        for stat_name, stat_val in stats_to_cache.items():
            if stat_val is not None:
                try:
                    conn.execute('''
                        INSERT OR REPLACE INTO fbref_cache (team, season, stat, value, updated)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (team, season, stat_name, float(stat_val), now))
                    merged += 1
                except Exception:
                    pass

    conn.commit()
    _log(f'FBref stats cached: {merged} entries')
    conn.close()
    return merged


# ─── Transfermarkt → player_roster merger ──────────────────────────────────
def merge_transfermarkt_squad() -> int:
    """Merge Transfermarkt squad data into player_roster."""
    conn = get_db()
    merged = 0

    rows = conn.execute('''
        SELECT ts.player_name, tc.club_name, ts.position, ts.age, ts.market_value
        FROM tm_squad ts
        JOIN tm_clubs tc ON ts.club_id = tc.club_id
        WHERE ts.player_name IS NOT NULL AND ts.player_name != ''
    ''').fetchall()

    for row in rows:
        player_name, club_name, position, age, market_value = row
        try:
            # Check if player exists
            existing = conn.execute(
                'SELECT player_name FROM player_roster WHERE player_name = ? AND team_name = ?',
                (player_name, club_name)
            ).fetchone()

            if not existing:
                pos_code = 0  # Default/unknown
                if position:
                    pos_lower = position.lower()
                    if 'goalkeeper' in pos_lower or 'gk' in pos_lower or 'goalie' in pos_lower:
                        pos_code = 1
                    elif 'defender' in pos_lower or 'def' in pos_lower or 'back' in pos_lower or 'centre-back' in pos_lower:
                        pos_code = 2
                    elif 'midfielder' in pos_lower or 'mid' in pos_lower or 'midfield' in pos_lower:
                        pos_code = 3
                    elif 'forward' in pos_lower or 'striker' in pos_lower or 'fw' in pos_lower or 'attack' in pos_lower:
                        pos_code = 4

                conn.execute('''
                    INSERT OR REPLACE INTO player_roster
                        (player_id, player_name, team_name, position, starts, subs, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (hash(player_name + club_name) % (2**31), player_name,
                      club_name, pos_code, 0, 0, datetime.now().isoformat()))
                merged += 1
        except Exception as e:
            _log(f'TM squad merge error: {e}', 'WARN')

    conn.commit()
    _log(f'Transfermarkt → player_roster: {merged} new players')
    conn.close()
    return merged


def merge_transfermarkt_injuries() -> int:
    """Merge Transfermarkt injury data into agent5_heist_injuries."""
    conn = get_db()
    merged = 0

    rows = conn.execute('''
        SELECT ti.player_name, ti.club_id, ti.injury_type, ti.return_date
        FROM tm_injuries ti
    ''').fetchall()

    for row in rows:
        player_name, club_id, injury_type, return_date = row
        try:
            conn.execute('''
                INSERT OR REPLACE INTO agent5_heist_injuries
                    (club_id, player_name, injury_type, return_date, fetched_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (club_id or 0, player_name, injury_type or 'Unknown',
                  return_date or '', time.time()))
            merged += 1
        except Exception:
            pass

    conn.commit()
    _log(f'Transfermarkt → injuries: {merged} entries')
    conn.close()
    return merged


# ─── Flashscore → sofa tables merger ───────────────────────────────────────
def merge_flashscore_matches() -> int:
    """Merge Flashscore match data into sofa_historical_results."""
    conn = get_db()
    merged = 0

    rows = conn.execute('''
        SELECT fsm.match_id, fsm.home_team, fsm.away_team, 
               fsm.home_score, fsm.away_score, fsm.ts
        FROM flashscore_matches fsm
        WHERE fsm.home_score IS NOT NULL AND fsm.home_score != ''
          AND fsm.away_score IS NOT NULL AND fsm.away_score != ''
    ''').fetchall()

    for row in rows:
        try:
            mid, home, away, hs, aw, ts = row
            if not home or not away:
                continue

            # Parse scores
            try:
                home_goals = int(hs)
                away_goals = int(aw)
            except (ValueError, TypeError):
                continue

            # Check if already exists
            existing = conn.execute('''
                SELECT id FROM sofa_historical_results
                WHERE home_team = ? AND away_team = ? AND home_score = ? AND away_score = ?
                LIMIT 1
            ''', (home, away, home_goals, away_goals)).fetchone()

            if not existing:
                max_id = conn.execute('SELECT COALESCE(MAX(id), 0) FROM sofa_historical_results').fetchone()[0]
                new_id = -(max_id + merged + 10000)

                conn.execute('''
                    INSERT OR IGNORE INTO sofa_historical_results
                        (id, home_team, away_team, home_score, away_score,
                         date, status_type)
                    VALUES (?, ?, ?, ?, ?, ?, 'finished')
                ''', (new_id, home, away, home_goals, away_goals, ts or ''))
                merged += 1

        except Exception as e:
            _log(f'Flashscore merge error: {e}', 'WARN')

    conn.commit()
    _log(f'Flashscore → sofa: {merged} matches merged')
    conn.close()
    return merged


# ─── OddsPortal → odds movement merger ─────────────────────────────────────
def merge_oddsportal_movements() -> int:
    """Merge OddsPortal odds movement data into odds_cache and existing tables."""
    conn = get_db()
    merged = 0
    now = time.time()

    # Get movements
    rows = conn.execute('''
        SELECT oom.match_url, oom.timestamp, oom.home_odds, 
               oom.draw_odds, oom.away_odds, oom.bookmaker
        FROM oddsportal_odds_snapshots oom
    ''').fetchall()

    for row in rows:
        try:
            url, ts, h_odds, d_odds, a_odds, bookmaker = row
            cache_key = f'oddsportal_{bookmaker}_{url}_{ts}'

            # Save to odds_cache
            conn.execute('''
                INSERT OR REPLACE INTO odds_cache (url, data, updated)
                VALUES (?, ?, ?)
            ''', (cache_key, json.dumps({
                'match': url, 'timestamp': ts,
                '1': h_odds, 'X': d_odds, '2': a_odds,
                'bookmaker': bookmaker,
            }), now))
            merged += 1
        except Exception:
            pass

    conn.commit()
    _log(f'OddsPortal → odds_cache: {merged} entries')
    conn.close()
    return merged


# ─── Weather → walkforward integration ─────────────────────────────────────
def merge_weather_into_walkforward() -> int:
    """Integrate weather data into existing walkforward_state features.

    This is done at prediction time, but we log what's available.
    """
    conn = get_db()
    merged = 0

    try:
        # Count weather entries not yet linked to venues
        cnt = conn.execute('''
            SELECT COUNT(*) FROM weather_cache wc
            LEFT JOIN venue_weather vw ON wc.lat = vw.lat AND wc.lon = vw.lon
            WHERE vw.venue_name IS NULL
        ''').fetchone()[0]
        merged = cnt
    except Exception:
        pass

    _log(f'Unlinked weather entries: {merged}')
    conn.close()
    return merged


# ─── Full merger ────────────────────────────────────────────────────────────
def run_all_merges() -> Dict:
    """Run all merge operations and return stats."""
    start_time = time.time()
    stats = {}

    _log('=== RUNNING ALL DB MERGES ===')

    # 1. Team name mapping (foundation for everything else)
    _log('1. Building team name mapping...')
    stats['team_mapping'] = build_team_mapping()

    # 2. football-data → sofa_historical_results
    _log('2. Merging football-data.co.uk → sofa...')
    stats['fd_to_sofa'] = merge_football_data_to_sofa()

    # 3. Understat → sofa_match_stats
    _log('3. Merging Understat xG → match stats...')
    stats['understat_to_stats'] = merge_understat_stats()

    # 4. FBref → cache
    _log('4. Merging FBref → cache...')
    stats['fbref_to_cache'] = merge_fbref_stats()

    # 5. Transfermarkt → player_roster
    _log('5. Merging Transfermarkt squad → player roster...')
    stats['tm_to_roster'] = merge_transfermarkt_squad()

    # 6. Transfermarkt → injuries
    _log('6. Merging Transfermarkt injuries...')
    stats['tm_to_injuries'] = merge_transfermarkt_injuries()

    # 7. Flashscore → sofa
    _log('7. Merging Flashscore matches → sofa...')
    stats['flashscore_to_sofa'] = merge_flashscore_matches()

    # 8. OddsPortal → odds_cache
    _log('8. Merging OddsPortal odds movements...')
    stats['oddsportal_to_cache'] = merge_oddsportal_movements()

    # 9. Weather venue linking
    _log('9. Checking weather venue links...')
    stats['weather_unlinked'] = merge_weather_into_walkforward()

    duration = time.time() - start_time
    total_merged = sum(stats.values())
    _log(f'=== ALL MERGES COMPLETE: {total_merged} total operations, {duration:.1f}s ===')

    stats['duration_seconds'] = duration

    return {'source': 'db_merger', 'stats': stats}


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='DB Merger - unify all scraped data')
    parser.add_argument('--all', action='store_true', help='Run all merges')
    parser.add_argument('--teams', action='store_true', help='Build team mapping only')
    parser.add_argument('--fd', action='store_true', help='Merge football-data → sofa')
    parser.add_argument('--understat', action='store_true', help='Merge Understat xG')
    parser.add_argument('--fbref', action='store_true', help='Merge FBref cache')
    parser.add_argument('--tm-squad', action='store_true', help='Merge TM squad')
    parser.add_argument('--tm-injuries', action='store_true', help='Merge TM injuries')
    parser.add_argument('--flashscore', action='store_true', help='Merge Flashscore')
    parser.add_argument('--oddsportal', action='store_true', help='Merge OddsPortal')
    args = parser.parse_args()

    if args.all or not any([args.teams, args.fd, args.understat, args.fbref,
                            args.tm_squad, args.tm_injuries, args.flashscore,
                            args.oddsportal]):
        result = run_all_merges()
        print(json.dumps(result, indent=2, default=str))
    else:
        sub_results = {}
        if args.teams: sub_results['team_mapping'] = build_team_mapping()
        if args.fd: sub_results['fd_to_sofa'] = merge_football_data_to_sofa()
        if args.understat: sub_results['understat'] = merge_understat_stats()
        if args.fbref: sub_results['fbref'] = merge_fbref_stats()
        if args.tm_squad: sub_results['tm_squad'] = merge_transfermarkt_squad()
        if args.tm_injuries: sub_results['tm_injuries'] = merge_transfermarkt_injuries()
        if args.flashscore: sub_results['flashscore'] = merge_flashscore_matches()
        if args.oddsportal: sub_results['oddsportal'] = merge_oddsportal_movements()
        print(json.dumps(sub_results, indent=2, default=str))
