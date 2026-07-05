"""
Smart Tournament Scanner — uses existing tournaments to find missing seasons
"""
import sys, os, json, time, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# Get all tournaments in DB
conn = sqlite3.connect(DB)
rows = conn.execute("""
    SELECT unique_tournament_id, MAX(home_league) as home_league, COUNT(*) as cnt
    FROM sofa_historical_results 
    WHERE unique_tournament_id IS NOT NULL 
    GROUP BY unique_tournament_id
    ORDER BY cnt DESC
""").fetchall()
conn.close()

tids = []
for r in rows:
    tid = r[0]
    league = r[1] if len(r) > 1 else '?'
    tids.append((tid, league))

print(f'Found {len(tids)} tournaments in DB')
print(f'{'TID':>6} {'Seasons':>8} {'Matches':>10}  League')
print('-'*60)

conn = sqlite3.connect(DB)
ranked = []
for tid, league in tids:
    cur = conn.execute('SELECT COUNT(*) FROM sofa_historical_results WHERE unique_tournament_id = ?', (tid,))
    count = cur.fetchone()[0]
    
    # Get seasons for this tournament
    data = _get(f'/unique-tournament/{tid}/seasons', cache_minutes=1440)
    seasons = []
    if data and 'seasons' in data:
        for s in data['seasons']:
            sid = s.get('id')
            year = s.get('year', '?')
            seasons.append({'id': sid, 'year': year})
    
    # Get which seasons we have matches for
    our_seasons = set()
    if seasons:
        for s in seasons:
            cur2 = conn.execute("""
                SELECT COUNT(*) FROM sofa_historical_results 
                WHERE unique_tournament_id = ? AND season_id = ?
            """, (tid, s['id']))
            sc = cur2.fetchone()[0]
            if sc > 0:
                our_seasons.add(s['id'])
    
    ranked.append({
        'tid': tid, 'league': league, 'count': count,
        'total_seasons': len(seasons),
        'our_seasons': len(our_seasons),
        'seasons': seasons,
        'our_season_ids': our_seasons,
    })
    print(f'{tid:>6} {len(our_seasons):>3}/{len(seasons):>3}  {count:>8}  {league[:40]}')
    time.sleep(0.3)

conn.close()

# Sort by missing seasons potential
ranked.sort(key=lambda x: x['total_seasons'] - x['our_seasons'], reverse=True)

print(f'\n\nTop 10 with MOST missing seasons:')
print(f'{'TID':>6} {'Missing':>8} {'Seasons':>7}  League')
print('-'*50)
for r in ranked[:10]:
    missing = r['total_seasons'] - r['our_seasons']
    print(f'{r["tid"]:>6} {missing:>8} {r["total_seasons"]:>3}/{r["our_seasons"]:>3}  {r["league"][:40]}')

# Calculate total potential matches from missing seasons
from sofascore_scraper import _get as api_get

print(f'\n\nFetching missing seasons (up to 200 seasons)...')
total_new = 0
new_matches_inserted = 0

for r in ranked[:30]:  # Process top 30 by missing seasons
    missing_seasons = [s for s in r['seasons'] if s['id'] not in r['our_season_ids']]
    if not missing_seasons:
        continue
    
    for s in missing_seasons[:5]:  # Max 5 missing seasons per tournament
        time.sleep(0.3)
        data = api_get(f'/unique-tournament/{r["tid"]}/season/{s["id"]}/events/last/0', cache_minutes=60)
        if not data:
            continue
        
        events = []
        for key in ('events', 'tournamentMatches', 'matches'):
            if key in data:
                events = data[key]
                break
        
        if not events:
            continue
        
        conn = sqlite3.connect(DB)
        inserted = 0
        for e in events:
            try:
                hs = e.get('homeScore', e.get('homeScore', {}))
                aw = e.get('awayScore', e.get('awayScore', {}))
                if isinstance(hs, dict):
                    hs = hs.get('current', hs.get('value', hs.get('display', 0)))
                if isinstance(aw, dict):
                    aw = aw.get('current', aw.get('value', aw.get('display', 0)))
                
                home_team = e.get('homeTeam', {}).get('name', '')
                away_team = e.get('awayTeam', {}).get('name', '')
                event_id = e.get('id', 0)
                date = e.get('startTimestamp', 0)
                
                if hs is None or aw is None or not home_team or not away_team:
                    continue
                
                import time as tm
                from datetime import datetime
                date_str = datetime.fromtimestamp(date).strftime('%Y-%m-%d') if date else ''
                
                conn.execute("""
                    INSERT OR IGNORE INTO sofa_historical_results
                    (id, home_team, away_team, home_score, away_score, date, 
                     home_league, start_timestamp, status_type, unique_tournament_id, season_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'finished', ?, ?)
                """, (
                    event_id * -1, home_team, away_team, int(hs), int(aw),
                    date_str, r['league'], date, r['tid'], s['id']
                ))
                if conn.total_changes > 0:
                    inserted += 1
            except:
                pass
        
        conn.commit()
        conn.close()
        
        if inserted > 0:
            new_matches_inserted += inserted
            print(f'  [{r["tid"]}] {r["league"][:30]} season {s["year"]}: +{inserted}')
            total_new += inserted

print(f'\n\n=== TOTAL NEW MATCHES ADDED: {new_matches_inserted} ===')
conn = sqlite3.connect(DB)
final_count = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
conn.close()
print(f'Total in DB: {final_count}')
