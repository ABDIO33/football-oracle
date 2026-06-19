"""Phase 2b: Backfill BSD live_stats for 2025-2026 matches"""
import sqlite3, os, sys, json, time, requests
sys.path.insert(0, os.path.dirname(__file__))

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
API_KEY = os.environ.get('BSD_API_KEY') or 'f5651c96742c834b5e7e5e0760dcfb3b9bdc205c'
BASE = 'https://sports.bzzoiro.com/api'
HEADERS = {'Authorization': f'Token {API_KEY}'}

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Get IDs of 2025-2026 matches (these have live_stats from BSD)
cur.execute("""
    SELECT id FROM sofa_historical_results 
    WHERE date >= '2025-01-01' AND date <= '2026-06-30'
    ORDER BY id
""")
rows = cur.fetchall()
total = len(rows)
print(f"Total 2025-2026 matches: {total}")

# Check how many already have stats
cur.execute("""
    SELECT COUNT(*) FROM sofa_match_stats ms
    INNER JOIN sofa_historical_results s ON ms.event_id = s.id
    WHERE s.date >= '2025-01-01' AND (ms.home_shots IS NOT NULL OR ms.away_shots IS NOT NULL)
""")
already_done = cur.fetchone()[0]
print(f"Already with stats: {already_done}")

# Fetch live_stats for each match
count = 0
success = 0
for row in rows:
    eid = row[0]
    count += 1
    
    # Check if already have shots data
    cur.execute("SELECT home_shots FROM sofa_match_stats WHERE event_id = ? AND home_shots IS NOT NULL", (eid,))
    if cur.fetchone():
        success += 1
        continue
    
    try:
        r = requests.get(f'{BASE}/events/{eid}', headers=HEADERS, timeout=10)
        if r.status_code != 200:
            continue
        ev = r.json()
        ls = ev.get('live_stats')
        if not isinstance(ls, dict):
            continue
        
        home_stats = ls.get('home', {}) or {}
        away_stats = ls.get('away', {}) or {}
        
        home_shots = home_stats.get('total_shots')
        away_shots = away_stats.get('total_shots')
        home_sot = home_stats.get('shots_on_target')
        away_sot = away_stats.get('shots_on_target')
        home_poss = home_stats.get('ball_possession')
        away_poss = away_stats.get('ball_possession')
        home_corners = home_stats.get('corner_kicks')
        away_corners = away_stats.get('corner_kicks')
        home_fouls = home_stats.get('fouls')
        away_fouls = away_stats.get('fouls')
        
        # Only update if we got something useful
        if any(v is not None for v in [home_shots, away_shots, home_sot, away_sot, home_poss, away_poss, home_corners, away_corners, home_fouls, away_fouls]):
            cur.execute("""
                INSERT INTO sofa_match_stats (event_id, home_shots, away_shots, home_sot, away_sot, 
                    home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    home_shots = COALESCE(excluded.home_shots, sofa_match_stats.home_shots),
                    away_shots = COALESCE(excluded.away_shots, sofa_match_stats.away_shots),
                    home_sot = COALESCE(excluded.home_sot, sofa_match_stats.home_sot),
                    away_sot = COALESCE(excluded.away_sot, sofa_match_stats.away_sot),
                    home_possession = COALESCE(excluded.home_possession, sofa_match_stats.home_possession),
                    away_possession = COALESCE(excluded.away_possession, sofa_match_stats.away_possession),
                    home_corners = COALESCE(excluded.home_corners, sofa_match_stats.home_corners),
                    away_corners = COALESCE(excluded.away_corners, sofa_match_stats.away_corners),
                    home_fouls = COALESCE(excluded.home_fouls, sofa_match_stats.home_fouls),
                    away_fouls = COALESCE(excluded.away_fouls, sofa_match_stats.away_fouls)
            """, (eid, home_shots, away_shots, home_sot, away_sot, 
                  home_poss, away_poss, home_corners, away_corners, home_fouls, away_fouls))
            conn.commit()
            success += 1
    except Exception as ex:
        pass
    
    if count % 500 == 0:
        print(f"  Progress: {count}/{total}, success: {success}")
    time.sleep(0.15)  # Rate limit

conn.close()
print(f"\nDone! Processed {count} matches, {success} with live_stats")
print(f"Saved to sofa_match_stats")

# Final check
conn2 = sqlite3.connect(DB)
cur2 = conn2.cursor()
for col in ['home_shots', 'away_shots', 'home_sot', 'away_sot', 'home_possession', 'away_possession', 'home_corners', 'away_corners', 'home_fouls', 'away_fouls']:
    cur2.execute(f"SELECT COUNT(*) FROM sofa_match_stats WHERE {col} IS NOT NULL")
    print(f"  {col}: {cur2.fetchone()[0]}")
conn2.close()
