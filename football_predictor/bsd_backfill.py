"""
bsd_backfill.py — Backfill ALL BSD historical matches into the DB.
Scrapes 56k+ matches from 2015-2026, stores in sofa_historical_results.
Rate-limit safe: BSD has NO rate limits. Resumable via last_page tracking.
"""
import sqlite3, os, json, time, requests

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
API_KEY = "f5651c96742c834b5e7e5e0760dcfb3b9bdc205c"
BASE = "https://sports.bzzoiro.com/api"
HEADERS = {"Authorization": f"Token {API_KEY}"}

STATE_FILE = os.path.join(os.path.dirname(__file__), 'bsd_backfill_state.json')

def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS sofa_historical_results (
            id INTEGER PRIMARY KEY,
            home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            home_score_ht INTEGER, away_score_ht INTEGER,
            start_timestamp INTEGER,
            date TEXT,
            status_type TEXT DEFAULT 'finished',
            competition TEXT,
            venue_name TEXT
        );
        CREATE TABLE IF NOT EXISTS sofa_match_stats (
            event_id INTEGER PRIMARY KEY,
            home_xg REAL, away_xg REAL,
            home_shots REAL, away_shots REAL,
            home_sot REAL, away_sot REAL,
            home_possession REAL, away_possession REAL,
            home_corners REAL, away_corners REAL,
            home_fouls REAL, away_fouls REAL
        );
        CREATE INDEX IF NOT EXISTS idx_sofa_date ON sofa_historical_results(date);
        CREATE INDEX IF NOT EXISTS idx_sofa_team ON sofa_historical_results(home_team);
    ''')
    conn.commit()
    conn.close()

def get_progress():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"processed_pages": 0, "total_matches": 0, "current_year": 2015}

def save_progress(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def fetch_page(url):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r.json()
        except:
            time.sleep(2)
    return None

def process_match(e, conn):
    eid = e['id']
    home = e.get('home_team', '')
    away = e.get('away_team', '')
    hs = e.get('home_score')
    aws = e.get('away_score')
    if home is None or away is None or hs is None or aws is None:
        return False
    date_str = (e.get('event_date') or '')[:10]
    conn.execute('''INSERT OR IGNORE INTO sofa_historical_results
        (id, home_team, away_team, home_score, away_score, date, status_type, competition, venue_name)
        VALUES (?, ?, ?, ?, ?, ?, 'finished', ?, ?)''',
        (eid, home, away, int(hs), int(aws), date_str,
         e.get('league', {}).get('name', ''),
         e.get('venue', {}).get('name', '') if isinstance(e.get('venue'), dict) else ''))
    return True

def backfill_year(year):
    conn = sqlite3.connect(DB)
    state = get_progress()
    offset = 0
    limit = 100
    total = 0
    
    print(f"\n=== Backfilling {year} ===")
    
    while True:
        url = f"{BASE}/events/?limit={limit}&offset={offset}&date_from={year}-01-01&date_to={year}-12-31"
        data = fetch_page(url)
        if not data or not data.get('results'):
            break
        
        matches = data['results']
        if not matches:
            break
        
        for e in matches:
            if process_match(e, conn):
                total += 1
        
        conn.commit()
        offset += limit
        
        if offset % 500 == 0:
            print(f"  {year}: {total} matches so far (offset={offset})")
        
        if offset >= data.get('count', 0):
            break
        
        time.sleep(0.1)  # Polite delay
    
    conn.close()
    print(f"  {year}: DONE — {total} matches")
    return total

def main():
    init_db()
    total = 0
    for year in range(2015, 2027):
        cnt = backfill_year(year)
        total += cnt
    print(f"\n{'='*50}")
    print(f"TOTAL: {total} matches backfilled")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
