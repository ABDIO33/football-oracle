"""
🔥 agent_heist_statsbomb_fast.py — تحميل StatsBomb 100% بسرعة خارقة
═════════════════════════════════════════════════════════════
يستخدم statsbombpy لاستيراد أسماء المسابقات + المباريات
ثم GitHub raw JSON لتحميل الأحداث + التشكيلات
مع Threading (10 workers) لسرعة قصوى
═════════════════════════════════════════════════════════════
"""
import sys, os, json, sqlite3, time, urllib.request, urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'scrape_cache.db')

sys.stdout.reconfigure(encoding='utf-8')
_lock = threading.Lock()
_failed = []
_progress = {'done': 0, 'events': 0, 'lineups': 0}

# =====================================================
# 1. جلب كل المباريات من StatsBomb
# =====================================================
def load_all_matches():
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
        except:
            pass
    
    return all_matches

# =====================================================
# 2. تحميل الأحداث من GitHub raw
# =====================================================
def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            time.sleep(1)
        except:
            time.sleep(1)
    return None

# =====================================================
# 3. threading worker — استيراد مباراة واحدة
# =====================================================
def import_one_match(match_info):
    mid = match_info['match_id']
    
    # Fetch events
    events_url = f'https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{mid}.json'
    events = fetch_json(events_url)
    
    if events is None:
        with _lock:
            _failed.append(mid)
        return None
    
    # Fetch lineups
    lineups_url = f'https://raw.githubusercontent.com/statsbomb/open-data/master/data/lineups/{mid}.json'
    lineups = fetch_json(lineups_url)
    if lineups is None:
        lineups = []
    
    return {
        'match': match_info,
        'events': events if events else [],
        'lineups': lineups if lineups else []
    }

def save_to_db(result):
    """حفظ المباراة في DB (thread safe)"""
    if result is None:
        return
    
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    
    try:
        m = result['match']
        
        # Insert match
        conn.execute("""
            INSERT OR REPLACE INTO statsbomb_matches
            (match_id, competition_id, season_id, competition_name, season_name,
             home_team, away_team, home_score, away_score, match_date,
             venue, referee, home_formation, away_formation, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m['match_id'], m['competition_id'], m['season_id'],
            m['competition_name'], m['season_name'],
            m['home_team'], m['away_team'],
            m['home_score'], m['away_score'],
            m['match_date'], m['venue'], m['referee'],
            m['home_formation'], m['away_formation'],
            datetime.now().isoformat()
        ))
        
        # Insert events
        for i, ev in enumerate(result['events']):
            try:
                xg_val = None
                if ev.get('shot'):
                    xg_val = float(ev['shot'].get('statsbomb_xg', 0)) if ev['shot'].get('statsbomb_xg') else None
                
                location = ev.get('location', [0, 0])
                pass_end = ev.get('pass', {}).get('end_location', [0, 0]) if ev.get('pass') else [0, 0]
                
                team_name = ev.get('team', {}).get('name', '') if isinstance(ev.get('team'), dict) else ''
                player_name = ev.get('player', {}).get('name', '') if isinstance(ev.get('player'), dict) else ''
                event_type = ev.get('type', {}).get('name', '') if isinstance(ev.get('type'), dict) else ''
                outcome = ev.get('shot', {}).get('outcome', {}).get('name', '') if ev.get('shot') else ''
                
                conn.execute("""
                    INSERT INTO statsbomb_events
                    (match_id, event_index, event_type, team, player, minute, second,
                     x, y, end_x, end_y, outcome, xg, related_events, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    m['match_id'], i, event_type, team_name, player_name,
                    int(ev.get('minute', 0)), int(ev.get('second', 0)),
                    float(location[0]) if len(location) >= 1 else 0,
                    float(location[1]) if len(location) >= 2 else 0,
                    float(pass_end[0]) if len(pass_end) >= 1 else 0,
                    float(pass_end[1]) if len(pass_end) >= 2 else 0,
                    outcome, xg_val,
                    json.dumps(ev.get('related_events', [])),
                    json.dumps(ev, default=str)[:3000]
                ))
            except:
                pass
        
        # Insert lineups
        for team_data in result['lineups']:
            team_name = team_data.get('team_name', '')
            for player in team_data.get('lineup', []):
                try:
                    conn.execute("""
                        INSERT INTO statsbomb_lineups
                        (match_id, team, player_id, player_name, jersey_number, position, starting)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        m['match_id'], team_name,
                        int(player.get('player_id', 0)),
                        player.get('player_name', ''),
                        int(player.get('jersey_number', 0)),
                        str(player.get('position', '')),
                        bool(player.get('starting', False))
                    ))
                except:
                    pass
        
        conn.commit()
        event_count = len(result['events'])
        
        with _lock:
            _progress['done'] += 1
            _progress['events'] += event_count
            _progress['lineups'] += len(result['lineups'])
    
    except Exception as e:
        pass
    finally:
        conn.close()

# =====================================================
# 4. الرئيسي — التنفيذ المتوازي
# =====================================================
def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_matches (
            match_id INTEGER PRIMARY KEY,
            competition_id INTEGER,
            season_id INTEGER,
            competition_name TEXT,
            season_name TEXT,
            home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            match_date TEXT, venue TEXT, referee TEXT,
            home_formation TEXT, away_formation TEXT,
            imported_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER, event_index INTEGER,
            event_type TEXT, team TEXT, player TEXT,
            minute INTEGER, second INTEGER,
            x REAL DEFAULT 0, y REAL DEFAULT 0,
            end_x REAL DEFAULT 0, end_y REAL DEFAULT 0,
            outcome TEXT, xg REAL, related_events TEXT,
            raw_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_lineups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER, team TEXT, player_id INTEGER,
            player_name TEXT, jersey_number INTEGER,
            position TEXT, starting BOOLEAN
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sbe_m ON statsbomb_events(match_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sbe_t ON statsbomb_events(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sbl_m ON statsbomb_lineups(match_id)")
    conn.commit()

def print_progress():
    """طابعة التقدم كل 3 ثواني"""
    start = time.time()
    last_done = 0
    while True:
        time.sleep(3)
        with _lock:
            d = _progress['done']
            e = _progress['events']
            l = _progress['lineups']
        
        if d == last_done and d > 0:
            continue  # No progress
        last_done = d
        
        elapsed = time.time() - start
        rate = d / elapsed if elapsed > 0 else 0
        
        if d > 0:
            print(f'  [{d}] {e} events, {l} lineups — {rate:.1f} match/s — {elapsed:.0f}s')

def main():
    print('🔥🔥🔥 STATSBOMB FAST HEIST 🔥🔥🔥')
    print('='*50)
    
    # Init DB
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    init_db(conn)
    existing = conn.execute('SELECT COUNT(*) FROM statsbomb_matches').fetchone()[0]
    conn.close()
    print(f'Already in DB: {existing} matches')
    
    # Load match list
    print('\n[1/3] Loading match list...')
    all_matches = load_all_matches()
    print(f'  Total matches: {len(all_matches)}')
    
    # Filter existing
    conn = sqlite3.connect(DB_PATH, timeout=60)
    existing_ids = set(r[0] for r in conn.execute('SELECT match_id FROM statsbomb_matches').fetchall())
    conn.close()
    
    to_import = [m for m in all_matches if m['match_id'] not in existing_ids]
    print(f'  New to import: {len(to_import)}')
    
    if not to_import:
        print('  ✅ All matches already imported!')
        return
    
    # Parallel import
    print(f'\n[2/3] Fast parallel import (10 workers)...')
    print(f'  First match: {to_import[0]["home_team"]} vs {to_import[0]["away_team"]}')
    print(f'  Last match: {to_import[-1]["home_team"]} vs {to_import[-1]["away_team"]}')
    print()
    
    import threading as t
    progress_thread = t.Thread(target=print_progress, daemon=True)
    progress_thread.start()
    
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all
        futures = {executor.submit(import_one_match, m): m for m in to_import}
        
        # Save as they complete
        for future in as_completed(futures):
            result = future.result()
            if result:
                save_to_db(result)
    
    elapsed = time.time() - start
    
    # Summary
    with _lock:
        d = _progress['done']
        e = _progress['events']
        l = _progress['lineups']
    
    print(f'\n[3/3] RESULTS')
    print(f'  Imported: {d} matches')
    print(f'  Events: {e:,}')
    print(f'  Lineups: {l}')
    print(f'  Failed: {len(_failed)}')
    print(f'  Time: {elapsed:.0f}s ({d/elapsed:.1f} matches/s)')
    print(f'  Rate: {e/elapsed:.0f} events/s')
    
    # Final DB check
    conn = sqlite3.connect(DB_PATH, timeout=60)
    total = conn.execute('SELECT COUNT(*) FROM statsbomb_matches').fetchone()[0]
    total_e = conn.execute('SELECT COUNT(*) FROM statsbomb_events').fetchone()[0]
    total_l = conn.execute('SELECT COUNT(*) FROM statsbomb_lineups').fetchone()[0]
    conn.close()
    
    print(f'\n  DB total: {total} matches, {total_e:,} events, {total_l} lineup entries')
    print(f'  ✅ StatsBomb Heist Complete!')

if __name__ == '__main__':
    main()
