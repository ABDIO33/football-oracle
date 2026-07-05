"""
run_lineup_backfill_10M.py — Backfill lineups for 10M-15M event ID range
Slower pacing to avoid SofaScore rate limits
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
        AND r.id >= 10000000 AND r.id <= 14999999
        AND r.id NOT IN (SELECT event_id FROM sofa_lineups)
        AND r.id NOT IN (SELECT event_id FROM lineup_backfill_progress WHERE status='done' OR status='skipped')
        ORDER BY r.id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def fetch_one(mid):
    url = f"https://api.sofascore.com/api/v1/event/{mid}/lineups"
    for attempt in range(3):
        try:
            r = req.get(url, impersonate="chrome120", headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                time.sleep(wait)
                continue
            return None
        except:
            time.sleep(2)
    return None

def save(mid, data):
    now = datetime.utcnow().isoformat()
    if not data:
        conn = sqlite3.connect(DB)
        conn.execute("INSERT OR REPLACE INTO lineup_backfill_progress (event_id, fetched_at, status) VALUES (?, ?, 'skipped')", (mid, now))
        conn.commit()
        conn.close()
        return False
    try:
        h = data.get('home', {}); a = data.get('away', {})
        conn = sqlite3.connect(DB)
        conn.execute("""INSERT OR REPLACE INTO sofa_lineups
            (event_id, home_formation, away_formation, home_players_json, away_players_json, confirmed)
            VALUES (?,?,?,?,?,?)""",
            (mid, h.get('formation',''), a.get('formation',''),
             json.dumps(h.get('players',[])), json.dumps(a.get('players',[])),
             1 if data.get('confirmed') else 0))
        conn.execute("INSERT OR REPLACE INTO lineup_backfill_progress (event_id, fetched_at, status) VALUES (?, ?, 'done')", (mid, now))
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
start = time.time()

print(f"Target: {total} matches (ID 10M-15M)")
print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
print()

rate_limiter = []

with ThreadPoolExecutor(max_workers=2) as ex:
    fut_map = {ex.submit(fetch_one, m[0]): m for m in missing}
    for f in as_completed(fut_map):
        mid, ht, at = fut_map[f]
        done += 1
        data = f.result()
        if data and save(mid, data):
            saved += 1
        if done % 100 == 0:
            elapsed = time.time() - start
            rate = done / elapsed
            remaining = (total - done) / rate if rate > 0 else 0
            pct = done / total * 100
            print(f"  [{done:,}/{total:,}] {pct:.1f}% — saved {saved:,} ({rate:.1f}/s, {remaining/60:.0f}min remaining)")

elapsed = time.time() - start
print(f"\nDone! Saved {saved:,} / {total:,} in {elapsed/60:.1f} min")
print(f"Finished: {datetime.now().strftime('%H:%M:%S')}")
