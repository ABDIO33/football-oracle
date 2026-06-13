import sqlite3
import os
import json
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__) or '.', 'elo.db')

K_FACTOR = 20
INITIAL_ELO = 1600
HOME_ADVANTAGE_ELO = 70


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS elo_ratings (
            team_name TEXT PRIMARY KEY,
            elo REAL NOT NULL,
            matches_played INTEGER DEFAULT 0,
            last_updated TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_matches (
            match_id INTEGER PRIMARY KEY,
            processed_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def expected_score(rating_a, rating_b):
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def _get_team_elo_from_db(team_name):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT elo FROM elo_ratings WHERE team_name = ?", (team_name,))
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return None


def _get_team_elo_from_teambd(team_name):
    try:
        from prediction_engine import TEAM_DB
        if team_name in TEAM_DB:
            return float(TEAM_DB[team_name][0])
    except Exception:
        pass
    return None


def get_elo(team_name):
    elo = _get_team_elo_from_db(team_name)
    if elo is not None:
        return elo
    elo = _get_team_elo_from_teambd(team_name)
    if elo is not None:
        return elo
    return INITIAL_ELO


def init_elo(team_name, competition=None):
    existing = _get_team_elo_from_db(team_name)
    if existing is not None:
        return existing
    elo = _get_team_elo_from_teambd(team_name)
    if elo is None:
        elo = INITIAL_ELO
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO elo_ratings (team_name, elo, matches_played, last_updated) VALUES (?, ?, 0, ?)",
            (team_name, elo, now)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    return elo


def update_elo(home_team, away_team, home_goals, away_goals, neutral_venue=False):
    home_elo = get_elo(home_team)
    away_elo = get_elo(away_team)
    if _get_team_elo_from_db(home_team) is None:
        home_elo = init_elo(home_team)
    if _get_team_elo_from_db(away_team) is None:
        away_elo = init_elo(away_team)
    home_advantage = 0 if neutral_venue else HOME_ADVANTAGE_ELO
    expected_home = expected_score(home_elo + home_advantage, away_elo)
    expected_away = 1.0 - expected_home
    if home_goals > away_goals:
        actual_home, actual_away = 1.0, 0.0
    elif home_goals == away_goals:
        actual_home, actual_away = 0.5, 0.5
    else:
        actual_home, actual_away = 0.0, 1.0
    new_home = home_elo + K_FACTOR * (actual_home - expected_home)
    new_away = away_elo + K_FACTOR * (actual_away - expected_away)
    home_change = new_home - home_elo
    away_change = new_away - away_elo
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO elo_ratings (team_name, elo, matches_played, last_updated) VALUES (?, ?, COALESCE((SELECT matches_played FROM elo_ratings WHERE team_name = ?), 0) + 1, ?)",
            (home_team, new_home, home_team, now)
        )
        cur.execute(
            "INSERT OR REPLACE INTO elo_ratings (team_name, elo, matches_played, last_updated) VALUES (?, ?, COALESCE((SELECT matches_played FROM elo_ratings WHERE team_name = ?), 0) + 1, ?)",
            (away_team, new_away, away_team, now)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    return {
        'home_elo': new_home,
        'away_elo': new_away,
        'home_change': home_change,
        'away_change': away_change,
    }


def _resolve_team_name_from_footballdb(team_id):
    try:
        fdb = os.path.join(os.path.dirname(__file__), 'football.db')
        if not os.path.exists(fdb):
            return None
        conn = sqlite3.connect(fdb)
        cur = conn.cursor()
        cur.execute("SELECT name FROM teams WHERE id = ?", (team_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return None


def run_historical_update():
    teams_updated = 0
    matches_processed = 0
    fdb = os.path.join(os.path.dirname(__file__), 'football.db')
    if not os.path.exists(fdb):
        return {'teams_updated': teams_updated, 'matches_processed': matches_processed}
    try:
        conn = sqlite3.connect(fdb)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
        if not cur.fetchone():
            conn.close()
            return {'teams_updated': teams_updated, 'matches_processed': matches_processed}
        cur.execute("""
            SELECT m.id, m.home_team_id, m.away_team_id, m.home_score, m.away_score,
                   m.utc_date, m.status, ht.name AS home_name, at.name AS away_name
            FROM matches m
            LEFT JOIN teams ht ON m.home_team_id = ht.id
            LEFT JOIN teams at ON m.away_team_id = at.id
            WHERE m.home_score IS NOT NULL AND m.away_score IS NOT NULL
              AND m.status IN ('FINISHED', 'FT', 'COMPLETED')
            ORDER BY m.utc_date ASC
        """)
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            match_id = row['id']
            home_name = row['home_name']
            away_name = row['away_name']
            home_goals = row['home_score']
            away_goals = row['away_score']
            if not home_name or not away_name:
                resolved_home = _resolve_team_name_from_footballdb(row['home_team_id'])
                resolved_away = _resolve_team_name_from_footballdb(row['away_team_id'])
                if not resolved_home or not resolved_away:
                    continue
                home_name = resolved_home
                away_name = resolved_away
            try:
                edb = sqlite3.connect(DB_PATH)
                ec = edb.cursor()
                ec.execute("SELECT 1 FROM processed_matches WHERE match_id = ?", (match_id,))
                if ec.fetchone():
                    edb.close()
                    continue
                edb.close()
            except Exception:
                pass
            try:
                result = update_elo(home_name, away_name, home_goals, away_goals)
                if result:
                    teams_updated += 2
                    matches_processed += 1
            except Exception:
                continue
            try:
                edb = sqlite3.connect(DB_PATH)
                ec = edb.cursor()
                ec.execute(
                    "INSERT OR IGNORE INTO processed_matches (match_id, processed_at) VALUES (?, ?)",
                    (match_id, datetime.now(timezone.utc).isoformat())
                )
                edb.commit()
                edb.close()
            except Exception:
                pass
    except Exception:
        pass
    return {'teams_updated': teams_updated, 'matches_processed': matches_processed}


def get_top_elo(limit=20):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT team_name, elo, matches_played FROM elo_ratings ORDER BY elo DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_all_ratings():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT team_name, elo FROM elo_ratings ORDER BY elo DESC")
        rows = cur.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}


if __name__ == '__main__':
    init_db()
    init_elo('Barcelona')
    init_elo('Real Madrid')
    result = update_elo('Barcelona', 'Real Madrid', 2, 1)
    print(f"Barcelona ELO: {result['home_elo']:.0f} ({result['home_change']:+.1f})")
    print(f"Real Madrid ELO: {result['away_elo']:.0f} ({result['away_change']:+.1f})")
