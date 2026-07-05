"""
🔥 agent_heist_statsbomb_bulk.py — تحميل StatsBomb كامل بسرعة
═════════════════════════════════════════════════════════════
يستخدم statsbombpy مباشرة + تعدد المباريات
كل المباريات تخزّن في scrape_cache.db
═════════════════════════════════════════════════════════════
"""
import sys, os, json, sqlite3, time, urllib.request, urllib.error
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'scrape_cache.db')

sys.stdout.reconfigure(encoding='utf-8')

# =====================================================
# 1. الأحمال المسبقة — كل المباريات من StatsBomb API
# =====================================================
def load_all_matches():
    """جلب كل مباريات StatsBomb مع نتائجها"""
    from statsbombpy import sb
    
    comps = sb.competitions()
    all_matches = []
    
    for _, comp in comps.iterrows():
        cid = int(comp['competition_id'])
        sid = int(comp['season_id'])
        
        try:
            matches = sb.matches(competition_id=cid, season_id=sid)
            for _, m in matches.iterrows():
                all_matches.append({
                    'match_id': int(m['match_id']),
                    'competition_id': cid,
                    'season_id': sid,
                    'competition_name': comp['competition_name'],
                    'season_name': comp['season_name'],
                    'home_team': str(m.get('home_team', '')),
                    'away_team': str(m.get('away_team', '')),
                    'home_score': int(m.get('home_score', 0)),
                    'away_score': int(m.get('away_score', 0)),
                    'match_date': str(m.get('match_date', ''))[:10],
                    'venue': str(m.get('venue', '')),
                    'referee': str(m.get('referee', '')),
                    'home_formation': str(m.get('home_formation', '')),
                    'away_formation': str(m.get('away_formation', '')),
                })
        except Exception as e:
            print(f'  Error comp {cid}/{sid}: {e}')
    
    return all_matches

# =====================================================
# 2. استيراد مباراة — من GitHub JSON مباشر 
# =====================================================
def fetch_match_events(match_id, retries=3):
    """جلب أحداث المباراة من StatsBomb GitHub مباشرة"""
    url = f'https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json'
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []  # No events for this match
            time.sleep(1 * (attempt + 1))
        except:
            time.sleep(1 * (attempt + 1))
    
    return None

def fetch_match_lineups(match_id, retries=3):
    """جلب تشكيلات المباراة"""
    url = f'https://raw.githubusercontent.com/statsbomb/open-data/master/data/lineups/{match_id}.json'
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data
        except:
            time.sleep(1 * (attempt + 1))
    
    return []

# =====================================================
# 3. قاعدة البيانات
# =====================================================
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_matches (
            match_id INTEGER PRIMARY KEY,
            competition_id INTEGER,
            season_id INTEGER,
            competition_name TEXT,
            season_name TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            match_date TEXT,
            venue TEXT,
            referee TEXT,
            home_formation TEXT,
            away_formation TEXT,
            imported_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            event_index INTEGER,
            event_type TEXT,
            team TEXT,
            player TEXT,
            minute INTEGER,
            second INTEGER,
            x REAL DEFAULT 0,
            y REAL DEFAULT 0,
            end_x REAL DEFAULT 0,
            end_y REAL DEFAULT 0,
            outcome TEXT,
            xg REAL,
            related_events TEXT,
            raw_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            team TEXT,
            player_id INTEGER,
            player_name TEXT,
            jersey_number INTEGER,
            position TEXT,
            starting BOOLEAN
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sbe_match ON statsbomb_events(match_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sbe_type ON statsbomb_events(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sbl_match ON statsbomb_lineups(match_id)")
    conn.commit()

def import_match(conn, match_info):
    """استيراد مباراة + أحداثها + تشكيلاتها"""
    mid = match_info['match_id']
    
    # Check if already exists
    existing = conn.execute('SELECT match_id FROM statsbomb_matches WHERE match_id=?', (mid,)).fetchone()
    if existing:
        return 0  # Already done
    
    # 1. Save match info
    conn.execute("""
        INSERT OR REPLACE INTO statsbomb_matches
        (match_id, competition_id, season_id, competition_name, season_name,
         home_team, away_team, home_score, away_score, match_date,
         venue, referee, home_formation, away_formation, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        mid, match_info['competition_id'], match_info['season_id'],
        match_info['competition_name'], match_info['season_name'],
        match_info['home_team'], match_info['away_team'],
        match_info['home_score'], match_info['away_score'],
        match_info['match_date'],
        match_info['venue'], match_info['referee'],
        match_info['home_formation'], match_info['away_formation'],
        datetime.now().isoformat()
    ))
    
    # 2. Fetch events from GitHub raw
    events = fetch_match_events(mid)
    if events is None:
        conn.commit()
        return -1  # Fetch failed
    
    if events:
        for i, ev in enumerate(events):
            try:
                xg_val = None
                if 'shot' in ev and ev['shot']:
                    xg_val = float(ev['shot'].get('statsbomb_xg', 0))
                
                location = ev.get('location', [0, 0])
                pass_end = ev.get('pass', {}).get('end_location', [0, 0]) if ev.get('pass') else [0, 0]
                
                team_name = ev.get('team', {}).get('name', '') if isinstance(ev.get('team'), dict) else str(ev.get('team', ''))
                player_name = ev.get('player', {}).get('name', '') if isinstance(ev.get('player'), dict) else ''
                event_type = ev.get('type', {}).get('name', '') if isinstance(ev.get('type'), dict) else str(ev.get('type', ''))
                outcome = ev.get('shot', {}).get('outcome', {}).get('name', '') if ev.get('shot') else ''
                
                conn.execute("""
                    INSERT INTO statsbomb_events
                    (match_id, event_index, event_type, team, player, minute, second,
                     x, y, end_x, end_y, outcome, xg, related_events, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mid, i, event_type, team_name, player_name,
                    int(ev.get('minute', 0)), int(ev.get('second', 0)),
                    float(location[0]) if len(location) >= 1 else 0,
                    float(location[1]) if len(location) >= 2 else 0,
                    float(pass_end[0]) if len(pass_end) >= 1 else 0,
                    float(pass_end[1]) if len(pass_end) >= 2 else 0,
                    outcome, xg_val,
                    json.dumps(ev.get('related_events', [])),
                    json.dumps(ev, default=str)[:3000]
                ))
            except Exception as e:
                pass  # Skip bad event
    
    # 3. Fetch lineups
    lineups = fetch_match_lineups(mid)
    for team_data in lineups:
        team_name = team_data.get('team_name', '')
        for player in team_data.get('lineup', []):
            try:
                conn.execute("""
                    INSERT INTO statsbomb_lineups
                    (match_id, team, player_id, player_name, jersey_number, position, starting)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    mid, team_name,
                    int(player.get('player_id', 0)),
                    player.get('player_name', ''),
                    int(player.get('jersey_number', 0)),
                    str(player.get('position', '')),
                    bool(player.get('starting', False))
                ))
            except:
                pass
    
    conn.commit()
    event_count = len(events) if events else 0
    lineup_count = len(lineups)
    return event_count

# =====================================================
# 4. الرئيسي
# =====================================================
def main():
    print('🔥 StatsBomb Bulk Import — GitHub Direct 🔥')
    print('='*50)
    
    # Init DB
    conn = get_db()
    init_tables(conn)
    
    # Count existing
    existing = conn.execute('SELECT COUNT(*) FROM statsbomb_matches').fetchone()[0]
    print(f'Already in DB: {existing} matches')
    
    # Load all match info
    print('\n[1/3] Loading match list from StatsBomb...')
    all_matches = load_all_matches()
    print(f'  Total matches available: {len(all_matches)}')
    
    # Filter out already imported
    to_import = []
    for m in all_matches:
        row = conn.execute('SELECT match_id FROM statsbomb_matches WHERE match_id=?', (m['match_id'],)).fetchone()
        if not row:
            to_import.append(m)
    
    print(f'  New matches to import: {len(to_import)}')
    
    if not to_import:
        print('  Nothing to import!')
        conn.close()
        return
    
    # Import in batches
    print('\n[2/3] Importing matches from GitHub raw JSON...')
    imported = 0
    events_total = 0
    failed = 0
    total = len(to_import)
    start_time = time.time()
    
    for i, match_info in enumerate(to_import):
        ev_count = import_match(conn, match_info)
        
        if ev_count < 0:
            failed += 1
            continue
        
        imported += 1
        events_total += ev_count
        
        # Progress
        if imported % 10 == 0:
            elapsed = time.time() - start_time
            rate = imported / elapsed if elapsed > 0 else 0
            pct = imported * 100 // total
            remaining = (total - imported) / rate if rate > 0 else 0
            print(f'  [{imported}/{total}] {pct}% — {events_total} events — {rate:.1f} matches/s — ETA: {remaining:.0f}s')
    
    # Summary
    elapsed = time.time() - start_time
    print(f'\n[3/3] RESULTS')
    print(f'  Imported: {imported} matches')
    print(f'  Events: {events_total}')
    print(f'  Failed: {failed}')
    print(f'  Time: {elapsed:.0f}s ({imported/elapsed:.1f} matches/s)')
    print(f'  Rate: {events_total/elapsed:.0f} events/s')
    
    # DB stats
    total_matches = conn.execute('SELECT COUNT(*) FROM statsbomb_matches').fetchone()[0]
    total_events = conn.execute('SELECT COUNT(*) FROM statsbomb_events').fetchone()[0]
    total_lineups = conn.execute('SELECT COUNT(*) FROM statsbomb_lineups').fetchone()[0]
    print(f'\n  DB total: {total_matches} matches, {total_events} events, {total_lineups} lineup entries')
    
    conn.close()
    print(f'\n✅ StatsBomb Heist Complete!')

if __name__ == '__main__':
    main()
