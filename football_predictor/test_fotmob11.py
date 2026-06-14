"""Explore match details and xG data"""
import requests, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) Chrome/120 Mobile',
    'Accept': 'application/json',
}
build_id = 'UkUOCnsJno2QeGq1r_43R'

# Get fresh league overview to find an unplayed match with date
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/leagues/47.json',
    params={'tab': 'overview', 'type': 'league'},
    headers=headers, timeout=15
)
pp = r.json().get('pageProps', {})

# Get all matches and find future ones if any, otherwise pick a recent one
overview_matches = pp.get('overview', {}).get('leagueOverviewMatches', [])
future = [m for m in overview_matches if m.get('status', {}).get('short') != 'FT']
print(f'Future matches: {len(future)}')
played = [m for m in overview_matches if m.get('status', {}).get('short') == 'FT']
print(f'Played matches: {len(played)}')

# Pick a match to inspect - find one with score
for m in overview_matches:
    if m.get('status', {}).get('short') == 'FT':
        mid = m.get('id')
        home = m.get('home', {}).get('name', '?')
        away = m.get('away', {}).get('name', '?')
        hs = m.get('home', {}).get('score', '?')
        aws = m.get('away', {}).get('score', '?')
        date = m.get('matchDateUTC', m.get('dateUTC', '?'))
        print(f'\nTarget match: {mid} {date} {home} {hs}-{aws} {away}')
        break

# Fetch match details
mid = mid or 4813374
print(f'\n\n=== Match {mid} ===')
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/matches/{mid}.json',
    headers=headers, timeout=15
)
data = r.json()
pp2 = data.get('pageProps', {})

# Save full response for inspection
with open('fotmob_match.json', 'w') as f:
    json.dump(pp2, f, indent=2)
print(f'Saved to fotmob_match.json ({len(json.dumps(pp2))} bytes)')

# Check content
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
