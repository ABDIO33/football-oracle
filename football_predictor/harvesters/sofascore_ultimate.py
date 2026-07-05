#!/usr/bin/env python3
"""
SOFASCORE ULTIMATE HARVESTER — أقوى مصدر بيانات كرة قدم
يستغل API SofaScore غير الرسمي لجلب كل المباريات + الإحصائيات
All Protocols Active — ENI for LO 🔥
"""

import sys, os, time, json, sqlite3, re, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scrape_cache.db')

# Try curl_cffi first, fall back to urllib
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL = True
except:
    import urllib.request
    HAS_CURL = False

API_BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

# Premier League tournaments with their SofaScore IDs
TOURNAMENTS = {
    # England
    17: "England-Premier-League",
    18: "England-Championship",
    19: "England-League-One",
    20: "England-League-Two",
    # Spain
    8: "Spain-LaLiga",
    9: "Spain-LaLiga2",
    # Italy
    34: "Italy-Serie-A",
    35: "Italy-Serie-B",
    # Germany
    35: "Germany-Bundesliga",  # wait, this conflicts
}

# Let me just get the right SofaScore tournament IDs
# From the existing flashscore rewrite, tournament ID 17 = England PL

def sofa_fetch(url, retries=3):
    """Fetch from SofaScore API with retries."""
    for i in range(retries):
        try:
            if HAS_CURL:
                resp = curl_requests.get(url, headers=HEADERS, impersonate='chrome124', timeout=15)
                if resp.status_code == 200:
                    return resp.json()
            else:
                req = urllib.request.Request(url, headers=HEADERS)
                resp = urllib.request.urlopen(req, timeout=15)
                return json.loads(resp.read())
        except Exception as e:
            if i < retries - 1:
                time.sleep(1)
                continue
            return None
    return None

def ensure_tables():
    """Create SofaScore tables if they don't exist."""
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS source_sofascore_extended (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER,
            season_id INTEGER,
            match_date TEXT,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            home_xg REAL,
            away_xg REAL,
            possession_home REAL,
            possession_away REAL,
            shots_home INTEGER,
            shots_away INTEGER,
            shots_on_target_home INTEGER,
            shots_on_target_away INTEGER,
            corners_home INTEGER,
            corners_away INTEGER,
            fouls_home INTEGER,
            fouls_away INTEGER,
            yellow_cards_home INTEGER,
            yellow_cards_away INTEGER,
            red_cards_home INTEGER,
            red_cards_away INTEGER,
            sofascore_id INTEGER UNIQUE,
            status TEXT,
            hash TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def get_tournaments():
    """Search for football tournaments."""
    # Common top tournaments
    tournaments = [
        (17, "England", "Premier League", 2025, 77744),
        (18, "England", "Championship", 2025, 77745),
        (34, "Italy", "Serie A", 2025, 77870),
        (8, "Spain", "La Liga", 2025, 77746),
        (35, "Italy", "Serie B", 2025, 77889),
        (9, "Spain", "La Liga 2", 2025, 77747),
        (7, "Germany", "1. Bundesliga", 2025, 77688),
        (22, "Germany", "2. Bundesliga", 2025, 77701),
        (16, "France", "Ligue 1", 2025, 77749),
        (23, "France", "Ligue 2", 2025, 77750),
        (45, "Netherlands", "Eredivisie", 2025, 77892),
        (40, "Portugal", "Liga Portugal", 2025, 77761),
        (73, "Turkey", "Super Lig", 2025, 78232),
        (49, "Belgium", "Pro League", 2025, 77885),
        (38, "Scotland", "Premiership", 2025, 77770),
    ]
    return tournaments

def get_rounds(tournament_id, season_id):
    """Get all round IDs for a tournament."""
    url = f"{API_BASE}/unique-tournament/{tournament_id}/season/{season_id}/rounds"
    data = sofa_fetch(url)
    if data and 'rounds' in data:
        return [r['id'] for r in data['rounds'] if isinstance(r, dict)]
    return []

def get_events(tournament_id, season_id, round_id):
    """Get events for a round."""
    url = f"{API_BASE}/unique-tournament/{tournament_id}/season/{season_id}/round/{round_id}/events"
    data = sofa_fetch(url)
    events = []
    if data and 'events' in data:
        events = data['events']
    return events

def get_event_detail(event_id):
    """Get detailed statistics for an event."""
    url = f"{API_BASE}/event/{event_id}/statistics"
    data = sofa_fetch(url)
    if not data:
        return None
    return data

def harvest_tournament(tid, country, name, season_id, max_rounds=None):
    """Harvest all matches for a tournament."""
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    
    print(f"  [..] {country} {name}: getting rounds...")
    rounds = get_rounds(tid, season_id)
    if not rounds:
        print(f"  [--] {country} {name}: no rounds found")
        conn.close()
        return 0
    
    if max_rounds:
        rounds = rounds[:max_rounds]
    
    print(f"  [..] {country} {name}: {len(rounds)} rounds")
    total = 0
    
    for rnd in rounds:
        events = get_events(tid, season_id, rnd)
        for ev in events:
            try:
                match_id = ev.get('id')
                home = ev.get('homeTeam', {}).get('name', '')
                away = ev.get('awayTeam', {}).get('name', '')
                date_ts = ev.get('startTimestamp', 0)
                match_date = time.strftime('%Y-%m-%d', time.gmtime(date_ts)) if date_ts else ''
                
                home_score = None
                away_score = None
                status = ev.get('status', {}).get('type', '')
                
                if status == 'finished':
                    home_score = ev.get('homeScore', {}).get('current', 0)
                    away_score = ev.get('awayScore', {}).get('current', 0)
                
                xg_h = None
                xg_a = None
                stats = ev.get('statistics', {})
                if not stats:
                    stats_detail = get_event_detail(match_id)
                    if stats_detail:
                        stats = stats_detail
                
                # Extract xG and other stats
                pos_h, pos_a = None, None
                shots_h, shots_a = None, None
                shots_on_h, shots_on_a = None, None
                corners_h, corners_a = None, None
                
                if stats and 'groups' in stats:
                    for group in stats['groups']:
                        for item in group.get('statisticsItems', []):
                            name_stat = item.get('name', '').lower()
                            h_val = item.get('home')
                            a_val = item.get('away')
                            
                            if 'possession' in name_stat:
                                try: pos_h = float(str(h_val).replace('%','')) 
                                except: pass
                                try: pos_a = float(str(a_val).replace('%','')) 
                                except: pass
                            elif 'shots on target' in name_stat:
                                try: shots_on_h = int(h_val) 
                                except: pass
                                try: shots_on_a = int(a_val) 
                                except: pass
                            elif 'total shots' in name_stat or 'shots' in name_stat:
                                try: shots_h = int(h_val) 
                                except: pass
                                try: shots_a = int(a_val) 
                                except: pass
                            elif 'corner' in name_stat:
                                try: corners_h = int(h_val) 
                                except: pass
                                try: corners_a = int(a_val) 
                                except: pass
                
                hash_key = f"sofa-{match_id}"
                
                c.execute("""
                    INSERT OR IGNORE INTO source_sofascore_extended
                    (tournament_id, season_id, match_date, home_team, away_team,
                     home_score, away_score, home_xg, away_xg,
                     possession_home, possession_away, shots_home, shots_away,
                     shots_on_target_home, shots_on_target_away, corners_home, corners_away,
                     sofascore_id, status, hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    tid, season_id, match_date, home, away,
                    home_score, away_score, xg_h, xg_a,
                    pos_h, pos_a, shots_h, shots_a,
                    shots_on_h, shots_on_a, corners_h, corners_a,
                    match_id, status, hash_key
                ))
                total += 1
                
            except Exception as e:
                pass
        
        # Commit per round
        if total % 50 == 0:
            conn.commit()
    
    conn.commit()
    conn.close()
    return total

def run_quick_scan():
    """Quick scan of top 5 leagues, 5 rounds each."""
    print("="*60)
    print("SOFASCORE ULTIMATE HARVESTER — QUICK SCAN")
    print("="*60)
    
    ensure_tables()
    
    # Just top leagues
    tours = [
        (17, "England", "Premier League", 77744),
        (18, "England", "Championship", 77745),
        (34, "Italy", "Serie A", 77870),
        (8, "Spain", "La Liga", 77746),
        (7, "Germany", "Bundesliga", 77688),
    ]
    
    grand_total = 0
    for tid, country, name, sid in tours:
        n = harvest_tournament(tid, country, name, sid, max_rounds=5)
        print(f"  [OK] {country} {name}: {n} events")
        grand_total += n
    
    print(f"\n  TOTAL: {grand_total} events")
    
    # Show DB counts
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    n = c.execute("SELECT COUNT(*) FROM source_sofascore_extended").fetchone()[0]
    print(f"  source_sofascore_extended: {n} total rows")
    conn.close()

def run_massive_harvest():
    """Harvest ALL available tournaments and seasons."""
    print("="*60)
    print("SOFASCORE ULTIMATE HARVESTER — MASSIVE HARVEST")
    print("="*60)
    
    ensure_tables()
    
    tours = get_tournaments()
    grand_total = 0
    
    for tid, country, name, default_season, season_id in tours:
        n = harvest_tournament(tid, country, name, season_id)
        print(f"  [OK] {country} {name}: {n} events")
        grand_total += n
        
        # Also try previous season
        prev_season_id = season_id - 1
        n2 = harvest_tournament(tid, country, f"{name} (prev)", prev_season_id, max_rounds=10)
        if n2 > 0:
            print(f"  [OK] {country} {name} (prev): {n2} events")
            grand_total += n2
    
    print(f"\n  GRAND TOTAL: {grand_total} events")
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    n = c.execute("SELECT COUNT(*) FROM source_sofascore_extended").fetchone()[0]
    print(f"  source_sofascore_extended: {n} total rows")
    conn.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['quick', 'massive'], default='quick')
    parser.add_argument('--max-rounds', type=int, default=5)
    args = parser.parse_args()
    
    if args.mode == 'massive':
        run_massive_harvest()
    else:
        run_quick_scan()
