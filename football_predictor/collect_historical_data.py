"""
Historical Data Collector for Score Exact 100
Collects match data from StatsBomb, FBref, and BSD for training/evaluation.
"""
import os, json, time, sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__) or '.', 'historical_data.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT UNIQUE,
            date TEXT, home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            source TEXT,
            xg_home REAL, xg_away REAL,
            possession_home REAL, possession_away REAL,
            shots_home INTEGER, shots_away INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date)
    """)
    conn.commit()
    conn.close()

def collect_statsbomb():
    """Collect match data from StatsBomb Open Data"""
    try:
        from statsbombpy import sb
        print("[StatsBomb] Fetching competitions...")
        comps = sb.competitions()
        print(f"[StatsBomb] Found {len(comps)} competitions")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        total = 0
        for _, comp in comps.iterrows():
            comp_id = comp['competition_id']
            season_id = comp['season_id']
            print(f"[StatsBomb] Competition {comp_id} season {season_id}: {comp.get('competition_name', '')}")
            try:
                matches = sb.matches(competition_id=comp_id, season_id=season_id)
                if matches.empty:
                    continue
                for _, m in matches.iterrows():
                    match_id = f"sb_{comp_id}_{season_id}_{m['match_id']}"
                    home = m.get('home_team', '')
                    away = m.get('away_team', '')
                    hs = m.get('home_score')
                    ac = m.get('away_score')
                    if not home or not away:
                        continue
                    xg_h, xg_a = None, None
                    try:
                        events = sb.events(match_id=m['match_id'])
                        if not events.empty and 'shot_statsbomb_xg' in events.columns:
                            xg_h = events[events['team'] == home]['shot_statsbomb_xg'].sum()
                            xg_a = events[events['team'] == away]['shot_statsbomb_xg'].sum()
                    except:
                        pass
                    cur.execute("""
                        INSERT OR IGNORE INTO matches
                        (match_id, date, home_team, away_team, home_score, away_score, source, xg_home, xg_away)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (match_id, m.get('match_date', '')[:10], home, away, int(hs) if hs else 0, int(ac) if ac else 0,
                           'statsbomb', float(xg_h) if xg_h else None, float(xg_a) if xg_a else None))
                    total += 1
                conn.commit()
            except Exception as e:
                print(f"[StatsBomb] Error: {e}")
                continue
        conn.close()
        print(f"[StatsBomb] Saved {total} matches")
    except ImportError:
        print("[StatsBomb] statsbombpy not installed. Skipping.")
    except Exception as e:
        print(f"[StatsBomb] Failed: {e}")

def collect_fbref(leagues=None, seasons=None):
    """Collect match data from FBref via soccerdata"""
    if leagues is None:
        leagues = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A", "GER-Bundesliga", "FRA-Ligue 1"]
    if seasons is None:
        seasons = [2025, 2024, 2023]
    try:
        import soccerdata as sd
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        total = 0
        for league in leagues:
            for season in seasons:
                print(f"[FBref] {league} {season}...")
                try:
                    fbref = sd.FBref(leagues=league, seasons=season)
                    sched = fbref.read_schedule()
                    if sched is None or sched.empty:
                        continue
                    for _, m in sched.iterrows():
                        home = m.get('home', '')
                        away = m.get('away', '')
                        hs = m.get('home_score', m.get('score_home'))
                        ac = m.get('away_score', m.get('score_away'))
                        if not home or not away or hs is None or ac is None:
                            continue
                        match_id = f"fb_{league}_{season}_{home}_{away}".replace(' ', '_')
                        cur.execute("""
                            INSERT OR IGNORE INTO matches
                            (match_id, date, home_team, away_team, home_score, away_score, source)
                            VALUES (?,?,?,?,?,?,?)
                        """, (match_id, str(m.get('date', ''))[:10], home, away, int(hs), int(ac), 'fbref'))
                        total += 1
                    conn.commit()
                except Exception as e:
                    print(f"[FBref] Error {league}/{season}: {e}")
                    continue
        conn.close()
        print(f"[FBref] Saved {total} matches")
    except ImportError:
        print("[FBref] soccerdata not installed. Skipping.")

def collect_bsd():
    """Collect match data from BSD API"""
    key = os.environ.get('BSD_API_KEY', '')
    if not key:
        print("[BSD] No API key. Skipping.")
        return
    headers = {'Authorization': f'Token {key}'}
    base = 'https://sports.bzzoiro.com/api/v2'
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total = 0
    try:
        import requests
        for page in range(1, 6):  # 5 pages max
            url = f"{base}/events/?status=finished&limit=50&page={page}"
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            results = data.get('results', [])
            if not results:
                break
            for ev in results:
                hs = ev.get('home_score')
                ac = ev.get('away_score')
                match_id = f"bsd_{ev.get('id')}"
                cur.execute("""
                    INSERT OR IGNORE INTO matches
                    (match_id, date, home_team, away_team, home_score, away_score, source)
                    VALUES (?,?,?,?,?,?,?)
                """, (match_id, ev.get('event_date', '')[:10], ev.get('home_team', ''),
                       ev.get('away_team', ''), int(hs) if hs else 0, int(ac) if ac else 0, 'bsd'))
                total += 1
            conn.commit()
            time.sleep(0.5)  # rate limit
    except Exception as e:
        print(f"[BSD] Error: {e}")
    conn.close()
    print(f"[BSD] Saved {total} matches")

def summary():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT source, COUNT(*) FROM matches GROUP BY source")
    rows = cur.fetchall()
    print("\n=== Historical Data Summary ===")
    for source, count in rows:
        print(f"  {source}: {count} matches")
    cur.execute("SELECT COUNT(*) FROM matches")
    total = cur.fetchone()[0]
    print(f"  TOTAL: {total} matches")
    conn.close()

if __name__ == '__main__':
    init_db()
    print("=== Historical Data Collector ===")
    collect_statsbomb()
    collect_fbref()
    collect_bsd()
    summary()
    print("Done.")
