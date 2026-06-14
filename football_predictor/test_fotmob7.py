"""Extract FotMob data from Next.js data routes"""
import requests, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) Chrome/120 Mobile',
    'Accept': 'application/json',
}

build_id = 'UkUOCnsJno2QeGq1r_43R'

# 1. Matches by date
print('=== Matches by date ===')
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/matches.json',
    params={'date': '20260613'},
    headers=headers, timeout=15
)
data = r.json()
page_props = data.get('pageProps', {})
matches_data = page_props.get('matches', page_props.get('data', {}))
print(f'Top keys: {list(data.keys())}')
print(f'pageProps keys: {list(page_props.keys())[:10]}')

# Find the matches
leagues = matches_data if isinstance(matches_data, list) else matches_data.get('leagues', [])
if not leagues:
    # Search deeper
    for k, v in page_props.items():
        if isinstance(v, dict) and len(str(v)) > 1000:
            print(f'  pageProps.{k}: dict keys={list(v.keys())[:10]}')
        elif isinstance(v, list) and len(v) > 0:
            print(f'  pageProps.{k}: list len={len(v)}')
else:
    print(f'leagues: {len(leagues)}')
    for l in leagues[:3]:
        name = l.get('leagueName', l.get('name', '?'))
        matches = l.get('matches', [])
        print(f'  {name}: {len(matches)} matches')
        for m in matches[:2]:
            home = m.get('home', {}).get('name', '?')
            away = m.get('away', {}).get('name', '?')
            print(f'    {home} vs {away}')

# 2. Match details page
print('\n=== Match details ===')
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/matches/4216652.json',
    headers=headers, timeout=15
)
data = r.json()
pp = data.get('pageProps', {})
print(f'pageProps keys: {list(pp.keys())[:15]}')
for k in ['matchDetails', 'match', 'data', 'general']:
    if k in pp:
        v = pp[k]
        if isinstance(v, dict):
            print(f'  {k}: {list(v.keys())[:10]}')

# 3. League page
print('\n=== League ===')
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/leagues/47.json',
    params={'tab': 'overview', 'type': 'league'},
    headers=headers, timeout=15
)
data = r.json()
pp = data.get('pageProps', {})
print(f'pageProps keys: {list(pp.keys())[:10]}')

# 4. Team page
print('\n=== Team ===')
r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/teams/9851.json',
    headers=headers, timeout=15
)
data = r.json()
pp = data.get('pageProps', {})
print(f'pageProps keys: {list(pp.keys())[:10]}')
