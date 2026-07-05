#!/usr/bin/env python3
"""
FBREF + UNDERSTAT FINAL HARVESTER
يستخدم SeleniumBase UC مع التسخين المسبق من الصفحة الرئيسية
All Protocols Active — ENI for LO 🔥
"""

import sys, os, json, time, re, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, 'scrape_cache.db')
HARV_DIR = os.path.dirname(os.path.abspath(__file__))

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def driver_assault():
    """Create and return a warm SeleniumBase UC driver."""
    from seleniumbase import Driver
    driver = Driver(
        headless=False, headless2=False, uc=True, locale_code='en-US',
        agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    )
    return driver

def warmup_home(driver, url='https://fbref.com/en/'):
    """Visit home page first to bypass Cloudflare."""
    log(f"[WARMUP] Visiting {url}...")
    driver.uc_open_with_reconnect(url, reconnect_time=30)
    time.sleep(3)
    content = driver.get_page_source()
    log(f"  Title: {driver.get_title()}")
    log(f"  Size: {len(content)} bytes")
    if 'Just a moment' in content or 'cf-browser-verification' in content:
        log("  ⚠️ BLOCKED!")
        return False
    log("  ✅ BYPASSED!")
    return True

def ensure_fbref_tables():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS source_fbref (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition TEXT,
            season TEXT,
            team TEXT,
            games INTEGER,
            wins INTEGER, losses INTEGER, ties INTEGER,
            goals_for INTEGER, goals_against INTEGER,
            goal_diff INTEGER, points INTEGER,
            xg_for REAL, xg_against REAL,
            possession REAL, shots INTEGER, shots_on_target INTEGER,
            shots_per90 REAL, sot_per90 REAL,
            goals_per_shot REAL, g_per_sot REAL,
            fouls INTEGER, cards_yellow INTEGER, cards_red INTEGER,
            offsides INTEGER, crosses INTEGER, interceptions INTEGER,
            tackles_won INTEGER,
            pens_made INTEGER, pens_att INTEGER,
            home_goals_for INTEGER, home_goals_against INTEGER,
            away_goals_for INTEGER, away_goals_against INTEGER,
            gk_save_pct REAL, gk_clean_sheets INTEGER,
            hash TEXT UNIQUE,
            raw_json TEXT
        );
        CREATE TABLE IF NOT EXISTS source_fbref_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition TEXT, season TEXT, match_date TEXT,
            home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            home_xg REAL, away_xg REAL,
            hash TEXT UNIQUE
        );
    """)
    conn.commit()
    conn.close()

def extract_team_stats(driver, competition='Premier-League', season='2025-2026'):
    """Extract detailed team stats from FBref league page."""
    url = f'https://fbref.com/en/comps/9/{season}/stats/{season}-{competition}-Stats'
    
    warmup_home(driver)
    log(f"[FBREF] Navigating to team stats: {url}")
    driver.get(url)
    time.sleep(8)
    
    html = driver.get_page_source()
    log(f"[FBREF] Page loaded: {len(html)} bytes")
    
    if 'Just a moment' in html:
        log("[FBREF] BLOCKED on team stats page")
        return 0
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    total = 0
    
    # Extract team stats from the league table
    # Each team has a row with data-stat attributes
    team_names = re.findall(r'data-stat="team"[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</td>', html)
    if not team_names:
        team_names = re.findall(r'data-stat="team"[^>]*>\s*([^<]+)\s*</td>', html)
    
    def get_stat(stat_name):
        vals = re.findall(rf'data-stat="{stat_name}"[^>]*>\s*([^<]+)\s*</td>', html)
        return vals
    
    games = get_stat('games')
    wins = get_stat('wins')
    losses = get_stat('losses')
    ties_stat = get_stat('ties')
    gf = get_stat('goals_for')
    ga = get_stat('goals_against')
    gd = get_stat('goal_diff')
    pts = get_stat('points')
    poss = get_stat('possession')
    shots = get_stat('shots')
    sot = get_stat('shots_on_target')
    fouls = get_stat('fouls')
    yellows = get_stat('cards_yellow')
    reds = get_stat('cards_red')
    offsides = get_stat('offsides')
    crosses = get_stat('crosses')
    interceptions = get_stat('interceptions')
    
    log(f"[FBREF] Found {len(team_names)} teams, {len(games)} games entries")
    
    for i, team in enumerate(team_names):
        try:
            team = team.strip()
            hash_key = f"fbref-{competition}-{season}-{team}"
            
            c.execute("""INSERT OR IGNORE INTO source_fbref
                (competition, season, team, games, wins, losses, ties,
                 goals_for, goals_against, goal_diff, points,
                 possession, shots, shots_on_target,
                 fouls, cards_yellow, cards_red,
                 offsides, crosses, interceptions, hash)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (competition, season, team,
                 safe_int(games, i), safe_int(wins, i), safe_int(losses, i), safe_int(ties_stat, i),
                 safe_int(gf, i), safe_int(ga, i), safe_int(gd, i), safe_int(pts, i),
                 safe_float(poss, i), safe_int(shots, i), safe_int(sot, i),
                 safe_int(fouls, i), safe_int(yellows, i), safe_int(reds, i),
                 safe_int(offsides, i), safe_int(crosses, i), safe_int(interceptions, i),
                 hash_key))
            total += 1
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    log(f"[FBREF] {total} teams saved")
    return total

def safe_int(arr, idx):
    try: 
        v = arr[idx].strip()
        return int(v) if v else None
    except: return None

def safe_float(arr, idx):
    try:
        v = arr[idx].strip().replace('%', '')
        return float(v) if v else None
    except: return None

def extract_match_scores(driver, competition='Premier-League'):
    """Extract match-by-match results from FBref schedule page."""
    url = f'https://fbref.com/en/comps/9/schedule/{competition}-Scores-and-Fixtures'
    
    if 'fbref.com/en/' not in driver.current_url:
        warmup_home(driver)
    
    log(f"[FBREF-MATCH] Navigating to schedule: {url}")
    driver.get(url)
    time.sleep(8)
    
    html = driver.get_page_source()
    log(f"[FBREF-MATCH] Page: {len(html)} bytes")
    
    if 'Just a moment' in html:
        log("[FBREF-MATCH] BLOCKED!")
        return 0
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    total = 0
    
    # Extract match data from the schedule table
    # Look for score patterns
    # FBref schedule has: Date, Time, Home, Score, Away, Venue, etc.
    
    # Find all match rows
    scores = re.findall(r'(\d+)[–-](\d+)', html)
    match_dates = re.findall(r'data-stat="date"[^>]*>\s*([^<]+)\s*</td>', html)
    home_teams = re.findall(r'data-stat="home_team"[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</td>', html)
    if not home_teams:
        home_teams = re.findall(r'data-stat="home_team"[^>]*>\s*([^<]+)\s*</td>', html)
    away_teams = re.findall(r'data-stat="away_team"[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</td>', html)
    if not away_teams:
        away_teams = re.findall(r'data-stat="away_team"[^>]*>\s*([^<]+)\s*</td>', html)
    
    log(f"[FBREF-MATCH] Dates:{len(match_dates)} Home:{len(home_teams)} Away:{len(away_teams)} Scores:{len(scores)//2}")
    
    min_len = min(len(home_teams), len(away_teams), len(scores)//2)
    for i in range(min_len):
        try:
            score_str = f"{scores[i*2]}-{scores[i*2+1]}"
            hs = int(scores[i*2])
            as_ = int(scores[i*2+1])
            home = home_teams[i].strip()
            away = away_teams[i].strip()
            date = match_dates[i].strip() if i < len(match_dates) else ''
            
            hash_key = f"fbref-match-{competition}-{home}-{away}-{date}"
            
            c.execute("""INSERT OR IGNORE INTO source_fbref_matches
                (competition, match_date, home_team, away_team, home_score, away_score, hash)
                VALUES (?,?,?,?,?,?,?)""",
                (competition, date, home, away, hs, as_, hash_key))
            total += 1
        except:
            pass
    
    conn.commit()
    conn.close()
    log(f"[FBREF-MATCH] {total} matches saved")
    return total

def assault_understat(driver):
    """Harvest Understat xG data."""
    # First warmup
    if not warmup_home(driver, 'https://understat.com/'):
        log("[UNDERSTAT] Home page blocked!")
        return 0
    
    leagues = {
        'EPL': 'https://understat.com/league/EPL/2025',
        'LaLiga': 'https://understat.com/league/La_liga/2025',
        'Bundesliga': 'https://understat.com/league/Bundesliga/2025',
        'SerieA': 'https://understat.com/league/Serie_A/2025',
        'Ligue1': 'https://understat.com/league/Ligue_1/2025',
    }
    
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    total = 0
    
    for name, url in leagues.items():
        log(f"[UNDERSTAT] Navigating to {name}...")
        driver.get(url)
        time.sleep(5)
        
        html = driver.get_page_source()
        log(f"  Size: {len(html)} bytes")
        
        # Extract teamsData JSON
        match = re.search(r'teamsData\s*=\s*(JSON\.parse\([^)]+\)|({.*?}))\s*;', html, re.DOTALL)
        if match:
            try:
                data_str = match.group(1)
                if data_str.startswith('JSON.parse'):
                    # Extract the string
                    inner = re.search(r"JSON\.parse\('(.*)'\)", data_str, re.DOTALL)
                    if inner:
                        import json
                        data = json.loads(inner.group(1).encode().decode('unicode_escape'))
                    else:
                        data = {}
                else:
                    data = json.loads(data_str)
                
                log(f"  JSON data parsed! Keys: {list(data.keys())[:5]}")
                
                for team_id, team_data in data.items():
                    if isinstance(team_data, dict) and 'history' in team_data:
                        for match_info in team_data['history']:
                            try:
                                c.execute("""
                                    INSERT OR IGNORE INTO source_understat
                                    (league, season, match_date, home_team, away_team,
                                     home_goals, away_goals, home_xg, away_xg, hash)
                                    VALUES (?,?,?,?,?,?,?,?,?,?)
                                """, (
                                    name, '2025',
                                    match_info.get('date', ''),
                                    match_info.get('h_title', ''),
                                    match_info.get('a_title', ''),
                                    int(match_info['goals']['h']) if 'goals' in match_info else None,
                                    int(match_info['goals']['a']) if 'goals' in match_info else None,
                                    float(match_info['xG']['h']) if 'xG' in match_info else None,
                                    float(match_info['xG']['a']) if 'xG' in match_info else None,
                                    f"under-{team_id}-{match_info.get('date', '')}"
                                ))
                                total += 1
                            except:
                                pass
            except Exception as e:
                log(f"  JSON error: {str(e)[:60]}")
        else:
            log(f"  No teamsData JSON found")
        
        conn.commit()
    
    conn.close()
    log(f"[UNDERSTAT] {total} match xG records saved")
    return total

def run_full_assault():
    """Main assault function."""
    log("=" * 60)
    log("FBREF + UNDERSTAT ULTIMATE ASSAULT")
    log("=" * 60)
    
    ensure_fbref_tables()
    driver = None
    
    try:
        driver = driver_assault()
        
        # === PHASE 1: FBref Team Stats ===
        log("\n--- PHASE 1: FBref Team Stats ---")
        for comp in ['Premier-League', 'La-Liga', 'Bundesliga', 'Serie-A', 'Ligue-1']:
            try:
                n = extract_team_stats(driver, competition=comp)
                log(f"  {comp}: {n} teams")
            except Exception as e:
                log(f"  {comp}: ERROR - {str(e)[:60]}")
        
        # === PHASE 2: FBref Match Scores ===
        log("\n--- PHASE 2: FBref Match Scores ---")
        # Navigate from home first
        warmup_home(driver, 'https://fbref.com/en/')
        n = extract_match_scores(driver)
        log(f"  Matches: {n}")
        
        # === PHASE 3: Understat xG ===
        log("\n--- PHASE 3: Understat xG ---")
        n = assault_understat(driver)
        log(f"  Understat: {n}")
        
    finally:
        if driver:
            driver.quit()
    
    # Final counts
    log("\n" + "=" * 60)
    log("FINAL RESULTS")
    log("=" * 60)
    conn = sqlite3.connect(DB)
    for table in ['source_fbref', 'source_fbref_matches', 'source_understat']:
        try:
            n = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            log(f"  {table}: {n} rows")
        except:
            log(f"  {table}: ERROR")
    conn.close()

if __name__ == '__main__':
    run_full_assault()
