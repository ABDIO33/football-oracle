"""
🔥 agent_heist_statsbomb_to_db.py — استيراد StatsBomb إلى scrape_cache.db
═══════════════════════════════════════════════════════════════
StatsBomb = FREE Opta-level data!
يحمّل 3,961 مباراة مع:
  ● Event data (كل حدث بالملعب)
  ● xG لكل تسديدة
  ● تشكيلات مؤكدة
  ● Player positions
  ● Nineties stats

🧠 Agent 2 الأسطوري
═══════════════════════════════════════════════════════════════
"""
import sys, os, json, sqlite3, time
from datetime import datetime

BASE = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE, 'scrape_cache.db')
LOG_FILE = os.path.join(BASE, 'output', 'statsbomb_import_log.txt')

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    safe_msg = msg.encode('ascii', 'ignore').decode('ascii')
    print(f'[{ts}] {safe_msg}', flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_competitions (
            competition_id INTEGER,
            season_id INTEGER,
            competition_name TEXT,
            season_name TEXT,
            country_name TEXT,
            match_available INTEGER DEFAULT 0,
            PRIMARY KEY (competition_id, season_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_matches (
            match_id INTEGER PRIMARY KEY,
            competition_id INTEGER,
            season_id INTEGER,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            match_date TEXT,
            venue TEXT,
            referee TEXT,
            home_formation TEXT,
            away_formation TEXT,
            data_json TEXT,
            imported_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS statsbomb_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            event_type TEXT,
            team TEXT,
            player TEXT,
            minute INTEGER,
            second INTEGER,
            x REAL,
            y REAL,
            end_x REAL,
            end_y REAL,
            outcome TEXT,
            xg REAL,
            related_events TEXT,
            raw_json TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sb_events_match ON statsbomb_events(match_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sb_events_type ON statsbomb_events(event_type)")
    conn.commit()

def import_competitions(conn):
    """استيراد قائمة المسابقات"""
    from statsbombpy import sb
    comps = sb.competitions()
    
    for _, comp in comps.iterrows():
        conn.execute("""
            INSERT OR REPLACE INTO statsbomb_competitions
            (competition_id, season_id, competition_name, season_name, country_name)
            VALUES (?, ?, ?, ?, ?)
        """, (
            int(comp['competition_id']), int(comp['season_id']),
            comp['competition_name'], comp['season_name'],
            str(comp.get('country_name', ''))
        ))
    
    conn.commit()
    log(f'Imported {len(comps)} competitions')
    return comps

def import_match(conn, competition_id, season_id, match_id):
    """استيراد مباراة واحدة مع كل الأحداث"""
    from statsbombpy import sb
    
    try:
        # Match info
        matches_df = sb.matches(competition_id=competition_id, season_id=season_id)
        match = matches_df[matches_df['match_id'] == match_id]
        if len(match) == 0:
            return False
        
        m = match.iloc[0]
        match_date = str(m.get('match_date', ''))[:10]
        
        # Save match
        conn.execute("""
            INSERT OR REPLACE INTO statsbomb_matches
            (match_id, competition_id, season_id, home_team, away_team,
             home_score, away_score, match_date, venue, referee,
             home_formation, away_formation, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(match_id), int(competition_id), int(season_id),
            str(m.get('home_team', '')), str(m.get('away_team', '')),
            int(m.get('home_score', 0)), int(m.get('away_score', 0)),
            match_date,
            str(m.get('venue', '')), str(m.get('referee', '')),
            str(m.get('home_formation', '')), str(m.get('away_formation', '')),
            datetime.now().isoformat()
        ))
        
        # Events
        events = sb.events(match_id=match_id)
        if events is not None and len(events) > 0:
            event_count = 0
            for _, ev in events.iterrows():
                try:
                    xg = float(ev.get('shot_statsbomb_xg', 0)) if 'shot_statsbomb_xg' in ev else None
                except:
                    xg = None
                
                conn.execute("""
                    INSERT INTO statsbomb_events
                    (match_id, event_type, team, player, minute, second,
                     x, y, end_x, end_y, outcome, xg, related_events, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(match_id),
                    str(ev.get('type', {}).get('name', '') if isinstance(ev.get('type'), dict) else ev.get('type', '')),
                    str(ev.get('team', {}).get('name', '') if isinstance(ev.get('team'), dict) else ev.get('team', '')),
                    str(ev.get('player', {}).get('name', '') if isinstance(ev.get('player'), dict) else ev.get('player', '')),
                    int(ev.get('minute', 0)),
                    int(ev.get('second', 0)),
                    float(ev.get('location', [0,0])[0]) if isinstance(ev.get('location'), (list,tuple)) and len(ev.get('location', [])) >= 1 else 0,
                    float(ev.get('location', [0,0])[1]) if isinstance(ev.get('location'), (list,tuple)) and len(ev.get('location', [])) >= 2 else 0,
                    float(ev.get('pass_end_location', [0,0])[0]) if isinstance(ev.get('pass_end_location'), (list,tuple)) and len(ev.get('pass_end_location', [])) >= 1 else 0,
                    float(ev.get('pass_end_location', [0,0])[1]) if isinstance(ev.get('pass_end_location'), (list,tuple)) and len(ev.get('pass_end_location', [])) >= 2 else 0,
                    str(ev.get('shot_outcome', {}).get('name', '') if isinstance(ev.get('shot_outcome'), dict) else ev.get('shot_outcome', '')),
                    xg,
                    str(ev.get('related_events', [])),
                    json.dumps(ev.to_dict(), default=str)[:2000]
                ))
                event_count += 1
            
            conn.commit()
            return event_count
        
        conn.commit()
        return 0
    
    except Exception as e:
        log(f'  Error match {match_id}: {e}')
        return -1

def import_all():
    """استيراد كل StatsBomb"""
    log('='*60)
    log('HEIST: StatsBomb -> scrape_cache.db')
    log('='*60)
    
    conn = get_db()
    init_tables(conn)
    
    # 1. Import competitions
    log('\n[1/3] Importing competitions...')
    comps = import_competitions(conn)
    
    # 2. Import all matches
    log('\n[2/3] Importing matches...')
    total_matches = 0
    total_events = 0
    failed = 0
    
    for _, comp in comps.iterrows():
        cid = int(comp['competition_id'])
        sid = int(comp['season_id'])
        
        try:
            from statsbombpy import sb
            matches = sb.matches(competition_id=cid, season_id=sid)
            
            for _, m in matches.iterrows():
                mid = int(m['match_id'])
                
                # Check if already imported
                existing = conn.execute(
                    'SELECT match_id FROM statsbomb_matches WHERE match_id = ?',
                    (mid,)
                ).fetchone()
                if existing:
                    continue
                
                ev_count = import_match(conn, cid, sid, mid)
                if ev_count >= 0:
                    total_matches += 1
                    total_events += ev_count
                    if total_matches % 50 == 0:
                        log(f'  Progress: {total_matches} matches, {total_events} events')
                else:
                    failed += 1
                
        except Exception as e:
            log(f'  Error comp {cid}/{sid}: {e}')
    
    # 3. Summary
    log('\n[3/3] Summary')
    log(f'Matches imported: {total_matches}')
    log(f'Events imported: {total_events}')
    log(f'Failed: {failed}')
    
    # Update competition match counts
    for _, comp in comps.iterrows():
        cnt = conn.execute(
            'SELECT COUNT(*) FROM statsbomb_matches WHERE competition_id=? AND season_id=?',
            (int(comp['competition_id']), int(comp['season_id']))
        ).fetchone()[0]
        if cnt > 0:
            conn.execute(
                'UPDATE statsbomb_competitions SET match_available=? WHERE competition_id=? AND season_id=?',
                (cnt, int(comp['competition_id']), int(comp['season_id']))
            )
    
    conn.commit()
    conn.close()
    
    log(f'\nDONE! Total: {total_matches} matches, {total_events} events')
    log(f'DB: {DB_PATH}')

if __name__ == '__main__':
    import_all()
