#!/usr/bin/env python3
"""
SOFASCORE MASS HARVESTER V2 — يستغل API SofaScore الحقيقي
يجيب كل المباريات من كل الدوريات الكبرى
All Protocols Active — ENI for LO 🔥
"""

import sys, os, time, json, sqlite3, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scrape_cache.db')
API_BASE = "https://api.sofascore.com/api/v1"

from curl_cffi import requests as curl_requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.sofascore.com",
    "Referer": "https://www.sofascore.com/",
}

# Verified tournament IDs from search
TOURNAMENTS = [
    # === TIER 1: TOP 5 EUROPEAN LEAGUES ===
    (17, "England", "Premier League", 96668),
    (18, "England", "Championship", 97037),
    (24, "England", "League One", 97077),
    (25, "England", "League Two", 97078),
    (23, "Italy", "Serie A", 95836),
    (53, "Italy", "Serie B", 79502),
    (8, "Spain", "La Liga", 77559),
    (1476, "Spain", "La Liga 2", 77994),
    (35, "Germany", "Bundesliga", 77333),
    (44, "Germany", "2. Bundesliga", 77354),
    (491, "Germany", "3. Liga", 96691),
    (34, "France", "Ligue 1", 96127),
    (182, "France", "Ligue 2", 96109),
    (37, "Netherlands", "Eredivisie", 96143),
    (238, "Portugal", "Liga Portugal", 77806),
    # === TIER 2: EUROPEAN COMPETITIONS ===
    (7, "Europe", "UEFA Champions League", 96758),
    (679, "Europe", "UEFA Europa League", 97010),
    (17015, "Europe", "UEFA Conference League", 97011),
    (36, "Scotland", "Premiership", 96658),
    (38, "Belgium", "Pro League", 96616),
    (9, "Belgium", "Challenger Pro League", 96991),
    (52, "Turkey", "Super Lig", 77805),
    (203, "Russia", "Premier League", 97023),
    (46, "Austria", "Bundesliga", 96130),
    (215, "Switzerland", "Super League", 96589),
    (39, "Denmark", "Superliga", 96650),
    (51, "Sweden", "Allsvenskan", 96655),
    (55, "Norway", "Eliteserien", 96654),
    (60, "Poland", "Ekstraklasa", 97025),
    (172, "Czech Republic", "First League", 96966),
    (67, "Greece", "Super League", 96669),
    (56, "Croatia", "HNL", 96897),
    (54, "Romania", "Liga I", 96997),
    (65, "Bulgaria", "First League", 97026),
    (64, "Serbia", "SuperLiga", 97027),
    (218, "Ukraine", "Premier League", 77625),
    (66, "Hungary", "NB I", 97030),
    # === TIER 3: SOUTH AMERICA ===
    (48, "Brazil", "Serie A", 96657),
    (390, "Brazil", "Serie B", 89840),
    (22, "Argentina", "Primera Division", 96760),
    (30, "Chile", "Primera Division", 96670),
    (33, "Colombia", "Primera A", 96660),
    # === TIER 4: NORTH AMERICA / ASIA / OCEANIA ===
    (42, "USA", "MLS", 96128),
    (319, "Mexico", "Liga MX", 96659),
    (79, "Japan", "J1 League", 96663),
    (318, "Japan", "J2 League", 96888),
    (78, "South Korea", "K League 1", 96664),
    (80, "China", "Super League", 96665),
    (955, "Saudi Arabia", "Pro League", 96662),
    (75, "Australia", "A-League", 96661),
    (59, "Netherlands", "Eerste Divisie", 96317),
]

last_request = 0.0

def api_get(path):
    """Rate-limited SofaScore API call."""
    global last_request
    now = time.time()
    since = now - last_request
    if since < 0.35:
        time.sleep(0.35 - since)
    
    url = API_BASE + path
    try:
        resp = curl_requests.get(url, headers=HEADERS, impersonate='chrome124', timeout=20)
        last_request = time.time()
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            print(f"  [!] Rate limited! Waiting 5s...", flush=True)
            time.sleep(5)
            return api_get(path)
        else:
            return None
    except Exception as e:
        return None

def log(msg):
    print(msg, flush=True)

def harvest_league(tid, country, name, sid, max_rounds=None):
    """Harvest ALL matches for a league from SofaScore."""
    log(f"\n{'='*50}")
    log(f"  {country} {name} (tid={tid}, sid={sid})")
    log(f"{'='*50}")
    
    # Get rounds
    data = api_get(f"/unique-tournament/{tid}/season/{sid}/rounds")
    if not data or 'rounds' not in data:
        log(f"  [!] No rounds found")
        return 0
    
    rounds = [r['round'] for r in data['rounds'] if isinstance(r, dict)]
    log(f"  [OK] {len(rounds)} rounds available")
    
    if max_rounds:
        rounds = rounds[:max_rounds]
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    
    total = 0
    errors = 0
    
    for i, rnd in enumerate(rounds):
        data = api_get(f"/unique-tournament/{tid}/season/{sid}/events/round/{rnd}")
        if not data or 'events' not in data:
            errors += 1
            continue
        
        for ev in data['events']:
            try:
                match_id = ev['id']
                home = ev.get('homeTeam', {}).get('name', '')
                away = ev.get('awayTeam', {}).get('name', '')
                date_ts = ev.get('startTimestamp', 0)
                match_date = time.strftime('%Y-%m-%d', time.gmtime(date_ts)) if date_ts else ''
                
                # Scores
                status = ev.get('status', {}).get('type', '')
                home_score = ev.get('homeScore', {}).get('current') if status == 'finished' else None
                away_score = ev.get('awayScore', {}).get('current') if status == 'finished' else None
                
                # Status flags
                is_finished = 1 if status == 'finished' else 0
                is_live = 1 if status == 'inprogress' else 0
                is_scheduled = 1 if status == 'notstarted' else 0
                
                # Round info
                round_info = ev.get('roundInfo', {}) or {}
                round_num = round_info.get('round', rnd)
                
                hash_key = f"sv2-{match_id}"
                league_name = f"{country}-{name}"
                
                c.execute("""
                    INSERT OR IGNORE INTO source_sofascore_extended
                    (match_id, league, match_date, home_team, away_team,
                     hash, raw_json)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    str(match_id), league_name, match_date, home, away,
                    hash_key, json.dumps(ev)
                ))
                total += 1
                
            except Exception as e:
                errors += 1
        
        # Progress
        if (i+1) % 10 == 0:
            log(f"  [..] Round {i+1}/{len(rounds)}: {total} matches so far...")
            conn.commit()
        
        # Small delay between rounds
        time.sleep(0.1)
    
    conn.commit()
    conn.close()
    
    log(f"  [OK] FINAL: {total} matches, {errors} errors")
    return total

def harvest_all(quick=False):
    """Harvest all tournaments."""
    grand_total = 0
    
    for tid, country, name, sid in TOURNAMENTS:
        n = harvest_league(tid, country, name, sid, max_rounds=5 if quick else None)
        grand_total += n
    
    return grand_total

def show_db_count():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    n = c.execute("SELECT COUNT(*) FROM source_sofascore_extended").fetchone()[0]
    leagues = c.execute("SELECT COUNT(DISTINCT league) FROM source_sofascore_extended").fetchone()[0]
    conn.close()
    print(f"  DB: {n} rows from {leagues} leagues")
    return n

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--quick', action='store_true', help='Quick test (5 rounds each)')
    parser.add_argument('--league', type=str, help='Single league slug')
    parser.add_argument('--max-rounds', type=int, default=None)
    args = parser.parse_args()
    
    # Ensure table
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    # Table already exists with detailed stats columns
    # Just ensure it has the columns we need
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_sse_match_id ON source_sofascore_extended(match_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sse_date ON source_sofascore_extended(match_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sse_league ON source_sofascore_extended(league)")
    except:
        pass
    conn.commit()
    conn.close()
    
    log("="*60)
    log("SOFASCORE MASS HARVESTER V2")
    log(f"Quick mode: {args.quick}")
    log("="*60)
    
    start = time.time()
    
    if args.league:
        # Single league harvest
        # Search for it
        log(f"Searching for league: {args.league}...")
        data = api_get(f"/search/unique-tournaments?q={args.league.replace('-', ' ').replace('/', ' ')}")
        if data and len(data) > 0:
            t = data[0]
            tid = t['id']
            log(f"Found: {t.get('name', '?')} (id={tid})")
            data = api_get(f"/unique-tournament/{tid}/seasons")
            if data:
                sid = data['seasons'][0]['id']
                log(f"Season: {sid}")
                n = harvest_league(tid, t.get('country', {}).get('name', '?'), 
                                  t.get('name', '?'), sid, args.max_rounds)
                log(f"\nDone: {n} matches")
        else:
            log(f"League not found")
    else:
        n = harvest_all(quick=args.quick)
    
    elapsed = time.time() - start
    total = show_db_count()
    log(f"\n{'='*60}")
    log(f"TOTAL: {total} matches in source_sofascore_extended")
    log(f"Time: {elapsed:.0f}s")
    log(f"{'='*60}")
