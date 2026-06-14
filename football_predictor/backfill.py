"""
730-day SofaScore historical backfill — collects match results + stats
Resumable: skips already-collected event IDs
Rate-limited: ~2 req/sec, runs in ~1 min for results + ~20 min for stats
"""
import os, sys, time, json, sqlite3
from datetime import datetime, timedelta
from curl_cffi import requests as curl_requests

SOFA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36 Chrome/120.0.6099.230 Mobile Safari/537.36',
    'Accept': 'application/json', 'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/', 'x-requested-with': '721637',
}
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
BASE = 'https://www.sofascore.com/api/v1'
_last_req = 0

def _rate_limit():
    global _last_req
    now = time.time()
    if now - _last_req < 0.5:
        time.sleep(0.5 - (now - _last_req))
    _last_req = time.time()

def _get(path):
    _rate_limit()
    try:
        r = curl_requests.get(f'{BASE}{path}', headers=SOFA_HEADERS, impersonate='chrome120', timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS sofa_historical_results (
            id INTEGER PRIMARY KEY,
            home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            tournament TEXT, unique_tournament_id INTEGER,
            season_id INTEGER, start_timestamp INTEGER,
            status_type TEXT, date TEXT,
            UNIQUE(id)
        );
        CREATE TABLE IF NOT EXISTS sofa_match_stats (
            event_id INTEGER PRIMARY KEY,
            home_xg REAL, away_xg REAL,
            home_shots INTEGER, away_shots INTEGER,
            home_sot INTEGER, away_sot INTEGER,
            home_possession REAL, away_possession REAL,
            home_corners INTEGER, away_corners INTEGER,
            home_fouls INTEGER, away_fouls INTEGER,
            raw_json TEXT
        );
        CREATE TABLE IF NOT EXISTS backfill_progress (
            date TEXT PRIMARY KEY,
            status TEXT,
            matches_found INTEGER
        );
    ''')
    conn.commit()
    conn.close()

def collect_results(days_back=730):
    """Collect finished match results from last N days. Resumable."""
    conn = sqlite3.connect(DB)
    init_db()
    today = datetime.now()
    total_new = 0
    total_days = 0

    for i in range(days_back):
        date_obj = today - timedelta(days=i)
        date_str = date_obj.strftime('%Y-%m-%d')
        cur = conn.execute('SELECT status FROM backfill_progress WHERE date = ?', (date_str,))
        row = cur.fetchone()
        if row and row[0] == 'done':
            continue
        data = _get(f'/sport/football/scheduled-events/{date_str}')
        if not data or 'events' not in data:
            conn.execute('INSERT OR REPLACE INTO backfill_progress VALUES (?, ?, ?)',
                         (date_str, 'no_data', 0))
            conn.commit()
            continue
        count = 0
        for e in data['events']:
            if e.get('status', {}).get('type') != 'finished':
                continue
            hs = (e.get('homeScore') or {}).get('display')
            aws = (e.get('awayScore') or {}).get('display')
            if hs is None or aws is None:
                continue
            eid = e.get('id')
            home = (e.get('homeTeam') or {}).get('name', '')
            away = (e.get('awayTeam') or {}).get('name', '')
            tournament = e.get('tournament', {})
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO sofa_historical_results
                    (id, home_team, away_team, home_score, away_score,
                     tournament, unique_tournament_id, season_id,
                     start_timestamp, status_type, date)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ''', (eid, home, away, int(hs), int(aws),
                      tournament.get('name', ''), tournament.get('uniqueTournament', {}).get('id'),
                      tournament.get('season', {}).get('id'), e.get('startTimestamp'),
                      e.get('status', {}).get('type'), date_str))
                count += 1
            except:
                pass
        conn.execute('INSERT OR REPLACE INTO backfill_progress VALUES (?, ?, ?)',
                     (date_str, 'done', count))
        conn.commit()
        total_new += count
        total_days += 1
        if total_days % 50 == 0:
            print(f"[Backfill] {date_str}: {count} matches ({total_new} total new)")

    total = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
    conn.close()
    print(f"[Backfill] Done. {total_new} new, {total} total matches in DB.")
    return total

def collect_stats(limit_events=None):
    """Fetch /event/{id}/statistics for finished matches that lack stats."""
    conn = sqlite3.connect(DB)
    init_db()
    query = '''SELECT r.id FROM sofa_historical_results r
               LEFT JOIN sofa_match_stats s ON r.id = s.event_id
               WHERE s.event_id IS NULL ORDER BY r.start_timestamp DESC'''
    cur = conn.execute(query)
    event_ids = [row[0] for row in cur.fetchall()]
    if limit_events:
        event_ids = event_ids[:limit_events]
    print(f"[Stats] Fetching stats for {len(event_ids)} events...")
    fetched = 0
    for eid in event_ids:
        data = _get(f'/match/{eid}/statistics')
        if not data:
            continue
        groups = data.get('statistics', []) if 'statistics' in data else (data.get('groups', data) if isinstance(data, dict) else [])
        home_xg = away_xg = None
        home_shots = away_shots = None
        home_sot = away_sot = None
        home_poss = away_poss = None
        home_corners = away_corners = None
        home_fouls = away_fouls = None
        if isinstance(groups, list):
            for group in groups:
                items = group.get('statisticsItems', []) if isinstance(group, dict) else group
                if not isinstance(items, list):
                    items = []
                for item in items:
                    name = (item.get('name') or '').lower() if isinstance(item, dict) else ''
                    h_val = item.get('home') if isinstance(item, dict) else None
                    a_val = item.get('away') if isinstance(item, dict) else None
                    if name == 'expected goals':
                        home_xg = _parse_num(h_val)
                        away_xg = _parse_num(a_val)
                    elif name == 'total shots':
                        home_shots = _parse_int(h_val)
                        away_shots = _parse_int(a_val)
                    elif name == 'shots on target':
                        home_sot = _parse_int(h_val)
                        away_sot = _parse_int(a_val)
                    elif name == 'ball possession':
                        home_poss = _parse_num(h_val)
                        away_poss = _parse_num(a_val)
                    elif name == 'corner kicks':
                        home_corners = _parse_int(h_val)
                        away_corners = _parse_int(a_val)
                    elif name == 'fouls':
                        home_fouls = _parse_int(h_val)
                        away_fouls = _parse_int(a_val)
        try:
            conn.execute('''
                INSERT OR REPLACE INTO sofa_match_stats
                (event_id, home_xg, away_xg, home_shots, away_shots,
                 home_sot, away_sot, home_possession, away_possession,
                 home_corners, away_corners, home_fouls, away_fouls, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (eid, home_xg, away_xg, home_shots, away_shots,
                  home_sot, away_sot, home_poss, away_poss,
                  home_corners, away_corners, home_fouls, away_fouls,
                  json.dumps(data, default=str)))
            fetched += 1
            conn.commit()
        except:
            pass
        if fetched % 200 == 0:
            print(f"[Stats] {fetched}/{len(event_ids)}")
    total = conn.execute('SELECT COUNT(*) FROM sofa_match_stats').fetchone()[0]
    conn.close()
    print(f"[Stats] Done. {fetched} new, {total} total match stats in DB.")
    return total

def _parse_num(v):
    if v is None:
        return None
    try:
        s = str(v).replace('%', '').replace(',', '.')
        return round(float(s), 2)
    except:
        return float(v) if v else None

def _parse_int(v):
    if v is None:
        return None
    try:
        return int(v)
    except:
        return int(float(v)) if v else None

def main():
    print("=== SofaScore Backfill ===")
    init_db()
    n = collect_results(730)
    print(f"[Backfill] Results done: {n} matches collected")
    print("[Backfill] Skipping stats collection (too slow). Can run separately: collect_stats()")
    print(f"Results: {n} matches")

if __name__ == '__main__':
    main()
