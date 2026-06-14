"""Explore match details and xG data"""
import requests, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) Chrome/120 Mobile',
    'Accept': 'application/json',
}
build_id = 'UkUOCnsJno2QeGq1r_43R'

# Get fresh league overview
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/leagues/47.json',
    params={'tab': 'overview', 'type': 'league'},
    headers=headers, timeout=15
)
pp = r.json().get('pageProps', {})

overview_matches = pp.get('overview', {}).get('leagueOverviewMatches', [])
print(f'Total matches: {len(overview_matches)}')

# Show first 5
for m in overview_matches[:5]:
    mid = m.get('id')
    home = m.get('home', {}).get('name', '?')
    away = m.get('away', {}).get('name', '?')
    hs = m.get('home', {}).get('score')
    aws = m.get('away', {}).get('score')
    status = m.get('status', {})
    date = m.get('matchDateUTC', m.get('dateUTC', '?'))
    print(f'{mid} {date} {home} {hs}-{aws} {away} status={status.get("short","?")}')

# Pick first match (likely most recent)
mid = overview_matches[0]['id']
print(f'\n\n=== Match {mid} ===')
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/matches/{mid}.json',
    headers=headers, timeout=15
)
data = r.json()
pp2 = data.get('pageProps', {})

# Save
with open('fotmob_match.json', 'w') as f:
    json.dump(pp2, f, indent=2)
print(f'Saved fotmob_match.json ({len(json.dumps(pp2))} bytes)')

# Show structure
for k in pp2:
    v = pp2[k]
    if isinstance(v, dict):
        vkeys = list(v.keys())[:15]
        vsize = len(json.dumps(v))
        print(f'{k}: dict keys={vkeys} size={vsize}')
    elif isinstance(v, list):
        print(f'{k}: list len={len(v)}')
    else:
        print(f'{k}: {type(v).__name__}={str(v)[:80]}')
