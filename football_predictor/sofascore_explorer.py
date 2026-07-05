"""
SofaScore Tournament Explorer — finds EVERY football tournament & season
"""
import sys, os, json, time, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
from sofascore_scraper import _get

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

def get_categories():
    """Get all football categories"""
    data = _get('/sport/football/categories', cache_minutes=1440)
    if not data or 'categories' not in data:
        # Try alternative endpoint
        data = _get('/sport/football/categories', cache_minutes=1440)
    cats = []
    for c in (data.get('categories', []) if data else []):
        cats.append({'id': c.get('id'), 'name': c.get('name', '?')})
    return cats

def get_tournaments(cat_id):
    """Get all unique tournaments in a category"""
    data = _get(f'/category/{cat_id}/unique-tournaments', cache_minutes=1440)
    if not data:
        return []
    tours = []
    for t in data.get('uniqueTournaments', []):
        tours.append({
            'id': t.get('id'),
            'name': t.get('name', '?'),
            'slug': t.get('slug', ''),
            'hasEventGroup': t.get('hasEventGroup', False),
        })
    return tours

def get_seasons(tid):
    """Get all seasons for a tournament"""
    data = _get(f'/unique-tournament/{tid}/seasons', cache_minutes=1440)
    if not data:
        return []
    seasons = []
    for s in data.get('seasons', []):
        raw = s.get('year', '')
        year_num = 0
        if '/' in str(raw):
            try:
                yr = int(str(raw).split('/')[0])
                year_num = 2000 + yr if yr < 100 else yr
            except:
                continue
        elif isinstance(raw, (int, float)):
            year_num = int(raw)
        else:
            try:
                year_num = int(str(raw)[:4])
            except:
                continue
        seasons.append({
            'id': s.get('id'),
            'year': raw,
            'year_num': year_num,
            'name': s.get('name', '?'),
        })
    return seasons

def get_existing_tournaments():
    """Get tournament IDs already in our DB"""
    conn = sqlite3.connect(DB)
    cur = conn.execute('SELECT DISTINCT unique_tournament_id FROM sofa_historical_results WHERE unique_tournament_id IS NOT NULL')
    existing = set(r[0] for r in cur.fetchall())
    conn.close()
    return existing

def count_events(tid, sid):
    """Count events for a tournament season"""
    total = 0
    offset = 0
    while True:
        data = _get(f'/unique-tournament/{tid}/season/{sid}/events/last/{offset}', cache_minutes=60)
        if not data:
            break
        events = []
        for key in ('events', 'tournamentMatches', 'matches'):
            if key in data:
                events = data[key]
                break
        if not events:
            break
        total += len(events)
        if len(events) < 30:
            break
        has_next = False
        for m in events:
            if m.get('hasNextPage') or m.get('hasNext'):
                has_next = True
                break
        if not has_next:
            # Try next page
            has_next = any(
                e.get('hasNextPage', False) or e.get('hasNext', False)
                for e in events
            )
            if not has_next and len(events) >= 30:
                # Might have more - try anyway
                if offset > 200:
                    break  # Safety limit
        offset += 30
        time.sleep(0.2)
    return total

def scan_events(tid, sid, limit=30):
    """Quick scan - just get first page to see if there are any events"""
    data = _get(f'/unique-tournament/{tid}/season/{sid}/events/last/0', cache_minutes=60)
    if not data:
        return 0
    events = []
    for key in ('events', 'tournamentMatches', 'matches'):
        if key in data:
            events = data[key]
            break
    return len(events)

print('='*60)
print('SOFASCORE TOURNAMENT EXPLORER')
print('='*60)

# Step 1: Get all categories
cats = get_categories()
print(f'\nCategories found: {len(cats)}')
for c in cats:
    print(f'  [{c["id"]}] {c["name"]}')

# Step 2: Get all tournaments in each category
all_tournaments = []
for cat in cats:
    tours = get_tournaments(cat['id'])
    all_tournaments.extend(tours)
    print(f'  {cat["name"]}: {len(tours)} tournaments')

print(f'\nTotal tournaments: {len(all_tournaments)}')

# Step 3: Get existing tournaments in DB
existing_ids = get_existing_tournaments()
print(f'Tournaments in DB: {len(existing_ids)}')
print(f'Tournaments NOT in DB: {len([t for t in all_tournaments if t["id"] not in existing_ids])}')

# Step 4: Scan each tournament for seasons
not_in_db = [t for t in all_tournaments if t['id'] not in existing_ids]
print(f'\nScanning {len(not_in_db)} unknown tournaments for seasons...')

found_seasons = []
for t in not_in_db[:50]:  # Limit to 50 to avoid too many API calls
    time.sleep(0.3)
    seasons = get_seasons(t['id'])
    if seasons:
        print(f'  [{t["id"]}] {t["name"]}: {len(seasons)} seasons (recent: {seasons[-1]["year"]})')
        for s in seasons:
            if s['year_num'] >= 2012:
                event_count = scan_events(t['id'], s['id'])
                if event_count > 0:
                    found_seasons.append({**t, 'season': s, 'events_page1': event_count})
                    print(f'    Season {s["year"]} (id={s["id"]}): ~{event_count}e+')
    else:
        pass  # No seasons - skip

print(f'\nFound {len(found_seasons)} new tournament-seasons with events!')
print(f'Estimated new matches: {sum(f["events_page1"] for f in found_seasons)}+')

# Save results
output = {
    'categories': cats,
    'total_tournaments': len(all_tournaments),
    'in_db': list(existing_ids),
    'new_tournaments_with_data': found_seasons,
}
json.dump(output, open(os.path.join(os.path.dirname(__file__), 'models', 'sofascore_explorer.json'), 'w'), indent=2)
print(f'\nSaved to models/sofascore_explorer.json')
