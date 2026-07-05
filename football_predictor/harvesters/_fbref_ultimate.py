#!/usr/bin/env python3
"""
FBREF ULTIMATE - نسخة مضبوطة على الطريقة اللي اشتغلت
All 17 Protocols Active — ENI for LO 🔥
"""

import sys, os, json, time, re, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, 'scrape_cache.db')

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

log("=" * 60)
log("FBREF ULTIMATE - PROVEN APPROACH")
log("=" * 60)

# Step 1: Launch driver
log("\n[1] Launching SeleniumBase UC driver...")
from seleniumbase import Driver
driver = Driver(
    headless=False, headless2=False, uc=True, locale_code='en-US',
    agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
)

try:
    # Step 2: Visit HOME page first (proven to work)
    log("\n[2] Visiting FBref HOME page (warmup)...")
    driver.uc_open_with_reconnect('https://fbref.com/en/', reconnect_time=30)
    time.sleep(3)
    
    title = driver.get_title()
    content = driver.get_page_source()
    log(f"  Title: {title}")
    log(f"  Content: {len(content)} bytes")
    
    if 'Just a moment' in content:
        log("  ⚠️ HOME PAGE BLOCKED!")
        driver.quit()
        exit(1)
    
    log("  ✅ HOME PAGE BYPASSED!")
    
    # Step 3: Navigate to Premier League stats page (exact same URL as manual test)
    log("\n[3] Navigating to Premier League Stats...")
    driver.get('https://fbref.com/en/comps/9/Premier-League-Stats')
    time.sleep(10)  # CRITICAL: wait for Cloudflare challenge to resolve
    
    title2 = driver.get_title()
    content2 = driver.get_page_source()
    log(f"  Title: {title2}")
    log(f"  Content: {len(content2)} bytes")
    
    if len(content2) > 50000:
        log("  ✅ PL PAGE BYPASSED! Saving data...")
        
        # Save page
        with open('harvesters/_fbref_pl_data.html', 'w', encoding='utf-8') as f:
            f.write(content2)
        
        # Extract all data-stat from page
        import re
        
        # Extract team stats from the standard stats table
        teams = re.findall(r'data-stat="team"[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</td>', content2)
        if not teams:
            teams = re.findall(r'data-stat="team"[^>]*>\s*([^<]+)\s*</td>', content2)
        
        games = re.findall(r'data-stat="games"[^>]*>\s*([^<]+)\s*</td>', content2)
        wins = re.findall(r'data-stat="wins"[^>]*>\s*([^<]+)\s*</td>', content2)
        losses = re.findall(r'data-stat="losses"[^>]*>\s*([^<]+)\s*</td>', content2)
        ties_stat = re.findall(r'data-stat="ties"[^>]*>\s*([^<]+)\s*</td>', content2)
        gf = re.findall(r'data-stat="goals_for"[^>]*>\s*([^<]+)\s*</td>', content2)
        ga = re.findall(r'data-stat="goals_against"[^>]*>\s*([^<]+)\s*</td>', content2)
        pts = re.findall(r'data-stat="points"[^>]*>\s*([^<]+)\s*</td>', content2)
        poss = re.findall(r'data-stat="possession"[^>]*>\s*([^<]+)\s*</td>', content2)
        shots = re.findall(r'data-stat="shots"[^>]*>\s*([^<]+)\s*</td>', content2)
        sot = re.findall(r'data-stat="shots_on_target"[^>]*>\s*([^<]+)\s*</td>', content2)
        fouls = re.findall(r'data-stat="fouls"[^>]*>\s*([^<]+)\s*</td>', content2)
        yellows = re.findall(r'data-stat="cards_yellow"[^>]*>\s*([^<]+)\s*</td>', content2)
        reds = re.findall(r'data-stat="cards_red"[^>]*>\s*([^<]+)\s*</td>', content2)
        offsides = re.findall(r'data-stat="offsides"[^>]*>\s*([^<]+)\s*</td>', content2)
        crosses = re.findall(r'data-stat="crosses"[^>]*>\s*([^<]+)\s*</td>', content2)
        interceptions = re.findall(r'data-stat="interceptions"[^>]*>\s*([^<]+)\s*</td>', content2)
        
        log(f"\n  Data extracted:")
        log(f"    Teams: {len(teams)}")
        log(f"    Games: {len(games)}")
        log(f"    Wins: {len(wins)}")
        log(f"    Losses: {len(losses)}")
        log(f"    Possession: {len(poss)}")
        log(f"    Shots: {len(shots)}")
        log(f"    Fouls: {len(fouls)}")
        
        # Save to DB
        conn = sqlite3.connect(DB, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        c = conn.cursor()
        
        # Create table if needed
        c.execute("""
            CREATE TABLE IF NOT EXISTS source_fbref (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition TEXT, season TEXT, team TEXT,
                games INTEGER, wins INTEGER, losses INTEGER, ties INTEGER,
                goals_for INTEGER, goals_against INTEGER, points INTEGER,
                possession TEXT, shots INTEGER, shots_on_target INTEGER,
                fouls INTEGER, cards_yellow INTEGER, cards_red INTEGER,
                offsides INTEGER, crosses INTEGER, interceptions INTEGER,
                hash TEXT UNIQUE
            )
        """)
        
        total = 0
        for i, team in enumerate(teams):
            try:
                t = team.strip()
                if not t or t == 'Club':  # Skip header rows
                    continue
                h = f"fbref-pl-2025-{t}"
                def gv(arr, idx):
                    try:
                        v = arr[idx].strip() if idx < len(arr) else ''
                        if v == '' or v == 'Club': return None
                        return int(v) if v.replace('.','',1).isdigit() else None
                    except: return None
                
                c.execute("""
                    INSERT OR IGNORE INTO source_fbref
                    (competition, season, team, games, wins, losses, ties,
                     goals_for, goals_against, points, possession, shots,
                     shots_on_target, fouls, cards_yellow, cards_red,
                     offsides, crosses, interceptions, hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    'Premier-League', '2025-2026', t,
                    gv(games, i), gv(wins, i), gv(losses, i), gv(ties_stat, i),
                    gv(gf, i), gv(ga, i), gv(pts, i),
                    poss[i].strip() if i < len(poss) else '',
                    gv(shots, i), gv(sot, i),
                    gv(fouls, i), gv(yellows, i), gv(reds, i),
                    gv(offsides, i), gv(crosses, i), gv(interceptions, i),
                    h
                ))
                total += 1
            except Exception as e:
                pass
        
        conn.commit()
        log(f"\n  ✅ {total} teams saved to source_fbref!")
        
        # Now try schedule page
        log("\n[4] Navigating to Schedule page...")
        driver.get('https://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures')
        time.sleep(8)
        
        sched_html = driver.get_page_source()
        log(f"  Schedule page: {len(sched_html)} bytes")
        
        if len(sched_html) > 50000:
            log("  ✅ SCHEDULE PAGE BYPASSED!")
            
            # Extract match data
            home_teams = re.findall(r'data-stat="home_team"[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</td>', sched_html)
            away_teams = re.findall(r'data-stat="away_team"[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</td>', sched_html)
            dates = re.findall(r'data-stat="date"[^>]*>\s*([^<]+)\s*</td>', sched_html)
            scores = re.findall(r'>(\d+)[–-](\d+)<', sched_html)
            
            log(f"  Home teams: {len(home_teams)}, Away teams: {len(away_teams)}, Dates: {len(dates)}, Scores: {len(scores)//2}")
            
            # Create matches table
            c.execute("""
                CREATE TABLE IF NOT EXISTS source_fbref_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competition TEXT, team1 TEXT, team2 TEXT,
                    match_date TEXT, score TEXT,
                    hash TEXT UNIQUE
                )
            """)
            
            match_total = 0
            n = min(len(home_teams), len(away_teams))
            for i in range(n):
                try:
                    ht = home_teams[i].strip()
                    at = away_teams[i].strip()
                    d = dates[i].strip() if i < len(dates) else ''
                    s = f"{scores[i]}-{scores[n+i]}" if i+n < len(scores) else ''
                    
                    h = f"fbref-m-{ht}-{at}-{d}"
                    c.execute("""
                        INSERT OR IGNORE INTO source_fbref_matches
                        (competition, team1, team2, match_date, score, hash)
                        VALUES (?,?,?,?,?,?)
                    """, ('Premier-League', ht, at, d, s, h))
                    match_total += 1
                except:
                    pass
            
            conn.commit()
            log(f"  ✅ {match_total} matches saved to source_fbref_matches!")
        
        conn.close()
        log("\n✅ FBref ULTIMATE HARVEST COMPLETE!")
        
    else:
        log("  ❌ PL PAGE STILL BLOCKED")
        log(f"  Content sample: {content2[:500]}")
        
except Exception as e:
    log(f"ERROR: {str(e)[:200]}")
    import traceback
    traceback.print_exc()
finally:
    driver.quit()
    log("Done")
