"""
lineup_backfill_parallel.py — Fast parallel SofaScore lineup fetcher
"""
import sys, os, sqlite3, json, time, random
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
import curl_cffi.requests as req

HEADERS = {"x-requested-with": "XMLHttpRequest"}

def get_missing():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.home_team, r.away_team
        FROM sofa_historical_results r
        WHERE r.status_type='finished'
        AND r.id >= 15000000
        AND r.id NOT IN (SELECT event_id FROM sofa_lineups)
        ORDER BY r.id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def fetch_one(mid):
    url = f"https://api.sofascore.com/api/v1/event/{mid}/lineups"
    for _ in range(2):
        try:
            r = req.get(url, impersonate="chrome120", headers=HEADERS, timeout=10)
            if r.status_code == 200:
                return r.json()
            return None
        except:
            time.sleep(1)
    return None

def save(mid, data):
    if not data:
        return False
    try:
        h = data.get('home', {}); a = data.get('away', {})
        conn = sqlite3.connect(DB)
        conn.execute("INSERT OR REPLACE INTO sofa_lineups (event_id, home_formation, away_formation, home_players_json, away_players_json) VALUES (?,?,?,?,?)",
            (mid, h.get('formation',''), a.get('formation',''),
             json.dumps(h.get('players',[])), json.dumps(a.get('players',[]))))
        conn.commit()
        conn.close()
        return True
    except:
        return False

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

missing = get_missing()
total = len(missing)
done = 0
saved = 0

print(f"Target: {total} matches (ID >= 15M)")
print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
print()

with ThreadPoolExecutor(max_workers=6) as ex:
    fut_map = {ex.submit(fetch_one, m[0]): m for m in missing}
    for f in as_completed(fut_map):
        mid, ht, at = fut_map[f]
        done += 1
        data = f.result()
        if data and save(mid, data):
            saved += 1
        time.sleep(random.uniform(0.2, 0.4))
        if done % 200 == 0:
            pct = done / total * 100
            print(f"  [{done:,}/{total:,}] {pct:.1f}% — saved {saved} ({(saved/max(done,1))*100:.0f}%)")

print(f"\nDone! Saved {saved:,} / {total:,}")
print(f"Finished: {datetime.now().strftime('%H:%M:%S')}")
