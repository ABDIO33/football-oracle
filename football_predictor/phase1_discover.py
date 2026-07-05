"""
Phase 1-A: Discover ALL SofaScore football tournaments + seasons
Bulk data collection — target: 500K-1M matches
"""
import sys, os, json, time, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# Known football tournament IDs (SofaScore)
# Start with major ones, we'll discover more
FOOTBALL_TOURNAMENTS = list(range(1, 150))  # Scan IDs 1-150

print("=== Phase 1-A: Tournament Discovery ===")
conn = sqlite3.connect(DB)

# First, check what tournaments we already have
existing = set()
cur = conn.execute('SELECT DISTINCT unique_tournament_id FROM sofa_historical_results WHERE unique_tournament_id IS NOT NULL')
for r in cur.fetchall():
    existing.add(r[0])
print(f'Existing tournaments in DB: {len(existing)}')
print(f'IDs: {sorted(existing)[:20]}...')

# Discover tournaments from SofaScore
found_tournaments = {}
for tid in range(1, 200):
    data = _get(f'/unique-tournament/{tid}', cache_minutes=1440*7)
    if data:
        t = data.get('uniqueTournament', {})
        if t.get('sport', {}).get('slug') == 'football' or not t.get('sport'):
            name = t.get('name', 'unknown')
            slug = t.get('slug', '')
            seasons = data.get('seasons', [])
            has_football = any(s.get('year', 0) >= 2010 for s in seasons)
            if has_football or tid in existing:
                found_tournaments[tid] = {
                    'name': name,
                    'slug': slug,
                    'seasons': [(s.get('year'), s.get('id')) for s in seasons if s.get('year', 0) >= 2010]
                }
                print(f'  [{tid}] {name}: {len(found_tournaments[tid]["seasons"])} seasons (2010+)')
    if tid % 50 == 0:
        print(f'  Scanned {tid}/200...')

# Save discovered tournaments
with open(os.path.join(os.path.dirname(__file__), 'data', 'tournaments.json'), 'w') as f:
    json.dump(found_tournaments, f, indent=2)

print(f'\nTotal football tournaments found: {len(found_tournaments)}')
total_potential = sum(len(t['seasons']) for t in found_tournaments.values())
print(f'Total season-years: {total_potential}')

conn.close()
print('Done - tournament discovery complete')
