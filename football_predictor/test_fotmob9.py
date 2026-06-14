"""Extract fixtures and match data from FotMob"""
import requests, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) Chrome/120 Mobile',
    'Accept': 'application/json',
}
build_id = 'UkUOCnsJno2QeGq1r_43R'

r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/leagues/47.json',
    params={'tab': 'overview', 'type': 'league'},
    headers=headers, timeout=15
)
data = r.json()
pp = data.get('pageProps', {})

# 1. Fixtures
fixtures = pp.get('fixtures', {})
all_matches = fixtures.get('allMatches', {})
print(f'=== Fixtures ===')
print(f'firstUnplayedMatch: {fixtures.get("firstUnplayedMatch")}')
print(f'allMatches rounds: {list(all_matches.keys())[:5]}')
for round_key, matches in list(all_matches.items())[:3]:
    print(f'\n  Round {round_key}: {len(matches)} matches')
    for m in matches[:3]:
        home = m.get('home', {}).get('name', '?')
        away = m.get('away', {}).get('name', '?')
        status = m.get('status', {}).get('reason', '?')
        score = f'{m.get("home",{}).get("score","")} - {m.get("away",{}).get("score","")}'
        mid = m.get('id', '?')
        date = m.get('matchDateUTC', m.get('dateUTC', '?'))
        print(f'    {date} {home} vs {away} [{score}] ({mid})')

# 2. Get a specific match
print(f'\n\n=== Specific match: {fixtures.get("firstUnplayedMatch")} ===')
mid = fixtures.get('firstUnplayedMatch')
if mid:
    r = requests.get(
        f'https://www.fotmob.com/_next/data/{build_id}/matches/{mid}.json',
        headers=headers, timeout=15
    )
    md = r.json()
    pp2 = md.get('pageProps', {})
    print(f'pageProps keys: {list(pp2.keys())[:15]}')
    for k in pp2:
        v = pp2[k]
        if isinstance(v, dict):
            print(f'  {k}: dict keys={list(v.keys())[:10]} size={len(json.dumps(v))}')
        elif isinstance(v, list):
            print(f'  {k}: list len={len(v)}')

# 3. Table
table_list = pp.get('table', [])
print(f'\n=== Table ({len(table_list)} tables) ===')
for tbl in table_list:
    rows = tbl.get('rows', tbl.get('table', []))
    lname = tbl.get('leagueName', tbl.get('name', '?'))
    print(f'  {lname}: {len(rows)} teams')
    for row in rows[:5]:
        t = row.get('team', {})
        name = t.get('name', row.get('name', '?'))
        pts = row.get('pts', '?')
        print(f'    {name}: {pts} pts')

# 4. Check if we can get team matches from league data
stats = pp.get('stats', {})
print(f'\n=== Stats ===')
print(f'stats keys: {list(stats.keys())}')
teams = stats.get('teams', {})
if teams:
    print(f'  teams keys: {list(teams.keys())[:5]}')
    # last item might be the data
    for k in teams:
        v = teams[k]
        if isinstance(v, list) and len(v) > 10:
            print(f'  teams.{k}: list {len(v)} items')
            print(f'    first: {json.dumps(v[0], indent=2)[:200]}')
        elif isinstance(v, dict) and len(v) > 5:
            print(f'  teams.{k}: dict {len(v)} keys')
