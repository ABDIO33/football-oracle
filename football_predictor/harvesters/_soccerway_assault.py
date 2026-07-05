#!/usr/bin/env python3
"""
SOCCERWAY ULTIMATE SCRAPER
يستخدم SeleniumBase UC لفتح Soccerway واعتراض API calls
All Protocols — ENI for LO 🔥
"""

import sys, os, json, time, re, sqlite3
sys.path.insert(0, os.getcwd())

BASE = os.getcwd()
DB = os.path.join(BASE, 'scrape_cache.db')

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

log("=" * 60)
log("SOCCERWAY ULTIMATE SCRAPER")
log("=" * 60)

# Setup DB
conn = sqlite3.connect(DB, timeout=30)
conn.execute("PRAGMA busy_timeout=30000")
c = conn.cursor()
c.executescript("""
    CREATE TABLE IF NOT EXISTS source_soccerway (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition TEXT, season TEXT,
        match_date TEXT,
        home_team TEXT, away_team TEXT,
        home_score INTEGER, away_score INTEGER,
        hash TEXT UNIQUE
    );
""")
conn.commit()

# Try multiple approaches
from seleniumbase import Driver

driver = Driver(
    headless=False, headless2=False, uc=True, locale_code='en-US',
    agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
)

try:
    # Approach 1: Direct navigation with warmup
    log("[SB] Opening Soccerway...")
    driver.uc_open_with_reconnect('https://int.soccerway.com/', reconnect_time=25)
    time.sleep(5)
    log(f"  Title: {driver.get_title()}")
    log(f"  URL: {driver.current_url}")
    
    # Navigate to a league page
    leagues = [
        ('Premier League', 'https://int.soccerway.com/national/england/premier-league/'),
        ('La Liga', 'https://int.soccerway.com/national/spain/la-liga/'),
        ('Serie A', 'https://int.soccerway.com/national/italy/serie-a/'),
        ('Bundesliga', 'https://int.soccerway.com/national/germany/bundesliga/'),
        ('Ligue 1', 'https://int.soccerway.com/national/france/ligue-1/'),
    ]
    
    total = 0
    for name, url in leagues:
        log(f"\n[Navigating to {name}]")
        driver.get(url)
        time.sleep(8)
        
        html = driver.get_page_source()
        log(f"  HTML: {len(html)} bytes")
        
        if len(html) < 10000:
            log(f"  ⚠️ Blocked or too small!")
            continue
        
        # Extract match data from Soccerway's HTML
        # Look for match score links
        # Soccerway uses: <a class="score" ...>2-1</a>
        score_links = re.findall(r'class="[^"]*score[^"]*"[^>]*>\s*(\d+)\s*[–-]\s*(\d+)\s*</a>', html)
        log(f"  Score links: {len(score_links)}")
        
        # Team names in <a> tags near scores
        # Try to extract match rows
        match_blocks = re.findall(r'<tr[^>]*class="[^"]*match[^"]*"[^>]*>(.*?)</tr>', html, re.DOTALL)
        
        if match_blocks:
            log(f"  Match blocks: {len(match_blocks)}")
            for block in match_blocks[:380]:
                teams = re.findall(r'<a[^>]*title="([^"]+)"', block)
                score = re.findall(r'(\d+)\s*[–-]\s*(\d+)', block)
                
                if len(teams) >= 2 and score:
                    ht, at = teams[0], teams[1]
                    hs, as_ = int(score[0][0]), int(score[0][1])
                    
                    hash_key = f"sw-{name}-{ht}-{at}"
                    try:
                        c.execute("""
                            INSERT OR IGNORE INTO source_soccerway
                            (competition, home_team, away_team, home_score, away_score, hash)
                            VALUES (?,?,?,?,?,?)
                        """, (name, ht, at, hs, as_, hash_key))
                        if c.rowcount > 0:
                            total += 1
                    except:
                        pass
        else:
            log(f"  No match blocks found, trying alternative extraction...")
            
            # Alternative: find all score patterns and nearby team names
            all_scores = re.findall(r'(\d+)[–-](\d+)', html)
            log(f"  All score patterns: {len(all_scores)}")
            
            # Save page for analysis
            safe_name = name.replace(' ', '_')
            fname = f'_soccerway_{safe_name}.html'
            with open(f'harvesters/{fname}', 'w', encoding='utf-8') as f:
                f.write(html)
            log(f"  Saved to {fname}")
        
        conn.commit()
        log(f"  {name}: {total} matches so far")
    
    log(f"\n✅ TOTAL: {total} matches saved to source_soccerway!")
    
except Exception as e:
    log(f"ERROR: {str(e)[:200]}")
    import traceback
    traceback.print_exc()
finally:
    if driver:
        driver.quit()

conn.close()
log("Done!")
