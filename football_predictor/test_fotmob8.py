"""Deep FotMob data extraction"""
import requests, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) Chrome/120 Mobile',
    'Accept': 'application/json',
}
build_id = 'UkUOCnsJno2QeGq1r_43R'

# League 47 (Premier League) data
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/leagues/47.json',
    params={'tab': 'overview', 'type': 'league'},
    headers=headers, timeout=15
)
data = r.json()
pp = data.get('pageProps', {})

# Check each key
for k in ['table', 'fixtures', 'overview', 'details', 'stats']:
    v = pp.get(k)
    if v:
        if isinstance(v, dict):
            keys = list(v.keys())[:5]
            size = len(json.dumps(v))
            print(f'{k}: dict keys={keys}  ({size} bytes)')
        elif isinstance(v, list):
            print(f'{k}: list len={len(v)}')

# Extract table
table = pp.get('table', {})
if table:
    all_tables = table.get('allTables', [])
    print(f'\n=== Table: {len(all_tables)} tables ===')
    for tbl in all_tables[:2]:
        rows = tbl.get('rows', tbl.get('table', []))
        print(f'  L{tbl.get("id","?")}: {len(rows)} teams')
        for row in rows[:3]:
            name = row.get('name', row.get('team', {}).get('name', '?'))
            pts = row.get('pts', row.get('points', '?'))
            print(f'    {name}: {pts} pts')

# Extract fixtures
fixtures = pp.get('fixtures', {})
if fixtures:
    all_f = fixtures.get('allFixtures', fixtures.get('matches', []))
    print(f'\n=== Fixtures: {len(all_f) if isinstance(all_f, list) else "?"} ===')
    if isinstance(all_f, dict):
        for k, v in list(all_f.items())[:3]:
            print(f'  {k}: {len(v) if isinstance(v,list) else type(v).__name__}')

# Try a team data with fallback
print('\n=== Team data via API ===')
# Not sure if this works, let's try fetching the team page server props
r = requests.get(
    f'https://www.fotmob.com/api/teamData?id=9851',
    headers=headers, timeout=15
)
print(f'/api/teamData: {r.status_code}')
if r.status_code == 200:
    print(json.dumps(r.json(), indent=2)[:500])

# Try different match ID
for mid in ['4216652', '4190289']:
    r = requests.get(
        f'https://www.fotmob.com/_next/data/{build_id}/matches/{mid}.json',
        headers=headers, timeout=15
    )
    pp = r.json().get('pageProps', {})
    if pp:
        print(f'\nMatch {mid}: pageProps keys={list(pp.keys())[:10]}')
    else:
        print(f'\nMatch {mid}: empty pageProps')
