"""
fetch_referees.py — Collect referee data from SofaScore API
Referee data is at event.referee in /event/{id} endpoint
"""
import sys, os, json, time, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
from sofascore_scraper import _get
from datetime import datetime

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sofa_referee (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT,
            games INTEGER DEFAULT 0,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0,
            yellow_red_cards INTEGER DEFAULT 0,
            country_name TEXT,
            country_alpha2 TEXT,
            country_alpha3 TEXT,
            first_seen INTEGER,
            last_seen INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sofa_referee_assignments (
            match_id INTEGER PRIMARY KEY,
            referee_id INTEGER,
            fetched_at INTEGER DEFAULT (unixepoch()),
            FOREIGN KEY (referee_id) REFERENCES sofa_referee(id)
        )
    """)
    conn.commit()
    conn.close()

def get_event_referee(event_id):
    data = _get(f'/event/{event_id}', cache_minutes=1440)
    if not data:
        return None
    event = data.get('event', {})
    return event.get('referee')

def save_referee(ref):
    if not ref:
        return None
    rid = ref.get('id')
    if not rid:
        return None
    country = ref.get('country', {}) or {}
    conn = sqlite3.connect(DB)
    conn.execute("""INSERT OR REPLACE INTO sofa_referee
        (id, name, slug, games, yellow_cards, red_cards, yellow_red_cards,
         country_name, country_alpha2, country_alpha3, first_seen, last_seen)
        VALUES (?,?,?,?,?,?,?,?,?,?,COALESCE((SELECT first_seen FROM sofa_referee WHERE id=?), unixepoch()), unixepoch())""",
        (rid, ref.get('name',''), ref.get('slug',''),
         ref.get('games',0), ref.get('yellowCards',0), ref.get('redCards',0), ref.get('yellowRedCards',0),
         country.get('name'), country.get('alpha2'), country.get('alpha3'),
         rid))
    conn.commit()
    conn.close()
    return rid

def save_assignment(match_id, referee_id):
    if not referee_id:
        return
    conn = sqlite3.connect(DB)
    conn.execute("""INSERT OR REPLACE INTO sofa_referee_assignments
        (match_id, referee_id, fetched_at) VALUES (?,?, unixepoch())""",
        (match_id, referee_id))
    conn.commit()
    conn.close()

log('Referee data collection started')
init_db()

conn = sqlite3.connect(DB)
matches = conn.execute("""
    SELECT r.id, r.home_team, r.away_team, r.tournament, r.date
    FROM sofa_historical_results r
    WHERE r.status_type = 'finished'
    AND r.id > 0
    AND r.id NOT IN (SELECT match_id FROM sofa_referee_assignments)
    AND r.date >= '2020-01-01'
    ORDER BY r.id DESC
    LIMIT 50000
""").fetchall()
conn.close()

log(f'Target: {len(matches)} matches (2020+, positive IDs, no referee)')

done = 0
found = 0
for mid, ht, at, tmt, dt in matches:
    done += 1
    ref = get_event_referee(mid)
    if ref:
        rid = save_referee(ref)
        save_assignment(mid, rid)
        found += 1
    if done % 100 == 0:
        log(f'  [{done}/{len(matches)}] Found refs: {found} ({found/max(done,1)*100:.1f}%)')

log(f'\nDone! Processed {done}, found referees for {found} matches')
